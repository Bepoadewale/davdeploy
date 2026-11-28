# test563 — Nova typed reference repair feedback

Date: 2026-11-28

Execution type: Hosted plan-only diagnostic baseline plus local contract tests

Customer repository: Synthetic DavDeploy acceptance case

Commit: pending PR #563 final commit

AWS account: `654654474502`

AWS region: `us-east-1`

## Resources created

No customer workload AWS resources were created or changed. This PR changes
Nova generation guidance and tests only. Any later control-plane code release
will use the protected saved-plan workflow and will be recorded here separately.

## Commands executed

- Authenticated read-only CLI request for hosted run
  `32b172f4-4ef7-4bbe-a5dc-f163df217b40`; output restricted to run state,
  prompt version, artifact presence, and allowlisted feedback.
- Focused tests:
  `PYTHONPATH=apps/api/src /Users/adewale/Projects/davdeploy/.venv-pr399/bin/python -m pytest tests/test_terraform_generation.py tests/test_customer_plan_review.py tests/test_nova_plan_runs.py -q`
  — 148 passed.

## Observed result

- Hosted v24 run `32b172f4-4ef7-4bbe-a5dc-f163df217b40` is terminal `FAILED`
  before CodeBuild, with no artifact. Its safe feedback is
  `reference_type_mismatch`; no raw proposal, plan, state, or secret was
  retrieved.
- Added a regression in which a typed reference with a mismatched output type
  fails strict validation, receives fixed guidance on the bounded repair
  attempt, and succeeds after matching the declared output type. The repair
  feedback does not expose the proposal's resource IDs or mismatched type.
- Full `make VENV=/Users/adewale/Projects/davdeploy/.venv-pr399 verify`
  passed 2,096 tests; Ruff, Actions configuration, OpenAPI snapshot, and Compose
  config passed. Documentation conventions and diff checks passed.
- The contract validator is unchanged. Isolated `make local-proof` at commit
  `8881b1b2` passed smoke, API contract, customer-plan E2E, seed/trace,
  2,096 tests, Ruff, Actions, OpenAPI, and Compose checks. It used project
  `davdeploy-nova-ref563-proof` and ports 18080/18090/19090/13200/13000/18181
  to avoid the existing `davdeploy-nova-lambda-health-feedback-560` stack.
- The isolated project containers are stopped. Its worktree, dedicated venv,
  and PostgreSQL volume remain retained; no files or volumes were deleted.
- No hosted v25 run has been requested yet; PR CI/review, release, and fresh
  hosted result remain pending.

## Teardown

No customer workload resources were created, so there was nothing to tear
down. No Terraform mutation was started for this test.

## Final boundary

The local regression proves one bounded correction path and keeps the typed
graph check strict. It does not prove that hosted Nova will produce a valid
composed plan, that its costs are real, or that any customer workload can be
approved, applied, operated, recovered, or destroyed.
