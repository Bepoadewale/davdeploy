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
4. Update the backlog to reflect that PR #517 merged and that the first hosted Nova plan remains unmet until a workspace administrator authenticates and the customer connection/role is verified. Direct isolated ECS and Batch lifecycle tests satisfy the general lifecycle gate only for their exact tested shapes; they do not substitute for hosted Nova authorization, dispatch, or cross-account trust.

## Acceptance criteria

- [x] Source `main`, last recorded deployed package hash/health observation, and active Terraform-operation state are reconciled. The PR #420 hash and health check are dated evidence, not evidence that later source is deployed.
- [x] PR #517's exact AWS evidence and retained resources are represented without claiming a hosted Nova workload.
- [x] The 26 architecture entries and 30 Terraform roots remain intact; unsupported capabilities remain explicitly unmet.
- [x] Status docs distinguish direct customer-side lifecycle evidence from Nova authorization/dispatch and state the actual hosted blocker without implying that hosted access is prohibited.
- [x] Documentation conventions, `git diff --check`, and 26/30 crosswalk counts pass locally.
- [ ] All seven required PR checks pass on the corrected final head; record the final commit and run here before merge.
- [x] This PR changes documentation only; no application code, AWS resource, hosted-control-plane configuration, or Terraform state was changed as part of this PR.

## Acceptance status

The source/deployed snapshots and PR #517 evidence crosswalk are updated. Local documentation conventions and `git diff --check` pass; the architecture and Terraform-root crosswalks still contain exactly 26 and 30 entries. The latest DavDeploy TOTP attempt was rejected, so no authenticated workspace session, verified customer connection, or hosted Nova plan exists. Final-head CI remains required before merge. No Nova customer workload is claimed.

## Tests / validation performed

- Read-only GitHub checks confirmed PR #517 merged as `1453a5efdffbbbf7f7853b7ccfa71903a231bb96`; its final-head CI run `45863379689` and merged-main CI run `45864105035` passed all seven checks.
- AWS identity and local Terraform monitor checks confirmed account `654654474502` and 75 historical records with zero active operations. The protected read-only deployment-plan workflow run `45866989345` completed for `1453a5e`: 0 add, 8 in-place changes, 0 destroy, 1 IAM-role-policy drift, and 8 output changes. The workflow uploaded immutable release packages and an encrypted saved plan; no Terraform apply or control-plane runtime change occurred. The Lambda package hash is unchanged from the prior snapshot. The earlier 2026-11-26 health probe returned HTTP 200; the latest bounded probe timed out, which is not enough to infer an outage. Neither observation proves that source through PR #517 is deployed.
- `GITHUB_PR_NUMBER=518 python3 scripts/check_doc_conventions.py`: passed.
- `git diff --check`: passed.
- The matrix retains 26 architecture entries and 30 Terraform roots, counted between its named section boundaries.
- The corrected final PR head and its CI run remain to be recorded before merge.
- No runtime test was needed for this documentation-only PR.

## Evidence files produced

- `docs/test/test517.md` records the direct AWS evidence, exact cleanup, retained inactive Batch job definitions, and limits.
- This PR updates `PROJECT_STATUS.md`, `docs/IMPLEMENTATION_STATUS.md`, `CODEX_BACKLOG.md`, and `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`.

## Boundaries

No AWS or control-plane mutation. Do not copy the private handoff or credential-location guidance into Git. Preserve unrelated untracked local files and worktrees. Do not claim any Nova customer workload has been applied or certified.

## Follow-up work

The first hosted plan is blocked on a valid DavDeploy TOTP session and verified customer connection; the latest supplied TOTP was rejected, and no session was issued. Continue independent source work without weakening MFA or tenant controls. Do not start a customer workload apply until an exact plan is reviewed and the required approval is bound to its digests. Any direct AWS lifecycle test must use a fresh exact customer-side manifest and remain limited to its verified resource shape. Control-plane releases use the protected, reviewed Terraform workflow; do not make direct/manual runtime changes.
