# ticket424 — price the bounded Aurora PostgreSQL Serverless v2 plan

PR: https://github.com/Bepoadewale/davdeploy/pull/424
Branch: `feat/aurora-serverless-pricing-424`

## Problem / goal

The Nova cost evaluator currently blocks `aws_rds_cluster` and `aws_rds_cluster_instance` as unpriced. The checked-in `modules/aurora-postgres` root provisions an Aurora PostgreSQL Serverless v2 writer, so the relational-data scenario cannot become approval-eligible even when the rest of the proposal is supported. Add a narrowly bounded, assumption-bound regional price calculation for that exact shape. Unsupported cluster modes, readers, storage modes, unknown cost drivers, and missing usage assumptions must continue to block approval.

## Current repo state

- Backend `main` is `8c7f1deab9e9b9865a25d0fffaf87be2066b8ea4` (PR #423); PR #422 role-profile verification is source-only and not deployed.
- The hosted control plane remains at PR #420. No customer Nova plan or workload has been applied or certified.
- `generated_plan_pricing.py` covers selected MySQL RDS, but not the `modules/aurora-postgres` cluster or Serverless v2 capacity.
- AWS pricing must come from exact regional Price List products; customer-provided quantities may be persisted, but prices and SKU identifiers must never come from model output.

## Research / references used

- `apps/api/src/davdeploy/generated_plan_pricing.py`
- `apps/api/src/davdeploy/domain.py`
- `apps/api/src/davdeploy/module_implementations.py`
- `infrastructure/terraform/modules/aurora-postgres/main.tf`
- `tests/test_generated_plan_pricing.py`
- Official AWS Aurora pricing: https://aws.amazon.com/rds/aurora/pricing/
- Official AWS Price List API documentation: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-price-list-query-api.html
- Official RDS-managed secret behavior and billing: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/rds-secrets-manager.html
- Official AWS Secrets Manager pricing: https://aws.amazon.com/secrets-manager/pricing/
- Official Aurora data-transfer pricing: https://aws.amazon.com/rds/aurora/pricing/#Data_Transfer
- Official Serverless v2 capacity configuration: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2.setting-capacity.html
- Official Aurora backup storage usage: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-storage-backup.html
- Read-only AWS Price List Query `GetProducts` in `us-east-1` on 2026-11-17 returned one exact product per requested cost component. SKU and rate evidence: Serverless v2 `AVKW7ZJP8D72HNQC`, `$0.12/ACU-Hr`; Aurora Standard storage `7GYUVAA992PFJPCB`, `$0.10/GB-Mo`; Standard I/O `7JDSZP38DMKT9B86`, `$0.0000002/IO`; backup `AYEW6PNFPJSSTGH7`, `$0.021/GB-Mo`; Secrets Manager stored secret `BJ3PQ9BYGU6P632F`, `$0.40/secret-month`; API requests `4MDZ5VNEJPMUTG9B`, `$0.000005/request`. Products were effective 2026-11-01; RDS products were published 2026-11-13 and Secrets Manager products 2026-11-11. These are current catalog values, not a customer quote or bill.
- AWS's Aurora pricing page says cross-AZ database/client transfer can incur regional transfer charges. The exact transfer product returned a zero rate while the published Aurora/EC2 price pages describe billable transfer, so the implementation requires explicit zero bounds for inter-AZ, cross-region, and internet transfer; any nonzero maximum blocks approval until reconciled with an authoritative rate.

## Work planned for the PR

- Define trusted usage assumptions for Aurora storage, standard I/O, billable backup overage, managed-secret API requests, and all transfer classes.
- Add exact regional Price List lookups for Serverless v2 ACU-hours, Aurora Standard storage, I/O requests, backup overage, managed-secret storage, and API requests.
- Price only one Aurora PostgreSQL Serverless v2 writer with explicitly bounded capacity and no extra readers or unsupported options.
- Bind assumptions and pricing lines into canonical evidence, approval validation, and safe summaries while retaining old manifest compatibility.
- Add positive and fail-closed tests, update the evidence matrix/backlog, and record all validation.

## Acceptance criteria

- [x] Only the explicitly supported Aurora PostgreSQL Serverless v2 configuration receives a price.
- [x] Every billable capacity, storage, I/O, backup, managed-secret storage, and secret API cost is modeled with a timestamped regional AWS Price List product and explicit quantity range.
- [x] The RDS-managed secret and its API requests are included; non-zero inter-AZ, cross-region, or internet transfer stays blocked until priced.
- [x] Unknown/missing assumptions and unsupported configuration fail closed before price approval.
- [x] Pricing assumptions are trusted persisted context, digest-bound, canonical, and not model-authored rates.
- [x] Legacy pricing evidence manifests remain readable and current evidence remains approval-verifiable.
- [x] Focused tests and required repository checks pass.
- [x] Documentation conventions and `git diff --check` pass.
- [x] No AWS resource, Terraform state, feature gate, customer credential, or workload is changed.

## Acceptance status

PR #424 remains open and in draft. The bounded source implementation, focused
tests, full repository verification, and final-head CI are complete. This source
is not merged or deployed.

- [x] Only one private Aurora PostgreSQL Serverless v2 Standard writer shape with the checked-in capacity settings is priced; unsupported topology and unknown price-driving fields remain ineligible.
- [x] Compute, storage, Standard I/O, billable backup overage, the managed secret, and secret API requests use exact regional catalog products with SKU, product digest, publication time, effective time, and bounded quantities. Inter-AZ, cross-region, and internet transfer ranges above zero stay blocked.
- [x] Missing, mixed, stale, or invalid usage assumptions fail closed; assumption quantities remain customer-provided persisted context, never model-authored rates.
- [x] Current evidence is canonical and approval-verifiable, and legacy RDS pricing evidence remains parseable.
- [x] Full repository verification passes (`make verify PY=.venv-pr399/bin/python`, 1,291 tests, Ruff, OpenAPI snapshot, and Compose config).
- [x] Final-head CI run [44066670092](https://github.com/Bepoadewale/davdeploy/actions/runs/44066670092) passed all seven checks for implementation commit `5b4ea952d05bee8f5f1275174fc5951d0959444c`.
- [x] Documentation conventions and `git diff --check` pass.
- [x] No AWS resource, Terraform state, feature gate, customer credential, or workload was changed.

## Tests / validation performed

Focused pricing and usage-assumption tests passed (108). Full repository
verification passed: `make verify PY=.venv-pr399/bin/python` (1,291 tests),
Ruff, OpenAPI snapshot check, and `docker compose config --quiet`. The generated
OpenAPI snapshot includes the optional Aurora usage bounds. Documentation
conventions and `git diff --check` passed. Final-head CI run `44066670092`
passed all seven checks for implementation commit `5b4ea952d05bee8f5f1275174fc5951d0959444c`.

## Evidence files produced

No customer workload is run by this source-only pricing change. The package
evidence is recorded here; no customer-workload `docs/test/test424.md` is
required.

## Boundaries

- Do not run Terraform or mutate AWS.
- Do not change hosted feature gates or deploy the control plane.
- Do not claim pricing support for Aurora unless every material modeled cost is included and its limits remain explicit.
- Preserve `--only-show-errors`, `.venv-pr399/`, and the retained clean-room evidence.

## Follow-up work

After merge and a separately authorized hosted release, exercise an authenticated customer plan with this exact Aurora shape and real regional usage assumptions. Hosted apply, health, recovery, and cleanup remain separate acceptance gates.
