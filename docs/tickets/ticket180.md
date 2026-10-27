# ticket180 — Multi-cloud provider enablement gate

PR: [#180 — Document multi-cloud provider enablement boundary](https://github.com/Bepoadewale/davdeploy/pull/180)
Branch: `docs/multicloud-enablement-roadmap`

## Problem / goal

Record the concrete backend and operational work required before DavDeploy can enable a cloud provider beyond AWS, so a visible browser option is never mistaken for product capability.

## Current repo state

The product has an AWS-only connection contract, AWS discovery and pricing adapters, an AWS planner catalogue, an AWS Terraform renderer, and AWS-specific plan/execution records. The browser now shows Azure, Google Cloud, and other providers as coming soon.

## Research / references used

- `apps/api/src/davdeploy/domain.py` cloud-connection request contract.
- `apps/api/src/davdeploy/models.py` cloud-connection persistence model.
- `apps/api/src/davdeploy/planner.py` AWS planner.
- `apps/api/src/davdeploy/service.py` AWS customer-plan review and execution boundary.
- `apps/api/src/davdeploy/terraform_generation.py` AWS Terraform provider rendering.

## Work planned for the PR

- Add an explicit provider enablement gate to the provider-model architecture documentation.
- Add provider-by-provider expansion to the private product roadmap.

## Acceptance criteria

- [x] The documentation distinguishes visible future-provider UI from an enabled provider.
- [x] The complete identity, discovery, pricing, policy, planning, rendering, execution, observation, and operational requirements are recorded.
- [x] The roadmap links to the architecture gate.

## Acceptance status

Implemented and statically validated; pending CI and review.

## Tests / validation performed

Documentation-only change. `python scripts/check_doc_conventions.py` validates ticket conventions; no runnable behavior changed and no workload evidence file is required.

## Evidence files produced

None. No customer workload, cloud operation, or executable behavior changed.

## Boundaries

This PR enables no provider, modifies no API/schema/runtime, and does not create or change cloud resources.

## Follow-up work

Create a separate scoped implementation and validation PR for every provider, beginning only after the AWS customer path is fully proven.
