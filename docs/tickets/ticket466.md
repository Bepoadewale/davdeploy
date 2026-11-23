# ticket466

PR: [#466 — feat: enforce safe OpenSearch domain plan settings](https://github.com/Bepoadewale/davdeploy/pull/466) (draft)

Branch: `feat/opensearch-plan-safety-466`

## Problem / goal

The OpenSearch Terraform module has no service-specific generated-plan checks.
Add fail-closed checks for the exact bounded module shape, its private-network
mode, and encryption/TLS settings, while recording the limits of those checks.

## Current repo state

- `infrastructure/terraform/modules/opensearch/main.tf` requests
  `OpenSearch_2.11`, one `t3.small.search` node, a 10 GiB gp3 volume, VPC
  options, encryption at rest, node-to-node encryption, HTTPS, and a TLS 1.2
  endpoint policy.
- Generated-plan policy did not validate any OpenSearch domain-specific
  settings.
- Existing `test244` records an OpenSearch domain reaching ready state, but
  does not prove the root's search workload, secure access, update/recovery,
  or full teardown. The separate OpenSearch Serverless `test262` is not this
  domain module.
- No OpenSearch AWS mutation is part of this PR. No regional cost estimate or
  full domain access-policy proof is added.

## Research / references used

- [Terraform AWS provider `aws_opensearch_domain` resource](https://registry.terraform.io/providers/hashicorp/aws/6.25.0/docs/resources/opensearch_domain)
- [AWS OpenSearch domain configuration](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/createupdatedomains.html)
- [AWS OpenSearch node-to-node encryption](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/ntn.html)
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `infrastructure/terraform/modules/opensearch/main.tf`
- `tests/test_generated_plan_policy.py`

## Work planned for the PR

1. Mark engine, node count/type, storage, encryption, HTTPS, and TLS settings
   as policy-critical known values.
2. Require the current module's one-node, small-instance, 10 GiB gp3 shape.
3. Require a VPC options block, at-rest and node-to-node encryption, HTTPS,
   and the module's TLS 1.2 policy.
4. Add accepted, unsafe, and unknown-value regression cases.
5. Update the evidence map and leave subnet/SG binding, effective access,
   workload, lifecycle, and cost gaps open.

## Acceptance criteria

- [x] Generated-plan policy permits the checked-in module shape.
- [x] Unsafe node/storage and unencrypted or non-HTTPS configurations are
  denied.
- [x] Unknown safety settings are denied.
- [x] Regression tests cover supported, unsafe, and unknown values.
- [x] The capability matrix scopes checks to this module shape and leaves
  network-binding, access-policy, workload, lifecycle, and price proof open.
- [x] No AWS or hosted control-plane resources are changed.
- [x] Focused and full policy tests, formatting, Terraform validation,
  documentation conventions, and `git diff --check` pass.
- [x] Final-head CI and review/merge state are tracked on PR #466; merge only
  after all required checks pass.

## Acceptance status

Implementation is complete on PR #466. The plan checks do not prove that
the VPC subnet is private, that the attached security group has only intended
ingress, or that customers can safely query/update indexes.

## Tests / validation performed

- `tests/test_generated_plan_policy.py` — 380 passed.
- Ruff on changed Python files — passed.
- Terraform format and module validation — passed.
- `GITHUB_PR_NUMBER=466 python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Final-head CI is tracked on PR #466.

## Evidence files produced

- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket466.md`

## Boundaries

- Source and documentation only; do not create, update, or delete AWS
  OpenSearch resources for this package.
- Do not access or change hosted control-plane resources.
- Do not claim private network reachability, domain access-policy correctness,
  tenant/index isolation, workload behavior, lifecycle completion, or complete
  OpenSearch pricing from these plan checks.
- Preserve `--only-show-errors`, `.venv-pr399/`,
  `docs/test/fixtures/nova-batch-retry-458/terraform.tfstate`, and generated
  provider lock files in the working tree.

## Follow-up work

Add a separately authorized, cost-reviewed customer test that validates the
exact module root, actual private connectivity and denial boundaries, index
operations, update/recovery, teardown, and independent absence evidence.
