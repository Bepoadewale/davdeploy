# ticket419 — safe IAM plan-summary failure context

PR: #419 https://github.com/Bepoadewale/davdeploy/pull/419
Branch: `fix/plan-summary-policy-error-context-419`

## Problem / goal

Protected plan runs `43972802456` and `43975879186` failed closed with the
same generic `invalid_policy_summary` reason and suppressed raw plan data.
The second failure persisted after accepting the known
`${codebuild:buildArn}` token. Add bounded, validated context to the safe
failure message so the next plan identifies only which IAM resource address,
before/after side, and policy field failed parsing. Never include policy
values or arbitrary exception text.

## Current repo state

- Backend `main` includes PR #418 at `d505b825ac7df877760a01b3aadb6d827e706f7c`.
- Protected plan runs `43972802456` and `43975879186` both initialized and
  validated Terraform, then failed closed with `invalid_policy_summary`.
- Neither run published a saved plan. No apply ran.
- The parser supports bounded `${...}` placeholders, but the production plan
  still encounters another IAM policy shape that has not yet been identified.

## Research / references used

- `scripts/summarize_terraform_plan.py` — value-free plan summary and
  fail-closed diagnostics.
- `tests/test_terraform_plan_summary.py` — current redaction and malformed
  policy regression tests.
- Protected plan runs `43972802456` and `43975879186` — raw plan diagnostics
  were suppressed; safe reason was `invalid_policy_summary`.

## Work planned for the PR

1. Carry only validated resource address, side (`before` or `after`), and
   policy field (`policy`, `assume_role_policy`, or `inline_policy`) through
   the policy-summary error path.
2. Print those fixed-shape fields only for `invalid_policy_summary`; never
   echo raw values or arbitrary exception strings.
3. Add a regression test proving useful context appears and policy sentinels
   remain absent.
4. Run focused tests, full verification, and required CI.
5. Use a fresh protected plan after merge to identify and fix the actual
   production policy shape, then inspect its sanitized summary. Do not apply.

## Acceptance criteria

- [x] Failure reports a validated IAM address, before/after side, and
      allowlisted policy field.
- [x] Malformed policy sentinels and arbitrary exception text never appear.
- [x] Focused tests, full verification, docs conventions, diff checks, and
      implementation-head GitHub CI pass.
- [x] No apply, deployment, runtime gate change, AWS resource mutation, or
      customer workload execution is part of this PR.

## Acceptance status

The failure path now reports only validated resource address, side, and policy
field metadata. Regression coverage verifies malformed policy input appears
only as the fixed reason and safe context, never as raw text. Focused/full
verification and documentation checks pass, and all seven CI jobs passed for
implementation commit `59b3c5c`. Both failed plans published no saved plan
and dispatched no apply.

## Tests / validation performed

- `tests/test_terraform_plan_summary.py` — 30 passed.
- `make verify VENV=/Users/adewale/Projects/davdeploy/.venv-pr399` — 1,260
  passed; Ruff, Actions configuration, OpenAPI snapshot, and Compose checks
  passed (one existing Starlette/httpx deprecation warning).
- Documentation conventions, focused Ruff, and diff checks — passed.

## Evidence files produced

- No `docs/test/` customer-workload evidence is required: this PR changes only
  safe plan-summary diagnostics, with no customer workload execution.

## Boundaries

This PR changes only error context for failed Terraform plan summaries. It
does not run Terraform apply, change production resources, enable Nova apply,
or publish customer workload evidence.

## Follow-up work

After merge, generate a fresh protected plan for current `main`. Use the safe
resource/side/field context to fix the remaining parser mismatch, then inspect
the complete sanitized plan summary before considering any apply separately.
