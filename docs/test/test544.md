# test544 — Specific Nova resource validation feedback

Date: 2026-11-27
Execution type: Hosted plan-only generation failure before CodeBuild
Customer repository: `Bepoadewale/fitness-backend` (synthetic acceptance project)
Commit: Control-plane `f508951645327e0d2b77d0904d17d44a783e1e57`
AWS account: `654654474502` (verified test connection; no workload operation)
AWS region: `us-east-1`

## Baseline evidence

Control-plane commit `f508951645327e0d2b77d0904d17d44a783e1e57` is deployed by
protected plan `45954762410` and exact saved-plan apply `45955715362`. The
control-plane migration passed, all six Lambdas match the versioned release
package, and `/healthz` returned HTTP 200.

One authorized retry of fresh hosted plan-only run
`137ab46f-f5ee-4fa8-80cf-363ffc5f2736` under prompt v8 failed as
`NOVA_GENERATION_FAILED` / `proposal_invalid` after two attempts and one repair.
The bounded diagnostics reported one `value_error` at `resources[*]`; they did
not expose raw validator text or proposal contents. No CodeBuild build, saved
plan, or AWS workload was created. Do not retry this run again.

## Resources created

None by the Nova customer plan request. Separately, the protected control-plane
release updated existing backend resources only; it added or destroyed none.

## Commands executed

- Authenticated CLI `GET /api/v1/generated-plan-runs/137ab46f-f5ee-4fa8-80cf-363ffc5f2736`.
- Authenticated CLI retry request to
  `/api/v1/generated-plan-runs/137ab46f-f5ee-4fa8-80cf-363ffc5f2736/retry`
  with a new idempotency key; API accepted one retry, which then failed.

## Observed result

The control-plane release is healthy, but the v8 run remains failed. A new v9
plan-only run is pending implementation and deployment.

## Teardown

Not applicable. The failed generation created no workload resources or plan
artifacts. The review and run records remain as audit evidence.

## Final boundary

This does not establish a valid plan, approval, customer apply, application
behavior, lifecycle, or certification. No customer workload has been applied.

## PR #544 result

The implementation adds allowlisted issue codes and fixed guidance for four
resource argument failure classes plus two resource output failure classes.
Local focused tests passed (105 tests); the full verification suite passed
(2029 tests), with one existing Starlette deprecation warning. Ruff,
documentation conventions, OpenAPI snapshot, Actions configuration boundary,
Docker Compose configuration, and `git diff --check` passed. Hosted CI and the
post-deployment v9 generation outcome are pending. No customer workload has
been approved or applied.

GitHub Actions run `45958110974` passed all seven required checks for PR head
`345aec0876e687c31000901cf50dd0eba00a6c0d`.
