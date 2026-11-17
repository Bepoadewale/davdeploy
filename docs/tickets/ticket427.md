# ticket427 — version Nova intent context provenance

PR: https://github.com/Bepoadewale/davdeploy/pull/427
Branch: `feat/nova-intent-context-provenance-427`

## Problem / goal

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

## Research / references used

- `DAVDEPLOY_NOVA_GOAL.md`, package 3: record model, prompt, context, and
  proposal versions/digests and keep repair bounded.
- `apps/api/src/davdeploy/intent.py`
- `apps/api/src/davdeploy/model_gateway.py` (`model_input_digest`)
- `tests/test_nova_intent.py`

## Work planned for the PR

- Version the composed Nova intent context recipe.
- Record a canonical digest of the original context on accepted Nova metadata
  and workload provenance, independent of any schema repair request.
- Preserve the final per-call request digest and accepted-proposal digest.
- Keep fixture provenance distinct and avoid retaining raw customer context.

## Acceptance criteria

- [x] Nova metadata includes the context version and original context digest.
- [x] Schema repair preserves the same original context digest while retaining
  the final model-call request digest.
- [x] A meaningful original-context change changes its digest.
- [x] Workload provenance carries the context identity without raw prompt text.
- [x] Fixture metadata does not claim Nova context provenance.
- [x] Focused tests, full verification, docs conventions, and diff checks pass.
- [x] All seven required GitHub checks pass on final head `dfa6ae6` in run
  `44189957814`.

## Acceptance status

Implementation is complete and locally verified. All seven required checks
passed on final PR head `dfa6ae6` in run `44189957814`. The PR remains draft
pending final review.

## Tests / validation performed

`make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python`
passed: 1,304 tests, Ruff, Actions configuration, OpenAPI, and Compose checks.
The focused Nova intent suite passed again after the final assertion (23 tests),
and focused Ruff, docs conventions, and `git diff --check` passed. An initial
docs-convention run caught a ticket-heading mismatch, which was corrected before
the passing run. No customer workload run is part of this package.

## Evidence files produced

- `docs/tickets/ticket427.md`
- No `docs/test/test427.md` is required because no customer workload was run.

## Boundaries

No Bedrock/AWS calls, Terraform plan/apply, hosted runtime change, credential
issuance, customer workload, or feature-gate change is included. The context
digest is evidence for exact input identity, not proof of model correctness or
safe execution.

## Follow-up work

Provider schema and official-document provenance, pinned real Nova evaluation,
prompt-injection coverage, and hosted customer lifecycle evidence remain
separate acceptance work.
