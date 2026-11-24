# ticket491 — verify private S3 artifact module lifecycle

PR: [#491 — test: verify S3 artifact module lifecycle](https://github.com/Bepoadewale/davdeploy/pull/491) (draft)
Branch: `test/s3-artifacts-lifecycle-491`

## Problem / goal

The Nova evidence map has private S3 usage through other workflows but no
exact-module lifecycle test for `modules/artifacts`. Verify the module's
public-access block, owner-enforced ownership, versioning, and AES256 default
encryption, then exercise synthetic object create/read/update/recovery and
exact cleanup.

## Current repo state

- Backend `main` is `aec05f72a24afcff00882077ccc19d3acb1f8be3` (PR #490).
- PR #486 remains open; its clean-room generated artifacts stay preserved
  pending explicit approval for their exact cleanup.
- PR #489 records the exact Lambda lifecycle; no matching Lambda resources
  remain. Terraform monitor has 59 records and zero active operations.
- AWS caller account is `654654474502`, region `us-east-1`. The hosted control
  plane, Terraform remote state, and locks are outside this test scope.

## Research / references used

- Local module source: `infrastructure/terraform/modules/artifacts/main.tf`.
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md` and
  `docs/test/test262.md`, `docs/test/test299.md`, and `docs/test/test399.md`.
- AWS APIs used by the test: S3 `GetBucketEncryption`,
  `GetBucketOwnershipControls`, `GetPublicAccessBlock`, `GetBucketVersioning`,
  object version reads, and exact-key version deletion.

## Work planned for the PR

1. Add a local-state fixture using exactly one `modules/artifacts` instance
   with unique `TestId` tags.
2. Add a bounded helper that confirms the account and bucket ownership before
   uploading two synthetic object versions, verifies both contents and
   encryption, then deletes only versions/delete markers for its exact test
   key.
3. Review create/destroy plans and run both mutations through the Terraform
   monitor; independently verify bucket absence and retain local state.
4. Record the exact resource profile, results, and evidence limits. Update the
   capability matrix only for the `modules/artifacts` shape.

## Acceptance criteria

- [x] The fixture creates only the tagged exact-module S3 bucket resources
  using local Terraform state.
- [x] AWS reads confirm all public access blocks, `BucketOwnerEnforced`,
  versioning enabled, and default AES256 encryption.
- [x] Synthetic object v1/v2 reads prove version history and latest-object
  behavior without logging object contents.
- [x] Cleanup deletes only the test object's exact versions/delete markers;
  monitored destroy and independent AWS reads confirm the bucket is absent.
- [x] Local state and generated artifacts are retained; no control-plane,
  remote-state, unrelated AWS, or customer data is touched.
- [x] Ticket/test docs and matrix report exact evidence and limitations;
  focused tests, Terraform checks, docs conventions, and diff checks pass.
- [ ] Final-head PR CI passes before merge.

## Acceptance status

Ticket-first draft opened before implementation. In AWS account
`654654474502`, the exact-module fixture created the tagged bucket from a
five-create plan, verified settings, read two synthetic object versions, and
removed exactly those versions. A reviewed five-delete destroy completed via
the run monitor. Independent reads confirmed the bucket absent, local state
retained, and zero active Terraform operations. No control-plane or remote
state resource changed. Final evidence CI is pending.

## Tests / validation performed

- Ticket-first documentation conventions and `git diff --check`: passed.
- Focused helper tests: 6 passed; Ruff: passed.
- Terraform format and fixture validation: passed.
- Create run `nova-s3-artifacts-491-create-20261124-a1b2c3` succeeded; Terraform
  PID `54017`, supervisor PID `54016`, finish `2026-11-24T21:42:45Z`.
- Destroy-plan apply `nova-s3-artifacts-491-destroy-20261124-a1b2c3`
  succeeded; Terraform PID `55883`, supervisor PID `55882`, finish
  `2026-11-24T21:48:56Z`.
- Independent account/resource/state checks passed; monitor has 59 records and
  zero active operations. The bucket and exact object key are absent; local
  state remains retained.
- Final-head PR CI: pending after evidence update.

## Evidence files produced

- `docs/tickets/ticket491.md`
- `docs/test/test491.md`
- `docs/test/fixtures/nova-s3-artifacts-491/`
- `scripts/s3_artifacts_lifecycle.py`
- `tests/test_s3_artifacts_lifecycle_script.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

## Boundaries

Use a verified same-account disposable resource, unique prefix and local state.
The helper may remove only versions and delete markers for the exact synthetic
object key it created after verifying the bucket's `TestId`. Do not use bucket
recursive cleanup, alter the hosted control plane or remote state, or include
customer data/secrets in the object or logs.

## Follow-up work

This test does not prove Nova authorization or dispatch, cross-account
isolation, private client authorization, complete S3 pricing, retention policy,
or a composed application lifecycle.
