# ticket344 — fix customer template retention address migration

PR: [#344](https://github.com/Bepoadewale/davdeploy/pull/344) (draft)
Branch: `fix/template-retention-address-344`

## Problem / goal

The first hosted Terraform plan after PR #343 failed before planning changes.
Terraform rejects a `moved` block whose source address remains declared as the
new current object. Preserve the existing public customer template and allow a
new immutable content-hash template to be planned at a distinct resource
address.

## Current repo state

- PR #343 merged as `9eb5b79e35bb4f805de8bf6fc2450165b177f913`; it adds the
  currently published key `7e03683a...b2b793.yaml` to the retained set and
  moves the former current address into that map.
- The first read-only plan used AWS account `654654474502`, region `us-east-1`,
  state key `davdeploy/connection-template-host.tfstate`, and bucket
  `davdeploy-customer-templates-654654474502`.
- That plan failed with Terraform `Moved object still exists` because the same
  `current_customer_discovery_role` address was still declared for the new
  template object. No apply or AWS write occurred.
- A corrected read-only plan then exposed that the active state address is
  `active_customer_discovery_role`, not `current_customer_discovery_role`.
  Read-only `HeadObject` confirmed the 7e key exists (5,401 bytes) and the
  configured 0e key returns 404; the 600 key exists (4,950 bytes). No object
  was written or removed.
- Historical PR #326 documents the same Terraform constraint and its earlier
  address correction in `docs/test/test326.md`.

## Research / references used

- `infrastructure/terraform/connection-template-host/main.tf`
- `infrastructure/terraform/connection-template-host/outputs.tf`
- `docs/test/test326.md` for the earlier migration-address correction
- Terraform's `moved` block semantics, validated by the hosted plan failure

## Work planned for the PR

- Rename the newly published content-hash object to a distinct
  `published_customer_discovery_role` address.
- Move the actual former `active_customer_discovery_role` state address to the
  retained entry for the verified live 7e key.
- Remove the stale 0e placeholder from the retained configuration because
  read-only S3 metadata confirmed that key is absent.
- Point the customer setup URL output at the newly published object.
- Add a regression assertion for the distinct declaration, move source, and
  output reference.
- Re-run focused tests and Terraform validation, then re-run the hosted plan.
  Apply only if the exact plan retains the existing public URL and has no
  unexpected deletes or replacements.

## Acceptance criteria

- [x] The verified live 7e key and actual active state address move to the
  matching retained entry; the absent 0e key is not created.
- [x] The new published object has an address distinct from the moved source.
- [x] The output URL uses the new published object address.
- [x] Focused tests, Terraform validation, docs checks, and required CI pass.
- [x] A new hosted plan succeeds and preserves the prior public object; any
  hosted apply is recorded separately and occurs only for an exact safe plan.
- [x] The failed initial plan is recorded accurately; no AWS mutation occurred.

## Acceptance status

The final implementation/evidence head is `dda5068`. Focused tests passed (9),
Terraform format and all-root validation passed, and documentation conventions
and diff checks passed. The corrected read-only hosted plan proposes one object
creation (the new f3d9e1 template), moves the old active state to the retained
7e key, and has zero changes or destroys. All seven required checks passed in
run `42982526696`. No AWS write occurred.

## Tests / validation performed

See `docs/test/test344.md`; record exact results before marking the PR ready.

## Evidence files produced

- `docs/test/test344.md`

## Boundaries

This PR corrects Terraform resource addresses for immutable public template
objects. It must keep the existing template URL available. It does not change
customer roles or publish a template unless the post-merge exact-plan review
shows a safe object addition with the old key retained.

## Follow-up work

After merge, re-run the protected account-guarded template-host plan. If safe,
apply through the repository Terraform PID monitor, verify old and new object
metadata, update the control-plane template URL, and deploy via the protected
serverless-control-plane plan/apply workflow. Record these runtime changes in
a separate evidence PR.
