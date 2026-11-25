# ticket511

Status: merged as `d5d9eebe663a8a1f3f3ff13086e570b63feaf490`.

PR: [#511 — feat: price bounded private ECR standard storage](https://github.com/Bepoadewale/davdeploy/pull/511) (merged)
Branch: `feat/ecr-storage-pricing-510`

## Problem / goal

Add a small, fail-closed cost line for standard-tier storage in explicitly
planned private Amazon Elastic Container Registry (ECR) repositories. Bind
customer-declared monthly storage ranges to exact repository addresses in the
integrity-checked plan revision and price them using the regional AWS Price
List. This extends Nova planning evidence only; it does not enable execution.

## Current repo state

- Backend `main` is `d5d9eebe663a8a1f3f3ff13086e570b63feaf490`, merged PR #511.
- PR #507 adds bounded Batch Fargate compute pricing; merged PR #509 adds
  bounded Batch CloudWatch Logs pricing.
- Batch and ECR approval remains blocked while material image transfer,
  networking, public IPv4, and other support costs lack bounded evidence.

## Research / references used
- AWS ECR bills private image storage by the stored data amount and charges
  separately for internet and cross-region transfer. In-region ECR-to-compute
  transfer is free according to the current ECR pricing page. Archive
  retrieval, image signing, replication, and other optional features are out
  of scope and remain blockers where relevant.

## Research references

- AWS [Amazon ECR pricing](https://aws.amazon.com/ecr/pricing/) describes
  standard storage and transfer billing.
- AWS [ECR User Guide](https://docs.aws.amazon.com/AmazonECR/latest/userguide/what-is-ecr.html)
  describes ECR as a regional registry and its billable features.
- AWS [Price List Query API](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_pricing_GetProducts.html)
  is the regional source for SKU-level rates.

## Work planned for the PR

- Add strict, bounded monthly stored-GB assumptions keyed by exact
  `aws_ecr_repository` Terraform address.
- Persist the assumptions in the customer revision, bind them into the trusted
  pricing-context digest, and include them in safe summaries and pricing
  evidence manifests.
- Preserve reading of existing pricing manifests and contexts that predate the
  ECR field.
- Price only planned private `aws_ecr_repository` resources using the exact
  regional ECR standard-storage product and `GB-Mo` unit.
- Keep an explicit finding for ECR transfer, archival, signing, replication,
  and other unpriced supporting costs. Any such material cost continues to
  make the estimate incomplete and approval-ineligible.
- Draft PR #510 links a digest-pinned same-region Batch image to exactly one
  planned, priced ECR repository. It reuses this package's storage line and
  assumption rather than adding a duplicate charge. NAT and other network
  path costs remain unpriced.

## Acceptance criteria

- [x] Exact-address monthly storage assumptions have strict shape and bounded
  usage; Nova-proposed prices or usage text are not read by the evaluator.
- [x] Regional Price List lookup identifies one unambiguous ECR standard
  storage rate; missing, ambiguous, malformed, or unavailable rates fail
  closed without a fabricated line.
- [x] AES256 private repositories are the only priced shape; unknown
  encryption or customer-managed-key settings fail closed.
- [x] Low/high monthly storage estimates use conservative cent rounding and
  retain SKU, product digest, publication date, and effective date.
- [x] Assumptions are revision-bound, digest-bound, visible in the safe
  evidence summary, and tamper-detectable.
- [x] Old pricing evidence remains readable; ECR estimates stay incomplete
  while transfer, archive retrieval, signing, replication, and other material
  costs remain unpriced.
- [x] Focused tests, complete verification, OpenAPI snapshot checks, and
  documentation conventions pass; all seven required checks pass on final
  head `9834b8e` in run [45663754469](https://github.com/Bepoadewale/davdeploy/actions/runs/45663754469).
- [x] PR merged as `d5d9eebe663a8a1f3f3ff13086e570b63feaf490`; merged-main CI
  passed all seven checks in run [45664820099](https://github.com/Bepoadewale/davdeploy/actions/runs/45664820099).
- [x] No AWS workload, Terraform state/lock, or hosted-control-plane resource
  is changed. No customer test or deployment is claimed.

## Acceptance status

- [x] Source implementation and focused regression tests are complete.
- [x] Full local `make verify` passes.
- [x] Generated OpenAPI snapshot and documentation conventions pass.
- [x] Final-head PR CI passed all seven checks; PR merged as
  `d5d9eebe663a8a1f3f3ff13086e570b63feaf490`.

## Tests / validation performed

- `tests/test_generated_plan_pricing.py -k 'ecr or batch'`: 23 passed, 109
  deselected.
- Full `tests/test_generated_plan_pricing.py` and
  `tests/test_infrastructure_plan_lifecycle.py`: 149 passed, 1 warning.
- `make openapi-update && make openapi-check`: passed after adding the optional
  constraint field.
- Read-only regional Price List lookup through `ai-platform-pilot-key` on
  2026-11-25 returned one `AmazonECR` standard-storage product in `us-east-1`,
  unit `GB-Mo`, current list rate `$0.10`, SKU `KJC988R4J65BDMTQ`. This verifies
  the lookup filter and response shape only; it is not customer billing or
  deployed pricing evidence.
- `make verify`: 1,933 tests, Ruff, Actions configuration, OpenAPI snapshot,
  and Docker Compose validation passed.
- `GITHUB_PR_NUMBER=511 python3 scripts/check_doc_conventions.py`: passed.
- Final-head PR CI passed all seven checks in run `45663754469`; merged-main CI
  passed in run `45664820099`; PR #511 merged as
  `d5d9eebe663a8a1f3f3ff13086e570b63feaf490`.

## Evidence files produced

No `docs/test/test511.md` is expected because this package performs no customer
workload test or cloud lifecycle.

## Boundaries

Source and test evidence only. No regional usage or price was presented as
customer billing evidence, and no ECR repository was created or changed. No
`docs/test/test511.md` is expected because this package performs no customer
workload test or cloud lifecycle.

The ECR price model is partial and is not a bill forecast or spending cap.
Never imply that ECR standard-storage pricing completes Batch pricing, binds
the stored images to a job image URI, proves an image was pulled, or certifies
Nova execution.

## Follow-up work

PR #510 continues the exact image-to-job binding and reuses this repository
storage line. Pricing for archive retrieval, signing, replication, network
path costs, and other material ECR or Batch costs remains incomplete. Keep
Nova apply and customer workload execution disabled until their existing
authorization and lifecycle gates are met.
