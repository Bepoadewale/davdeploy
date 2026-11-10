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
- [Terraform saved plans](https://developer.hashicorp.com/terraform/cli/commands/plan)
- [API Gateway HTTP API IAM authorization](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-access-control-iam.html)
- [API Gateway HTTP API Lambda proxy payload](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html)
- [API Gateway HTTP API parameter mapping](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-parameter-mapping.html)
- [CodeBuild StartBuild API](https://docs.aws.amazon.com/codebuild/latest/APIReference/API_StartBuild.html)

## Work planned for the PR

- Add a state identity bound to organization, workspace, project, stable environment, target account/region, and approved execution context; never trust caller-selected object keys. Refuse state bootstrap when the revision has no environment ID.
- Add short-lived, run/attempt-bound Basic Auth credentials and lock ownership with bounded TTL and explicit conflict handling.
- Persist state as versioned S3 objects through a least-privilege API role; retain immutable version metadata and reconcile interrupted writes.
- Add separately gated optional private S3/KMS state storage with versioning, TLS-only access, and a prefix-scoped API role; keep both storage provisioning and state API disabled by default.
- Add strict HTTP backend GET/POST/lock/unlock semantics, request-size and content validation, and fail-closed authorization.
- Add tests for tenant crossing, stale/forged tokens, lock conflicts/expiry, object versioning, interrupted writes, and HTTP status mapping.
- Keep the plan runner disabled and do not provision AWS resources or apply customer infrastructure in this PR.

## Acceptance criteria

- [ ] State identifiers and credentials are bound to one execution scope and cannot select arbitrary tenant/object paths.
- [ ] Only the dedicated state routes accept the short-lived Terraform Basic Auth token; ordinary authenticated API routes retain their current edge/auth controls. Bootstrap accepts SigV4 only through an exact API Gateway IAM route and verifies the active fixed-project build before issuing credentials.
- [ ] State writes use versioned encrypted storage, and durable metadata identifies exact object version, lineage, serial, and digest.
- [ ] Lock/unlock is tenant-safe, ownership-checked, bounded, and race-tested; stale locks have an explicit recovery path.
- [ ] Oversized, malformed, cross-tenant, stale, and unauthenticated requests fail closed without leaking state contents.
- [ ] Interrupted persistence is detectable and cannot be reported as a completed state write.
- [ ] Database migrations, focused tests, `make verify`, and required clean-room lifecycle checks pass.
- [x] No runner enablement, AWS infrastructure deployment, pricing bypass, customer plan/apply, or destroy is included.

## Acceptance status

Implementation is in progress. This draft now contains additive state/credential/lock/write models, a schema v33 migration, strict scope/state/lock/token validation, S3 version-pointer logic with pending-write reconciliation, Terraform HTTP routes, exact API Gateway IAM credential bootstrap, expired-lock reclamation tied to terminal CodeBuild status and the exact lock/run/build identity, and separately gated optional private S3/KMS storage. Storage provisioning defaults off; the state API feature flag remains hard-disabled, the state API URL remains empty, and the plan runner remains backend-free. Criteria remain unmet until missing lifecycle/race tests, runner integration, clean-room evidence, and required GitHub CI/review are complete.

## Tests / validation performed

- Runtime test/evidence file: `docs/test/test331.md` records the local validation commands/results and unverified hosted behavior.
- No AWS state bucket, role, or customer workload has been created as part of this PR; infrastructure was statically validated only.

## Evidence files produced

- `docs/test/test331.md` records local validation and explicitly lists unverified hosted behavior.

## Boundaries

This PR does not grant permission to deploy the state service or enable Nova execution. A separate reviewed deployment must configure the versioned SSE-KMS bucket, server role, database capacity, observability, recovery alarms, and endpoint protection. The runner must remain disabled until provisioning and CodeBuild integration are separately reviewed and all cost/approval gates remain enforced.

## Follow-up work

Integrate the runner with the bootstrap and HTTP backend only after a dedicated review, then prove state freshness, durable locking, exact-plan approval, and crash reconciliation. Any deployment that enables the separately gated storage or state API requires its own reviewed deployment evidence before customer use.
