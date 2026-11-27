# ticket536 — Deny unapproved actions on exact Nova apply resources

PR: #536 (draft; session-policy boundary hardening)
Branch: `fix/nova-apply-session-boundary-536`

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

1. Group exact plan resources by their per-resource allowed action set.
2. Add an explicit `Deny`/`NotAction` statement per action-set group, scoped
   to only those exact resource ARNs, so unapproved actions are explicitly
   denied even when an AWS resource policy names the role session.
3. Keep the existing deny for all actions on unplanned resources and retain
   the STS size limit; reject plans whose complete policy exceeds the limit.
4. Bump the session-policy version and add regression tests for single and
   multiple resources, action subsets, resource scope, grouping, and overflow.
5. Record that deterministic policy-shape tests do not replace IAM's live
   policy evaluation semantics or customer-side lifecycle evidence.

## Acceptance criteria

- [ ] Every planned resource ARN has an explicit deny for actions outside the
  action set allowed for that exact ARN.
- [ ] The deny does not block plan-allowed actions on the exact resource or
  `sts:GetCallerIdentity`.
- [ ] The existing deny for unplanned resource ARNs remains effective.
- [ ] Multiple resources with identical action sets share a deny safely; a
  resource with a different action set receives a separate scope.
- [ ] The complete serialized policy remains under 2,048 bytes or fails
  closed without issuing credentials.
- [ ] Policy versioning, artifact digests, credential contract, and worker
  checks remain consistent.
- [ ] Focused regression tests and final-head CI pass. No AWS role, workload,
  hosted control plane, Terraform state, or lock is changed.

## Acceptance status

Implementation has not started. This PR is a draft; no cloud execution or
customer workload evidence is claimed.

## Tests / validation performed

- Initial ticket conventions and `git diff --check`: pending.
- No code tests or cloud operations have been run for this package.

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

After the boundary is reviewed and merged, re-evaluate the ECS plan-policy
shape and exact IAM action/resource mapping. Complete isolated authorization
and lifecycle validation under the separate approved customer-workload gates.
