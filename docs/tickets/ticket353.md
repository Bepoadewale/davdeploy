# ticket353 — fail closed on IAM escalation in generated Terraform plans

PR: [#353](https://github.com/Bepoadewale/davdeploy/pull/353) (draft)
Branch: `feat/nova-iam-plan-escalation-353`
Base: `main`

## Problem / goal

The actual-plan policy already rejects wildcard IAM permissions and wildcard trust, but IAM escalation can still be hidden behind a `NotAction` statement or an exact-resource permission-management/pass-role grant. Inspect generated plan policy documents deterministically so dangerous delegation cannot appear safe just because its resource ARN is narrow.

## Current repo state

Backend `main` is `334865159a0a6f7dcf155dc7595f4cc455aea679` (PR #352). `generated_plan_policy.py` parses IAM policy/trust documents from actual Terraform plan JSON and rejects selected wildcard patterns; the Nova plan runner, role verification, state API, and plan review remain disabled. Complete regional pricing is unavailable and PR #318 remains held. This change must not enable any customer plan or apply path.

## Research / references used

- AWS IAM PassRole guidance: https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_passrole.html
- AWS IAM condition keys: https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_iam-condition-keys.html
- AWS policy evaluation logic: https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic_policy-eval-denyallow.html

## Work planned for the PR

- Treat allow statements using `NotAction` as unsafe in generated IAM policies.
- Detect IAM permission-management actions and role delegation independently of whether the resource ARN contains a wildcard.
- Fail closed on broad/unconditioned `iam:PassRole`; require a literal `iam:PassedToService` condition and exact resource scope before allowing the proposal to proceed to explicit human review.
- Add regressions for exact-resource escalation, wildcard/unknown pass-role conditions, narrowly conditioned pass-role review, and safe read-only policies.
- Preserve current customer feature gates and prove no hosted execution is enabled.

## Acceptance criteria

- [ ] Actual generated-plan IAM policy analysis fails closed for unsafe `NotAction`, permission-management, and role-delegation constructs.
- [ ] A tightly scoped pass-role grant is surfaced for human review; broad or unconditioned pass-role grants are denied.
- [ ] Regression tests cover positive and negative policy documents and preserve safe policies.
- [ ] Focused tests, Ruff, full verification, clean-room proof if required by the execution-security change, documentation conventions, and diff checks pass.
- [ ] Required final-head CI passes and the current-head code review has no unresolved blocking findings.
- [ ] Runner, state API, role verification, plan review, and customer apply remain disabled; no AWS customer resources are changed.

## Acceptance status

Implementation has not started. This PR is a draft bootstrap.

## Tests / validation performed

None yet; implementation is not started.

## Evidence files produced

A runtime evidence file will be added only if a customer workload or AWS mutation is performed. This PR is intended to use local policy fixtures and tests only.

## Boundaries

This is plan-level policy hardening. It does not install or attest customer IAM policies, enable the plan worker, implement pricing, approve a plan, or apply customer infrastructure. Human approval and all existing fail-closed gates remain required.

## Follow-up work

Continue the hosted plan-worker/state/pricing prerequisites and exact-cost approval. PR #318 remains closed and held for account-owner direction.
