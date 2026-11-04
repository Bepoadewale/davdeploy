# Ticket 307: Typed Nova deployment graph contract

## Goal

Define the strict resource graph accepted from Nova before deterministic
validation and Terraform generation.

## Current state

Previously, generated resources used arbitrary argument dictionaries with
basic forbidden-field checks. The result was plan-only and had no structured
dependency, health, recovery or cost assumption contract. This PR adds a
versioned typed boundary; it does not connect Nova to hosted apply.

## References

- Nova structured output: https://docs.aws.amazon.com/nova/latest/nova2-userguide/advanced-prompting-techniques.html
- Terraform provider schema: https://developer.hashicorp.com/terraform/cli/commands/providers/schema
- Existing typed ports: apps/api/src/davdeploy/module_ports.py.

## Work and acceptance

- [x] Versioned proposal, resource, output, reference and requirement models.
- [x] Reject duplicate resource IDs/addresses, unresolved references, mismatched output types and dependency cycles.
- [x] Reject raw Terraform expressions and sensitive/execution authority fields from resource arguments.
- [x] Carry source/context digest, cost assumptions, health assertions and recovery requirements.
- [x] Focused tests cover valid graph and malformed, cyclic, unresolved references, mismatched types and unsafe inputs.
- [ ] Required checks pass and review is complete.

## Validation and evidence

Runnable Python change. .venv/bin/python -m pytest -q tests/test_generated_deployment_contract.py tests/test_terraform_generation.py passed: 13 tests. No AWS resources or customer workloads are involved.

## Boundaries and follow-up

Passing this model is not provider-schema validation, policy approval, cost
validation, IAM authority or evidence of deployable infrastructure. Next work
must integrate it with Nova generation, deterministic Terraform JSON output,
actual plan inspection and the existing hosted lifecycle without enabling
unvalidated execution. Keep the full goal and operational notes local.
