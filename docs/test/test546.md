# test546 — Hosted Nova v10 secret-reference correction

Date: 2026-11-27
Execution type: Hosted plan-only generation failure before CodeBuild
Customer repository: `Bepoadewale/fitness-backend` (synthetic acceptance project)
Control-plane commit: `4ecb7070bfa030041dd43958595cb24b5eaff54b`
AWS account: `654654474502` (verified control-plane account; no customer workload operation)
AWS region: `us-east-1`

## Control-plane deployment

Protected plan run `45964473463` completed successfully with 0 additions, 8
updates, 0 destroys, and 0 replacements. The saved plan updated six Lambda
packages/environments and the Nova plan CodeBuild package/environment and
scoped artifact policy; it showed no IAM action/resource-scope expansion and no
runtime gate changes. It recorded one pre-existing inline-policy drift.

Apply run `45965284428` succeeded. Database migrations completed. All six
control-plane Lambda functions are Active with successful updates and the same
code hash as the exact versioned release ZIP. The API health endpoint returned
HTTP 200.

## Hosted Nova retry

After v10 deployed, the authenticated workspace administrator retried run
`3f27c5fc-75d6-4393-8035-1938035a5a00` once using a new idempotency key. Nova
model: `us.amazon.nova-2-lite-v1:0`; prompt: `terraform-nova2-contract-v10`.
The run completed 2 attempts and 1 semantic repair in 11,727 ms, using 12,079
input and 3,119 output tokens. Estimated model cost was unavailable.

The run failed as `proposal_invalid` before CodeBuild. The only sanitized
validation issue was `credential_value`. Raw proposal content was not retrieved
or logged. No saved plan, CodeBuild build, or customer workload resource was
created. The run's single explicit retry is exhausted; do not retry it again.

## PR #546 local validation

The v11 prompt adds the exact accepted RDS-managed master-secret output and
Lambda typed-reference shape to initial generation and fixed repair guidance.
The credential validator and allowed locations were not changed. Focused tests
passed (161 tests); full `make verify` passed (2,029 tests), Ruff, Actions
configuration, OpenAPI snapshot, and Docker Compose configuration, with one
existing Starlette deprecation warning. Hosted CI and v11 deployment/evaluation
remain pending.

## Teardown and evidence retention

No customer workload resources or plan artifacts were created. The control-plane
release and run diagnostics remain as audit evidence. No cleanup was needed.

## Boundary

This run establishes only a bounded hosted generation failure. It does not
establish a valid saved plan, customer approval, apply, application behavior,
lifecycle, or certification. The workload remains unapproved and unapplied.
