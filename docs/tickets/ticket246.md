# ticket246 — AWS certification harness

PR: [#246](https://github.com/Bepoadewale/davdeploy/pull/246)

Branch: `feat/aws-certification-harness`

## Problem / goal

Create a bounded runner for disposable composed AWS certification roots.

## Current repo state

The lifecycle compiler and scenario catalogue are merged in PR #245.

## Research / references used

Existing module-validation roots and PR #244 evidence.

## Work planned for the PR

Add explicit scenario-to-root orchestration and evidence capture.

## Acceptance criteria

- [x] No apply is possible without exact disposable-test confirmation.
- [x] Scenario evidence is persisted as JSON outside source control by caller choice.
- [ ] Real scenario executions are recorded in a later evidence PR.

## Acceptance status

Implementation in progress.

## Tests / validation performed

`pytest tests/test_certify_aws_scenario.py -q`

## Evidence files produced

`docs/test/test246.md`

## Boundaries

The script never receives customer credentials or arbitrary Terraform input.

## Follow-up work

Add service-specific readiness probes and prerequisite fixtures.
