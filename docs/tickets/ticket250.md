# ticket250 — Real workload certification evidence

PR: [#250](https://github.com/Bepoadewale/davdeploy/pull/250)

Branch: `test/real-workload-certifications`

## Problem / goal

Add bounded health-evidence capture for real certification workloads.

## Current repo state

Infrastructure lifecycle tests exist, but application health evidence needs a reusable helper.

## Research / references used

Certification factory and universal execution contracts.

## Work planned for the PR

Add an HTTP health-evidence helper and record controlled workload validation.

## Acceptance criteria

- [x] Health checks record status and bounded response evidence.

## Acceptance status

Implementation in progress.

## Tests / validation performed

Pending focused test.

## Evidence files produced

`docs/test/test250.md`

## Boundaries

The helper makes no deployment mutation.

## Follow-up work

Run each representative workload through readiness, rollback and cleanup.
