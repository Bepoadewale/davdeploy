# ticket336 — wire Nova state feature gates into the protected Terraform plan

PR: [#336](https://github.com/Bepoadewale/davdeploy/pull/336)
Branch: `feat/nova-state-workflow-wiring-336`
Base: `main`

## Problem / goal

The control-plane Terraform defines opt-in variables for the dedicated Nova
state bucket and tenant-scoped HTTP state API, but the protected Terraform
plan workflow does not pass them. That prevents a reviewed deployment from
provisioning the separately gated state storage and makes the API URL
configuration incomplete.

## Current repo state

- The state storage/API Terraform switches default to false.
- The API switch additionally requires the isolated plan runner, state
  storage, and a valid HTTPS API origin.
- The GitHub Actions variable allowlist currently has no state-specific
  feature-gate or API-origin variables.
- Nova runner, plan review, role verification, and state API are currently
  disabled in the hosted service.

## Research / references used

- `infrastructure/terraform/serverless-control-plane/variables.tf`
- `infrastructure/terraform/serverless-control-plane/main.tf`
- `.github/workflows/terraform-plan.yml`
- `scripts/check_actions_configuration.py`
- `tests/test_nova_plan_only_infra.py`

## Work planned for the PR

- Map state storage, state API enablement, and state API origin from explicitly
  named GitHub Actions variables into Terraform.
- Add those names to the Actions configuration allowlist.
- Add static checks that the variables default off and preserve the existing
  Terraform dependency validation.
- Document that mapping a switch does not enable it; runtime values remain
  false by default unless an authorized deployment explicitly sets them.

## Acceptance criteria

- [ ] The protected Terraform plan passes the three state inputs, with enable
      flags defaulting to false and URL defaulting to empty.
- [ ] The Actions variable allowlist accepts only the new named variables.
- [ ] Contract tests assert the mappings and fail-closed Terraform validations.
- [ ] No hosted state API, runner, or customer workload is enabled by this PR.
- [ ] Focused and full verification pass; required CI checks pass.

## Acceptance status

Implementation has not started.

## Tests / validation performed

Pending implementation.

## Evidence files produced

- `docs/test/test336.md` will record test results and boundaries.

## Boundaries

No GitHub Actions variable values are changed in this PR. No AWS resources,
state API, plan runner, customer plans, or customer infrastructure are
created or enabled.

## Follow-up work

A separate reviewed deployment must decide when to provision encrypted Nova
state storage and when to enable the state API after worker, recovery,
authorization, pricing, and approval gates are satisfied.
