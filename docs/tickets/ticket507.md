# ticket507 — Price the bounded AWS Batch Fargate job shape

PR: [#507 — feat: price bounded Batch Fargate plans](https://github.com/Bepoadewale/davdeploy/pull/507) (draft)
Branch: `feat/batch-fargate-pricing-507`

## Problem / goal

AWS Batch generated-plan policy now bounds a small Fargate job shape, but the
plan pricing evaluator has no Batch/Fargate usage model. It therefore reports
these resources as unpriced and blocks approval. Add an explicit, customer-
declared usage contract and current regional Fargate vCPU/memory price lookup
for the exact supported shape. Keep unsupported OS, architecture, capacity,
storage, and network costs blocked. This is source-only; it must not change
AWS resources or the hosted control plane.

## Current repo state

- Nova source baseline is `4a14cd2f70d6e964c9aaf28e6f906e48bd04ae8e` (PR #506).
- PR #498 bounds AWS Batch to one managed Fargate compute environment, one
  queue, and one digest-pinned single-container job definition, with capacity,
  resource, retry, timeout, role, and environment checks.
- `generated_plan_pricing.py` prices a finite set of resources and marks other
  billable resource types unpriced. Trusted usage assumptions are integrity-
  bound through `TrustedPlanPricingContext`.
- No PRs are currently open. The Terraform monitor has 67 terminal records and
  zero active operations. AWS account identity was checked as `654654474502`.
- No AWS or control-plane operation is in scope for this package.

## Research / references used

- AWS [Fargate pricing](https://aws.amazon.com/fargate/pricing/) says vCPU,
  memory, OS, architecture and storage affect cost; runtime begins at image
  download, rounds to seconds, with a one-minute minimum. Linux Fargate receives
  20 GiB ephemeral storage without extra charge.
- AWS [Batch Fargate tutorial](https://docs.aws.amazon.com/batch/latest/userguide/getting-started-fargate.html)
  says the billable resources are the requested vCPU, memory, OS, architecture,
  and storage; AWS Batch itself does not define the compute price.
- AWS [Price List Query API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-price-list-query-api.html)
  supports retrieving current service products and rates by product attributes.
- Repository implementation: `generated_plan_pricing.py`,
  `domain.py`, `tests/test_generated_plan_pricing.py`, and the Batch plan
  checks in `generated_plan_policy.py`.

## Work planned for the PR

1. Add strict, address-bound Batch job usage assumptions to the trusted pricing
   context, including monthly job-count and billed-duration ranges.
2. Price only plan-bound, policy-supported Fargate vCPU and memory usage using
   regional AWS Price List rates, applying the documented 60-second minimum
   per job. Derive CPU and memory from the exact planned job definition.
3. Reject missing, extra, malformed, excessive, or mismatched usage addresses;
   preserve incomplete pricing for unsupported/unknown shapes.
4. Include assumptions in the versioned, integrity-checked evidence and safe
   summaries without exposing plan contents.
5. Add regression tests for both priced dimensions, minimum duration, bounds,
   unsupported plan shapes, missing rates, and approval blocking.
6. Update the capability evidence matrix and Nova handoff with exact limits.

## Acceptance criteria

- [x] Exact bounded Fargate plan plus valid trusted usage yields auditable
  regional vCPU and memory cost lines; estimate status stays incomplete and
  approval-ineligible while material supporting costs are unpriced.
- [x] Every job's billed duration uses at least 60 seconds and includes image
  pull time in the declared range.
- [x] Batch pricing assumptions are trusted-context-bound and preserved in
  signed/digested evidence and safe summaries.
- [x] Unsupported OS, CPU architecture, ephemeral storage, compute type,
  unknown resource settings, or unpriced material dependencies remain
  incomplete and approval-ineligible.
- [x] Missing/ambiguous price data and invalid usage assumptions fail
  closed with redacted findings.
- [x] Focused tests and required repository validation pass; required CI remains
  the final PR merge gate.
- [x] No AWS workload, Terraform state/lock, or hosted control-plane resource
  is changed; no customer workload test is claimed.

## Acceptance status

- [x] Implementation complete.
- [x] Focused validation complete.
- [x] All seven required checks passed on implementation head `ec97300` in
  [run 45645636327](https://github.com/Bepoadewale/davdeploy/actions/runs/45645636327);
  a final-head run follows this ticket reconciliation.
- [ ] PR reviewed and merged.

## Evidence files produced

- Regression tests in `tests/test_generated_plan_pricing.py` and relevant
  schema/persistence tests.
- No `docs/test/test507.md` is expected because this PR performs no workload
  test and creates no AWS resources.

## Tests / validation performed

- Focused pricing and persisted-revision tests: 130 passed before the explicit
  supporting-cost blocker was added; the final `make verify` run passed 1,914
  tests, Ruff, Actions configuration, OpenAPI snapshot, and Compose checks.
- All seven required PR checks passed on implementation head
  `ec9730025a378f89ecfcaf63dd886493347b2c52` in
  [run 45645636327](https://github.com/Bepoadewale/davdeploy/actions/runs/45645636327).
  A final-head run follows this ticket reconciliation.
- `make openapi-update` updated `contracts/openapi-v1.json`; the final OpenAPI
  check confirms it matches the API.
- `git diff --check` and documentation conventions are recorded before the
  PR is marked ready.

## Boundaries

Source and documentation only. Do not run Terraform plan/apply/destroy, alter
AWS or the hosted control plane, access remote Terraform state/locks, change
feature gates, or touch protected untracked local files.

## Follow-up work

This package does not establish full Batch cost: ECR storage/scanning and pulls,
CloudWatch logs, NAT, public IPv4, data transfer, role effectiveness, actual job
throughput, or Nova-dispatched execution remain separate evidence and pricing
gaps.
