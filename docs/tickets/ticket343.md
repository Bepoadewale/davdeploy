# ticket343 — retain the current customer template before publishing

PR: [#343](https://github.com/Bepoadewale/davdeploy/pull/343) (draft)
Branch: `infra/retain-current-cfn-template-343`

## Problem / goal

The live CloudFormation Quick Create URL points to immutable template key
`cloudformation/customer-discovery-role-7e03683a397f0d4e2a5f68b9559d2790ff127e5513540457b47e9c4779b2b793.yaml`.
Before publishing the updated bounded plan-role template, Terraform must move
the currently tracked S3 object into the retained set so existing customer
stacks and saved setup links keep working.

## Current repo state

- Backend `main` is `e95271b334fe9edddef9cc61c6990ed77c37ff9a` after PRs #341
  and #342; the latest customer template source is in `main`.
- The published object is in bucket `davdeploy-customer-templates-654654474502`
  in `us-east-1`. Read-only `HeadObject` confirmed it exists, is versioned,
  uses AES256, and was last modified `2026-10-29T16:00:54Z`.
- `connection-template-host` already retains two earlier immutable template
  keys, but not the current key above.
- No new template has been uploaded and no customer role has changed.

## Research / references used

- `infrastructure/terraform/connection-template-host/main.tf` defines an
  immutable content-hash template object and a separate retained-object map
  with `prevent_destroy` and `ignore_changes = all`.
- `infrastructure/terraform/connection-template-host/variables.tf` documents
  that the formerly-current key must be appended before each publish.
- `scripts/customer-aws-template-host.sh` checks the account and requires a
  separate apply confirmation; any apply must use the repository Terraform
  PID monitor and a freshly reviewed plan.

## Work planned for the PR

- Add the current live template key to `retained_template_keys`.
- Move the existing current-object address to its retained-object address, so
  the old public URL remains present when a new content-hash object is added.
- Add a regression test for the exact retained key and state move.
- Validate Terraform roots and publish no AWS changes in this PR.

## Acceptance criteria

- [x] The currently published immutable key is explicitly retained.
- [x] Terraform state moves the current object into the retained set rather
  than deleting or replacing the old object.
- [x] Focused test, clean-room CI verification, Terraform validation, docs
  checks, and required CI pass.
- [x] No AWS write, customer role change, or new public object is part of this
  source PR.

## Acceptance status

The retention key and state move were implemented in commits `93dfea5` and
`ea29d07`; PR #343 merged as `9eb5b79e35bb4f805de8bf6fc2450165b177f913`.
Focused tests (9 passed), all-root Terraform validation, docs conventions,
diff checks, and all seven CI jobs passed in run `42980959224`, including
clean-room integration. PR #344 corrected the actual state move and was
applied separately. PR #345 records that publication and control-plane URL
rollout. No customer stack or role was changed.

## Tests / validation performed

See `docs/test/test343.md` for exact local and hosted validation evidence.

## Evidence files produced

- `docs/test/test343.md`

## Boundaries

This PR only preserves the current immutable template object in Terraform
configuration. It neither publishes the updated template nor changes customer
IAM roles. The old object must remain available. Any subsequent host publish
and control-plane URL update require exact, separately reviewed plans.

## Follow-up work

Follow-up completed in PRs #344 and #345: the exact host plan was applied with
the old URL retained, and the protected control-plane URL was deployed and
verified. No customer stack or role was changed.
