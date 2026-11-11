# test341 — production release of Nova plan-role boundary

Date: 2026-11-11

Execution type: Protected production control-plane Terraform plan and apply.
No customer account role was changed and no customer workload was deployed.

Customer repository: None. This release deployed the DavDeploy control-plane
package from backend PR #340.

Commit: `8d3b4764bcefae8cb9f93a930b064e10fd893762` (merge commit for PR #340).

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

None. The reviewed saved plan had 99 no-op resources, 6 in-place Lambda
function updates, 0 additions, and 0 deletions or replacements. All six
control-plane Lambda functions reported `State=Active` and
`LastUpdateStatus=Successful`. Their deployed `CodeSha256` values matched:
`7WRZObyX6jYTE2n4b9fLumY0h4GMAtm+I2cQv6WIIi0=`.

The plan changed the package object version for all six Lambda functions. The
API, worker, and migration functions also updated the
`DAVDEPLOY_CUSTOMER_EXECUTION_ARTIFACT_S3_URI` environment variable to refer to
this release's immutable package. No IAM role, API route, state bucket, or
customer resource was changed. The plan reported one state-drift record on the
Nova state bucket's parent `aws_s3_bucket` metadata (`policy`, encryption, and
versioning); the standalone bucket policy, encryption, and versioning resources
were no-ops, and the bucket itself had no planned action. No secret or plan
value was copied into this evidence.

## Commands executed

- `gh workflow run terraform-plan.yml --ref main -f confirmation=PLAN_SERVERLESS_CONTROL_PLANE`
  — [plan run 42973143188](https://github.com/Bepoadewale/davdeploy/actions/runs/42973143188), passed.
- Saved-plan manifest: version 2, commit above, run `42973143188`, attempt 1,
  production deployment, root
  `infrastructure/terraform/serverless-control-plane`; saved-plan SHA-256
  `74e6b78e0eef6daaa26334807f31fae4bade242a09a18331a7a4dfbc1b483a9d`.
  The plan artifact hash matched the manifest before apply.
- Redacted Terraform JSON review with Terraform 1.14.7 — 99 no-op resources,
  6 in-place Lambda updates, no create/delete/replace actions, no changed
  outputs. Review printed resource addresses/actions and changed field names
  only; environment values and other sensitive values were not displayed.
- `gh workflow run terraform-apply.yml --ref main -f confirmation=APPLY_SAVED_SERVERLESS_PLAN`
  — [apply run 42974086012](https://github.com/Bepoadewale/davdeploy/actions/runs/42974086012), passed after the protected `terraform-apply` deployment gate was approved under the user's standing authorization.
- The apply workflow completed its migration check successfully.
- Read-only `aws sts get-caller-identity` confirmed account `654654474502`.
- Read-only Lambda checks confirmed all six functions Active with successful
  updates and the same code hash listed above. The plan-review, plan-runner,
  role-verification, and state-API feature flags remained false on the API,
  worker, and migration functions.
- `curl -fsS https://api.davdeploy.tech/healthz` — returned
  `{"status":"ok","product":"davdeploy"}`.

## Observed result

The Nova plan-role permission-boundary code from PR #340 is deployed in the
DavDeploy control plane. The hosted customer planning, plan review, runner,
role verification, and state API remain disabled. The customer CloudFormation
role template is source code only until a customer installs it. This release
does not prove a customer role's effective permissions, execute a Nova plan,
or create customer infrastructure.

## Teardown

None required. The release created and destroyed no infrastructure resources.
Versioned release and saved-plan artifacts remain under their existing bucket
retention and access controls. They were not deleted.

## Final boundary

This verifies the production control-plane package release, successful
migration check, Lambda update state, feature-gate values, and public API health
for the exact commit. It does not verify customer IAM installation, hosted Nova
planning, regional pricing, saved-plan approval, customer apply, application
health, recovery, or customer teardown.
