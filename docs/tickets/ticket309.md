# ticket309 Validate generated AWS resource schemas

PR: #309
Branch: feat/nova-provider-schema-check

## Problem / goal

Reject generated AWS resources whose types, arguments, required fields, nested blocks, outputs or typed references conflict with the selected Terraform AWS provider schema.

## Current repo state

PR #308 now emits the versioned typed proposal and trusted Terraform reference compilation. It remains plan-only. There is no generic hosted apply path. Terraform provider schemas are available locally from an initialized root, but their release version must be bound to the provider lockfile by the trusted caller.

## Research / references used

- Terraform provider schema command: https://developer.hashicorp.com/terraform/cli/commands/providers/schema
- Terraform provider schema JSON format: https://developer.hashicorp.com/terraform/cli/commands/providers/schema
- Provider schema is configuration-shape evidence, not permission, quota, cost, service readiness or successful deployment.

## Work planned for the PR

Implement deterministic validation against caller-supplied provider schema data. Reject missing resource types, unknown or missing required fields, computed-only writes, invalid primitive/nested shapes, plaintext sensitive inputs, undeclared outputs, incorrect reference type/sensitivity and unsupported nesting modes.

## Acceptance criteria

- [x] Resource types and fields are checked against supplied AWS provider schema.
- [x] Required arguments, computed-only fields and nested blocks are checked.
- [x] Sensitive values require declared typed references.
- [x] Provider outputs and typed references are checked against schema.
- [x] Provider schema format version may be pinned and checked separately from provider release version.
- [ ] Focused and required checks pass.
- [ ] Review is complete.

## Acceptance status

Implementation and focused tests pass locally. This validator is a reusable preflight component; it is not yet wired into the hosted runner or an actual Terraform plan.

## Tests / validation performed

Ruff passed. Focused test suite: .venv/bin/python -m pytest -q tests/test_generated_provider_validation.py, 8 passed. A read-only check validated a synthetic S3 bucket proposal against the locally installed AWS provider schema (1,526 resource schemas). No cloud mutation or customer workload occurred.

## Evidence files produced

No customer workload is exercised; no docs/test/test309.md is required.

## Boundaries

This schema check does not establish AWS authorization, quota availability, pricing, policy approval, customer approval, Terraform plan outcome, runtime health, recovery or cleanup. Provider release pinning and schema provenance must be supplied by the trusted runner from the lockfile; the schema format version is not the provider release version.

## Follow-up work

Bind the schema to the runner's exact lockfile/provider binary, run Terraform validate and plan in an isolated workspace, inspect actual plan JSON under policy, bind final approval to the saved plan, and then execute through the generic hosted worker.
