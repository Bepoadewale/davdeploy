"""Thin operator/developer CLI. It forwards a caller's token to the governed API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from davdeploy.client import ProductApiClient

CLI_PROTOCOL_VERSION = "v1"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="davdeploy governed API client")
    parser.add_argument(
        "--api-url", default=os.getenv("DAVDEPLOY_API_URL", "http://127.0.0.1:8080")
    )
    parser.add_argument("--token", default=os.getenv("DAVDEPLOY_TOKEN"))
    subparsers = parser.add_subparsers(dest="command", required=True)

    intent = subparsers.add_parser("analyze-workload")
    intent.add_argument("--project-id", required=True)
    intent.add_argument("--prompt", required=True)
    intent.add_argument("--idempotency-key", required=True)
    intent.add_argument("--repository")
    intent.add_argument("--cloud-connection-id")

    plan = subparsers.add_parser("plan-infrastructure")
    plan.add_argument("--intent-id", required=True)

    get_plan = subparsers.add_parser("get-plan")
    get_plan.add_argument("--plan-id", required=True)

    compare = subparsers.add_parser("compare-architectures")
    compare.add_argument("--plan-id", required=True)

    execute = subparsers.add_parser("execute-approved-plan")
    execute.add_argument("--plan-id", required=True)

    environment = subparsers.add_parser("get-environment-status")
    environment.add_argument("--environment-id", required=True)

    audit = subparsers.add_parser("get-audit-events")
    audit.add_argument("--environment-id")

    destroy = subparsers.add_parser("destroy-environment")
    destroy.add_argument("--environment-id", required=True)

    estimate = subparsers.add_parser("get-cost-estimate")
    estimate.add_argument("--plan-id", required=True)

    approval = subparsers.add_parser("get-approval-status")
    approval.add_argument("--plan-id", required=True)

    approve = subparsers.add_parser("approve-plan")
    approve.add_argument("--plan-id", required=True)
    approve.add_argument("--plan-hash", required=True)

    customer_review = subparsers.add_parser("create-customer-review")
    customer_review.add_argument("--plan-id", required=True)

    customer_get = subparsers.add_parser("get-customer-review")
    customer_get.add_argument("--revision-id", required=True)

    customer_submit = subparsers.add_parser("submit-customer-review")
    customer_submit.add_argument("--revision-id", required=True)

    customer_execute = subparsers.add_parser("execute-customer-dry-run")
    customer_execute.add_argument("--revision-id", required=True)

    terraform_render = subparsers.add_parser("render-customer-terraform")
    terraform_render.add_argument("--revision-id", required=True)
    terraform_render.add_argument("--content-digest", required=True)

    cloud_preflight = subparsers.add_parser("preflight-customer-cloud")
    cloud_preflight.add_argument("--revision-id", required=True)
    cloud_preflight.add_argument("--content-digest", required=True)
    cloud_preflight.add_argument("--expected-account-id")
    cloud_preflight.add_argument("--region", required=True)
    cloud_preflight.add_argument("--budget-ceiling-usd", type=int)
    cloud_preflight.add_argument("--runtime-identity-configured", action="store_true")

    terraform_review = subparsers.add_parser("review-customer-terraform-plan")
    terraform_review.add_argument("--revision-id", required=True)
    terraform_review.add_argument("--content-digest", required=True)
    terraform_review.add_argument("--preflight-id")
    terraform_review.add_argument("--expected-account-id")
    terraform_review.add_argument("--region", required=True)
    terraform_review.add_argument("--authenticated", action="store_true")
    terraform_review.add_argument("--destroy", action="store_true")

    cloud_run = subparsers.add_parser("create-customer-cloud-run")
    cloud_run.add_argument("--revision-id", required=True)
    cloud_run.add_argument("--content-digest", required=True)
    cloud_run.add_argument("--terraform-render-id")
    cloud_run.add_argument("--preflight-id")
    cloud_run.add_argument("--terraform-plan-review-id")
    cloud_run.add_argument("--expected-account-id")
    cloud_run.add_argument("--region", required=True)
    cloud_run.add_argument("--confirmation", required=True)
    cloud_run.add_argument("--destroy", action="store_true")

    image_build = subparsers.add_parser("build-customer-image")
    image_build.add_argument("--revision-id", required=True)
    image_build.add_argument("--content-digest", required=True)
    image_build.add_argument("--expected-account-id")
    image_build.add_argument("--region", required=True)
    image_build.add_argument("--confirmation", required=True)

    queue_cloud_run = subparsers.add_parser("queue-customer-cloud-run")
    queue_cloud_run.add_argument("--run-id", required=True)
    queue_cloud_run.add_argument("--content-digest", required=True)
    queue_cloud_run.add_argument("--confirmation", required=True)

    cloud_evidence = subparsers.add_parser("get-customer-cloud-run-evidence")
    cloud_evidence.add_argument("--run-id", required=True)

    reconcile_cloud_run = subparsers.add_parser("reconcile-customer-cloud-run-result")
    reconcile_cloud_run.add_argument("--run-id", required=True)

    customer_queue = subparsers.add_parser("list-customer-reviews")
    customer_queue.add_argument("--state")

    recommend = subparsers.add_parser("recommend-optimization")
    recommend.add_argument("--environment-id", required=True)

    change = subparsers.add_parser("create-change-plan")
    change.add_argument("--environment-id", required=True)

    incidents = subparsers.add_parser("get-incidents")
    incidents.add_argument("--environment-id", required=True)
    return parser


def run(
    args: argparse.Namespace, client: ProductApiClient
) -> dict[str, Any] | list[dict[str, Any]]:
    if args.command == "analyze-workload":
        return client.request(
            "POST",
            "/api/v1/intents",
            {
                "project_id": args.project_id,
                "prompt": args.prompt,
                "source_repository": args.repository,
                "cloud_connection_id": args.cloud_connection_id,
                "idempotency_key": args.idempotency_key,
            },
        )
    if args.command == "plan-infrastructure":
        return client.request("POST", f"/api/v1/intents/{args.intent_id}/plans")
    if args.command == "get-plan":
        return client.request("GET", f"/api/v1/deployment-plans/{args.plan_id}")
    if args.command == "compare-architectures":
        plan = client.request("GET", f"/api/v1/deployment-plans/{args.plan_id}")
        return plan["payload"]["architecture"]["candidates"]
    if args.command == "get-cost-estimate":
        plan = client.request("GET", f"/api/v1/deployment-plans/{args.plan_id}")
        return plan["payload"]["architecture"]["cost_estimate"]
    if args.command == "get-approval-status":
        plan = client.request("GET", f"/api/v1/deployment-plans/{args.plan_id}")
        return {key: plan[key] for key in ("id", "state", "plan_hash", "policy_result")}
    if args.command == "approve-plan":
        return client.request(
            "POST",
            f"/api/v1/deployment-plans/{args.plan_id}/approve",
            {"plan_hash": args.plan_hash},
        )
    if args.command == "create-customer-review":
        return client.request("POST", f"/api/v1/deployment-plans/{args.plan_id}/customer-review")
    if args.command == "get-customer-review":
        return client.request("GET", f"/api/v1/customer-plan-revisions/{args.revision_id}")
    if args.command == "submit-customer-review":
        return client.request("POST", f"/api/v1/customer-plan-revisions/{args.revision_id}/submit")
    if args.command == "execute-customer-dry-run":
        return client.request(
            "POST", f"/api/v1/customer-plan-revisions/{args.revision_id}/execute-dry-run"
        )
    if args.command == "render-customer-terraform":
        return client.request(
            "POST",
            f"/api/v1/customer-plan-revisions/{args.revision_id}/terraform-plan-renders",
            {"content_digest": args.content_digest},
        )
    if args.command == "preflight-customer-cloud":
        return client.request(
            "POST",
            f"/api/v1/customer-plan-revisions/{args.revision_id}/cloud-readiness-preflights",
            {
                "content_digest": args.content_digest,
                "expected_account_id": args.expected_account_id,
                "allowed_regions": [args.region],
                "required_tags": {"ManagedBy": "davdeploy"},
                "budget_ceiling_usd": args.budget_ceiling_usd,
                "execution_mode": "PLAN_ONLY",
                "require_reviewed_pr": False,
                "runtime_identity_configured": args.runtime_identity_configured,
            },
        )
    if args.command == "review-customer-terraform-plan":
        return client.request(
            "POST",
            f"/api/v1/customer-plan-revisions/{args.revision_id}/terraform-plan-reviews",
            {
                "content_digest": args.content_digest,
                "preflight_id": args.preflight_id,
                "expected_account_id": args.expected_account_id,
                "expected_region": args.region,
                "mode": (
                    "AUTHENTICATED_TERRAFORM_DESTROY_PLAN"
                    if args.authenticated and args.destroy
                    else "AUTHENTICATED_TERRAFORM_PLAN"
                    if args.authenticated
                    else "LOCAL_CONTRACT_ONLY"
                ),
                "allow_cloud_plan": args.authenticated,
            },
        )
    if args.command == "create-customer-cloud-run":
        return client.request(
            "POST",
            f"/api/v1/customer-plan-revisions/{args.revision_id}/cloud-execution-runs",
            {
                "content_digest": args.content_digest,
                "terraform_render_id": args.terraform_render_id,
                "preflight_id": args.preflight_id,
                "terraform_plan_review_id": args.terraform_plan_review_id,
                "expected_account_id": args.expected_account_id,
                "expected_region": args.region,
                "mode": "AUTHENTICATED_APP_RUNNER_DESTROY" if args.destroy else "AUTHENTICATED_APP_RUNNER_APPLY",
                "confirmation": args.confirmation,
            },
        )
    if args.command == "build-customer-image":
        return client.request(
            "POST",
            f"/api/v1/customer-plan-revisions/{args.revision_id}/customer-image-builds",
            {
                "content_digest": args.content_digest,
                "expected_account_id": args.expected_account_id,
                "expected_region": args.region,
                "confirmation": args.confirmation,
            },
        )
    if args.command == "queue-customer-cloud-run":
        return client.request(
            "POST",
            f"/api/v1/cloud-execution-runs/{args.run_id}/execute",
            {"content_digest": args.content_digest, "confirmation": args.confirmation},
        )
    if args.command == "get-customer-cloud-run-evidence":
        return client.request("GET", f"/api/v1/cloud-execution-runs/{args.run_id}/evidence")
    if args.command == "reconcile-customer-cloud-run-result":
        return client.request("POST", f"/api/v1/cloud-execution-runs/{args.run_id}/reconcile-result")
    if args.command == "list-customer-reviews":
        suffix = f"?state={args.state}" if args.state else ""
        return client.request("GET", f"/api/v1/admin/customer-plan-revisions{suffix}")
    if args.command == "execute-approved-plan":
        return client.request("POST", f"/api/v1/deployment-plans/{args.plan_id}/execute")
    if args.command == "get-environment-status":
        return client.request("GET", f"/api/v1/environments/{args.environment_id}")
    if args.command == "get-audit-events":
        suffix = f"?environment_id={args.environment_id}" if args.environment_id else ""
        return client.request("GET", f"/api/v1/audit-events{suffix}")
    if args.command == "destroy-environment":
        return client.request("POST", f"/api/v1/environments/{args.environment_id}/destroy-plan")
    if args.command == "recommend-optimization":
        return client.request("GET", f"/api/v1/environments/{args.environment_id}/recommendation")
    if args.command == "create-change-plan":
        return client.request("POST", f"/api/v1/environments/{args.environment_id}/change-plan")
    if args.command == "get-incidents":
        return client.request("GET", f"/api/v1/environments/{args.environment_id}/incidents")
    raise ValueError(f"unknown command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.token:
        raise SystemExit(
            "set DAVDEPLOY_TOKEN or pass --token; the CLI never obtains cloud credentials"
        )
    result = run(args, ProductApiClient(args.api_url, args.token))
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
