# ticket558 — diagnose Nova health-target repair failures

PR: [#558](https://github.com/Bepoadewale/davdeploy/pull/558) (draft)

Branch: `fix/nova-rds-health-feedback-558`

## Problem / goal

The v19 hosted plan-only generation retried an incompatible database health
target, then failed without a Terraform artifact. Improve the bounded repair
feedback with only a validated assertion kind and recognized AWS resource type,
and make the RDS target instruction direct enough for a relational workload.

## Current repo state

- Main: `63a94632d07e125d83c54f236a349b93d94254f9` (PR #557 merged).
- PR #557 is deployed through protected plan `46052921538` and apply
  `46053869885`; migration succeeded, all six control-plane Lambdas match the
  exact versioned package, and `/healthz` returned HTTP 200.
- Hosted plan-only run `572b2750-4070-4d8d-b903-15929297b929` used prompt v19,
  made two attempts (one repair), and failed as `NOVA_GENERATION_FAILED` /
  `proposal_invalid` with safe issue `incompatible_health_target` at
  `health_assertions[*].target_resource_id`. No artifact or customer resources
  were created. The revision remains unapproved and unexecuted.

## Research / references used

- `generated_deployment_contract.py` owns typed health-target compatibility.
- `terraform_generation.py` owns bounded prompt repair and safe feedback.
- The hosted artifact and run endpoints expose value-free review evidence; raw
  proposals, plans, state, and secret values remain out of diagnostics.

## Work planned for the PR

1. Preserve the contract validator's deterministic rejection while carrying a
   bounded assertion kind and AWS resource type into the sanitizer.
2. Emit only the canonical target field, recognized resource type, fixed issue
   code, and fixed guidance; never include resource IDs or proposal text.
3. Direct Nova to target the declared RDS resource itself for relational
   `database_roundtrip` checks, rather than an API, secret, or network resource.
4. Bump the prompt version and add regression tests for bounded repair and
   diagnostic redaction.

## Acceptance criteria

- [x] Compatible RDS instance/cluster targets remain accepted; incompatible
  pairs still fail before a runner can receive the proposal.
- [x] Repair feedback includes the recognized AWS resource type and canonical
  target field, but no resource ID, rationale, raw cause, secret, or proposal.
- [x] Bounded repair can correct a database assertion from an API target to an
  RDS target using the direct instruction.
- [x] Focused tests, full verification, and docs conventions pass.
- [ ] Clean-room cycle, review, all required PR CI, and deployed hosted
  plan-only evidence pass.
- [ ] After protected deployment, a fresh review-only hosted run reaches an
  inspectable saved plan or a new precise blocker; no customer approval/apply.

## Acceptance status

Implementation, focused/full local verification, and docs conventions
complete. Clean-room proof, review, CI, and deployed hosted plan-only evidence
remain pending.

## Tests / validation performed

Focused test command:

```text
PYTHONPATH=apps/api/src python -m pytest -q tests/test_generated_deployment_contract.py tests/test_terraform_generation.py tests/test_nova_plan_runs.py tests/test_customer_plan_review.py
```

Result: 196 passed. `make VENV=/Users/adewale/Projects/davdeploy/.venv-pr399
verify` passed with 2,084 tests, lint, OpenAPI snapshot, and Compose config.
Ruff, `git diff --check`, and both CI documentation/configuration scripts
passed. Clean-room proof, review, CI, and deployed hosted plan-only evidence
remain pending. Prior deployment evidence is in
`docs/test/test557.md`; the hosted v19 diagnostic is recorded there.

## Evidence files produced

- `docs/tickets/ticket558.md`
- `docs/test/test558.md`

## Boundaries

Do not expose raw proposal/plan/state data or credentials. No customer approval,
apply, or destroy. Preserve the protected untracked backend files and retained
audit evidence.

## Follow-up work

Deploy only through an inspected protected saved plan. Create a fresh review-only
revision, queue one plan-only run, and inspect only safe diagnostics and the
value-free artifact summary.
