# ticket563 — make typed reference repair feedback actionable

PR: [#563](https://github.com/Bepoadewale/davdeploy/pull/563) (draft)

Branch: `fix/nova-reference-type-feedback-563`

## Problem / goal

The fresh hosted v24 plan-only generation failed before CodeBuild with the
allowlisted `reference_type_mismatch` issue. The current repair guidance says
to match a typed reference to its declared output but provides no paired schema
example or explicit self-check. Improve the model-facing contract guidance and
bounded repair feedback without relaxing graph validation or exposing raw
proposal values.

## Current repo state

- Backend `main`: `bb4c5dd751c1d4a40cafc889163a5ee30272a4c7` (PR #562 merged).
- PR #562's protected release plan/apply and post-deployment checks passed.
- Fresh hosted v24 run `32b172f4-4ef7-4bbe-a5dc-f163df217b40` failed before
  CodeBuild with `reference_type_mismatch`; no artifact or customer workload
  was created. The review-only revision remains unapproved.

## Research / references used

- `apps/api/src/davdeploy/generated_deployment_contract.py` enforces exact
  output-name and value-type equality for every typed reference.
- `apps/api/src/davdeploy/terraform_generation.py` supplies versioned Nova
  generation instructions and fixed, sanitized repair feedback.
- `docs/test/test562.md` records the prior hosted baseline and release evidence.

## Work planned for the PR

1. Explain the paired declared-output/reference contract with a schema-shaped,
   non-sensitive example and a self-check for each edge.
2. Make `reference_type_mismatch` feedback explicitly distinguish matching the
   exact declared output name and type from inventing or changing architecture.
3. Keep strict validators unchanged; do not normalize semantic type mismatches.
4. Add tests proving feedback reaches the bounded repair attempt and arbitrary
   IDs, output names, values, and unknown text stay redacted.
5. Update prompt version, test evidence, and private local goal ledger.

## Acceptance criteria

- [x] Guidance clearly explains declared output/reference pair equality.
- [x] Graph validation remains strict and unchanged; no validator code changed.
- [x] Feedback remains fixed/sanitized and the repair test confirms the bounded second attempt.
- [ ] Focused generation/review/run suite passes (148 tests); full verification passes (2,096 tests). Isolated clean-room proof remains pending.
- [ ] Current-head CI/review checks pass and PR is merged.
- [ ] Fresh hosted review-only run reaches a plan or a more precise blocker;
      no customer workload is approved or applied.

## Acceptance status

In progress. The prompt and fixed repair guidance are implemented; 148 focused
tests pass. Focused/full verification and isolated `local-proof` pass. Its dedicated worktree,
venv, and volume remain retained under the no-delete rule; project containers are
stopped. CI/review, protected release, and a fresh hosted v25 result remain pending.

## Tests / validation performed

- Focused generation/review/run suite: 148 passed.
- `make VENV=/Users/adewale/Projects/davdeploy/.venv-pr399 verify`: 2,096 passed; Ruff, Actions configuration, OpenAPI snapshot, and Compose config passed.
- Documentation convention and `git diff --check` passed.
- `COMPOSE_PROJECT_NAME=davdeploy-nova-ref563-proof` isolated `make VENV=/private/tmp/davdeploy-nova-reference-cleanroom-563-venv local-proof`: all smoke, API contract, customer-plan E2E, seed/trace, 2,096 tests, Ruff, Actions, OpenAPI, and Compose checks passed.
- Project containers were stopped after proof. The clean-room worktree, venv, and database volume are retained; no local files or volumes were deleted.

## Evidence files produced

- `docs/tickets/ticket563.md`
- `docs/test/test563.md` (to be added)

## Follow-up work

Use the next hosted outcome to advance the actual planning gate. A generated
proposal alone is not acceptance: require supported composed resources, real
pricing, saved-plan policy, and later hosted lifecycle evidence.

## Boundaries

Do not expose raw proposal, resource IDs, output names, secrets, plans, or state
in public diagnostics. Do not weaken authorization, validation, policy, or
customer workload approval requirements. Do not claim a Nova workload was
applied or certified.
