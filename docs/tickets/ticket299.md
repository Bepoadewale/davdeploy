# ticket299 — Add a bounded private object storage renderer

PR: https://github.com/Bepoadewale/davdeploy/pull/299
Branch: `feat/customer-private-object-storage-renderer`

## Problem / goal

Add a checked-in Terraform renderer for the `aws-file-storage` module with a private, encrypted, versioned S3 bucket and bounded plan/apply/observe/destroy/cleanup operations. Keep customer execution disabled until the renderer is independently validated and certified.

## Current repo state

PR #298 merged durable one-module-at-a-time dependency scheduling as `42200c0`. Typed module output validation exists, but `aws-file-storage` had no renderer binding and unresolved input bindings remained rejected. App Runner remains the only renderer enabled for customer execution; the Lambda/API renderer remains gated.

## Research / references used

- `AGENTS.md` PR, validation, evidence and customer-workload boundaries.
- `apps/api/src/davdeploy/module_ports.py` typed storage outputs.
- `apps/api/src/davdeploy/module_renderers.py` fixed renderer allowlist.
- `apps/api/src/davdeploy/cloud_execution.py` renderer dispatch boundary.
- Existing `infrastructure/terraform/customer-workload-serverless-api/` and its fixed runner script.
- AWS S3 security controls: block public access, bucket-owner-enforced ownership, server-side encryption, versioning, and TLS-only bucket policy.

## Work planned for the PR

- Add a project-scoped Terraform root and fixed runner for a private S3 bucket lifecycle.
- Enforce account, connection, project and immutable plan-digest guards/tags; keep state, saved plans and result artifacts under project-scoped prefixes.
- Emit only declared non-secret typed outputs (`bucket_name`, `bucket_arn`) and verify bucket security controls are in place.
- Register the renderer as disabled for customer execution pending certification; do not relax general execution gates or accept arbitrary input/configuration.
- Add unit/contract tests, evidence documentation, and reconcile execution goal/readiness docs with PRs #297–#298.

## Acceptance criteria

- [x] Only the fixed storage lifecycle operations and checked-in Terraform root are registered.
- [x] The bucket configuration is private, versioned, AES256 encrypted, ownership-enforced and tagged; public access is blocked and insecure transport is denied.
- [x] The runner checks expected AWS account, project-scoped state/saved-plan/result paths, plan digest and cleanup absence.
- [x] Output normalization persists only the declared non-secret storage outputs and rejects malformed or sensitive values.
- [x] The renderer is disabled for customer execution; the CodeBuild dispatcher has a separate off-by-default certification guard.
- [x] Unsupported operations, arbitrary Terraform/configuration, unresolved input bindings and mismatched account/project fail closed.
- [ ] Focused tests, `make verify`, documentation checks and clean-room validation pass.
- [ ] Ticket and evidence accurately state final validation type and limitations.

## Acceptance status

The private S3 Terraform root, fixed lifecycle runner, typed output mapping,
registry entry, dispatcher guard and tests are implemented. The renderer remains
disabled. The local clean-room gate and GitHub CI have not completed yet.

## Tests / validation performed

Terraform formatting, shell syntax, focused tests (61 passed), `make verify`
(491 passed), Terraform validation and documentation conventions have passed.
The fresh local clean-room cycle and GitHub CI remain pending.

## Evidence files produced

`docs/test/test299.md` records local validation and will record the clean-room and CI results. No live AWS workload test is in scope for this PR.

## Boundaries

No live AWS resources, hosted schema changes, customer execution enablement, public bucket access, generic Terraform, secret payloads or customer-specific data are in scope.

## Follow-up work

Run a controlled real AWS lifecycle test and prove composed data flow before enabling this renderer or resolving storage references into another renderer. The renderer currently does not delete non-empty buckets (`force_destroy = false`) and does not implement a separate rollback operation.
