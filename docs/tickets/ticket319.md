# ticket319 — Map Nova capabilities to execution evidence

PR: #319 https://github.com/Bepoadewale/davdeploy/pull/319
Branch: `docs/nova-capability-evidence-319`
Base at start: `3fe7d07` (`docs: reconcile Nova execution status (#316)`)

## Problem / goal

Add a source-backed matrix joining every architecture catalogue module and
Terraform implementation root to its current scenario, implementation binding,
policy evidence, health evidence, pricing evidence, and hosted lifecycle proof.
Record missing relationships and capabilities explicitly. Do not claim that a
catalogue entry or isolated AWS service test is a hosted customer capability.

## Current repo state

- `module_catalogue.py` defines 26 architecture modules.
- `module_implementations.py` defines 30 Terraform implementation roots.
- `certification_factory.py` defines eight scenario manifests.
- Existing readiness and scenario documents distinguish service-level AWS
  tests from hosted composed lifecycle evidence.
- PR #316 updated the execution-status handoff on `main`; this PR adds a
  separate capability evidence matrix and does not modify that handoff or the
  existing readiness matrix.

## Research / references used

- `apps/api/src/davdeploy/module_catalogue.py`
- `apps/api/src/davdeploy/module_implementations.py`
- `apps/api/src/davdeploy/certification_factory.py`
- `apps/api/src/davdeploy/certification_evidence.py`
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `apps/api/src/davdeploy/generated_plan_inspection.py`
- `apps/api/src/davdeploy/generated_provider_validation.py`
- `apps/api/src/davdeploy/evidence.py`
- `docs/product/EXECUTION_READINESS_MATRIX.md`
- `docs/product/COMPOSED_EXECUTION_GOAL.md`
- `docs/test/` scenario and AWS evidence records

## Work planned for the PR

- Add `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md` with all 26 catalogue
  modules and all 30 implementation entries.
- Map scenario membership and implementation links only where the checked-in
  registry or scenario factory makes that relationship explicit; mark other
  links missing or inferred as unavailable rather than implying support.
- Record policy, pricing, health, update, failure/recovery, cleanup, and hosted
  proof status from checked-in code and evidence files.
- Preserve the source's limitations and distinguish local/fixture,
  static/provider-schema, isolated AWS, and hosted lifecycle evidence.

## Acceptance criteria

- [x] All 26 architecture module IDs appear once in the catalogue table.
- [x] All 30 implementation IDs and Terraform roots appear once in the root
  table.
- [x] Every scenario/module relationship matches `certification_factory.py`.
- [x] Missing registry links and unsupported resource families are explicit.
- [x] Policy, pricing, health, update/recovery, cleanup, and hosted proof claims
  link to checked-in evidence or say not implemented/not evidenced.
- [x] No private strategy, access instructions, secrets, or customer data are
  included.
- [x] Documentation convention checks and whitespace checks pass; no
  application tests or AWS calls are needed for this documentation-only PR.

## Acceptance status

The matrix content and local validation are complete. GitHub is the source of
truth for pull-request checks, review, and merge state. This ticket records no
deployment or runtime behavior.

## Tests / validation performed

Validation performed:

- Source-to-document comparison: all 26 catalogue IDs and their eight-scenario
  memberships match `module_catalogue.py` and `certification_factory.py`; all
  30 implementation IDs and root paths match `module_implementations.py`.
- `GITHUB_PR_NUMBER=319 python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Local Markdown links in the new matrix resolve.
- No application tests or AWS calls were run, as this PR is documentation-only.

## Evidence files produced

- Planned: `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- This ticket: `docs/tickets/ticket319.md`

## Boundaries

This PR documents existing evidence only. It does not add code, change
capability stages, enable a renderer, change the existing execution readiness
matrix, or copy the private Nova goal into the repository.

## Follow-up work

Update matrix status only alongside PRs that add evidence. A source-code change,
provider-schema validation, local fixture, or isolated AWS service test must not
be recorded as hosted composed lifecycle proof.
