# ticket421 — reconcile current Nova execution evidence

PR: #421 https://github.com/Bepoadewale/davdeploy/pull/421
Branch: `docs/reconcile-nova-current-evidence-421`

## Problem / goal

Refresh the durable Nova execution handoff with current backend, hosted release,
draft apply-worker, AWS inventory, and Terraform monitor evidence. Keep source,
deployment, and customer workload acceptance as separate states.

## Current repo state

- Backend `main` is `9951caa9244128b1551fea3af66b1bdbf884c800` (PR #420).
- PR #413 merged as `de873ef9e22a96ec38aa4650741b42ff73f053f1`.
- Draft PR #399 is open at `72648dcf2b1237bfcbdd1643d02f1b3fd7d0c824`.
  It contains the apply credential and input APIs, isolated artifact staging,
  a fixed apply worker, and result reconciliation in source. CI run
  [43997205241](https://github.com/Bepoadewale/davdeploy/actions/runs/43997205241)
  passed all seven jobs. The runner and credential gates remain disabled; no
  customer role, credential issuance, or customer workload lifecycle has been
  verified.
- The protected control plane was deployed from current `main` using plan run
  [43981566184](https://github.com/Bepoadewale/davdeploy/actions/runs/43981566184)
  and apply run
  [43982396577](https://github.com/Bepoadewale/davdeploy/actions/runs/43982396577).
  Both jobs succeeded, including database migrations. The six `davdeploy-*`
  Lambda packages report one shared code hash, and public `/healthz` returned
  HTTP 200. This is control-plane deployment evidence only.
- AWS identity was read-only verified as account `654654474502` in
  `us-east-1`. No SageMaker endpoint, model, or endpoint configuration was
  returned. Four `davdeploy-*` Batch definitions are inactive. One test
  SageMaker lineage action and one context remain as audit evidence; no lineage
  records were changed.
- `scripts/terraform_run_monitor.py status` returned an empty registry, and no
  Terraform plan, apply, or destroy process was found.
- The protected untracked `--only-show-errors` file and `.venv-pr399/` remain
  untouched.
- Frontend `main` is `b6cb14bc9563802d9b0b644739a6136336594174`. PR #102 is
  draft at `d3008e72296064beb2eea75c3efffcd96c809554`; all five required checks
  passed in run `43579164304`, but the change is not merged and does not add a
  backend execution path. PR #99 is draft at
  `76908ebd7ea3453320fe7959c9b4643b3b6632ac`; backend `main` still returns a
  fixed blog author display name and the PR is not cleanly mergeable. Five
  Dependabot PRs (#82–#86) also remain open.
- `PROJECT_STATUS.md`, `docs/IMPLEMENTATION_STATUS.md`, and
  `CODEX_BACKLOG.md` still reported a November 13 source/deployment baseline
  and said regional pricing was not integrated.

## Research / references used

- [Nova execution handoff](../product/COMPOSED_EXECUTION_GOAL.md)
- [Nova capability evidence matrix](../product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md)
- [PR #399 source and evidence](https://github.com/Bepoadewale/davdeploy/pull/399)
- [PR #420](https://github.com/Bepoadewale/davdeploy/pull/420)
- [Frontend PR #102](https://github.com/Bepoadewale/davdeploy-frontend/pull/102)
- [Frontend PR #99](https://github.com/Bepoadewale/davdeploy-frontend/pull/99)
- AWS CLI read-only inventory in account `654654474502`, region `us-east-1`.

## Work planned for the PR

- Reconcile current source and hosted control-plane release in the goal handoff.
- Record the exact current status of PR #399 and preserve the disabled apply
  boundary.
- Update pricing and plan-review status notes in the capability matrix.
- Refresh the stale project, implementation, and backlog status summaries.
- Record the relevant open frontend PRs and distinguish UI clarity from actual
  lifecycle parity.

## Acceptance criteria

- [x] Current main, merged coverage-ledger PR, and open draft apply PR are
  identified by exact commit and workflow evidence.
- [x] Hosted control-plane deployment and runtime health are recorded without
  claiming a Nova customer workload.
- [x] Current AWS test inventory and monitor status are recorded without
  deleting or altering retained evidence.
- [x] Follow-up work and safety boundaries are explicit.
- [x] The open frontend PRs are checked for relevance and dependency status.
- [x] The three stale project/implementation/backlog summaries are reconciled.

## Acceptance status

Complete for this documentation scope; no customer execution gate is promoted.

## Tests / validation performed

Documentation-only. No runtime evidence file is required.

- `python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Final validation after the status-file updates: both checks passed again.
- No Terraform mutation or customer workload was run.

## Evidence files produced

No `docs/test/test421.md` is required because this PR changes documentation only.
The reconciled evidence is linked from the two product documents above.

## Boundaries

- Do not merge PR #399 or enable either apply gate without the separate
  customer-role, hosted plan/apply, application health, update/recovery, destroy,
  and independent absence acceptance evidence.
- Do not alter the hosted control plane or retained SageMaker lineage records
  as part of this documentation update.
- Do not claim any Nova customer workload has been applied or certified.

## Follow-up work

Implement the next dependency-ready customer apply-role and permission evidence
package, then complete hosted apply and lifecycle acceptance before enabling the
customer path.
