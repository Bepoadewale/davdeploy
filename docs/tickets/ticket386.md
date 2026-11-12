# ticket386 — diagnose missing runtime gate values safely

PR: pending
Branch: `fix/diagnose-missing-runtime-gate-values-386`

## Problem / goal

Protected plan `43285350771` still failed closed after #385 because all nine
allowlisted runtime gates were absent from both `planned_values` and
`resource_changes[].change.after`. Add a bounded diagnostic reporting only
Lambda counts, environment/map presence counts, and fixed gate presence by
source. It must never expose plan values or arbitrary names.

## Current repo state

- Backend `main`: PR #385 merge pending.
- Run `43285350771` failed before saved-plan publication. No control-plane
  infrastructure apply occurred; the workflow published its immutable Lambda
  package before planning.
- Customer cloud execution and hosted certification remain disabled.
- Protected untracked `--only-show-errors` remains untouched.

## Research / references used

- `scripts/summarize_terraform_plan.py`
- `tests/test_terraform_plan_summary.py`
- HashiCorp Terraform JSON plan format:
  https://developer.hashicorp.com/terraform/internals/json-format
- Value-free failure output from protected run `43285350771`.

## Work planned for the PR

- Add bounded, value-free source-shape details only for `aws_lambda_function`
  runtime gate scanning.
- Keep the summary fail-closed when any required gate is unavailable or
  malformed.
- Test counts and presence fields with private values and untrusted variable
  names excluded from output.

## Acceptance criteria

- [ ] Diagnostic counts are bounded integers and report only allowlisted
  environment/gate names.
- [ ] Raw plan values and arbitrary variable names remain suppressed.
- [ ] Focused tests, full verification, docs checks, and required CI pass.
- [ ] A fresh protected plan explains its structural omission without exposing
  raw JSON; no apply is dispatched.

## Acceptance status

- [ ] Implementation and local verification pending.

## Tests / validation performed

- None yet.

## Evidence files produced

- `docs/tickets/ticket386.md`

## Boundaries

This diagnostic does not enable customer plan/apply, hosted certification,
regional pricing approval, or infrastructure mutation.

## Follow-up work

Use only the safe structural facts to fix the source mismatch; require another
protected plan to prove the repaired summary before any apply review.
