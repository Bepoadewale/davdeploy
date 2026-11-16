# ticket420 — summarize single IAM inline policy objects

PR: #420 https://github.com/Bepoadewale/davdeploy/pull/420
Branch: `fix/plan-summary-inline-policy-shape-420`

## Problem / goal

Protected plan `43978767214` reached the new safe policy locator and reported
that the failing value is `aws_iam_role.nova_plan_only[0]`, before state,
field `inline_policy`. Its policy name `isolated-nova-plan-only-artifacts`
contains hyphens, but the summarizer validated policy names with its
environment variable-name pattern, which rejects hyphens. Use an IAM
policy-name allowlist for named `{name, policy}` objects while preserving
strict validation and value redaction.

## Current repo state

- Backend `main` includes PR #419 at `e34dea6c3d566b9f43211406c62bc05c9e23aa82`.
- Main CI run `43978072011` passed all seven jobs.
- Protected plan run `43978767214` failed closed with safe context:
  resource `aws_iam_role.nova_plan_only[0]`, side `before`, field
  `inline_policy`. It did not publish a plan and no apply ran.
- The HashiCorp AWS provider defines `aws_iam_role.inline_policy` as a set of
  objects containing `name` and `policy` fields:
  https://github.com/hashicorp/terraform-provider-aws/blob/main/internal/service/iam/role.go
- A regression test using a hyphenated name reproduced the rejection.

## Research / references used

- `scripts/summarize_terraform_plan.py` — IAM policy shape parsing and safe
  diagnostics.
- `tests/test_terraform_plan_summary.py` — policy summary and redaction tests.
- HashiCorp AWS provider `internal/service/iam/role.go` — inline policy
  schema and provider state flattening.
- Protected plan run `43978767214` — safe failure context only; raw plan was
  suppressed and no plan was published.

## Work planned for the PR

1. Validate named policy objects with an IAM policy-name allowlist that
   accepts hyphens instead of the environment variable-name pattern.
2. Keep direct document, single named object, and list/set named policy
   support.
3. Add tests for supported representations and malformed names/documents.
4. Run focused tests, full verification, docs conventions, and required CI.
5. Generate a fresh protected plan after merge and inspect its sanitized
   summary; do not apply.

## Acceptance criteria

- [x] Hyphenated names in single and list named `{name, policy}` values are
      summarized correctly.
- [ ] Existing list and direct document shapes continue to work.
- [ ] Malformed shapes fail closed without exposing raw policy values.
- [ ] Focused tests, full verification, docs conventions, diff checks, and
      final-head GitHub CI pass.
- [x] No apply, deployment, runtime gate change, AWS resource mutation, or
      customer workload execution is part of this PR.

## Acceptance status

Policy names now use a bounded IAM-specific allowlist that supports hyphens;
the rest of the summary remains value-redacted and fail-closed. Focused tests
pass; full verification, docs checks, and final-head CI are pending. The last
protected plan published no plan and dispatched no apply.

## Tests / validation performed

- `tests/test_terraform_plan_summary.py` — 31 passed.
- Focused Ruff and `git diff --check` — passed.

## Evidence files produced

- No `docs/test/` customer-workload evidence is required: this PR adjusts the
  sanitized plan parser only, with no customer workload execution.

## Boundaries

This PR changes only accepted structural shapes for IAM policy summaries. It
does not run Terraform apply, change production resources, enable Nova apply,
or publish customer workload evidence.

## Follow-up work

After merge, generate a new protected plan for current `main`. Review its
sanitized resource, IAM policy, CodeBuild environment, and output details.
Do not apply the plan as part of this PR.
