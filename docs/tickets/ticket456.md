# ticket456 — bound Step Functions roles to planned Lambda tasks

PR: https://github.com/Bepoadewale/davdeploy/pull/456
Branch: `feat/step-functions-role-scope-456`

## Current repo state

- Backend `main` is `d894357518dcd929fdabaa9292e1b649d0eb2ca0` (PR #455).
- Merged PR #454 records direct Lambda failure/Catch recovery and teardown.
  Nova dispatch and hosted lifecycle remain unproven by that service test.
- Step Functions role permissions were previously subject only to generic IAM
  checks; those checks did not bind permissions to the workflow's actual tasks.
- The hosted control plane and its Terraform state/locks are out of scope.

## Problem / goal

A Standard state machine can call AWS services under its execution role. Generic
IAM checks do not prove that the role can only invoke the same-plan Lambda
functions named by the workflow definition. Add a bounded policy contract for
that directly tested shape, rejecting unknown integrations and unverified role
permissions.

## Research / references used

- AWS [Step Functions execution-role guidance](https://docs.aws.amazon.com/step-functions/latest/dg/manage-state-machine-permissions.html)
  states that the execution role grants permissions used by workflow tasks.
- AWS [creating a Step Functions IAM role](https://docs.aws.amazon.com/step-functions/latest/dg/procedure-create-iam-role.html)
  recommends `aws:SourceArn` and `aws:SourceAccount` conditions to prevent
  confused-deputy use.
- AWS [Lambda integration](https://docs.aws.amazon.com/step-functions/latest/dg/connect-lambda.html)
  documents `lambda:InvokeFunction` permissions scoped to function ARNs.
- [`test454.md`](../test/test454.md) — the direct Standard workflow failure,
  Catch recovery, normal success, and teardown shape.

## Work planned for the PR

1. Require a known Standard state-machine definition with direct Lambda task
   ARNs and exact references to same-plan Lambda functions.
2. Require exactly one referenced IAM role with a `states.amazonaws.com` trust
   policy conditioned on the exact state-machine ARN and account.
3. Require inline role policies to grant only `lambda:InvokeFunction` on the
   exact Lambda ARNs used by the workflow; reject extra grants and managed
   policy attachments.
4. Fail closed on Express workflows, logging configuration, Map/Parallel
   states, optimized or AWS SDK integrations, and unknown task resources.
5. Add regression tests and update the handoff/matrix without claiming hosted
   execution or customer support beyond this finite plan shape.

## Evidence used

- PR #454's direct test established one Standard state machine with two direct
  Lambda task states and exact function invocation permissions.
- The AWS documentation above defines the role and Lambda permissions that the
  plan check binds.

## Acceptance criteria

- [x] A valid Standard workflow with same-plan Lambda task(s), exact role trust,
      and exact invoke grants remains eligible for human review.
- [x] Extra, wildcard, unrelated, and unplanned Lambda permissions are denied;
      missing exact invocation grants fail closed.
- [x] Trust without exact `aws:SourceArn` and `aws:SourceAccount` conditions is
      denied.
- [x] Managed-policy attachments and unsupported integrations/configurations
      fail closed.
- [x] Findings expose no policy values, workflow definition text, or secrets.
- [ ] Focused tests, Ruff, documentation conventions, and all seven required
      PR checks pass.
- [x] No AWS workload, hosted control-plane resource, Terraform state/lock, or
      Nova execution gate is changed.

## Acceptance status

The source policy and regression cases are implemented. Focused validation
passes; required PR CI is pending.

## Tests / validation performed

- `.venv-pr399/bin/python -m pytest -q tests/test_generated_plan_policy.py` — 339 passed.
- `.venv-pr399/bin/python -m ruff check apps/api/src/davdeploy/generated_plan_policy.py tests/test_generated_plan_policy.py` — passed.
- `python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.

## Evidence files produced

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- `docs/tickets/ticket456.md`
- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

## Boundaries

This is a source-only policy change. Do not touch the hosted control-plane
runtime, state/locks, production resources, Nova apply gates, customer
credentials, or retained SageMaker lineage. Do not claim that the direct test
or this policy check proves Nova dispatch or a certified customer workload.
Preserve protected untracked `--only-show-errors` and `.venv-pr399/`.

## Follow-up work

This policy covers only Standard workflows with direct same-plan Lambda tasks.
Other service integrations, version/alias permissions, CloudWatch logging,
Map/Parallel states, retries/redrive, and hosted Nova lifecycle remain
unsupported or unverified.
