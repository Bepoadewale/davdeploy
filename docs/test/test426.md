# test426 — validated Nova intent proposal identity

Date: 2026-11-17
Execution type: source tests
Customer repository: none
Commit: `e2f98fe20b70ded9bbd849143cbcf4571b8d8406` (implementation)
AWS account: none
AWS region: none

Status: source implementation is complete locally. Tests use gateway fixtures;
no real model, AWS, or hosted calls occurred for this package.

## Resources created

None. No model, AWS, Terraform, or clean-room resources were created.

## Verification

- Focused `tests/test_nova_intent.py`: 23 passed. Coverage includes accepted,
  repaired, out-of-scope, and fixture metadata behavior, equivalent normalized
  proposal stability, and digest change when a validated field changes.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python`:
  1,304 tests passed; Ruff, Actions configuration, OpenAPI, and Compose checks
  passed. One existing Starlette/httpx deprecation warning remains.
- Documentation convention checks and `git diff --check` passed.
- GitHub Actions run [`44185396711`](https://github.com/Bepoadewale/davdeploy/actions/runs/44185396711)
  passed all seven required checks on implementation commit `e2f98fe`.
- The documentation-only evidence commit's fresh-head CI result will be
  recorded in the PR description.

## Commands executed

- `pytest -q tests/test_nova_intent.py`
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python`
- `GITHUB_PR_NUMBER=426 python scripts/check_doc_conventions.py`
- `git diff --check`
- `gh pr checks 426 --watch --interval 120`

## Observed result

Bedrock-backed intent metadata now records proposal contract version
`nova-intent-proposal-v1` and the SHA-256 canonical JSON digest of the final
locally validated proposal, including after repair and for out-of-scope
responses. Fixture metadata remains marked as fixture and omits this Nova
proposal identity. No raw response is added to the metadata.

## Teardown

No teardown was required; no external or runtime resources were created.

## Final boundary

Tests will use gateway fixtures only. They will not call Bedrock, AWS, hosted
services, Terraform, or customer workloads.
