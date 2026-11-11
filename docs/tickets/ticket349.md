# ticket349 — Expose the default-off Nova broker deployment variable

PR: [#349](https://github.com/Bepoadewale/davdeploy/pull/349)
Branch: fix/nova-broker-workflow-input-349
Base: main

## Problem / goal

Add the missing explicit GitHub environment input for the Nova plan credential broker to the production Terraform plan workflow. Keep the default false so deployment cannot enable broker credentials implicitly.

## Current repo state

The backend control-plane change is merged in #348. The GitHub Terraform workflow has explicit mappings for the other Nova feature gates but not `enable_nova_plan_credential_broker`.

## Research / references used

- `.github/workflows/terraform-plan.yml`
- `infrastructure/terraform/serverless-control-plane/variables.tf`
- `infrastructure/terraform/serverless-control-plane/main.tf`
- `scripts/check_actions_configuration.py`

## Work planned for the PR

- Map the protected GitHub environment variable `NOVA_PLAN_CREDENTIAL_BROKER_ENABLED` to `TF_VAR_enable_nova_plan_credential_broker`, defaulting to `false`.
- Classify that public feature-gate variable in the Actions configuration checker.
- Preserve separate gates for plan-role verification and the plan-only runner.

## Acceptance criteria

- [x] The workflow maps the broker variable with a default of `false`.
- [x] The Actions checker recognizes the new non-secret configuration variable.
- [x] Terraform validation still requires role verification and the broker before the plan-only runner can be enabled.
- [ ] Required final-head CI passes.
- [ ] This ticket records the final commit and evidence before the PR is marked review-ready.

## Acceptance status

Implementation and local validation are complete. Implementation commit `d711cf2` passed all seven required CI jobs in run `43035050359`; current-head Codex review of `d711cf2` found no major issues. Final-head CI after this evidence update remains pending.

## Tests / validation performed

- `python scripts/check_actions_configuration.py` passed.
- `make terraform-validate` passed across all configured roots.
- `terraform -chdir=infrastructure/terraform/serverless-control-plane fmt -check -recursive` passed.
- `python scripts/check_doc_conventions.py` passed.
- `git diff --check` passed.
- PR CI run `43035050359` passed all seven jobs on implementation commit `d711cf2`; the required checks will rerun for the evidence update commit.
- Current-head Codex review of `d711cf2` found no major issues.
- No AWS plan/apply was run for this PR.

## Evidence files produced

- No runtime evidence file is required: the PR changes only protected workflow input mapping and static configuration classification. No AWS calls, customer credentials, plan, or resource mutations are performed.

## Boundaries

This PR only exposes the protected variable. It does not set the environment variable, enable the broker, turn on role verification or the runner, issue credentials, or run a hosted plan.

## Follow-up work

The broker and plan worker remain disabled until role verification, customer authorization, pricing and the protected environment variable are reviewed and enabled through a separate plan.
