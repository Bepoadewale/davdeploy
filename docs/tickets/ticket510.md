# ticket510 — price bounded Batch container images

PR: https://github.com/Bepoadewale/davdeploy/pull/510 (draft)
Branch: `feat/batch-ecr-pricing-510`

## Problem / goal

PR #507 prices bounded AWS Batch Fargate compute. PR #509 adds explicit
CloudWatch Logs pricing, while preserving the general supporting-cost blocker.
The next dependency is container image storage and transfer. Add only a narrow,
revision-bound pricing path for image costs that can be tied to the exact
generated Batch plan and trusted customer usage. Keep estimates
approval-ineligible when image ownership, size, transfer path, or supporting
costs are unknown or unsupported.

## Current repo state

- Backend `main` is `46fe152233ac9fcbdba1961d5d02086c30c959fa` (PR #509).
- PR #509 prices explicitly configured same-region CloudWatch Logs for the
  bounded Batch Fargate profile. Its generic supporting-cost blocker remains.
- The Batch fixture uses a public ECR image pinned by digest. The repository
  has an exact-module ECR lifecycle test, but that does not establish image
  size, pull path, or pricing for a Batch plan.
- The Terraform run monitor has 67 terminal records and zero active runs.
- AWS credentials are unavailable in this session. No AWS inventory refresh,
  Terraform operation, workload, or hosted-control-plane access is in scope.

## Research / references

- [Amazon ECR pricing](https://aws.amazon.com/ecr/pricing/) describes private
  repository storage and transfer charges, same-region transfer to AWS compute,
  and cross-region transfer pricing.
- [Amazon ECR User Guide](https://docs.aws.amazon.com/AmazonECR/latest/userguide/what-is-ecr.html)
  identifies repository storage, transfer, and optional image actions as cost
  dimensions.
- `docs/tickets/ticket509.md` identifies ECR image storage and transfer as
  follow-up cost gaps.
- Existing generated-plan pricing and Batch usage-assumption contracts,
  manifests, policy findings, and tests.

## Work planned

1. Define the smallest defensible ECR image cost shape for the bounded Batch
   plan, with trusted, bounded, customer-context-bound usage assumptions.
2. Bind any priced image/repository to exact plan resources and region; reject
   public, external, ambiguous, unsupported, or unknown image-cost paths unless
   their applicable cost is demonstrably zero under documented AWS terms.
3. Reuse regional AWS Price List lookups and emit auditable cost lines with
   source metadata; do not hardcode rates or infer image size from a tag/digest.
4. Preserve legacy Batch usage assumptions and evidence manifests, and retain
   a general supporting-cost blocker for every unmodeled material dependency.
5. Add focused tests and update the active handoff, capability evidence, and
   ticket with exact limits and validation results.

## Acceptance criteria

- [ ] Image costs are priced only when the exact Batch image and repository,
  region, and trusted usage inputs are unambiguously bound to the reviewed plan.
- [ ] Missing, malformed, stale, over-bound, external, public/private-ambiguous,
  cross-region-unsupported, or otherwise unpriced cases fail closed without
  invented price lines.
- [ ] Regional AWS Price List data provides every emitted rate and auditable
  source metadata; no prices are hardcoded.
- [ ] Existing Batch log/compute assumptions and manifests remain readable and
  digest checked.
- [ ] Batch approval remains blocked for every material image, network,
  transfer, or other cost not covered by verified assumptions and regional
  prices.
- [ ] Focused tests, required local validation, documentation conventions, and
  all required GitHub checks pass on the final PR head.
- [ ] No AWS workload, Terraform state/lock, hosted control-plane resource, or
  feature gate is changed; no Nova customer workload is claimed.

## Acceptance status

- [ ] Implementation and focused validation complete.
- [ ] Final-head GitHub checks pass.
- [ ] PR reviewed and merged.

## Evidence files

No `docs/test/test510.md` is expected unless this PR performs a customer
workload test. This package is intended to remain source-only.

## Boundaries

Preserve the PR-only workflow. Do not execute Terraform, mutate AWS, access or
change the hosted control plane, enable Nova execution, delete resources, alter
protected untracked files, or claim Nova-dispatched workload certification.

## Follow-up work

Any image storage/transfer case outside the accepted bounded model, NAT and
public IPv4 costs outside the existing modeled VPC shape, other material Batch
dependencies, effective role permissions, runtime/recovery, and Nova-dispatched
execution remain open.
