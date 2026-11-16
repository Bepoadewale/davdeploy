# ticket418 — summarize IAM policy placeholders safely

PR: #418 https://github.com/Bepoadewale/davdeploy/pull/418
Branch: `fix/plan-summary-policy-placeholders-418`

## Problem / goal

The first protected plan after PR #417 failed closed with
`invalid_policy_summary`. The control-plane IAM policy intentionally contains
the literal AWS policy variable `${codebuild:buildArn}`. The value allowlist
rejects its `$` and braces, preventing the new summary from reviewing the
policy. Accept only the bounded placeholder syntax required for policy
resource values, and keep arbitrary values redacted or rejected.

## Current repo state

- Backend `main` includes PR #417 at `a866153bed7f445832892dec700cbbf2082fe140`.
- Main CI run `43972038466` passed all seven jobs.
- Fresh protected plan run `43972802456` for that main commit initialized and
  validated Terraform but failed closed with `invalid_policy_summary` before
  publishing a saved plan. No apply ran and no plan was published.
- `infrastructure/terraform/serverless-control-plane/main.tf` defines the
  literal `$${codebuild:buildArn}` in the fixed runner's scoped S3 prefix; the
  resulting IAM resource contains `${codebuild:buildArn}`.

## Research / references used

- `scripts/summarize_terraform_plan.py` — bounded IAM value parser.
- `tests/test_terraform_plan_summary.py` — structural summary and redaction
  regression tests.
- `infrastructure/terraform/serverless-control-plane/main.tf` — fixed
  `nova_plan_only_scoped_prefix` resource pattern.
- Protected plan workflow `43972802456` — safe failure reason only; raw plan
  output was suppressed and no saved plan was published.

## Work planned for the PR

1. Permit only AWS policy variable placeholders matching `${name}` in policy
   resource/principal values, without allowing arbitrary braces or dollar
   content.
2. Preserve the literal placeholder in structural output so reviewers can see
   the exact scoped policy pattern.
3. Add regression tests for valid placeholders and malformed lookalikes.
4. Run focused tests, full verification, and required CI.
5. Generate and inspect a fresh protected plan after merge; do not apply it.

## Acceptance criteria

- [x] The exact `${codebuild:buildArn}` resource form is summarized.
- [x] Malformed placeholder syntax still fails closed without echoing values.
- [ ] Focused tests, full verification, docs conventions, diff checks, and
      final-head GitHub CI pass.
- [x] No apply, deployment, runtime gate change, AWS resource mutation, or
      customer workload execution is part of this PR.

## Acceptance status

The parser now accepts only bounded `${...}` tokens in policy values, including
the fixed `${codebuild:buildArn}` resource pattern. Malformed placeholder
syntax still fails closed without echoing the value. Focused and full local
verification pass; final-head GitHub CI is pending. The failed protected plan
published no saved plan and dispatched no apply.

## Tests / validation performed

- `tests/test_terraform_plan_summary.py` — 30 passed.
- `make verify VENV=/Users/adewale/Projects/davdeploy/.venv-pr399` — 1,260
  passed; Ruff, Actions configuration, OpenAPI snapshot, and Compose checks
  passed (one existing Starlette/httpx deprecation warning).
- Diff check and focused Ruff — passed.

## Evidence files produced

- No `docs/test/` customer-workload evidence is required: this is a bounded
  plan-summary parser change, with no customer workload execution.

## Boundaries

This PR changes only the value allowlist used by protected Terraform plan
summaries. It does not run Terraform apply, change production resources,
enable Nova apply, or publish customer workload evidence.

## Follow-up work

After merge, generate a fresh protected plan for current `main` and review its
sanitized policy, CodeBuild environment, output, and resource summaries. Do
not apply the plan as part of this PR.
