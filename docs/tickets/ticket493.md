# ticket493 — verify Parameter Store module lifecycle

PR: #493 — draft, ticket-first implementation.
Branch: `test/parameter-config-lifecycle-493`.

## Problem / goal

The capability matrix has source-level checks for `aws_ssm_parameter` but no
direct lifecycle evidence for `modules/parameter-config`. Verify the exact
Standard-tier `SecureString` module shape, a synthetic value update, encrypted
retrieval, redaction, and exact cleanup without involving the hosted control
plane, remote Terraform state, or customer data.

Terraform state contains the parameter value despite the variable's `sensitive`
mark. Test only with synthetic values, retain the local state as evidence, and
never print either value.

## Current repo state

- Backend `main` is `fb9a0dca09f5604b45aeef81c3a2dbe8423b87c4` (PR #491).
- PR #486 remains open; its synchronized CI is green, while its clean-room
  artifact cleanup awaits explicit approval. Preserve those artifacts.
- AWS test account is `654654474502`, region `us-east-1`. The hosted control
  plane, Terraform remote state, and lock resources are outside this test.

## Research / references used

- `infrastructure/terraform/modules/parameter-config/main.tf`.
- SSM parameter checks and regressions in
  `apps/api/src/davdeploy/generated_plan_policy.py` and
  `tests/test_generated_plan_policy.py`.
- The root-specific acceptance requirements in
  `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`.

## Work planned for the PR

1. Add a local-state fixture with exactly one `modules/parameter-config`
   instance, a unique parameter name, synthetic values, and a `TestId` tag.
2. Add a bounded read helper that confirms the caller account and parameter
   ownership, verifies type/tier/key metadata, and compares decrypted v1/v2
   values in memory without printing values or response bodies.
3. Add helper regression tests for identity mismatch, wrong ownership,
   metadata mismatch, value mismatch, and output redaction.
4. Review and monitor exact create, update, and destroy plans; independently
   verify the tagged parameter is absent and retain local state.
5. Record evidence limits: no consumer authorization/revocation, secret
   rotation, application behavior, complete cost, hosted execution, or Nova
   dispatch is established by this module test.

## Acceptance criteria

- [ ] The fixture creates only one tagged exact-module Standard `SecureString`
  parameter using local Terraform state and synthetic values.
- [ ] AWS confirms the parameter name, ARN, Standard tier, SecureString type,
  and expected KMS key identity without outputting the value.
- [ ] A Terraform update changes the synthetic v1 value to v2; helper reads
  both versions without logging either value.
- [ ] Monitored destroy and independent AWS reads confirm only the test
  parameter is absent; state and local evidence remain retained.
- [ ] Helper regressions, Terraform checks, docs conventions, diff checks, and
  final-head CI pass.
- [ ] No hosted control-plane, remote-state, unrelated AWS, or customer data is
  touched.

## Acceptance status

Ticket-first work is staged. No fixture or helper implementation, AWS resource,
Terraform operation, or control-plane change has occurred yet.

## Tests / validation performed

- Ticket-first `git diff --check` and documentation-convention checks will be
  recorded after the initial ticket structure is complete.

## Evidence files produced

- `docs/tickets/ticket493.md`

## Boundaries

Use a unique `/davdeploy/nova-parameter-config-493/<TestId>/...` name and a
local Terraform state file. Use synthetic values only. Confirm account and
`TestId` before any test-owned AWS operation. Do not print decrypted values or
state contents. No cleanup is allowed outside the exact test parameter. Do not
touch hosted control-plane, remote-state, lock-table, unrelated AWS, or
customer resources. Preserve generated state and local evidence after teardown.

## Follow-up work

Consumer-role least privilege and revoked-access denial, actual secret
rotation, application retrieval/redaction at use, full request/KMS/log cost,
and Nova-originated execution remain separate acceptance gates.
