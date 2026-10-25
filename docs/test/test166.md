# test166 — Hosted worker Bedrock Nova compatibility

Execution boundary: local/static validation. This test did not contact AWS, replay SQS messages, or deploy a runtime.

## Commands and results

```text
.venv/bin/python -m pytest -q tests/test_queue_and_model_gateway.py
12 passed
```

The regression test confirms that the legacy `bedrock-nova` provider alias selects `BedrockNovaGateway`. Unknown provider values remain rejected by the existing fail-closed branch.
