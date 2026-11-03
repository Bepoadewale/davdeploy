# ticket266 — Universal module renderer registry

PR: [#266](https://github.com/Bepoadewale/davdeploy/pull/266)

Branch: `feat/universal-module-dispatch`

## Problem / goal

Introduce one deterministic registry that maps a typed module identifier to a
checked-in renderer contract, rather than allowing profiles or requests to
select scripts directly.

## Current repo state

The module catalogue and module contracts are broad, but only the App Runner
workload renderer is executable in the customer runner.

## Research / references used

Existing module catalogue, module contracts, universal lifecycle work, and the
customer App Runner runner package.

## Work planned for the PR

Create a typed registry and a first renderer binding for the existing managed
application module. Unknown or unbound modules must remain non-executable.

## Acceptance criteria

- [x] Renderer selection is deterministic and module-id based.
- [x] Only checked-in renderer bindings are returned.
- [x] Unknown and unbound modules are rejected.
- [ ] Focused tests and full CI pass.

## Acceptance status

In progress.

## Tests / validation performed

`make lint && uv run pytest tests/test_module_renderers.py tests/test_cloud_execution.py -q` — 16 passed.

## Evidence files produced

No customer workload is created by this registry-only PR.

## Boundaries

This does not enable a module merely because a planning contract exists.

## Follow-up work

Add individual renderer bindings only with the module's Terraform, health,
rollback, destroy and real AWS certification evidence.
