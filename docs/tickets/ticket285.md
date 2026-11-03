# ticket285 — Wire certification allowlist into Terraform release workflow

PR: pending
Branch: `feat/terraform-certification-inputs`

## Problem / goal

The controlled Lambda/API certification gate and workspace allowlist now exist
in Terraform, but the protected plan/apply workflows do not pass GitHub
Environment variables into those Terraform inputs. Add explicit workflow wiring
with safe defaults so the feature remains disabled until an operator sets the
allowlist.

## Current repo state

PR #284 is merged. Both Terraform variables default to false/empty. The hosted
control plane has not yet been updated with these inputs.

## Research / references used

- `.github/workflows/terraform-plan.yml`
- `.github/workflows/terraform-apply.yml`
- `infrastructure/terraform/serverless-control-plane/variables.tf`
- `docs/product/EXECUTION_READINESS_MATRIX.md`

## Work planned for the PR

- Pass the explicit certification boolean and workspace-ID list into the
  protected Terraform plan workflow; apply consumes only the immutable saved
  plan produced from those inputs.
- Default the workflow inputs to false and an empty list.
- Document the expected GitHub Environment variable format and keep secrets out
  of the configuration.
- Add contract tests for both workflow files.

## Acceptance criteria

- [x] The protected plan workflow receives typed settings and apply applies only
  the saved plan containing those exact settings.
- [x] Missing settings keep the route disabled and deny every workspace.
- [x] A workspace ID can only be enabled through explicit GitHub Environment
  configuration.
- [x] Local tests and documentation checks pass.
- [ ] Required CI passes.

## Acceptance status

Workflow input wiring and classification are implemented and locally verified.
GitHub CI is pending. No GitHub Environment values have been changed and no AWS
deployment has been performed.

## Tests / validation performed

Commands and results will be recorded in `docs/test/test285.md`.

## Evidence files produced

- `docs/test/test285.md`.

## Boundaries

This PR does not change either setting in GitHub, enable the feature, deploy
customer infrastructure, or enable general customer execution.

## Follow-up work

Use a tightly scoped allowlisted workspace for the Lambda/API AWS certification,
then reset the settings to false/empty and deploy that disabled state.
