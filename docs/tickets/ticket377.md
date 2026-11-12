# ticket377 — reject Nova intents outside infrastructure planning

PR: [#377](https://github.com/Bepoadewale/davdeploy/pull/377) (draft)
Branch: `feat/nova-intent-scope-guard-377`

## Problem / goal

The Nova intent contract extracts workload fields but has no explicit request
scope. A stock-advice or other unrelated request could be treated like a vague
infrastructure request and receive irrelevant deployment questions. DavDeploy
must give a clear out-of-scope response before creating an intent or any plan.
A request to deploy software in a financial domain remains in scope.

## Current repo state

- Backend `main` is PR #376 merge commit `6f15aaf23b4184d0ec46835f6e3e1237cf83250e`.
- Merged-main CI run `43184018244` passed all seven jobs.
- The Nova intent provider is schema constrained but previously had no
  explicit out-of-scope classification or user-facing refusal.
- Nova-generated proposals remain non-authoritative; this PR makes no AWS
  infrastructure or customer workload changes. Two bounded synthetic Bedrock
  inference calls are recorded in `docs/test/test377.md`.

## Research / references used

- `apps/api/src/davdeploy/intent.py`
- `apps/api/src/davdeploy/service.py` intent creation boundary
- `apps/api/src/davdeploy/main.py` intent API error mapping
- `tests/test_nova_intent.py` and `tests/test_product.py`
- [AWS Nova 2 Lite service card](https://docs.aws.amazon.com/ai/responsible-ai/nova-2-lite/overview.html),
  including its guidance to evaluate specific use cases and acknowledge prompt
  variation.

## Work planned for the PR

- Add a required typed request-scope field to the Nova intent schema.
- Instruct Nova to separate AWS workload infrastructure requests from
  unrelated advice, while keeping deployment of financial software in scope.
- Reject out-of-scope classification with a fixed, actionable API message
  before an intent is persisted.
- Pin the changed prompt as a new version and cover intent rejection,
  in-scope financial software, error mapping, and no-persistence behavior.

## Acceptance criteria

- [x] Intent schema requires an explicit infrastructure/out-of-scope result.
- [x] Out-of-scope requests produce a fixed client error and are not persisted.
- [x] Deploying a software workload in a financial domain remains in scope.
- [x] No generated plan or executor is invoked for an out-of-scope request.
- [x] Focused tests pass.
- [ ] `make verify` and isolated clean-room proof must be rerun after the final schema correction.
- [ ] Documentation conventions, current-head review, and final-head CI pass.
- [x] No AWS infrastructure or customer workload mutations occur; bounded
  Bedrock inference calls were used for synthetic classification checks.

## Acceptance status

- [x] Implementation and focused tests complete.
- [ ] Full verification and clean-room proof are pending on the final schema correction; PR review and final-head CI also remain outstanding.
- [x] No runtime/AWS/customer workload mutation is in scope or performed.

## Tests / validation performed

- Focused: `.venv/bin/python -m pytest -q tests/test_nova_intent.py tests/test_product.py` — 61 passed.
- Full: `make verify` — 1,048 tests passed; Ruff, Actions configuration,
  OpenAPI snapshot and Compose config checks passed.
- Isolated `make local-proof` passed at `4d28a71`; project containers are stopped
  and local validation artifacts are retained.

## Evidence files produced

- `docs/tickets/ticket377.md`
- `docs/test/test377.md`

## Boundaries

This change only scopes natural-language intent requests. The classification
is not authorization or policy approval. A false in-scope classification still
cannot bypass deterministic schema, plan, security, cost, approval, and
execution gates. It does not train or change Nova model weights.

## Follow-up work

Add direct model-evaluation cases for unrelated requests, adversarial prompt
injection, ambiguous questions, and supported small/large workload variants.
Continue hosted planning, pricing, exact-plan approval, and full customer
lifecycle work independently; do not claim a general-purpose assistant.
