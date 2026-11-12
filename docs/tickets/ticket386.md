# ticket386 — diagnose missing runtime gate values safely

PR: [#386](https://github.com/Bepoadewale/davdeploy/pull/386) (draft)
Branch: `fix/diagnose-missing-runtime-gate-values-386`

## Problem / goal

Protected plan `43285350771` still failed closed after #385 because all nine
allowlisted runtime gates were absent from both `planned_values` and
`resource_changes[].change.after`. Add a bounded diagnostic reporting only
Lambda counts, environment/map presence counts, and fixed gate presence by
source. It must never expose plan values or arbitrary names.

## Current repo state

- Backend `main`: `96cb7b51c841f795d5a2d1ce9f3cfd4b55d12dcb` (PR #385 merge).
- Run `43285350771` failed before saved-plan publication. The summary reported
  all nine fixed gates missing from both `planned_values` and change after
  values. No control-plane infrastructure apply occurred; the workflow
  published its immutable Lambda package before planning.
- Initial CI run `43287781330` exposed the supply-chain job's dependency on the
  runner image's preinstalled `python3.12`; the image no longer provided that
  command. This PR pins Python 3.12 through the existing setup-python action
  before building the package.
- Corrected implementation head `ae9f2f507f5d5071e21d159bc1330196b0df65b8`
  passed all seven required checks in run `43288891088`.
- Customer cloud execution and hosted certification remain disabled.
- Implementation commit `a9338a1` passed all seven required checks in run
  `43286995660`.
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
- Pin Python 3.12 in the supply-chain job before building the Lambda package.

## Acceptance criteria

- [x] Diagnostic counts are bounded integers and report only allowlisted
  environment/gate names.
- [x] Raw plan values and arbitrary variable names remain suppressed.
- [x] Focused tests (18) and full verification (1,056 tests) pass.
- [x] Supply-chain CI explicitly provisions the Python version required by the
  Lambda package build script.
- [x] Documentation conventions, diff checks, and all seven required CI checks
  pass on corrected implementation head `ae9f2f5` (run `43288891088`).
- [ ] A fresh protected plan explains its structural omission without exposing
  raw JSON; no apply is dispatched.

## Acceptance status

- [x] Bounded shape diagnostics are implemented and locally verified.
- [x] Local verification, documentation checks, and corrected implementation
  CI are complete. GitHub remains authoritative for current-head merge checks.

## Tests / validation performed

- `.venv/bin/pytest tests/test_terraform_plan_summary.py -q`: 18 passed.
- `make verify`: 1,056 passed; Ruff, Actions configuration, OpenAPI, and Docker
  Compose checks passed. One existing Starlette/httpx deprecation warning.
- Initial CI run `43287781330` failed only in the supply-chain package build
  because `python3.12` was unavailable on the runner; explicit setup is added.
- `GITHUB_PR_NUMBER=386 .venv/bin/python scripts/check_doc_conventions.py` and
  `git diff --check` passed.
- Implementation commit `a9338a1` passed all seven CI checks in run
  `43286995660`.
- Corrected head `ae9f2f5` passed all seven checks in run `43288891088`.

## Evidence files produced

- `docs/tickets/ticket386.md`

## Boundaries

This diagnostic does not enable customer plan/apply, hosted certification,
regional pricing approval, or infrastructure mutation.

## Follow-up work

Use only the safe structural facts to fix the source mismatch; require another
protected plan to prove the repaired summary before any apply review.
