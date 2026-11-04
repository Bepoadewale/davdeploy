# ticket306 Nova-led infrastructure execution decision

Goal: establish a technical decision and finite evidence coverage map for Nova generated AWS infrastructure through one Terraform execution path.

Current state: backend main was 277fb925. Nova generation is plan-only and is not connected to hosted execution. The current matrix records 26 architecture modules and 30 Terraform implementation roots. No runtime capability changes are included in PR #306.

Research: AWS Nova structured output https://docs.aws.amazon.com/nova/latest/nova2-userguide/advanced-prompting-techniques.html; Terraform provider schemas https://developer.hashicorp.com/terraform/cli/commands/providers/schema; saved plans https://developer.hashicorp.com/terraform/cli/commands/plan; Bedrock guardrail scope https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-prompt-attack.html.

Work: record Nova versus deterministic responsibilities, generated proposal to saved plan lifecycle, 26 module and 30 implementation mappings, eight representative application scenarios, explicit security and evidence boundaries. Keep full strategy and operational notes local.

Acceptance:
- [x] Proposed architecture is distinguished from deployed functionality.
- [x] All 26 catalogue entries and 30 Terraform roots are enumerated.
- [x] Eight scenarios and targeted coverage gaps are recorded.
- [x] Approval, tenant isolation, policy, secret, recovery and cleanup boundaries are specified.
- [x] No local goal, credential-location notes or private access information are committed.
- [ ] Required CI and review pass.

Validation: documentation-only. No runtime test, test evidence file, AWS mutation or customer execution is required. CI documentation convention caught the missing ticket marker; this update supplies the required PR-numbered ticket.

Boundaries: this ADR does not implement or certify generated execution, change IAM, enable renderers or authorize arbitrary AWS actions. Follow-up starts with a typed generation contract, deterministic validation, actual plan inspection and hosted workload evidence.
