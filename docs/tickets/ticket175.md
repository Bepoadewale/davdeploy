# ticket175 — Preserve requested founder workspace names

PR: [#175](https://github.com/Bepoadewale/davdeploy/pull/175)
Branch: `fix/workspace-name-origin`

## Problem / goal

Founder workspaces were always given a Cognito-subject suffix, producing names such as
`DavDeploy Founder ceebf207` even when the requested name was unique.

## Work planned for the PR

- Use the verified caller's requested workspace name unchanged when it is available.
- Retain a short, deterministic disambiguator only for a genuine duplicate name.

## Acceptance criteria

- [x] A unique requested workspace name is preserved exactly.
- [x] A duplicate name remains globally unique without exposing a full subject.
- [x] Existing invitation onboarding behavior is unchanged.

## Tests / validation performed

- `.venv/bin/python -m pytest -q tests/test_product.py` — 37 passed.
- `.venv/bin/python -m pytest -q` — 293 passed.
- `.venv/bin/python -m ruff check apps/api/src/davdeploy/service.py tests/test_product.py`

## Boundaries

This change affects only the name assigned at first-workspace creation. It does not alter existing
workspace names, invitations, roles, or identity verification.
