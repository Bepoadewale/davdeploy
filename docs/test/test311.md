# test311 — Nova proposal to real Terraform saved plan

Date: 2026-11-04

Execution type: real AWS-authenticated Terraform plan only. No apply, destroy,
or AWS resource creation was run.

Customer repository: None. The proposal and bucket name are synthetic.

Repository: `Bepoadewale/davdeploy`.

Commit: PR #311 branch working tree; implementation is committed with this PR.

AWS account: `654654474502` (confirmed by STS caller identity and a Terraform
`aws_caller_identity` plan precondition).

AWS region: `us-east-1`.

Terraform version: `1.14.7`, downloaded from HashiCorp and checked against its
published SHA256 sums.

AWS provider: `5.100.0`, from the repository's committed lockfile. Lockfile
SHA256: `5f753c99e33ab4c4a9de6b2096b69c61561dbe80945c43b1c5c6f2f039ffbdf1`.

## Commands executed

The repository's `GeneratedTerraformPlanRunner.plan` method ran these fixed
Terraform commands in a private local workspace, with backend disabled:

```text
terraform version -json
terraform init -backend=false -input=false -lockfile=readonly -no-color
terraform providers schema -json
terraform validate -no-color
terraform plan -input=false -lock=false -no-color -out=saved.tfplan
terraform show -json saved.tfplan
```

The exact proposal and trusted configuration were bound by SHA256 digests:

- Proposal: `e16d113bac3ecb0391924727f90f98cb1a8c400e6bfdfbfe55879c8cbb20d0bb`
- Generated configuration: `ff1a252132198ccb8ab3906d306af7557fd100d8afaca6e63deb5e237ae2c846`
- Saved plan: `33ad15739fc251d5789af50b338a6ac2e7b2cf9df83f2a197fa702863d9c6ae6`

## Observed result

The saved plan was valid, applyable and not errored. Terraform proposed two
creates: synthetic `aws_s3_bucket.bucket` and the trusted account-guard
`terraform_data.account_guard`; there were no updates, deletes, replacements or
drift. The inspector returned resource addresses and actions only; it did not
return planned values or sensitive data.

## Resources created

No AWS resources were created, so there were no AWS resources to destroy.

## Teardown

No AWS teardown or absence check was needed because this was a plan-only run.

## Retained resources

The local saved-plan artifact and initialized provider cache remain in the private workspace:
`/Users/adewale/.cache/davdeploy-tools/terraform-1.14.7/nova-plan-pr311-20261104`.
The saved plan file is mode `0600`; the workspace is private. It was retained
for reproducibility and was not deleted.

## Final boundary

This proves a local, authenticated, actual Terraform plan against the target
AWS account and the pinned AWS provider. It does not prove hosted CodeBuild
dispatch, pricing accuracy, customer approval, apply, application health,
recovery or cleanup. No customer workload was deployed.
