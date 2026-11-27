# ticket536 — Deny unapproved actions on exact Nova apply resources

PR: #536 (merged 2026-11-27 as `c58a2d4a6f3ce45712641e47a4aec52f8181d42b`)
Branch: `fix/nova-apply-session-boundary-536` (deleted after merge)

## Problem / goal

The Nova apply session policy allows only plan actions on exact resource ARNs,
and denies all actions on resources outside the plan. However, AWS may let a
same-account resource policy grant directly to the assumed role session,
bypassing an implicit session-policy deny. The current session policy does not
explicitly deny actions outside the plan on a resource ARN that is in the
plan's resource set. Add an explicit per-resource action deny while preserving
the existing cross-resource deny and the 2,048-byte fail-closed limit.

## Current repo state

- Backend `main` is `95ce2aa76cbefedf94b5949866f7d29ecf4cd995`.
- `build_nova_apply_access_policy` emits exact-resource allows and one
  `Deny`/`NotResource` statement for resources outside the plan.
- The fixed customer apply role has a maximum action deny, but its action set
  is the union of supported services and operations, not the exact actions for
  this plan.
- The builder now emits a per-resource `Deny`/`NotAction` statement for each
  exact plan action set, groups identical sets, retains the out-of-plan
  resource deny, and versions the policy as `nova-apply-plan-scope.v2`.
- PR #519 remains a draft renderer branch and is not deployed. Its IAM review
  and customer lifecycle gates remain open.
- The Terraform monitor currently reports 75 terminal runs and no active
  Terraform process. No AWS mutation is part of this package.

## Research / references used

- AWS [IAM policy evaluation](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html)
  documents that a same-account resource policy can grant directly to an
  assumed role session beyond an implicit deny in its session policy.
- AWS [IAM permissions boundaries](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html)
  documents the different evaluation behavior for role ARNs and role-session
  ARNs.
- [`nova_apply_access.py`](../../apps/api/src/davdeploy/nova_apply_access.py)
  builds the plan-bound session policy.
- [`test_nova_apply_access.py`](../../tests/test_nova_apply_access.py)
  covers current allow and deny documents.

## Work planned for the PR

1. [x] Group exact plan resources by their per-resource allowed action set.
2. [x] Add an explicit `Deny`/`NotAction` statement per action-set group, scoped
   to only those exact resource ARNs, so unapproved actions are explicitly
   denied even when an AWS resource policy names the role session.
3. [x] Keep the existing deny for all actions on unplanned resources and retain
   the STS size limit; reject plans whose complete policy exceeds the limit.
4. [x] Bump the session-policy version and add regression tests for single and
   multiple resources, action subsets, resource scope, grouping, and overflow.
5. [x] Record that deterministic policy-shape tests do not replace IAM's live
   policy evaluation semantics or customer-side lifecycle evidence.

## Acceptance criteria

- [x] Every planned resource ARN has an explicit deny for actions outside the
  action set allowed for that exact ARN.
- [x] The deny does not block plan-allowed actions on the exact resource or
  `sts:GetCallerIdentity`.
- [x] The existing deny for unplanned resource ARNs remains effective.
- [x] Multiple resources with identical action sets share a deny safely; a
  resource with a different action set receives a separate scope.
- [x] The complete serialized policy remains under 2,048 bytes or fails
  closed without issuing credentials.
- [x] Policy versioning, artifact digests, credential contract, and worker
  checks remain consistent.
- [x] Full Python test suite, focused regression coverage, lint, documentation
  conventions, and `git diff --check` pass.
- [x] No AWS role, workload, hosted control plane, Terraform state, or lock is
  changed.
- [x] Final-head GitHub Actions checks pass.
- [x] Complete the repository-required clean-room cycle for this authorization
  change.
- [x] PR #536 merged after all seven checks passed; source branch deleted.

## Acceptance status

The per-resource explicit-deny behavior and v2 fail-closed policy version are
implemented. The compact mixed S3/SQS/DynamoDB fixture correctly fails closed
at 2,641 bytes; a smaller mixed SQS/DynamoDB policy remains within the limit.
All seven final-head CI checks passed on head `5689dfaf` in run
`45933859275`, including `local-e2e` on a fresh GitHub runner. PR #536 merged
to source `main` as `c58a2d4a6f3ce45712641e47a4aec52f8181d42b`. A separate
fresh local worktree passed bootstrap, smoke, customer-plan
end-to-end, simple/complex/degraded/Day-2 demos, policy and readiness failures,
trace verification, full lint, and all 2,021 tests. Its project containers were
stopped; generated local files and the test database volume were retained.
The renderer remains disabled. The source merge did not update a live AWS role
or prove AWS policy evaluation or customer lifecycle execution.

## Tests / validation performed

- `uv run --frozen --extra dev python -m pytest tests/test_nova_apply_access.py tests/test_nova_apply_contract.py tests/test_nova_apply_clients.py tests/test_nova_apply_role_profile.py tests/test_nova_apply_codebuild.py -q`: 53 passed.
- `uv run --frozen --extra dev python -m pytest -q`: 2,021 passed, 1 Starlette deprecation warning.
- `uv run --frozen --extra dev ruff check apps/api/src tests scripts`: passed.
- `GITHUB_PR_NUMBER=536 python3 scripts/check_doc_conventions.py`: passed.
- `git diff --check`: passed.
- Fresh local worktree `/private/tmp/davdeploy-nova-apply-session-boundary-536-cleanroom`
  at `a41db8d3fe1a455a83ae9de27a30329e4ea60491`: `COMPOSE_PROJECT_NAME=davdeploy-pr536-cleanroom make local-proof`
  passed; required demo/failure targets passed; stack containers were stopped
  without removing the named volume or generated files.
- Final-head GitHub Actions run
  [45933859275](https://github.com/Bepoadewale/davdeploy/actions/runs/45933859275):
  all seven checks passed, including `local-e2e` and its fresh-runner cleanup.
- Merge commit: `c58a2d4a6f3ce45712641e47a4aec52f8181d42b`.
- No AWS calls, role changes, Terraform operations, or control-plane access.

## Evidence files produced

No `docs/test/test536.md` is required. This package changes policy-generation
code and deterministic tests only; it does not run a customer workload.

## Boundaries

- Do not mutate the hosted control plane, customer IAM roles, AWS workloads,
  Terraform state, or lock resources.
- Preserve protected local files, existing audit artifacts, worktrees, and
  SageMaker lineage evidence.
- Keep PR #519's renderer disabled; this package does not authorize Nova
  dispatch or an apply.

## Follow-up work

Re-evaluate the ECS plan-policy shape and exact IAM action/resource mapping,
then complete isolated authorization and lifecycle validation under the
separate approved customer-workload gates. Before that work, determine whether
the policy-size limit needs a narrower supported service/action set or a
different supported credential strategy; oversized plans must continue to
fail closed.
