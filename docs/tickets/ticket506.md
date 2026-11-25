# ticket506 — validate Nova architecture and Terraform crosswalk

PR: [#506 — test: validate Nova architecture and Terraform crosswalk](https://github.com/Bepoadewale/davdeploy/pull/506) (draft).

Branch: `feat/nova-crosswalk-validation`.

## Problem / goal

Make the candidate architecture-module-to-Terraform-root references in
`docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md` machine-checkable. Detect
identifier drift, missing roots, and one-sided candidate relationships while
keeping compatibility references separate from runtime dispatch and workload
certification.

## Current repo state

- Backend `main` is `526d4e14aab08ff671b57bee4a1eb3021a748957` after PR #495
  merged.
- The evidence matrix has 26 architecture rows and 30 Terraform implementation
  rows. Root-to-module candidates and reverse module-to-root candidates are
  prose and can drift.
- `module_catalogue.py` defines architecture modules; `certification_factory.py`
  defines scenario-to-module relationships.
- `infrastructure/terraform/modules/` contains the customer implementation
  roots. The matrix is the only current registry of their public implementation
  IDs.
- No open PRs were present when this package began. Protected untracked files
  in the primary worktree remain untouched.

## Research / references used

This is an internal consistency package; no cloud or external technology
adoption is required. The design uses these existing sources:

- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/product/NOVA_CATALOGUE_ROOT_BINDING.md`
- `apps/api/src/davdeploy/module_catalogue.py`
- `apps/api/src/davdeploy/certification_factory.py`
- `infrastructure/terraform/modules/*/main.tf`
- `AGENTS.md` PR, ticket, evidence, and validation requirements

## Work planned for the PR

1. Expose the architecture module identifiers through a stable read-only
   catalogue function.
2. Add tests that parse both matrix tables and verify the architecture and
   scenario rows against their Python sources.
3. Verify the implementation IDs and paths are unique, cover every checked-in
   customer Terraform module root, and point to existing root files.
4. Parse candidate architecture/root IDs in both directions and reject unknown
   or asymmetric relationships. Keep `partial` and unassigned relationships
   explicit; do not infer compatibility from service-name overlap.
5. Reconcile the AppConfig matrix row and Nova handoff/status documents to
   PR #495's merged direct lifecycle and verified cleanup evidence. Link this
   contract and validator from the matrix and documentation map.
6. Run focused tests, repository validation, documentation checks, and required
   final-head CI. No cloud workload test is part of this PR.

## Acceptance criteria

- [x] Architecture rows exactly match the source architecture catalogue.
- [x] Architecture-row scenario references exactly match
  `certification_factory` relationships; scenario IDs in root descriptions
  are validated against that catalogue.
- [x] All 30 implementation IDs/paths are unique and map to existing workload
  Terraform roots. Every module directory is accounted for once, with four
  shared/plan-only components classified separately.
- [x] Candidate relationships agree in both matrix directions; all referenced
  IDs are known and explicit gaps/partial overlaps remain visible.
- [x] Documentation states that this consistency contract does not enable Nova
  dispatch, cloud execution, or workload certification.
- [x] The AppConfig row reports PR #495 merged and its exact cleanup evidence.
- [x] Focused tests and required local validation pass; no cloud resources are
  changed.
- [x] Final-head CI passed all seven checks on `ec235ea` in run
  `45639652857`.

## Acceptance status

- [x] Draft PR opened before substantive implementation; bootstrap document
  committed as `b298f58`.
- [x] This ticket was created before implementation work.
- [x] Crosswalk validator and matrix/handoff updates are implemented.
- [x] Focused tests and full repository validation pass locally.
- [x] Final-head CI passed all seven checks on `ec235ea` in run
  `45639652857`.
- [ ] Review and merge.

## Tests / validation performed

- `PYTHONPATH=apps/api/src /Users/adewale/Projects/davdeploy/.venv-pr399/bin/python -m pytest tests/test_nova_capability_evidence_registry.py -q` — 3 passed.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python` — 1,907 passed; lint, Actions configuration, OpenAPI snapshot, and Compose checks passed. One existing Starlette/httpx deprecation warning remains.
- `scripts/check_doc_conventions.py` — passed.
- `ruff check apps/api/src/davdeploy/module_catalogue.py tests/test_nova_capability_evidence_registry.py` and `git diff --check` passed.
- Final-head GitHub Actions run `45639652857` — all seven checks passed.

## Evidence files produced

- `docs/product/NOVA_CATALOGUE_ROOT_BINDING.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `tests/test_nova_capability_evidence_registry.py`
- `docs/test/test495.md` remains the direct AWS lifecycle evidence source.
- This ticket and the updated Nova goal handoff/status documents.

## Boundaries

- This PR creates only source-level validation and documentation.
- No AWS mutation, hosted control-plane action, Terraform plan/apply/destroy,
  Nova runtime change, or customer workload test is authorized or planned.
- Candidate mappings are documentation compatibility references, not deployable
  bindings. Unsupported or ambiguous roots remain partial or unassigned.
- Required evidence is the focused test result, full repository validation,
  documentation convention result, final-head GitHub checks, and this ticket.

## Follow-up work

Runtime Nova dispatch-to-root binding remains a separate goal gate. It requires
its own typed adapter contract, exact-plan authorization, and lifecycle evidence;
this PR must not imply that gate has passed.
