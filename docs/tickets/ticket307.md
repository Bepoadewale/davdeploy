# ticket307 Typed Nova deployment graph contract

PR: #307
Branch: feat/nova-deployment-contract

## Problem / goal

Define the strict resource graph accepted from Nova before deterministic validation and Terraform generation.

## Current repo state

Generated resources previously used arbitrary argument dictionaries with basic forbidden-field checks. Nova generation is plan-only and not connected to hosted execution. The 26-entry catalogue and 30 Terraform roots are mapped in the readiness matrix.

## Research / references used

- Nova structured output: https://docs.aws.amazon.com/nova/latest/nova2-userguide/advanced-prompting-techniques.html
- Terraform provider schema: https://developer.hashicorp.com/terraform/cli/commands/providers/schema
- Existing typed module ports: apps/api/src/davdeploy/module_ports.py

## Work planned for the PR

Add strict models for proposal, resources, typed references, declared outputs, requirements, health assertions, recovery needs and cost assumptions. Validate graph identities, dependencies and references before runner dispatch.

## Acceptance criteria

- [x] Versioned proposal and resource graph models.
- [x] Reject duplicate IDs/addresses, invalid dependencies, unresolved references, type mismatch and dependency cycles.
- [x] Reject raw Terraform expressions and sensitive/execution authority fields.
- [x] Carry context digest, source revision, costs, health and recovery requirements.
- [ ] Required CI passes and review is complete.

## Acceptance status

Local implementation and focused tests pass. Hosted execution is not connected. This contract does not authorize a deployment.

## Tests / validation performed

Ruff passed for changed files. .venv/bin/python -m pytest -q tests/test_generated_deployment_contract.py tests/test_terraform_generation.py: 13 passed. No AWS operations.

## Evidence files produced

No customer workload evidence. No test<PR_NUMBER>.md is required because this PR creates no customer workload and changes no runtime cloud environment.

## Boundaries

Schema/model validation is not provider validation, policy authorization, trustworthy cost, IAM authority, customer approval or AWS evidence. No runner is enabled by this PR.

## Follow-up work

Integrate the typed contract with Nova generation, trusted Terraform JSON generation, provider schemas, actual-plan policy checks and the existing hosted lifecycle. Keep the full goal and access details local.
