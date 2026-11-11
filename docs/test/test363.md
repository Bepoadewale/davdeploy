# test363 — DynamoDB point-in-time recovery plan policy

Date: 2026-11-12
Execution type: Local clean-room verification; no AWS execution
Customer repository: `Bepoadewale/davdeploy`
Commit: `8b5a7cd` (`feat: enforce DynamoDB recovery policy in Nova plans`)
AWS account: Not accessed
AWS region: Not accessed

## Resources created

- No AWS resources or customer workload resources were created or changed.
- The isolated local Compose project `davdeploy-pr363-cleanroom-20261112` created application containers, a project-scoped network, and a local Postgres volume for fixtures. All its containers are stopped. Its volume, images, clean-room worktree `/private/tmp/davdeploy-pr363-cleanroom-20261112`, and local `.venv` are retained; none were deleted.
- Local fixture records and demo deployment records were created in the isolated Postgres database by the standard seed/E2E/demo scripts.

## Commands executed

- Focused policy suite: `.venv/bin/python -m pytest -q tests/test_generated_plan_policy.py` — 143 passed.
- Full backend verification: `make verify` — 998 tests passed; Ruff, Actions configuration, OpenAPI snapshot and Compose configuration passed.
- Clean-room cycle in `/private/tmp/davdeploy-pr363-cleanroom-20261112` at this commit: `COMPOSE_PROJECT_NAME=davdeploy-pr363-cleanroom-20261112 make local-proof` — fresh Python 3.12 virtual environment/dependency install, Compose bootstrap, smoke check, API/CORS contract, customer-plan E2E, fixture seed, trace check, and `make verify` passed (998 tests).
- The first immediate `make demo-simple` attempt after restarting stopped containers hit a transient local connection reset. `make smoke` then reported API, worker, executor, Prometheus and Grafana ready; rerunning `make demo-simple demo-complex demo-degraded demo-day2 demo-failure demo-readiness-failure` passed all six. Final `make trace-check`, docs conventions and `git diff --check` passed.
- Existing Starlette/httpx deprecation warning is unchanged.

## Observed result

- Actual generated-plan policy now denies critical unknown PITR fields, requires PITR enabled with a valid 1–35 day recovery period when the proposal declares `backup_required`, and returns an explicit review finding if PITR is disabled or omitted when backup is not required.
- Known enabled PITR with a valid period passes this specific recovery check. Policy results contain no plan values.
- This is local policy evidence only. Hosted Nova planning remains disabled; no AWS plan, approval, apply, application health check, recovery, or customer teardown was performed.

## Teardown

- Stopped the isolated Compose project using `COMPOSE_PROJECT_NAME=davdeploy-pr363-cleanroom-20261112 docker compose stop`.
- The local Postgres volume, images, worktree and `.venv` remain for reproducibility. No deletion was performed.
- No AWS cleanup was needed because the run made no AWS calls and created no AWS resources.

## Final boundary

The evidence validates deterministic local plan-policy behavior and the repository's local clean-room workflow. It does not establish regional pricing, hosted customer plan generation, customer role permissions, exact-plan approval/apply, data restore behavior, health monitoring, teardown authorization, or composed workload certification. Final-head GitHub CI run `43117539516` passed all seven required jobs, and current-head Codex review reported no major issues. The control-plane release was not deployed because this policy remains part of the disabled Nova workflow.
