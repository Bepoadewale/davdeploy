# test358 — deployed API Gateway route policy

Date: 2026-11-11

Execution type: Protected control-plane Terraform plan and exact saved-plan
apply. No customer workload was deployed or changed.

Repository: `Bepoadewale/davdeploy`

Customer repository: Not applicable; this was a DavDeploy control-plane release.

Commit: `4de1022592fdf65cdd38f32386cbccbce5a40071` (PR #358 merge).

Terraform root: `infrastructure/terraform/serverless-control-plane`.

AWS account: `654654474502`.

AWS region: `us-east-1`.

Terraform plan run: [43088843169](https://github.com/Bepoadewale/davdeploy/actions/runs/43088843169).

Terraform apply run: [43091195912](https://github.com/Bepoadewale/davdeploy/actions/runs/43091195912).

GitHub deployment: `7720114909` (`terraform-apply` environment).

## Resources created

No AWS resources were created or destroyed. The saved plan updated six
existing control-plane Lambda functions in place.

## Commands executed

- Dispatched the protected Terraform plan workflow for exact merged `main`
  commit `4de1022592fdf65cdd38f32386cbccbce5a40071`.
- Reviewed the bounded saved-plan summary before apply.
- Dispatched the protected saved-plan apply for the reviewed run and approved
  the `terraform-apply` GitHub environment under the user's standing
  automatic-approval instruction.
- Ran read-only `aws sts get-caller-identity` and six selected Lambda
  configuration queries using profile `ai-platform-pilot-key`; only function
  state, update status, package digest, version and modification time were
  emitted.
- Ran `curl -fsS https://api.davdeploy.tech/healthz`.

## Observed result

The protected plan completed and was inspected before its exact saved plan was
approved and applied. Its bounded summary reported `applyable=true`,
`errored=false`, complete, 0 additions, 6 in-place Lambda updates, 0 destroys,
0 replacements, 0 other changes, 0 drift, and 8 output changes. The six
updated functions were `davdeploy-api`, `davdeploy-worker`,
`davdeploy-migrate`, `davdeploy-policy`, `davdeploy-cognito-link`, and
`davdeploy-cognito-email-sender`. The plan did not enable Nova execution gates.

The apply verified the selected plan run and saved-plan artifact, applied only
that plan, and completed database migration verification successfully. The
workflow completed with success for source commit
`4de1022592fdf65cdd38f32386cbccbce5a40071`.

AWS identity was confirmed as account `654654474502` in `us-east-1`. All six
control-plane Lambda functions reported `State=Active` and
`LastUpdateStatus=Successful`, with the common deployed package
`CodeSha256=ow5dokRWRp4rsyxb3NnPpkjIfil1xps+G4/OwLcgV9g=`. Their reported
modification times ranged from `2026-11-11T20:14:48Z` to
`2026-11-11T20:15:03Z`.

`GET https://api.davdeploy.tech/healthz` returned
`{"status":"ok","product":"davdeploy"}`.

The deployed API Lambda reported these Nova gates as `false`:

- `DAVDEPLOY_NOVA_PLAN_RUNNER_READY`
- `DAVDEPLOY_NOVA_PLAN_ROLE_VERIFY_ENABLED`
- `DAVDEPLOY_NOVA_PLAN_CREDENTIAL_BROKER_ENABLED`
- `DAVDEPLOY_TERRAFORM_STATE_ENABLED`
- `DAVDEPLOY_NOVA_PLAN_REVIEWS_ENABLED`
- `DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION`

The existing legacy cloud-execution command, `ALLOW_CLOUD_PLAN`, and
`ALLOW_CLOUD_APPLY` settings remain `true`. They do not enable Nova's
saved-plan planning or apply path.

PR #358's actual-plan authorization policy is deployed. PR #359's separate
untaggable-resource ownership change was merged after this apply and is not in
this Lambda package.

## Teardown

None. This control-plane release updated existing Lambda packages in place and
created or destroyed no resources.

## Final boundary

No Nova-generated customer plan was run or approved. No customer workload or
customer AWS resource was created, updated, or destroyed. This is control-plane
release evidence only; it does not establish customer planning, approval,
apply, health, recovery, or teardown readiness.
