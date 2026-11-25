# ticket503 — Bound generated Lambda function plans

PR: https://github.com/Bepoadewale/davdeploy/pull/503 (draft)
Branch: `feat/lambda-service-plan-policy-503`

## Problem / goal

The Nova generated-plan policy applies shared IAM checks to Lambda resources,
but does not bound the Lambda function configuration, code identity, or
execution-role relationship. Add fail-closed checks for the ZIP Lambda shape
supported by `modules/lambda-service`, aligned with the existing Lambda pricing
model. This is source-only and does not change AWS resources or the hosted
control plane.

## Current repo state

- Backend `main` is `e7b697127691f8454e1f468a562338e6276957b4` (PR #501).
- `modules/lambda-service` supplies a ZIP file, role ARN, handler, and runtime;
  it defaults to Python 3.12 and a 30-second timeout. The pricing evaluator
  already limits Lambda pricing to ZIP packages, one architecture, 128–10,240
  MB memory, 1–900 second timeout, default 512 MB ephemeral storage, and no
  VPC attachment or reserved concurrency.
- Existing plan-policy checks cover SQS-to-Lambda bindings, Step Functions
  invoke grants, and Lambda public invoke permissions. They do not validate
  the function's runtime, artifact digest, package settings, or role trust.
- Direct isolated Lambda module lifecycle evidence exists in `docs/test/test489.md`;
  it does not prove this new policy or Nova dispatch.
- The hosted control plane and AWS resources are outside this source-only PR.

## Research / references used

- AWS [Lambda runtime table](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html), checked 2026-11-25: managed runtime identifiers and projected deprecation windows. The policy allowlist excludes runtimes already deprecated on the check date and must be reviewed when AWS changes the table.
- AWS [Lambda memory settings](https://docs.aws.amazon.com/lambda/latest/dg/configuration-memory.html): 128–10,240 MB.
- AWS [Lambda quotas](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html): 4 KB aggregate environment variables, 512–10,240 MB `/tmp`, supported architectures, and function configuration bounds.
- Repository source: `modules/lambda-service/main.tf`, `generated_plan_policy.py`, `generated_plan_pricing.py`, and their regression tests.

## Work planned for the PR

1. Fail closed when Lambda safety-critical settings are missing or unknown.
2. Bound managed runtime, ZIP package type, handler/function identity, code
   SHA-256, architecture, memory, timeout, ephemeral storage, concurrency,
   layers, tracing, dead-letter, filesystem, and VPC settings to the priced
   module shape.
3. Require a same-account execution-role ARN; validate Lambda service trust
   when that role is in the plan, and explicitly flag an external role whose
   effective permissions are not in the plan for human review.
4. Reject secret-like environment variable names without logging their values;
   enforce AWS's aggregate 4 KB variable bound.
5. Add tests for the accepted shape, each unsupported configuration, unknown
   values, untrusted role scope, and secret-like key names.
6. Update the Lambda row in the capability evidence matrix. Do not add AWS
   workload evidence for this source-only change.

## Acceptance criteria

- [x] A bounded ZIP Lambda plan with a known source hash and same-account role
  has no Lambda-specific deny findings.
- [x] Missing/unknown runtime, identity, hash, architecture, memory, timeout,
  or role scope is denied.
- [x] Image packages, VPC attachment, custom ephemeral storage, layers,
  SnapStart, custom concurrency, filesystem, and unpriced event/dead-letter
  settings fail closed.
- [x] Same-plan role trust must name only the Lambda service; external role
  permissions are visibly marked for review without exposing policy values.
- [x] Secret-like environment keys and environment maps over 4 KB are denied
  without including values in findings.
- [x] Existing SQS consumer and Step Functions Lambda policy tests continue to
  pass.
- [x] Capability documentation states exact boundaries and does not claim
  hosted execution, customer deployment, or Nova dispatch.
- [x] No AWS resource, remote state, or hosted control-plane state/runtime is
  changed.

## Acceptance status

- [x] Implementation complete.
- [x] Focused validation complete.
- [x] Required GitHub checks passed on the current final PR head.
- [ ] PR reviewed and merged.

## Tests / validation performed

Local validation: `uv run --locked --extra dev pytest
tests/test_generated_plan_policy.py tests/test_generated_plan_review.py -q`
passed (594 tests); Ruff passed for the policy module and its regression tests;
`python3 scripts/check_doc_conventions.py` and `git diff --check` passed. This
package is source-only; do not create `docs/test/test503.md` or mutate AWS.
All seven required GitHub checks passed on final-head commit `3a5dd2b` in
[CI run 45565279893](https://github.com/Bepoadewale/davdeploy/actions/runs/45565279893).
PR review and merge are pending.

## Evidence files produced

- Regression tests in `tests/test_generated_plan_policy.py`.
- No customer workload test report; this PR creates no AWS resources.

## Boundaries

Keep the PR-only workflow and preserve unrelated local work. Do not change the
hosted control plane, deploy a runtime, access Terraform state/locks, or create
AWS resources. Do not print source, environment, role-policy, or credential
values in test output.

## Follow-up work

Role permission verification for existing customer-managed Lambda roles,
artifact provenance beyond a known ZIP hash, VPC Lambda network/cost coverage,
and Nova-originated apply/lifecycle evidence remain separate acceptance work.
