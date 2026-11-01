# ticket230 — Add specialised scale module contracts

PR: [#230](https://github.com/Bepoadewale/davdeploy/pull/230)

Branch: `feat/specialised-scale-modules`

## Problem / goal

Define bounded planning contracts for specialised Kubernetes, GPU/ML and private
connectivity workloads without presenting those provider decisions to customers.

## Current repo state

Core and advanced composed module contracts are available. Specialist workloads
need their own cost, quota, network and operational controls.

## Research / references used

- `docs/product/automatic-infrastructure-program.md`
- `docs/architecture/adapter-catalogue.md`

## Work planned for the PR

- Add typed resource, policy and health contracts for EKS, GPU/CPU inference
  and private connectivity.

## Acceptance criteria

- [x] Kubernetes requires reviewed GitOps controls.
- [x] GPU requires quota and cost controls.
- [x] Private connectivity requires private routing controls.
- [x] Focused validation passes.

## Acceptance status

Implementation and focused validation are complete.

## Tests / validation performed

Recorded in `docs/test/test230.md`.

## Evidence files produced

`docs/test/test230.md`

## Boundaries

No cloud execution or resources are created.

## Follow-up work

PRs #231 and #232 complete operations and commercial launch work.
