# test320 — Bounded Nova Terraform proposal repair evidence

Date: 2026-11-04
Execution type: local deterministic fixtures and service tests
Customer repository: Bepoadewale/davdeploy
Commit: pending
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

Pending implementation.

## Observed result

Pending implementation.

## Teardown

No external resources required teardown.

## Final boundary

This evidence covers local fixture and service behavior only. It is not AWS
deployment evidence, a live Nova test, a saved-plan test, or customer execution
validation.
