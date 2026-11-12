# test374 — deny unbound Secrets Manager value reads

Date: 2026-11-12

Execution type: Local policy verification; no AWS execution

Customer repository: `Bepoadewale/davdeploy`

Commit: `0514ac1ba45096a29c620785f27e813e1dde447f`

AWS account: Not accessed

AWS region: Not accessed

## Resources created

- No AWS resources, customer roles, plans, approvals, or workloads were
  created or changed.
- Clean-room resources and retained artifacts will be recorded after the
  isolated verification run.

## Commands executed

- `uv run pytest -q tests/test_generated_plan_policy.py` — 149 passed.
- `make verify` — 1,044 tests passed; Ruff, Actions configuration, OpenAPI
  snapshot and Compose checks passed. One existing Starlette/httpx deprecation
  warning remains.
- `uv run ruff check apps/api/src/davdeploy/generated_plan_policy.py tests/test_generated_plan_policy.py`
  — passed.
- `python scripts/check_doc_conventions.py` and `git diff --check` — passed
  on final evidence head `4e43cbb`.
- Full isolated clean-room proof passed from worktree
  `/private/tmp/davdeploy-pr374-cleanroom-20261112` at `58bd8d4` with unique
  Compose project `davdeploy-pr374-cleanroom-20261112`. It included clean,
  bootstrap, smoke, API contract, simple/complex/degraded/Day-2/failure/
  readiness-failure demos, customer-plan E2E, fixture seed, post-restart
  persistence, trace check and `make verify` (1,044 tests).

## Observed result

- Actual-plan IAM policy now denies explicit `GetSecretValue` and
  `BatchGetSecretValue` grants, plus action patterns such as `Get*` and
  `secretsmanager:*` that match either retrieval action.
- The check is case-insensitive, reports a fixed safe finding, and does not
  include policy resources or secret values in the finding message.
- `DescribeSecret` metadata-only permission remains eligible for human review.
- Managed-policy attachments remain explicitly review-required when their
  policy contents are not available in the plan; they are not treated as
  verified secret-read permissions by this check.
- This guard does not yet bind an application permission to a typed RDS secret
  reference; runtime secret value access remains unavailable.
- After proof, all project containers were stopped. No named volume was
  created; the external virtual environment, worktree, bind-mounted Postgres
  data, Compose network and images are retained. No files, volumes, networks or
  images were deleted. The pre-existing `davdeploy-nova-cleanroom-20261105a`
  container was not touched.

## Teardown

No AWS cleanup is needed. All PR-specific project containers are stopped;
local artifacts listed above are retained.

## Final boundary

This is local actual-plan policy verification, not a hosted plan, approval,
apply, secret retrieval, or customer workload. Hosted planning, exact costed
approval, apply, health, recovery and teardown remain separate acceptance gates.

## Pull request verification

PR #374 head `4e43cbb` passed all seven required GitHub Actions checks in run
`43161277559`. Manual review confirmed that the secret action matcher denies
exact actions and wildcards case-insensitively, while the policy's separate
`NotAction` and broad IAM checks remain in force. No AWS role, plan, approval,
apply, or customer workload was changed.
