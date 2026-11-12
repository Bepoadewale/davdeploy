# ticket385 — read runtime feature gates from Terraform plan changes

PR: pending
Branch: `fix/read-runtime-gates-from-plan-changes-385`

## Problem / goal

Protected control-plane plan `43281070996` failed closed because the value-free
plan summary found all expected Lambda feature gates missing from
`planned_values`. Terraform JSON also carries planned after-values in
`resource_changes`; inspect only the fixed gate allowlist there when required.

## Current repo state

- Backend `main`: `9c0bdf7c6fc46d00fd192746ac9a5ae76bfd87a3` (PR #384 merge).
- Run `43281070996` failed before a saved plan was published. The workflow
  uploaded its immutable Lambda package to the release bucket first; no
  Terraform apply or control-plane infrastructure mutation occurred.
- Customer cloud execution and hosted certification remain disabled in the
  protected plan environment; exact feature values must be reviewed before
  any apply.
- Protected untracked `--only-show-errors` remains untouched.

## Research / references used

- `scripts/summarize_terraform_plan.py`
- `tests/test_terraform_plan_summary.py`
- HashiCorp Terraform JSON plan format:
  https://developer.hashicorp.com/terraform/internals/json-format
- Protected plan run `43281070996`, value-free failure detail.

## Work planned

- Read runtime flag values from `resource_changes[].change.after` only for
  `aws_lambda_function` resources and names in `FLAG_NAMES`.
- Preserve fail-closed behavior for missing, malformed, or conflicting values.
- Add regression tests that prove raw plan values remain suppressed.

## Acceptance criteria

- [ ] Terraform plan summaries handle omitted `planned_values` gates using
  typed `change.after` values.
- [ ] Missing, malformed, or conflicting gate values fail closed.
- [ ] Focused tests, full verification, docs conventions, and required CI pass.
- [ ] Fresh protected plan yields a safe exact-action summary; no apply unless
  the saved plan is inspected and remains within authorized gates.

## Validation performed

- Not started.

## Evidence files

- `docs/tickets/ticket385.md`

## Boundaries and follow-up

Do not log or persist raw `terraform show -json` output. This change does not
enable customer apply, hosted certification, or regional pricing approval.
