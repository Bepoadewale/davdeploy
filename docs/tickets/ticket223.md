# ticket223 — Governed adapter catalogue and maintenance cadence

PR: [#223 — docs: define governed adapter catalogue and cadence](https://github.com/Bepoadewale/davdeploy/pull/223)

Branch: `docs/adapter-catalogue-cadence`

## Problem / goal

Document the AWS workload patterns DavDeploy can reason about, distinguish
planning from real execution, define safe composition rules, and establish a
repeatable adapter-maintenance cadence.

## Current repo state

- `execution_profiles.py` exposes nine bounded code-level AWS profiles.
- App Runner is the only pattern with real customer-workload pilot create,
  health and destroy evidence.
- Other profiles and adjacent workload families must not be represented as
  live deployment features.

## Research / references used

- AWS Modern Applications: <https://aws.amazon.com/modern-apps/>
- AWS workload decision guide: <https://docs.aws.amazon.com/decision-guides/latest/decision-guides/modern-apps-strategy-on-aws-how-to-choose.html>
- AWS cloud design patterns: <https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/>
- AWS serverless agentic-AI guidance: <https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-serverless/designing-serverless-ai-architectures.html>
- AWS Well-Architected Framework: <https://docs.aws.amazon.com/wellarchitected/latest/framework/>

## Work planned for the PR

- [x] Add a versioned catalogue with capability labels.
- [x] Cover the important web, API, container, VM, Kubernetes, data, event,
  batch, AI/ML, GPU and hybrid patterns as bounded families.
- [x] Define composition and adapter promotion requirements.
- [x] Record continuous, monthly, quarterly and per-execution cadence.
- [x] Correct profile-execution documentation to match current pilot evidence.

## Acceptance criteria

- [x] The document does not claim all AWS services or catalogue rows are live.
- [x] The only real pilot capability is labelled accurately.
- [x] AI is prevented from expanding the bounded execution surface.
- [x] The next practical adapter priorities are explicit.
- [x] Documentation and focused registry validation pass.

## Acceptance status

Implementation and validation are complete.

## Tests / validation performed

Documentation-only validation is recorded in `docs/test/test223.md`.

## Evidence files produced

`docs/test/test223.md`

## Boundaries

This PR adds no deployment adapter, cloud permission, infrastructure resource
or provider integration. Each pilot adapter remains a separate reviewed PR and
requires its own real-AWS evidence.

## Follow-up work

Prioritise an ECS Fargate adapter only when a customer needs a multi-container
or API-worker workload and it can meet the documented pilot gate.
