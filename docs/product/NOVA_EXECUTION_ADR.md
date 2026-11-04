# Nova-led infrastructure generation and execution

**Status:** proposed; generic hosted execution is not implemented or certified.

This record is the technical decision for DavDeploy's private backend. The full
goal, access notes and implementation handoff remain in a local file outside
Git. Do not copy that private material into either repository.

## Decision

Use Nova to interpret workload intent, choose AWS resources, compose an
architecture, generate Terraform configuration, explain trade-offs and revise
a proposal after bounded validator feedback. Keep Terraform as the one general
execution engine. Do not add a general CloudFormation engine or require a
handwritten full renderer for every AWS service.

The model generates a versioned, typed proposal, not executable authority.
Trusted code owns tenant identity, account/region scope, IAM permissions,
policy, pricing evidence, Terraform state, plan/apply, approval, secrets,
observations, recovery and cleanup. Nova cannot approve its own plan, change
policy, receive cloud credentials, or issue arbitrary commands.

## Proposed lifecycle

1. Build context from natural-language intent, existing workspace constraints,
   repository evidence, and authorized account discovery.
2. Ask Nova for a structured resource graph with references, dependencies,
   requirements, outputs, health checks, cost assumptions, recovery needs and
   rationale. Pin and record model/prompt/schema versions and input digests.
3. Validate structure, provider schemas, allowed references and deterministic
   security policy. Inject provider, account, region, backend and state settings
   in trusted code. Never accept arbitrary generated Terraform expressions,
   provider/backend blocks, modules, provisioners, shell or local-file access.
4. Run Terraform validation and an isolated plan. Inspect actual planned
   changes for account/region, workspace scope, privilege escalation, public
   exposure, encryption, sensitive values, replacements/deletes, retention,
   artifacts, costs, permissions and quota evidence. Resolve or reject
   safety-critical unknown values.
5. Show costs, assumptions, trade-offs and actual resource changes. Bind the
   authenticated customer approval to the saved plan digest, context, source
   artifact, policy version and target account. A changed plan needs a new
   review and approval.
6. Execute only that saved plan with an isolated scoped role through the
   durable worker/CodeBuild path. Persist idempotent run state, lock ownership,
   callbacks and outcomes. On uncertain completion, reconcile before retry.
7. Verify application behavior with deterministic probes, record evidence,
   and handle update, recovery and exact owned-resource cleanup. Preserve
   customer data unless a specifically designed and approved migration or
   deletion operation applies.

Validation errors can be returned to Nova for bounded proposal repair. The
model cannot alter the rules that rejected its output. The final plan is
validated and approved again after any repair.

## Why this replaces per-service renderers

Terraform's provider schema and resource graph provide a common infrastructure
language. One isolated runner can execute the generated graph, while generic
policy inspects the real plan. This avoids writing a separate provision/apply
framework per AWS service. Small service-specific checks remain where AWS
behavior differs, such as health probes, migration/recovery, permissions or
data retention. Resource schema validity alone is not deployment certification.

Reuse current renderers as compatibility paths, schema examples, and regression
cases during migration. Do not switch off the existing App Runner path until
parity is demonstrated. Nova-generated output is currently plan-only and is
not connected to hosted CodeBuild; this ADR records a direction, not a shipped
capability.

## Finite coverage map

The following 26 architecture entries and 30 Terraform implementation entries
are the starting scope. A catalogue entry is not evidence that it deploys.
Each concrete configuration must map to a representative hosted scenario or a
targeted test. The eight scenario names are not permission to claim every
possible AWS service combination works.

| Architecture entry | Existing implementation roots or known gap | Proposed evidence path |
|---|---|---|
| aws-observability | KMS; parameter config; no complete observability lifecycle | SaaS and all scenario telemetry |
| aws-secrets-config | KMS; parameter config; feature flags | SaaS secret/config access and rotation boundary |
| aws-edge-https | DNS zone; ACM; CloudFront; no WAF renderer | Web app TLS, origin restrictions, exposure policy |
| aws-static-web | S3 artifacts; CloudFront | Web app served through distribution |
| aws-serverless-api | API Gateway HTTP; Lambda | Hosted API request, update and cleanup |
| aws-managed-application | Existing App Runner pilot | SaaS application compatibility |
| aws-container-service | ECR only; ECS/Fargate renderer gap | SaaS service and background worker |
| aws-virtual-machine-service | EC2 Auto Scaling | Representative VM service and cleanup |
| aws-kubernetes-platform | EKS | Kubernetes app, load balancer and teardown |
| aws-identity | No listed customer identity implementation root | Web app identity flow and tenant policy |
| aws-relational-data | Aurora PostgreSQL | SaaS writes, backup/restore and data safety |
| aws-nosql-data | DynamoDB | Web/API and async data-flow scenarios |
| aws-file-storage | Private S3 | Upload/read policy and exact cleanup |
| aws-jobs-events | SQS, EventBridge, Step Functions, SNS, Batch | Async/data job success and failure recovery |
| aws-realtime | No listed implementation root | Add targeted real-time test if in customer scope |
| aws-search | OpenSearch | AI/RAG retrieval and search query |
| aws-payments-webhooks | No listed payment provider implementation | Webhook contract; external payment setup disclosed |
| aws-ai-retrieval | Bedrock runtime and Knowledge Base | Synthetic ingestion and retrieval request |
| aws-managed-ml | SageMaker endpoint | Real inference, observe and destroy |
| aws-cpu-inference | No listed CPU inference root | Map to supported runtime and measure workload |
| aws-gpu-inference | No listed GPU implementation root | Targeted quota, invocation, cost and teardown test |
| aws-data-analytics | No listed analytics implementation root | Add a representative analytics workload test |
| aws-stream-processing | Kinesis stream | Real event write/consume behavior |
| aws-media | No listed media implementation root | Add a representative media workload test |
| aws-private-connectivity | VPC and site-to-site VPN | Real routed encrypted traffic |
| aws-backup-recovery | No listed backup implementation root | Restore, integrity and cleanup evidence |

The current implementation registry has 30 roots: DNS zone, ACM, KMS,
parameter config, feature flags, S3 artifacts, CloudFront, API Gateway HTTP,
Lambda service, ECR, Aurora PostgreSQL, DynamoDB, ElastiCache Redis, OpenSearch,
EFS, SQS, EventBridge, Step Functions, SNS, SES, Bedrock runtime, Bedrock
Knowledge Base, SageMaker endpoint, Kinesis, Batch, EKS, EC2 Auto Scaling, VPC,
site-to-site VPN, and multi-region DNS. Map these roots to typed customer
inputs/outputs, the eight application scenarios, lifecycle checks, pricing,
permissions, region/quotas, real hosted evidence and gaps in follow-up work.

The existing eight scenarios remain: web app, SaaS backend, async/data platform,
AI/RAG app, Kubernetes app, hybrid network, multi-region app, and ML endpoint.
Each requires real traffic or workload behavior, health observation, update,
controlled failure/recovery, destroy and independent absence checks. Add
targeted tests for coverage gaps; do not remove gaps from the matrix.

## Required security and operating properties

- Per-workspace/project/deployment state isolation, locking and ownership.
- IAM scope derives from deterministic rules; generated permissions cannot
  widen the executor role or customer role trust.
- Approval hashes bind actual saved plan, target account, source/artifact and
  policy/context revisions. Reject stale/tampered plans.
- No arbitrary model shell, Terraform CLI, cloud API, credentials or secrets.
- Prompt, retrieved repository text, docs and tool results are untrusted.
  Guardrails are supplementary, not authorization or execution policy.
- Durable idempotency, duplicate-event defense, worker restart reconciliation,
  bounded retries, partial-failure handling and alarms.
- Health claims come from deterministic customer-relevant observations.
  Terraform apply success alone is not application health.
- Cleanup uses exact state and ownership evidence, never broad tags alone.
  Terraform rollback is not a substitute for database recovery or data safety.
- Redact sensitive plan/state/output content from logs and model context.

## Launch gates

1. The finite coverage map links every catalogue entry and implementation root
   to support boundaries, permissions, prices, scenario evidence and gaps.
2. The generic proposal contract rejects malformed, cyclic, executable,
   cross-tenant and unscoped resource graphs.
3. Nova proposal correction has attempt/time bounds, provenance and regression
   cases; model outages fail clearly without silent production fixtures.
4. Provider schemas, Terraform validation and actual-plan policies reject
   unsafe exposure, privilege escalation, stale/tampered approval, unexpected
   destructive changes and unpriced critical unknowns.
5. One composed Nova-generated application passes the hosted lifecycle through
   the generic runner with real requests, failure/recovery and verified cleanup.
6. All eight scenarios plus targeted gap tests prove their declared lifecycle
   behavior through hosted execution; spending and retained resources are
   recorded honestly.
7. Browser, CLI and MCP use the same authorized plan/apply/evidence workflow.
8. Security tests cover tenant isolation, approval, artifact, callback,
   concurrency, worker restart, retries, state locking and cleanup boundaries.
9. Changes are reviewed, required checks pass, deployments are confirmed, and
   no unexplained operations or disposable workloads remain.

Passing these gates certifies the declared finite configurations, not arbitrary
AWS infrastructure. Normal compatibility, AWS account permissions, service
quotas, budget limits, regional availability and external-provider setup remain
real deployment conditions. There is no service-tier/operator unlock; the
system either validates and supports a request or gives a clear reason it
cannot safely execute it yet.

## Research references

- Nova structured output and tools:
  https://docs.aws.amazon.com/nova/latest/nova2-userguide/advanced-prompting-techniques.html
- Terraform provider schema:
  https://developer.hashicorp.com/terraform/cli/commands/providers/schema
- Saved plans and sensitive plan artifacts:
  https://developer.hashicorp.com/terraform/cli/commands/plan
- Bedrock prompt-attack guardrail scope:
  https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-prompt-attack.html

## Evidence and boundaries for this PR

This ADR is a proposal and coverage map only. It does not change runtime code,
enable a renderer, grant cloud permissions, or claim a deployed capability.
Update this decision as implementation and real evidence establish or revise
the contract. Keep the complete private implementation goal outside the repo.
