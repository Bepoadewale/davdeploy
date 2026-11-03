from __future__ import annotations

import json
from argparse import Namespace

from davdeploy.cli import run
from davdeploy.mcp import TOOL_DEFINITIONS, davdeployMcp, handle_request
from davdeploy.policy import PolicyClient
from davdeploy.security import LOCAL_USERS, Principal
from davdeploy.service import ProductService
from test_product import LocalExecutor, complete_prompt, founder, make_service


class RecordingClient:
    def __init__(self):
        self.calls: list[tuple[str, str, dict | None]] = []

    def request(self, method: str, path: str, payload: dict | None = None):
        self.calls.append((method, path, payload))
        if method == "GET" and path.startswith("/api/v1/deployment-plans/"):
            return {
                "id": "plan-1",
                "state": "APPROVAL_REQUIRED",
                "plan_hash": "a" * 64,
                "policy_result": "APPROVAL_REQUIRED",
                "payload": {
                    "architecture": {
                        "profile": "aws-app-runner",
                        "cost_estimate": {"monthly_low": 65, "monthly_high": 180},
                        "candidates": [{"candidate_id": "aws-app-runner"}],
                    }
                },
            }
        return {"ok": True}


def test_mcp_catalogue_exposes_governed_operations_and_only_customer_review_decisions():
    names = {tool["name"] for tool in TOOL_DEFINITIONS}
    assert {
        "analyze_workload",
        "plan_infrastructure",
        "get_plan",
        "create_customer_plan_review",
        "get_customer_plan_review",
        "submit_customer_plan_review",
        "decide_customer_plan_review",
        "execute_approved_customer_dry_run",
        "render_customer_terraform",
        "preflight_customer_cloud",
        "review_customer_terraform_plan",
        "create_customer_cloud_run",
        "queue_customer_cloud_run",
        "get_customer_cloud_run_evidence",
        "recommend_optimization",
        "create_change_plan",
        "destroy_environment",
    } <= names
    assert "approve_plan" not in names
    assert "approve_customer_plan_review" not in names
    assert all("credential" not in name for name in names)


def test_mcp_compares_candidates_and_preserves_api_authority():
    client = RecordingClient()
    result = davdeployMcp(client).call_tool("compare_architectures", {"plan_id": "plan-1"})
    assert result["selected"] == "aws-app-runner"
    assert client.calls == [("GET", "/api/v1/deployment-plans/plan-1", None)]


def test_mcp_day2_tools_only_request_governed_api_operations():
    client = RecordingClient()
    server = davdeployMcp(client)
    assert server.call_tool("recommend_optimization", {"environment_id": "env-1"}) == {"ok": True}
    assert server.call_tool("create_change_plan", {"environment_id": "env-1"}) == {"ok": True}
    assert client.calls == [
        ("GET", "/api/v1/environments/env-1/recommendation", None),
        ("POST", "/api/v1/environments/env-1/change-plan", None),
    ]


def test_mcp_customer_plan_tools_forward_an_explicit_governed_decision():
    client = RecordingClient()
    server = davdeployMcp(client)
    assert server.call_tool("create_customer_plan_review", {"plan_id": "plan-1"}) == {"ok": True}
    assert server.call_tool("get_customer_plan_review", {"revision_id": "revision-1"}) == {"ok": True}
    assert server.call_tool("submit_customer_plan_review", {"revision_id": "revision-1"}) == {
        "ok": True
    }
    assert server.call_tool(
        "decide_customer_plan_review",
        {
            "revision_id": "revision-1",
            "decision": "APPROVED",
            "content_digest": "a" * 64,
            "reason": "Administrator approved the exact reviewed digest.",
        },
    ) == {"ok": True}
    assert server.call_tool("execute_approved_customer_dry_run", {"revision_id": "revision-1"}) == {
        "ok": True
    }
    assert client.calls == [
        ("POST", "/api/v1/deployment-plans/plan-1/customer-review", None),
        ("GET", "/api/v1/customer-plan-revisions/revision-1", None),
        ("POST", "/api/v1/customer-plan-revisions/revision-1/submit", None),
        (
            "POST",
            "/api/v1/customer-plan-revisions/revision-1/decisions",
            {
                "decision": "APPROVED",
                "content_digest": "a" * 64,
                "reason": "Administrator approved the exact reviewed digest.",
            },
        ),
        ("POST", "/api/v1/customer-plan-revisions/revision-1/execute-dry-run", None),
    ]


def test_mcp_cloud_lifecycle_tools_only_forward_governed_contracts():
    client = RecordingClient()
    server = davdeployMcp(client)
    digest = "a" * 64
    assert server.call_tool(
        "render_customer_terraform", {"revision_id": "revision-1", "content_digest": digest}
    ) == {"ok": True}
    assert server.call_tool(
        "preflight_customer_cloud",
        {"revision_id": "revision-1", "content_digest": digest, "region": "us-east-1"},
    ) == {"ok": True}
    assert server.call_tool(
        "queue_customer_cloud_run",
        {"run_id": "run-1", "content_digest": digest, "confirmation": "bad"},
    ) == {"ok": True}
    assert client.calls == [
        (
            "POST",
            "/api/v1/customer-plan-revisions/revision-1/terraform-plan-renders",
            {"content_digest": digest},
        ),
        (
            "POST",
            "/api/v1/customer-plan-revisions/revision-1/cloud-readiness-preflights",
            {
                "content_digest": digest,
                "expected_account_id": None,
                "allowed_regions": ["us-east-1"],
                "required_tags": {"ManagedBy": "davdeploy"},
                "budget_ceiling_usd": None,
                "execution_mode": "PLAN_ONLY",
                "require_reviewed_pr": False,
                "runtime_identity_configured": False,
            },
        ),
        (
            "POST",
            "/api/v1/cloud-execution-runs/run-1/execute",
            {"content_digest": digest, "confirmation": "bad"},
        ),
    ]


def test_mcp_json_rpc_tools_list_and_error_shape_are_deterministic():
    server = davdeployMcp(RecordingClient())
    listed = handle_request(server, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert listed and listed["result"]["tools"] == TOOL_DEFINITIONS
    invalid = handle_request(
        server,
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "approve_plan"}},
    )
    assert invalid and invalid["result"]["isError"] is True
    assert "unknown MCP tool" in invalid["result"]["content"][0]["text"]
    assert json.loads(json.dumps(listed))["jsonrpc"] == "2.0"


def test_cli_forwards_analyze_request_without_creating_cloud_credentials():
    client = RecordingClient()
    result = run(
        Namespace(
            command="analyze-workload",
            project_id="project-1",
            prompt="Deploy a small AI API in AWS with a budget under $300.",
            repository="https://github.com/example/api",
            cloud_connection_id="connection-1",
            idempotency_key="agent-client-001",
        ),
        client,
    )
    assert result == {"ok": True}
    assert client.calls == [
        (
            "POST",
            "/api/v1/intents",
            {
                "project_id": "project-1",
                "prompt": "Deploy a small AI API in AWS with a budget under $300.",
                "source_repository": "https://github.com/example/api",
                "cloud_connection_id": "connection-1",
                "idempotency_key": "agent-client-001",
            },
        )
    ]


def test_cli_customer_plan_commands_forward_to_governed_api():
    client = RecordingClient()
    assert run(Namespace(command="create-customer-review", plan_id="plan-1"), client) == {
        "ok": True
    }
    assert run(Namespace(command="get-customer-review", revision_id="revision-1"), client) == {
        "ok": True
    }
    assert run(Namespace(command="submit-customer-review", revision_id="revision-1"), client) == {
        "ok": True
    }
    assert run(Namespace(command="execute-customer-dry-run", revision_id="revision-1"), client) == {
        "ok": True
    }
    assert run(Namespace(command="list-customer-reviews", state="submitted"), client) == {
        "ok": True
    }
    assert client.calls == [
        ("POST", "/api/v1/deployment-plans/plan-1/customer-review", None),
        ("GET", "/api/v1/customer-plan-revisions/revision-1", None),
        ("POST", "/api/v1/customer-plan-revisions/revision-1/submit", None),
        ("POST", "/api/v1/customer-plan-revisions/revision-1/execute-dry-run", None),
        ("GET", "/api/v1/admin/customer-plan-revisions?state=submitted", None),
    ]


def test_cli_cloud_lifecycle_commands_forward_exact_digests_only():
    client = RecordingClient()
    digest = "b" * 64
    assert run(
        Namespace(command="render-customer-terraform", revision_id="revision-1", content_digest=digest),
        client,
    ) == {"ok": True}
    assert run(
        Namespace(
            command="queue-customer-cloud-run",
            run_id="run-1",
            content_digest=digest,
            confirmation="EXECUTE_APP_RUNNER_WORKLOAD",
        ),
        client,
    ) == {"ok": True}
    assert client.calls == [
        (
            "POST",
            "/api/v1/customer-plan-revisions/revision-1/terraform-plan-renders",
            {"content_digest": digest},
        ),
        (
            "POST",
            "/api/v1/cloud-execution-runs/run-1/execute",
            {"content_digest": digest, "confirmation": "EXECUTE_APP_RUNNER_WORKLOAD"},
        ),
    ]


def test_cli_and_mcp_can_request_typed_serverless_certification_phases():
    digest = "e" * 64
    client = RecordingClient()
    cli_result = run(
        Namespace(
            command="create-customer-cloud-run",
            revision_id="revision-1",
            content_digest=digest,
            terraform_render_id=None,
            preflight_id=None,
            terraform_plan_review_id=None,
            expected_account_id="654654474502",
            region="us-east-1",
            confirmation=None,
            serverless_operation="build-artifact",
            prior_run_id=None,
            source_commit="a" * 40,
            destroy=False,
        ),
        client,
    )
    assert cli_result == {"ok": True}
    assert client.calls[-1] == (
        "POST",
        "/api/v1/customer-plan-revisions/revision-1/cloud-execution-runs",
        {
            "content_digest": digest,
            "terraform_render_id": None,
            "preflight_id": None,
            "terraform_plan_review_id": None,
            "expected_account_id": "654654474502",
            "expected_region": "us-east-1",
            "mode": "AUTHENTICATED_SERVERLESS_CERTIFICATION",
            "confirmation": None,
            "serverless_operation": "build-artifact",
            "prior_run_id": None,
            "source_commit": "a" * 40,
        },
    )

    mcp_client = RecordingClient()
    result = davdeployMcp(mcp_client).call_tool(
        "create_customer_cloud_run",
        {
            "revision_id": "revision-2",
            "content_digest": digest,
            "region": "us-east-1",
            "serverless_operation": "plan",
            "prior_run_id": "artifact-run-1",
        },
    )
    assert result == {"ok": True}
    assert mcp_client.calls[-1][2]["mode"] == "AUTHENTICATED_SERVERLESS_CERTIFICATION"
    assert mcp_client.calls[-1][2]["prior_run_id"] == "artifact-run-1"


def test_agent_read_interfaces_remain_tenant_scoped():
    service, db = make_service()
    project = service.create_project(founder(), "agent-read", "https://github.com/example/agent")
    intent = service.create_intent(
        founder(), project.id, complete_prompt(), None, None, "agent-read-interface-001"
    )
    plan = service.plan_intent(founder(), intent.id)
    assert service.get_plan(founder(), plan.id).id == plan.id
    subject, organization_id, role = LOCAL_USERS["other-tenant"]
    other = Principal(subject, organization_id, role)
    try:
        service.get_plan(other, plan.id)
    except PermissionError:
        pass
    else:
        raise AssertionError("agent read crossed tenant boundary")
    restarted = ProductService(db, policy=PolicyClient(fixture=True), executor=LocalExecutor())
    assert restarted.get_plan(founder(), plan.id).plan_hash == plan.plan_hash
