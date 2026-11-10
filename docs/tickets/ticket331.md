# ticket331 — implement tenant-isolated Terraform state boundary

PR: [#331](https://github.com/Bepoadewale/davdeploy/pull/331) (draft)
Branch: `feat/tenant-isolated-terraform-state-331`
Base: `main` at `35fd477` (includes merged ADR-013 from PR #330)

## Problem / goal

ADR-013 selects a DavDeploy HTTP state API backed by versioned encrypted S3 objects and PostgreSQL lock metadata. The current Nova plan runner uses `-backend=false`; it cannot safely preserve state across runs. This PR implements a narrow, fail-closed state API/storage boundary while leaving the runner disabled.

## Current repo state

- PR #328's Nova plan-only runner is source-only, disabled, and backend-free.
- PR #330 documents ADR-013; it provides no state routes, storage, credentials, or infrastructure.
- Terraform HTTP backend callers can use Basic Auth through `TF_HTTP_USERNAME` and `TF_HTTP_PASSWORD`. Their requests can use the public API domain: Cloudflare's Worker replaces the edge-origin header before forwarding to API Gateway. Credential bootstrap is a separate path because CodeBuild must prove its AWS identity without exposing a long-lived secret through build environment overrides. A narrow API Gateway `AWS_IAM` route with SigV4 is the candidate bootstrap boundary; it must bind the request to the exact active trusted build before issuing a short-lived state token.
- The Terraform HTTP backend has no caller-supplied resource key. DavDeploy must resolve state from trusted organization/project/environment context; the environment identifier is optional in some current revisions, so state-enabled runs must fail closed until a stable environment binding is present.
- Pricing evidence is still unavailable; no plan from this path may become approvable or be applied.

## Research / references used

- [ADR-013: tenant-isolated Terraform state](../decisions/ADR-013-tenant-isolated-terraform-state.md)
- [Terraform HTTP backend](https://developer.hashicorp.com/terraform/language/backend/http)
- [Terraform state locking](https://developer.hashicorp.com/terraform/language/state/locking)
- [Terraform saved plans](https://developer.hashicorp.com/terraform/cli/commands/plan)
- [Amazon S3 `HeadObject` missing-object permissions](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html)
- [Amazon S3 conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html)
- [API Gateway HTTP API IAM authorization](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-access-control-iam.html)
- [API Gateway HTTP API Lambda proxy payload](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html)
- [API Gateway HTTP API parameter mapping](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-parameter-mapping.html)
- [CodeBuild StartBuild API](https://docs.aws.amazon.com/codebuild/latest/APIReference/API_StartBuild.html)

## Work planned for the PR

- Add a state identity bound to organization, workspace, project, stable environment, target account/region, and approved execution context; never trust caller-selected object keys. Refuse state bootstrap when the revision has no environment ID.
- Add short-lived, run/attempt-bound Basic Auth credentials and lock ownership with bounded TTL and explicit conflict handling.
- Persist state as versioned S3 objects through a least-privilege API role; retain immutable version metadata and reconcile interrupted writes.
- Reconcile missing-object `HeadObject` 403 responses without granting broad bucket listing: use an `IfNoneMatch="*"` conditional write, verify matching object metadata on 412, and retry a 409 only within a fixed bound.
- Add separately gated optional private S3/KMS state storage with versioning, TLS-only access, and a prefix-scoped API role; keep both storage provisioning and state API disabled by default.
- Add strict HTTP backend GET/POST/lock/unlock semantics, request-size and content validation, and fail-closed authorization.
- Require the HTTP backend's lock ID query parameter on state writes to match the active database lock; the runner must configure the custom POST/DELETE lock methods explicitly when backend integration is added.
- Add tests for tenant crossing, stale/forged tokens, lock conflicts/expiry, object versioning, interrupted writes, and HTTP status mapping.
- Keep the plan runner disabled and do not provision AWS resources or apply customer infrastructure in this PR.

## Acceptance criteria

- [x] State identifiers and credentials are bound to one execution scope and cannot select arbitrary tenant/object paths.
- [x] Only the dedicated state routes accept the short-lived Terraform Basic Auth token; ordinary authenticated API routes retain their current edge/auth controls. Bootstrap accepts SigV4 only through an exact API Gateway IAM route and verifies the active fixed-project build before issuing credentials.
- [x] State writes use versioned encrypted storage, and durable metadata identifies exact object version, lineage, serial, and digest.
- [x] Lock/unlock is tenant-safe, ownership-checked, bounded, and race-tested; stale locks have an explicit recovery path.
- [x] Oversized, malformed, cross-tenant, stale, and unauthenticated requests fail closed without leaking state contents.
- [x] Interrupted persistence is detectable and cannot be reported as a completed state write.
- [x] Database migrations, focused tests, `make verify`, and required clean-room lifecycle checks pass.
- [x] No runner enablement, AWS infrastructure deployment, pricing bypass, customer plan/apply, or destroy is included.

## Acceptance status

The implementation and required local/CI verification pass at runtime code commit `b09d211`; independent review found no remaining blocker in either failed-write recovery case. Prior pending S3 versions are checked by exact key, encryption, metadata, version, and state digest before adoption. Changed bytes at that serial are rejected after the valid prior version is committed; absent or invalid objects are recorded in bounded attempt history and rotated under the current lock. Forced two-session tests cover simultaneous acquisition and stale-lock reclaim racing a new acquisition against local SQLite. Production PostgreSQL/Aurora race behavior and hosted AWS behavior remain unverified. Schema v33 remains additive. The bucket toggle defaults off, the state API feature flag remains hard-disabled, and the runner is still backend-free. Worker restart recovery and Terraform CLI retry behavior also remain unverified, so keep the PR draft and state feature disabled.

## Tests / validation performed

- Focused suites: `tests/test_terraform_state.py tests/test_db_config.py` — 35 passed, including pending-write recovery, schema-field coverage, simultaneous acquisition, and stale-reclaim/reacquisition races.
- `make verify` with Python 3.12 — 847 tests passed; Ruff, Actions configuration, OpenAPI snapshot, and Compose configuration passed.
- Full isolated clean-room sequence passed at runtime code commit `b09d211`: bootstrap, readiness, all demos, API contract, customer-plan E2E, seed, API restart/persistence, trace check, `make verify`, and MCP tools-list request. The exact project containers, network, Postgres volume, `.venv`, and `.local` database were removed and absence verified.
- GitHub Actions run `42876621371` — all seven required checks passed for final test/evidence head `240079a`, including fresh-runner local E2E with 847 tests.
- The local race tests use separate SQLite sessions. They validate single-lock ownership under forced concurrent inserts and reclaim/acquisition interleaving but do not establish PostgreSQL/Aurora locking behavior.
- `scripts/terraform-validate.sh` — all configured roots passed.
- Documentation conventions and `git diff --check` passed.
- Runtime test/evidence file: `docs/test/test331.md` records the local validation commands/results and unverified hosted behavior.
- No AWS state bucket, role, or customer workload has been created as part of this PR; infrastructure was statically validated only.

## Evidence files produced

- `docs/test/test331.md` records local validation and explicitly lists unverified hosted behavior.

## Boundaries

This PR does not grant permission to deploy the state service or enable Nova execution. A separate reviewed deployment must configure the versioned SSE-KMS bucket, server role, database capacity, observability, recovery alarms, and endpoint protection. The runner must remain disabled until provisioning and CodeBuild integration are separately reviewed and all cost/approval gates remain enforced.

## Follow-up work

Integrate the runner with the bootstrap and HTTP backend only after a dedicated review, then prove state freshness, durable locking, exact-plan approval, and crash reconciliation. Any deployment that enables the separately gated storage or state API requires its own reviewed deployment evidence before customer use.
