# ticket387 — summarize runtime gates from protected plan inputs

PR: pending
Branch: `fix/summary-runtime-gates-from-inputs-387`

## Problem / goal

Protected plan `43295927625` contains six Lambda resources, six environment
blocks, and only one variable map in both `planned_values` and
`resource_changes`. It contains none of the nine runtime gates. These gates
are Terraform boolean input variables mapped into the Lambda environment by
trusted Terraform configuration. Use the plan's typed input values only when
resource values omit a gate, while checking the source mapping and rejecting
missing, malformed, or conflicting values.

## Current repo state

- Backend `main`: `296272a7256e2b9fd38e21ae0b133b3f60a1bfa9` (PR #386 merge).
- Plan `43295927625` failed closed before saved-plan publication. Safe
  diagnostics showed no gate names in either resource representation. The
  immutable Lambda package was published first; no Terraform apply or
  control-plane infrastructure mutation occurred.
- Customer cloud execution and hosted certification remain disabled.
- Protected untracked `--only-show-errors` remains untouched.

## Research / references used

- `scripts/summarize_terraform_plan.py`
- `infrastructure/terraform/serverless-control-plane/main.tf`
- `tests/test_terraform_plan_summary.py`
- HashiCorp Terraform JSON plan format:
  https://developer.hashicorp.com/terraform/internals/json-format
- Value-free output from protected run `43295927625`.

## Work planned for the PR

- Add a fixed map from runtime gate names to Terraform input variables.
- Fall back to plan input values only when corresponding resource values are
  absent; require literal booleans and reject disagreements.
- Test all source mappings against Terraform and prove raw variable values and
  unrelated input data are never emitted.

## Acceptance criteria

- [ ] Runtime gate values can be summarized from their typed Terraform input
  variables when nested resource values are omitted.
- [ ] Resource values and input variables that disagree fail closed.
- [ ] Missing or malformed gate inputs fail closed; no sensitive or unrelated
  plan values are exposed.
- [ ] Focused tests, full verification, documentation checks, and required CI
  pass.
- [ ] A fresh protected plan produces a safe exact-action summary and saved
  plan; no apply is dispatched by this change.

## Acceptance status

- [ ] Implementation and local verification pending.

## Tests / validation performed

- None yet.

## Evidence files produced

- `docs/tickets/ticket387.md`

## Boundaries

This change does not enable customer apply, hosted certification, regional
pricing approval, or unrestricted execution. Do not emit raw plan JSON.

## Follow-up work

Review the exact saved plan, gate values, resource actions, and policy before
any separately authorized apply; keep customer apply and certification gates
closed.
