# ticket539 — Integrate current main into the Nova ECS renderer branch

PR: #539 (draft; merge current main into PR #519's feature branch)
Branch: `chore/sync-main-into-renderer-519-539`
Base: `feat/ecs-express-renderer-519` (PR #519)

## Problem / goal

PR #519's branch was based on an older `main` and became conflicting after
Nova apply session-policy hardening and handoff reconciliation merged. Bring
current main into the feature branch through a reviewed PR, preserving the
current main handoff document and running the full repository checks on the
combined tree. The renderer must remain disabled.

## Current repo state

- Backend `main`: `c714fcb9686653c8e3ee36a334171b9deb4b92f3` (PR #538).
- PR #519 feature branch before this integration: #535 merge commit
  `65423bd073871d446a151fe2d1b347d336e67305`.
- PR #519 was conflicting with main; merging main brought 27 commits and
  resolved the handoff conflict using the current main version.
- PR #536's session-policy change is source-only and is not live in AWS.
- PR #519's renderer remains disabled; no AWS, Terraform, or hosted runtime
  mutation is included.

## Research / references used

- [Composed execution goal handoff](../product/COMPOSED_EXECUTION_GOAL.md)
- PR #519 and current PR #538 merge state.
- Repository-required CI workflow and validation jobs in
  [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml).

## Work planned for the PR

1. Merge `origin/main` into the PR #519 feature branch in an isolated branch.
2. Resolve the Nova handoff document using current main's reconciled status.
3. Validate documentation conventions and complete all seven CI jobs.
4. Keep the renderer and hosted control plane unchanged.

## Acceptance criteria

- [x] Current main is merged into the candidate feature branch.
- [x] The handoff conflict is resolved in favor of current main's status.
- [ ] All seven required CI checks pass on the final PR head.
- [ ] GitHub reports clean mergeability into the #519 feature branch.
- [x] No AWS, Terraform, hosted control-plane, or workload mutation occurs.
- [x] PR #519 remains a draft and its renderer remains disabled.

## Acceptance status

The candidate branch merges current main and resolves the handoff conflict.
This is branch integration only; CI is pending. It does not deploy or authorize
the renderer, prove AWS IAM evaluation, or establish Nova customer-workload
lifecycle evidence.

## Tests / validation performed

- `git merge --no-ff origin/main` — merged the current main line; the only
  conflict was `docs/product/COMPOSED_EXECUTION_GOAL.md`, resolved using the
  current main version.
- Final-head GitHub Actions validation is pending.
- No cloud calls or Terraform operations were run.

## Evidence files produced

No `docs/test/test539.md` is required. This is a source-branch integration PR
and performs no customer workload test.

## Boundaries

- Merge this PR only into PR #519's feature branch, never directly into main.
- Keep the hosted control plane, Terraform state/locks, and customer resources
  untouched.
- Preserve PR #519's renderer-disabled default and all authorization/cost gates.

## Follow-up work

After integration, reassess PR #519's effective runner permissions,
project-scoped remote-state lifecycle, approval-bound pricing, and isolated
Nova lifecycle gates. Resolve those separately before making the renderer
review-ready.
