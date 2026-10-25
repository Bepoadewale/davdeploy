"""A small stdio MCP server exposing only governed davdeploy operations."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from davdeploy.client import ProductApiClient

MCP_TOOL_SCHEMA_VERSION = "v1"

TOOL_DEFINITIONS = [
    {
        "name": "analyze_workload",
        "description": "Turn a workload outcome into a typed request. It does not execute infrastructure.",
        "inputSchema": {
            "type": "object",
            "required": ["project_id", "prompt", "idempotency_key"],
            "properties": {
                "project_id": {"type": "string"},
                "prompt": {"type": "string"},
                "idempotency_key": {"type": "string"},
                "source_repository": {"type": "string"},
                "cloud_connection_id": {"type": "string"},
            },
        },
    },
    {
        "name": "plan_infrastructure",
        "description": "Create a policy-evaluated immutable plan from an interpreted workload.",
        "inputSchema": {
            "type": "object",
            "required": ["intent_id"],
            "properties": {"intent_id": {"type": "string"}},
        },
    },
    {
        "name": "compare_architectures",
        "description": "Return the selected architecture and alternatives from an existing immutable plan.",
        "inputSchema": {
            "type": "object",
            "required": ["plan_id"],
            "properties": {"plan_id": {"type": "string"}},
        },
    },
    {
        "name": "get_cost_estimate",
        "description": "Return the fixture cost estimate and assumptions from an existing plan. It is not actual AWS billing.",
        "inputSchema": {
            "type": "object",
            "required": ["plan_id"],
            "properties": {"plan_id": {"type": "string"}},
        },
    },
    {
        "name": "get_plan",
        "description": "Read a tenant-scoped immutable deployment plan.",
        "inputSchema": {
            "type": "object",
            "required": ["plan_id"],
            "properties": {"plan_id": {"type": "string"}},
        },
    },
    {
        "name": "get_approval_status",
        "description": "Read plan state and approval requirement. This server has no approval tool.",
        "inputSchema": {
            "type": "object",
            "required": ["plan_id"],
            "properties": {"plan_id": {"type": "string"}},
        },
    },
    {
        "name": "create_customer_plan_review",
        "description": "Create one customer-facing AWS review draft from an existing governed deployment plan. It does not submit, approve, or deploy.",
        "inputSchema": {
            "type": "object",
            "required": ["plan_id"],
            "properties": {"plan_id": {"type": "string"}},
        },
    },
    {
        "name": "get_customer_plan_review",
        "description": "Read a tenant-scoped customer-plan revision with its digest, status, cost, security, observability and audit context.",
        "inputSchema": {
            "type": "object",
            "required": ["revision_id"],
            "properties": {"revision_id": {"type": "string"}},
        },
    },
    {
        "name": "submit_customer_plan_review",
        "description": "Submit an exact customer-plan revision for human administrator review. It never approves or deploys.",
        "inputSchema": {
            "type": "object",
            "required": ["revision_id"],
            "properties": {"revision_id": {"type": "string"}},
        },
    },
    {
        "name": "execute_approved_customer_dry_run",
        "description": "Request the local bounded dry-run executor for an already approved customer-plan revision. API policy remains authoritative; no cloud credentials are returned.",
        "inputSchema": {
            "type": "object",
            "required": ["revision_id"],
            "properties": {"revision_id": {"type": "string"}},
        },
    },
    {
        "name": "render_customer_terraform",
        "description": "Render a Terraform contract for an approved customer-plan digest. It cannot plan, apply, or destroy cloud resources.",
        "inputSchema": {
            "type": "object",
            "required": ["revision_id", "content_digest"],
            "properties": {"revision_id": {"type": "string"}, "content_digest": {"type": "string"}},
        },
    },
    {
        "name": "preflight_customer_cloud",
        "description": "Run the governed preflight for an approved digest. It only evaluates boundaries and never changes cloud resources.",
        "inputSchema": {
            "type": "object",
            "required": ["revision_id", "content_digest", "region"],
            "properties": {
                "revision_id": {"type": "string"}, "content_digest": {"type": "string"},
                "region": {"type": "string"}, "expected_account_id": {"type": "string"},
                "budget_ceiling_usd": {"type": "integer"}, "runtime_identity_configured": {"type": "boolean"},
            },
        },
    },
    {
        "name": "review_customer_terraform_plan",
        "description": "Record a Terraform plan review for an approved digest. Authenticated planning remains backend-gated and never applies infrastructure.",
        "inputSchema": {
            "type": "object",
            "required": ["revision_id", "content_digest", "region"],
            "properties": {
                "revision_id": {"type": "string"}, "content_digest": {"type": "string"},
                "preflight_id": {"type": "string"}, "expected_account_id": {"type": "string"},
                "region": {"type": "string"}, "authenticated": {"type": "boolean"},
                "destroy": {"type": "boolean", "description": "Generate a reviewed Terraform destroy plan only."},
            },
        },
    },
    {
        "name": "create_customer_cloud_run",
        "description": "Create an approval-gated cloud execution request. It cannot queue or apply without all backend guards and exact confirmation.",
        "inputSchema": {
            "type": "object",
            "required": ["revision_id", "content_digest", "region"],
            "properties": {
                "revision_id": {"type": "string"}, "content_digest": {"type": "string"},
                "terraform_render_id": {"type": "string"}, "preflight_id": {"type": "string"},
                "terraform_plan_review_id": {"type": "string"}, "expected_account_id": {"type": "string"},
                "region": {"type": "string"}, "confirmation": {"type": "string"},
                "destroy": {"type": "boolean", "description": "Execute only a reviewed saved Terraform destroy plan."},
            },
        },
    },
    {
        "name": "build_customer_image",
        "description": "Build and push exactly one commit pinned from the repository already selected by an approved plan. This cannot create or update an App Runner service.",
        "inputSchema": {
            "type": "object",
            "required": ["revision_id", "content_digest", "region", "confirmation"],
            "properties": {
                "revision_id": {"type": "string"}, "content_digest": {"type": "string"},
                "expected_account_id": {"type": "string"}, "region": {"type": "string"},
                "confirmation": {"type": "string", "description": "Must be BUILD_CUSTOMER_IMAGE."},
            },
        },
    },
    {
        "name": "queue_customer_cloud_run",
        "description": "Queue an already-ready exact cloud execution request. The API independently verifies role, digest, policy, approval, and confirmation.",
        "inputSchema": {
            "type": "object",
            "required": ["run_id", "content_digest", "confirmation"],
            "properties": {"run_id": {"type": "string"}, "content_digest": {"type": "string"}, "confirmation": {"type": "string"}},
        },
    },
    {
        "name": "get_customer_cloud_run_evidence",
        "description": "Read tenant-scoped execution evidence, including observed outputs and destruction proof when available.",
        "inputSchema": {"type": "object", "required": ["run_id"], "properties": {"run_id": {"type": "string"}}},
    },
    {
        "name": "reconcile_customer_cloud_run_result",
        "description": "Replay only an administrator-authorized, completed runner result whose encrypted artifact could not previously be read. It never reruns Terraform.",
        "inputSchema": {"type": "object", "required": ["run_id"], "properties": {"run_id": {"type": "string"}}},
    },
    {
        "name": "execute_approved_plan",
        "description": "Ask the governed API to execute an already executable plan. API policy and exact-plan approval remain authoritative.",
        "inputSchema": {
            "type": "object",
            "required": ["plan_id"],
            "properties": {"plan_id": {"type": "string"}},
        },
    },
    {
        "name": "get_environment_status",
        "description": "Read independently observed environment state.",
        "inputSchema": {
            "type": "object",
            "required": ["environment_id"],
            "properties": {"environment_id": {"type": "string"}},
        },
    },
    {
        "name": "explain_environment",
        "description": "Read the tenant-scoped desired and independently observed state for an environment.",
        "inputSchema": {
            "type": "object",
            "required": ["environment_id"],
            "properties": {"environment_id": {"type": "string"}},
        },
    },
    {
        "name": "recommend_optimization",
        "description": "Return a non-mutating Day-2 recommendation from bounded local telemetry evidence.",
        "inputSchema": {
            "type": "object",
            "required": ["environment_id"],
            "properties": {"environment_id": {"type": "string"}},
        },
    },
    {
        "name": "create_change_plan",
        "description": "Create a governed immutable change plan. It does not approve or autonomously apply a protected change.",
        "inputSchema": {
            "type": "object",
            "required": ["environment_id"],
            "properties": {"environment_id": {"type": "string"}},
        },
    },
    {
        "name": "get_incidents",
        "description": "Read tenant-scoped Day-2 incident evidence for one environment.",
        "inputSchema": {
            "type": "object",
            "required": ["environment_id"],
            "properties": {"environment_id": {"type": "string"}},
        },
    },
    {
        "name": "get_audit_events",
        "description": "Read tenant-scoped audit events, optionally for one environment.",
        "inputSchema": {"type": "object", "properties": {"environment_id": {"type": "string"}}},
    },
    {
        "name": "destroy_environment",
        "description": "Create a governed destroy plan. It does not approve or execute protected deletion.",
        "inputSchema": {
            "type": "object",
            "required": ["environment_id"],
            "properties": {"environment_id": {"type": "string"}},
        },
    },
]


class davdeployMcp:
    def __init__(self, client: ProductApiClient):
        self.client = client

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if name == "analyze_workload":
            return self.client.request("POST", "/api/v1/intents", arguments)
        if name == "plan_infrastructure":
            return self.client.request("POST", f"/api/v1/intents/{arguments['intent_id']}/plans")
        if name in {
            "compare_architectures",
            "get_cost_estimate",
            "get_plan",
            "get_approval_status",
        }:
            plan = self.client.request("GET", f"/api/v1/deployment-plans/{arguments['plan_id']}")
            if name == "compare_architectures":
                return {
                    "selected": plan["payload"]["architecture"]["profile"],
                    "candidates": plan["payload"]["architecture"]["candidates"],
                }
            if name == "get_cost_estimate":
                return plan["payload"]["architecture"]["cost_estimate"]
            if name == "get_approval_status":
                return {key: plan[key] for key in ("id", "state", "plan_hash", "policy_result")}
            return plan
        if name == "create_customer_plan_review":
            return self.client.request(
                "POST", f"/api/v1/deployment-plans/{arguments['plan_id']}/customer-review"
            )
        if name == "get_customer_plan_review":
            return self.client.request(
                "GET", f"/api/v1/customer-plan-revisions/{arguments['revision_id']}"
            )
        if name == "submit_customer_plan_review":
            return self.client.request(
                "POST", f"/api/v1/customer-plan-revisions/{arguments['revision_id']}/submit"
            )
        if name == "execute_approved_customer_dry_run":
            return self.client.request(
                "POST", f"/api/v1/customer-plan-revisions/{arguments['revision_id']}/execute-dry-run"
            )
        if name == "render_customer_terraform":
            return self.client.request(
                "POST",
                f"/api/v1/customer-plan-revisions/{arguments['revision_id']}/terraform-plan-renders",
                {"content_digest": arguments["content_digest"]},
            )
        if name == "preflight_customer_cloud":
            return self.client.request(
                "POST",
                f"/api/v1/customer-plan-revisions/{arguments['revision_id']}/cloud-readiness-preflights",
                {
                    "content_digest": arguments["content_digest"],
                    "expected_account_id": arguments.get("expected_account_id"),
                    "allowed_regions": [arguments["region"]],
                    "required_tags": {"ManagedBy": "davdeploy"},
                    "budget_ceiling_usd": arguments.get("budget_ceiling_usd"),
                    "execution_mode": "PLAN_ONLY",
                    "require_reviewed_pr": False,
                    "runtime_identity_configured": bool(arguments.get("runtime_identity_configured")),
                },
            )
        if name == "review_customer_terraform_plan":
            authenticated = bool(arguments.get("authenticated"))
            return self.client.request(
                "POST",
                f"/api/v1/customer-plan-revisions/{arguments['revision_id']}/terraform-plan-reviews",
                {
                    "content_digest": arguments["content_digest"],
                    "preflight_id": arguments.get("preflight_id"),
                    "expected_account_id": arguments.get("expected_account_id"),
                    "expected_region": arguments["region"],
                    "mode": (
                        "AUTHENTICATED_TERRAFORM_DESTROY_PLAN"
                        if authenticated and bool(arguments.get("destroy"))
                        else "AUTHENTICATED_TERRAFORM_PLAN"
                        if authenticated
                        else "LOCAL_CONTRACT_ONLY"
                    ),
                    "allow_cloud_plan": authenticated,
                },
            )
        if name == "create_customer_cloud_run":
            return self.client.request(
                "POST",
                f"/api/v1/customer-plan-revisions/{arguments['revision_id']}/cloud-execution-runs",
                {
                    "content_digest": arguments["content_digest"],
                    "terraform_render_id": arguments.get("terraform_render_id"),
                    "preflight_id": arguments.get("preflight_id"),
                    "terraform_plan_review_id": arguments.get("terraform_plan_review_id"),
                    "expected_account_id": arguments.get("expected_account_id"),
                    "expected_region": arguments["region"],
                    "mode": "AUTHENTICATED_APP_RUNNER_DESTROY" if bool(arguments.get("destroy")) else "AUTHENTICATED_APP_RUNNER_APPLY",
                    "confirmation": arguments.get("confirmation"),
                },
            )
        if name == "build_customer_image":
            return self.client.request(
                "POST",
                f"/api/v1/customer-plan-revisions/{arguments['revision_id']}/customer-image-builds",
                {
                    "content_digest": arguments["content_digest"],
                    "expected_account_id": arguments.get("expected_account_id"),
                    "expected_region": arguments["region"],
                    "confirmation": arguments["confirmation"],
                },
            )
        if name == "queue_customer_cloud_run":
            return self.client.request(
                "POST",
                f"/api/v1/cloud-execution-runs/{arguments['run_id']}/execute",
                {"content_digest": arguments["content_digest"], "confirmation": arguments["confirmation"]},
            )
        if name == "get_customer_cloud_run_evidence":
            return self.client.request("GET", f"/api/v1/cloud-execution-runs/{arguments['run_id']}/evidence")
        if name == "reconcile_customer_cloud_run_result":
            return self.client.request("POST", f"/api/v1/cloud-execution-runs/{arguments['run_id']}/reconcile-result")
        if name == "execute_approved_plan":
            return self.client.request(
                "POST", f"/api/v1/deployment-plans/{arguments['plan_id']}/execute"
            )
        if name in {"get_environment_status", "explain_environment"}:
            return self.client.request("GET", f"/api/v1/environments/{arguments['environment_id']}")
        if name == "recommend_optimization":
            return self.client.request(
                "GET", f"/api/v1/environments/{arguments['environment_id']}/recommendation"
            )
        if name == "create_change_plan":
            return self.client.request(
                "POST", f"/api/v1/environments/{arguments['environment_id']}/change-plan"
            )
        if name == "get_incidents":
            return self.client.request("GET", f"/api/v1/environments/{arguments['environment_id']}/incidents")
        if name == "get_audit_events":
            suffix = (
                f"?environment_id={arguments['environment_id']}"
                if arguments.get("environment_id")
                else ""
            )
            return self.client.request("GET", f"/api/v1/audit-events{suffix}")
        if name == "destroy_environment":
            return self.client.request(
                "POST", f"/api/v1/environments/{arguments['environment_id']}/destroy-plan"
            )
        raise ValueError(f"unknown MCP tool: {name}")


def handle_request(server: davdeployMcp, request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        result = {
            "protocolVersion": request.get("params", {}).get("protocolVersion", "2025-03-26"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "davdeploy", "version": "0.1.0", "toolSchemaVersion": MCP_TOOL_SCHEMA_VERSION},
        }
    elif method == "tools/list":
        result = {"schemaVersion": MCP_TOOL_SCHEMA_VERSION, "tools": TOOL_DEFINITIONS}
    elif method == "tools/call":
        params = request.get("params", {})
        try:
            payload = server.call_tool(params["name"], params.get("arguments", {}))
            result = {"content": [{"type": "text", "text": json.dumps(payload, default=str)}]}
        except (KeyError, ValueError, RuntimeError) as error:
            result = {"content": [{"type": "text", "text": str(error)}], "isError": True}
    else:
        if request_id is None:
            return None
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": "method not found"},
        }
    if request_id is None:
        return None
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def main() -> int:
    token = os.getenv("DAVDEPLOY_TOKEN")
    if not token:
        print(
            "DAVDEPLOY_TOKEN is required; MCP never obtains cloud credentials", file=sys.stderr
        )
        return 2
    server = davdeployMcp(
        ProductApiClient(os.getenv("DAVDEPLOY_API_URL", "http://127.0.0.1:8080"), token)
    )
    for line in sys.stdin:
        if not line.strip():
            continue
        response = handle_request(server, json.loads(line))
        if response is not None:
            print(json.dumps(response), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
