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
- Detect IAM permission-management actions, unapproved trust principals, and role delegation independently of whether the resource ARN contains a wildcard.
- Fail closed on broad/unconditioned `iam:PassRole`; require a literal `iam:PassedToService` condition and exact resource scope before allowing the proposal to proceed to explicit human review.
- Add regressions for exact-resource escalation, external-account and `NotPrincipal` trust, wildcard/unknown pass-role conditions, narrowly conditioned pass-role review, and safe read-only policies.
- Preserve current customer feature gates and prove no hosted execution is enabled.

## Acceptance criteria

- [x] Actual generated-plan IAM policy analysis fails closed for unsafe `NotAction`, permission-management, and role-delegation constructs.
- [x] A tightly scoped pass-role grant is surfaced for human review; broad or unconditioned pass-role grants are denied.
- [x] Regression tests cover positive and negative policy documents and preserve safe policies.
- [ ] Focused tests, Ruff, full verification, clean-room proof, documentation conventions, and diff checks pass on the final code head.
- [ ] Required final-head CI passes and the current-head code review has no unresolved blocking findings.
- [x] Runner, state API, role verification, plan review, and customer apply remain disabled; no AWS customer resources are changed.

## Acceptance status

The implementation is in progress on draft PR #353, pending final clean-room proof, CI, and review. The policy denies IAM allow statements that use `NotAction`, denies IAM permission-management actions regardless of resource wildcarding, denies unbounded `iam:PassRole`, rejects wildcard/unverified and external-account trust principals, and denies wildcard or cross-account role assumption. Exact same-account role passing with a literal `iam:PassedToService` condition, same-account role trust, and exact same-account role assumption are surfaced for human review. Managed policy attachments other than `AdministratorAccess` are also surfaced because their policy contents are not included in the Terraform plan. The expanded focused tests pass (82 tests) and current `make verify` passes (921 tests); the isolated clean-room run on this expanded code is pending. Hosted CI and review are pending.

## Tests / validation performed

- `uv run ruff check apps/api/src/davdeploy/generated_plan_policy.py tests/test_generated_plan_policy.py` — passed.
- `uv run pytest -q tests/test_generated_plan_policy.py` — 82 passed after expanding trust checks.
- `make verify` — 921 passed; Ruff, Actions configuration, OpenAPI, and Docker Compose configuration checks passed. One existing Starlette/httpx deprecation warning remains.
- An earlier clean-room `COMPOSE_PROJECT_NAME=davdeploy-pr353-cleanroom make local-proof` at `86757b1` passed before the trust-check expansion; it is superseded for final-head evidence. The isolated Docker stack was stopped and its worktree/local test artifacts retained.
- Final-code clean-room proof, documentation convention checks, and diff checks are pending.
- `GITHUB_PR_NUMBER=353 python3.12 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Clean-room verification and hosted CI are pending.

## Evidence files produced

A runtime evidence file will be added only if a customer workload or AWS mutation is performed. This PR is intended to use local policy fixtures and tests only.

## Boundaries

This is plan-level policy hardening. It does not install or attest customer IAM policies, enable the plan worker, implement pricing, approve a plan, or apply customer infrastructure. Human approval and all existing fail-closed gates remain required.

## Follow-up work

Continue the hosted plan-worker/state/pricing prerequisites and exact-cost approval. PR #318 remains closed and held for account-owner direction.
