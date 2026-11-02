# ticket249 — Certification evidence records

PR: [#249](https://github.com/Bepoadewale/davdeploy/pull/249)

Branch: `feat/certification-evidence-records`

## Problem / goal

Prevent resource-only Terraform success from being treated as workload certification.

## Current repo state

Disposable resource lifecycle runs are recorded; workload readiness evidence is incomplete.

## Research / references used

PR #244 and controlled certification scenario definitions.

## Work planned for the PR

Add typed scenario status aggregation.

## Acceptance criteria

- [x] Readiness, rollback and cleanup are required for certification.

## Acceptance status

Implementation in progress.

## Tests / validation performed

`pytest tests/test_certification_evidence.py -q`

## Evidence files produced

`docs/test/test249.md`

## Boundaries

No scenario is marked certified solely from Terraform apply/destroy.

## Follow-up work

Execute and record real workload readiness tests.
