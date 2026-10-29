# ticket200 — Retain immutable customer connection templates

PR: [#200](https://github.com/Bepoadewale/davdeploy/pull/200)
Branch: `fix/retain-connection-template-history`

## Problem / goal

Publishing a revised public CloudFormation template would replace the Terraform
object and delete the former immutable key. Existing customer stacks and saved
Quick Create links can reference that key.

## Current repo state

The connection-template host uses public, versioned object keys. The first
administrator-pilot-aware key is still referenced by existing setup evidence.

## Research / references used

The production template-host Terraform plan, its state, the immutable template
URL contract, and CloudFormation setup-link behaviour.

## Work planned for the PR

Move the existing object into an explicitly retained Terraform resource with
deletion protection, publish the active template under its new immutable key,
and document the retention rule for future revisions.

## Acceptance criteria

- [x] The former public template is retained, not deleted.
- [x] The new template has a distinct immutable key.
- [x] The production plan reports one add and zero deletes.

## Acceptance status

Published on 2026-10-29: one new immutable object was added; no prior template
object was deleted.

## Tests / validation performed

Connection-template Terraform validation passed. The controlled production plan
reported one addition, no changes, and no deletions. Eight focused tests passed.

## Evidence files produced

`docs/test/test200.md` records the plan evidence and retention boundary.

## Boundaries

No existing template, stack, role, workload, or customer record is deleted.

## Follow-up work

For every later template revision, append the formerly active key to
`retained_template_keys` before publication.
