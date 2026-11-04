# ticket310 Inspect Terraform's generated JSON plan

PR: #310
Branch: feat/nova-terraform-plan-inspection

## Problem / goal

Convert Terraform's machine-readable plan into a deterministic, secret-safe review summary before any approval or apply. Make creates, updates, deletes and replacements visible without authorizing execution.

## Current repo state

PR #308 generates a typed Nova deployment proposal and Terraform configuration, still plan-only. PR #309 validates proposed AWS resource fields against a supplied provider schema. There is no trusted Terraform runner integration or generic hosted apply path yet.

## Research / references used

- Terraform plan JSON format: https://developer.hashicorp.com/terraform/internals/json-format
- `terraform show -json`: https://developer.hashicorp.com/terraform/cli/commands/show
- Plan JSON exposes before/after values and sensitivity metadata; this component must not copy values into review evidence.

## Work planned for the PR

Implement a strict, bounded parser for Terraform plan JSON that returns resource addresses, action summaries, create/update/delete/replacement counts, drift counts and sensitive-field presence without returning before/after values. Reject unsupported formats and malformed action records. Keep it a pure inspection component with no process, filesystem, cloud, approval or apply access.

## Acceptance criteria

- [x] Terraform JSON format and resource changes are validated with strict bounds.
- [x] Create, update, delete, replacement and no-op actions are categorized correctly.
- [x] Review output contains no resource values, secrets or raw Terraform JSON.
- [x] Sensitive changes are indicated without exposing values.
- [x] Focused tests cover normal, destructive, malformed, oversized and sensitive plans.
- [x] Full `make verify` passes; required CI is pending.
- [ ] PR review is complete.

## Acceptance status

Implementation and local verification pass. Focused suite: 11 tests. Full `make verify`: 539 tests passed, Ruff passed, Actions configuration passed, OpenAPI snapshot passed, Docker Compose config passed. One existing Starlette/httpx deprecation warning remains.

## Tests / validation performed

`.venv/bin/python -m pytest -q tests/test_generated_plan_inspection.py` (11 passed); `.venv/bin/python -m ruff check apps/api/src tests scripts` (passed); `make verify` (539 passed plus config, OpenAPI and Compose checks).

## Evidence files produced

No AWS workload is run by this PR, so no `docs/test/test310.md` is required.

## Boundaries

Inspection does not prove policy compliance, cost accuracy, AWS authorization, runtime health, recovery, cleanup or customer approval. It does not invoke Terraform or authorize apply. The trusted runner must later bind the inspected plan to its exact generated configuration, provider lockfile and saved-plan artifact digest.

## Follow-up work

Integrate this parser with a trusted isolated Terraform plan runner; bind outputs to immutable saved plan bytes; evaluate policy and cost; present the summary to the customer; require attributable approval of the exact plan digest before apply.
