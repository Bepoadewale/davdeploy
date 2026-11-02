# test255 — Real EKS workload certification

Date: 2026-11-02

Execution type: Controlled disposable AWS workload validation.

Customer repository: None.

Commit: `b553c2d` plus evidence update in progress.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

A disposable EKS cluster, two managed nodes, isolated VPC, NAT gateway, IAM
roles and OIDC provider, tagged `TestId=certeksworkload20261102a`.

## Commands executed

Terraform monitor applied and destroyed the EKS root. `aws eks update-kubeconfig`
configured the temporary context; `kubectl` deployed NGINX, waited for rollout,
and port-forwarded the owned service for an HTTP probe.

## Observed result

Two EKS nodes became Ready. The NGINX deployment rolled out successfully, and
the local probe returned its default HTML response through the Kubernetes
service. Public API access was restricted to the operator `/32`.

## Teardown

Terraform recorded `Destroy complete! Resources: 23 destroyed.`

## Final boundary

This proves cluster workload readiness, not a public load-balancer path.
