# test359 — deployed API Gateway route ownership policy

Date: 2026-11-11

Execution type: Protected control-plane Terraform plan and exact saved-plan
apply. This was not a Nova customer workload test.

Repository: `Bepoadewale/davdeploy`

Customer repository: Not applicable; this was a DavDeploy control-plane release.

Commit: `d734547a0551e85c5eafcc7349561e3ea7790589` (PR #359 merge).

Terraform root: `infrastructure/terraform/serverless-control-plane`.

AWS account: `654654474502`.

AWS region: `us-east-1`.

Terraform plan run: [43098415855](https://github.com/Bepoadewale/davdeploy/actions/runs/43098415855).

Terraform apply run: [43101777948](https://github.com/Bepoadewale/davdeploy/actions/runs/43101777948).

GitHub deployment: `7721332861` (`terraform-apply` environment).

## Resources created

No AWS resources were created or destroyed. The reviewed plan updated six
existing control-plane Lambda functions in place.

## Commands executed

- Dispatched `terraform-plan.yml` for exact merged `main` commit
  `d734547a0551e85c5eafcc7349561e3ea7790589`.
- Reviewed the bounded plan summary before apply: `applyable=true`,
  `errored=false`, `complete=true`; 0 additions, 6 in-place Lambda package
  updates, 0 destroys, 0 replacements or other changes, 0 drift, and 8 output
  changes.
- The plan summary identified only the `aws_lambda_function` resources `api`,
  `cognito_email_sender`, `cognito_link`, `migrate`, `policy`, and `worker`.
  Nova runner, plan-role verification, credential broker, plan reviews,
  Terraform state, and hosted certification were all `false` in planned values.
  Existing legacy cloud execution and `ALLOW_CLOUD_PLAN` / `ALLOW_CLOUD_APPLY`
  remained `true`; they are not Nova execution gates.
- Dispatched the protected exact saved-plan apply for run `43098415855`.
  The workflow verified the selected plan source, immutable manifest, and
  saved-plan SHA-256 before applying. The `terraform-apply` environment
  approval was recorded under the account owner's standing instruction.
- Ran read-only AWS identity and six selected Lambda configuration queries
  with profile `ai-platform-pilot-key`, emitting only function state, update
  status, package digest, modification time, and allowlisted runtime gates.
- Ran `curl -fsS https://api.davdeploy.tech/healthz`.

The first rollout attempt, run `43095354497`, ended `startup_failure` with no
jobs or Terraform execution. It was not treated as a plan; successful plan
`43098415855` and apply `43101777948` supersede that failed attempt.

## Observed result

Apply run `43101777948` succeeded for the exact saved plan and commit. Database
migration verification completed successfully. Read-only AWS identity was
account `654654474502` in `us-east-1`. All six control-plane Lambdas reported
`State=Active` and `LastUpdateStatus=Successful` with the common deployed
package `CodeSha256=vg52ZDcTSAhZ3hK7dra2Ou7oExSdzGDPjMBjoNQe4ZM=`.

`GET https://api.davdeploy.tech/healthz` returned
`{"status":"ok","product":"davdeploy"}`.

The deployed API configuration confirmed Nova plan runner, role verification,
credential broker, Terraform state API, plan review, and hosted certification
flags are `false`. Existing legacy cloud execution and plan/apply flags remain
`true` and do not enable the Nova saved-plan workflow.

## Teardown

None. The control-plane Lambda packages were updated in place; no disposable
customer or test resources were created.

## Final boundary

PR #359's state-backed ownership policy is deployed. No Nova-generated
customer plan was run or approved. No customer workload or customer AWS
resource was created, updated, or destroyed. This evidence does not establish
customer planning, pricing, approval, apply, application health, recovery,
data restoration, or teardown readiness.
