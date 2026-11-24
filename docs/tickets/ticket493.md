# ticket493 — verify Parameter Store module lifecycle

PR: [#493 — test: verify Parameter Store module lifecycle](https://github.com/Bepoadewale/davdeploy/pull/493) (draft).
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

- Backend `main` is `fb9a0dca09f5604b45aeef81c3a2dbe8423b87c4` (PR #491),
  including merged roadmap documentation from PR #492.
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
- [AWS Parameter Store setup and default `aws/ssm` key](https://docs.aws.amazon.com/systems-manager/latest/userguide/parameter-store-setting-up.html).
- [AWS `SecureString` KMS encryption behavior](https://docs.aws.amazon.com/systems-manager/latest/userguide/secure-string-parameter-kms-encryption.html).

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

- [x] The fixture creates only one tagged exact-module Standard `SecureString`
  parameter using local Terraform state and synthetic values.
- [ ] AWS confirms the parameter name, ARN, Standard tier, SecureString type,
  and expected KMS key identity without outputting the value.
- [ ] A Terraform update changes the synthetic v1 value to v2; helper reads
  both versions without logging either value.
- [ ] Monitored destroy and independent AWS reads confirm only the test
  parameter is absent; state and local evidence remain retained.
- [x] Helper regressions, Terraform checks, docs conventions, diff checks, and
  final-head CI pass.
- [x] No hosted control-plane, remote-state, unrelated AWS, or customer data is
  touched.

## Acceptance status

Ticket-first draft PR #493 is open. The local-state fixture and redacted
verification helper are implemented. Nine focused tests, Ruff, Terraform
format/validation, and documentation checks pass. In account `654654474502`,
the exact target name was absent and a saved plan proposed exactly one create,
zero changes, and zero deletes; Terraform redacted the synthetic value. No
resource has been applied and the hosted control plane remains untouched.
Final-head CI run `45507936770` passed all seven checks. A fresh read still
finds the exact parameter absent, and the Terraform monitor has 59 terminal
records with zero active operations. The AWS lifecycle remains pending explicit
approval to destroy only this exact synthetic parameter after verification.

## Tests / validation performed

- Ticket-first `git diff --check` and
  `GITHUB_PR_NUMBER=493 python3 scripts/check_doc_conventions.py`: passed.
- `.venv-pr399/bin/python -m pytest
  tests/test_parameter_config_lifecycle_script.py -q`: 9 passed.
- `.venv-pr399/bin/ruff check scripts/parameter_config_lifecycle.py
  tests/test_parameter_config_lifecycle_script.py`: passed.
- `make VENV=/Users/adewale/Projects/davdeploy/.venv-pr399 verify`: 1,757
  tests passed, including lint, configuration checks, OpenAPI snapshot, and
  Compose configuration (one existing Starlette/httpx deprecation warning).
- Terraform format, initialization, and validation of
  `docs/test/fixtures/nova-parameter-config-493`: passed.
- Read-only identity check returned account `654654474502`; exact SSM name
  `/davdeploy/nova-parameter-config-493/20261125-d0f5ab/synthetic` was absent.
- Saved plan `/tmp/davdeploy-nova-parameter-config-493-20261125-d0f5ab/create-v1.tfplan`
  contains exactly one create, zero updates, and zero deletes. The sensitive
  value is redacted in the plan output. No apply or destroy has run.
- `gh pr checks 493` — all seven checks passed in final-head run
  `45507936770`.
- Read-only Parameter Store lookup after CI confirmed the exact synthetic
  parameter remains absent; `python3 scripts/terraform_run_monitor.py status`
  reported 59 terminal runs and zero active operations.

## Evidence files produced

- `docs/tickets/ticket493.md`
- `docs/test/fixtures/nova-parameter-config-493/`
- `scripts/parameter_config_lifecycle.py`
- `tests/test_parameter_config_lifecycle_script.py`

## Boundaries

Use a unique `/davdeploy/nova-parameter-config-493/<TestId>/...` name and a
local Terraform state file. Use synthetic values only. Confirm account and
`TestId` before any test-owned AWS operation. Do not print decrypted values or
state contents. No cleanup is allowed outside the exact test parameter. Do not
touch hosted control-plane, remote-state, lock-table, unrelated AWS, or
customer resources. Preserve generated state and local evidence after teardown.
Do not apply the saved plan until explicit approval covers destroying only the
exact test parameter named above; otherwise keep the package source-only.

## Follow-up work

Consumer-role least privilege and revoked-access denial, actual secret
rotation, application retrieval/redaction at use, full request/KMS/log cost,
and Nova-originated execution remain separate acceptance gates.
