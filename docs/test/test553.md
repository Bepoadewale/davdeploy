# test553 — Nova v16 resource ID failure and v17 follow-up

Date: 2026-11-27
Execution type: Authenticated hosted Nova plan-only generation; no CodeBuild
plan or customer workload
Customer repository: `Bepoadewale/fitness-backend` (synthetic acceptance case)
Commit: control-plane v16 `e8c69f77095d4c0eb08a4a102b2ffde68ba41c71`; v17
implementation `1e11e594cb4cc510f467813c7f7d39739a55677f`
AWS account: `654654474502` (control-plane release only)
AWS region: `us-east-1`

## Resources created

- v16 control-plane deployment changed eight resources in place, added and
  destroyed zero. No customer workload resources were created.
- The v16 generated-plan run failed before CodeBuild. The submitted review
  remains undecided.

## Commands executed

- PR #552 merged as `e8c69f77095d4c0eb08a4a102b2ffde68ba41c71`; final-head CI
  run `46020616677` and merged-main CI run `46021378959` passed all seven
  checks.
- Protected plan `46022153258` and exact saved-plan apply `46023240678`
  completed for the merge SHA. The apply reported 0 added, 8 changed, 0
  destroyed; database migrations completed.
- All six control-plane Lambdas were Active/Successful and matched the
  versioned release ZIP hash. `/healthz` returned HTTP 200. Authenticated CLI
  `/api/v1/me` returned HTTP 200 with workspace role `administrator`.
- Created and submitted a fresh review-only revision with no approval decision.
  Queued one plan-only run using a fresh idempotency key.
- The API status watcher inspected only run state and allow-listed diagnostics.
  It did not fetch raw proposal content, submitted values, validator messages,
  saved-plan bytes, or credentials.
- Local v17 tests exercise fixed short-ID guidance, duplicate suffix examples,
  the exact 24-character regex, strict pattern failure, and redaction of a
  synthetic invalid ID. Focused tests passed (126); full `make verify` passed
  2,056 tests, Ruff, Actions configuration, OpenAPI snapshot, and Compose
  checks. Documentation and diff checks passed. PR CI and v17 deployment are
  pending.

## Observed result

Hosted run `e2395afb-6017-4ceb-9be1-6fdd5661e3c5` failed terminally before
CodeBuild as `proposal_invalid`, prompt v16, two attempts, one repair. Safe
feedback contains one `string_pattern_mismatch` at
`resources[*].resource_id` with fixed pattern guidance. The preceding v15
health-payload diagnostic no longer appears. No CodeBuild build, saved plan,
or customer workload was created.

## Teardown

No customer workload resources were created; no teardown was required.

## Final boundary

PR #553 improves fixed ID guidance and bumps the trusted prompt version to v17.
It does not change the typed schema, approve a plan, or apply a workload.
The architecture and fixture-price limitations remain open; a corrected ID
does not alone satisfy the hosted plan acceptance gate.
