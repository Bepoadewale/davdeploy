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
- Application Auto Scaling target tracking creates and manages alarms:
  https://docs.aws.amazon.com/autoscaling/application/userguide/target-tracking-scaling-policy-overview.html
- CloudWatch documents target tracking's high and low alarms:
  https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/alarm-actions.html
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
  Logs, both target-tracking CloudWatch alarms, ECR storage, and data transfer.
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
  IPv4 address duration, CloudWatch log volume, both target-tracking alarms,
  transfer bounds, and ALB sharing behavior are represented correctly.
- [x] Price evidence includes exact regional SKU, product digest, published
  and effective timestamps, and remains bound to the trusted persisted
  assumptions and exact plan digest.
- [x] Missing or stale catalog evidence, stale assumptions, unknown resources,
  unsupported sharing, and malformed input cannot produce `COMPLETE` pricing.
- [x] Existing pricing manifest versions remain readable and canonical; new
  evidence uses a versioned strict shape.
- [x] A provider-generated create plan may contain computed resource IDs and
  variable-bound region values only when the exact same-plan resource
  references and the trusted `var.region` value are present; unrelated or
  mixed references and missing bindings remain incomplete.
- [x] Focused and full relevant tests, lint, docs conventions, and final-head CI
  pass. A full clean-room run is not applicable to this pricing-only change.
- [x] No AWS workload or hosted control-plane resource is changed, and no
  remote Terraform state or lock is accessed. The retained isolated local
  provider-generated plan from PR #519 was evaluated using read-only AWS
  discovery and current AWS Price List data; no apply or destroy was run.

## Acceptance status

The current revision prices the high and low alarms for the pilot's one
target-tracking scaling policy. Focused tests, repository CI, and documentation
checks pass. The fresh regional-price evaluation is complete for the tested
plan and usage assumptions, but its synthetic trusted-context digest and
unset customer budget make it unsuitable as a customer approval artifact. PR
#520 has merged, and this draft targets `main`.

## Tests / validation performed

- Read-only AWS identity and Batch definition inventory were reconciled in
  account `654654474502`.
- Official AWS ECS Express, ECS, Fargate, ELB, VPC, CloudWatch, and billing
  documentation was reviewed.
- AWS Price List API product metadata was queried read-only for current
  `us-east-1` Application Load Balancer/LCU and standard CloudWatch alarm
  product families.
- `make PY=/private/tmp/davdeploy-private-batch-endpoints-517/.venv/bin/python openapi-check`: passed.
- `make verify` after rebasing on merged PR #520 and adding the second alarm:
  2,001 passed, with one existing Starlette/httpx deprecation warning; Ruff,
  OpenAPI snapshot, actions configuration, and Compose checks passed.
- Ruff checks on changed Python files: passed.
- `python scripts/check_doc_conventions.py`: passed.
- `git diff --check`: passed.
- After the alarm correction, `tests/test_generated_plan_pricing.py`:
  175 passed; Ruff, documentation conventions, and `git diff --check` passed.
- Initial final-head CI run `45893810916` exposed an OpenAPI snapshot mismatch;
  after regenerating the contract snapshot, CI run `45894761342` passed all
  seven checks.
- Final-head CI run `45900573713` on head
  `a04c5909075bfe975ba1628aeef9851a7b317784` passed all seven checks.
- Focused pricing tests cover accepted and rejected computed-ID bindings,
  including references placed in an unrelated field or mixed with an
  untrusted reference in the same field.
- Fresh evaluation of the retained provider-generated create plan with live
  `us-east-1` AWS Price List data at `2026-11-26T21:55:12Z` returned `COMPLETE`
  with 12 lines and a modeled monthly range of USD 1.27 to USD 415.81 under
  the documented synthetic usage assumptions. The source saved plan has
  SHA-256 `73e9596b651cdeb9095ae39bb1d182ea286dd4362a0495d2782e9011ff6e804e`.
  Both target-tracking alarms are priced at USD 0.10 per alarm-month (SKU
  `EVETVUGEN3MUTMXM`, published `2026-11-25T15:02:40Z`). The evaluator used a
  synthetic persisted-context digest and no customer budget, so this is not a
  customer approval artifact. The estimates are not measured spend or a hard
  billing cap. No workload/control-plane mutation or remote Terraform
  state/lock access occurred.

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
