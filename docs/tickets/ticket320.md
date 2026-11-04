# ticket320 — Bound semantic repair for Nova Terraform proposals

PR: #320 https://github.com/Bepoadewale/davdeploy/pull/320  
Branch: `feat/nova-semantic-repair-320`  
Base at start: `b8fd531` (`docs: map Nova capabilities to execution evidence (#319)`)

## Problem / goal

`NovaTerraformGenerator` makes one structured call. If Nova returns a schema-
invalid proposal or changes trusted source revision, context digest, or region,
generation stops without a bounded correction opportunity. Add a tightly
bounded semantic repair loop that sends only sanitized validation codes and
allowlisted field paths back to Nova. Trusted input and its digest remain
unchanged, fixture fallback remains rejected, and no tools or credentials are
added.

## Current repo state

- `NovaTerraformGenerator` validates the model result using
  `GeneratedDeploymentProposal` and `validate_generation_context`.
- `BedrockNovaGateway` locally validates structured JSON and already sums token
  usage, estimated cost, and JSON-repair retry counts for its one optional JSON
  repair call.
- `FallbackModelGateway` can return fixture output after a provider error; the
  generator rejects any response whose provider is not Bedrock.
- The generator's request digest must identify the complete serialized model
  document for `BedrockNovaGateway`, while the proposal `context_digest` remains
  the separate trusted generation-context digest used by saved-plan artifacts.
- No live Bedrock calls or AWS mutations are part of this PR.

## Research / references used

- `apps/api/src/davdeploy/terraform_generation.py`
- `apps/api/src/davdeploy/nova_contract_generation.py`
- `apps/api/src/davdeploy/generated_deployment_contract.py`
- `apps/api/src/davdeploy/model_gateway.py`
- `apps/api/src/davdeploy/contracts.py`
- `tests/test_terraform_generation.py`
- `tests/test_queue_and_model_gateway.py`
- PR #314 saved-plan approval contract and
  `tests/test_generated_plan_review.py`

## Work planned for the PR

- Bound semantic attempts and an overall elapsed-time budget; adjust every
  request timeout to the remaining budget and stop before further calls once
  the deadline is exhausted.
- Retry only proposal schema and trusted-context validation failures.
- Send Nova at most a small capped list of Pydantic error codes and canonical
  schema field paths. Never include exception messages, input values, raw model
  output, customer content, or credentials in repair feedback.
- Preserve the original source revision and trusted generation-context digest
  in every attempt; bind the request input digest to the full current document.
- Aggregate token usage, known costs, latency, retry counts, and evidence across
  semantic calls, retaining gateway-reported JSON repair totals.
- Reject fixture/provider fallback and return a safe actionable error when the
  attempt or time bound is reached.
- Add deterministic fixture tests for success after repair, stop at the cap,
  trusted-context preservation, safe feedback, cost/usage aggregation, JSON
  repair accounting, and complete-document digest enforcement.

## Acceptance criteria

- [ ] Semantic repair has a strict small maximum attempt count and time bound.
- [ ] Repair input contains only allowlisted validation codes and canonical
  schema paths, never unsafe error contents.
- [ ] Original trusted source revision and context digest remain fixed across
  all semantic attempts and are validated on final output.
- [ ] Invalid output stops at the attempt cap with a safe actionable error.
- [ ] Fixture fallback output is rejected and never accepted as repaired
  output.
- [ ] Aggregated response usage includes all semantic calls and their
  gateway-reported JSON repairs; unknown cost remains unknown.
- [ ] Bedrock validates the digest of the complete serialized request document
  while proposal binding keeps the existing trusted-context digest.
- [ ] Focused tests, formatting/lint, docs conventions, and required GitHub CI
  pass; no AWS calls or mutations occur.

## Validation performed

Pending implementation.

## Evidence files

- `docs/test/test320.md` (fixture/local validation only; no real Bedrock or AWS
  execution)
- `docs/tickets/ticket320.md`

## Boundaries

This PR does not change runner, execution policy, artifact persistence, service
authorization, approval behavior, Terraform execution, or AWS infrastructure.
Nova remains a proposal generator only. No local fixture is accepted as a
repaired Bedrock proposal.

## Follow-up work

The generated proposal remains plan-only until the separate hosted plan worker
and exact saved-plan review path are connected. Real provider behavior must be
validated separately before any deployment capability is enabled.
