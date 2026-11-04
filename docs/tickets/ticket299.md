# ticket299 — Add a bounded private object storage renderer

PR: pending

## Goal

Add a checked-in Terraform renderer for the `aws-file-storage` module with a private, encrypted, versioned S3 bucket and bounded plan/apply/observe/destroy/cleanup operations. Keep customer execution disabled until the renderer is independently validated and certified.

## Current repo state

PR #298 merged durable one-module-at-a-time dependency scheduling. Typed module output validation exists, but `aws-file-storage` has no renderer binding and unresolved input bindings remain rejected. App Runner remains the only renderer enabled for customer execution; the Lambda/API renderer remains gated.

## Research / references

- `AGENTS.md` PR, validation, evidence and customer-workload boundaries.
- `apps/api/src/davdeploy/module_ports.py` typed storage outputs.
- `apps/api/src/davdeploy/module_renderers.py` fixed renderer allowlist.
- `apps/api/src/davdeploy/cloud_execution.py` renderer dispatch boundary.
- Existing `infrastructure/terraform/customer-workload-serverless-api/` and its fixed runner script.
- AWS S3 security controls: block public access, bucket-owner-enforced ownership, server-side encryption, versioning, and TLS-only bucket policy.

## Work planned

- Add a project-scoped Terraform root and fixed runner for a private S3 bucket lifecycle.
- Enforce account, connection, project and immutable plan-digest guards/tags; keep state, saved plans and result artifacts under project-scoped prefixes.
- Emit only declared non-secret typed outputs (`bucket_name`, `bucket_arn`) and verify object access remains private.
- Register the renderer as disabled for customer execution pending certification; do not relax general execution gates or accept arbitrary input/configuration.
- Add unit/contract tests, evidence documentation, and reconcile execution goal/readiness docs with PRs #297–#298.

## Acceptance criteria

- [ ] Only the fixed storage lifecycle operations and checked-in Terraform root can execute.
- [ ] The bucket is private, versioned, encrypted, ownership-enforced and tagged; insecure public access is blocked.
- [ ] The runner verifies expected AWS account, project-scoped state/artifact/result paths, plan digest and cleanup absence.
- [ ] Output normalization persists only the declared typed storage outputs and rejects malformed or sensitive data.
- [ ] The renderer remains disabled for customer execution until lifecycle certification is complete.
- [ ] Unsupported operations, arbitrary Terraform/configuration, unresolved input bindings and mismatched account/project fail closed.
- [ ] Focused tests, `make verify`, documentation checks and required clean-room validation pass.
- [ ] Ticket and evidence accurately state validation type and limitations.

## Validation performed

Bootstrap only. Substantive implementation and validation have not started.

## Evidence files

`docs/test/test299.md` will record local/clean-room validation. No live AWS workload test is planned in this PR.

## Boundaries

No live AWS resources, hosted schema changes, customer execution enablement, public bucket access, generic Terraform, secret payloads or customer-specific data are in scope.

## Follow-up

Run a controlled real AWS lifecycle test and prove composed data flow before enabling this renderer or resolving storage references into another renderer.
