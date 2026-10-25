# ticket144: Split control-plane state access from customer provider access

PR: #144
Branch: fix/customer-state-provider-credentials

## Problem / goal

The scoped customer role correctly denies access to DavDeploy's control-plane
Terraform state bucket. Terraform needs runner credentials for its backend and
the short-lived customer session only for the AWS provider and customer API
calls.

## Current repo state

The runner exports the assumed customer session globally. This switches both
the Terraform backend and provider to customer credentials, causing the backend
state read to fail safely with S3 access denied.

## Research / references used

- Failed real plan run `9cebd2cb-8375-4b67-b39a-e3d72bfe3c9c`.
- Terraform S3 backend and AWS provider credential separation.
- Existing CodeBuild executor state-bucket policy and customer-role boundary.

## Work planned for the PR

- Write the assumed customer session to an ephemeral named shared-credentials
  profile without exporting it as the process default.
- Configure the Terraform AWS provider to use only that named profile.
- Route bounded customer AWS API calls through that profile.
- Preserve runner credentials for state and result-artifact operations.

## Acceptance criteria

- [x] The Terraform backend continues using the isolated runner role.
- [x] Terraform resource operations and customer checks use the scoped role.
- [x] The external ID does not reach Terraform variables, plans, or state.
- [ ] Focused tests and required CI pass.
- [ ] The released runner completes a fresh real customer plan and apply.

## Acceptance status

Implementation is complete. Focused local validation, CI, guarded release, and
a fresh live customer plan/apply remain.

## Tests / validation performed

- Pending focused Terraform, shell, lifecycle, and documentation checks.

## Evidence files produced

- Customer live-run evidence continues in `docs/test/test130.md`.

## Boundaries

- The temporary profile contains only short-lived STS credentials within the
  ephemeral runner filesystem.
- The result artifact and Terraform state remain under the control-plane role.
- This does not broaden customer or control-plane IAM permissions.

## Follow-up work

- Release the immutable runner through the guarded workflow.
- Run the signed customer plan, reviewed apply, observation, and destroy flow.
