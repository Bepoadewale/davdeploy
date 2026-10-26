# ticket178 — Customer-chosen project names

PR: [#178 — Allow human-readable customer project names](https://github.com/Bepoadewale/davdeploy/pull/178)

## Goal

Allow a customer to give a project a readable name instead of forcing a generated lowercase slug.

## Current state

The create-project request only accepts lowercase, hyphenated names. The browser therefore generates timestamped placeholder names such as `project-53905575`.

## References

- The reviewed customer plan screen showing the generated project name.
- `ProjectRequest`, the versioned API input contract.

## Planned work

- Broaden the display-name validation while keeping a bounded, safe character set.
- Regenerate the committed OpenAPI contract.
- Add contract regression coverage.

## Acceptance criteria and status

- [x] A customer-facing name such as `French Pattern Cramming` is accepted.
- [x] Blank, unsafe, and overlong names are rejected.
- [x] The API contract and validation checks pass.

## Validation

`make openapi-update`, `.venv/bin/python -m pytest -q tests/test_project_name_contract.py`, and `make verify` passed. The full suite passed 295 tests; the OpenAPI snapshot matches the application.

## Evidence files

- `docs/test/test178.md`

## Boundaries

This only changes the project display-name validation. It does not grant additional access or affect planning, cloud execution, authorization, or persisted project ownership.

## Follow-up

The browser will collect the name in the coordinated frontend PR.
