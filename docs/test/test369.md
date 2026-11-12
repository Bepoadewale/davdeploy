# test369 — deploy the Nova plan-role verification gate

Date: 2026-11-12  
Execution type: Protected control-plane Terraform plan/apply and read-only post-release verification  
Customer repository: N/A; no customer repository or workload was used  
Backend source: `8cebf39f700309fbb57c1b307c18026204be844d`  
Commit: `8cebf39f700309fbb57c1b307c18026204be844d`  
Terraform root: `infrastructure/terraform/serverless-control-plane`  
AWS account: `654654474502`  
AWS region: `us-east-1`

## Purpose

Enable the authenticated plan-role trust/account verification endpoint. This
does not enable Nova planning, approval, apply, or customer workload execution.

## Protected release evidence

- Plan [43144381303](https://github.com/Bepoadewale/davdeploy/actions/runs/43144381303)
  succeeded and was complete/applyable with no errors.
- Sanitized plan summary: 0 additions, 7 in-place updates (the API role policy
  and six Lambda packages), 0 destroys/replacements, 0 drift, and 8 output
  changes.
- Only `DAVDEPLOY_NOVA_PLAN_ROLE_VERIFY_ENABLED` was enabled. The plan runner,
  credential broker, plan reviews, Terraform state API, and hosted
  certification remained false. Existing legacy cloud execution flags are
  separate.
- The IAM permission is limited to `sts:AssumeRole` on
  `arn:aws:iam::*:role/davdeployPlan-*`, conditioned on a nonempty external ID
  and `davdeploy-plan-verify-*` role-session name. Its purpose is trust and
  account identity verification only; it does not verify effective permissions.
- Saved-plan SHA-256:
  `dd705e3003d9dc771d961665681068bc429f5b0e066f8b28aed3e30780efe6d3`.
  Streaming the encrypted S3 saved-plan object reproduced this digest. The
  manifest bound run `43144381303`, attempt 1, source commit, production
  deployment, and the serverless control-plane Terraform root.
- Exact saved-plan apply [43145180803](https://github.com/Bepoadewale/davdeploy/actions/runs/43145180803)
  succeeded as deployment `7727105514`; the workflow verified the manifest
  and plan digest. Database migrations completed successfully.

## Resources created

- Six existing control-plane Lambda package versions and the API Lambda role
  policy were updated.
- No customer workload, customer role, or customer AWS resource was created.

## Commands executed

- `gh run watch 43144381303 --interval 300 --exit-status --compact`
- `gh run watch 43145180803 --interval 300 --exit-status --compact`
- Read-only AWS Lambda configuration and API health checks.
- Streamed the encrypted saved-plan object to verify its SHA-256 digest; raw
  Terraform plan content was not written locally.

## Post-apply observations

- AWS caller account was `654654474502`.
- All six control-plane Lambda functions are Active with successful updates
  and common `CodeSha256=IbVtk5DgEOPl6OZu9qOsmh5bTHf1qz+y8sFekwGkDkE=`.
- API, worker, and migration Lambda configuration reports role verification
  `true`; runner, broker, plan reviews, state API, and hosted certification
  report `false`.
- `https://api.davdeploy.tech/healthz` returned
  `{"status":"ok","product":"davdeploy"}`.
- No customer plan role was installed or verified. No Nova customer plan,
  workload, or AWS resource mutation occurred.

## Observed result

The exact plan completed successfully, migrations passed, all six control-plane
Lambdas are active with successful updates, and the API health endpoint is
healthy. Only plan-role trust/account verification is enabled. No customer
role was installed or verified, and no Nova plan or workload was run.

## Teardown

Not applicable: this was a persistent control-plane configuration release and
created no disposable resources. A customer administrator must install and
verify a plan role through the authenticated connection workflow.

## Final boundary

This release does not attest effective customer role permissions, enable the
worker/state API, provide complete regional pricing, or allow exact-plan
approval/apply. Customer workload health, recovery, teardown, and composed
certification remain incomplete. Pricing PR #318 remains held pending
account-owner direction.
