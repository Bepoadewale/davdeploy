# ADR-013: Tenant-isolated Terraform state through the HTTP backend

- Status: Proposed
- Date: 2026-11-10
- Related: PR #328, ticket #330

## Context

PR #328 adds a disabled-by-default Nova runner that creates backend-free, review-only plans. It cannot safely support durable updates or apply until every deployment has a persistent state identity, encrypted version history, locking, tenant isolation, and crash recovery.

The shared CodeBuild service role must not receive direct read/write access to all tenant state. Terraform's S3 backend has native locking with `use_lockfile=true` and recommends S3 bucket versioning, but a direct backend path still needs a defensible way to scope backend credentials to one workspace/project/environment for every build. Giving the shared build role broad state access would violate the tenant boundary.

## Decision proposed

Use Terraform's built-in HTTP backend for the runner, backed by a DavDeploy state API. The API is the tenant authorization boundary. It stores state objects in a dedicated private, versioned, SSE-KMS S3 bucket and stores locks and state-version metadata in PostgreSQL. CodeBuild gets no direct state-bucket permission.

Use one server-created opaque state ID per workspace, project, and environment. Do not let Nova, the customer repository, or a request parameter choose or change this ID. Use only Terraform's default workspace; reject attempts to select another workspace.

The fixed runner receives trusted HTTP backend endpoints and a short-lived, high-entropy state credential bound to one state ID, one durable run/attempt, and an allowed operation. The API stores only a hash of the credential, authenticates it in constant time, expires or revokes it on terminal/reconciled runs, and never logs or returns it to the browser. The runner injects authentication through `TF_HTTP_USERNAME` / `TF_HTTP_PASSWORD`; it does not put credentials in generated Terraform or `-backend-config`.

The HTTP contract uses `GET` and `POST` for state and separate lock endpoints using `POST` to lock and `DELETE` to unlock. Lock conflicts return Terraform's supported `423 Locked` or `409 Conflict` response with bounded lock metadata. The state endpoint does not accept `DELETE`; teardown writes an empty Terraform state and retains version history. Releasing a lock after an uncertain worker outcome requires confirmed terminal CodeBuild status and an exact state/run/lock-ID match. Time expiry alone never proves a lock is abandoned.

For each successful state write, validate the bounded Terraform state JSON and monotonic lineage/serial, persist a pending update record, write an immutable S3 object version tagged with the update digest/ID, then commit the exact S3 VersionId and digest in PostgreSQL. Reconciliation must finish an interrupted write from the pending marker without overwriting a newer state. S3 version history supports recovery; no state payload is logged, included in a model prompt, or returned in a normal plan-detail response.

The approved plan manifest will bind the state ID, exact pre-plan state VersionId/digest/serial/lineage, backend contract version, and policy version. Apply must acquire the same state lock and fail closed if the approved plan's state version is stale. Each apply gets a new run-bound state credential; Nova cannot request state reads, write state, change a backend, unlock, or choose credentials.

## Security and lifecycle requirements before enabling

- Use a dedicated S3 bucket with versioning, Block Public Access, TLS-only bucket policy, SSE-KMS/Bucket Keys, expected-owner checks, and a separate state object prefix. Restrict the API role to this bucket and required state objects; CodeBuild and customer roles receive no state-bucket access.
- Bind credentials to tenant, workspace, project, environment, state ID, operation, run, build attempt, and expiry. Reject cross-tenant, cross-project, cross-state, stale, revoked, and replayed credentials.
- Require an active durable run and its exact build identity for all backend requests. Scope lock conflict/release to one state and one lock ID.
- Enforce a configured maximum state size below the HTTP/API transport limit. On unsupported size, backend outage, invalid JSON, serial regression, version mismatch, failed upload, or uncertain lock outcome, stop the run and enter explicit reconciliation; preserve any locally recovered state only in encrypted, run-scoped recovery storage.
- Protect state versions from user-facing plan APIs and public logs. Audit state/lock metadata, actor/run/build IDs, timestamps, digests, and VersionIds without recording payloads or credentials.
- Keep state after `terraform destroy` for audit and recovery. State retention/deletion requires a separate lifecycle policy and must never infer authority from tags.
- Test concurrent plans/applies, worker crashes before/during/after state writes, duplicate callbacks, expired/revoked tokens, tampering, lock recovery, tenant isolation, Terraform backend retries, state-version recovery, and teardown retention before any customer apply.

## Alternatives considered

- Direct S3 backend credentials in the shared CodeBuild role: rejected because the role would have direct access across tenant prefixes.
- Per-project S3 backend roles: technically possible and compatible with S3 `use_lockfile`, but requires dynamic role provisioning, ExternalId lifecycle, role cleanup, and credential scoping for every project. Revisit if the API-backed HTTP boundary cannot meet measured size, throughput, availability, or recovery limits.
- DynamoDB-backed S3 locking: rejected for new state because HashiCorp now marks DynamoDB locking deprecated. If the S3 backend is selected later, use S3 `use_lockfile=true` and versioning instead.
- A new external Terraform service: rejected for this goal because it adds a purchased/third-party state authority outside the existing API and CodeBuild architecture.

## Consequences

This decision avoids direct state-bucket access from CodeBuild and lets the API enforce workspace/project/environment boundaries. DavDeploy must implement and operate a state API, including write-ahead reconciliation, lock recovery, token issuance/revocation, and a dedicated encrypted bucket. This is an explicit infrastructure milestone; it is not implemented or enabled by this ADR or by PR #328.

Terraform documents the HTTP backend's GET/POST state operations and optional LOCK/UNLOCK requests, plus environment-based credential configuration. It documents S3 bucket versioning and the native `use_lockfile` option; DynamoDB locking is deprecated. References: [HTTP backend](https://developer.hashicorp.com/terraform/language/backend/http), [S3 backend](https://developer.hashicorp.com/terraform/language/backend/s3), [state locking](https://developer.hashicorp.com/terraform/language/state/locking), and [state security](https://developer.hashicorp.com/terraform/language/manage-sensitive-data).
