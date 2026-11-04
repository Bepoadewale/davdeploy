# ticket311 Run isolated Nova Terraform plans

PR: #311
Branch: feat/nova-isolated-plan-runner

## Problem / goal

Turn a strictly typed Nova proposal into an isolated, backend-free Terraform saved plan, validate it with the exact locked AWS provider schema, confirm the trusted target account/region, and return only secret-safe plan metadata. This is plan-only; it must not apply or destroy.

## Current repo state

PR #307 defines the proposal contract, #308 generates proposals with trusted context binding, #309 validates AWS resource shapes, and #310 inspects plan JSON without exposing values. These pieces are not yet connected to an actual Terraform plan command. Customer execution remains gated.

## Research / references used

- Terraform JSON plan format and flags: https://developer.hashicorp.com/terraform/internals/json-format
- Terraform `plan` command: https://developer.hashicorp.com/terraform/cli/commands/plan
- Terraform provider schema: https://developer.hashicorp.com/terraform/cli/commands/providers/schema
- Terraform lock file: https://developer.hashicorp.com/terraform/language/files/dependency-lock

## Work planned for the PR

Generate a deterministic root from the validated proposal plus trusted AWS provider/account/region settings. Use only fixed Terraform subcommands, a trusted committed lockfile, no backend, bounded timeouts/output, and isolated workspace paths. Validate the proposal against the schema emitted by that initialized provider, check caller account identity, produce and hash a saved plan, inspect its JSON in memory, and return a redacted result. Add focused tests with a fake executable and one real read-only AWS plan if available. Do not expose apply.

## Acceptance criteria

- [x] Only typed AWS resources are compiled; generated provider/backend/command configuration is rejected.
- [x] Terraform and AWS provider versions are pinned to trusted values and lockfile digest is recorded.
- [x] Caller account and region must match trusted context before plan creation; Terraform also enforces account identity in the generated plan.
- [x] `init`, `validate`, `plan`, and `show -json` use fixed arguments, bounded timeouts, and no backend.
- [x] Plan JSON values are never persisted or returned; saved plan bytes are mode `0600` in a mode `0700` workspace and digest-bound.
- [x] Plan failures, unapplyable/errored plans, saved-plan tampering and unsafe paths fail closed.
- [x] Focused tests, full `make verify`, real AWS-authenticated plan and clean-room cycle pass; required CI is pending.
- [ ] Review is complete.

## Acceptance status

Implementation and verification pass. A real AWS-authenticated plan (no apply) passed in account `654654474502`, region `us-east-1`, using Terraform `1.14.7` and AWS provider `5.100.0`. It planned two creates: one synthetic S3 bucket and the trusted account guard. The clean-room bootstrap, smoke, API, demo, trace and verification cycle also passed. Exact digests and limitations are in `docs/test/test311.md`. `make verify` passed with 552 tests, Ruff, Actions configuration, OpenAPI and Compose checks. Documentation conventions passed; required CI is pending.

## Tests / validation performed

Focused tests: `.venv/bin/python -m pytest -q tests/test_generated_terraform_plan.py` (11 passed). A real run of `GeneratedTerraformPlanRunner.plan` completed `terraform init -backend=false`, provider schema validation, `terraform validate`, saved `terraform plan`, and `terraform show -json`; no AWS resources were created. Saved-plan tampering is detected by the digest verifier. `make verify`: 552 passed, plus Ruff, Actions configuration, OpenAPI snapshot, and Docker Compose config. The isolated clean-room cycle passed all documented targets at commit `2bc7f31`. Documentation conventions passed. Required CI is pending.

## Evidence files produced

No customer workload is applied by this PR. Real AWS plan-only evidence is in `docs/test/test311.md`.

## Boundaries

Terraform plans can contact provider APIs and reveal account configuration. This runner only performs read-only planning; it does not prove cost, runtime health, deletion safety, policy completeness, or hosted lifecycle readiness. Approval, apply, destroy, worker dispatch and customer API integration remain separate future gates.

## Follow-up work

Add deterministic policy over the actual plan, encrypt and durably store the saved plan, bind approval to its exact digest, integrate with hosted worker, implement post-apply observations/recovery/cleanup, and certify the first composed customer workload.
