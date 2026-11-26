# ticket518 — Reconcile Nova status after PR #517

PR: #518
Branch: `docs/nova-status-through-517`

## Problem / goal

Refresh the durable Nova status, backlog, and capability-evidence crosswalk against merged backend PR #517, the last recorded hosted control-plane release, and the exact acceptance work still outstanding. This is a documentation-only reconciliation; it does not enable a runner or assert customer deployment readiness.

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
4. Update the backlog to reflect that PR #517 merged. Direct isolated ECS and Batch lifecycle tests satisfy the general lifecycle gate for their exact tested shapes; Nova authorization/dispatch, customer-role verification, and cross-account execution remain separate gaps. Do not require a hosted control-plane test under the current user boundary.

## Acceptance criteria

- [x] Source `main`, last recorded deployed package hash/health observation, and active Terraform-operation state are reconciled. The PR #420 hash and health check are dated evidence, not evidence that later source is deployed.
- [x] PR #517's exact AWS evidence and retained resources are represented without claiming a hosted Nova workload.
- [x] The 26 architecture entries and 30 Terraform roots remain intact; unsupported capabilities remain explicitly unmet.
- [x] Status docs distinguish direct customer-side lifecycle evidence from Nova authorization/dispatch, and record the explicit no-hosted-control-plane boundary.
- [x] Documentation conventions, `git diff --check`, and 26/30 crosswalk counts pass locally.
- [x] All seven required PR checks passed on the latest status-content head `f2abfbbcf16c738cea672aa844c776444c322a8c` in run `45867539029`; the ticket-only status commit is subject to the same CI gate before merge.
- [x] This PR changes documentation only; no application code, AWS resource, hosted-control-plane configuration, or Terraform state was changed as part of this PR.

## Acceptance status

The source/deployed snapshots and PR #517 evidence crosswalk are updated. Local documentation conventions and `git diff --check` pass; the architecture and Terraform-root crosswalks still contain exactly 26 and 30 entries. All seven checks passed on content head `f2abfbbcf16c738cea672aa844c776444c322a8c` in run `45867539029`; the final ticket-only status commit remains gated by its own CI. No hosted Nova plan or workload is claimed.

## Tests / validation performed

- Read-only GitHub checks confirmed PR #517 merged as `1453a5efdffbbbf7f7853b7ccfa71903a231bb96`; its final-head CI run `45863379689` and merged-main CI run `45864105035` passed all seven checks.
- Read-only AWS identity and Terraform monitor checks confirmed account `654654474502` and zero active operations. The package hash and HTTP 200 observation are retained as the documented 2026-11-26 read-only snapshot; no hosted deployment or resource mutation was performed.
- `GITHUB_PR_NUMBER=518 python3 scripts/check_doc_conventions.py`: passed.
- `git diff --check`: passed.
- The matrix retains 26 architecture entries and 30 Terraform roots, counted between its named section boundaries.
- PR head `f2abfbbcf16c738cea672aa844c776444c322a8c` passed all seven checks in CI run `45867539029`; the final ticket-only status commit requires the same checks before merge.
- No runtime test was needed for this documentation-only PR.

## Evidence files produced

- `docs/test/test517.md` records the direct AWS evidence, exact cleanup, retained inactive Batch job definitions, and limits.
- This PR updates `PROJECT_STATUS.md`, `docs/IMPLEMENTATION_STATUS.md`, `CODEX_BACKLOG.md`, and `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`.

## Boundaries

No AWS or control-plane mutation. Do not copy the private handoff or credential-location guidance into Git. Preserve unrelated untracked local files and worktrees. Do not claim any Nova customer workload has been applied or certified.

## Follow-up work

Do not log into, mutate, or run customer tests through the hosted control plane under the current user boundary. Continue source and isolated-test work on Nova authorization and exact-plan lifecycle interfaces, preserving TOTP, tenant binding, immutable plan/artifact checks, deterministic policy, and the disabled hosted apply/credential gates. Any direct AWS lifecycle test must use a fresh exact customer-side manifest and remain limited to its verified resource shape.
