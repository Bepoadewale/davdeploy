# ticket461

PR: [#461 — feat: enforce safe ECR repository settings](https://github.com/Bepoadewale/davdeploy/pull/461) (draft)

Branch: `feat/ecr-repository-plan-safety-461`

## Problem / goal

The ECR Terraform module declares immutable tags, scan-on-push, AES256
encryption, and does not force-delete image contents. Generated-plan policy
does not currently verify those settings. Add fail-closed checks and regression
tests so a generated repository plan cannot silently weaken the module's
declared safeguards.

## Current repo state

- `infrastructure/terraform/modules/ecr/main.tf` sets `IMMUTABLE` tags,
  `scan_on_push = true`, and `AES256` encryption.
- The module leaves ECR `force_delete` at its provider default (`false`).
- Generated-plan policy has no ECR repository-specific checks.
- `docs/test/test239.md` records ECR settings in a combined AWS stack, not an
  image push-and-run test mapped to this module root.
- AWS documents the repository-level scan setting as deprecated in favor of
  registry-level scanning. The plan field is therefore configuration intent,
  not evidence that the account's effective scanning policy is enabled.

## Research / references used

- [Amazon ECR CreateRepository API](https://docs.aws.amazon.com/AmazonECR/latest/APIReference/API_CreateRepository.html)
- [Preventing image tags from being overwritten](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-tag-mutability.html)
- [Creating an ECR private repository](https://docs.aws.amazon.com/AmazonECR/latest/userguide/repository-create.html)
- `infrastructure/terraform/modules/ecr/main.tf`
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`

## Work planned for the PR

1. Mark ECR image mutability, scanning, encryption, and force-delete fields as
   policy-critical unknowns.
2. Require immutable tags, scan-on-push declared, AES256 encryption, and
   `force_delete = false` for planned ECR repositories.
3. Add passing, unsafe, and unknown-value regression cases.
4. Apply the checked-in ECR module in the same AWS account under an explicit
   account guard, verify repository settings, then destroy the empty test
   repository and independently confirm its absence.
5. Update the capability matrix with the implemented source checks and the
   remaining effective-scanning, image provenance, access-policy, runtime, and
   pricing gaps.

## Acceptance criteria

- [x] A repository matching the checked-in module's declared settings remains
  eligible for human review.
- [x] Mutable tags, disabled scan-on-push, unsupported encryption, and
  `force_delete=true` are denied.
- [x] Unknown safety-critical ECR values are denied.
- [x] No rule claims registry-level image scanning is active from the
  deprecated repository-level field alone.
- [x] The capability matrix records the new source-only policy and leaves
  image provenance, effective scanning, scoped use, pricing, and live lifecycle
  evidence open.
- [x] Focused regression tests, documentation conventions, and `git diff
  --check` pass.
- [ ] The exact disposable ECR test repository is destroyed and independently
  confirmed absent; no hosted control-plane state is changed.

## Acceptance status

Implementation and focused regression tests pass locally. The disposable AWS
module lifecycle run, PR CI, and review are pending.

## Tests / validation performed

- ECR-focused generated-plan policy tests — 15 passed.
- Full `tests/test_generated_plan_policy.py` — 348 passed.
- Ruff on the changed Python files — passed.
- Documentation conventions and `git diff --check` — pending.
- Terraform plan/apply/destroy and independent AWS inventory evidence — pending.

## Evidence files produced

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- `docs/test/fixtures/nova-ecr-repository-461/main.tf`
- `docs/test/test461.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket461.md`

## Boundaries

- Do not modify the hosted control plane, registry-wide scanning settings, or
  any existing ECR repository.
- The only planned cloud mutation is the exact fresh tagged test repository in
  `docs/test/fixtures/nova-ecr-repository-461/main.tf`; destroy it after
  verification.
- Do not treat repository-level scan configuration as proof of effective
  registry-level scanning.
- Do not claim ECR image provenance, image execution, complete pricing, or
  general ECR support from these plan-policy checks.
- Preserve `--only-show-errors`, `.venv-pr399/`, and the untracked Batch
  Terraform state file.

## Follow-up work

Add customer-tested image provenance, scoped pull/run, registry scanning
evidence, and complete image storage/transfer/scanning price coverage before
claiming ECR workload support.
