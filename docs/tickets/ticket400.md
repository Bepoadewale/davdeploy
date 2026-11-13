# ticket400 — reconcile Nova readiness matrix with live gates

PR: [#400](https://github.com/Bepoadewale/davdeploy/pull/400)
Branch: `docs/reconcile-nova-readiness-400`

## Problem / goal

The readiness matrix still says that hosted plan reviews, the plan worker,
credential broker, and Terraform state API are disabled. The latest deployed
status section and read-only AWS configuration report those gates enabled. The
matrix must distinguish enabled infrastructure from actual customer evidence,
and include current draft PR #399 without claiming apply exists.

## Current repo state

- Backend `main` is `bded74a38bea677ed8dc8d9e4dad470892a96a3c` (PR #398).
- Latest hosted code is PR #390, deployed by plan `43388286514` and apply
  `43389226372`; deployment is not inferred from the newer source main.
- Read-only AWS checks on 2026-11-13 in account `654654474502`, region
  `us-east-1` found plan runner, plan reviews, role verification, credential
  broker, and Terraform state API enabled. No `davdeployPlan-*` customer role
  exists in the account. No customer plan or workload was applied, operated,
  or certified.
- Draft PR #399 adds an apply request contract and exact encrypted artifact
  restoration, but no apply dispatcher, apply credential broker, or apply
  CodeBuild project.
- Protected untracked `--only-show-errors` must remain untouched.

## Research / references used

- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `PROJECT_STATUS.md`
- `infrastructure/terraform/serverless-control-plane/main.tf`
- Draft PR #399 and `docs/tickets/ticket399.md`

## Work planned for the PR

- Correct the stale readiness matrix statements about deployed feature gates.
- Separate enabled control-plane gates from unproven customer role assumption,
  effective permissions, hosted plan execution, pricing, apply and lifecycle.
- Record PR #399 as draft source-only work and preserve the no-customer-apply
  statement.

## Acceptance criteria

- [x] Current source, current hosted release and runtime gate values are
  described separately and agree with the available evidence.
- [x] No customer plan/apply/health/recovery/destroy evidence is inferred from
  enabled flags, IAM simulations, code, or CI.
- [x] PR #399 is identified as draft and not deployed; pricing remains
  unavailable and approval/apply remain blocked.
- [x] Documentation conventions, diff checks and required CI pass in final-head
  run `43471519104` (all seven jobs).
- [x] No infrastructure or customer data changes occur.

## Acceptance status

Implementation and validation complete for this documentation-only scope.
Runtime behavior is unchanged.

## Tests / validation performed

`python3 scripts/check_doc_conventions.py` and `git diff --check` passed.
All seven required CI jobs passed in run `43471519104`. This is
documentation-only; no `docs/test/test400.md` is required.

## Evidence files produced

- `docs/tickets/ticket400.md`
- Updated Nova readiness matrix in `docs/product/EXECUTION_READINESS_MATRIX.md`

## Boundaries

This ticket changes readiness documentation only. It does not enable or deploy
any gate, create a customer role, approve a plan, or add apply behavior. The
### Follow-up work

The next runtime work remains hosted customer-role verification, trusted regional
pricing, then exact approved-plan apply and lifecycle evidence.
