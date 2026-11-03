# PR #289: Validate durable lifecycle dependency graphs

## Goal

Strengthen the trusted execution boundary so durable lifecycle work is accepted only when its module graph is complete, unambiguous, and ordered consistently with its operation.

## Current state

The universal plan compiler validates identifiers and dependencies when an approved plan is first compiled. The CodeBuild boundary separately reloads serialized lifecycle work and resolves fixed renderer bindings, but should independently reject malformed or reordered persisted graphs.

## Research and references

- `apps/api/src/davdeploy/universal_execution.py`
- `apps/api/src/davdeploy/cloud_execution.py`
- `tests/test_cloud_execution.py`
- Product rule: only typed, checked-in renderer work may cross the execution boundary.

## Planned work

1. Validate lifecycle graph identity, dependency references, duplicate/self dependencies, operation consistency, cycles, and dependency ordering at the trusted execution boundary.
2. Add focused positive and adversarial contract tests.
3. Update the composed-execution goal and readiness matrix only if the implementation status changes; do not claim multi-module execution is enabled.

## Acceptance criteria

- [ ] Invalid or ambiguous graphs fail before any renderer is selected or subprocess can run.
- [ ] Valid dependency-ordered work remains accepted for forward and reverse operations.
- [ ] No arbitrary command or provider input is introduced.
- [ ] Focused tests and full required CI pass.
- [ ] Evidence and limitations are recorded accurately.

## Validation

Pending implementation.

## Boundaries and follow-up

This PR validates serialized graph integrity; it does not add multi-module scheduling, execute customer graphs, or enable additional renderers. Durable scheduling and composed AWS certification remain follow-up work.
