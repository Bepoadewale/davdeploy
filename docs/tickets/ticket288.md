# ticket288 — Validate universal execution plan identity and graph input

PR: https://github.com/Bepoadewale/davdeploy/pull/288
Branch: `fix/validate-universal-plan-identity`

## Problem / goal

The universal plan compiler currently accepts an empty graph, an empty module
identifier, duplicate dependencies, and any 64-character string as a plan
digest. An empty graph can appear trivially complete, while malformed identity
values weaken resource tagging and audit binding. Reject these cases before
creating lifecycle work.

## Current repo state

Dependency ordering, cycle detection, digest-bound tags, operation-specific
terminal evidence, and cleanup evidence validation are implemented. The
compiler does not yet validate all graph and identity inputs.

## Research / references used

- `apps/api/src/davdeploy/universal_execution.py`
- `tests/test_universal_execution.py`
- `docs/product/COMPOSED_EXECUTION_GOAL.md`

## Work planned for the PR

- Require a non-empty graph with unique non-empty module identifiers.
- Reject duplicate/self/unknown dependency references.
- Require non-empty workspace and project scope and a lowercase SHA-256 plan
  digest.
- Add focused negative tests.

## Acceptance criteria

- [x] Empty or malformed graph identity is rejected before lifecycle ordering.
- [x] Duplicate, self, and unknown dependencies are rejected.
- [x] Valid plans preserve deterministic dependency ordering and tags.
- [ ] Focused tests and required CI pass.

## Acceptance status

Implementation and local verification pass. GitHub CI is pending.

## Tests / validation performed

`make verify` passed: 423 tests, Ruff, Actions configuration, OpenAPI snapshot,
and Docker Compose configuration checks. `python3 scripts/check_doc_conventions.py`
and `git diff --check` passed.

## Evidence files produced

No AWS workload evidence is expected. This PR changes local input validation
only.

## Boundaries

No renderer is enabled and no hosted execution or AWS configuration changes.

## Follow-up work

Add module-specific schemas and dependency output bindings to the planner and
renderer manifests before multi-module hosted scheduling.
