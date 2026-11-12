# ticket385 — read runtime feature gates from Terraform plan changes

PR: [#385](https://github.com/Bepoadewale/davdeploy/pull/385) (draft; final ticket evidence added)
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
- Implementation commit `eeae564` passed all seven required CI checks in run
  `43283005098`.
- Protected untracked `--only-show-errors` remains untouched.

## Research / references used

- `scripts/summarize_terraform_plan.py`
- `tests/test_terraform_plan_summary.py`
- HashiCorp Terraform JSON plan format:
  https://developer.hashicorp.com/terraform/internals/json-format
- HashiCorp documents `planned_values` and resource changes as separate plan
  representations. `terraform show -json` can contain sensitive values, so the
  implementation reads only the fixed boolean allowlist and never prints raw
  plan values.
- Protected plan run `43281070996`, value-free failure detail.

## Work planned for the PR

- Read runtime flag values from `resource_changes[].change.after` only for
  `aws_lambda_function` resources and names in `FLAG_NAMES`.
- Preserve fail-closed behavior for missing, malformed, or conflicting values.
- Add regression tests that prove raw plan values remain suppressed.

## Acceptance criteria

- [x] Terraform plan summaries handle omitted `planned_values` gates using
  typed `change.after` values.
- [x] Missing, malformed, or conflicting gate values fail closed.
- [x] Focused tests (17) and full verification (1,055 tests) pass.
- [x] Documentation conventions and diff checks pass; implementation commit
  `eeae564` passed all seven required CI checks in run `43283005098`.
- [ ] Fresh protected plan yields a safe exact-action summary; no apply unless
  the saved plan is inspected and remains within authorized gates.

## Acceptance status

- [x] Bounded fallback and regression coverage are implemented and locally
  verified.
- [ ] Documentation checks and final-head CI remain pending.
- [ ] A fresh protected plan must confirm the parser now yields a safe summary.

## Tests / validation performed

- `.venv/bin/pytest tests/test_terraform_plan_summary.py -q`: 17 passed.
- `make verify`: 1,055 passed; Ruff, OpenAPI, Actions configuration, and Docker
  Compose checks passed. One existing Starlette/httpx deprecation warning.
- `GITHUB_PR_NUMBER=385 .venv/bin/python scripts/check_doc_conventions.py` and
  `git diff --check` passed.
- Implementation commit `eeae564` passed all seven required checks in CI run
  `43283005098`; the updated PR head remains subject to GitHub's merge checks.

## Evidence files produced

- `docs/tickets/ticket385.md`
- `scripts/summarize_terraform_plan.py`
- `tests/test_terraform_plan_summary.py`

## Boundaries

Do not log or persist raw `terraform show -json` output. This change does not
enable customer apply, hosted certification, or regional pricing approval.

## Follow-up work

After merge, dispatch one fresh protected plan, inspect its exact summarized
actions and runtime gate values, and keep apply closed until the saved plan is
reviewed.
