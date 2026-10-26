# ticket175 — Preserve requested founder workspace names

PR: [#175](https://github.com/Bepoadewale/davdeploy/pull/175)
Branch: `fix/workspace-name-origin`

## Problem / goal

Founder workspaces were always given a Cognito-subject suffix, producing names such as
`DavDeploy Founder ceebf207` even when the requested name was unique.

## Current repo state

The existing founder workspace has been manually renamed to `DavDeploy Founder`. The onboarding
service still appended a subject suffix to every future founder workspace.

## Research / references used

- `ProductService.onboard_identity` and the globally unique `organizations.name` constraint.
- Existing workspace-onboarding test coverage.

## Work planned for the PR

- Use the verified caller's requested workspace name unchanged when it is available.
- Retain a short, deterministic disambiguator only for a genuine duplicate name.

## Acceptance criteria

- [x] A unique requested workspace name is preserved exactly.
- [x] A duplicate name remains globally unique without exposing a full subject.
- [x] Existing invitation onboarding behavior is unchanged.

## Acceptance status

Implementation is complete pending review.

## Tests / validation performed

- `.venv/bin/python -m pytest -q tests/test_product.py` — 37 passed.
- `.venv/bin/python -m pytest -q` — 293 passed.
- `.venv/bin/python -m ruff check apps/api/src/davdeploy/service.py tests/test_product.py`

## Evidence files produced

- Focused and full backend test results recorded above.

## Boundaries

This change affects only the name assigned at first-workspace creation. It does not alter existing
workspace names, invitations, roles, or identity verification.

## Follow-up work

Run the controlled browser founder-workspace creation flow after Cognito email delivery is
available, and confirm the requested workspace name is shown without a suffix.
