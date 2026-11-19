# ticket438 — publish customer CloudFormation templates append-only

PR: [#438](https://github.com/Bepoadewale/davdeploy/pull/438) (open, draft)
Branch: `docs/template-host-append-only-20261119`

## Problem / goal

PR #381 retains older template objects, but its current-object resource does not have `prevent_destroy` when first created. A future replacement can therefore require a migration before protection applies. Make every new template protected from its first creation and keep each published S3 object at a stable Terraform address.

## Current repo state

- PR #381 is merged. The template host uses a content-hash S3 key, a distinct current-object resource, and a manually maintained map of older keys with `prevent_destroy`.
- The currently configured source template hash is `8c5d1c82682b3bb90ff1f45d121b475e7b33b484f556feabafbf387c335aea4e`.
- Existing URLs are customer-facing setup inputs and must continue to resolve unchanged.
- This work is source, documentation, and automated regression coverage. The initial lock-free read-only plan failed with an ambiguous move graph before producing a plan; no lock or AWS change occurred. After the move correction, a lock-free plan against actual protected state showed four address moves and `0 to add, 0 to change, 0 to destroy`. No apply has run.

## Research / references used

- Merged PR #381 and its migration/evidence: https://github.com/Bepoadewale/davdeploy/pull/381
- HashiCorp Terraform `moved` blocks: https://developer.hashicorp.com/terraform/language/block/moved
- HashiCorp AWS provider `aws_s3_object`: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_object
- Design rationale and migration steps: `docs/architecture/append-only-template-publishing.md`.

## Work planned for the PR

- Use the content-hash object key as the `for_each` key for one shared S3 object resource.
- Apply `prevent_destroy` to every instance from initial creation.
- Migrate all existing Terraform addresses with static `moved` blocks, retaining their existing S3 keys.
- Keep the current URL output and add regression assertions for protection and migration coverage.
- Document release operations, trade-offs, and the required protected-state plan acceptance.

## Acceptance criteria

- [x] New and retained objects use a stable content-hash-keyed resource address with `prevent_destroy = true`.
- [x] Existing current, retained, and historical state addresses have one-destination moves forming an explicit chain to the new resource shape without renaming S3 keys.
- [x] Existing template URLs remain unchanged; the output still points to the current source hash.
- [x] Focused regression tests, Terraform format/validation, and documentation conventions pass.
- [x] All seven PR CI checks passed in run `44504126648` on commit `98c8477`.
- [x] The corrected lock-free protected-state plan shows exactly four object address moves, `0 to add, 0 to change, 0 to destroy`, and no prior-object replacement or deletion.
- [x] No live AWS resources were modified, and no deployment is claimed.

## Acceptance status

The implementation, local/static validation, and corrected lock-free plan against actual protected state pass. The initial plan attempt failed with `Ambiguous move statements` at `main.tf` lines 116, 121, and 126, before producing a plan. After correction, exactly four object addresses moved with `0 to add, 0 to change, 0 to destroy`. Neither attempt acquired a state lock or changed AWS resources/state. PR #438 remains draft; no apply is claimed.

## Tests / validation performed

See `docs/test/test438.md` for commands, results, and the AWS/deployment boundary.

## Evidence files produced

- `docs/tickets/ticket438.md`
- `docs/test/test438.md`
- `docs/architecture/append-only-template-publishing.md`

## Boundaries

This PR does not publish a template, update a hosted URL, apply Terraform, modify live AWS resources, or install a customer CloudFormation stack or IAM role. A protected-state plan and any subsequent apply remain separately reviewed and approval-gated.

## Follow-up work

After merge, run and review a read-only plan against the protected template-host state. Proceed with a separate apply only with explicit approval and only if the plan preserves every existing key and proposes no prior-object mutation or deletion.
