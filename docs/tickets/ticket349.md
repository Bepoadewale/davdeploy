# PR #349 — Expose the default-off Nova broker deployment variable

## Goal

Add the missing explicit GitHub environment input for the Nova plan credential broker to the production Terraform plan workflow. Keep the default false so deployment cannot enable broker credentials implicitly.

## Current state

This is the initial PR bootstrap commit. The backend control-plane change is merged in #348. The GitHub Terraform workflow has explicit mappings for the other Nova feature gates but not enable_nova_plan_credential_broker.

## Research and references

- .github/workflows/terraform-plan.yml
- infrastructure/terraform/serverless-control-plane/variables.tf
- infrastructure/terraform/serverless-control-plane/main.tf

## Acceptance criteria

- [ ] Add TF_VAR_enable_nova_plan_credential_broker mapped from the protected GitHub environment variable NOVA_PLAN_CREDENTIAL_BROKER_ENABLED, defaulting to false.
- [ ] Confirm the runner and role-verification flags remain separately controlled and Terraform validations still require the broker before enabling the plan-only runner.
- [ ] Run the required workflow/configuration and Terraform validation checks; add final-head CI evidence.
- [ ] Update this ticket with exact PR number, commit, and test results before marking review-ready.

## Validation and evidence

Bootstrap only; no runtime or Terraform validation has been run yet. No AWS calls or resource changes are part of this PR.

## Boundaries

This is only the deployment input mapping. It does not set the environment variable, enable the broker, turn on role verification or the runner, issue credentials, or run a hosted plan.

## Follow-up

The broker and plan worker remain disabled until role verification, customer authorization and the explicit protected environment variable are reviewed and enabled as part of a separate plan.
