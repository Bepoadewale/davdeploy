# ticket512 — price public IPv4 for bounded Batch Fargate jobs

PR: https://github.com/Bepoadewale/davdeploy/pull/512 (draft)
Branch: `feat/batch-fargate-public-ip-pricing-512`

## Problem / goal

The bounded AWS Batch Fargate pricing path already prices compute, explicit
CloudWatch Logs, and eligible same-plan private ECR storage. Public IPv4
addresses assigned to Batch Fargate jobs are a separate billable dependency.
Add a narrow, plan-bound cost line when the exact job definition explicitly
enables `assignPublicIp`, using trusted monthly job-count and billed-runtime
bounds and the existing regional Amazon VPC Price List lookup. Keep all other
network-path and supporting costs approval-blocking. This is source-only.

## Current repo state

- Backend baseline is `80ed545898986282976f6e6e8f952c847f2648cb` (PR #510).
- PR #507 bounds Batch to one managed Fargate compute environment, one queue,
  and one Fargate job definition; trusted assumptions bound monthly job count
  and average billed runtime.
- PRs #509–#511 add bounded Logs, ECR storage, and private-image binding, while
  retaining the generic Batch supporting-cost blocker.
- `AwsPriceListCatalog.public_ipv4_in_use_rate(region)` already returns the
  regional Amazon VPC in-use public IPv4 hourly rate, also used for an eligible
  public NAT Gateway's associated Elastic IP.
- The isolated worktree starts at merged `origin/main`. The original checkout's
  protected untracked `--only-show-errors` file and `.venv-pr399/` are outside
  this worktree and must remain untouched.
- No AWS workload, Terraform operation, hosted control-plane operation, or
  customer execution is in scope.

## Research / references

- AWS [VPC pricing](https://aws.amazon.com/vpc/pricing/) prices in-use public
  IPv4 addresses by the second, with a 60-second minimum; the current published
  rate is $0.005 per address-hour. Use the regional AWS Price List result for
  the emitted rate rather than hardcoding this value.
- AWS [Batch job definition parameters](https://docs.aws.amazon.com/batch/latest/userguide/job_definition_parameters.html)
  defines `networkConfiguration.assignPublicIp` with `ENABLED` and `DISABLED`
  values and a default of `DISABLED`.
- AWS [Batch Fargate job definition](https://docs.aws.amazon.com/batch/latest/userguide/create-job-definition-Fargate.html)
  documents the job-level network configuration.
- AWS [Batch Fargate compute environments](https://docs.aws.amazon.com/batch/latest/userguide/fargate-compute-environments.html)
  describes subnet/NAT requirements for public-IP assignment.
- Existing code and contracts: `domain.py`, `generated_plan_pricing.py`,
  `tests/test_generated_plan_pricing.py`, and tickets #502, #507, #509–#511.

## Work planned

1. Treat the exact Batch job definition as the source for public-IP assignment;
   emit no public IPv4 line when the field is absent/default-disabled or
   explicitly disabled.
2. For explicit `ENABLED`, bind one public IPv4 address to each bounded running
   Fargate job attempt. Apply the documented 60-second per-address minimum,
   use trusted job-count and average billed-runtime bounds, and express
   address-seconds against the regional hourly rate without rounding down the
   minimum.
3. Fail closed on malformed or unsupported network configuration and on any
   usage/address mismatch; do not infer subnet topology or a free network path.
4. Keep NAT, endpoints, transfer, internet egress, image-pull path, and other
   unmodeled material costs blocked by the existing supporting-cost finding.
5. Add regression tests for disabled/default, enabled, per-job minimum, bounds,
   malformed/unknown configuration, regional price failures, evidence round
   trips, and persistent approval blocking.
6. Update the Nova capability/evidence matrix and active goal handoff with exact
   support limits and validation results.

## Acceptance criteria

- [ ] An explicit `ENABLED` planned job definition with valid trusted bounded
  usage emits one address-bound regional public IPv4 cost line with the AWS
  per-address 60-second floor applied per job.
- [ ] Missing/default or explicit `DISABLED` assignment emits no public IPv4
  line; existing plans and evidence remain backward-compatible.
- [ ] Malformed, ambiguous, unsupported, unbounded, stale, or mismatched
  network/usage evidence fails closed without invented pricing.
- [ ] Rates and source metadata come from the exact regional Price List match;
  no rate is hardcoded.
- [ ] NAT, endpoints, internet egress, image/network path, and other material
  costs remain approval-blocking; Batch approval is not enabled by this change.
- [ ] Focused tests, full required verification, documentation conventions, and
  all seven final-head CI checks pass before merge.
- [ ] No AWS/customer workload, Terraform state/lock, hosted control plane, or
  feature gate is changed; no Nova customer workload is claimed.

## Acceptance status

- [ ] Implementation complete.
- [ ] Focused validation complete.
- [ ] Full local verification complete.
- [ ] Final-head CI passed.
- [ ] PR reviewed and merged.

## Evidence files

No `docs/test/test512.md` is expected because this package is source-only and
performs no customer workload test.

## Boundaries

Do not execute Terraform, mutate AWS, access/change the hosted control plane,
enable Nova execution, delete resources, alter protected untracked files, or
claim Nova-dispatched workload certification.

## Follow-up work

The generic Batch supporting-cost blocker intentionally remains for unpriced
NAT, endpoint, transfer, egress, image-pull network paths, and other linked
usage. Pricing these requires separate bounded assumptions and evidence.
