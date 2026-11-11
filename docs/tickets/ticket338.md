# ticket338 - gate Nova state access on the state API

PR: [#338](https://github.com/Bepoadewale/davdeploy/pull/338)
Branch: `fix/nova-state-api-permission-gate-338`

## Problem / goal

Storage provisioning and runtime access are separate capabilities. The state-storage flag should create the encrypted bucket, but the API Lambda must not receive Terraform state object or KMS permissions until the state API itself is enabled.

## Current repo state

- Backend main is `4e087724a86839893994354321dadff1c60df336` after PR #337.
- Only `NOVA_TERRAFORM_STATE_STORAGE_ENABLED=true` is set in the protected plan environment; the state API remains false by default.
- Fresh plan run [42955035771](https://github.com/Bepoadewale/davdeploy/actions/runs/42955035771) succeeded and was reviewed before apply. Its 7 additions and 7 updates contained exact state storage resources, but also gave the API Lambda state object and KMS permissions while the state API was false. That plan was not applied. No AWS resources were changed by this plan.
- The protected plan runner, plan review, and role verification are also disabled.

## Research / references used

- `infrastructure/terraform/serverless-control-plane/main.tf`: API role policy currently conditions Terraform state data access on the storage flag.
- `infrastructure/terraform/serverless-control-plane/variables.tf`: state API is a separate default-off input and requires storage when enabled.
- `tests/test_nova_plan_only_infra.py`: static Terraform contract tests for state storage and API boundaries.

## Work planned for the PR

- Require both state storage and state API flags before granting the API Lambda S3 object and KMS permissions.
- Keep bucket/key provisioning controlled only by the storage flag.
- Assert the permissions remain absent while only storage is enabled.

## Acceptance criteria

- [x] Runtime state object and KMS permissions are conditioned on both storage and state API flags; bucket/key provisioning remains controlled by storage.
- [x] Storage plus state API configuration retains the existing exact-prefix S3 and bucket-context KMS permissions.
- [x] Focused tests, full verification, clean-room proof, Terraform validation, and docs checks pass locally. All seven required CI checks passed in [run 42956394546](https://github.com/Bepoadewale/davdeploy/actions/runs/42956394546) for `4bcd70a`.
- [x] Fresh saved plan [42957384890](https://github.com/Bepoadewale/davdeploy/actions/runs/42957384890) on merged main included storage resources while state API, runner, review, and role-verification gates remained disabled.
- [x] The exact reviewed plan was applied by run [42958408176](https://github.com/Bepoadewale/davdeploy/actions/runs/42958408176); no state API permission or route was enabled.

## Acceptance status

- [x] Implementation, focused/full local validation, and isolated clean-room are complete.
- [x] Required CI passed for evidence head `4bcd70a`; final evidence-update head must also pass required CI before merge.
- [x] No AWS apply occurred as part of this PR. A post-merge rollout applied the fresh reviewed plan; see `docs/test/test338.md`.

## Tests / validation performed

See `docs/test/test338.md` for final-head CI and clean-room results, plus post-merge protected plan/apply and read-only AWS checks.

## Evidence files produced

- `docs/test/test338.md` — local tests, clean-room and final CI evidence.

## Boundaries

This PR does not enable the state API, Nova runner, plan review, role verification, or customer execution. It does not apply Terraform or change AWS resources.

## Follow-up work

The corrected storage-only plan has been applied and its controls verified. Future work must independently gate and review state API, customer plan-role verification, runner, pricing, and customer execution; storage provisioning alone does not enable hosted Nova plans.
