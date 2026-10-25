# test166 — Hosted worker Bedrock Nova compatibility

Date: 2026-10-25

Execution type: local/static validation

Customer repository: not used

Commit: `f2e09fc`

AWS account: not contacted

AWS region: not contacted

## Resources created

None.

## Commands executed

```text
.venv/bin/python -m pytest -q tests/test_queue_and_model_gateway.py
12 passed
```

## Observed result

The regression test confirms that the legacy `bedrock-nova` provider alias selects
`BedrockNovaGateway`. Unknown provider values remain rejected by the existing fail-closed branch.

## Teardown

No resources were created.

## Final boundary

This test did not contact AWS, replay SQS messages, or deploy a runtime.
