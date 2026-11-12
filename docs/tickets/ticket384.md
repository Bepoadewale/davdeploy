# ticket384 — identify missing protected plan feature gates safely

PR: [#384](https://github.com/Bepoadewale/davdeploy/pull/384) (draft)
Branch: `fix/identify-missing-plan-runtime-gates-384`

## Problem / goal

Protected Terraform plan run `43273176464` failed closed with reason
`runtime_gates_missing`. The value-free summary did not identify which
expected runtime feature gate was absent from all planned Lambda environments.
Report only missing gate names from the fixed `FLAG_NAMES` allowlist to make
the next diagnosis actionable without exposing Terraform plan values.

## Current repo state

- Backend `main`: `449cf52ed1a04ee9e35b772fe33f44e839c81b9a` (PR #383 merge).
- Implementation head `abb68c6395b331b85ae73803e62e83bdf5ff8af4` passed all
  seven required checks in run `43274565256`.
- Ticket-evidence head `175c8497429257ef551e72ae49c6c6c74ef349d2` passed all
  seven required checks in run `43278449197`.
- Plan run `43273176464` is terminal failure at the summary step. No saved plan
  was uploaded; no AWS apply was dispatched.
- Plan-only/state/review environment variables are enabled for a future
  protected plan. The running Lambda gates remain unchanged until an exact
  saved plan is reviewed and applied.
- Protected untracked `--only-show-errors` remains untouched.

## Research / references used

- `scripts/summarize_terraform_plan.py`
- `tests/test_terraform_plan_summary.py`
- Failed protected plan run `43273176464`; safe reason code was
  `runtime_gates_missing` and raw plan output remained suppressed.
- Terraform Lambda environment configuration in
  `infrastructure/terraform/serverless-control-plane/main.tf`

## Work planned for the PR

- Carry missing expected gate names as a typed, fixed-list diagnostic detail.
- Validate diagnostic names against the constant `FLAG_NAMES` set before
  printing them.
- Add tests proving a known missing flag is named and arbitrary gate names,
  values, and other plan data are not printed.

## Acceptance criteria

- [x] Missing gate diagnostics list only expected names from `FLAG_NAMES`.
- [x] No raw Terraform JSON, values, or untrusted names are logged.
- [x] Focused sanitizer suite (15 tests) and full verification pass (1,053 tests).
- [x] Implementation diff reviewed; implementation-head required CI passed
  (run `43274565256`, all seven checks).
- [x] Ticket-evidence head passed all seven required CI checks in run
  `43278449197`.
- [ ] Re-run the protected plan after merge; apply only after reviewing the
  exact saved plan and keeping customer apply/certification gates closed.

## Acceptance status

- [x] Implementation and local verification are complete.
- [x] Implementation-head CI and manual diff review are complete.
- [x] Required CI passed on implementation and ticket-evidence heads; GitHub
  remains authoritative for the current PR head's merge checks.

## Tests / validation performed

Run `43273176464` failed at the summary step before uploading a saved plan. No
infrastructure was applied or changed. `.venv/bin/pytest
tests/test_terraform_plan_summary.py -q` passed (15 tests); `make verify` passed
(1,053 tests; Ruff, OpenAPI snapshot, and Docker Compose checks passed; one
existing Starlette/httpx deprecation warning). Documentation conventions and
`git diff --check` passed locally. Implementation head CI run
`43274565256` and ticket-evidence head CI run `43278449197` each passed all
seven required checks.

## Evidence files produced

- `docs/tickets/ticket384.md`
- `scripts/summarize_terraform_plan.py`
- `tests/test_terraform_plan_summary.py`

## Boundaries

This change only improves value-free diagnosis of protected control-plane
plans. It does not enable customer apply, approve customer plans, alter pricing,
or grant customer-role permissions. The private Nova strategy and status ledger
remain outside this repository.

## Follow-up work

Use the missing gate names to fix the plan-summary mismatch. Then obtain a fresh
protected plan, review every planned action, and preserve the approval block
while complete regional pricing evidence is unavailable.
