# ticket164 — Nova-generated Terraform plan contracts

PR: [#164 — feat: add Nova-generated Terraform plan contracts](https://github.com/Bepoadewale/davdeploy/pull/164)
Branch: `feat/nova-generated-terraform`

## Problem / goal

Remove the App Runner-only renderer limitation so Nova can generate a customer-specific AWS
Terraform resource graph from an approved architecture, without requiring a pre-existing module
for every AWS service combination.

## Current repo state

App Runner has a proven authenticated execution path. Other approved profiles previously failed at
Terraform rendering even though the customer execution role may be authorized for broader AWS use.

## Research / references used

- Existing immutable revision, saved-plan, approval, and execution contracts.
- Existing Nova 2 Lite structured-output gateway and tenant-scoping controls.
- Existing Terraform plan-render persistence and cloud-execution boundaries.

## Work planned for the PR

- Add a Nova structured-output schema for AWS resource graphs.
- Reject credentials, provisioners, provider configuration, local-file reads, and untagged resources.
- Persist a revision-bound, plan-only Terraform JSON render for non-App-Runner profiles.
- Keep apply and destroy unavailable for generated contracts.

## Acceptance criteria

- [x] Nova output is typed, tenant-scoped, and immutable-revision-bound.
- [x] Generated resource graphs reject unsafe fields and require `ManagedBy=davdeploy`.
- [x] An EKS profile can render a Nova-generated plan-only contract without an EKS module.
- [x] No generated contract exposes an apply or destroy command.
- [x] Full test suite passes.

## Acceptance status

Implementation complete; awaiting CI and review.

## Tests / validation performed

- `.venv/bin/pytest -q tests/test_terraform_generation.py tests/test_customer_plan_review.py tests/test_nova_intent.py`
- `.venv/bin/pytest -q` — 288 passed.

## Evidence files produced

- `tests/test_terraform_generation.py`.
- `tests/test_customer_plan_review.py`.

## Boundaries

Generated Terraform is an untrusted, plan-only artifact. It cannot run shell commands, include
credentials, apply, destroy, call AWS, or write GitHub. A future execution path still requires
provider-schema validation, policy evaluation, a saved Terraform plan, and explicit approval.

## Follow-up work

Add an isolated generated-artifact validation runner, provider-schema checks, pricing/policy
admission for arbitrary resource graphs, and a separately approved saved-plan execution path.
