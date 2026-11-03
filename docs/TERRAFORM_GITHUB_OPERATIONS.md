# Manual Terraform plan and apply

davdeploy uses two separate, manually dispatched GitHub Actions workflows for its single
production serverless control plane. Merging Terraform code never provisions infrastructure.

## Safety sequence

1. Merge a reviewed PR containing the Terraform change.
2. Manually run **Terraform plan** from `main` with `PLAN_SERVERLESS_CONTROL_PLANE`.
3. Review the complete successful plan run.
4. Without changing `main`, manually run **Terraform apply** with
   `APPLY_SAVED_SERVERLESS_PLAN`.
5. The apply workflow automatically selects the newest manual plan for the exact current `main`
   commit. It verifies that the plan succeeded, checks its workflow path and attempt, downloads its
   encrypted saved plan, verifies its manifest and SHA-256 digest, and applies only that plan.

If `main` changes after planning, apply fails closed. Run and review a new plan from the new commit
before applying.

There is no automatic apply trigger. The apply workflow cannot generate a replacement plan.

## Required GitHub environments

Create `terraform-plan` and `terraform-apply`. Configure required reviewers on
`terraform-apply`. Use separate least-privilege OIDC roles for planning and applying.

Required environment variables:

- `AWS_REGION`
- `EXPECTED_AWS_ACCOUNT_ID`
- `AWS_TERRAFORM_PLAN_ROLE_ARN` for `terraform-plan`
- `AWS_TERRAFORM_APPLY_ROLE_ARN` for `terraform-apply`
- `TF_STATE_BUCKET`
- `TF_STATE_LOCK_TABLE`
- `TF_PLAN_BUCKET`
- `TF_PLAN_KMS_KEY_ARN` for `terraform-plan`
- `TF_RELEASE_BUCKET` for `terraform-plan`
- `TF_RELEASE_KMS_KEY_ARN` for `terraform-plan`
- `FRONTEND_ORIGIN` for `terraform-plan`
- `AWS_CONNECTION_TEMPLATE_URL` for `terraform-plan`: the immutable public S3 URL emitted by the separately reviewed `connection-template-host` Terraform root. This is public template metadata, not a secret. Do not use a raw GitHub URL because CloudFormation does not accept it as `TemplateURL`.
- `RESEND_INVITATION_PARAMETER_NAME` for `terraform-plan`: the non-secret name of the exact
  Standard SSM SecureString that the hosted API role may read for Resend invitation delivery.
  Never store its value in GitHub; the value remains in Parameter Store.
- `COGNITO_DOMAIN_PREFIX` for `terraform-plan`; this is the single globally unique production
  Cognito domain prefix

These are non-secret deployment identifiers. Keep them as GitHub environment variables so their
classification is honest. Public visitors cannot read repository Settings, but workflow variables
are unencrypted and must never hold credentials. See `docs/CONFIGURATION_SECURITY.md`.

Optional `terraform-plan` variable:

- `GOOGLE_IDENTITY_PROVIDER_ENABLED`, default `false`
- `SERVERLESS_API_HOSTED_CERTIFICATION_ENABLED`, default `false`; keep false except for an explicitly approved, allowlisted renderer certification.
- `SERVERLESS_CERTIFICATION_WORKSPACE_IDS_JSON`, default `[]`; a JSON list of exact workspace IDs. An empty list denies every workspace. Configure these in `terraform-plan`; the apply workflow applies only the immutable plan created from those values.

Optional `terraform-plan` environment secrets:

- `BUDGET_NOTIFICATION_EMAIL`; keep the notification address encrypted rather than exposing it as
  a public repository or environment variable
- `SES_IDENTITY_ARN`; ARN of the verified `davdeploy.tech` Amazon SES identity used by Cognito
- `SES_FROM_ADDRESS`; bare verified sender address used for both Cognito From and Reply-To

Workspace invitation delivery is enabled when `RESEND_INVITATION_PARAMETER_NAME` identifies the
verified Resend sending key. The API role retrieves the value at runtime; the application never
exposes it in the browser. SES controls Cognito account and authentication mail only; it does not
control the active Resend invitation sender.

The state, plan, and release buckets must already exist. Enable versioning on the release bucket.
Keep both plan and state buckets private. The plan bucket holds sensitive saved plans and must use
KMS encryption. Do not use GitHub artifacts for saved Terraform plans in this public repository.

## AWS role boundary

Both workflows use GitHub OIDC and short-lived AWS credentials. Do not add access keys to GitHub.
The plan role may read state, acquire the state lock, publish versioned release packages, write
encrypted saved plans, and perform the read permissions Terraform needs. The apply role may read
the selected plan and state, acquire the lock, and change only the approved control-plane resource
scope. Both trust policies should restrict the repository, branch, and GitHub environment. This
repository uses GitHub's immutable OIDC subject customization, which includes owner and repository
numeric IDs. Role trust must use that exact subject rather than a name-only repository subject.

## Current boundary

The renamed prerequisite layer is active in account `654654474502`, region `us-east-1`:

- state bucket: `davdeploy-tfstate-654654474502`
- lock table: `davdeploy-terraform-locks`
- saved-plan bucket: `davdeploy-tfplans-654654474502`
- release bucket: `davdeploy-releases-654654474502`
- OIDC roles: `davdeploy-terraform-plan-github` and `davdeploy-terraform-apply-github`
- KMS aliases: `alias/davdeploy-terraform-plans` and `alias/davdeploy-lambda-releases`

The corresponding GitHub environments use these resources and the canonical production frontend
origin `https://davdeploy.tech`. The prior-name resources remain isolated and recoverable during
migration. They are not active workflow targets and must not be deleted until their state, object
versions, and rollback value have been reviewed separately.

Historical staging plan run `39140954204` completed successfully from `main` at commit
`3f4fe983a1b34a91e42967c1057bb723c20bdad9`, but it predates the single-production manifest
contract and cannot be applied.

Current deployed production release: plan run [41716352953](https://github.com/Bepoadewale/davdeploy/actions/runs/41716352953)
and apply run [41716835229](https://github.com/Bepoadewale/davdeploy/actions/runs/41716835229)
for commit `2d77ee2206a425813b8169eed460aff9b5634dc2`. The reviewed apply changed six existing
Lambda packages in place, created zero resources, and destroyed zero; database migrations completed
through schema version 24. All six Lambda functions report the same release code hash, and
`https://api.davdeploy.tech/healthz` returned HTTP 200 through the Cloudflare edge. App Runner
remains the only enabled customer renderer and multi-module runs are rejected.

PRs #277, #278 and #280 are deployed. Their module outcome and worker-lease state supports the
current single-renderer execution path; it is not a graph scheduler and does not enable new
renderers. Do not enable a new renderer as part of an unrelated deployment.

The production workflow uses one remote state object at
`serverless-control-plane/terraform.tfstate`, one canonical `davdeploy` resource namespace,
and one Cognito domain. Future development or staging environments require a separately reviewed
design change rather than an operator choice in the current workflow.

Google identity federation and SES sender configuration remain disabled until their provider setup
exists. SES delivery is enabled only by the two encrypted sender secrets described above. The budget
notification address is supplied through the encrypted `terraform-plan` environment secret when
configured.

The static frontend is active at `https://davdeploy.tech`; `https://davdeploy-frontend.pages.dev`
is a secondary Pages hostname. The hosted frontend uses the deployed API base URL and Cognito
authority/client values. API traffic passes through `https://api.davdeploy.tech`; direct API Gateway
requests without the origin guard are rejected. Do not replace the canonical public origins with
the secondary Pages hostname.
