# ticket345 — record Nova customer template rollout

PR: [#345](https://github.com/Bepoadewale/davdeploy/pull/345) (draft)
Branch: `docs/record-nova-template-rollout-345`

## Problem / goal

Record the exact production publication of the current customer plan-role
template, preserve the prior public setup URL, document the protected hosted
control-plane URL rollout, and reconcile current status documentation with
observed evidence.

## Current repo state

- PR #343 retained the previously published 7e object.
- PR #344 corrected the Terraform state move and published the f3d9e1 template.
- The control plane was still configured with the old template URL until the
  protected `terraform-plan` environment variable was updated and its saved
  plan was applied.
- Nova plan review, plan-only runner, plan-role verification, and Terraform
  state API remain disabled. Pricing evidence is unavailable and no
  Nova-generated customer plan is approvable.

## Research / references used

- `docs/test/test343.md` and `docs/test/test344.md`
- `docs/test/test341.md` for the previous protected release's evidence format
- `docs/customer-aws-connection.md`
- Protected workflows `.github/workflows/terraform-plan.yml` and
  `.github/workflows/terraform-apply.yml`
- Read-only AWS S3, Lambda, and API health checks recorded in `test345.md`

## Work planned for the PR

- Record the template-host saved plan and monitored apply, including the exact
  plan digest, created object, retained object, and absence of deletions.
- Record both public URL checks and object version/encryption metadata.
- Record protected GitHub variable update, plan artifact digest, saved-plan
  apply, migration result, Lambda health, and API health.
- Update current customer-template URL and hosted status documentation while
  preserving historical release evidence and product claims.
- Reconcile #343 and #344 follow-up statements with the completed rollout.

## Acceptance criteria

- [x] Evidence is tied to exact commits, plans, runs, account and region.
- [x] Existing and new immutable template URLs both return HTTP 200.
- [x] Template-host plan/apply creates only the intended new public object;
  the old key remains present and no customer stack/role changes.
- [x] Protected control-plane plan/apply and database migration succeed.
- [x] Six functions are Active with successful updates and the API health check
  returns HTTP 200.
- [x] Nova review/runner/role-verification/state API flags remain disabled;
  no Nova workload or customer resource is claimed as deployed.
- [x] Focused documentation convention and diff checks pass locally.
- [x] All required final-head CI checks pass.

## Acceptance status

Runtime rollout completed and is recorded in `docs/test/test345.md`. The
customer template source URL and current hosted status docs are reconciled.
Documentation convention and diff checks pass locally. All seven final-head
CI checks passed in run `42987624957`.

## Tests / validation performed

See `docs/test/test345.md` for exact AWS, workflow, and health-check evidence.

## Evidence files produced

- `docs/test/test345.md`

## Boundaries

This rollout publishes only the versioned CloudFormation template and updates
DavDeploy's hosted setup URL. It does not create or change a customer stack,
role, or workload. The legacy `ALLOW_CLOUD_APPLY=true` configuration was not
changed by this rollout; the Nova plan-only and review gates remain disabled.
Pricing, customer plan generation, customer apply, health, recovery and
teardown remain incomplete.

## Follow-up work

Continue the independent Nova plan-only runner, durable customer plan history,
trusted pricing, exact-plan approval, and lifecycle contract work. Do not
enable hosted customer plan/apply/cleanup gates before those dependencies are
implemented and verified.
