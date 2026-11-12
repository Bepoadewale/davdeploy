# test368 — Nova source and hosted release reconciliation

Date: 2026-11-12  
Execution type: Protected control-plane Terraform plan/apply and read-only post-release verification  
Customer repository: N/A; no customer repository or workload was used  
Backend source: `0481696d8a9aa1c73d789b2076a23f9c07ccc1fb` (PR #367 merge)  
Commit: `0481696d8a9aa1c73d789b2076a23f9c07ccc1fb`  
AWS account: `654654474502`  
AWS region: `us-east-1`

## Resources created

- The protected control-plane release updated six Lambda package versions.
- No customer workload or customer AWS resource was created or changed.

## Commands executed

- `gh run watch 43138701232 --interval 300 --exit-status --compact`
- `gh run watch 43139500663 --interval 300 --exit-status --compact`
- Read-only AWS Lambda configuration and API health checks; no customer resource
  operations.

## Protected release workflow

- Main CI run [43137760056](https://github.com/Bepoadewale/davdeploy/actions/runs/43137760056) passed all seven required jobs for the merge commit.
- Protected Terraform plan [43138701232](https://github.com/Bepoadewale/davdeploy/actions/runs/43138701232) completed successfully for that exact commit and Terraform root `infrastructure/terraform/serverless-control-plane`.
- Exact saved-plan apply [43139500663](https://github.com/Bepoadewale/davdeploy/actions/runs/43139500663) succeeded as deployment `7726355215`. The workflow verified the plan run, commit, immutable manifest and saved-plan digest before applying. Migration verification succeeded.
- Manifest SHA-256: `724071565858a91b690b747553ababe317be73e76b108c457e3aa5dcdfeb64b3`; a streamed SHA-256 of the encrypted S3 saved-plan object matched. Raw Terraform plan content was not written to the local filesystem.

## Sanitized plan summary

- Terraform 1.14.7; applyable, complete, and no errors.
- 0 additions, 6 in-place Lambda package updates, 0 destroys, 0 replacements, 0 other changes, and 0 drift records; 8 output changes.
- Every updated function was an `aws_lambda_function`: `api`, `cognito_email_sender`, `cognito_link`, `migrate`, `policy`, and `worker`.
- The Nova plan runner, plan-role verification, credential broker, plan reviews, Terraform state API, and hosted certification were all planned `false`.
- Existing legacy cloud execution/plan/apply settings remained true; these are separate legacy controls and do not enable Nova.

## Post-apply observations

- AWS identity matched account `654654474502` in `us-east-1`.
- All six control-plane Lambdas reported `State=Active` and
  `LastUpdateStatus=Successful`, with common
  `CodeSha256=3TnyyXXSTrbTMpuDmE/4P302+IMHdJIX+dW86M9WbPc=`.
- API health endpoint returned `{"status":"ok","product":"davdeploy"}`.
- Read-only runtime configuration confirmed Nova runner, role verification,
  credential broker, plan reviews, Terraform state API, and hosted
  certification remain false. Legacy `ALLOW_CLOUD_PLAN` and
  `ALLOW_CLOUD_APPLY` remain true and are not Nova gates.

## Observed result

The exact reviewed control-plane plan applied successfully, migrations
completed, all six Lambda packages are healthy, and API health is good. The
Nova feature gates remain off. No customer Nova plan or infrastructure change
occurred.

## Teardown

Not applicable. The protected control-plane release is persistent and no
disposable customer test resources were created.

## Final boundary

This is a control-plane code release only. No Nova-generated customer plan,
customer workload, or customer-resource mutation occurred. The release does
not install a customer plan role, enable the worker/state API, provide
regional pricing, or allow exact-plan approval/apply. Runtime health,
recovery, teardown, and composed customer certification remain incomplete.
PR #318 pricing work remains held pending account-owner direction.
