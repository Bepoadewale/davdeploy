# ticket460

PR: [#460 — docs: accept isolated customer lifecycle evidence](https://github.com/Bepoadewale/davdeploy/pull/460) (draft)

Branch: `docs/accept-direct-customer-lifecycle-460`

## Problem / goal

The active Nova handoff and capability matrix treated Nova-hosted lifecycle
execution as required to satisfy the general customer-side lifecycle gate.
The goal owner accepts properly isolated same-account customer tests, including
direct Terraform runs, as that gate for the exact tested resource shape and
observed behaviors. The documentation must state this accurately while keeping
Nova dispatch and per-resource support as separate claims.

## Current repo state

- PR #437 records isolated same-account ECS Express plan/apply, health, update,
  failed-revision recovery, teardown, and independent absence evidence.
- PR #458 records a direct AWS Batch retry and teardown test.
- The current evidence matrix records selected direct AWS service behavior,
  while other rows remain untested or only source/CI validated.
- No authenticated customer Nova request has produced a recorded hosted plan;
  Nova dispatch and credential issuance remain separate product gaps.

## Research / references used

- [PR #437](https://github.com/Bepoadewale/davdeploy/pull/437) and its
  isolated ECS Express lifecycle evidence.
- [PR #458](https://github.com/Bepoadewale/davdeploy/pull/458) and its direct
  Batch retry/teardown evidence.
- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `CODEX_BACKLOG.md`

## Work planned for the PR

1. Clarify in the active handoff that a properly isolated direct customer-side
   AWS test can meet the general plan/apply/lifecycle gate for its tested
   shape.
2. Separate isolated customer lifecycle evidence from Nova authorization,
   dispatch, and credential-path evidence in the capability matrix.
3. Define evidence labels and a shape-specific rule so service tests do not
   imply support for untested Terraform roots, configurations, or scenarios.
4. Reconcile the top-level backlog wording with that rule.

## Acceptance criteria

- [x] The handoff accepts direct, properly isolated same-account customer
  tests for the general lifecycle gate where the recorded evidence covers the
  tested plan/apply, health, update/recovery, teardown, and independent absence
  behaviors.
- [x] The matrix treats isolated lifecycle evidence as valid for the exact
  tested shape and keeps Nova dispatch/authorization/credentials separate.
- [x] No language makes Nova-hosted dispatch a prerequisite for the general
  customer-side lifecycle gate.
- [x] Direct tests do not imply support for untested roots, configurations,
  or composed scenarios; other policy, pricing, and safety gates stay visible.
- [x] The backlog, handoff, and matrix agree on this acceptance rule.
- [x] Documentation conventions and `git diff --check` pass.
- [x] No AWS resources or hosted control-plane state are changed.

## Acceptance status

Documentation is drafted; local acceptance criteria are met. All seven checks
passed in [CI run 45253901006](https://github.com/Bepoadewale/davdeploy/actions/runs/45253901006).
The PR remains a draft pending final-head checks and merge.

## Tests / validation performed

- `GITHUB_PR_NUMBER=460 python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- PR CI run 45253901006 — all seven checks passed.
- No product runtime or AWS workload test is planned for this documentation-only PR.

## Evidence files produced

- `CODEX_BACKLOG.md`
- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket460.md`

## Boundaries

- Do not change or destroy the hosted control plane.
- Do not mutate AWS resources.
- Preserve the protected untracked `--only-show-errors`, `.venv-pr399/`, and
  `docs/test/fixtures/nova-batch-retry-458/terraform.tfstate`.
- Do not claim Nova dispatched a customer workload or that untested resources
  are supported.

## Follow-up work

Continue the next dependency-ready Nova implementation package after this
acceptance rule is merged. Keep lifecycle evidence attached to the exact
resource shape and behavior it proves.
