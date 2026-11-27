# ticket562 — give Nova safe feedback for malformed resource objects

PR: [#562](https://github.com/Bepoadewale/davdeploy/pull/562) (draft)

Branch: `fix/nova-resource-shape-feedback-562`

## Problem / goal

After PR #561 was merged and deployed, the fresh v23 hosted plan-only run
failed before CodeBuild with ten safe `missing` or `extra_forbidden`
diagnostics collapsed to `resources[*]`. The diagnostics do not reveal which
resource-object fields need repair. Add fixed shape guidance for these root
resource-object errors while preserving schema rejection and not echoing
untrusted field names or proposal data.

## Current repo state

- Backend `main`: `17df898510290134e0ef1770f51506d81474bb64` (PR #561 merged).
- Protected release apply run `46081012438` succeeded after applying saved
  plan `46080412351`. Migration, Lambda hash, API health, and workspace-admin
  checks passed.
- Hosted v23 run `40c14f88-5a49-4df7-9fd0-199e6454b98a` failed with no
  artifact after two attempts and one repair. Final safe feedback contains
  only `missing`/`extra_forbidden` at `resources[*]`.
- Review revision `0005b2f5-71b7-4efd-8b7e-70f2664a4e16` remains submitted
  with no approval decision. No customer workload plan, approval, apply, or
  destroy is claimed.

## Research / references used

- `generated_deployment_contract.py` defines the strict resource fields and
  generated proposal schema.
- `terraform_generation.py` canonicalizes validator paths, strips raw input,
  and allowlists fixed repair guidance for bounded Nova retries.
- `docs/test/test561.md` and private `DAVDEPLOY_NOVA_GOAL_STATUS.md` preserve
  hosted v22/v23 results.

## Work planned for the PR

1. For root `resources[*]` missing-field errors, give fixed guidance naming
   the contract-required `resource_id`, `resource_type`, `name`, `arguments`,
   and `rationale` fields, plus the only optional resource keys.
2. For root `resources[*]` extra-field errors, tell Nova to remove wrapper or
   undeclared keys and place provider resource arguments under `arguments`.
3. Keep the schema validator unchanged and suppress the untrusted extra key,
   input, resource ID, and values in feedback.
4. Add safe path/guidance and bounded-repair tests; bump the prompt version and
   record exact evidence.
5. Pass focused/full and clean-room checks, review/merge via PR, perform the
   exact protected release workflow, then make one fresh v24 review-only run.

## Acceptance criteria

- [x] `missing` and `extra_forbidden` root-resource errors receive distinct
  fixed, actionable guidance.
- [x] Feedback reveals no raw unknown key, input value, resource ID, or
  rationale.
- [x] Strict schema rejection remains unchanged; malformed and executable
  payloads are still rejected before any credentialed runner.
- [x] Focused generation/review/run suite passes: 147 tests.
- [x] Full `make verify` passes 2,095 tests; Ruff, Actions configuration,
  OpenAPI, Compose, docs conventions, and diff checks pass.
- [ ] Required isolated clean-room proof passes.
- [ ] PR review and all required current-head CI checks pass.
- [ ] One fresh v24 run reaches an inspectable plan or a precise next blocker;
  no customer workload approval/apply/destroy occurs.

## Acceptance status

In progress. Fixed guidance and bounded repair are implemented and focused
tests pass. Full verification, clean-room proof, PR CI, protected release, and
the fresh v24 hosted result remain pending.

## Tests / validation performed

- Focused command:
  `PYTHONPATH=apps/api/src /Users/adewale/Projects/davdeploy/.venv-pr399/bin/python -m pytest tests/test_terraform_generation.py tests/test_customer_plan_review.py tests/test_nova_plan_runs.py -q`
  — 147 passed, with one pre-existing Starlette/httpx deprecation warning.
- `make VENV=/Users/adewale/Projects/davdeploy/.venv-pr399 verify` — 2,095
  passed; Ruff, Actions configuration, OpenAPI snapshot, and Compose checks
  passed. Documentation convention and diff checks also passed.
- Isolated clean-room proof will be added before merge.

## Evidence files produced

- `docs/test/test562.md`
- `docs/tickets/ticket562.md`

## Boundaries

Do not relax the generated deployment contract, expose raw proposal/plan/state
data or secrets, change execution roles, or claim customer deployment or
lifecycle evidence.

## Follow-up work

Use the next hosted result to address the earliest remaining contract,
pricing, plan-policy, state, or lifecycle blocker. Keep the workload unapproved
and unapplied.

