# ticket421 — reconcile current Nova execution evidence

## Goal

Refresh the durable Nova execution handoff with current backend, hosted release,
draft apply-worker, AWS inventory, and Terraform monitor evidence. Keep source,
deployment, and customer workload acceptance as separate states.

## Current state

- Backend `main` is `9951caa9244128b1551fea3af66b1bdbf884c800` (PR #420).
- PR #413 merged as `de873ef9e22a96ec38aa4650741b42ff73f053f1`.
- Draft PR #399 is open at `72648dcf2b1237bfcbdd1643d02f1b3fd7d0c824`.
  It includes the apply credential and input APIs, isolated artifact staging,
  a fixed apply worker, and result reconciliation in source. CI run
  [43997205241](https://github.com/Bepoadewale/davdeploy/actions/runs/43997205241)
  passed all seven jobs. The runner and credential gates remain disabled; no
  customer role, credential issuance, or customer workload lifecycle has been
  verified.
- The protected control plane was subsequently deployed from current `main`
  using plan run
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

## References

- [Nova execution handoff](../product/COMPOSED_EXECUTION_GOAL.md)
- [Nova capability evidence matrix](../product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md)
- [PR #399 source and evidence](https://github.com/Bepoadewale/davdeploy/pull/399)
- [PR #420](https://github.com/Bepoadewale/davdeploy/pull/420)
- AWS CLI read-only inventory in account `654654474502`, region `us-east-1`.

## Work

- Reconcile the current source and hosted control-plane release in the goal
  handoff.
- Record the exact current status of PR #399 and preserve the disabled apply
  boundary.
- Update the acceptance matrix's status notes where the pricing and plan-review
  evidence advanced after its last documented baseline.

## Acceptance criteria

- [ ] Current main, merged coverage-ledger PR, and open draft apply PR are
  identified by exact commit and workflow evidence.
- [ ] Hosted control-plane deployment and runtime health are recorded without
  claiming a Nova customer workload.
- [ ] Current AWS test inventory and monitor status are recorded without
  deleting or altering retained evidence.
- [ ] Follow-up work and safety boundaries are explicit.

## Validation and evidence

Documentation-only. No runtime evidence file is required. Reviewed GitHub PR
and workflow metadata, the Terraform monitor, AWS read-only inventory, and the
health endpoint; no repository tests or Terraform mutation are part of this
change.

## Boundaries

- Do not merge PR #399 or enable either apply gate without the separate
  customer-role, hosted plan/apply, application health, update/recovery, destroy,
  and independent absence acceptance evidence.
- Do not alter the hosted control plane or the retained SageMaker lineage
  records as part of this documentation update.
- Do not claim any Nova customer workload has been applied or certified.

## Follow-up

Implement the next dependency-ready customer apply-role and permission evidence
package, then complete hosted apply and lifecycle acceptance before enabling the
customer path.
