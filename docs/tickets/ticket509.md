# ticket509 — price explicit Batch CloudWatch Logs usage

PR: [#509 — feat: price bounded Batch CloudWatch Logs](https://github.com/Bepoadewale/davdeploy/pull/509) (draft)
Branch: `feat/batch-cloudwatch-log-pricing-509`

## Problem / goal

PR #507 prices only Batch Fargate CPU and memory. It deliberately leaves all
Batch estimates incomplete and approval-ineligible because logs, image
transfer, networking, public IPv4, and other material costs remain. Add a
narrow, trusted-usage model for CloudWatch Logs on the existing bounded Batch
shape. Price only an explicitly configured `awslogs` driver bound to one
same-plan managed Standard log group; preserve approval blocking for every
unpriced Batch dependency and unsupported logging configuration.

## Current repo state

- Backend `main` is `29605fa9192a3ff4ac0ba168ced82e39e784d1f6`, after PR #508
  merged. No PRs are currently open.
- PR #507 provides bounded Linux/x86 Fargate compute prices and a generic
  supporting-cost blocker; Batch estimates cannot approve.
- Existing CloudWatch catalog lookup functions and usage assumptions price
  Lambda log ingestion/storage, but bind them only to Lambda-created log
  groups.
- The Terraform run monitor has 67 historical records and zero active runs.
- No AWS or hosted-control-plane changes are in scope.

## Research / references

- AWS Batch [Fargate job definition contract](https://docs.aws.amazon.com/batch/latest/userguide/fargate-job-definitions.html)
  supports `awslogs` and `splunk` logging drivers for Fargate.
- AWS Batch [awslogs configuration](https://docs.aws.amazon.com/batch/latest/userguide/using_awslogs.html)
  documents the group, region, stream-prefix, and auto-create options. AWS
  advises against automatic log-group creation.
- AWS [CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/) covers
  log ingestion and storage. The implementation will reuse the repository's
  regional AWS Price List lookups rather than hardcoding rates.
- AWS [ECR pricing](https://aws.amazon.com/ecr/pricing/) describes repository
  storage and transfer charges; these remain follow-up blockers in this PR.

## Work planned for the PR

1. Extend per-job Batch usage assumptions with bounded CloudWatch log ingestion
   and retained-storage ranges, preserving old persisted assumptions and
   evidence manifests.
2. Bind pricing to one explicit same-plan `awslogs` group, same-region driver
   configuration, and a retained Standard CloudWatch log group. Fail closed on
   missing/ambiguous groups, unsupported drivers/options, cross-region logging,
   missing usage, or malformed bounds.
3. Add auditable regional ingestion and storage cost lines while keeping the
   general Batch supporting-cost finding, so compute plus logs alone never
   implies approval eligibility.
4. Add tests for valid linkage and prices, legacy evidence, tampering, address
   mismatch, unknown/unsupported logging, missing rates, and approval blocking.
5. Reconcile ticket #507 and ticket #508 completion status because their PRs
   are merged; update the Batch pricing evidence and active handoff.

## Acceptance criteria

- [ ] Logs are priced only for the exact planned Batch job and its one
  same-plan, same-region retained Standard log group.
- [ ] Ingestion and retained-storage usage ranges are strict, bounded,
  customer-context-bound, digested, and present in safe evidence summaries.
- [ ] Old Batch pricing assumptions and manifests remain readable; malformed,
  missing, ambiguous, cross-region, external, or unsupported logging fails
  closed without adding invented price lines.
- [ ] Regional AWS Price List lookups produce auditable log ingestion and
  storage lines; no prices are hardcoded.
- [ ] Batch estimates remain incomplete and approval-ineligible until image,
  networking, transfer, and every other material cost is priced.
- [ ] Focused tests, generated OpenAPI validation, documentation conventions,
  and required final-head CI pass.
- [ ] No AWS workload, Terraform state/lock, or hosted control-plane resource
  is changed; no customer workload test is claimed.

## Acceptance status

- [ ] Implementation complete.
- [ ] Focused validation complete.
- [ ] Final-head CI passed.
- [ ] PR reviewed and merged.

## Tests / validation performed

To be completed during implementation. No Terraform or cloud mutation is in
scope.

## Evidence files

No `docs/test/test509.md` is expected because this PR performs no customer
workload test and creates no AWS resources.

## Boundaries and follow-up

Source, tests, and documentation only. Do not change hosted-control-plane
resources or state, execute Terraform, alter feature gates, or delete existing
AWS audit evidence. ECR image storage and transfer, VPC/NAT/public IPv4, other
material Batch dependencies, effective role permissions, runtime/recovery, and
Nova-dispatched execution remain open.
