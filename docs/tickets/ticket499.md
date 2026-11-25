# ticket499 — bound generated Amazon EKS plans

PR: [#499 — feat: bound generated EKS plans](https://github.com/Bepoadewale/davdeploy/pull/499)
Branch: `feat/eks-plan-bounds-499`

## Problem / goal

The generated-plan policy checks EKS node metadata only when a node group binds
to one same-plan launch template. It does not bound the cluster endpoint,
control-plane logging, Kubernetes version, node-group size, or relationships
between the cluster, node group, launch template, and IAM roles. The repository
module currently selects Kubernetes 1.31, enables only a private endpoint by
default, and creates a managed node group without the launch template required
by the existing IMDSv2 policy.

Add a source-only policy for the repository's one-cluster, one-managed-node-
group shape, and update the module to satisfy that policy. This does not prove
Kubernetes RBAC, pod security, node workload health, full IAM permissions,
cluster upgrade/recovery, or Nova dispatch.

## Current repo state

- `main` is `9680e6ff0d7637b9dc56948c3154126ef052afd4` (merged PR #498).
- The module is `infrastructure/terraform/modules/eks/main.tf`; generated-plan
  policy already requires managed EKS nodes to bind one same-plan launch
  template with IMDSv2 required.
- `docs/test/test255.md` records a direct EKS workload/service probe, but does
  not test this plan policy.
- PR #486 remains open at synchronized head `bb374e8`; its seven checks passed
  in run `45545915711`, while final local clean-room artifact cleanup remains
  pending approval. Draft PR #495's six tagged AppConfig resources remain in
  account `654654474502`; do not mutate them in this source-only PR.
- The Terraform monitor has 66 records and zero active operations. AWS account
  `654654474502` was verified read-only.

## Research / references used

- Repository source: `infrastructure/terraform/modules/eks/main.tf`,
  `apps/api/src/davdeploy/generated_plan_policy.py`, and
  `tests/test_generated_plan_policy.py`.
- AWS [Kubernetes version lifecycle](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html)
  lists standard and extended support versions; extended support adds a
  per-cluster-hour charge. As of 2026-11-25, versions 1.36 and 1.37 are in
  standard support.
- AWS [control-plane logging](https://docs.aws.amazon.com/eks/latest/userguide/control-plane-logs.html)
  requires each log type to be enabled separately and documents CloudWatch
  ingestion/storage charges.
- AWS [cluster endpoint access](https://docs.aws.amazon.com/eks/latest/userguide/cluster-endpoint.html)
  describes private-only access and its VPC connectivity requirements.
- AWS [EKS envelope encryption](https://docs.aws.amazon.com/eks/latest/userguide/envelope-encryption.html)
  documents default envelope encryption of Kubernetes API data for version
  1.28 and later.
- AWS [managed-node launch templates](https://docs.aws.amazon.com/eks/latest/userguide/launch-templates.html)
  documents node-group launch-template restrictions and IMDS hop-limit
  considerations.

## Work planned for the PR

1. Bound the profile to exactly one EKS cluster and one managed node group.
2. Require a known Kubernetes version 1.36 or newer, a private-only endpoint,
   at least two distinct known subnets, and API, audit, and authenticator logs.
3. Bind cluster name, control-plane role, node role, and node launch template
   through exact same-plan references. Reuse the existing IMDSv2 launch-template
   check.
4. Bound nodes to ON_DEMAND `t3.medium` capacity with
   `1 <= min <= desired <= max <= 3`; reject SSH remote access.
5. Update the module to Kubernetes 1.36, enable all five control-plane log
   types, and use a node launch template with IMDSv2 required and hop limit 1.
6. Add regression tests and update the Nova capability matrix. Make no AWS,
   hosted control-plane, or Terraform-state change.

## Limitations and migration risk

This plan-shape guard does not inspect Kubernetes manifests, RBAC bindings,
admission controls, pod IAM, network policy, add-on versions, workload images,
endpoint reachability, node AMI provenance, quota, or all node-volume
encryption settings. It does not prove a live cluster, upgrade, recovery,
application health, cost estimate, or customer deployment. Direct EKS evidence
in `test255.md` remains limited to its tested workload and does not prove the
new policy or Nova dispatch.

AWS warns against adding a custom launch template to a managed node group that
was created without one. This module change can require a planned node-group
replacement for existing users. This PR performs no apply; any later upgrade
needs an explicit reviewed migration plan.

## Acceptance criteria

- [x] The checked plan binds one EKS cluster and one managed node group to
  same-plan cluster/node roles and launch template.
- [x] The module's endpoint is private-only, uses a standard-support version,
  enables control-plane logs, and binds nodes to the IMDSv2 launch template.
- [x] Unsupported/unknown versions, public endpoints, missing required logs,
  invalid subnet sets, unbounded scaling, unsupported instance shapes, bad
  bindings, and SSH remote access fail closed.
- [x] Regression tests cover the supported profile and fail-closed cases.
- [x] Documentation conventions and Terraform formatting pass. Final-head CI
  remains pending.
- [x] Capability matrix keeps source policy distinct from direct workload
  evidence and does not claim Nova dispatch or certification.
- [x] This PR makes no AWS, hosted control-plane, Terraform-state/lock, or
  protected local-file changes.

## Acceptance status

Implementation and focused regression coverage are in place. The generated-plan
policy test file passes 541 tests. Ruff, Terraform formatting, documentation
conventions, and `git diff --check` pass locally. Required final-head GitHub
checks remain pending.

## Tests / validation performed

- `PYTHONDONTWRITEBYTECODE=1 /Users/adewale/Projects/davdeploy/.venv-pr399/bin/python -m pytest -p no:cacheprovider tests/test_generated_plan_policy.py -q`:
  541 passed.
- `/Users/adewale/Projects/davdeploy/.venv-pr399/bin/ruff check apps/api/src/davdeploy/generated_plan_policy.py tests/test_generated_plan_policy.py`:
  passed.
- `terraform -chdir=infrastructure/terraform/modules/eks fmt -check -recursive`:
  passed.
- `GITHUB_PR_NUMBER=499 python3 scripts/check_doc_conventions.py` and
  `git diff --check`: passed.
- No AWS workload, hosted-control-plane, or Terraform mutation was run.

## Evidence files produced

- `infrastructure/terraform/modules/eks/main.tf`
- `apps/api/src/davdeploy/generated_plan_policy.py`
- `tests/test_generated_plan_policy.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- `docs/tickets/ticket499.md`

## Boundaries

Source and documentation only. Do not create or delete AWS resources, run a
Terraform plan/apply/destroy, alter the hosted control plane, change remote
state/locks, or modify protected local files in this PR.

## Follow-up work

Kubernetes RBAC/admission, pod identity, image provenance, network policy,
node AMI and volume controls, quota, complete cost, upgrade/failure recovery,
and Nova-dispatched lifecycle evidence remain separate gates. EKS versions
and their standard-support threshold must be reviewed against current AWS
lifecycle data before future policy updates.
