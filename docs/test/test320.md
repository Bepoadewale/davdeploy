# Test evidence for PR #320

Status: implementation in progress. This record is reserved for deterministic
local fixture tests and static validation only. No real Bedrock invocation or
AWS resource mutation is in scope.

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

## Commands and results

Pending implementation.

## Limits

This is not AWS deployment evidence, a live Nova test, a saved-plan test, or
customer execution validation.
