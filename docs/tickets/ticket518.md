# ticket518 — Reconcile Nova status after PR #517

PR: #518
Branch: `docs/nova-status-through-517`

## Problem / goal

Refresh the durable Nova status, backlog, and capability-evidence crosswalk against merged backend PR #517, the currently deployed control-plane version, and the exact hosted acceptance work still outstanding. This is a documentation-only reconciliation; it does not enable a runner or assert customer deployment readiness.

## Current repo state

- Backend `main` is `1453a5efdffbbbf7f7853b7ccfa71903a231bb96`, the squash merge for PR #517.
- PR #517 added backward-compatible private public-IP configuration for Batch Fargate and a bounded private endpoint validation root. Its suffix-`b` same-account test job succeeded with exit code 0 and emitted the expected CloudWatch marker; its exact resources were destroyed and independently checked absent. Suffix `a`'s queue-cleanup failure and retained inactive job-definition evidence remain documented in `docs/test/test517.md`.
- The hosted Lambda remains on its previously deployed code package: `CodeSha256=GL+7py0mhfOeY0RcD/BC7RZ0cWS+buxedxhrwtNzps0=`. A read-only check in account `654654474502`, region `us-east-1`, returned `/healthz` HTTP 200. This confirms control-plane health only.
- The Terraform run monitor has 75 records and no active operation. No hosted workspace admin session or verified customer connection has produced a hosted Nova plan. No Nova customer workload has been applied, operated, or certified.

## Research / references used

- PR #517: https://github.com/Bepoadewale/davdeploy/pull/517
- Per-run Batch evidence: `docs/test/test517.md`
- Capability crosswalk: `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- Current hosted/source status: `PROJECT_STATUS.md`, `docs/IMPLEMENTATION_STATUS.md`, and `CODEX_BACKLOG.md`
- The local-only Nova specification remains in `/Users/adewale/Projects/DAVDEPLOY_NOVA_SESSION_PROMPT.md`; it must not be copied into this repository.

## Work planned for the PR

1. Update the source/deployed version snapshots through PR #517 while keeping the hosted deployment version distinct from backend `main`.
2. Reconcile the Batch and private-network rows with the exact direct same-account result in `test517.md`, including the suffix-`a` failure, suffix-`b` success, teardown, retained AWS history, and evidence limits.
3. Keep the 26 architecture entries and 30 Terraform roots intact; preserve unsupported/unpriced gaps and state explicitly that PR #517 is not Nova-dispatch evidence.
4. Update the backlog to reflect that PR #517 merged and that hosted authentication, customer connection verification, hosted planning, apply, health, recovery, and lifecycle acceptance remain open.

## Acceptance criteria

- [x] Source `main`, deployed package hash, API health, and active Terraform-operation state are reconciled with current reads.
- [x] PR #517's exact AWS evidence and retained resources are represented without claiming a hosted Nova workload.
- [x] The 26 architecture entries and 30 Terraform roots remain intact; unsupported capabilities remain explicitly unmet.
- [x] Status docs distinguish the authentication/customer-connection blocker from implemented source and name the next hosted step.
- [ ] Documentation conventions, `git diff --check`, and required PR CI all pass.
- [x] This PR changes documentation only; no application code, AWS resource, hosted-control-plane configuration, or Terraform state was changed as part of this PR.

## Acceptance status

The source/deployed snapshots and PR #517 evidence crosswalk are updated. Local documentation conventions and `git diff --check` pass. CI for this PR is pending; keep the PR draft until all seven required checks pass. No hosted Nova plan or workload is claimed.

## Tests / validation performed

- Read-only GitHub checks confirmed PR #517 merged as `1453a5efdffbbbf7f7853b7ccfa71903a231bb96`; its final-head CI run `45863379689` and merged-main CI run `45864105035` passed all seven checks.
- Read-only AWS identity, Lambda package hash, public `/healthz`, and Terraform monitor checks confirmed account `654654474502`, current package hash, HTTP 200, and zero active operations.
- `GITHUB_PR_NUMBER=518 python3 scripts/check_doc_conventions.py`: passed.
- `git diff --check`: passed.
- No runtime test was needed for this documentation-only PR.

## Evidence files produced

- `docs/test/test517.md` records the direct AWS evidence, exact cleanup, retained inactive Batch job definitions, and limits.
- This PR updates `PROJECT_STATUS.md`, `docs/IMPLEMENTATION_STATUS.md`, `CODEX_BACKLOG.md`, and `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`.

## Boundaries

No AWS or control-plane mutation. Do not copy the private handoff or credential-location guidance into Git. Preserve unrelated untracked local files and worktrees. Do not claim any Nova customer workload has been applied or certified.

## Follow-up work

Once a workspace administrator authenticates through the required DavDeploy TOTP flow, verify the isolated customer connection and role, then submit the first hosted generated-plan request and inspect its durable evidence. Continue independent generic-runner implementation work without weakening MFA or tenant authorization.
