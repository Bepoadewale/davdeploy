# ticket389 — expose value-free Terraform drift details

PR: https://github.com/Bepoadewale/davdeploy/pull/389
Branch: `feat/value-free-terraform-drift-summary-389`

## Problem / goal

The protected control-plane plan summary reports only a drift count. The latest
fresh plan has three drifted resources, and the count alone is insufficient to
review reconciliation safely. Emit only bounded resource address, resource
type, action, and changed field names. Never emit before/after values,
sensitive values, or output values.

## Current repo state

- Backend `main`: `04750dc4f6b7eaf2e4aee64c039ebd98c8398063` (PR #388).
- Fresh protected plan `43380768283` is successful and tied to that exact main
  commit. Its value-free summary shows 3 adds, 8 changes, 0 destroys, 0
  replacements, 3 drifted resources, and 8 changed outputs. Do not apply until
  drift details are reviewed.
- No customer workload or infrastructure apply occurred for this plan.
- Protected untracked `--only-show-errors` remains untouched.

## Research / references used

- `scripts/summarize_terraform_plan.py`
- `tests/test_terraform_plan_summary.py`
- Terraform JSON plan resource drift uses a `change` object with before/after
  values; values must remain out of the emitted summary.

## Work planned

- Add strict, bounded drift inventory output using only sanitized address,
  type, actions and changed field names.
- Reject malformed drift/action metadata without echoing input values.
- Test that resource and output values are never present in the summary.

## Acceptance criteria

- [ ] Drift summary emits safe bounded field-name details for valid drift.
- [ ] Malformed data fails closed with a fixed reason and no value leakage.
- [ ] Focused tests, full verification, and required CI pass.
- [ ] A fresh plan summary can be reviewed before deciding on apply.

## Acceptance status

- [ ] Implementation and validation pending.

## Tests / validation performed

- None yet.

## Evidence files produced

- `docs/tickets/ticket389.md`

## Boundaries

This diagnostic change does not alter infrastructure policy, execution,
credentials, state, or Terraform mutation behavior. The saved plan for
`43380768283` is not to be applied until its drift is understood.

## Follow-up work

After merge, create a fresh protected plan against current `main`, inspect the
action and drift summaries, then proceed with the exact saved plan only if the
reviewed actions and reconciliation are acceptable.
