# ticket561 — improve Nova RDS secret output repair

PR: pending

Branch: `fix/nova-rds-secret-output-repair-561`

## Problem / goal

After PR #560 was deployed, a fresh hosted v22 review-only generation failed
before CodeBuild with sanitized feedback `unsupported_secret_output` at
`resources[*]`. Tighten repair guidance and normalize only a provably unique
RDS-managed secret ARN output consumed by one declared Lambda environment
variable. Keep strict contract validation for ambiguous or unsupported outputs.

## Current repo and hosted state

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

## Research / references

- `generated_deployment_contract.py` permits only the RDS-managed output
  `master_user_secret[0].secret_arn` when
  `manage_master_user_password=true`.
- `nova_contract_generation.py` already normalizes an unambiguous RDS/Lambda
  secret reference, but currently recognizes only the canonical output name.
- `terraform_generation.py` owns fixed validation feedback and the bounded
  Nova repair loop.
- `docs/test/test560.md` records the preceding hosted health-target failure.

## Work planned

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

- [ ] Fixed feedback identifies the exact RDS-managed output and required flag.
- [ ] One unambiguous RDS/Lambda reference is normalized and validated.
- [ ] Unsupported and ambiguous outputs remain rejected.
- [ ] No model-authored password or secret value is retained by normalization.
- [ ] Focused tests and required local/clean-room verification pass.
- [ ] PR review and all required current-head CI checks pass.
- [ ] Fresh hosted generation yields an inspectable plan or a precise next
  blocker; no customer workload approval/apply/destroy occurs.

## Boundaries

Do not weaken schema/policy validation, alter execution roles or hosted
infrastructure outside the protected release workflow, expose secrets or raw
proposal/plan/state data, or claim customer deployment/lifecycle evidence.

## Acceptance status

In progress. This ticket was created before substantive implementation. The
observed hosted blocker is documented above; implementation and validation
remain pending.

