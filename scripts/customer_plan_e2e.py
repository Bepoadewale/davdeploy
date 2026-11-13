"""Deterministic two-user proof for the customer-plan product workflow.

This uses separate HTTP clients as the local developer and administrator browser
sessions would. It exercises plan creation, approval/rejection, administrator
self-approval, approved-plan local dry-run execution, governed local destroy and
restart persistence. It never calls AWS, Terraform, Kubernetes or GitHub writes.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

BASE = os.environ.get("DAVDEPLOY_API_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
PROMPT = (
    "Deploy this small containerized FastAPI AI API in AWS. Support 2 requests per second "
    "and peak at 10 requests per second. Keep monthly infrastructure under $300. "
    "Create staging and production. Enable monitoring."
)


def token(client: httpx.Client, username: str) -> str:
    response = client.post(f"{BASE}/api/v1/auth/local-login", json={"username": username})
    response.raise_for_status()
    return response.json()["access_token"]


def auth(value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {value}"}


def expect(response: httpx.Response, status: int, description: str) -> dict[str, Any]:
    if response.status_code != status:
        raise AssertionError(
            f"{description}: expected {status}, got {response.status_code}: {response.text}"
        )
    return response.json()


def create_review(client: httpx.Client, actor: str, label: str, prompt: str = PROMPT) -> dict[str, Any]:
    suffix = f"{label}-{uuid.uuid4().hex[:8]}"
    repository = f"https://github.com/example/{label}"
    project = expect(
        client.post(
            f"{BASE}/api/v1/projects",
            headers=auth(actor),
            json={"name": suffix, "repository_url": repository, "repository_branch": "main"},
        ),
        201,
        "create project",
    )
    intent = expect(
        client.post(
            f"{BASE}/api/v1/intents",
            headers=auth(actor),
            json={
                "project_id": project["id"],
                "prompt": prompt,
                "source_repository": repository,
                "idempotency_key": suffix,
            },
        ),
        201,
        "create intent",
    )
    deployment = expect(
        client.post(f"{BASE}/api/v1/intents/{intent['id']}/plans", headers=auth(actor)),
        201,
        "create deployment recommendation",
    )
    review = expect(
        client.post(
            f"{BASE}/api/v1/deployment-plans/{deployment['id']}/customer-review",
            headers=auth(actor),
        ),
        201,
        "create customer review",
    )
    assert review["state"] == "DRAFT"
    assert review["content"]["summary"]["selected_profile"] == "aws-app-runner"
    observability = review["content"]["observability"]
    assert observability["metrics_backend"].startswith("Prometheus")
    assert observability["dashboard"] == "Amazon Managed Grafana"
    return review


def submit(client: httpx.Client, actor: str, revision_id: str) -> dict[str, Any]:
    review = expect(
        client.post(
            f"{BASE}/api/v1/customer-plan-revisions/{revision_id}/submit", headers=auth(actor)
        ),
        200,
        "submit customer review",
    )
    assert review["state"] == "SUBMITTED"
    assert review["execution"] == "UNEXECUTED_APPROVAL_ONLY"
    return review


def decide(
    client: httpx.Client, actor: str, review: dict[str, Any], decision: str, reason: str | None = None
) -> httpx.Response:
    payload = {"decision": decision, "content_digest": review["content_digest"]}
    if reason:
        payload["reason"] = reason
    return client.post(
        f"{BASE}/api/v1/customer-plan-revisions/{review['id']}/decisions",
        headers=auth(actor),
        json=payload,
    )


def wait_for_environments(
    client: httpx.Client,
    actor: str,
    revision_id: str,
    expected_states: set[str],
    timeout_seconds: int = 20,
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout_seconds
    last: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        response = client.get(f"{BASE}/api/v1/environments", headers=auth(actor))
        response.raise_for_status()
        last = [
            item
            for item in response.json()
            if item.get("customer_plan_revision_id") == revision_id
        ]
        if last and {item["state"] for item in last}.issubset(expected_states):
            return last
        time.sleep(0.5)
    raise AssertionError(f"environment states did not reach {expected_states}: {last}")


def execute_and_destroy_local_dry_run(
    client: httpx.Client, developer: str, administrator: str, approved: dict[str, Any]
) -> list[dict[str, Any]]:
    queued = expect(
        client.post(
            f"{BASE}/api/v1/customer-plan-revisions/{approved['id']}/execute-dry-run",
            headers=auth(developer),
        ),
        200,
        "execute approved local dry run",
    )
    assert queued["execution"] == "LOCAL_DRY_RUN"
    assert {item["state"] for item in queued["environments"]} == {"QUEUED"}
    observed = wait_for_environments(client, developer, approved["id"], {"READY"})
    assert {item["type"] for item in observed} == {"staging", "production"}
    assert all(item["execution_mode"] == "LOCAL_DRY_RUN" for item in observed)
    assert all(item["cost_estimate"] for item in observed)
    production = next(item for item in observed if item["type"] == "production")

    destroy = expect(
        client.post(
            f"{BASE}/api/v1/customer-plan-revisions/{approved['id']}/environments/{production['id']}/destroy-dry-run",
            headers=auth(developer),
        ),
        200,
        "create local destroy plan",
    )
    assert destroy["state"] == "DESTROY_APPROVAL_REQUIRED"
    expect(
        client.post(
            f"{BASE}/api/v1/deployment-plans/{destroy['id']}/approve",
            headers=auth(administrator),
            json={"plan_hash": destroy["plan_hash"]},
        ),
        200,
        "administrator approves local destroy",
    )
    destroyed = expect(
        client.post(
            f"{BASE}/api/v1/deployment-plans/{destroy['id']}/execute",
            headers=auth(administrator),
        ),
        200,
        "execute local destroy",
    )
    assert destroyed["environments"][0]["state"] == "DESTROY_REQUESTED"
    final = wait_for_environments(client, developer, approved["id"], {"READY", "DESTROYED"})
    assert any(item["state"] == "DESTROYED" for item in final)
    return final


def record_plan_only_readiness(
    client: httpx.Client, developer: str, administrator: str, approved: dict[str, Any]
) -> dict[str, Any]:
    publication = expect(
        client.post(
            f"{BASE}/api/v1/customer-plan-revisions/{approved['id']}/desired-state-publications",
            headers=auth(developer),
            json={"content_digest": approved["content_digest"]},
        ),
        200,
        "create fixture desired-state PR",
    )
    assert publication["state"] == "PUBLISHED"
    checks = expect(
        client.post(
            f"{BASE}/api/v1/customer-plan-revisions/{approved['id']}/desired-state-publications/{publication['id']}/state",
            headers=auth(administrator),
            json={"content_digest": approved["content_digest"], "state": "CHECKS_PASSED"},
        ),
        200,
        "record fixture desired-state checks",
    )
    assert checks["state"] == "CHECKS_PASSED"
    render = expect(
        client.post(
            f"{BASE}/api/v1/customer-plan-revisions/{approved['id']}/terraform-plan-renders",
            headers=auth(developer),
            json={"content_digest": approved["content_digest"]},
        ),
        200,
        "render App Runner Terraform contract",
    )
    assert render["profile"] == "aws-app-runner"
    assert render["render"]["apply_command_available"] is False
    preflight = expect(
        client.post(
            f"{BASE}/api/v1/customer-plan-revisions/{approved['id']}/cloud-readiness-preflights",
            headers=auth(administrator),
            json={
                "content_digest": approved["content_digest"],
                "expected_account_id": None,
                "allowed_regions": ["us-east-1"],
                "required_tags": {"ManagedBy": "davdeploy"},
                "budget_ceiling_usd": 1000,
                "execution_mode": "PLAN_ONLY",
                "require_reviewed_pr": True,
                "runtime_identity_configured": True,
            },
        ),
        200,
        "run cloud-readiness preflight",
    )
    assert preflight["state"] == "READY_FOR_AUTHORIZED_CLOUD_PLAN"
    review = expect(
        client.post(
            f"{BASE}/api/v1/customer-plan-revisions/{approved['id']}/terraform-plan-reviews",
            headers=auth(administrator),
            json={
                "content_digest": approved["content_digest"],
                "preflight_id": preflight["id"],
                "expected_account_id": None,
                "expected_region": "us-east-1",
                "mode": "LOCAL_CONTRACT_ONLY",
                "allow_cloud_plan": False,
            },
        ),
        200,
        "record Terraform plan-only review",
    )
    assert review["state"] == "LOCAL_CONTRACT_PLAN_REVIEWED"
    assert review["apply_available"] is False
    assert all(" apply" not in command for command in review["command"]["commands"])
    return review


def run(state_file: Path) -> None:
    with httpx.Client(timeout=15) as client:
        developer = token(client, "founder")
        administrator = token(client, "administrator")
        other_tenant = token(client, "other-tenant")

        developer_review = submit(
            client, developer, create_review(client, developer, "developer-approval")["id"]
        )
        assert decide(client, developer, developer_review, "APPROVED").status_code == 403
        assert (
            decide(
                client,
                administrator,
                {**developer_review, "content_digest": "0" * 64},
                "APPROVED",
            ).status_code
            == 409
        )
        approved = expect(decide(client, administrator, developer_review, "APPROVED"), 200, "admin approval")
        assert approved["state"] == "APPROVED"
        assert approved["decision"]["is_self_approval"] is False
        assert decide(client, administrator, approved, "APPROVED").status_code == 409
        assert client.get(
            f"{BASE}/api/v1/customer-plan-revisions/{approved['id']}", headers=auth(other_tenant)
        ).status_code == 403

        plan_review = record_plan_only_readiness(client, developer, administrator, approved)
        final_environments = execute_and_destroy_local_dry_run(
            client, developer, administrator, approved
        )

        failure = submit(
            client,
            developer,
            create_review(
                client,
                developer,
                "developer-readiness-failure",
                f"{PROMPT} Force failure local readiness evidence.",
            )["id"],
        )
        failure = expect(decide(client, administrator, failure, "APPROVED"), 200, "admin failure approval")
        expect(
            client.post(
                f"{BASE}/api/v1/customer-plan-revisions/{failure['id']}/execute-dry-run",
                headers=auth(developer),
            ),
            200,
            "execute failure dry run",
        )
        failed = wait_for_environments(client, developer, failure["id"], {"FAILED"})
        assert failed and {item["state"] for item in failed} == {"FAILED"}

        rejected = submit(
            client, developer, create_review(client, developer, "developer-rejection")["id"]
        )
        rejected = expect(
            decide(client, administrator, rejected, "REJECTED", "Use a lower-risk data store."),
            200,
            "admin rejection",
        )
        assert rejected["state"] == "REJECTED"
        assert rejected["decision"]["reason"] == "Use a lower-risk data store."
        revised = expect(
            client.post(
                f"{BASE}/api/v1/customer-plans/{rejected['plan_id']}/revisions",
                headers=auth(developer),
                json={"content": rejected["content"]},
            ),
            201,
            "create revised draft",
        )
        assert revised["revision"] == 2 and revised["state"] == "DRAFT"

        admin_review = submit(
            client, administrator, create_review(client, administrator, "admin-self-approval")["id"]
        )
        self_approved = expect(
            decide(client, administrator, admin_review, "APPROVED"), 200, "administrator self-approval"
        )
        assert self_approved["state"] == "APPROVED"
        assert self_approved["decision"]["is_self_approval"] is True
        assert (
            self_approved["decision"]["authorization_policy"]
            == "workspace-administrator-self-approval-allowed"
        )

        audit = expect(client.get(f"{BASE}/api/v1/audit-evidence", headers=auth(developer)), 200, "audit evidence")
        actions = {event["action"] for event in audit}
        assert "desired_state.fixture_pr_published" in actions
        assert "desired_state.fixture_pr_state_recorded" in actions
        assert "terraform.plan_only_review_recorded" in actions
        assert "customer_plan.local_dry_run_queued" in actions
        assert "customer_plan.local_destroy_requested" in actions
        assert "environment.destroyed" in actions

        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(
            json.dumps(
                {
                    "revision_id": approved["id"],
                    "expected_state": "APPROVED",
                    "terraform_plan_review_id": plan_review["id"],
                    "destroyed_environment_id": next(
                        item["id"] for item in final_environments if item["state"] == "DESTROYED"
                    ),
                    "failure_revision_id": failure["id"],
                }
            )
            + "\n"
        )
        print(
            "customer-plan E2E passed: developer submission, admin decision, self-approval, "
            "local dry-run execution, readiness failure, governed destroy and audit"
        )


def verify_persistence(state_file: Path) -> None:
    state = json.loads(state_file.read_text())
    with httpx.Client(timeout=15) as client:
        developer = token(client, "founder")
        review = expect(
            client.get(
                f"{BASE}/api/v1/customer-plan-revisions/{state['revision_id']}", headers=auth(developer)
            ),
            200,
            "read persisted customer review",
        )
        environments = wait_for_environments(
            client, developer, state["revision_id"], {"READY", "DESTROYED"}
        )
    assert review["state"] == state["expected_state"]
    assert review["execution"] == "UNEXECUTED_APPROVAL_ONLY"
    assert any(item["id"] == state["destroyed_environment_id"] for item in environments)
    print("customer-plan persistence check passed after API restart")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--state-file",
        default=os.environ.get("DAVDEPLOY_CUSTOMER_PLAN_STATE_FILE", ".local/customer-plan-e2e.json"),
    )
    parser.add_argument("--verify-persistence", action="store_true")
    args = parser.parse_args()
    state_file = Path(args.state_file)
    if args.verify_persistence:
        verify_persistence(state_file)
    else:
        run(state_file)


if __name__ == "__main__":
    main()
