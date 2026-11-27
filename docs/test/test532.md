# test532 — Explicit Nova workload requirement preservation

Date: 2026-11-27
Execution type: Local structured-provider unit tests
Customer repository: None; synthetic intent fixtures only
Commit: `2bbdb9d18571f603b826dd0db602128378cd3e7a` (implementation commit exercised by the recorded checks)
AWS account: `654654474502` (hosted acceptance account; no AWS operations in this PR)
AWS region: `us-east-1`

## Resources created

No AWS or hosted DavDeploy resources were created or changed.

## Commands executed

- `uv run --project . pytest -q tests/test_nova_intent.py` — 25 passed
- `uv run --project . ruff check apps/api/src/davdeploy/intent.py tests/test_nova_intent.py` — passed
- `git diff --check` — passed

## Observed result

- Structured model output that omitted explicit storage, database, and
  asynchronous-job requirements is supplemented from a fixed allow-listed
  prompt vocabulary.
- Event-driven, stateful, and multi-service flags follow the resulting
  requirements.
- Substring matches and simple negated capability mentions do not add a
  capability.
- Test fixtures retain the same allow-list and unknown-field behavior.
- Hosted re-evaluation is pending; no runtime deployment or Terraform plan is
  claimed.

## Teardown

No resources were created; no teardown was required.

## Final boundary

This proves only deterministic interpretation logic with synthetic unit-test
inputs. It does not prove the hosted model will produce the required
architecture, that every matrix family is executable, or that any Nova
customer workload has been applied or certified.
