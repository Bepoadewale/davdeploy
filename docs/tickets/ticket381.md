# ticket381 — retain the currently published CloudFormation template

PR: [#381](https://github.com/Bepoadewale/davdeploy/pull/381) (merged)
Branch: `fix/retain-current-customer-template-381`

## Problem / goal

The reviewed `connection-template-host` Terraform plan for merged PR #379
showed one add and one destroy. The replacement targets the current immutable
CloudFormation Quick Create template URL, which customers may still use. Keep
that exact object and URL available while publishing the new content-hash
template.

## Current repo state

- Backend `main` is `fab68c8bea3166da257b71484f67c980c94ccb51` after PR #380.
- Protected untracked `--only-show-errors` remains untouched.
- Read-only AWS identity is account `654654474502`; no AWS role or other
  customer-account object was changed.
- A plan of `infrastructure/terraform/connection-template-host` on 2026-11-12
  showed `1 to add, 0 to change, 1 to destroy`: old key
  `cloudformation/customer-discovery-role-f3d9e1e5776fe147bbbc10107e41d221497f9b98c6b641eb8ac08467fd54aedb.yaml`
  replaced by `cloudformation/customer-discovery-role-8c5d1c82682b3bb90ff1f45d121b475e7b33b484f556feabafbf387c335aea4e.yaml`.
- No template-host apply was run. The old public object remains untouched.
- A separate protected serverless-control-plane plan `43254329556` was
  dispatched for exact current `main` and completed with 0 adds, 6 Lambda in-place
  updates, 0 destroys, and Nova runner/broker/plan-review/state-API flags
  still false. It wrote versioned release-package and saved-plan artifacts to
  dedicated S3 buckets but applied no infrastructure. It does not publish the
  template-host root and will not be applied with its old template URL.

## Research / references used

- HashiCorp Terraform `moved` block reference:
  https://developer.hashicorp.com/terraform/language/block/moved
- HashiCorp AWS provider `aws_s3_object` reference:
  https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_object
- Initial and corrected read-only plans for the exact
  `connection-template-host` state are recorded in `docs/test/test381.md`.

## Work planned for the PR

- Add the current `f3d9…` object key to the immutable retained-template set.
- Move Terraform's current published-object address into the retained map
  before Terraform creates the next content-hash object.
- Add regression assertions for the exact source/destination state move and
  retention behavior.
- Re-run the template-host plan and verify it creates the new object without
  deleting or replacing the old object.

## Acceptance criteria

- [x] The current `f3d9…` URL remains represented by a retained object with
      `prevent_destroy` and `ignore_changes = all`.
- [x] Terraform moves the existing published-object state to the retained
      address and plans a separate new current object.
- [x] The refreshed read-only plan has no destroy, replacement, or mutation of prior
      published template keys.
- [x] Focused tests, full verification, Terraform validation, and diff checks
      pass. Documentation conventions, final review, clean-room CI proof, and
      required GitHub checks remain pending.
- [x] No template-host apply or customer role installation occurred.

## Acceptance status

- [x] A safe source correction is implemented and its refreshed plan contains
      no destruction.
- [ ] Required clean-room CI, final-head review, and CI checks pass.
- [x] No template-host apply or customer role installation is claimed.

## Tests / validation performed

Commands and results are recorded in `docs/test/test381.md`. The original
pre-fix plan is read-only evidence and is documented above; it will not be
applied.

## Evidence files produced

- `docs/tickets/ticket381.md`
- `docs/test/test381.md`

## Boundaries

This change preserves immutable public template URLs. It does not install a
role in any customer account, attest effective customer permissions, enable
hosted planning, or apply customer infrastructure. After this PR, review and
apply the separate template-host plan; then update the environment-scoped
`AWS_CONNECTION_TEMPLATE_URL` only to the verified new URL and release the
backend code through the protected serverless plan/apply flow. Nova planning,
approval, apply, health, recovery, and teardown remain gated independently.

## Follow-up work

- Completed after merge: the template-host root published the new immutable
  object with 1 add and 0 changes/destroys; the existing `f3d9…` URL was
  retained. The hosted `AWS_CONNECTION_TEMPLATE_URL` was updated to the
  verified `8c5d…` URL.
- Completed after merge: fresh protected plan `43260003885` and exact saved-plan
  apply `43261766144` deployed PR #381 source. See `docs/test/test382.md` for
  exact publication, release, and post-deployment evidence.
- Customer role installation/effective permission verification and hosted
  Nova customer execution remain incomplete.

## Post-merge deployment reconciliation — 2026-11-12

The acceptance items above describe the state before merge and remain
historical. PR #381 merged as `a12205972cc124d08d85845f30c9b574f7cf87fd` after
the final-head checks passed. The template-host apply and subsequent protected
control-plane plan/apply completed successfully; full evidence is in
[`test382.md`](../test/test382.md). No customer role or workload was created.
