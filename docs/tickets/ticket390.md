# ticket390 — bootstrap the fixed Nova override-deny policy

PR: https://github.com/Bepoadewale/davdeploy/pull/390
Branch: `fix/scope-nova-policy-create-permission-390`

## Problem / goal

The protected apply run `43383886857` failed after partial updates because the
GitHub Terraform apply role was denied `iam:CreatePolicy` for the fixed
`nova-plan-only-start-build-overrides` policy. Create and own this fixed deny
policy in the existing operations-bootstrap stack, then have the serverless
Terraform root look it up and attach it. Do not grant the GitHub apply role
policy-creation permissions.

## Current repo state

- Backend `main`: `2a4b4223d987f314574ace41360afb9b25f6a3f1` (PR #389).
- Apply `43383886857` is terminal failure. The inline StartBuild policy, fixed
  CodeBuild project and runner policy updates, and six Lambda updates
  completed. Creation of the managed deny policy failed with `AccessDenied`;
  its role attachment was not attempted. Do not reuse the saved plan
  `43383020849` or dispatch another control-plane apply until this permission
  is deployed and a fresh plan is reviewed.
- The apply role already has role-scoped attach permission for DavDeploy roles.
  Keep its IAM permissions unchanged; the existing trusted operations-bootstrap
  apply creates the deny policy with a fixed document.
- No customer Nova workload has been started. Protected untracked
  `--only-show-errors` remains untouched.

## Research / references used

- `infrastructure/terraform/terraform-operations-bootstrap/main.tf`
- `tests/test_terraform_operations_bootstrap.py`
- AWS IAM [managed policy resource controls](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_controlling.html)
- AWS IAM [managed policy versioning](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_managed-versioning.html)
- Failure from run `43383886857`: no identity-based permission for
  `iam:CreatePolicy` on `policy/nova-plan-only-start-build-overrides`.

## Work planned for the PR

- Create the tagged managed policy in operations-bootstrap, targeting only the
  fixed Nova CodeBuild project and preserving all 22 existing override deny
  keys plus the environment-name deny.
- Replace the serverless root's policy resource with a data lookup of that
  fixed policy ARN, then attach it to the API role only when the runner is
  enabled.
- Test that deny keys match across roots, the policy document remains under
  AWS's managed-policy size limit, and the GitHub apply role receives no new
  policy-creation permission.
- Validate both Terraform roots and run required CI.

## Acceptance criteria

- [x] Operations-bootstrap owns the fixed override policy; serverless only
  looks it up and attaches it.
- [x] GitHub apply role gets no new IAM policy-management permission.
- [x] Focused tests, full verification and Terraform validation pass.
- [ ] Required CI passes and PR merges.
- [ ] Bootstrap deployment and fresh protected control-plane plan/apply pass.
- [ ] A monitored operations-bootstrap plan/apply deploys the permission; then
  a fresh protected control-plane plan is reviewed before any apply.

## Acceptance status

- [x] Implementation and local verification complete.
- [ ] Hosted CI and merge pending.
- [ ] Bootstrap deployment pending.
- [ ] Fresh control-plane plan and deployment pending.

## Tests / validation performed

- `.venv/bin/python -m pytest tests/test_terraform_operations_bootstrap.py tests/test_nova_plan_only_infra.py tests/test_nova_plan_artifact_infra.py -q` — 23 passed.
- `make verify` — 1,063 tests passed; Ruff, Actions configuration, OpenAPI and Compose checks passed (one existing Starlette/httpx deprecation warning).
- `terraform fmt -check -recursive infrastructure/terraform/terraform-operations-bootstrap infrastructure/terraform/serverless-control-plane` passed.
- `terraform -chdir=infrastructure/terraform/terraform-operations-bootstrap validate` and the corresponding serverless-control-plane validate both passed.
- `git diff --check` passed.
- Full local clean-room proof was not run because the existing shared `davdeploy` containers occupy the fixed host ports used by the local stack. I left that running stack untouched; hosted `local-e2e` remains the clean integration check.

## Evidence files produced

- `docs/tickets/ticket390.md`

## Boundaries

Do not grant IAM policy creation to the GitHub apply role. Do not retry either
failed control-plane plan. The override-deny policy must remain separate from
the API role's aggregate inline-policy quota. This PR does not enable customer
apply or certification.

## Follow-up work

After merge, use the repository PID-based Terraform monitor to create and
review a no-destroy operations-bootstrap plan, then apply it. Record the run and
result. Create and inspect a fresh serverless-control-plane plan against
current `main`; apply that exact plan only if it succeeds without unexpected
destructive actions.
