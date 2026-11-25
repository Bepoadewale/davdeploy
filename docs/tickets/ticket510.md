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

- Backend `main` is `d5d9eebe663a8a1f3f3ff13086e570b63feaf490` (PR #511).
- PR #509 prices explicitly configured same-region CloudWatch Logs for the
  bounded Batch Fargate profile. Its generic supporting-cost blocker remains.
- The Batch fixture uses a public ECR image pinned by digest. The repository
  has an exact-module ECR lifecycle test, but that does not establish image
  size, pull path, or pricing for a Batch plan.
- Merged PR #511 provides regional standard-storage pricing for planned
  private ECR repositories. This PR reuses that single storage line and its
  revision-bound assumptions; it does not add a second Batch-specific charge.
- The Terraform run monitor has 67 terminal records and zero active runs.
- AWS account `654654474502` was verified read-only with the
  `ai-platform-pilot-key` profile on 2026-11-25. The Terraform monitor had 67
  terminal records and zero active runs. Five `davdeploy-*` Batch test definitions
  were inactive; the SageMaker test action and context remain as audit
  evidence. No AWS mutation, Terraform operation, workload, or hosted
  control-plane access occurred.

## Research / references used

- [Amazon ECR pricing](https://aws.amazon.com/ecr/pricing/) describes private
  repository storage and transfer charges, same-region transfer to AWS compute,
  and cross-region transfer pricing.
- [Amazon ECR User Guide](https://docs.aws.amazon.com/AmazonECR/latest/userguide/what-is-ecr.html)
  identifies repository storage, transfer, and optional image actions as cost
  dimensions.
- AWS documents same-Region ECR-to-Fargate image transfer as free on the ECR
  pricing page. This does not cover NAT, VPC endpoint, public IPv4, or other
  network-path charges.
- `docs/tickets/ticket511.md` records the merged ECR storage model. Image-to-job
  binding and unsupported transfer/network costs are tracked here.
- Existing generated-plan pricing and Batch usage-assumption contracts,
  manifests, policy findings, and tests.

## Work planned for the PR

1. Bind a digest-pinned private image to exactly one planned ECR repository
   with matching registry account, repository, and plan region.
2. Require the matched repository to pass PR #511's trusted, bounded,
   revision-bound storage pricing path; do not emit a duplicate cost line.
3. Reject
   public, external, ambiguous, unsupported, or unknown image-cost paths unless
   their applicable cost is demonstrably zero under documented AWS terms.
4. Reuse regional AWS Price List evidence from the ECR storage model; do not
   hardcode rates or infer image size from a tag or digest.
5. Preserve existing Batch usage assumptions and evidence manifests, and retain
   a general supporting-cost blocker for every unmodeled material dependency.
6. Add focused tests and update the active handoff, capability evidence, and
   ticket with exact limits and validation results.

## Acceptance criteria

- [x] Image costs are priced only when the exact Batch image and repository,
  region, and trusted PR #511 usage inputs are unambiguously bound to the
  reviewed plan, with no duplicate repository-storage line.
- [x] Missing, malformed, stale, over-bound, external, public/private-ambiguous,
  cross-region-unsupported, or otherwise unpriced cases fail closed without
  invented price lines.
- [x] The registry account must be explicitly known in the planned repository
  values; an unknown registry ID fails closed instead of being inferred from
  the image URI.
- [x] Regional AWS Price List data provides every emitted rate and auditable
  source metadata; no prices are hardcoded.
- [x] Existing Batch log/compute assumptions and manifests remain readable and
  digest checked.
- [x] Batch approval remains blocked for every material image, network,
  transfer, or other cost not covered by verified assumptions and regional
  prices.
- [x] Focused tests, required local validation, documentation conventions, and
  all seven required checks passed on code head `242e271` in run
  [45672425136](https://github.com/Bepoadewale/davdeploy/actions/runs/45672425136).
  This ticket-only follow-up also requires its own final-head CI before merge.
- [x] No AWS workload, Terraform state/lock, hosted control-plane resource, or
  feature gate is changed; no Nova customer workload is claimed.

## Acceptance status

- [x] Implementation and focused validation complete.
- [x] Seven checks passed on final code head `242e271`; the ticket-only
  follow-up requires one final CI rerun.
- [ ] PR reviewed and merged.

## Tests / validation performed

- `make VENV=/Users/adewale/Projects/davdeploy/.venv openapi-update` — passed;
  removed the superseded Batch-specific ECR usage field in favor of PR #511's
  existing revision-bound ECR repository storage contract.
- `make VENV=/Users/adewale/Projects/davdeploy/.venv verify` — 1,934 passed;
  Ruff, Actions-configuration, OpenAPI snapshot, and Docker Compose checks
  passed.
- `/Users/adewale/Projects/davdeploy/.venv/bin/python -m pytest
  tests/test_generated_plan_pricing.py -k batch_private_ecr -q` — 1 passed.
- `GITHUB_PR_NUMBER=510 python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- The prior pushed head `070110e` passed all seven required checks in run
  [45671187103](https://github.com/Bepoadewale/davdeploy/actions/runs/45671187103).
  Follow-up code head `242e271` also passed all seven checks in run
  [45672425136](https://github.com/Bepoadewale/davdeploy/actions/runs/45672425136).
  This ticket-only update records the verified status; its final-head CI must
  pass before merge.
- AWS account/inventory and Terraform monitor were checked read-only as recorded
  above; no Terraform operation, workload, or control-plane call was made.

## Evidence files produced

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
