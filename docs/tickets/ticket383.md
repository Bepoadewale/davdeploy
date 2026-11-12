# ticket383 — report safe Terraform plan summary failure reasons

PR: [#383](https://github.com/Bepoadewale/davdeploy/pull/383) (draft)
Branch: `fix/terraform-plan-summary-failure-codes-383`

## Problem / goal

The protected control-plane Terraform plan run `43268823644` failed after
Terraform planning, when the value-free summarizer rejected the JSON. The
workflow correctly suppressed the raw plan but emitted only a generic failure,
so the cause could not be fixed without a safe diagnostic. Emit fixed
allowlisted reason codes that never include plan values or raw parser errors.

## Current repo state

- Backend `main`: `4b5a84616ea43ad1a127f8ec2a98b72e7d724eec` (PR #382 merge).
- Run `43268823644` is terminal failure at the plan summary step. No saved plan
  was uploaded and no AWS apply was dispatched.
- Nova infrastructure feature variables are enabled in the protected planning
  environment, but the running control-plane Lambda configuration is unchanged
  until an exact saved plan is reviewed and applied.
- Protected untracked `--only-show-errors` remains untouched.

## Research / references used

- `scripts/summarize_terraform_plan.py`
- `tests/test_terraform_plan_summary.py`
- Failed protected plan run `43268823644` (raw plan output was suppressed)
- AWS CodeBuild plan-only boundary tests and infrastructure source

## Work planned for the PR

- Map known summary validation failures to fixed non-sensitive reason codes.
- Add regression tests for plan invalidity, malformed/oversized JSON, and
  runtime-gate mismatches while checking that input values never appear.
- Preserve fail-closed behavior and the existing value-free plan summary.

## Acceptance criteria

- [x] Every current `PlanSummaryError`, JSON parse failure, invalid encoding,
  and excessive nesting maps to a fixed allowlisted reason token.
- [x] No raw JSON, plan values, provider messages, or untrusted input is emitted.
- [x] The control-plane plan sanitizer regression suite passes (14 tests).
- [x] Documentation conventions, diff checks, and full verification pass.
- [ ] Final-head review and required CI pass.
- [ ] The protected plan is re-run only after this diagnostic change is merged;
  any resulting plan must be reviewed before apply.

## Acceptance status

- [x] Implementation and local verification are complete.
- [ ] Final-head CI and review remain pending.

## Tests / validation performed

`GITHUB_PR_NUMBER=383 .venv/bin/python scripts/check_doc_conventions.py` and
`git diff --check` passed. `.venv/bin/pytest tests/test_terraform_plan_summary.py
-q` passed (14 tests). `make verify` passed (1,052 tests; Ruff, OpenAPI
snapshot, and Docker Compose checks passed; one existing Starlette/httpx
deprecation warning). The failed plan run ended before a saved plan was
published; no AWS resources were applied or changed.

## Evidence files produced

- `docs/tickets/ticket383.md`
- `tests/test_terraform_plan_summary.py`
- `scripts/summarize_terraform_plan.py`

## Boundaries

This change only improves safe diagnostics for the protected control-plane
Terraform plan. It does not enable customer apply, approve generated plans, or
alter pricing, tenant authorization, or customer-role permissions. The private
Nova strategy and status ledger remain outside the repository.

## Follow-up work

After merge, create and review a fresh protected plan using the enabled but
not-yet-applied plan-only feature variables. Keep final saved-plan approval
blocked while complete regional pricing is unavailable.
