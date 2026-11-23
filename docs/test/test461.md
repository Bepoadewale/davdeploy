# test461 — ECR repository module lifecycle

Date: 2026-11-23

Execution type: Controlled disposable AWS Terraform module validation.

Customer repository: None; direct same-account customer-side test.

PR: [#461](https://github.com/Bepoadewale/davdeploy/pull/461).

Commit: `156dcb9` (test evidence will be finalized on the PR head).

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

One fresh empty ECR repository, `davdeploy-nova-ecr-461-a1`, from the checked-in
`infrastructure/terraform/modules/ecr` module. No image was pushed. No existing
ECR repository or registry-wide setting was changed.

## Commands executed

- `terraform init -backend=false -input=false` with Terraform data stored under
  `/tmp/davdeploy-nova-ecr-461-tfdata`; provider `hashicorp/aws` v5.100.0 is
  pinned in the fixture lock file.
- `terraform fmt -check` and `terraform validate` — passed.
- Reviewed saved create plan: one ECR repository addition, no changes or
  deletions. The plan specified immutable tags, scan-on-push, AES256 encryption,
  and `force_delete=false`.
- Monitored create run `nova-ecr-repository-461-create-20261123-a1` stopped
  before AWS changes because the saved plan was followed by options. Corrected
  the argument order and ran `nova-ecr-repository-461-create-20261123-a1-retry1`;
  the monitor reports success with one resource created. The successful run
  used root `/Users/adewale/Projects/davdeploy/docs/test/fixtures/nova-ecr-repository-461`,
  supervisor PID `98276`, Terraform PID `98277`, and log
  `/var/folders/p1/wtz8hss162jgrh2bgr3n3wn400000gn/T/davdeploy-terraform-runs/nova-ecr-repository-461-create-20261123-a1-retry1.log`.
- The failed pre-mutation run used the same root, supervisor PID `96742`,
  Terraform PID `96743`, and log
  `/var/folders/p1/wtz8hss162jgrh2bgr3n3wn400000gn/T/davdeploy-terraform-runs/nova-ecr-repository-461-create-20261123-a1.log`.
- `aws ecr describe-repositories --repository-names davdeploy-nova-ecr-461-a1`
  confirmed the repository ARN, immutable tag setting, scan-on-push setting,
  and AES256 encryption.
- `aws ecr list-images --repository-name davdeploy-nova-ecr-461-a1` returned
  no images.
- Read-only `aws ecr get-registry-scanning-configuration` returned scanning
  type `BASIC` and no explicit rules. No registry-wide setting was changed and
  no image was pushed, so this test does not claim a vulnerability scan ran.
- Reviewed saved destroy plan: exactly one repository to destroy.
- Monitored teardown run `nova-ecr-repository-461-destroy-20261123-a1`
  succeeded: zero additions, zero changes, one repository destroyed. It used
  the same root, supervisor PID `401`, Terraform PID `402`, and log
  `/var/folders/p1/wtz8hss162jgrh2bgr3n3wn400000gn/T/davdeploy-terraform-runs/nova-ecr-repository-461-destroy-20261123-a1.log`.
- Independent `aws ecr describe-repositories` inventory after teardown listed
  only the pre-existing `my-app` repository. The `/tmp` Terraform state lists
  no resources, and the monitor has no active runs.

## Observed result

Terraform created the repository successfully. Independent AWS reads observed
`IMMUTABLE`, `scanOnPush=true`, and `AES256`; the repository contains no images.
This run verifies repository configuration and lifecycle only. It does not
verify image push/pull, image provenance, or a completed vulnerability scan.

## Teardown

The exact saved destroy plan removed the one ECR repository. The monitored run
succeeded and independent account/region inventory confirmed it absent. No
images were present, and the local Terraform state lists no resources.

## Final boundary

The control plane was not accessed or changed. The account-level ECR scanning
configuration was read only and left unchanged. This direct test is scoped to
the repository module configuration; it does not certify ECR workload support,
Nova dispatch, image provenance, effective registry-level scanning, or complete
pricing. No test repository or test image remains in AWS.
