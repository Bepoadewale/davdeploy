# ticket337 - grant exact Nova state provisioning permissions

PR: [#337](https://github.com/Bepoadewale/davdeploy/pull/337)
Branch: `fix/nova-state-bucket-apply-permissions-337`

## Goal

Allow the existing GitHub Terraform apply role to finish provisioning the dedicated Nova Terraform state bucket and its KMS alias after the first reviewed apply stopped on two explicit access denials. Keep the runner, plan review, role verification, and state API disabled.

## Relevant state

- Main was at `1983ca815c40f26c1a33433ba263e04febf31098` when the state-storage-only plan was applied.
- Apply run [42950844151](https://github.com/Bepoadewale/davdeploy/actions/runs/42950844151) failed because the apply role lacked `kms:CreateAlias` and `s3:CreateBucket`. Terraform had already created the state KMS key and updated three Lambda packages/configurations. The saved plan must not be replayed.
- The apply role policy is defined by `infrastructure/terraform/terraform-operations-bootstrap/main.tf`; that root has no GitHub plan/apply workflow, so its permission update is applied through the repository Terraform run monitor after merge.

## Research

- [AWS KMS alias permissions](https://docs.aws.amazon.com/kms/latest/developerguide/alias-access.html): alias creation requires permissions for both the alias and target key.
- [AWS S3 identity policy examples](https://docs.aws.amazon.com/AmazonS3/latest/userguide/example-policies-s3.html): `s3:LocationConstraint` can restrict bucket creation to a Region.
- [AWS S3 bucket tagging](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucket-create-tag.html): tagged bucket creation requires tagging permissions.

## Work

- Grant bucket creation and required setup actions only on `davdeploy-tfstate-<account>-<region>`, with an optional location constraint matching the configured Region.
- Grant `kms:CreateAlias` only for `alias/davdeploy-nova-terraform-state` and only against KMS keys tagged `Product=davdeploy` and `Purpose=nova-terraform-state`.
- Add a regression test that rejects bucket deletion/object access and broad alias permissions.
- Verify the exact bootstrap Terraform plan, apply it, then produce a new serverless plan from current state and review before applying.

## Acceptance

- [x] IAM grants are limited to the exact dedicated state bucket and tagged state key/alias.
- [ ] The apply role gains no object read/write, bucket deletion, alias deletion, runner, state API, or customer workload permission from this change.
- [ ] Focused tests, `make verify`, clean-room proof, Terraform formatting/validation, docs checks, and required CI pass.
- [ ] Bootstrap saved plan has no unrelated changes; exact reviewed plan is applied and state reconciled.
- [ ] The dedicated state bucket is versioned, SSE-KMS, private, and owner-enforced. State API and runner remain off.

## Validation and evidence

See `docs/test/test337.md`; add final commit, CI run, plan/apply run IDs, and post-apply AWS observations before merge/final status.

## Boundaries and follow-up

This does not enable the Nova plan runner, state API, plan review, or customer apply. A successful state-storage setup is infrastructure groundwork only. Keep the failed apply run as historical evidence and reconcile its partial result; do not re-run its saved plan.
