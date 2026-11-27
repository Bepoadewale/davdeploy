# test558 — safe diagnostics for incompatible Nova health targets

Date: 2026-11-27

Execution type: Local code validation pending; baseline hosted plan-only diagnostic only

Customer repository: Synthetic DavDeploy acceptance scenario; no customer repository was accessed

Commit: `63a94632d07e125d83c54f236a349b93d94254f9` (baseline)

AWS account: `654654474502` (control-plane release only)

AWS region: `us-east-1`

## Baseline hosted diagnostic

Run `572b2750-4070-4d8d-b903-15929297b929` used prompt v19 and ended
`NOVA_GENERATION_FAILED` / `proposal_invalid`, with two attempts and one repair.
The safe issue was `incompatible_health_target` at
`health_assertions[*].target_resource_id`. No Terraform artifact or customer
workload resources were created. The review revision remains unapproved and
unexecuted.

## Resources created

No customer workload AWS resources were created or changed by this hosted
diagnostic. PR #557's protected control-plane release is separate from customer
execution.

## Commands executed

Authenticated CLI requests created and submitted a fresh review-only revision,
then queued exactly one plan-only run. Output was filtered to the run ID, safe
status, prompt version, token counts, and allowlisted issue code/field. Raw
proposal, plan, state, and credential values were not retrieved.

## Observed result

The existing feedback identifies the incompatible assertion field but omits
the recognized target resource type. That is insufficient to distinguish a
contract mapping defect from Nova selecting an API, secret, or network resource.
The PR will add a value-free type diagnostic and more direct RDS targeting
guidance.

## Teardown

No customer workload resources were created, so no teardown was needed.

## Final boundary

This baseline failure does not prove SQL connectivity or write/read behavior,
an inspectable saved plan, pricing, policy acceptance, approval, apply,
observation, lifecycle recovery, destroy, or absence.

## Local implementation verification

- Focused contract/generation/run/review tests: 196 passed.
- `make VENV=/Users/adewale/Projects/davdeploy/.venv-pr399 verify`: 2,084
  tests passed; lint, OpenAPI snapshot check, and Compose config passed.
- `ruff check` on the changed source and tests passed.
- `git diff --check` passed.
- CI documentation conventions and Actions configuration boundary scripts
  passed for PR #558.
- Clean-room cycle, PR CI/review, deployment, and a fresh hosted plan-only
  attempt remain pending.
