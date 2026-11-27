# ticket541 — Clarify Nova resource IDs and health assertion feedback

PR: #541
Branch: `fix/nova-resource-id-pattern-541`

## Problem / goal

After prompt v5 deployment, hosted plan-only run
`0b1e4807-7532-45df-ad99-8edde41a82f4` progressed past Terraform resource-name
validation but still failed. Safe diagnostics contained six
`resources[*].resource_id` and five `health_assertions[*]` pattern errors.
The resource ID prompt said only that lowercase letters, digits and hyphens
were allowed; it omitted the initial-letter rule and length limit. The
health-assertion error path also stopped at the union item because its
whitelisted discriminator tag was omitted from canonicalization.

## Current repo state

- The strict contract requires resource IDs and health target/source IDs to
  match `^[a-z][a-z0-9-]{0,62}$`.
- Health assertions are a closed tagged union. Their IDs must reference declared
  resources; event-processing assertions also reference a declared source.
- Safe diagnostics allowlist known fields but currently truncates nested paths
  at the union variant discriminator.

## Research / references used

- `apps/api/src/davdeploy/generated_deployment_contract.py` resource ID,
  health assertion variants, and graph validation.
- `apps/api/src/davdeploy/terraform_generation.py` trusted task and canonical
  feedback sanitizer.
- Hosted safe diagnostics for run
  `0b1e4807-7532-45df-ad99-8edde41a82f4` after prompt-v5 deployment.
- `tests/test_terraform_generation.py`, `tests/test_nova_plan_runs.py`, and
  `tests/test_customer_plan_review.py`.

## Work planned for the PR

- State the exact resource ID pattern, valid examples, and exact reference
  relationship for resource IDs and health assertions in the trusted prompt.
- Version the prompt as `terraform-nova2-contract-v6` consistently in requests,
  usage records, and run diagnostics.
- Canonicalize health assertion feedback through only the fixed known
  discriminator tags so the returned path includes the allowlisted field.
- Leave all schema, validation, policy, and execution limits unchanged.

## Acceptance criteria

- [x] Prompt v6 states the exact resource-ID regex, examples, and health
  assertion reference rules.
- [x] Safe diagnostics retain `health_assertions[*].<field>` paths only for
  fixed known assertion kinds and schema fields.
- [ ] Generation, feedback, plan-run, and customer-review tests pass; Ruff and
  documentation checks pass.
- [x] Required hosted CI run `45939566852` passed all seven checks.
- [ ] After protected deployment, the same submitted plan-only revision yields
  an inspectable saved plan or a new actionable safe diagnostic.

## Acceptance status

- [x] Prompt v6 and improved canonical feedback are implemented and locally tested.
- [x] Required hosted CI run `45939566852` passed all seven checks.
- [ ] Post-deployment hosted retry is complete.

## Tests / validation performed

- `uv run --project . --extra dev pytest -q tests/test_terraform_generation.py tests/test_nova_plan_runs.py tests/test_customer_plan_review.py` — 98 passed.
- Ruff passed for the five changed Python files.
- `GITHUB_PR_NUMBER=541 uv run --project . python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Hosted CI run `45940609886` — all seven checks passed.
- Hosted CI run `45940069020` — all seven checks passed.
- Hosted CI run `45939566852` — all seven checks passed.

## Evidence files produced

- `docs/test/test541.md`

## Evidence and observed hosted failure

- Protected plan/apply runs `45937343100` / `45937978900` deployed prompt-v5
  commit `c714fcb9686653c8e3ee36a334171b9deb4b92f3`; the exact package matched
  all six active, successfully updated control-plane Lambdas, migration passed,
  and `/healthz` returned HTTP 200.
- The v5 retry failed before CodeBuild with `NOVA_GENERATION_FAILED`, two
  attempts and one repair. Safe diagnostics reported six
  `resources[*].resource_id` and five `health_assertions[*]`
  `string_pattern_mismatch` entries; raw model output was not accessed.
- Usage was 11,444 input tokens, 4,236 output tokens, and 15,154 ms; estimated
  cost was not available. No plan artifact or AWS workload was created.

## Boundaries

- This clarifies trusted prompt constraints and safe error paths only. It does
  not relax the contract or enable approval, apply, or destroy.
- Do not approve or apply a generated workload unless exact-plan ownership,
  policy, live regional pricing, and safety evidence pass.

## Follow-up work

Deploy through the protected control-plane plan/apply workflow and retry the
same submitted synthetic revision once, recording a valid saved plan or the
next bounded safe diagnostic.
