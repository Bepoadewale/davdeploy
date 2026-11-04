# ticket306 Nova-led infrastructure execution decision

PR: #306
Branch: docs/nova-execution-decision

## Problem / goal

Record the technical decision to let Nova generate composed AWS infrastructure through one generic Terraform execution path, and map the existing finite capability scope to evidence and gaps.

## Current repo state

Backend main at start was 277fb925. NovaTerraformGenerator is plan-only and is not connected to hosted execution. Existing readiness documentation records 26 architecture entries and 30 Terraform roots. No runtime capability change is included.

## Research / references used

- Nova structured output: https://docs.aws.amazon.com/nova/latest/nova2-userguide/advanced-prompting-techniques.html
- Terraform provider schema: https://developer.hashicorp.com/terraform/cli/commands/providers/schema
- Terraform saved plans: https://developer.hashicorp.com/terraform/cli/commands/plan
- Bedrock guardrail scope: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-prompt-attack.html

## Work planned for the PR

Record model versus deterministic responsibilities, proposed lifecycle from generation to cleanup, mapping for all 26 catalogue modules and 30 Terraform roots, eight application scenarios and additional known coverage gaps. Keep the complete strategy and access notes local.

## Acceptance criteria

- [x] Proposed status is distinct from deployed capability.
- [x] 26 catalogue entries and 30 Terraform roots are mapped.
- [x] Eight scenario names and targeted gaps are included.
- [x] Approval, tenant, policy, credentials, recovery and cleanup boundaries are specified.
- [x] No local goal or operational access notes are copied into the repository.
- [ ] Required CI and review pass.

## Acceptance status

Documentation is complete. CI and review are pending. No runtime capability is claimed.

## Tests / validation performed

Documentation-only change. No runtime test or customer workload evidence is required. CI's documentation convention check identified the missing PR-numbered ticket; this file satisfies that requirement.

## Evidence files produced

No customer workload or AWS test was performed. No docs/test/test306.md is required for this documentation-only PR.

## Boundaries

This decision does not connect Nova to Terraform apply, certify any deployment, change IAM, enable renderers or authorize arbitrary AWS access.

## Follow-up work

Implement and verify the typed generation contract, deterministic provider and actual-plan validation, saved-plan-bound approval, generic hosted execution, application health evidence, recovery and exact cleanup. Keep the full implementation goal local.
