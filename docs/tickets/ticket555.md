# ticket555 — normalize malformed Nova resource IDs safely

PR: [#555](https://github.com/Bepoadewale/davdeploy/pull/555) (draft)
Branch: `fix/nova-resource-id-normalization-555`

## Problem / goal

Hosted Nova generation continues to emit IDs outside the strict contract even after bounded repair and exact pattern guidance. Make malformed, unique ID labels usable by canonicalizing them deterministically before validation and rewriting only their declared graph references. Duplicate or otherwise ambiguous identities must remain invalid.

## Current repo state

- Backend main: `2d79b15f03a922289667e1f5bdea60763ac92f25` (PR #554).
- Deployed prompt v18 run `9cd5f381-7300-431d-9b13-e3c0b337a67d` failed before CodeBuild with safe `string_pattern_mismatch` at `resources[*].resource_id`; no artifact exists. Do not retry it.
- The hosted architecture remains unsupported for the required composed milestone and uses fixture pricing; a corrected ID alone cannot close the hosted-plan gate.

## Research / references used

- `apps/api/src/davdeploy/generated_deployment_contract.py` — strict 24-character ID pattern and typed graph references.
- `apps/api/src/davdeploy/terraform_generation.py` — bounded Nova generation and prompt feedback loop.
- `docs/test/test554.md` — v18 deployed failure and sanitized evidence.

## Work planned for the PR

1. Canonicalize only malformed string resource IDs into deterministic lowercase hyphenated IDs within the strict length/pattern.
2. Rewrite exact matches in dependencies, typed resource references, health targets/sources, and cost assumptions.
3. Preserve valid IDs and fail closed for duplicate original IDs or unresolvable collisions.
4. Strictly validate the normalized proposal using the unchanged contract; never expose raw model IDs.
5. Add regression tests for uniqueness, deterministic output, all reference paths, and fail-closed cases.
6. After deployment, create a fresh undecided review and one plan-only run; inspect only bounded diagnostics or value-free artifact evidence.

## Acceptance criteria

- [x] Valid IDs are unchanged; bounded malformed unique string IDs become deterministic valid IDs.
- [x] Dependencies, typed argument references, health targets/sources, and cost assumptions referencing a changed ID are rewritten consistently.
- [x] Duplicate original IDs, sensitive or unbounded source labels, and unresolved collisions are left unchanged for strict schema rejection.
- [x] The unchanged strict contract, cycle checks, typed reference checks, trusted context, policy, and no-apply boundary remain enforced.
- [x] No raw source ID is placed in diagnostics; existing sanitized validator feedback remains unchanged.
- [x] Focused tests (60) and full `make verify` (2,072 tests, Ruff, Actions configuration, OpenAPI, Compose) pass locally.
- [x] Documentation conventions passed locally; required PR CI run `46038096622` passed all seven checks on implementation head `89190e23ab41d6f136dce0e8f14a483eaa14c063`. Final evidence-updated head CI remains pending.
- [ ] Fresh deployed plan-only run reaches an inspectable artifact or actionable bounded feedback; no customer approval/apply occurs.
- [ ] Acceptance is not claimed unless supported API, private storage, database, async behavior, current pricing, and plan policy are evidenced.

## Acceptance status

Implementation and local test validation complete; PR CI passed on implementation head; final evidence-updated head CI, protected deployment, and hosted v18 plan-only result remain pending.

## Tests / validation performed

- Read-only hosted v18 run status and bounded diagnostic inspection; no raw proposal access.
- `/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python -m pytest -q tests/test_nova_resource_id_normalization.py tests/test_terraform_generation.py` — 60 passed.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python` — 2,072 passed; Ruff, Actions configuration, OpenAPI, and Compose checks passed. One existing Starlette deprecation warning.
- `GITHUB_PR_NUMBER=555 .../python scripts/check_doc_conventions.py` and `git diff --check` — passed.
- CI run `46038096622` passed all seven required checks on implementation head `89190e23ab41d6f136dce0e8f14a483eaa14c063`; final evidence-updated head CI is pending.

## Evidence files produced

- `docs/tickets/ticket555.md`
- `docs/test/test555.md`

## Boundaries

Do not weaken schema or graph policy. Never return raw generated identifiers, proposal text, plan/state values, credentials, or signed URLs. Keep the customer review unapproved and the generated run plan-only. Preserve protected local files and retained audit evidence.

## Follow-up work

A valid generated plan remains subject to live pricing, actual plan-policy checks, hosted approval/execution, application behavior, recovery, and independent teardown verification.
