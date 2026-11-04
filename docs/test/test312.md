# test312 — deterministic policy for generated Terraform plans

Date: 2026-11-04

Execution type: authenticated Terraform plan only. No apply, destroy, or AWS
resource creation was run.

Test ID: `pr312-synthetic-s3-policy-plan`.

Repository: `Bepoadewale/davdeploy`, PR #312 branch.

Customer repository: None. All proposed resources and names are synthetic.

Commit: PR #312 working tree (the exact source commit will be added after commit).

AWS account: `654654474502`, verified before planning through STS and enforced
again by the generated Terraform account guard.

AWS region: `us-east-1`.

Terraform: `1.14.7`, previously checksum-verified from HashiCorp's published
checksums. AWS provider: `5.100.0`, from the repository's committed lockfile.

## Commands executed

The runner invoked these fixed commands with backend disabled and the pinned
provider lockfile: `terraform version -json`, `terraform init -backend=false
-input=false -lockfile=readonly -no-color`, `terraform providers schema -json`,
`terraform validate -no-color`, `terraform plan -input=false -lock=false
-no-color -out=saved.tfplan`, and `terraform show -json saved.tfplan`.

Focused regression command: `uv run pytest -q
tests/test_generated_plan_policy.py tests/test_generated_plan_inspection.py
tests/test_generated_terraform_plan.py` (62 passed). Full command: `make verify`
(590 passed, Ruff, Actions configuration, OpenAPI snapshot, Compose
configuration). Documentation convention check: `python3.12
scripts/check_doc_conventions.py` (passed).

The resulting saved plan was then re-opened with `terraform show -json` and
passed to the plan inspection and policy functions. Only finding codes,
summary counts, and SHA256 digests were printed.

## Observed result

The synthetic proposal contains one S3 bucket and an
`aws_s3_bucket_public_access_block` that sets all four public-access controls
to `true`. Terraform planned three creates: the bucket, its public access block, and the trusted account guard. There were zero updates, deletes, replacements, and drift findings.

Policy result: `ELIGIBLE_FOR_HUMAN_REVIEW`, version
`nova-generated-plan-2026-11-04.2`, no findings. Human approval remains
required. The S3 public-access block refers to the bucket's computed ID, which
Terraform leaves unknown during planning. The evaluator verifies that
association from Terraform's configuration-reference metadata.

## Resources created

No AWS resources were created.

## Teardown

No AWS cleanup was needed because this was plan-only. The saved plan artifact
remains in a private local workspace and was not deleted.

## Data handling

The policy reads Terraform plan JSON in memory and returns only summary,
policy findings, and digests. It does not persist or return plan values or
secrets.

## Digest evidence

- Proposal SHA256: `334a0bde4c3bee3be9aeea303e753767f626ea9016452c8dc297bb30661d93f9`
- Generated configuration SHA256: `6547b41dbd5878d985f8f0189270ef12852059086f9802fec89ac25ca26d05d7`
- Saved plan SHA256: `fa8f5f75cf8d72ef84fc5f6a9bb4599374d938905a88dac140f51a579c37a680`

## Negative evidence

An initial run of the same proposal was denied with
`s3_public_access_block_missing` because the first policy implementation only
compared the computed bucket ID. After using the plan's configuration
references to associate the block with the bucket, the safe proposal became
eligible for human review. Focused tests also deny missing/incomplete S3
public-access controls, public ACLs, sensitive public ports, wildcard IAM
administration/pass-role, wildcard trust, public or unencrypted databases,
unbounded ingress, unproposed resource changes, and malformed/unknown policy
inputs. Public web ingress, destructive changes, and sensitive changes require
explicit human review. Direct public S3 bucket policies are denied. The final
policy also verifies the generated trusted account-guard precondition,
inventories nested modules, and rejects malformed IAM documents and invalid
CIDR values.

## Final boundary

The mode-0600 saved plan remains in the private local workspace:
`/Users/adewale/.cache/davdeploy-tools/terraform-1.14.7/nova-plan-pr312-20261104c/saved.tfplan`.
It was not deleted. No AWS resource was created, so no AWS cleanup was needed.

This validates an initial policy baseline against one real composed Terraform
plan and synthetic negative cases. It does not prove comprehensive coverage
of every AWS service, pricing accuracy, customer approval, hosted worker
execution, apply, health, recovery, or cleanup.
