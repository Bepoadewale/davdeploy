# ticket440 — refresh Nova goal handoff after PR #399

PR: https://github.com/Bepoadewale/davdeploy/pull/440
Branch: `docs/nova-goal-handoff-refresh-20261119`

## Problem / goal

The canonical Nova goal handoff and evidence matrix still describe PRs #399
and #438 as open at stale heads, despite both being merged. Refresh the current
source, PR, acceptance, hosted-release, and operations snapshot while preserving
the full 26 architecture-entry and 30 Terraform-root scope and the dated
historical checklist.

## Current repo state

- Backend `main` is `ff6ffae9ab88a37facbc443dfb35efe8c11b598d`, including PR
  #399. No pull requests are open at the start of this documentation update.
- PR #399 merged at `ff6ffae`; its final source head `61bdb3f` passed all seven
  required checks in run `44598735006`. Its Nova apply and credential gates
  remain disabled and the source is not deployed to the hosted control plane.
- PR #438 merged at `cb78865`; its append-only template-host source was not
  applied. Its protected-state plan recorded four address moves and zero
  resource changes.
- The owner accepts PR #437's properly isolated, same-account ECS Express run
  as the general goal's customer-side plan/apply/health/update/recovery/teardown
  evidence. The run used direct Terraform and does not claim Nova generation,
  authorization, dispatch, or cross-account isolation.
- A temporary customer apply role created from the PR #399 CloudFormation
  template was exercised in the same account with a temporary broker role,
  valid and invalid ExternalId attempts, an exact S3 session policy, and an
  explicit denial check. The test bucket, role stack, and broker role were
  removed and independently checked absent; this does not test Nova dispatch.
- The last recorded hosted control-plane release remains PR #420, applied by
  run `43982396577` after plan run `43981566184`. No hosted control-plane
  mutation was made; the customer-side test resources were temporary and
  cleaned up.
- The Terraform run monitor has terminal history and no active run. Preserve
  the protected untracked `--only-show-errors` file and `.venv-pr399/`.

## Research / references used

- `docs/product/COMPOSED_EXECUTION_GOAL.md` — canonical goal handoff.
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md` — 26 architecture entries
  and 30 Terraform roots with per-entry evidence requirements.
- `docs/test/test399.md` and `docs/tickets/ticket399.md` — source and CI record
  for the exact-plan Nova apply boundary.
- `docs/test/test437.md` and `docs/tickets/ticket437.md` — isolated customer
  ECS lifecycle evidence and its accepted scope.
- `docs/test/test438.md` and `docs/tickets/ticket438.md` — append-only template
  publishing source and protected-state plan evidence.
- Current GitHub PR and CI state for #399, #437, #438, and #439.

## Work planned for the PR

1. Correct the canonical current-source and active-PR status after PRs #399,
   #438, and #439 merged.
2. Record PR #399's source-only merge and keep hosted execution gates and
   deployment status explicit.
3. Preserve the accepted ECS customer-side evidence with direct-Terraform
   provenance and retain Nova-specific and per-entry gaps.
4. Record bounded customer-role verification without attributing it to Nova or
   broadening the accepted direct ECS evidence.
5. Keep the historical renderer checklist historical and preserve the complete
   26/30 evidence matrix.

## Acceptance criteria

- [x] Current source head, merged PRs, CI runs, hosted-release boundary, and
      open-PR state are accurately recorded.
- [x] The ECS test is counted for the general customer-side lifecycle gate,
      with direct-Terraform provenance and no claim of Nova execution.
- [x] The exact-plan apply path is identified as merged source only; apply and
      credential gates remain disabled and no hosted deployment is claimed.
- [x] The 26 architecture entries and 30 Terraform roots remain intact, and
      broad Nova acceptance is not marked complete.
- [ ] Documentation conventions, diff checks, matrix counts, and PR CI pass on
      the final content head.
- [x] No hosted-control-plane, Terraform state/lock, runtime, or feature-gate
      mutation; temporary customer test resources were removed.

## Acceptance status

The handoff and matrix now reconcile the current source and preserve the
customer-side evidence acceptance and remaining Nova-specific scope. The
customer apply-role template also passed a bounded temporary same-account
assume-role/session-policy test; all created resources were removed. No hosted
control-plane resource or state was changed. Documentation checks passed; final
PR CI is pending.

## Tests / validation performed

- `GITHUB_PR_NUMBER=440 python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Matrix count validation — 26 architecture entries and 30 Terraform roots.
- Customer-role smoke: created a temporary broker IAM role and the template's
  dedicated apply role; verified the correct ExternalId succeeds, a wrong
  ExternalId is rejected, a plan-scoped session can create/head/delete only
  its fresh S3 bucket, and EC2 `DescribeInstances` is explicitly denied.
- CloudTrail records `Client.UnauthorizedOperation` with explicit identity
  policy denial for `ec2:DescribeInstances` at `2026-11-19T19:57:25Z`.
- CloudFormation stack `davdeploy-nova-apply-smoke-b9e85dc2` reached
  `DELETE_COMPLETE`; independent AWS reads confirmed both temporary roles and
  the S3 bucket are absent.
- Required PR CI is pending.
- Current GitHub state verified with `gh pr list`, `gh pr view`, and the
  terminal checks for PR #399.
- Terraform monitor inspected; no active run was reported.

## Evidence files produced

- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket440.md`
- `docs/test/test440.md`

## Boundaries

Do not modify the hosted control plane, its state, locks, runtime, queues, or
feature gates. The isolated role test is customer-side source/template evidence,
not Nova credential issuance or dispatch proof. Do not claim Nova initiated or
certified the ECS run, or that the full 26/30 capability matrix is complete.
Preserve the protected untracked `--only-show-errors` and `.venv-pr399/` in the
user's main checkout.

## Follow-up work

Continue dependency-ordered implementation and acceptance work against the
full Nova goal. The exact-plan execution source is merged but unexercised
through Nova; cost, policy, role-permission, cross-account, browser/CLI/MCP,
and per-entry scenario evidence remain incomplete.
