# Amazon Nova 2 Lite

**Implemented, disabled by default.** davdeploy can use Amazon Nova 2 Lite
through the Amazon Bedrock Converse API to interpret a customer request into a
typed workload proposal. Local development and CI continue to use the explicitly
labelled fixture unless Bedrock is selected.

## Authority boundary

Nova may interpret requirements and propose values. It cannot approve a plan,
evaluate OPA policy, calculate the immutable plan digest, invoke Terraform, run a
shell, or mutate a customer cloud. Pydantic validation, deterministic planning,
policy, human approval, and the bounded runner remain independent.

The current Nova 2 Lite Bedrock model card marks native structured outputs as
unsupported. davdeploy therefore sends a JSON schema with the request and
accepts only a plain JSON object or that object inside one exact `json` code
fence. It rejects surrounding prose and non-object JSON, validates the decoded
object locally, permits one bounded JSON-format repair attempt per structured
request, and fails closed if the response remains invalid. Terraform proposal
generation permits at most two semantic attempts under a 120-second total
deadline by default. It sends only sanitized schema error codes and allowlisted
field paths in the repair request. It does not claim provider-enforced schema
compliance.

## Configuration

Set these on the API runtime through its secret/configuration system:

```text
DAVDEPLOY_MODEL_PROVIDER=bedrock
DAVDEPLOY_MODEL_FALLBACK=disabled
DAVDEPLOY_BEDROCK_REGION=us-east-1
DAVDEPLOY_BEDROCK_MODEL_ID=us.amazon.nova-2-lite-v1:0
DAVDEPLOY_MODEL_DATA_POLICY=bedrock-no-training
DAVDEPLOY_MODEL_MAX_OUTPUT_TOKENS=2000
DAVDEPLOY_MODEL_TIMEOUT_SECONDS=60
```

The AWS SDK credential chain is the only credential mechanism. App Runner uses
its runtime role. No AWS access key belongs in repository configuration.

`enable_nova_model=true` in the App Runner runtime Terraform contract adds only
`bedrock:InvokeModel` for the selected Nova 2 Lite geographic inference profile
and permits its Nova 2 Lite foundation model only when Bedrock evaluates it
through that exact profile. The default is `false`, so applying the existing
runtime contract cannot silently begin sending customer data to a model.

The `us.` inference profile can route within the US geography. A different
geographic profile requires an explicit configuration and residency review.

## Evidence and failure behavior

Each successful call records the provider, model, prompt version, input digest,
data policy, token usage, latency, finish reason, provider request ID, output
digest, and validation result. Raw prompts and model output are not copied into
audit metadata. The workload intent continues to retain the customer's original
request as existing product data.

The Bedrock SDK does not retry transport calls; each request's connect and read
timeouts share the caller's remaining deadline. The JSON repair uses that same
deadline. Terraform semantic repair uses separate, uniquely identified model
requests, and aggregates token usage, known cost, latency, retry count and
digest-only evidence across them. If generation fails, ProductService persists
the safe aggregate usage/evidence before returning a redacted error. Content
filtering, timeouts, incomplete output, digest mismatches, and repeated schema
failures fail closed. Terraform proposal generation bypasses fixture fallback
even if a fallback gateway is configured; fixture output is never accepted as a
repaired Bedrock proposal. Fixture fallback elsewhere is available only when
`DAVDEPLOY_MODEL_FALLBACK=fixture` is explicitly set; its response remains
labelled `SIMULATED` and never masquerades as Nova evidence.

Pricing estimates remain unset unless both current per-million-token rates and a
catalog version are configured. This prevents stale model-memory pricing from
being presented as an AWS charge.

## Activation gate

Before enabling Nova for a tenant:

1. confirm Bedrock access and the geographic processing boundary;
2. set a reviewed pricing catalog version and budget alarms;
3. run the offline intent benchmark plus an authorized, capped live evaluation;
4. review prompt-injection, unsupported-request, and schema-failure results;
5. enable a small tenant allowlist before a wider rollout.

PR #81 completed a capped live integration evaluation in the pilot account:
two fixed synthetic cases passed with 700 combined billed tokens and no retained
prompt or response content. This satisfies the basic transport and response-
shape check only. The broader benchmark, current pricing catalog and tenant
allowlist gates remain required before customer activation.

References:

- [Nova 2 Lite model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-2-lite.html)
- [Nova 2 Converse API](https://docs.aws.amazon.com/nova/latest/nova2-userguide/using-converse-api.html)
- [Geographic cross-Region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/geographic-cross-region-inference.html)
