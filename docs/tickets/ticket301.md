# ticket301 — Add a gated DynamoDB table renderer

PR: #301 (draft)
Branch: `feat/gated-dynamodb-renderer`

## Problem / goal

Add one bounded, checked-in Terraform renderer for the `aws-nosql-data` module so natural-language plans can include a real DynamoDB table in a composed workload. Keep the renderer unavailable for ordinary customer execution until real lifecycle certification. The renderer must use pay-per-request billing, project-scoped identity and tags, point-in-time recovery, encryption at rest, and a deterministic partition key. Destruction must fail closed when the table contains items.

## Current repo state

Main is at `afd6736` after PR #300. The planner has a typed `aws-nosql-data` module contract (`table_name`, `table_arn`), but no customer lifecycle renderer. App Runner is the only renderer enabled for ordinary customer execution; S3 and Lambda/API remain disabled and require a separate hosted-certification gate. The readiness docs are being corrected to record PR #300 as merged and to capture this PR's current scope.

## Research / references used

- `apps/api/src/davdeploy/module_ports.py` for the existing NoSQL typed output contract.
- `apps/api/src/davdeploy/module_renderers.py` for disabled-by-default renderer registration and certification gating.
- `apps/api/src/davdeploy/cloud_execution.py` and `scripts/customer-workload-dispatcher.sh` for fixed renderer dispatch.
- `infrastructure/terraform/customer-workload-private-s3/` for account guard, project-scoped state, saved-plan digest and runner patterns.
- `infrastructure/terraform/modules/dynamodb-table/` for the existing reusable table module.
- [Terraform `aws_dynamodb_table` resource documentation](https://registry.terraform.io/providers/hashicorp/aws/5.100.0/docs/resources/dynamodb_table) for pay-per-request mode, encryption and point-in-time recovery.
- [DynamoDB Scan API](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_Scan.html) for bounded item-presence checks and pagination behavior.

## Work planned for the PR

- Add a customer-scoped DynamoDB root with account guard, deterministic table identity, tags, on-demand billing, encryption, point-in-time recovery, and explicit key schema.
- Add a fixed runner for plan, saved-plan apply, observe, destroy-plan, destroy-saved-plan and cleanup verification; bind state and evidence to connection/project/plan/run scopes.
- Check for items before destroy and refuse automatic deletion when any are present.
- Add typed output mapping for the declared table name and ARN, but no new customer input values.
- Register the renderer as disabled for ordinary customer execution and permit it only in explicit hosted certification mode.
- Add focused contract tests, Terraform validation, full verification, documentation reconciliation, PR-numbered evidence and a clean-room cycle.

## Acceptance criteria

- [x] Terraform root enforces expected AWS account and project-scoped tags/name/state.
- [x] Table uses on-demand billing, encryption at rest and point-in-time recovery.
- [x] Runner accepts only fixed operations/fields and uses an immutable saved plan with digest verification.
- [x] Observe validates the live table properties and exports only declared non-sensitive outputs.
- [x] Destroy is blocked unless a bounded check proves the table empty; cleanup verification confirms remote absence and empty Terraform state.
- [x] Renderer is unavailable to ordinary customer execution and only available through the explicit certification gate.
- [x] Focused and full local validation, clean-room cycle and documentation checks pass.
- [x] GitHub Actions run `41777364015` passes all seven required checks on the preceding committed revision; the final documentation update is revalidated by the current PR checks.
- [x] Final merge review confirms no unresolved feedback and a clean merge state.
- [x] Evidence will separate local configuration proof from real AWS lifecycle certification; this PR creates no AWS resources.

## Acceptance status

Implementation and local validation are complete; final PR CI and merge review remain.

## Tests / validation performed

- Focused tests — 100 passed.
- `make verify` — 505 passed, OpenAPI snapshot and Compose configuration passed; one existing Starlette/httpx deprecation warning.
- `scripts/terraform-validate.sh` — all configured Terraform roots initialized and validated, including the new DynamoDB root.
- `terraform -chdir=infrastructure/terraform/customer-workload-dynamodb validate` — passed.
- `GITHUB_PR_NUMBER=301 python3.12 scripts/check_doc_conventions.py`, shell syntax checks and `git diff --check` — passed.
- Executor package smoke test — package contains the DynamoDB runner, Terraform root, dispatcher and locked AWS provider selection.
- Clean-room at `64ca498`: bootstrap, smoke, API contract, customer-plan E2E, seed data, simple/complex/Day-2/degraded/policy/readiness demos, trace check and full `make verify` passed (505 tests, one existing deprecation warning).
- No AWS resources were created. The renderer stays disabled outside the certification gate.
- GitHub Actions run [41776876739](https://github.com/Bepoadewale/davdeploy/actions/runs/41776876739) — all seven required checks passed.
- Final merge review — GitHub reports `CLEAN`, no reviews, and no comments.

## Evidence files produced

`docs/test/test301.md` records local/clean-room validation and the no-AWS test boundary.

## Boundaries

No public enablement, arbitrary Terraform, caller-provided code/commands, cross-project state, table data ingestion, broad table permissions, destructive force deletion, hosted production apply, or live AWS customer table is in scope.

## Follow-up work

Run a controlled real AWS table lifecycle test with synthetic data and verified cleanup. Add a region-aware cost estimate for table requests, data storage and point-in-time recovery before customer routing. Add typed data-source-to-API bindings only with renderer-specific environment and IAM scoping. Do not enable customer execution based on Terraform validation alone.
