# ticket271 — Reconcile deployed execution state and map renderer readiness

PR: pending

Branch: `docs/execution-readiness-matrix`

## Problem / goal

Record verified hosted deployment status and map architecture modules and Terraform implementations to customer renderer support and evidence. Keep planned, isolated, hosted, and deployed capabilities distinct.

## Current repo state

PR #270 is merged. Its production saved plan applied as workflow run `41671744510` for commit `93c895e6e40e80f20b71a6f3a21e3186ca63d576`: 0 added, 7 changed, 0 destroyed. The workflow confirmed database migrations. Live AWS showed `davdeploy-api` active with a successful update and the CodeBuild project buildspec invoking `scripts/customer-workload-dispatcher.sh`.

CodeBuild dispatch still allows only one enabled renderer, `aws-managed-application` (App Runner). The isolated `aws-serverless-api` renderer remains disabled for hosted customer execution. Multiple-module runs fail closed. Existing service-level AWS certifications do not prove a composed hosted customer deployment.

## Research / references used

- `PROJECT_STATUS.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/product/CURRENT_STATE_AUDIT.md`
- `CODEX_BACKLOG.md`
- `apps/api/src/davdeploy/module_catalogue.py`
- `apps/api/src/davdeploy/module_implementations.py`
- `apps/api/src/davdeploy/module_renderers.py`
- PR #270 and Terraform apply run `41671744510`

## Current repo state details

PR #270 has deployed the typed dispatcher, but only App Runner has a hosted renderer. The isolated serverless API renderer remains disabled, and composed execution remains unavailable.

## Work planned for the PR

- Correct claims contradicted by current deployed AWS and GitHub workflow evidence.
- Add a status matrix for all catalogue modules and Terraform implementation entries, linking renderers, lifecycle support, service-level evidence, hosted evidence, and gaps.
- Record exact current dispatcher and customer execution limits without changing runtime behavior.
- Keep unverified integrations visibly incomplete.

## Acceptance criteria

- [ ] Every one of the 26 architecture catalogue entries appears in the matrix.
- [ ] Every one of the 30 Terraform implementation registry entries is mapped or identified as unmapped.
- [ ] Isolated certification and hosted customer-runner certification are separate columns/states.
- [ ] PR #270 deployment and migration completion are recorded with evidence.
- [ ] Stale status documents agree with verified live state and preserve remaining blockers.
- [ ] Documentation conventions and diff checks pass.

## Tests / validation performed

Read-only evidence inspected: GitHub PR #270 merged; Terraform run #41671744510 succeeded; workflow logs showed 0/7/0 resource actions and successful migrations; AWS Lambda configuration showed active/successful; CodeBuild buildspec showed typed dispatcher invocation. Direct unauthenticated API returned 401, which requires edge/auth-aware verification before interpreting API health. No customer workload was created by this documentation PR.

`GITHUB_PR_NUMBER=271 python3 scripts/check_doc_conventions.py` and `git diff --check` are the required checks before review.

## Acceptance status

Documentation changes are implemented; final convention checks and PR CI are pending.

## Evidence files produced

`docs/product/EXECUTION_READINESS_MATRIX.md`. This documentation-only PR creates no customer workload, so no `docs/test/test271.md` is required.

## Boundaries

Documentation only. This PR does not enable renderers, execute a customer workload, or change AWS resources. Do not remove or downgrade catalogue scope to make coverage appear complete.

## Follow-up work

Complete durable hosted execution for Lambda/API, prove typed composition, then implement and certify renderer families through the real CodeBuild path. Replace the frontend App Runner-specific execution states only when provider-neutral lifecycle behavior exists in the API.
