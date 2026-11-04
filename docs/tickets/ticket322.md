# ticket322 - require complete cost evidence for generated-plan approval

PR: [#322](https://github.com/Bepoadewale/davdeploy/pull/322)
Branch: `feat/submitted-plan-cost-gate-322`

## Problem / goal

Generated Terraform plans must be produced from a submitted customer revision before the final decision. The current persistence method requires that revision to be approved first, while the existing Nova plan path has no complete regional pricing evaluator. The artifact must remain explicitly unpriced and impossible to approve until cost evidence is complete.

## Current repo state

- `persist_generated_plan_artifact` currently accepts only `APPROVED` revisions.
- Artifact manifests bind the actual saved plan, policy and ownership, and approval verifies the manifest and stored object.
- The separate explicit architecture-decision endpoint continues to approve/reject submitted revisions for compatibility.
- Regional pricing implementation PR #318 was closed and is not part of this change. No complete cost evaluator is currently integrated into generated-plan artifacts.

## Research / references used

- `apps/api/src/davdeploy/service.py`: generated-plan persistence, detail and approval boundaries.
- `apps/api/src/davdeploy/generated_plan_artifacts.py`: immutable manifest and encrypted artifact evidence.
- `apps/api/src/davdeploy/models.py`: immutable artifact and approval records.
- `tests/test_generated_plan_review.py` and existing infrastructure-plan decision tests.
- Private local Nova goal is not copied into this public repository.

## Work planned for the PR

- Permit trusted persistence against the current, latest `SUBMITTED` revision while retaining tenant, target, digest, ownership and policy checks.
- Include an explicit incomplete/unavailable pricing status in the immutable manifest and safe detail response.
- Report that the artifact is waiting for regional cost evidence.
- Reject exact-manifest approval before any approval record or revision state change while pricing evidence is incomplete.
- Preserve the existing architecture-decision route unchanged.
- Add tests for submitted persistence, stale revisions, tampering, and unpriced approval denial.

## Acceptance criteria

- [x] A trusted generated plan can be persisted for a current, latest `SUBMITTED` revision without changing that revision's state.
- [x] Stale revisions and revision/proposal/manifest tampering remain rejected.
- [x] Artifact manifest/detail explicitly mark regional pricing as unavailable or incomplete.
- [x] Exact-manifest approval fails closed while cost evidence is incomplete and records no approval or state transition.
- [x] The explicit architecture-decision route remains unchanged.
- [x] Focused tests, full `make verify`, and documentation convention checks pass.
- [x] No AWS, Bedrock, or infrastructure calls/mutations are performed.
- [x] All seven required GitHub checks pass in run [41910023222](https://github.com/Bepoadewale/davdeploy/actions/runs/41910023222).

## Acceptance status

Implementation and local validation are complete. All seven required GitHub checks passed in run [41910023222](https://github.com/Bepoadewale/davdeploy/actions/runs/41910023222). Draft PR #322 remains open and unmerged for review.

## Tests / validation performed

See `docs/test/test322.md`. Local full verification passed with 683 tests; required GitHub checks passed on the current implementation and evidence.

## Evidence files produced

`docs/test/test322.md` records local test and validation evidence. No customer workload execution is in scope.

## Boundaries

This PR does not implement or claim pricing. All Nova-generated plan artifacts remain unapprovable until a separate trusted regional cost evaluator is integrated and its evidence is bound into the artifact manifest. This change does not perform AWS planning, apply, destroy, or migration work.

## Follow-up work

Integrate a reviewed regional cost evaluator and bind complete cost evidence, assumptions, freshness, and pricing-source provenance into the immutable manifest before permitting final plan approval. Continue with the separate hosted plan-only runner only after the cost and approval contract is complete.
