# ticket561 — improve Nova RDS secret output repair

PR: [#561](https://github.com/Bepoadewale/davdeploy/pull/561) (draft)

Branch: `fix/nova-rds-secret-output-repair-561`

## Problem / goal

After PR #560 was deployed, a fresh hosted v22 review-only generation failed
before CodeBuild with sanitized feedback `unsupported_secret_output` at
`resources[*]`. Tighten repair guidance and normalize only a provably unique
RDS-managed secret ARN output consumed by one declared Lambda environment
variable. Keep strict contract validation for ambiguous or unsupported outputs.

## Current repo state

- Backend `main`: `1c4d36fa65ea34cd96f56c6356549b57fafd1d59` (PR #560 merged).
- Protected control-plane apply run `46076195000` succeeded using saved plan
  `46075269981`; migrations completed, `/healthz` returned HTTP 200, and all
  six control-plane Lambda package hashes match the exact release object.
- Hosted v22 run `64d26083-1521-4388-b2a6-e71b0054c72b` is terminally
  `FAILED`, with two attempts, no artifact, and safe feedback
  `unsupported_secret_output` at `resources[*]`.
- Its submitted review-only revision is `e28d434e-de59-457c-8e3a-95d37b43154c`;
  content digest matches the prior revision and no decision exists.
- No customer workload was approved, planned, applied, or destroyed. The
  customer workload is not certified.

## Research / references used

- `generated_deployment_contract.py` permits only the RDS-managed output
  `master_user_secret[0].secret_arn` when
  `manage_master_user_password=true`.
- `nova_contract_generation.py` already normalizes an unambiguous RDS/Lambda
  secret reference, but currently recognizes only the canonical output name.
- `terraform_generation.py` owns fixed validation feedback and the bounded
  Nova repair loop.
- `docs/test/test560.md` records the preceding hosted health-target failure.

## Work planned for the PR

1. Clarify the exact supported RDS output name and managed-password requirement
   in fixed repair feedback.
2. Normalize one uniquely declared RDS secret-reference output to the canonical
   output name only when one Lambda `_SECRET_ARN` consumer identifies it.
3. Keep duplicate, non-RDS, multi-database, multi-consumer, and otherwise
   ambiguous secret outputs unchanged so strict validation rejects them.
4. Add focused normalization and bounded-repair tests; update the private goal
   ledger, ticket, and PR-specific evidence without recording raw proposal data.
5. Pass required CI, self-review, and the repository's verification gates;
   then deploy via the exact saved-plan control-plane workflow and make one
   fresh hosted review-only attempt.

## Acceptance criteria

- [x] Fixed feedback identifies the exact RDS-managed output and required flag.
- [x] One unambiguous RDS/Lambda reference is normalized and validated.
- [x] Unsupported outputs on non-RDS resources and ambiguous references remain
  unchanged for strict rejection.
- [x] Normalization removes a model-authored RDS password and retains no such
  literal in its normalized result.
- [x] Focused tests pass (153 passed); full `make verify` passes (2,092
  passed, Ruff, Actions configuration, OpenAPI, and Compose checks pass).
- [ ] Required isolated clean-room verification passes.
- [ ] PR review and all required current-head CI checks pass.
- [ ] Fresh hosted v23 generation yields an inspectable plan or a precise next
  blocker; no customer workload approval/apply/destroy occurs.

## Boundaries

Do not weaken schema/policy validation, alter execution roles or hosted
infrastructure outside the protected release workflow, expose secrets or raw
proposal/plan/state data, or claim customer deployment/lifecycle evidence.

## Acceptance status

In progress. The narrow normalization and fixed guidance are implemented and
locally verified. Clean-room proof, PR/CI review, protected release, and the
fresh hosted v23 outcome remain pending.

## Tests / validation performed

- Focused Nova contract/generation/review/run suite: 153 passed.
- Full `make VENV=/Users/adewale/Projects/davdeploy/.venv-pr399 verify`:
  2,092 passed; Ruff, Actions configuration, OpenAPI, and Compose passed.
- Documentation convention check and `git diff --check` pass.
- Isolated clean-room proof, PR review/CI, and hosted verification remain
  pending.

## Evidence files produced

- `docs/test/test561.md`
- `docs/tickets/ticket561.md`

## Follow-up work

Complete clean-room proof, PR review/CI, protected control-plane release, then
run one fresh v23 review-only generation. Continue with its earliest safe
blocker. Do not approve or apply the synthetic customer workload.

