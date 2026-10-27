# ticket179 — Project name storage bound

PR: [#179 — Align project-name validation with storage](https://github.com/Bepoadewale/davdeploy/pull/179)
Branch: `fix/project-name-length-bound`

## Problem / goal

Keep the public project-name input validation within the existing 64-character database column capacity.

## Current repo state

Readable project names are accepted by the API, while the persisted `projects.name` column is limited to 64 characters.

## Research / references used

- `ProjectRequest` input contract.
- `Project.name` database model.

## Work planned for the PR

- Restrict the API request to the existing storage length.
- Regenerate the OpenAPI snapshot and update the regression case.

## Acceptance criteria

- [x] The API rejects names longer than the persisted column allows.
- [x] Contract and full validation pass.

## Acceptance status

Implemented and locally verified; pending CI and review.

## Tests / validation performed

`make openapi-update`, `.venv/bin/python -m pytest -q tests/test_project_name_contract.py`, `make verify`, and `python scripts/check_doc_conventions.py` passed. The full suite passed 295 tests.

## Evidence files produced

- `docs/test/test179.md`

## Boundaries

This is a validation correction only. It does not change existing records, tenancy, authorization, or infrastructure.

## Follow-up work

Keep the browser input bound in sync with this API limit.
