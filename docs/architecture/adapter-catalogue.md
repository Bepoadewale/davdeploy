# Governed workload-adapter catalogue

This catalogue is the boundary between an architecture recommendation and a
customer-cloud change. It deliberately does **not** promise that every AWS
service, configuration, or future workload can be deployed today.

An adapter is a versioned, bounded delivery pattern. It combines a typed
workload contract, allowed resources, policy checks, a least-privilege role
contract, a cost/risk model, an observation contract, and a governed destroy
path. The model may propose and compare adapters; it cannot choose arbitrary
AWS APIs, Terraform, shell commands, or permissions.

The catalogue is based on AWS's current workload guidance for modern
applications, event-driven systems, data workloads and AI/ML. It uses
Well-Architected trade-offs rather than treating a service catalogue as a
default architecture. Sources: [AWS Modern Applications](https://aws.amazon.com/modern-apps/),
[AWS workload decision guide](https://docs.aws.amazon.com/decision-guides/latest/decision-guides/modern-apps-strategy-on-aws-how-to-choose.html),
[AWS cloud design patterns](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/),
[serverless agentic-AI guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-serverless/designing-serverless-ai-architectures.html),
and the [AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/).

## Capability labels

| Label | Meaning |
| --- | --- |
| `catalogued` | A typed recommendation and policy vocabulary exists or is intentionally reserved. It is not executable. |
| `planning` | The planner can select the profile and render bounded planning evidence. It is not a cloud deployment capability. |
| `pilot` | A named, separately authorised customer run may use a versioned adapter, with create, health evidence, destroy and retained audit evidence. It is not general availability. |
| `general-availability` | Repeated production evidence, documented support ownership, recovery evidence and explicit release approval exist. |

No profile progresses merely because an AI model can describe it or generate
configuration for it.

## AWS workload catalogue

The following set covers the common deployment patterns customers ask for,
without pretending to cover every AWS product or bespoke enterprise topology.
Patterns can be composed in one approved plan when their resource, identity,
network and destroy contracts are compatible.

| Adapter family | Typical bounded AWS building blocks | Current status | Use when | Do not default to it when |
| --- | --- | --- | --- | --- |
| Static web and edge | S3, CloudFront, Route 53, WAF | `planning` | A frontend, documentation site or immutable web asset is needed | Server-side identity, private APIs or background processing are required |
| Serverless HTTP/API | Lambda, API Gateway, EventBridge, SQS, DynamoDB | `planning` | Traffic is variable and the service is short-running | Long-lived connections, specialised runtimes or sustained container workloads are required |
| Managed application | App Runner, ECR, CloudWatch | `pilot` | One containerised web/API service has a clear health endpoint | Multiple services, custom orchestration or GPU compute are required |
| Managed containers | ECS Fargate, ECR, ALB, CloudWatch, Service Connect where justified | `planning` | A service needs container control without Kubernetes | A single small service fits App Runner or Lambda |
| Managed virtual machines | EC2, Auto Scaling, ALB, SSM | `planning` | A workload needs OS-level control, an agent, legacy software or special networking | A managed/serverless option meets the same need |
| Kubernetes platform | EKS, ECR, IAM Roles for Service Accounts, GitOps, load balancing | `planning` | The customer already operates Kubernetes or needs Kubernetes-specific scheduling/ecosystem features | The request is a single API, worker or standard container service |
| Scheduled jobs and batch | EventBridge Scheduler, Step Functions, SQS, AWS Batch or ECS tasks | `catalogued` | Work is asynchronous, scheduled, fan-out or compute-bounded | A request-response service is sufficient |
| Event and integration backbone | EventBridge, SQS, SNS, Step Functions | `catalogued` | Decoupled workflows, retries, notifications or integrations are needed | A synchronous direct call is adequate |
| Relational data service | RDS/Aurora, Secrets Manager, backups, read replicas only when measured | `catalogued` | Transactions, relational queries or existing PostgreSQL/MySQL compatibility are needed | A key-value/document access pattern is the real requirement |
| NoSQL and cache | DynamoDB, ElastiCache only with measured latency/load need | `catalogued` | Predictable key access, high-scale events or a justified cache are needed | A small relational workload is simpler |
| Object, content and data lake | S3, CloudFront, Glue, Athena, Lake Formation where justified | `catalogued` | Files, analytics, archival or data-lake workloads are needed | The data is operational relational state |
| Streaming and real-time processing | Kinesis, MSK only when managed streaming is justified, Lambda/Flink consumers | `catalogued` | Ordered/event stream processing, telemetry or sustained ingestion is needed | A queue or scheduled batch is enough |
| Public APIs and real-time clients | API Gateway HTTP/WebSocket, AppSync only when GraphQL is required | `catalogued` | Contracted APIs, WebSockets or mobile/web clients require it | An internal service endpoint is enough |
| AI application and retrieval | Amazon Bedrock, managed vector/retrieval components, S3, Lambda/Step Functions, guardrails | `planning` | A customer needs model inference, retrieval-augmented generation, evaluation or bounded agents | AI is not needed to meet the stated business requirement |
| Managed ML inference and training | SageMaker endpoints/jobs/pipelines, S3, model registry, monitoring | `catalogued` | A customer owns a model or needs managed training/inference lifecycle | A foundation-model API or ordinary CPU service is sufficient |
| CPU model inference | ECS Fargate/EC2 or SageMaker, ECR, autoscaling and measured performance evidence | `planning` | Custom inference has predictable CPU requirements | Managed AI or a normal API fits better |
| GPU inference and training | SageMaker, EKS/EC2 GPU only with quota, cost, capacity and security approval | `planning` | A validated workload genuinely requires accelerators | The model can run acceptably on a managed API or CPU |
| Secure connectivity and hybrid integration | VPC, private endpoints, Transit Gateway/VPN/Direct Connect only when required | `catalogued` | Private customer networks, regulated data paths or hybrid dependencies require it | A simpler private service boundary meets the need |
| Observability, resilience and recovery | CloudWatch, OpenTelemetry, backups, restoration drills, alarms, incident evidence | `catalogued` | Every live adapter | It is never optional for a live adapter |

`aws-app-runner` is the only customer workload pattern with real create,
health-check and destroy pilot evidence. Its availability is still controlled
per run and per customer account. All other rows are recommendation/planning
or catalogue scope, not deployed adapters. The current code-level execution
profiles intentionally remain the narrower nine-profile set in
`apps/api/src/davdeploy/execution_profiles.py` until each added pattern meets
the adapter acceptance gate below. The typed, non-executable registry in
`apps/api/src/davdeploy/adapter_catalogue.py` is the product source of truth
for the broader catalogue and carries the same lifecycle labels.

## Composition rules

One plan may combine compatible families, for example a static frontend plus
serverless API, a managed container plus relational database and queue, or an
AI retrieval service plus object storage and event processing. The planner
must create one immutable dependency graph and cost/risk explanation. It must
not independently apply each family.

Before execution, the composed plan must have:

1. a named version for every selected adapter;
2. compatible regions, network boundaries, tagging and identity assumptions;
3. a least-privilege role contract for the exact resource set;
4. approved budget, quota and data-classification checks;
5. a create, observe, rollback/destroy and retained-evidence contract; and
6. one human approval of the exact combined digest.

If no compatible bounded adapter exists, DavDeploy returns a planning result
and a clear implementation gap. It never converts that gap into unrestricted
Terraform or model-directed AWS access.

## Adapter acceptance gate

Before a catalogue row may become `pilot`, it needs all of the following:

1. Typed input/output schema and supported-region/service matrix.
2. Versioned Terraform or provider implementation with only an allow-listed
   resource set.
3. Least-privilege assume-role policy, external-ID and request/resource tag
   conditions.
4. Policy, cost, quota, data-classification and dependency checks that fail
   closed.
5. Exact-digest approval, idempotency, tenant isolation and immutable audit
   evidence.
6. Create, health/readiness observation, failure classification, rollback and
   destroy behaviour proven in a separately authorised AWS run.
7. Operational ownership: alarms, runbook, support boundary, backup/recovery
   treatment and known limitations.

General availability additionally requires repeated successful pilots,
security review, recovery evidence, clear customer documentation and an
explicit product release decision.

## Maintenance cadence

| Cadence | Work | Release bar |
| --- | --- | --- |
| Continuous | Triage provider deprecations, critical CVEs, security advisories, service outages and broken provider contracts | Pause affected execution immediately when a safety assumption is invalid; publish a bounded fix or disable the adapter |
| Monthly | Review AWS service changes, SDK/provider versions, regional availability, quotas, pricing inputs, guardrails, test fixtures and documentation | Low-risk catalogue or planning updates require tests and review; no automatic expansion of cloud permissions |
| Quarterly | Reassess top customer requests, cost/performance evidence, architecture patterns, support incidents, recovery drills and the next two pilot candidates | Publish a versioned catalogue decision and keep unsupported demand as documented backlog, not implied capability |
| Per adapter release | Run contract, policy, failure, idempotency, security and real-AWS pilot evidence | Meet the acceptance gate above, then release behind explicit enablement |
| Per customer execution | Revalidate account, region, identity, plan digest, budget, quota and approved scope | Human approval remains required; cached discovery or a prior approval is insufficient |

The practical rule is: update existing adapters monthly for safety and
provider drift; consider new patterns quarterly; ship an execution adapter only
after its own controlled pilot proves it.

## Prioritisation

For the current product, the next candidates should be selected by customer
demand and evidence, not catalogue size:

1. Finish product-driven App Runner output ingestion and failure recovery.
2. Add an ECS Fargate adapter for multi-container/API-worker services when a
   customer needs it.
3. Add static web plus serverless API as the cheapest common composition.
4. Add event/job and data-store modules as bounded companions to those
   workloads.
5. Add managed AI/RAG only with evaluation, data-boundary and cost controls.
6. Treat EKS, custom GPU and hybrid networking as high-risk specialised
   patterns, never baseline functionality.

This is intentionally a living catalogue, not a claim of universal cloud
coverage.
