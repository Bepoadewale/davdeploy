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
- [ ] Focused tests, full verification, clean-room proof, docs checks, and required CI pass.
- [ ] A fresh saved Terraform plan on the merged commit confirms storage resources are created while state API, runner, review, and role-verification gates remain disabled.
- [ ] No state API permissions or route are applied as part of storage-only setup.

## Acceptance status

- [x] Implementation and focused/full local validation are complete.
- [ ] Isolated clean-room and required CI are pending.
- [ ] No AWS apply is in scope for this PR; the corrected saved plan and storage rollout follow after merge.

## Tests / validation performed

See `docs/test/test338.md`; CI and isolated clean-room results will be added before merge.

## Evidence files produced

- `docs/test/test338.md` — local tests, clean-room and final CI evidence.

## Boundaries

This PR does not enable the state API, Nova runner, plan review, role verification, or customer execution. It does not apply Terraform or change AWS resources.

## Follow-up work

After merge, create a new protected Terraform plan because the previous plan predates this permission-gate correction. Review it for storage-only actions, then apply the exact new saved plan and verify bucket controls and Lambda flags.
