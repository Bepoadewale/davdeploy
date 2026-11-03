# ticket259 — Bind universal module graph to approved execution

PR: Pending creation.

Branch: `feat/universal-execution-service-contract`

## Problem / goal

Persist the selected internal module graph in the immutable customer review and
bind it to the exact approved digest at cloud-execution request time.

## Current repo state

Lifecycle compiler functions existed, but the hosted customer-review and cloud
execution path did not use them.

## Research / references used

Existing revision digest checks, universal-execution contract and cloud-run
evidence model.

## Work planned for the PR

Preserve selected modules in the revision, compile their exact graph against
the approved digest when an execution run is created, and persist the graph
and ownership tags in durable evidence.

## Acceptance criteria

- [x] Immutable customer reviews include the internal module graph.
- [x] Cloud-run evidence binds every module to the approved digest and owner.
- [x] Regression tests cover the persisted graph.

## Acceptance status

Complete locally; CI pending.

## Tests / validation performed

`48 passed` across customer review, cloud execution and lifecycle tests.

## Evidence files produced

`docs/test/test259.md`

## Boundaries

This wires the universal graph to the hosted control plane. It does not make
an unvalidated provider module executable.

## Follow-up work

Add module-specific executor adapters and real provider evidence for remaining
certification scenarios.
