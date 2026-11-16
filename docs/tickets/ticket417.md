# ticket417 — reviewable protected Terraform plan details

PR: #417 https://github.com/Bepoadewale/davdeploy/pull/417
Branch: `fix/terraform-plan-detail-summary-417`

## Problem / goal

The production Terraform plan workflow currently reports changed resource
fields and total output changes, but hides the IAM policy statements,
CodeBuild environment variable names, and changed output names needed to
review a plan before applying it. Improve this value-redacted summary so
reviewers can identify the exact structural change without seeing raw plan
values or secrets.

## Current repo state

- Backend `main` is `f89a4018b31c14e8a060065045169644dc422c57` after PR #416.
- Protected plan run [`43966504332`](https://github.com/Bepoadewale/davdeploy/actions/runs/43966504332)
  for that commit succeeded with 0 adds, 8 updates, 0 destroys, and one drifted
  `aws_iam_role.nova_plan_only[0].inline_policy`.
- The plan summary lists `policy` and `environment` as changed fields and
  reports 8 output changes without naming their structure. No apply was
  dispatched.
- The plan environment keeps Nova plan review/runner/state features enabled,
  hosted certification disabled, and has no Nova apply gate in the deployed
  source. No customer workload has been applied.

## Research / references used

- `scripts/summarize_terraform_plan.py` — current value-free resource and
  feature-gate summary.
- `tests/test_terraform_plan_summary.py` — plan metadata and redaction tests.
- `.github/workflows/terraform-plan.yml` — production plan summary and saved
  plan workflow.
- `infrastructure/terraform/serverless-control-plane/main.tf` — fixed Nova
  plan-only CodeBuild project and IAM policy definitions.

## Work planned for the PR

1. Summarize IAM policy statements with bounded effects, actions, resource
   patterns, principal shape, and condition keys; redact account IDs and all
   condition values.
2. Report changed CodeBuild environment variable names and allowlisted
   boolean gates, while redacting all other variable values.
3. Report changed Terraform output names, action metadata, and sensitivity
   flags without output values.
4. Reject malformed or unbounded structures rather than emitting partial or
   raw content.
5. Add regression tests proving the expected structural detail is present
   and secret-like sentinels/values never appear.
6. Keep apply disabled; use an updated protected plan summary before any
   infrastructure apply decision.

## Acceptance criteria

- [x] IAM policy scope changes are reviewable without raw policy/value leaks.
- [x] CodeBuild environment changes show exact variable names and only
      allowlisted boolean values.
- [x] Output changes show names, actions, and sensitivity without values.
- [x] Malformed, unexpected, oversized, or unknown shapes fail closed.
- [ ] Focused tests, full `make verify`, docs conventions, diff checks, and
      final-head GitHub CI pass.
- [x] No apply, deployment, runtime gate change, or AWS resource mutation is
      part of this PR.

## Acceptance status

Implementation and focused regression coverage are complete. The summary now
shows IAM policy actions/resources/principal/condition-key structure, changed
CodeBuild environment names with only fixed boolean values exposed, and
output names/actions/sensitivity. It never emits condition values, output
values, or arbitrary environment values. Review found and closed a redaction
gap for bare 12-digit AWS account IDs in principal values. Focused and full
verification plus documentation checks pass; final-head GitHub CI remains
pending for the redaction fix. No AWS apply or runtime configuration change
has occurred.

## Tests / validation performed

- `tests/test_terraform_plan_summary.py` — 28 passed after account-ID fix.
- `make verify VENV=/Users/adewale/Projects/davdeploy/.venv-pr399` — 1,258
  passed; Ruff, Actions configuration, OpenAPI snapshot, and Compose checks
  passed (one existing Starlette/httpx deprecation warning).
- Ruff on `scripts/summarize_terraform_plan.py` and
  `tests/test_terraform_plan_summary.py` — passed.
- Documentation conventions and `git diff --check` — passed.
- Required final-head GitHub CI — pending.

## Evidence files produced

- No `docs/test/` customer-workload evidence is required: this is a local plan
  summary and redaction change, with no customer workload execution.

## Boundaries

This PR changes only value-redacted Terraform plan diagnostics. It does not
run Terraform apply, change the production environment, enable Nova apply, or
claim customer workload evidence.

## Follow-up work

After merge, regenerate and inspect a fresh plan for current `main`; do not
reuse the prior saved plan. Apply only if the fresh exact plan can be reviewed
and contains expected safe changes.
