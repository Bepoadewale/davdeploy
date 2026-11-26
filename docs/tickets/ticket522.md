# ticket522 — Bound Nova ECS Express actual-plan pricing

PR: #522
Branch: `feat/ecs-express-pricing-522`

## Problem / goal

The ECS Express renderer creates billable supporting services that do not
appear as separate Terraform resources. Its plan must remain ineligible for
approval until DavDeploy accounts for the service's compute, load balancer,
public IPv4, logs, image storage, and network usage with current regional rates
and trusted usage bounds.

## Current repo state

- Backend `main` includes the current private Batch lifecycle evidence.
- Draft PR #519 adds a default-off ECS Express renderer and fixed customer
  pilot root.
- Draft PR #520 adds the source-only actual-plan contract. It remains stacked
  on the current source baseline and does not enable dispatch.
- This PR is stacked on PR #520 so the price model and exact-plan contract can
  be reviewed as separate packages.
- AWS account `654654474502` was read-only verified. No AWS workload or hosted
  control-plane resource is changed by this package.

## Research / references used

- AWS ECS Express resources, sharing, and defaults:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-work.html
- AWS ECS Express availability and underlying-resource pricing:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html
- AWS ECS pricing:
  https://aws.amazon.com/ecs/pricing/
- AWS Fargate pricing and task billing granularity:
  https://aws.amazon.com/fargate/pricing/
- Application Load Balancer hourly and LCU pricing:
  https://aws.amazon.com/elasticloadbalancing/pricing/
- Public IPv4 pricing:
  https://aws.amazon.com/vpc/pricing/
- CloudWatch pricing:
  https://aws.amazon.com/cloudwatch/pricing/
- AWS data-transfer categories:
  https://docs.aws.amazon.com/cur/latest/userguide/cur-data-transfers-charges.html
- Current regional Price List products will be matched through the existing
  `AwsPriceListCatalog`; no customer-provided prices are accepted.

## Work planned for the PR

1. Add a strict, versioned trusted ECS Express usage-assumptions model bound
   to the exact service address. Include task starts/runtime, Application Load
   Balancer hours and LCU-hours, task and load-balancer public IPv4 address
   seconds, log ingestion/storage, internet egress, and cross-AZ transfer.
2. Carry the model through the persisted-revision boundary, pricing-context
   digest, evidence manifest and parser without invalidating older manifests;
   expose it through constraint updates and the versioned OpenAPI contract.
3. Price the one-service fresh-VPC pilot using exact regional AWS Price List
   matches for Fargate, Application Load Balancer, LCU, public IPv4, CloudWatch
   Logs, CloudWatch alarm, ECR storage, and data transfer.
4. Reuse existing ECR storage and CloudWatch Logs price catalog methods without
   double counting.
   Treat ACM, VPC, route tables, IAM, service-linked roles, and ECS orchestration
   as no-direct-charge only where official documentation supports that claim.
5. Keep pricing `INCOMPLETE` for missing, stale, mismatched, unsupported, or
   unbounded usage assumptions, shared load balancers, extra services, or
   unsupported cost-bearing resources.
6. Add regression tests for complete synthetic evidence, missing and malformed
   assumptions, extra services/resources, wrong regions, and catalog failure.
7. Preserve the default-off renderer and avoid AWS plans, mutations, or
   hosted-control-plane changes.

## Acceptance criteria

- [x] The price model accepts only the exact single ECS Express pilot shape and
  binds all usage assumptions to its exact planned service, log group, and
  ECR repository.
- [x] Every material billable supporting resource and variable usage dimension
  listed in the design document has a separate regional price line or causes
  an explicit incomplete finding.
- [x] Fargate minimum billing duration, partial ALB hours, hourly LCU usage,
  IPv4 address duration, CloudWatch log volume, transfer bounds, and ALB
  sharing behavior are represented correctly.
- [x] Price evidence includes exact regional SKU, product digest, published
  and effective timestamps, and remains bound to the trusted persisted
  assumptions and exact plan digest.
- [x] Missing or stale catalog evidence, stale assumptions, unknown resources,
  unsupported sharing, and malformed input cannot produce `COMPLETE` pricing.
- [x] Existing pricing manifest versions remain readable and canonical; new
  evidence uses a versioned strict shape.
- [x] Focused and full relevant tests, lint, docs conventions, and final-head CI
  pass. A full clean-room run is not applicable to this pricing-only change.
- [x] No AWS workload or hosted control-plane resource is changed; no Terraform
  plan/apply/destroy or state/lock operation is run.

## Acceptance status

Implementation and local validation are complete. Final-head CI run
`45894761342` passed all seven checks. The PR remains a draft, stacked on PR
#520.

## Tests / validation performed

- Read-only AWS identity and Batch definition inventory were reconciled in
  account `654654474502`.
- Official AWS ECS Express, ECS, Fargate, ELB, VPC, CloudWatch, and billing
  documentation was reviewed.
- AWS Price List API product metadata was queried read-only for current
  `us-east-1` Application Load Balancer/LCU and standard CloudWatch alarm
  product families.
- `make PY=/private/tmp/davdeploy-private-batch-endpoints-517/.venv/bin/python openapi-check`: passed.
- Focused pricing and lifecycle tests: 188 passed.
- `python -m pytest tests -q`: 1,990 passed, with one existing Starlette/httpx
  deprecation warning.
- Ruff checks on changed Python files: passed.
- `python scripts/check_doc_conventions.py`: passed.
- `git diff --check`: passed.
- Initial final-head CI run `45893810916` exposed an OpenAPI snapshot mismatch;
  after regenerating the contract snapshot, CI run `45894761342` passed all
  seven checks.
- No Terraform plan or AWS/control-plane operation was run for this PR.

## Evidence files produced

- No `docs/test/test522.md` is required because this package performs no
  customer workload test or cloud mutation.

## Boundaries

- Preserve the hosted control plane, runtime, state, and locks.
- Do not enable Nova execution or alter the ECS Express renderer gate.
- Do not claim a usage estimate is a hard spending cap. The assumption ranges
  are estimate inputs and require human review until independently enforceable
  limits exist.
- Preserve the protected untracked `--only-show-errors`, `.venv-pr399/`, and
  SageMaker lineage evidence.

## Follow-up work

Build an independent cost cap and cleanup-expiry mechanism before any hosted
customer apply. Complete the ECS Express runtime IAM, isolated state, and
Nova-originated lifecycle gates separately.
