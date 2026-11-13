# ticket397 — preserve the exact Nova Terraform apply workspace

PR: https://github.com/Bepoadewale/davdeploy/pull/397
Branch: `feat/nova-saved-plan-apply-records-397`

## Problem / goal

The Nova plan runner currently persists the saved Terraform plan, but not the
initialized working directory required to apply it later. Preserve the exact
generated configuration and initialized provider/backend workspace in a
versioned, encrypted artifact so a future apply can use the approved saved
plan without regenerating configuration.

## Current repo state

Backend `main` is at `dde1dc3d80d2a8adf0d8e6ebeef6fbdbb7f9e1ce` (PR #396).
The plan-only runner is deployed. Its artifact stores exact saved-plan bytes,
while the plan's generated configuration and `.terraform` initialization
metadata remain only in the temporary CodeBuild workspace. Regional pricing
still blocks approval; no Nova apply executor exists.

## Research / references used

- HashiCorp [Terraform automation guidance](https://developer.hashicorp.com/terraform/tutorials/automation/automate-terraform)
- HashiCorp [Terraform backend configuration](https://developer.hashicorp.com/terraform/language/backend)
- `apps/api/src/davdeploy/generated_terraform_plan.py`
- `apps/api/src/davdeploy/generated_plan_artifacts.py`
- `apps/api/src/davdeploy/nova_plan_codebuild.py`
- `apps/api/src/davdeploy/service.py` generated-plan persistence and approval
- `apps/api/src/davdeploy/db.py` schema migrations

## Work planned for the PR

- Produce a deterministic, bounded archive of the exact generated Terraform
  configuration, pinned lockfile and initialized `.terraform` working metadata.
- Exclude the saved plan from the workspace archive; persist it once as its
  existing separately hashed artifact.
- Reject symlinks, unexpected files, unsafe paths, oversized members and
  workspace credential leakage before archiving.
- Store the workspace archive as a separate versioned, KMS-encrypted object
  with exact size, digest, key and version binding in the immutable manifest
  and database record.
- Make plan approval fail closed when either the saved plan or its execution
  workspace object is absent, stale or unverifiable.
- Add bounded verification and safe extraction primitives for a later fixed
  apply worker; do not execute Terraform apply in this PR.
- Keep existing review APIs free of raw plan, configuration, workspace,
  provider, state or secret values.

## Acceptance criteria

- [x] The workspace archive contains the exact plan-time configuration,
  lockfile and initialized backend/provider metadata without the saved plan.
- [x] Archive generation and extraction reject traversal, links, special
  files, unexpected entries, credential bytes and size/member-limit breaches.
- [x] The archive object is encrypted, versioned, integrity-checked and
  immutably bound to the same tenant, revision, proposal, configuration,
  provider lock and saved plan.
- [x] Approval verifies exact object versions and fails closed if either
  object is missing, tampered, expired or incorrectly scoped. Its live approval
  path remains gated by unavailable pricing and the closed plan-only boundary.
- [x] Fresh and pre-existing schema migration tests pass.
- [x] Existing plan-review response remains value-free.
- [x] No apply dispatch, apply credentials, Terraform apply, AWS workload
  mutation, customer plan, or health/lifecycle claim occurs.
- [ ] Focused tests, `make verify`, docs conventions, clean-room local proof,
  and required CI pass.

## Acceptance status

- Implementation is in progress on the draft PR. The exact initialized workspace
  is bundled separately from the saved plan, stored with KMS encryption and S3
  versioning, bound in the immutable manifest/database row, and verified before
  approval. Terraform apply remains intentionally out of scope.

## Tests / validation performed

- `uv run ruff check --fix` on the changed Terraform workspace, artifact and
  CodeBuild test files: passed.
- `uv run pytest tests/test_generated_plan_artifacts.py tests/test_generated_plan_review.py tests/test_nova_plan_codebuild.py tests/test_db_config.py tests/test_generated_terraform_plan.py -q --tb=short`:
  86 passed before adding safe extraction coverage.
- `uv run pytest tests/test_generated_terraform_plan.py tests/test_generated_plan_artifacts.py -q --tb=short`:
  40 passed after adding archive extraction and build-scoped artifact checks.
- `git diff --check`: passed before the last test addition.
- Focused artifact, plan review, CodeBuild, migration, Terraform workspace,
  infrastructure-policy, and invitation migration tests: 106 passed on final
  implementation (including the encrypted/versioned workspace object round-trip).
- `make verify`: 1,091 passed, Ruff, Actions configuration, OpenAPI, and Compose
  checks passed before the final added workspace-store unit test.
- Documentation conventions and Terraform formatting checks passed. A fresh
  full clean-room Docker cycle is pending because the existing `davdeploy`
  Compose stack is running against its persisted local database; this PR has
  not interrupted or reseeded that stack. Required hosted CI is pending.
- No AWS or customer workload execution occurred.

## Evidence files produced

- `docs/tickets/ticket397.md`
- Add `docs/test/test397.md` if any customer workload or AWS execution occurs.
  This PR is intended to remain local and CI verified only.

## Boundaries

This PR does not add or enable apply, regenerate or edit configuration at apply
time, weaken pricing or approval gates, expose saved-plan/workspace bytes to
the API or browser, or reuse `customer_executor`. The later fixed apply worker
must verify and consume both exact artifacts and must reconcile uncertain
Terraform outcomes before retry.

## Follow-up work

Implement separate disabled-by-default apply dispatch, a trusted apply role
and scoped session policy, fresh short-lived state credentials, exact saved
plan application, durable run/build reconciliation, observed health, recovery,
and teardown. Regional pricing remains held for account-owner direction on
the closed PR #318 work.
