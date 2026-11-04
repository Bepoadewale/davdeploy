# test320 — Bounded Nova Terraform proposal repair evidence

Date: 2026-11-04
Execution type: local deterministic fixtures and service tests
Customer repository: Bepoadewale/davdeploy
Commit: a5c501e (rebased on fd75135)
AWS account: none; no AWS calls were made
AWS region: not applicable

## Planned cases

- A schema-invalid fixture response is repaired on the bounded next call and
  the final proposal retains the original trusted source revision and context
  digest.
- Sanitized feedback contains only allowlisted Pydantic codes and canonical
  proposal field paths; it excludes values, raw output, exception text,
  customer content, and credentials.
- A second invalid response stops at the configured cap and produces the safe
  actionable error.
- A provider fixture fallback is rejected, including on a repair attempt.
- Token usage, known cost, latency, evidence, and retry counts aggregate across
  semantic attempts, including JSON repair totals reported by the gateway.
- The generator's complete-document input digest passes the Bedrock adapter's
  integrity guard, while document tampering is rejected before a provider call.

## Resources created

No AWS or other external resources were created.

## Commands executed

- uv run pytest -q tests/test_terraform_generation.py tests/test_customer_plan_review.py tests/test_queue_and_model_gateway.py tests/test_nova_intent.py tests/test_generated_plan_review.py — 75 passed.
- make PY=/tmp/davdeploy320py312/bin/python verify — 671 passed; lint, configuration, OpenAPI and Compose checks passed.
- GITHUB_PR_NUMBER=320 uv run python scripts/check_doc_conventions.py — passed.
- git diff --check — passed.

## Observed result

Semantic repair, timeout, provider retry accounting, complete-document digest
checks, service persistence, sanitization, and failure boundaries passed their
fixture-backed tests. No real Bedrock or AWS request was made. The full suite
emitted one pre-existing Starlette/httpx deprecation warning.

## Teardown

No external resources required teardown.

## Final boundary

This evidence covers local fixture and service behavior only. It is not AWS
deployment evidence, a live Nova test, a saved-plan test, or customer execution
validation.
