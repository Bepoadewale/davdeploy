# ticket438 — publish customer CloudFormation templates append-only

PR: [#438](https://github.com/Bepoadewale/davdeploy/pull/438) (open, draft)
Branch: `docs/template-host-append-only-20261119`

## Problem / goal

PR #381 retains older template objects, but its current-object resource does not have `prevent_destroy` when first created. A future replacement can therefore require a migration before protection applies. Make every new template protected from its first creation and keep each published S3 object at a stable Terraform address.

## Current repo state

- PR #381 is merged. The template host uses a content-hash S3 key, a distinct current-object resource, and a manually maintained map of older keys with `prevent_destroy`.
- The currently configured source template hash is `8c5d1c82682b3bb90ff1f45d121b475e7b33b484f556feabafbf387c335aea4e`.
- Existing URLs are customer-facing setup inputs and must continue to resolve unchanged.
- This work is source, documentation, and automated regression coverage only. No live AWS plan or apply has been run.

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
- [x] Existing current, retained, and historical state addresses have explicit moves to the new resource shape without renaming S3 keys.
- [x] Existing template URLs remain unchanged; the output still points to the current source hash.
- [x] Focused regression tests, Terraform format/validation, and documentation conventions pass.
- [x] PR CI passed all seven checks on the prior source head in run `44496579412`; the latest documentation-only head is pending CI.
- [ ] A future approved protected-state plan has zero existing-object changes, replacements, or deletions.
- [x] No live AWS resources were modified, and no deployment is claimed.

## Acceptance status

The implementation, local/static validation, and prior seven-check CI run pass. PR #438 remains draft; CI for the latest documentation-only commit is pending. The future protected-state plan remains pending. No live plan or apply is claimed.

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
