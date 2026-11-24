# ticket479

PR: [#479 — feat: require authenticated bounded Redis plans](https://github.com/Bepoadewale/davdeploy/pull/479) (draft)
Branch: `feat/redis-plan-safety-479`

## Problem / goal

The Redis module uses private security-group access and enables encryption at
rest and in transit, but it does not require client authentication and leaves
capacity settings caller-selectable. Add a bounded, authenticated profile:
Redis OSS 7.1, one `cache.t4g.micro` node, TLS, and a required AUTH token set at
creation. Generated-plan policy must verify the profile and restrict port 6379
to security-group sources.

## Current repo state

- `infrastructure/terraform/modules/elasticache-redis/main.tf` creates one
  replication group with at-rest and in-transit encryption, private subnets,
  and security-group ingress on TCP/6379 from supplied application groups.
- The module has no AUTH token. Its user-selectable node type has no generated
  plan cost bound.
- The evidence matrix records an available replication group from `test244.md`,
  but no client operation, auth denial, reconnect, failover, or current price.
- The module-validation root calls this module and must receive the token only
  through a sensitive input variable; no token value belongs in source control.
- This package is source-only. It will not create AWS or hosted control-plane
  resources.

## Research / references used

- [AWS Redis OSS AUTH guidance](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/auth.html)
- [AWS in-transit encryption guidance](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/in-transit-encryption.html)
- [AWS supported engine versions](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/engine-versions.html)
- [Terraform AWS provider `aws_elasticache_replication_group`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/elasticache_replication_group)
- [AWS ElastiCache engine versions and support](https://docs.aws.amazon.com/AmazonElastiCache/latest/dg/engine-versions.html)
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/elasticache-redis/main.tf`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

## Work planned for the PR

1. Require a sensitive AUTH-token input with AWS-compatible character and
   length validation; use `SET` so authentication is required at creation.
2. Pin the module to Redis OSS 7.1, one `cache.t4g.micro` node, port 6379,
   at-rest encryption, and required in-transit encryption.
3. Enforce the known bounded profile, token sensitivity/presence, and exact
   TCP/6379 security-group-only ingress in generated plans; deny critical
   unknowns and avoid including token values in findings.
4. Add regression tests and update the evidence matrix with unproven client,
   failover, lifecycle, and price behavior.

The AUTH token remains sensitive through Terraform variables and plan findings,
but Terraform may still store it in protected plan/state. This package does not
remove that state-access risk; it relies on the existing encrypted artifact and
state boundaries and does not output the token.

## Acceptance criteria

- [x] The Terraform module requires a valid sensitive AUTH token, TLS, and the
  bounded one-node Redis OSS 7.1 profile.
- [x] Generated-plan policy rejects missing, unsafe, or unknown Redis settings
  and requires the token value to remain marked sensitive.
- [x] TCP/6379 ingress must be exact and sourced only from a security group;
  CIDRs, prefix lists, broad rules, and unknowns are denied.
- [x] Tests cover the accepted profile, unsafe settings, unknown values, and
  token non-disclosure.
- [x] The evidence matrix records source-only policy and leaves client
  operations, failover, lifecycle, pricing, and Nova execution unproven.
- [x] No AWS or hosted control-plane resource is changed.
- [x] Focused tests, full verification, Terraform format/validation, docs
  conventions, and `git diff --check` pass locally. Merge only after all seven
  CI checks pass on the final PR head.

## Acceptance status

Implementation, tests, local full verification, Terraform validation, and docs
checks are complete. CI must pass on the final PR head before merge. No AWS or
hosted control-plane resource has been changed.

## Tests / validation performed

- `tests/test_generated_plan_policy.py -q` — 476 passed.
- `make verify` — passed: 1,705 tests, Actions configuration, Ruff, OpenAPI,
  and Docker Compose checks; one existing Starlette/httpx deprecation warning.
- `terraform fmt -check -recursive infrastructure/terraform/modules/elasticache-redis infrastructure/terraform/module-validation/data-services`
  — passed.
- Standalone module `terraform init -backend=false -input=false` and
  `terraform validate` — passed with AWS provider v6.74.0.
- Module-validation root `terraform init -backend=false -input=false -lockfile=readonly`
  and `terraform validate` — passed with the root's pinned AWS provider v5.100.0.
- `GITHUB_PR_NUMBER=479 .venv-pr399/bin/python scripts/check_doc_conventions.py`
  — passed.
- `git diff --check` — passed.
- GitHub PR checks have not run on the implementation head yet.

## Evidence files produced

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/elasticache-redis/main.tf`
- `infrastructure/terraform/module-validation/data-services/main.tf`
- `infrastructure/terraform/module-validation/data-services/variables.tf`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket479.md`

## Boundaries

Source and documentation only. Never print the AUTH token. Do not claim a
client connection, authentication denial, failover, complete price, or Nova
execution from Terraform plan checks.

## Follow-up work

Use an isolated customer-side test to prove authenticated and unauthenticated
client behavior, update/recovery, teardown, and independent absence. Add a
separate regional price model for cache node-hours, backup, storage, and
transfer; keep approval blocked while material charges remain unpriced.
