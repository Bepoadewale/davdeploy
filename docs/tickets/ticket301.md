# ticket301 — Add a gated DynamoDB table renderer

PR: pending
Branch: `feat/gated-dynamodb-renderer`

## Problem / goal

Add one bounded, checked-in Terraform renderer for the `aws-nosql-data` module so natural-language plans can include a real DynamoDB table in a composed workload. Keep the renderer unavailable for ordinary customer execution until real lifecycle certification. The renderer must use pay-per-request billing, project-scoped identity and tags, point-in-time recovery, encryption at rest, and a deterministic partition key. Destruction must fail closed when the table contains items.

## Current repo state

Main is at `afd6736` after PR #300. The planner has a typed `aws-nosql-data` module contract (`table_name`, `table_arn`), but no customer lifecycle renderer. App Runner is the only renderer enabled for ordinary customer execution; S3 and Lambda/API remain disabled and require a separate hosted-certification gate. The readiness docs still refer to pre-#300 main and will be reconciled in this PR.

## Research / references

- `apps/api/src/davdeploy/module_ports.py` for the existing NoSQL typed output contract.
- `apps/api/src/davdeploy/module_renderers.py` for disabled-by-default renderer registration and certification gating.
- `apps/api/src/davdeploy/cloud_execution.py` and `scripts/customer-workload-dispatcher.sh` for fixed renderer dispatch.
- `infrastructure/terraform/customer-workload-private-s3/` for account guard, project-scoped state, saved-plan digest and runner patterns.
- `infrastructure/terraform/modules/dynamodb-table/` for the existing reusable table module.
- AWS DynamoDB Terraform provider resource documentation and AWS guidance on on-demand billing, encryption, point-in-time recovery and table deletion semantics.

## Work planned

- Add a customer-scoped DynamoDB root with account guard, deterministic table identity, tags, on-demand billing, encryption, point-in-time recovery, and explicit key schema.
- Add a fixed runner for plan, saved-plan apply, observe, destroy-plan, destroy-saved-plan and cleanup verification; bind state and evidence to connection/project/plan/run scopes.
- Check for items before destroy and refuse automatic deletion when any are present.
- Add typed output mapping for the declared table name and ARN, but no new customer input values.
- Register the renderer as disabled for ordinary customer execution and permit it only in explicit hosted certification mode.
- Add focused contract tests, Terraform validation, full verification, documentation reconciliation, PR-numbered evidence and a clean-room cycle.

## Acceptance criteria

- [ ] Terraform root enforces expected AWS account and project-scoped tags/name/state.
- [ ] Table uses on-demand billing, encryption at rest and point-in-time recovery.
- [ ] Runner accepts only fixed operations/fields and uses an immutable saved plan with digest verification.
- [ ] Observe validates the live table properties and exports only declared non-sensitive outputs.
- [ ] Destroy is blocked when the table contains any items; cleanup verification confirms both remote absence and empty Terraform state.
- [ ] Renderer is unavailable to ordinary customer execution and only available through the explicit certification gate.
- [ ] Focused and full validation, clean-room cycle, documentation and CI pass.
- [ ] Evidence clearly separates local configuration proof from real AWS lifecycle certification; no AWS resource is created by this PR unless an explicit controlled test is documented.

## Validation performed

Bootstrap commit only; no substantive implementation yet.

## Evidence files

`docs/test/test301.md` will record local/clean-room validation and any explicit AWS test boundary.

## Boundaries

No public enablement, arbitrary Terraform, caller-provided code/commands, cross-project state, table data ingestion, broad table permissions, destructive force deletion, hosted production apply, or live AWS customer table is in scope.

## Follow-up

Run a controlled real AWS table lifecycle test with synthetic data and verified cleanup. Add typed data-source-to-API bindings only with renderer-specific environment and IAM scoping. Do not enable customer execution based on Terraform validation alone.
