# ticket165 — Enable live Nova Terraform generation

PR: [#165 — feat: enable live Nova Terraform generation](https://github.com/Bepoadewale/davdeploy/pull/165)
Branch: `feat/enable-live-nova-generation`

## Problem / goal

Enable the Terraform-managed runtime gate for the already deployed Nova 2 Lite structured Terraform
generation path.

## Current repo state

The API has the scoped Bedrock permission and Nova model ID, but the explicit
`DAVDEPLOY_ENABLE_NOVA_MODEL` runtime gate is unset and therefore fails closed.

## Research / references used

- Read-only Lambda environment inspection for `davdeploy-api`.
- Serverless Terraform runtime environment and scoped Bedrock IAM policy.
- PR #164 generated Terraform plan-only boundary.

## Work planned for the PR

- Set `DAVDEPLOY_ENABLE_NOVA_MODEL=true` through Terraform.
- Assert the managed environment value in the runtime contract test.

## Acceptance criteria

- [x] Runtime gate is Terraform managed, not manually changed.
- [x] Nova remains restricted to the configured Nova 2 Lite model family.
- [x] Generated Terraform remains plan-only and approval-bound.
- [x] Focused runtime and generation tests pass.

## Acceptance status

Implementation complete; awaiting CI, protected apply, and live configuration verification.

## Tests / validation performed

- `.venv/bin/pytest -q tests/test_serverless_runtime.py tests/test_terraform_generation.py` — 31 passed.
- `terraform -chdir=infrastructure/terraform/serverless-control-plane fmt -check`.

## Evidence files produced

- `tests/test_serverless_runtime.py`.

## Boundaries

This enables model inference only. It does not grant Nova approval, shell access, AWS mutation,
Terraform apply/destroy, GitHub writes, or access to customer secrets.

## Follow-up work

Apply the protected control-plane Terraform plan, verify the live environment gate, then run a
non-mutating authenticated generated-contract request against a customer-approved revision.
