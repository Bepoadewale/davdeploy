# ticket300 — Bind validated private storage output into the serverless renderer

PR: pending
Branch: `feat/typed-s3-to-lambda-inputs`

## Problem / goal

PR #299 adds a gated private S3 renderer and typed bucket outputs. The dependency scheduler still blocks all renderer input references, so a composed storage-plus-API plan cannot pass the bucket name to a Lambda runtime. Add a narrow, typed, value-validated binding for `aws-file-storage.bucket_name` → `aws-serverless-api.uploads_bucket_name`. Keep the API renderer disabled for general customer execution.

## Current repo state

PR #298 adds durable one-module-at-a-time scheduling. PR #299 (`982bb50`) adds a gated private S3 root/runner and typed outputs, but does not enable customer execution. `resolve_module_inputs` validates references in the graph library; the worker still blocks every input-bound module and the dispatcher rejects all bindings. Lambda's Terraform module supports a generic environment map but the customer API root does not yet configure bucket access.

## Research / references used

- `apps/api/src/davdeploy/universal_execution.py` typed graph and dependency resolver.
- `apps/api/src/davdeploy/module_ports.py` input/output schemas and output validation.
- `apps/api/src/davdeploy/service.py` worker claims and dependency scheduling.
- `apps/api/src/davdeploy/cloud_execution.py` fixed CodeBuild dispatch adapter.
- `scripts/customer-workload-dispatcher.sh` renderer allowlist and input boundary.
- PR #299 private S3 renderer (`infrastructure/terraform/customer-workload-private-s3/`).
- `infrastructure/terraform/customer-workload-serverless-api/` and `modules/lambda-service/`.

## Work planned for the PR

- Resolve a selected node's declared references only from successful dependency module rows and validate source values and consumer input types.
- Persist no secret contents; pass only approved reference values to the exact selected CodeBuild item.
- Allow only the `uploads_bucket_name` storage-to-API binding in this renderer version; reject unsupported input names/types before dispatch.
- Validate the binding in the dispatcher and again in the fixed Lambda runner; reject arbitrary fields, mismatched project/account/region bucket names, malformed JSON and unresolved bindings.
- Configure Lambda with the bucket name and a least-privilege role policy scoped to that bucket.
- Keep repeated module types/shared Terraform state roots and general Lambda/API customer execution fail-closed.
- Reconcile readiness documentation and add focused tests, full verification, and a clean-room cycle.

## Acceptance criteria

- [ ] The worker queues a dependent module only after all bound source outcomes and typed outputs are successful.
- [ ] The worker resolves only the declared storage `bucket_name` into the API `uploads_bucket_name` input.
- [ ] CodeBuild receives resolved values only for the selected module; no source secret contents or arbitrary command/configuration are passed.
- [ ] Dispatcher, adapter and runner reject missing, extra, malformed, wrong-type and wrong-scope input values.
- [ ] Lambda receives `UPLOADS_BUCKET_NAME` and only scoped S3 object/list permissions for the referenced bucket.
- [ ] Input values do not appear in user-facing errors, logs or general run output; audit evidence records only reference identities or redacted values.
- [ ] Unresolved or unsupported bindings remain fail-closed and are not silently skipped.
- [ ] Lambda/API renderer remains disabled for ordinary customer execution; this PR adds no public enablement.
- [ ] Focused tests, `make verify`, documentation checks and required clean-room validation pass.
- [ ] Ticket/evidence distinguish local proof from hosted/AWS certification.

## Acceptance status

Bootstrap only. Substantive implementation and validation have not started.

## Tests / validation performed

Bootstrap ticket and draft PR only.

## Evidence files produced

`docs/test/test300.md` will record local and clean-room verification. No AWS customer workload is planned in this PR.

## Boundaries

No live AWS resources, hosted schema migration, renderer enablement for general customers, arbitrary Terraform/input, secret payloads, or repeated/shared renderer state is in scope.

## Follow-up work

Run controlled AWS certification for a composed private bucket plus Lambda/API lifecycle, with a real write/read probe, health observation and exact cleanup before enabling this renderer. Add more input bindings only alongside renderer-specific Terraform/permission/config validation.
