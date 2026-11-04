# Ticket 306: Nova-led infrastructure generation decision

## Goal

Record the proposed architecture for using Nova to generate composed AWS
infrastructure through one Terraform execution path, and map the existing
catalogue and Terraform roots to representative evidence and explicit gaps.
Keep the full implementation strategy and access notes in the local goal file.

## Current state

Backend main at start: `277fb925349a2b167249827d165491ffd0c93f48`.
Backend repo is private. The local branch includes the untracked protected file
`--only-show-errors`; it must remain untouched. Nova generation exists in
`apps/api/src/davdeploy/terraform_generation.py`, but `service.py` keeps its
result at `PLAN_ONLY_NOT_APPLIED`. It is not connected to the hosted executor.
Current matrix identifies 26 architecture entries and 30 Terraform roots.

## References and research

- AWS Nova structured output: https://docs.aws.amazon.com/nova/latest/nova2-userguide/advanced-prompting-techniques.html
- Terraform provider schema: https://developer.hashicorp.com/terraform/cli/commands/providers/schema
- Terraform saved plans: https://developer.hashicorp.com/terraform/cli/commands/plan
- Bedrock guardrail prompt attack scope: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-prompt-attack.html
- Existing status: `docs/product/EXECUTION_READINESS_MATRIX.md` and
  `docs/product/COMPOSED_EXECUTION_GOAL.md`.

## Work

- Record Nova's responsibilities and deterministic execution/security boundary.
- Define generate, validate, plan, approve, apply, observe, recover and cleanup
  at the architecture level.
- Map all 26 catalogue entries and 30 Terraform roots to scenario evidence or
  a documented test gap.
- Preserve the original product outcome and require evidence beyond Terraform
  resource creation.
- Keep this technical record distinct from the private local goal document.

## Acceptance

- [x] ADR states this is proposed, not implemented or certified.
- [x] It records one generic Terraform execution path and bounded Nova repair.
- [x] All catalogue entries and implementation roots are enumerated.
- [x] Eight application scenarios and targeted gaps remain in scope.
- [x] Approval, tenant, IAM, state, secrets, recovery and cleanup controls are
  specified at the architecture level.
- [x] The local-only strategy and operational details are not copied here.
- [ ] Required PR checks pass and review is complete.

## Validation and evidence

Documentation-only change. No runtime test or `docs/test/test306.md` is
required. Manually cross-checked the enumerated catalogue and Terraform roots
against `docs/product/EXECUTION_READINESS_MATRIX.md`. No infrastructure was
created or destroyed in this PR. No runtime behavior changed.

## Boundaries and follow-up

This ADR does not enable generic execution, deploy customer workloads, change
IAM, authorize arbitrary AWS requests, or certify the eight scenarios. Next
implementation work should deliver the typed resource contract, deterministic
schema/plan validation and the first hosted composed lifecycle. Do not publish
the local goal document or its credential-location notes.
