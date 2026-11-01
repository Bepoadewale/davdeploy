# ticket224 — Establish composed infrastructure plan foundation

PR: [#224](https://github.com/Bepoadewale/davdeploy/pull/224)

Branch: `feat/composed-plan-foundation`

## Problem / goal

Replace the planner's internal one-profile-only representation with the
foundation for a composed architecture plan. Customers continue to describe an
outcome in natural language; they do not choose cloud resources.

## Current repo state

The AWS planner selects one of nine profiles and returns profile components.
The broader adapter catalogue is documentation/registry scope, while App
Runner is the only customer workload pattern with real pilot deployment
evidence.

## Research / references used

- [Automatic infrastructure programme](../product/automatic-infrastructure-program.md)
- [Governed workload-adapter catalogue](../architecture/adapter-catalogue.md)
- AWS [Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/)
- AWS [modern application decision guide](https://docs.aws.amazon.com/decision-guides/latest/decision-guides/modern-apps-strategy-on-aws-how-to-choose.html)

## Work planned for the PR

- Add typed selected-module records to architecture plans.
- Add a deterministic internal module registry and dependency composer.
- Preserve current profile selection and all existing safety boundaries.
- Record PRs #224–#232, their scopes and dependencies in the repository.

## Acceptance criteria

- [x] A plan can contain a dependency-ordered internal module graph.
- [x] Existing profile decisions remain backwards compatible.
- [x] Customer-facing inputs never become a resource picker.
- [x] The nine-PR programme and context are documented.
- [x] Focused tests and repository validation pass.

## Acceptance status

Implementation and focused validation are complete.

## Tests / validation performed

Recorded in `docs/test/test224.md`.

## Evidence files produced

`docs/test/test224.md`

## Boundaries

This PR does not add an AWS permission, Terraform apply path, customer-cloud
resource, or model execution authority. A module graph is planning data; only
separately implemented and evidenced modules can be automatically deployed.

## Follow-up work

PR #225 uses Bedrock/repository signals to populate capability requirements.
PRs #226–#230 implement module families; #231 supplies live cost/operations;
#232 completes commercial launch surfaces.
