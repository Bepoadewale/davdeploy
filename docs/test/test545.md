# test545 — Nova secret and resource ID guidance

Date: 2026-11-27
Execution type: Hosted plan-only generation failure before CodeBuild
Customer repository: `Bepoadewale/fitness-backend` (synthetic acceptance project)
Commit: Control-plane `668b90d7a7a9516913891667bb3c4dc27353f34c`
AWS account: `654654474502` (verified test connection; no customer workload operation)
AWS region: `us-east-1`

## Resources created

No Nova customer workload resources. The protected release updated existing
control-plane resources only; no workload was created by generation.

## Commands executed

- Authenticated CLI `GET /api/v1/generated-plan-runs/3f27c5fc-75d6-4393-8035-1938035a5a00`.
- Retrieved only the endpoint's allowlisted generation diagnostics.

## Observed result

The v9 run failed as `NOVA_GENERATION_FAILED` / `proposal_invalid` after 2
attempts and 1 repair. Safe feedback reported credential values and malformed
resource, health-target, and cost-assumption IDs. The run failed before
CodeBuild; no saved plan or workload exists. The run remains eligible for one
explicit retry after v10 deployment.

## PR #545 local verification

The v10 prompt now gives the exact supported typed secret-reference object and
stronger examples for short IDs. Focused tests passed (105 tests); the full
verification suite passed (2029 tests), with one existing Starlette
deprecation warning. Ruff, OpenAPI snapshot, Actions configuration boundary,
and Docker Compose configuration checks passed. Hosted CI and the post-release
retry remain pending.

## Teardown

Not applicable. Generation created no workload resources, builds, or plan
artifacts. Review and run evidence remain for audit.

## Final boundary

This is a generation failure only. It does not establish a valid plan,
customer approval, apply, application behavior, lifecycle, or certification.
The workload remains unapproved and unapplied.
