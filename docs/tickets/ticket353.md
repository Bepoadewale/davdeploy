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
- [x] Focused tests, Ruff, full verification, clean-room proof, documentation conventions, and diff checks pass on the final code head.
- [x] Required CI passes on code/test head `94bc338`, and the latest code review has no unresolved blocking findings.
- [x] Runner, state API, role verification, plan review, and customer apply remain disabled; no AWS customer resources are changed.

## Acceptance status

The implementation is complete on draft PR #353. The policy denies IAM allow statements that use `NotAction`, denies IAM permission-management actions regardless of resource wildcarding, denies unbounded `iam:PassRole`, rejects wildcard/unverified and external-account trust principals, and denies wildcard or cross-account role assumption. Exact same-account role passing with a literal `iam:PassedToService` condition, same-account role trust, and exact same-account role assumption are surfaced for human review. Managed policy attachments other than `AdministratorAccess` are also surfaced because their policy contents are not included in the Terraform plan. The focused tests pass (83 tests), and `make verify` passes (922 tests). Final-code clean-room `make local-proof` passed in isolated worktree `/private/tmp/davdeploy-pr353-final-cleanroom` at code commit `549c0ab` (921 tests); its code is unchanged by the later safe-policy test-only addition. Documentation conventions and diff checks pass. The isolated Docker stack is stopped; its worktree and local test artifacts are retained. All seven required CI jobs passed on code/test head `94bc338` in run [43065453896](https://github.com/Bepoadewale/davdeploy/actions/runs/43065453896), and Codex review of that head found no major issues. This ticket evidence update requires its own final PR checks before merge.

## Tests / validation performed

- `uv run ruff check apps/api/src/davdeploy/generated_plan_policy.py tests/test_generated_plan_policy.py` — passed.
- `uv run pytest -q tests/test_generated_plan_policy.py` — 83 passed after adding the safe read-only policy regression.
- `make verify` — 922 passed; Ruff, Actions configuration, OpenAPI, and Docker Compose configuration checks passed. One existing Starlette/httpx deprecation warning remains.
- An earlier clean-room run at `86757b1` passed before the trust-check expansion and is superseded.
- `COMPOSE_PROJECT_NAME=davdeploy-pr353-final-cleanroom make local-proof` in a fresh worktree at `549c0ab` — local services ready, API contract and customer-plan E2E passed, demo data seeded locally, trace check passed, and all 921 tests passed. No AWS calls or customer infrastructure changes occurred. The isolated Docker stack is stopped; its worktree and generated test artifacts remain available for review.
- `GITHUB_PR_NUMBER=353 python3.12 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- All seven required PR CI jobs passed on code/test head `94bc338` in run [43065453896](https://github.com/Bepoadewale/davdeploy/actions/runs/43065453896). Codex review of commit `94bc338` found no major issues.

## Evidence files produced

The PR implementation was tested with local policy fixtures and tests only.
The later protected control-plane release is recorded in
[`test353.md`](../test/test353.md); it did not create or change customer
workloads or customer IAM roles.

## Boundaries

This is plan-level policy hardening. It does not install or attest customer IAM policies, enable the plan worker, implement pricing, approve a plan, or apply customer infrastructure. Human approval and all existing fail-closed gates remain required.

## Follow-up work

Continue the hosted plan-worker/state/pricing prerequisites and exact-cost approval. PR #318 remains closed and held for account-owner direction.

## Post-merge control-plane release

The merged policy change was deployed with the protected saved-plan workflow.
The exact plan and deployment, migration result, six Lambda identities, health
check, and still-disabled Nova runtime gates are recorded in
[`test353.md`](../test/test353.md). This release did not apply a Nova customer
plan or customer workload.
