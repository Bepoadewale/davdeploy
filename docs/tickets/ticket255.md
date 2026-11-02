# ticket255 — Real EKS workload certification

PR: Pending creation.

Branch: `test/real-eks-workload`

## Problem / goal

Prove a disposable EKS cluster can run and expose an owned workload, rather
than only proving that the cluster and node group reach active state.

## Current repo state

The EKS module defaults to a private API endpoint and the validation root did
not provide an operator access path for a live workload test.

## Research / references used

Amazon EKS endpoint access guidance and the existing isolated EKS validation
root.

## Work planned for the PR

Temporarily allow only the validation operator CIDR to reach the disposable
cluster API, deploy a minimal workload, observe readiness, then destroy it.

## Acceptance criteria

- [ ] A minimal workload reaches Ready on real EKS nodes.
- [ ] Operator public API access is limited to one CIDR.
- [ ] Cluster and all owned networking resources are destroyed.

## Acceptance status

In progress.

## Tests / validation performed

Pending controlled AWS execution.

## Evidence files produced

`docs/test/test255.md`

## Boundaries

This controlled test does not change the module's secure private-only default.
It also does not claim public load-balancer certification, which needs the AWS
Load Balancer Controller and a separately scoped test.

## Follow-up work

Certify an ingress/load-balancer path and rollback of a deployed workload.
