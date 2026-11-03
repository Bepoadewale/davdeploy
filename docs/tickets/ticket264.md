# ticket264 — Universal execution contract integration

PR: pending

Branch: `feat/universal-execution-contract`

## Problem / goal

Replace the execution request's hard-coded App Runner profile assumption with
an immutable, typed universal execution contract that supports composed module
graphs while retaining the existing deterministic authorization boundary.

## Current repo state

The compiler emits lifecycle operations and resource tags, but hosted run
creation still rejects every selected profile other than `aws-app-runner`.

## Research / references

Existing `universal_execution.py`, composed deployment tests, and the current
customer execution runner contract.

## Work planned

Add typed execution operation validation, dependency ordering, plan-level
command metadata, and service integration without accepting free-form cloud
commands or weakening existing authorization checks.

## Acceptance criteria

- [ ] The compiled graph is dependency ordered and immutable.
- [ ] Service execution records use the graph rather than a profile-only gate.
- [ ] Existing App Runner execution remains compatible.
- [ ] Focused tests and full CI pass.

## Acceptance status

In progress.

## Validation performed

Pending implementation.

## Evidence files

No AWS workload is created by this contract-only PR.

## Boundaries

No model or browser receives shell, Terraform, cloud-admin, or secret access.

## Follow-up work

Each module needs its own deterministic renderer and controlled real AWS
certification before its cloud operation can be enabled.
