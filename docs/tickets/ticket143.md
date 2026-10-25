# ticket143: Keep customer external IDs out of Terraform artifacts

PR: #143
Branch: fix/customer-runner-session-provider

## Problem / goal

The isolated executor correctly assumes the bounded customer role, but the
Terraform provider then attempted the same role assumption again. That requires
passing the ExternalId to Terraform and risks persisting a secret in a saved
plan or state.

## Current repo state

The runner has a short-lived STS customer session before Terraform starts. The
customer workload Terraform provider still contains an `assume_role` block and
two role-assumption input variables.

## Research / references used

- Failed real plan run `ae0b4001-c47c-4203-9c1c-bf551f3673d7`.
- `scripts/customer-workload-app-runner-pilot.sh` role-assumption boundary.
- Terraform AWS provider ambient credential behavior.

## Work planned for the PR

- Use the runner's already-assumed STS customer session as the Terraform
  provider credential source.
- Remove the redundant Terraform role-assumption variables.
- Add regression assertions that the customer ExternalId cannot enter the
  Terraform provider or runner variable list.

## Acceptance criteria

- [x] The runner assumes the customer role exactly once per bounded run.
- [x] The customer ExternalId is not passed to Terraform.
- [x] Terraform uses short-lived scoped credentials.
- [ ] Focused tests and required CI pass.
- [ ] The released runner completes a fresh real customer plan and apply.

## Acceptance status

Implementation is complete. Focused local validation, CI, guarded release, and
a fresh live customer plan/apply remain.

## Tests / validation performed

- Pending focused Terraform, shell, lifecycle, and documentation checks.

## Evidence files produced

- Customer live-run evidence continues in `docs/test/test130.md`.

## Boundaries

- The external ID is fetched only to create the STS session and is then removed
  from the process environment.
- This does not broaden any customer or control-plane IAM permission.

## Follow-up work

- Release the immutable runner through the guarded workflow.
- Run the signed customer plan, reviewed apply, observation, and destroy flow.
