# ticket247 — Low-overhead Terraform run monitoring

PR: [#247](https://github.com/Bepoadewale/davdeploy/pull/247)

Branch: `feat/terraform-run-monitor`

## Problem / goal

Provide local PID, log and registry tracking for Terraform applies without busy polling.

## Current repo state

Disposable certification runs use Terraform roots but do not share a reusable monitor.

## Research / references used

Personal Codex long-running-operation instructions and Terraform state isolation rules.

## Work planned for the PR

Add a bounded monitor CLI and regression test.

## Acceptance criteria

- [x] One process has one run record and log.
- [x] Concurrent mutation of the same root is refused.
- [x] Credentials are never written to registry metadata.

## Acceptance status

Implementation in progress.

## Tests / validation performed

`pytest tests/test_terraform_run_monitor.py -q`

## Evidence files produced

`docs/test/test247.md`

## Boundaries

The monitor is local tooling, not customer execution authority.

## Follow-up work

Use this monitor for future controlled Terraform runs.
