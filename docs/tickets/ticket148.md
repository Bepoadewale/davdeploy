# ticket148: Reconcile generated legacy customer execution artifacts

PR: #148
Branch: fix/reconcile-legacy-result-uri

## Problem / goal

Safely ingest a result from a run created before the explicit result URI field
was persisted.

## Current repo state

The customer foundation apply completed and its immutable result artifact
exists. The run was created before ticket147, so the generated URI exists only
inside its durable execution context.

## Research / references used

- The immutable completed customer runner artifact.
- Current and pre-ticket147 execution record formats.

## Work planned for the PR

- Prefer the current top-level result URI.
- Fall back only to the control-plane-generated legacy execution URI.
- Add regression coverage for legacy result ingestion.

## Acceptance criteria

- [x] New records retain their explicit URI preference.
- [x] Legacy generated URIs can be reconciled without Terraform re-execution.
- [ ] Focused tests and required CI pass.
- [ ] The live customer output is ingested.

## Acceptance status

Implementation is complete; validation, release, and live ingestion remain.

## Tests / validation performed

- Pending focused tests, documentation convention checks, and CI.

## Evidence files produced

- Final customer lifecycle evidence will be recorded in `docs/test/test130.md`.

## Boundaries

- The fallback accepts only a URI produced by the pre-existing control-plane
  execution context.
- It does not rerun Terraform or make a new customer-cloud request.

## Follow-up work

- Release and reconcile the completed customer foundation output.
