# davdeploy

davdeploy turns an AI workload request into a governed infrastructure plan. A developer describes the outcome, reviews one recommended AWS design, then submits its exact digest for workspace-administrator approval or rejection. Approval never means deployment.

**Delivery state: hosted serverless control plane live; customer-workload execution disabled.** API Gateway, Lambda, Aurora Serverless v2 Data API, Cognito and SQS are applied in `us-east-1` for the hosted planning, review, approval and read-only discovery control plane. The static React frontend lives in [`davdeploy-frontend`](https://github.com/Bepoadewale/davdeploy-frontend) and is deployed on Cloudflare Pages Free. The local workflow remains executable with FastAPI, PostgreSQL, OPA, a bounded execution fixture, Prometheus, Tempo and Grafana in Docker Compose. Workspace invitations are sent by Resend from `notify@davdeploy.tech`, with replies directed to `support@davdeploy.tech`; no customer workload infrastructure is running through routine product operation.

## What it does

```text
customer request → typed workload specification → reusable-cloud inventory fixture
→ simplest viable architecture and cost plan
→ policy → immutable customer-plan review draft
→ submission → administrator decision
```

After approval, a separate explicit **Execute local dry run** action can queue the bounded fixture worker, observe READY/FAILED/DEGRADED, show health/cost evidence, and create a governed local destroy plan. This remains local execution evidence only.

For the first Day-2 loop, a bounded telemetry fixture can explain elevated latency, propose a replica change with a cost range and rollback, then send that exact change through the same policy, approval, worker and observation path. It never repairs a protected environment automatically.

The planner evaluates viable choices internally, including why simpler options were rejected. The browser presents only the selected AWS design, with its cost range, security controls, observability contract and stated limits.

Customers do not have to choose subnets, Helm values or Kubernetes internals to use the demo. They can inspect those decisions, edit important constraints, record assumption decisions and create a new draft revision before submitting for approval.

Developers and AI clients can use the same governed product surface through the REST API, `davdeploy` CLI, or `davdeploy-mcp` stdio server. See [agent client strategy](docs/product/agent-client-strategy.md). The approved architecture profile chooses a matching delivery contract: EKS/GitOps is used only when EKS is the selected profile.

| Role | Can do | Cannot do |
| --- | --- | --- |
| Developer/founder | Describe a workload, create/revise/submit a customer-plan review and inspect cost | Choose another organisation, bypass policy, approve or reject a customer plan |
| Workspace administrator | Create and submit a plan; approve or reject submitted workspace plans, including their own | Approve changed/stale revisions or bypass cloud controls |
| Intent provider | Propose a typed requirement set | Run shell commands, Terraform, `kubectl`, or cloud mutations |

The local administrator experience includes filtered queues for pending, approved, rejected and self-approved plan revisions, a richer review detail with requester/repository/AWS target/digest/policy/monitoring/cost/risk evidence, an explicit **approved, not deployed** boundary, and a human-readable audit timeline.

## Run it locally

```bash
make help
make local-proof
make clean-local
```

`make local-proof` bootstraps the local stack, then runs service readiness, the API/CORS contract, customer-plan E2E, demo-data seeding, Tempo trace verification and `make verify`. Individual setup and demo targets remain available for narrower checks: `make install`, `make bootstrap-local`, `make demo-simple`, `make demo-complex`, `make demo-day2`, `make demo-degraded`, `make demo-failure`, `make demo-readiness-failure`, `make customer-plan-persistence`.

The API is at http://localhost:8080, Grafana at http://localhost:3000 and
Prometheus at http://localhost:9090. Run the frontend repository separately at
http://localhost:5173. The local login is a documented signed fixture, not
production identity.

For customer AWS onboarding, see [Connect an AWS account](docs/customer-aws-connection.md). The UI includes an account picker, AWS account-ID setup, a Quick Create handoff, and a durable server-side verification job. Customers provide no access keys or administrator access. The public CloudFormation template and historical read-only verification path were applied and verified; the temporary hosted runtime was removed afterward.

The frontend/backend ownership and contract are documented in the
[migration audit](docs/MIGRATION_AUDIT.md) and [ADR-012](docs/decisions/ADR-012-separated-static-frontend.md).

## What is real, simulated and next

- **Executed locally:** natural-language fixture interpretation, typed validation, AWS candidate comparison, fixture-inventory reuse, transparent estimated cost ranges and complexity scores, live OPA policy, PostgreSQL lifecycle/audit state, tenant-scoped GitHub/AWS connection metadata, exact-plan approval, fixture desired-state PR/check-state records, App Runner Terraform contract rendering, cloud-readiness preflight, Terraform plan-only review records, durable queued fixture work, observed status, persisted incident/recommendation records, bounded Day-2 recommendation/change evidence, metrics, traces and dashboards.
- **Simulated only:** planner inventory/pricing, fixture GitHub desired-state publication/checks, and the bounded dry-run deployment target. Production planning uses the governed Nova 2 Lite/Bedrock intent adapter; see [its authority boundary](docs/architecture/nova-2-lite.md). Local Compose calls a fixed fixture endpoint, while hosted Lambda uses a stateless embedded fixture adapter. Neither adapter has shell, Docker, Kubernetes, Terraform, GitHub, or cloud authority.
- **Live hosted control plane:** API Gateway, Lambda, Aurora Data API, Cognito and SQS support hosted planning, review, approval and read-only customer discovery. Resend delivers workspace invitations from a verified domain; its sending key is an AWS Parameter Store SecureString readable only by the API role. Guarded GitHub desired-state PR publishing is implemented but disabled by default.
- **Executed hosted discovery:** AWS App Runner-hosted davdeploy runtime, separate runtime IAM role, ECR image, runtime signing secret in Secrets Manager, public versioned CloudFormation template host, short-lived AWS STS role assumption into a customer read-only discovery role, credential-free inventory snapshots, and GitHub App read-only repository metadata. The AWS discovery role is read-only; no deployment role is granted. GitHub desired-state writes are implemented behind explicit reviewed-write configuration and are not the default local path.
- **Roadmap:** a controlled browser invitation-to-workspace journey, hosted GitHub App installation initiation and public webhooks, authenticated Terraform plan execution and separately authorised customer deployment, real GitOps/Argo execution, customer billing and production support. Local/provider-neutral private-beta controls and self-hosted diagnostics are implemented; see [API and trust surfaces](docs/api-and-trust.md), [serverless deployment](docs/SERVERLESS_DEPLOYMENT.md), and the [administrator runbook](docs/self-hosted-admin-runbook.md).

## Architecture

See the [documentation map](docs/README.md), [minimum-necessary infrastructure](docs/product/minimum-necessary-infrastructure.md), [planner](docs/architecture/planner.md), [Day-2 operations](docs/architecture/day2.md), [agent interfaces](docs/architecture/agent-interfaces.md), [why davdeploy exists](docs/product/differentiation.md), [profile-aware execution](docs/architecture/profile-execution.md), [Terraform plan-only review](docs/architecture/terraform-plan-review.md), [governed integrations](docs/architecture/governed-integrations.md), [hosted persistence](docs/architecture/hosted-persistence.md), [AWS V1 families](docs/architecture/aws-v1.md), [provider model](docs/architecture/provider-model.md), [single-cloud default](docs/architecture/multicloud.md), [planned cloud-pilot architecture](docs/architecture/cloud-pilot.md), [security model](docs/security/security-model.md), and [validation evidence](docs/VALIDATION.md).

davdeploy is private commercial product work. The public portfolio repositories remain independent technical evidence and are not copied wholesale into this product.

See the [current-state audit](docs/product/CURRENT_STATE_AUDIT.md), [product flow](docs/product/PRODUCT_FLOW.md), [approval architecture](docs/architecture/PLAN_APPROVAL_ARCHITECTURE.md), [plan lifecycle](docs/architecture/PLAN_LIFECYCLE.md), and [two-user demo](docs/DEMO.md).

For the active outbound/inbound mail boundary, alias registry, rotation procedure and provider
change process, see [email operations](docs/EMAIL_OPERATIONS.md).
