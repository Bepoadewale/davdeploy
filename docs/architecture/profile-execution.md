# Profile-aware execution

davdeploy does not send every approved plan to Kubernetes.

The planner selects an architecture profile. The executor then selects the matching, bounded delivery contract. A static site uses a static-hosting contract; a Lambda API uses a serverless contract; App Runner and ECS use their own managed-container contracts. GitOps and Kubernetes are required only for the `aws-eks-governed` profile.

| Selected profile | Delivery contract | GitOps / Kubernetes |
| --- | --- | --- |
| Static, Lambda, App Runner, EC2, or managed AI | The matching Terraform contract | Not used |
| ECS, CPU inference, or GPU inference | The matching Terraform contract | A reviewed desired-state change can be used when it helps; Kubernetes is not required |
| EKS | The EKS Terraform contract | A reviewed GitOps pull request and Argo observation; Kubernetes is required |

This prevents a request that needs a simple managed application from accidentally becoming an EKS deployment.

## Current evidence

**Executed locally:** the planner stores the selected profile in the immutable plan; the local worker passes that profile to the bounded executor; tests prove that an App Runner recommendation has no Kubernetes contract and an EKS recommendation does.

**Implemented / planning:** approved `aws-app-runner` customer-plan revisions
can render a digest-bound Terraform contract. The rendered contract includes
module inputs for the service, repository/branch, ECR/source boundary, IAM
boundary, secret references, HTTPS assumptions, Prometheus/Grafana monitoring
contract, required tags, selected account/region, revision ID and exact
approved digest. Other selected profiles have bounded planning contracts, not
live cloud executors.

Approved revisions can also run a workspace-administrator-only cloud-readiness preflight that checks account, region, tags, budget, reviewed PR state, runtime identity and dry-run/plan-only mode before any future cloud workflow can be considered. The local demo can produce `READY_FOR_AUTHORIZED_CLOUD_PLAN` only by using fixture reviewed-PR/check state and the explicit local runtime-identity checkbox; that is guardrail evidence, not proof of a hosted runtime identity or live GitHub checks.

**Pilot evidence:** `aws-app-runner` has separately recorded real AWS
create, health-check and destroy pilot evidence. Product-driven execution is
still controlled per customer, exact digest and explicit enablement; it is not
general availability. The remaining profiles have no live customer-workload
execution evidence.

**Simulated:** the local executor reports a deterministic result. Fixture
desired-state PR publication records a reviewed-PR contract without writing
GitHub.

**Adapter catalogue:** see [the governed workload-adapter catalogue](adapter-catalogue.md)
for lifecycle labels, composition rules, promotion requirements and the
monthly/quarterly maintenance cadence.
