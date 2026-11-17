# ticket427 — version Nova intent context provenance

PR: https://github.com/Bepoadewale/davdeploy/pull/427
Branch: `feat/nova-intent-context-provenance-427`

## Goal

Make the context recipe and original intent context identifiable in accepted Nova
intent evidence, including when schema repair adds later model requests.

## Current repo state

Backend `main` is `ae2358388cb36c14a270242ee11db82042e408c1`. It records the
Nova prompt version and request input digest, plus the validated proposal
version and digest. The initial request's context recipe has no explicit
version, and the final metadata's request digest can refer only to the last
repair request rather than identifying the original context consistently.

PR #399 remains open and draft. This change is source-only and does not enable
customer plan or apply execution.

## Research / references

- `DAVDEPLOY_NOVA_GOAL.md`, package 3: record model, prompt, context, and
  proposal versions/digests and keep repair bounded.
- `apps/api/src/davdeploy/intent.py`
- `apps/api/src/davdeploy/model_gateway.py` (`model_input_digest`)
- `tests/test_nova_intent.py`

## Planned work

- Version the composed Nova intent context recipe.
- Record a canonical digest of the original context on accepted Nova metadata
  and workload provenance, independent of any schema repair request.
- Preserve the final per-call request digest and accepted-proposal digest.
- Keep fixture provenance distinct and avoid retaining raw customer context.

## Acceptance criteria

- [ ] Nova metadata includes the context version and original context digest.
- [ ] Schema repair preserves the same original context digest while retaining
  the final model-call request digest.
- [ ] A meaningful original-context change changes its digest.
- [ ] Workload provenance carries the context identity without raw prompt text.
- [ ] Fixture metadata does not claim Nova context provenance.
- [ ] Focused tests, full verification, docs conventions, and diff checks pass.
- [ ] All required GitHub checks pass on the final PR head.

## Validation / evidence

No validation has been performed for implementation yet. This package does not
perform a customer workload run, so no `docs/test/test427.md` file is required.

## Boundaries

No Bedrock/AWS calls, Terraform plan/apply, hosted runtime change, credential
issuance, customer workload, or feature-gate change is included. The context
digest is evidence for exact input identity, not proof of model correctness or
safe execution.

## Follow-up

Provider schema and official-document provenance, pinned real Nova evaluation,
prompt-injection coverage, and hosted customer lifecycle evidence remain
separate acceptance work.
