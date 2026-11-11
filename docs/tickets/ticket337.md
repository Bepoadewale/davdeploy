# ticket337 - grant exact Nova state provisioning permissions

PR: [#337](https://github.com/Bepoadewale/davdeploy/pull/337)
Branch: `fix/nova-state-bucket-apply-permissions-337`

## Problem / goal

Allow the existing GitHub Terraform apply role to finish provisioning the dedicated Nova Terraform state bucket and its KMS alias after the first reviewed apply stopped on two explicit access denials. Keep the runner, plan review, role verification, and state API disabled.

## Current repo state

- Main was at `1983ca815c40f26c1a33433ba263e04febf31098` when the state-storage-only plan was applied.
- Apply run [42950844151](https://github.com/Bepoadewale/davdeploy/actions/runs/42950844151) failed because the apply role lacked `kms:CreateAlias` and `s3:CreateBucket`. Terraform had already created the state KMS key and updated three Lambda packages/configurations. The saved plan must not be replayed.
- The apply role policy is defined by `infrastructure/terraform/terraform-operations-bootstrap/main.tf`; that root has no GitHub plan/apply workflow, so its permission update is applied through the repository Terraform run monitor after merge.

## Research / references used

- [AWS KMS alias permissions](https://docs.aws.amazon.com/kms/latest/developerguide/alias-access.html): alias creation requires permissions for both the alias and target key.
- [AWS S3 identity policy examples](https://docs.aws.amazon.com/AmazonS3/latest/userguide/example-policies-s3.html): `s3:LocationConstraint` can restrict bucket creation to a Region.
- [AWS S3 bucket tagging](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-create-tag.html): tagged bucket creation requires tagging permissions.

## Work planned for the PR

- Grant bucket creation and required setup actions only on `davdeploy-tfstate-<account>-<region>`, with an optional location constraint matching the configured Region.
- Grant `kms:CreateAlias` only for `alias/davdeploy-nova-terraform-state` and only against KMS keys tagged `Product=davdeploy` and `Purpose=nova-terraform-state`.
- Add a regression test that rejects bucket deletion/object access and broad alias permissions.
- Verify the exact bootstrap Terraform plan, apply it, then produce a new serverless plan from current state and review before applying.

## Acceptance criteria

- [x] IAM grants are limited to the exact dedicated state bucket and tagged state key/alias.
- [x] The apply role grants only the scoped setup actions; it gains no state-object access, bucket deletion, alias deletion, runner, state API, or customer workload permission from this change.
- [x] Focused tests, `make verify`, clean-room proof, Terraform formatting/validation, docs checks, and required CI pass; all seven CI checks passed in run [42953078494](https://github.com/Bepoadewale/davdeploy/actions/runs/42953078494).
- [x] The scoped operations-bootstrap permission update completed, then the fresh reviewed serverless plan from merged #338 was applied and reconciled.
- [x] The dedicated state bucket is versioned, SSE-KMS encrypted, private, and owner-enforced. State API, runner, plan review, and plan-role verification remain off.

## Acceptance status

- [x] Exact permission scopes and static regression coverage are implemented.
- [x] Focused tests, full verification, clean-room proof, Terraform formatting/validation, docs checks, and required CI pass at implementation head `cadcf57`.
- [x] The exact state-storage rollout was applied from current main and reconciled; see `docs/test/test337.md`.
- [x] Bucket controls were verified read-only; state API, runner, plan review, and role verification remain disabled.

## Tests / validation performed

See `docs/test/test337.md` for final commits, CI, protected plan/apply runs, and read-only post-apply observations.

## Evidence files produced

- `docs/test/test337.md` — local automated and Terraform validation, clean-room, CI, and exact AWS rollout observations.

## Boundaries

This does not enable the Nova plan runner, state API, plan review, or customer apply. A successful state-storage setup is infrastructure groundwork only. Keep the failed apply run as historical evidence and reconcile its partial result; do not re-run its saved plan.

## Follow-up work

State storage is provisioned. Safe hosted planning still requires a customer plan role with an attested least-privilege policy, tenant-isolated remote state through the separately gated state API, complete trusted regional pricing, and a durable worker path. Keep the runner, state API, plan review, and role verification disabled until their own security evidence and gates are satisfied.
