"""Seed realistic local demo records through the public davdeploy API.

This script is local-fixture only. It creates no AWS resources, stores no secrets,
and performs no GitHub writes. It is intended to make a fresh local UI feel useful
immediately after `make bootstrap-local`.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from typing import Any

import httpx

BASE = os.environ.get("DAVDEPLOY_API_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
PROMPT = (
    "Deploy this small FastAPI AI application in AWS. It receives about 2 requests per "
    "second and may peak at 10. Keep it private where practical. Keep infrastructure "
    "below $300/month. Create staging and production. Enable Prometheus and Grafana "
    "monitoring."
)


def token(client: httpx.Client, username: str) -> str:
    response = client.post(f"{BASE}/api/v1/auth/local-login", json={"username": username})
    response.raise_for_status()
    return response.json()["access_token"]


def auth(value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {value}"}


def expect(response: httpx.Response, description: str, status: int = 200) -> dict[str, Any]:
    if response.status_code != status:
        raise RuntimeError(
            f"{description}: expected {status}, got {response.status_code}: {response.text}"
        )
    return response.json()


def create_review(
    client: httpx.Client,
    actor: str,
    label: str,
    cloud_connection_id: str | None,
    prompt: str = PROMPT,
) -> dict[str, Any]:
    suffix = f"{label}-{uuid.uuid4().hex[:7]}"
    repository = f"https://github.com/example/{label}"
    project = expect(
        client.post(
            f"{BASE}/api/v1/projects",
            headers=auth(actor),
            json={"name": suffix, "repository_url": repository, "repository_branch": "main"},
        ),
        f"create {label} project",
        201,
    )
    expect(
        client.get(f"{BASE}/api/v1/projects/{project['id']}/repository-discovery", headers=auth(actor)),
        f"inspect {label} repository fixture",
    )
    intent = expect(
        client.post(
            f"{BASE}/api/v1/intents",
            headers=auth(actor),
            json={
                "project_id": project["id"],
                "prompt": prompt,
                "source_repository": repository,
                "cloud_connection_id": cloud_connection_id,
                "idempotency_key": suffix,
            },
        ),
        f"create {label} intent",
        201,
    )
    deployment = expect(
        client.post(f"{BASE}/api/v1/intents/{intent['id']}/plans", headers=auth(actor)),
        f"create {label} plan",
        201,
    )
    return expect(
        client.post(
            f"{BASE}/api/v1/deployment-plans/{deployment['id']}/customer-review",
            headers=auth(actor),
        ),
        f"create {label} review",
        201,
    )


def submit(client: httpx.Client, actor: str, review: dict[str, Any]) -> dict[str, Any]:
    return expect(
        client.post(
            f"{BASE}/api/v1/customer-plan-revisions/{review['id']}/submit",
            headers=auth(actor),
        ),
        "submit review",
    )


def decide(
    client: httpx.Client,
    actor: str,
    review: dict[str, Any],
    decision: str,
    reason: str | None = None,
) -> dict[str, Any]:
    payload = {"decision": decision, "content_digest": review["content_digest"]}
    if reason:
        payload["reason"] = reason
    return expect(
        client.post(
            f"{BASE}/api/v1/customer-plan-revisions/{review['id']}/decisions",
            headers=auth(actor),
            json=payload,
        ),
        f"{decision.lower()} review",
    )


def wait_for_revision_environments(
    client: httpx.Client,
    actor: str,
    revision_id: str,
    expected: set[str],
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
        if last and {item["state"] for item in last}.issubset(expected):
            return last
        time.sleep(0.5)
    raise RuntimeError(f"seeded dry-run environments did not reach {expected}: {last}")


def record_readiness_artifacts(
    client: httpx.Client,
    developer: str,
    administrator: str,
    approved: dict[str, Any],
) -> dict[str, Any]:
    publication = expect(
        client.post(
            f"{BASE}/api/v1/customer-plan-revisions/{approved['id']}/desired-state-publications",
            headers=auth(developer),
            json={"content_digest": approved["content_digest"]},
        ),
        "seed fixture desired-state PR",
    )
    checked = expect(
        client.post(
            f"{BASE}/api/v1/customer-plan-revisions/{approved['id']}/desired-state-publications/{publication['id']}/state",
            headers=auth(administrator),
            json={"content_digest": approved["content_digest"], "state": "CHECKS_PASSED"},
        ),
        "seed fixture desired-state checks",
    )
    render = expect(
        client.post(
            f"{BASE}/api/v1/customer-plan-revisions/{approved['id']}/terraform-plan-renders",
            headers=auth(developer),
            json={"content_digest": approved["content_digest"]},
        ),
        "seed App Runner Terraform contract",
    )
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
        "seed cloud-readiness preflight",
    )
    plan_review = expect(
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
        "seed Terraform plan-only review",
    )
    return {
        "desired_state_publication_id": publication["id"],
        "desired_state_publication_state": checked["state"],
        "terraform_render_id": render["id"],
        "cloud_readiness_preflight_id": preflight["id"],
        "cloud_readiness_state": preflight["state"],
        "terraform_plan_review_id": plan_review["id"],
        "terraform_plan_review_state": plan_review["state"],
    }


def seed(run_dry_run: bool) -> dict[str, Any]:
    with httpx.Client(timeout=20) as client:
        developer = token(client, "founder")
        administrator = token(client, "administrator")
        cloud = expect(
            client.post(
                f"{BASE}/api/v1/cloud-connections",
                headers=auth(developer),
                json={"display_name": f"Demo AWS fixture {uuid.uuid4().hex[:6]}"},
            ),
            "create demo AWS fixture connection",
            201,
        )

        draft = create_review(client, developer, "demo-draft-plan", None)
        submitted = submit(client, developer, create_review(client, developer, "demo-submitted-plan", None))
        approved = decide(
            client,
            administrator,
            submit(client, developer, create_review(client, developer, "demo-approved-plan", None)),
            "APPROVED",
        )
        rejected = decide(
            client,
            administrator,
            submit(client, developer, create_review(client, developer, "demo-rejected-plan", None)),
            "REJECTED",
            "Seeded rejection: tighten the data-store assumption before resubmitting.",
        )
        admin_self_approved = decide(
            client,
            administrator,
            submit(
                client,
                administrator,
                create_review(client, administrator, "demo-admin-self-approved", None),
            ),
            "APPROVED",
        )
        readiness = record_readiness_artifacts(client, developer, administrator, approved)

        dry_run_environments: list[dict[str, Any]] = []
        if run_dry_run:
            expect(
                client.post(
                    f"{BASE}/api/v1/customer-plan-revisions/{approved['id']}/execute-dry-run",
                    headers=auth(developer),
                ),
                "execute seeded local dry run",
            )
            dry_run_environments = wait_for_revision_environments(
                client, developer, approved["id"], {"READY"}
            )

        return {
            "cloud_connection_id": cloud["id"],
            "draft_revision_id": draft["id"],
            "submitted_revision_id": submitted["id"],
            "approved_revision_id": approved["id"],
            "rejected_revision_id": rejected["id"],
            "admin_self_approved_revision_id": admin_self_approved["id"],
            **readiness,
            "dry_run_environment_ids": [item["id"] for item in dry_run_environments],
            "boundary": (
                "Local fixture seed only. No AWS resources, GitHub writes, authenticated "
                "Terraform plan/apply, Kubernetes or GitOps execution occurred."
            ),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-dry-run",
        action="store_true",
        help="Seed plan states without queueing the local fixture executor.",
    )
    args = parser.parse_args()
    print(json.dumps(seed(run_dry_run=not args.skip_dry_run), indent=2))


if __name__ == "__main__":
    main()
