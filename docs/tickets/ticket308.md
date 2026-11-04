# ticket308 Integrate Nova output with the typed proposal contract

PR: #308
Branch: feat/nova-contract-generation

## Problem / goal

Move the plan-only Nova proposal path from its legacy resource schema into the shared versioned graph contract while keeping deterministic provenance and trusted Terraform reference generation.

## Current repo state

PR #307 added strict contract models and trusted reference compilation. The existing NovaTerraformGenerator still asks Nova for a legacy untyped resource list and renders it through the old generator. There is no generic apply path.

## Research / references used

- Nova structured output: https://docs.aws.amazon.com/nova/latest/nova2-userguide/advanced-prompting-techniques.html
- Terraform provider schema: https://developer.hashicorp.com/terraform/cli/commands/providers/schema
- Existing generator: apps/api/src/davdeploy/terraform_generation.py

## Work planned for the PR

Have Nova emit typed graph content; derive source/context provenance and customer requirements in trusted code; compile only validated references into Terraform JSON; keep result explicitly plan-only.

## Acceptance criteria

- [x] Nova structured response uses the versioned graph resource/reference schema.
- [x] Source revision, target region and context digest come from trusted inputs and are checked.
- [x] Terraform JSON references are emitted only by trusted deterministic code.
- [x] Existing API remains explicitly plan-only and no execution gate changes.
- [x] Focused and full local verification pass; required CI pending.

## Acceptance status

Implementation, focused tests and full local verification pass. CI and review are pending.

## Tests / validation performed

make verify passed: action configuration, Ruff, full pytest (520 passed), OpenAPI snapshot and Docker Compose configuration. Focused tests also passed: 87. One existing Starlette/httpx deprecation warning. No live Nova call or AWS resources were used.

## Evidence files produced

No customer workload is exercised; no docs/test evidence file is required.

## Boundaries

This PR does not validate AWS provider schemas, policy, prices, IAM, Terraform actual plans, approval binding or hosted execution. Nova output remains non-executable until later packages connect all those gates.

## Follow-up work

Add provider schema and Terraform plan validation, policy checks on the actual plan, approved saved-plan binding and generic hosted execution. Keep the full goal and operational access details local.
