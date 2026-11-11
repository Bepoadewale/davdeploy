# ticket355 — deny public SQS queue policies in Nova plans

PR: [#355](https://github.com/Bepoadewale/davdeploy/pull/355) (merged)
Branch: `security/sqs-public-policy-355` (deleted after merge)
Base: `main`

## Problem / goal

The Nova plan access profile supports SQS, but actual generated-plan policy
does not inspect `aws_sqs_queue_policy`. An allow policy with a wildcard
principal or an allow using `NotPrincipal` can make a queue reachable by
unintended callers. Unknown queue policy data must not be treated as safe.

## Current repo state

- Backend PR #355 merged as `6e60da0075e22092c0b5278d68bb592114f21f61`.
- `generated_plan_policy.py` checks public S3 policies and selected IAM
  policies, but does not check SQS queue policies.
- The supported read-only plan access profile includes SQS queue metadata.
  The hosted Nova plan worker and state API remain disabled; this change does
  not enable them or perform AWS operations.

## Research / references used

- AWS [SQS security best practices](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-security-best-practices.html)
  advise keeping queues nonpublic and avoiding wildcard principals.
- AWS [SQS queue creation](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/creating-sqs-standard-queues.html)
  documents default server-side encryption; this PR does not infer or change
  encryption behavior.
- Terraform [JSON output format](https://developer.hashicorp.com/terraform/internals/json-format)
  defines `after_unknown` metadata used to reject an unknown policy document.

## Work planned for the PR

- Add the SQS queue policy document to the existing security-critical unknown
  value checks.
- Reject `Allow` statements with `Principal="*"`, wildcard principals in
  principal maps/lists, or `NotPrincipal` because their effective audience is
  not safely bounded by this policy.
- Reuse bounded policy-document parsing and keep findings free of raw policy
  text or queue values.
- Bump the generated-plan policy version and add positive/negative regressions.

## Acceptance criteria

- [x] Public wildcard-principal SQS allow policies are denied.
- [x] `NotPrincipal` SQS allow policies are denied.
- [x] Unknown/malformed SQS queue policy data fails closed.
- [x] Specific non-wildcard principals do not trigger the public-policy rule.
- [x] Findings contain no raw policy or queue values; existing S3 policy
  regressions remain covered.
- [x] Focused tests, `make verify`, and docs checks pass locally.
- [x] Required hosted CI passes on the final PR head.

## Acceptance status

Implementation, local verification, required hosted CI, current-head review
and merge are complete. PR run `43076888679` passed all seven required jobs.
The code is merged but not yet deployed. A protected plan for the merge
commit is run `43078429737`; the plan must be reviewed before any apply.

## Tests / validation performed

- `uv run pytest tests/test_generated_plan_policy.py -q` — 91 passed.
- `uv run ruff check apps/api/src/davdeploy/generated_plan_policy.py tests/test_generated_plan_policy.py` — passed.
- `DAVDEPLOY_DATABASE_URL=sqlite+pysqlite:///:memory: make verify` — 930
  passed; Ruff, Actions configuration, OpenAPI, and Compose checks passed.
  One existing Starlette/httpx deprecation warning remains.
- `GITHUB_PR_NUMBER=355 python3.12 scripts/check_doc_conventions.py` and
  `git diff --check` — passed.
- Final PR head `d77a927085f1db817b83a11f937b193bd1261e9d` passed all seven
  required CI jobs in run `43076888679`; merge commit is
  `6e60da0075e22092c0b5278d68bb592114f21f61`.
- No Terraform plan/apply, customer role setup, or AWS customer-resource
  mutation is in scope.

## Evidence files produced

No customer-workload test evidence applies. Local test commands and results
will be recorded in this ticket and the PR checks.

## Boundaries

This is a deterministic plan-policy change only. It does not enable or invoke
the hosted plan runner, approve plans, integrate pricing, create SQS queues,
or apply customer infrastructure. It addresses public grants and
`NotPrincipal`; it does not claim complete SQS permission analysis.

## Follow-up work

Continue the remaining typed resource-policy, regional pricing, exact
cost-bound approval, hosted state/runner, health, recovery, and teardown gates.
