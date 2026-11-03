# ticket285 — Wire certification allowlist into Terraform release workflow

PR: https://github.com/Bepoadewale/davdeploy/pull/285 (merged)
Branch: `feat/terraform-certification-inputs` (merged; deleted after merge)
Merged commit: `2e39e4a45fee9bd69b5827a48431c052e5f772e2`

## Problem / goal

The controlled Lambda/API certification gate and workspace allowlist now exist
in Terraform, but the protected plan/apply workflows do not pass GitHub
Environment variables into those Terraform inputs. Add explicit workflow wiring
with safe defaults so the feature remains disabled until an operator sets the
allowlist.

## Current repo state before this PR

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
- [x] Required CI passes (run [41729016251](https://github.com/Bepoadewale/davdeploy/actions/runs/41729016251)).

## Acceptance status

Workflow input wiring and classification are implemented, CI-verified and
deployed. Plan run [41729846651](https://github.com/Bepoadewale/davdeploy/actions/runs/41729846651)
for the merged commit planned 0 adds, 6 in-place Lambda code updates and 0
destroys. Apply run [41730396958](https://github.com/Bepoadewale/davdeploy/actions/runs/41730396958)
passed after the authorized environment review. Migration verification passed;
the public health endpoint returned HTTP 200. The certification gate is still
`false` and its workspace allowlist is empty. No customer workload was deployed.

## Tests / validation performed

Commands and results are recorded in `docs/test/test285.md`.

## Evidence files produced

- `docs/test/test285.md`.

## Boundaries

This PR wires both settings with disabled defaults. The merged release deployed
with those defaults and did not enable customer infrastructure execution.

## Follow-up work

Use a tightly scoped allowlisted workspace for the Lambda/API AWS certification,
then reset the settings to false/empty and deploy that disabled state.
