# Nova capability and execution evidence matrix

Status snapshot: backend `main` at `653619d` (PR #402), 2026-11-13. Merged-main
CI run [43515569852](https://github.com/Bepoadewale/davdeploy/actions/runs/43515569852)
passed all seven jobs. This source snapshot is not a deployment claim.

This document joins the checked-in architecture catalogue, Terraform
implementation registry, scenario catalogue and existing evidence. A catalogue
entry, a Terraform root, provider-schema validation, or an isolated AWS service
test does not by itself prove that Nova can safely deploy that capability for a
customer.

## Evidence meanings

- **Scenario** is exact membership from `certification_factory.py`. A dash means
  the module is not named by any current scenario.
- **Candidate roots** are a documentation cross-reference by resource purpose.
  The runtime registries do not currently declare a binding between these
  catalogues; a candidate is not an executable mapping.
- **Service evidence** links to the strongest relevant repository record found.
  `docs/test/` AWS tests are isolated service/root tests unless explicitly
  described otherwise. They are not Nova-hosted customer execution.
- **Policy evidence** describes the shared generated-plan checks in
  `generated_plan_policy.py`, not a complete policy for the named module.
- **Plan price** means an independently sourced regional estimate for the exact
  generated plan, with assumptions and timestamp. `FixturePricingCatalog`
  profile ranges and Cost Explorer history do not meet this definition.
- **Hosted lifecycle** means the Nova-generated saved plan was dispatched by
  the hosted customer runner and its application behavior, update/failure
  recovery, and cleanup were observed. No such evidence is recorded for the
  listed catalogue modules or roots in this snapshot.

## Cross-cutting evidence status

| Area | Implemented evidence | Coverage limit in this snapshot |
|---|---|---|
| Proposal/schema checks | `generated_provider_validation.py` checks generated resource types and arguments against the initialized, locked AWS provider schema. [`ticket309.md`](../tickets/ticket309.md) records a synthetic S3 schema check; [`test311.md`](../test/test311.md) records the later authenticated S3 saved-plan run with the locked provider schema. | This verifies Terraform schema shape, not service semantics, customer security, cost, or lifecycle behavior. There is no per-module schema-version/evidence binding in either registry. |
| Generated-plan policy | `generated_plan_policy.py` binds trusted account/region and proposal inventory; reviews destructive and sensitive changes; checks policy-critical unknowns for a finite list of Terraform types; and contains S3, IAM, security-group/network-ACL ingress, EC2 metadata, and relational-database rules. PRs #401/#402 are merged source; [`test401.md`](../test/test401.md) and [`test402.md`](../test/test402.md) record synthetic/local tests and hosted CI. Draft PR #404 adds a same-plan EKS node-group/launch-template IMDSv2 check; [`test404.md`](../test/test404.md) will record its source evidence. | Partial shared rules only. Unknown-value checks cover only paths in `POLICY_CRITICAL_UNKNOWN_PATHS`. ACL association, route/egress reachability, EKS node metadata (until #404 is merged, deployed, and exercised on a customer plan), and a complete deterministic policy map for all 26 modules or 30 roots are not established. The policy changes have not been deployed or exercised on a customer plan. See the resource-family table below. |
| Cost | `evidence.py` has `FixturePricingCatalog` profile ranges. `integrations.py` can capture a sample AWS Pricing API query and historical Cost Explorer totals during discovery. | No independent, resource-by-resource regional quote for a Nova generated plan, no complete usage model for requests/storage/transfer/idle resources, and no verified hard budget cap. All rows below therefore say **not evidenced** for plan pricing. |
| Workload health | `certification_factory.py` declares textual readiness probes for eight scenario names. Some isolated AWS evidence below records real service requests or traffic. | The scenario declarations are not proof that the hosted worker ran the probes. The current `CertificationEvidence` is five booleans (apply, destroy, readiness, rollback, cleanup); it does not record update, controlled failure, cost, source/artifact digest, or evidence link. |
| Update/recovery/cleanup | Some service-level evidence records create and destroy; the scenario declarations include rollback and cleanup descriptions. | No complete Nova-hosted composed application evidence for update, injected failure, recovery, exact ownership-based destroy, and independent absence verification. A scenario label is not an observed result. |
| Hosted execution | The repository records an App Runner customer workload pilot in [`test42.md`](../test/test42.md). PR #314 added durable saved-plan storage and administrator approval; its ticket states the hosted worker has no caller and apply/destroy are unavailable on this path. | The App Runner pilot is a separate legacy renderer, not Nova-generated composed execution. No Nova-hosted plan-to-apply customer workload is evidenced here. Hosted control-plane health is not workload health. |

### Resource families checked by the current generated-plan policy

| Check | What code checks | What it does not establish |
|---|---|---|
| Scope and plan | Trusted account and region guard; declared-resource inventory; malformed/non-applyable plans; destructive changes and sensitive changes require review. | Resource ownership for every AWS type, quota availability, or workload suitability. |
| S3 | Requires all four public-access-block flags for planned buckets; denies public ACLs and public bucket policies. | It does not universally require an encryption configuration to exist or validate every bucket use pattern. Unknown-value checks cover listed S3 policy-critical fields only. |
| IAM | Denies broad wildcard privileges, wildcard trust, unknown policy attachments, and application `AdministratorAccess`. | Complete least-privilege analysis across service-specific policies, resource-based policies, permission boundaries, and all generated trust relationships. |
| Network | Reviews public security-group and network-ACL web/general ingress; denies all-protocol and listed sensitive-port exposure; unknown ACL ingress sources fail closed. Globally routable source ranges are recognized. | ACL association and rule-precedence reachability, complete VPC topology, egress, endpoint policy, DNS, TLS, VPN, multi-region, or service-to-service reachability review. |
| Databases and unknowns | Denies public RDS/Redshift, requires encryption for the listed relational types, and checks unknown critical fields for the bounded resource/path list. | Backup restore evidence, workload data integrity, every database product, every retention setting, or unknown values on unlisted types. |

## Architecture catalogue: all 26 entries

`Candidate roots` are semantic references only; there is no authoritative
catalogue-to-root dispatch binding. The policy column refers to the shared
checks above and names the closest implemented resource-family checks. All
rows have **no plan price evidence** and **no Nova-hosted lifecycle evidence**
unless the limitation says otherwise.

| Architecture module | Existing scenario | Candidate implementation roots | Shared policy evidence / gap | Service-level evidence (not hosted Nova proof) | Remaining health/lifecycle evidence |
|---|---|---|---|---|---|
| `aws-observability` | — | No matching observability root | No CloudWatch/OTel-specific plan rule | No mapped workload probe | No module-specific alert delivery, health-history, update, recovery, or cleanup proof |
| `aws-secrets-config` | — | `aws-kms-key`, `aws-parameter-config` | IAM checks apply to IAM resources; KMS unknown fields are bounded. No secret retrieval/exposure policy is mapped to this module. | No mapped secret/config workload probe | No secret rotation, runtime retrieval, redaction-at-use, update, or recovery proof |
| `aws-edge-https` | `multi-region` | `aws-dns-zone`, `aws-acm-certificate`, `aws-cloudfront-delivery`, `aws-multi-region-dns` | No CloudFront, certificate, DNS ownership, or failover policy suite | [`test253.md`](../test/test253.md) HTTPS content; [`test254.md`](../test/test254.md) ACM/SES DNS validation; [`test260.md`](../test/test260.md) public failover | No Nova-hosted edge lifecycle or per-plan TLS/domain cost evidence |
| `aws-static-web` | `web-application` | `aws-s3-private-storage`, `aws-cloudfront-delivery` | S3 public-access checks apply; no private-origin/cache/deployment policy suite | [`test253.md`](../test/test253.md) served HTTPS content | No Nova-hosted source-to-site build, update/rollback, or cleanup proof |
| `aws-serverless-api` | `web-application` | `aws-api-gateway-http`, `aws-lambda-service` | Shared IAM/network rules only; no API auth, throttling, or Lambda runtime-specific plan policy | [`test268.md`](../test/test268.md) real isolated HTTP 200 and teardown through a separate serverless renderer root | No Nova-hosted plan/apply or composed API/data/queue health proof |
| `aws-managed-application` | `saas-backend` | No root in the 30-entry registry; separate App Runner renderer | Shared IAM/network checks only; no App Runner-specific policy map | [`test42.md`](../test/test42.md) records a separate App Runner customer workload pilot | No Nova-generated App Runner plan evidence; the pilot does not prove composed Nova execution |
| `aws-container-service` | `kubernetes` | `aws-ecr-image` (partial; ECS/Fargate and ALB roots are absent) | Shared IAM/network checks only; no container image, task role, or service deployment policy | [`test255.md`](../test/test255.md) is EKS, not ECS/Fargate evidence | No ECS/Fargate API-plus-worker behavior, update, recovery, or cleanup proof |
| `aws-virtual-machine-service` | — | `aws-ec2-autoscaling` | Merged source PR #402 checks IMDSv2 for planned `aws_instance`, `aws_launch_template`, and `aws_launch_configuration`, and requires regional metadata defaults to require tokens; no VM image, role, or host-hardening policy | [`test244.md`](../test/test244.md) records a zero-capacity Auto Scaling group reaching service-valid state | No guest application health, scaling behavior, patch/update, recovery, or hosted proof; metadata defaults can be overridden and are not account-wide enforcement |
| `aws-kubernetes-platform` | `kubernetes` | `aws-eks-cluster`, `aws-ecr-image`, `aws-vpc-private-network` | Shared IAM/network checks only; no Kubernetes RBAC, admission, node, or cluster policy suite | [`test255.md`](../test/test255.md) deployed a workload and probed its service | No Nova-hosted cluster lifecycle, upgrade/failure recovery, or independent cleanup proof |
| `aws-identity` | `web-application` | No Cognito or application-identity root | No customer-identity tenant/MFA/session policy in generated-plan policy | No customer workload identity probe mapped to this module | No Nova-hosted sign-up, authorization, revocation, or identity-recovery proof |
| `aws-relational-data` | `saas-backend` | `aws-aurora-postgres` | RDS public-access/encryption checks; unknown deletion-protection/final-snapshot fields are bounded | [`test244.md`](../test/test244.md) records Aurora available before teardown; no application query is recorded | No application read/write, restore/integrity, migration, update, or hosted cleanup proof |
| `aws-nosql-data` | `saas-backend` | `aws-dynamodb-table` | Unknown DynamoDB encryption/deletion-protection fields are checked; no complete known-value policy suite | [`test244.md`](../test/test244.md) records encryption and point-in-time recovery | No hosted application read/write, restore, update, or independent cleanup proof |
| `aws-file-storage` | `ai-rag` | `aws-s3-private-storage`, `aws-efs-shared-storage` | S3 public-access checks; no EFS mount/access or file-retention policy map | [`test262.md`](../test/test262.md) used private S3 input for KB ingestion; [`test244.md`](../test/test244.md) recorded EFS available | No customer upload/download authorization, file integrity, update, or hosted cleanup proof |
| `aws-jobs-events` | `saas-backend`, `async-data` | `aws-sqs-queue`, `aws-eventbridge-bus`, `aws-step-functions`, `aws-sns-notifications`, `aws-ses-email` | Shared IAM rules only; no event-source, DLQ/retry, idempotency, delivery, or email policy suite | [`test257.md`](../test/test257.md) proves EventBridge-to-SQS delivery; [`test256.md`](../test/test256.md) proves a Step Functions execution | No consumer-to-completion, retry/DLQ transition, notification delivery, update, or hosted recovery proof |
| `aws-realtime` | — | No WebSocket or AppSync root; DynamoDB root is only a partial resource overlap | No subscription authorization/message fan-out policy | No mapped real-time probe | No connect/publish/receive, reconnect, update, or cleanup evidence |
| `aws-search` | `ai-rag` | `aws-opensearch` | Shared IAM/network checks only; no index/document authorization or exposure policy suite | [`test262.md`](../test/test262.md) proves KB retrieval using OpenSearch Serverless; [`test244.md`](../test/test244.md) records an OpenSearch domain ready | No general application-search query, reindex/update, recovery, or hosted proof |
| `aws-payments-webhooks` | — | `aws-api-gateway-http`, `aws-lambda-service`, `aws-sqs-queue` are only generic building blocks | No provider-signature, replay, idempotency, payment-data, or webhook abuse policy | No external payment/webhook behavior is evidenced | No provider-backed event delivery, reconciliation, retry, update, or cleanup proof |
| `aws-ai-retrieval` | `ai-rag` | `aws-bedrock-runtime`, `aws-bedrock-knowledge-base`, `aws-s3-private-storage`, `aws-opensearch`, `aws-lambda-service` | Shared S3/IAM/network checks; no end-to-end prompt/data access policy suite | [`test262.md`](../test/test262.md) ingested a synthetic document and returned grounded text; [`test244.md`](../test/test244.md) records guardrail readiness only | No hosted customer application, authorization, model cost, update, recovery, or cleanup proof |
| `aws-managed-ml` | `machine-learning` | `aws-sagemaker-endpoint` | Shared IAM/S3/network checks only; no model artifact provenance, endpoint access, or inference cost policy | [`test261.md`](../test/test261.md) records real SageMaker inference and teardown | No Nova-hosted training/model deployment or update/recovery proof |
| `aws-cpu-inference` | — | `aws-sagemaker-endpoint` is a possible resource overlap; no CPU-specific implementation | No inference image, endpoint access, scaling, or model-data policy | [`test261.md`](../test/test261.md) is a SageMaker endpoint test, not evidence for this planner capability | No CPU-inference selection, load, update, recovery, or hosted proof |
| `aws-gpu-inference` | — | `aws-sagemaker-endpoint`, `aws-eks-cluster`, `aws-ec2-autoscaling` are partial overlaps | No GPU quota, accelerator, artifact, endpoint, or spend guard | No GPU inference evidence found | No GPU workload, cost, health, update, recovery, or cleanup proof |
| `aws-data-analytics` | `async-data` | `aws-s3-private-storage`, `aws-batch-compute`; Glue/Athena roots are absent | Shared S3/IAM checks only; no data catalog, query exposure, or retention policy | [`test252.md`](../test/test252.md) proves a Batch job, not a Glue/Athena analytics pipeline | No ingestion-to-query result, update, recovery, or hosted proof |
| `aws-stream-processing` | `async-data` | `aws-kinesis-stream`; MSK root is absent | Shared IAM/network checks only; no stream encryption/retention/consumer policy suite | [`test258.md`](../test/test258.md) proves one Kinesis record was accepted | No consumer processing, replay, shard scaling, failure/recovery, or hosted proof |
| `aws-media` | — | `aws-s3-private-storage`, `aws-cloudfront-delivery`; MediaConvert root is absent | Shared S3/network rules only; no media ingest/transcode/access/retention policy | No media workload evidence found | No upload/transcode/playback, update, failure recovery, pricing, or cleanup proof |
| `aws-private-connectivity` | `hybrid-network` | `aws-vpc-private-network`, `aws-site-to-site-vpn` | Shared security-group ingress rule only; no route, peer, egress, or tunnel-policy suite | [`test263.md`](../test/test263.md) proves encrypted routed probe traffic | No Nova-hosted customer network, route change/recovery, or independent cleanup proof |
| `aws-backup-recovery` | `multi-region` | No AWS Backup vault/plan/restore implementation root; S3 and DNS roots are not backup proof | No backup-retention/restore-integrity policy or RPO/RTO enforcement | [`test260.md`](../test/test260.md) proves DNS failover, not backup or restore | No backup creation, restore/data-integrity drill, recovery timing, or cleanup proof |

## Terraform implementation registry: all 30 roots

The `catalogue candidate` column is descriptive only; the implementation
registry does not declare these relationships. The `policy` column lists only
current generated-plan checks that apply by resource type. Every row has **no
independent generated-plan price evidence** and **no Nova-hosted lifecycle
proof**. Linked tests are isolated AWS service/root evidence, not hosted
customer execution.

| Implementation ID | Terraform root | Catalogue candidate / existing scenario | Current applicable plan-policy checks | Existing service-level evidence |
|---|---|---|---|---|
| `aws-dns-zone` | `modules/dns-zone` | `aws-edge-https` / `multi-region` | Shared account/region/destructive checks; no DNS-specific rule | [`test260.md`](../test/test260.md), [`test244.md`](../test/test244.md) |
| `aws-acm-certificate` | `modules/acm-certificate` | `aws-edge-https` / `multi-region` | Shared checks only; no certificate/domain validation policy | [`test254.md`](../test/test254.md) |
| `aws-kms-key` | `modules/kms-key` | `aws-secrets-config` (candidate; KMS not listed in module services) / no scenario | Unknown `key_usage` and deletion window are checked; no full key-policy/rotation/consumer binding policy | `test244` used AWS-managed KMS encryption for Kinesis, not this customer-managed-key root; no root-specific evidence found |
| `aws-parameter-config` | `modules/parameter-config` | `aws-secrets-config` / no scenario | Shared IAM checks only; no parameter tier, secret exposure, or rotation rule | No root-specific workload evidence found |
| `aws-feature-flags` | `modules/feature-flags` | No matching catalogue module / no scenario | No AppConfig-specific policy | No root-specific workload evidence found |
| `aws-s3-private-storage` | `modules/artifacts` | `aws-file-storage`, `aws-static-web`, `aws-ai-retrieval` / `ai-rag`, `web-application` | S3 block-public-access and public ACL/policy checks; bounded unknown fields; not a complete private-upload policy | [`test262.md`](../test/test262.md) private source bucket; not hosted `modules/artifacts` lifecycle evidence |
| `aws-cloudfront-delivery` | `modules/cloudfront-delivery` | `aws-edge-https`, `aws-static-web` / `multi-region`, `web-application` | No CloudFront origin/TLS/cache policy | [`test253.md`](../test/test253.md) |
| `aws-api-gateway-http` | `modules/api-gateway-http` | `aws-serverless-api`; generic API building block for payments / `web-application` | Shared network/IAM checks only; no route auth, authorizer, throttling, or WAF rule | [`test268.md`](../test/test268.md) |
| `aws-lambda-service` | `modules/lambda-service` | `aws-serverless-api`, `aws-ai-retrieval`; generic building block for other APIs / `web-application`, `ai-rag` | Shared IAM checks only; no Lambda-specific execution-role, egress, secret, or artifact policy | [`test268.md`](../test/test268.md) exercises Lambda through a separate serverless renderer root; no Nova-hosted function proof |
| `aws-ecr-image` | `modules/ecr` | `aws-managed-application`, `aws-container-service`, `aws-kubernetes-platform` / `saas-backend`, `kubernetes` | No ECR image provenance, scan, or immutability rule | No ECR push-and-run evidence mapped to this root |
| `aws-aurora-postgres` | `modules/aurora-postgres` | `aws-relational-data` / `saas-backend` | RDS public access/encryption and bounded deletion/final-snapshot unknown checks | [`test244.md`](../test/test244.md): Aurora available; no app query or restore |
| `aws-dynamodb-table` | `modules/dynamodb-table` | `aws-nosql-data` / `saas-backend` | Bounded unknown checks for SSE enabled and deletion protection; no full known-value DynamoDB policy suite | [`test244.md`](../test/test244.md): SSE and point-in-time recovery; no app read/write |
| `aws-elasticache-redis` | `modules/elasticache-redis` | No cache module in catalogue / no scenario | No Redis-specific encryption, auth, network, or failover rule | [`test244.md`](../test/test244.md): replication group available; no client operation |
| `aws-opensearch` | `modules/opensearch` | `aws-search`, `aws-ai-retrieval` / `ai-rag` | Shared IAM/network checks only; no OpenSearch domain/collection access policy | [`test244.md`](../test/test244.md) domain ready; [`test262.md`](../test/test262.md) uses OpenSearch Serverless for KB retrieval |
| `aws-efs-shared-storage` | `modules/efs-shared-storage` | No explicit EFS catalogue module; possible `aws-file-storage` overlap / no exact scenario mapping | Shared network/IAM checks only; no EFS mount/access-point policy | [`test244.md`](../test/test244.md): EFS available; no file read/write |
| `aws-sqs-queue` | `modules/sqs-queue` | `aws-jobs-events`, `aws-payments-webhooks` / `saas-backend`, `async-data` | Shared IAM checks only; no queue policy, encryption, retry, or DLQ contract | [`test257.md`](../test/test257.md): real EventBridge delivery to SQS |
| `aws-eventbridge-bus` | `modules/eventbridge-bus` | `aws-jobs-events` / `saas-backend`, `async-data` | Shared IAM checks only; no event bus/rule target authorization policy | [`test257.md`](../test/test257.md): real event delivery |
| `aws-step-functions` | `modules/step-functions` | `aws-jobs-events` / `saas-backend`, `async-data` | Shared IAM checks only; no state-machine role/state-data policy | [`test256.md`](../test/test256.md): execution completed |
| `aws-sns-notifications` | `modules/sns-notifications` | `aws-jobs-events` / `saas-backend`, `async-data` | Shared IAM checks only; no topic/subscribe confirmation or delivery policy | [`test257.md`](../test/test257.md) created a topic; its observed behavior was EventBridge-to-SQS, not SNS delivery |
| `aws-ses-email` | `modules/ses-email` | Notification/email gap under `aws-jobs-events` / no exact scenario binding | Shared checks only; no deliverability, recipient, or sandbox-exit policy | [`test254.md`](../test/test254.md): identity/DKIM verification, not application email delivery |
| `aws-bedrock-runtime` | `modules/bedrock-runtime` | `aws-ai-retrieval` / `ai-rag` | Shared IAM checks only; no model access, guardrail invocation, or token-cost policy | [`test244.md`](../test/test244.md): guardrail resource ready; no model/guardrail request |
| `aws-bedrock-knowledge-base` | `modules/bedrock-knowledge-base` | `aws-ai-retrieval` / `ai-rag` | Shared S3/IAM/network checks; no ingestion-role/index/data-access policy suite | [`test262.md`](../test/test262.md): ingestion and real retrieval |
| `aws-sagemaker-endpoint` | `modules/sagemaker-endpoint` | `aws-managed-ml`; possible CPU/GPU overlap / `machine-learning` | Shared IAM/S3/network checks only; no model artifact, endpoint exposure, quota, or inference cost policy | [`test261.md`](../test/test261.md): real endpoint inference and teardown |
| `aws-kinesis-stream` | `modules/kinesis-stream` | `aws-stream-processing` / `async-data` | Shared IAM checks only; no stream retention, consumer, throughput, or data-key policy suite | [`test258.md`](../test/test258.md): one record accepted; no consumer processing |
| `aws-batch-compute` | `modules/batch-compute` | `aws-jobs-events`, `aws-data-analytics` / `saas-backend`, `async-data` | Shared IAM/network checks only; no queue/job role, retry, capacity, or budget policy suite | [`test252.md`](../test/test252.md): controlled disposable Batch job |
| `aws-eks-cluster` | `modules/eks` | `aws-kubernetes-platform`, `aws-gpu-inference` / `kubernetes` | Shared IAM/network checks only. Draft PR #404 checks managed-node metadata only when the plan binds one in-plan launch template with IMDSv2 required; it does not cover Kubernetes/RBAC/quota policy. | [`test255.md`](../test/test255.md): workload service probe through EKS |
| `aws-ec2-autoscaling` | `modules/ec2-autoscaling` | `aws-virtual-machine-service`, possible GPU compute / no scenario for VM/GPU | Merged-source IMDSv2 checks cover `aws_instance`, `aws_launch_template`, `aws_launch_configuration`, and regional defaults; no AMI, capacity, patching, or instance spend policy | [`test244.md`](../test/test244.md): zero-capacity ASG reached service-valid state |
| `aws-vpc-private-network` | `modules/vpc` | `aws-private-connectivity` / `hybrid-network` | Security-group ingress checks only; no VPC topology, egress, endpoint, route, or NAT policy | [`test244.md`](../test/test244.md) VPC for EKS; [`test263.md`](../test/test263.md) includes routed topology |
| `aws-site-to-site-vpn` | `modules/site-to-site-vpn` | `aws-private-connectivity` / `hybrid-network` | Shared network checks only; no peer, tunnel, route propagation, or encryption policy | [`test263.md`](../test/test263.md): encrypted routed traffic; [`test244.md`](../test/test244.md) was lifecycle-only with tunnels down |
| `aws-multi-region-dns` | `modules/multi-region-dns` | `aws-edge-https`, `aws-backup-recovery` / `multi-region` | No failover health-check/record/region policy | [`test260.md`](../test/test260.md): public DNS failed over between two endpoints; not backup/restore evidence |

## Explicit coverage gaps

1. **Unassigned catalogue modules:** `aws-observability`,
   `aws-secrets-config`, `aws-virtual-machine-service`, `aws-realtime`,
   `aws-payments-webhooks`, `aws-cpu-inference`, `aws-gpu-inference`, and
   `aws-media` are not in a current certification scenario.
2. **Missing catalogue-to-root capabilities:** no registered root for Cognito,
   ECS/Fargate or ALB, App Runner (it uses a separate legacy path), WebSocket or
   AppSync, Secrets Manager, CloudWatch/OTel, Glue/Athena, MSK, MediaConvert,
   or AWS Backup. Existing roots such as EFS, Redis, SES, and AppConfig do not
   have an exact catalogue contract.
3. **No authoritative binding:** scenario manifests list architecture module
   IDs; the 30-entry implementation registry is independent. The semantic
   cross-references above are not executable bindings.
4. **Policy is incomplete by module:** schema validation is not a security
   policy. The existing generated-plan checks do not establish least privilege,
   service-specific safe configuration, quota, recovery, or ownership for all
   26/30 entries.
5. **No per-plan cost proof:** fixture profile ranges and historical account
   spend do not price the generated plan. Every row needs product/region,
   runtime/traffic/storage/transfer assumptions, a captured catalog source and
   timestamp, and an explicit unknown-cost outcome.
6. **Service evidence is not composed hosted evidence:** no scenario currently
   proves, through the Nova hosted runner, create/invoke/observe/update/failure
   recovery/destroy/independent absence. `test244.md` records useful resource
   lifecycle checks, while tests #252–#268 prove selected direct AWS behavior;
   neither set is the package's hosted customer acceptance.
7. **Certification record is too small for the goal gate:** record a durable
   test ID, exact main/deployed commit and artifact digests, target account and
   region, cost estimate/actual delayed bill note, resource ownership manifest,
   each behavior result, rollback/recovery result, retained resources, and
   independent absence check. Add update and controlled-failure outcomes rather
   than inferring them from a single `rollback_proven` boolean.

## Status rule

Update individual rows only when the linked evidence exists. Use separate
labels for catalogued, contract-tested, provider-schema-validated,
plan-policy-tested, isolated-AWS-tested, hosted-plan-tested,
hosted-lifecycle-tested, and cleanup-verified. Do not promote a root to hosted
customer support based on this documentation, CI, Terraform validation, or an
isolated service certification. The existing renderer and hosted execution
gates remain the authority for runtime eligibility.
