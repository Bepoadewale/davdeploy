# Nova capability and execution evidence matrix

Status snapshot: backend `main` at
`f58b308376f759e45e63e3d7c79422f84bbdfd40` (PR #503), 2026-11-25. Merged PR
#502 adds source-only assumption-bound NAT/network pricing; all seven checks
passed on final PR head `86b4b89` in run
[45578164764](https://github.com/Bepoadewale/davdeploy/actions/runs/45578164764).
Merged PR #503 adds source-only Lambda function plan bounds as
`f58b308`; final PR head `08ace0b` passed all seven checks in run
[45582032631](https://github.com/Bepoadewale/davdeploy/actions/runs/45582032631),
and automated review found no issues. Neither package changes hosted runtime or
AWS resources. Merged PRs
#492 and #496 record the bootstrapped growth strategy as roadmap-only; they
change no product behavior or AWS resources. Merged PR #497 corrects the
source-level Nova plan-only status; merged PRs #498 and #499 add source-only
Batch and EKS generated-plan bounds, merged PR #500 adds bounded VPC topology
and egress review, and merged PR #501 reconciles the evidence snapshot. Merged
PRs #502 and #503 add assumption-bound NAT pricing and bounded Lambda policy in
source; all
seven checks passed on final PR head `86b4b89` in run
[45578164764](https://github.com/Bepoadewale/davdeploy/actions/runs/45578164764).
These PRs do not change the hosted runtime or AWS state.
PR #500 final-head CI passed all seven checks in
[run 45552193668](https://github.com/Bepoadewale/davdeploy/actions/runs/45552193668).
Merged PR #493's final-head CI run
[45515203315](https://github.com/Bepoadewale/davdeploy/actions/runs/45515203315)
passed all seven checks. Its exact synthetic Parameter Store lifecycle created
and updated version 1 to version 2, verified both values in memory without
printing them, destroyed the exact parameter through the Terraform run
monitor, and independently confirmed absence. Local state and plans are
retained with mode 600; Nova dispatch is not claimed. PR #413
merged this 26-architecture-entry / 30-root coverage ledger. The last recorded
hosted release remains PR #420 commit
`9951caa9244128b1551fea3af66b1bdbf884c800`, applied by
[run 43982396577](https://github.com/Bepoadewale/davdeploy/actions/runs/43982396577)
after plan [run 43981566184](https://github.com/Bepoadewale/davdeploy/actions/runs/43981566184).
The hosted control plane was not accessed or changed for this reconciliation.

PR #485 is merged and records direct same-account Auto Scaling scale/health/
teardown evidence for its bounded shape. PR #486 remains open and now includes
current `main` through merge commit `05a6e5c`; all seven checks passed on its
prior head in run
[45545915711](https://github.com/Bepoadewale/davdeploy/actions/runs/45545915711).
Its encrypted root-volume tests passed. The clean-room run passed through
`make verify`, but final cleanup remains pending explicit approval; generated
artifacts remain preserved. PR #487 is merged and
records exact-module DynamoDB point-in-time recovery and teardown. PR #489 is
merged with final-head CI run [45487279034](https://github.com/Bepoadewale/davdeploy/actions/runs/45487279034)
and merged-main run [45488186730](https://github.com/Bepoadewale/davdeploy/actions/runs/45488186730)
passing all seven checks. It records exact-module Lambda v1 invocation,
in-place v2 update, teardown, and independent absence verification. A read-only AWS check found no matching
DynamoDB test table, Auto Scaling group, EC2 instance, or Lambda test resources.
These tests count only for the tested shapes and do not establish Nova
dispatch. Draft PR #495 records a direct AppConfig rollout/rollback test; its
application, profile, rollout strategy, and deployment history remain
preserved pending exact teardown approval. Read-only checks observed the
environment as `Reverted` and deployments 1 and 2 as `COMPLETE` then
`REVERTED`. The Terraform monitor has 66 records and no active operations.

PR #473 merged with seven checks passing in CI run
[45284594649](https://github.com/Bepoadewale/davdeploy/actions/runs/45284594649).
It adds source-only DynamoDB safety checks and enables deletion protection in
the bounded module. No AWS table was created, and this adds no application,
restore, complete-cost, or Nova-dispatch evidence.

PR #475 merged with seven checks passing in CI run
[45288480162](https://github.com/Bepoadewale/davdeploy/actions/runs/45288480162).
It adds bounded source-only Kinesis policy checks; no AWS stream was created.

PR #476 reconciles the status, backlog, and evidence snapshot through PR #475;
its final seven checks passed in CI run
[45290021353](https://github.com/Bepoadewale/davdeploy/actions/runs/45290021353).
No workload or cloud resource was created.

PR #479 merged with all seven checks passing in final-head CI run
[45373475770](https://github.com/Bepoadewale/davdeploy/actions/runs/45373475770)
and merged-main CI run
[45374665792](https://github.com/Bepoadewale/davdeploy/actions/runs/45374665792).
Its source-only ElastiCache checks require Redis OSS 7.1, one `cache.t4g.micro`
node, TLS-required connections, a sensitive AUTH token applied with the `SET`
strategy, and exact TCP/6379 ingress bound to the replication group's
security group. The token can enter Terraform plan/state and therefore
requires the existing protected, encrypted artifact/state handling. No Redis
workload, client authentication, failover, lifecycle, complete price, or Nova
execution is proven.

PR #399 adds the exact-plan Nova apply path and customer role template in
source; its apply and credential gates remain disabled. PR #437's isolated
same-account ECS Express run is accepted by the owner as the general
customer-side plan/apply/health/update/recovery/teardown gate for the exact ECS
shape tested. A properly isolated same-account AWS lifecycle test can satisfy
the general customer-side lifecycle gate even when it uses direct Terraform;
it need not be dispatched by Nova. This does not prove Nova authorization,
dispatch, or credential issuance, cross-account isolation, or support for any
untested resource shape.

PR #443 merged as `e63d3ec`; seven checks passed in
[run 45065309558](https://github.com/Bepoadewale/davdeploy/actions/runs/45065309558).
Its temporary role test used the checked-in customer-role template and a
temporary same-account broker. Exact-plan session scopes allowed S3, SQS, and
DynamoDB create/read, SQS update, and a separate three-service destroy. The
test denied out-of-scope S3/SQS/DynamoDB creates and unrelated EC2 access.
Create/update/destroy policy sizes were 1,549/470/1,489 bytes. The stack, roles,
bucket, queue, and table were independently verified absent. This is direct
role-policy evidence, not Nova credential issuance, dispatch, cross-account
trust, or a complete permission attestation. See
[`test443.md`](../test/test443.md).

PR #445 merged as `c874b0d`; all seven checks passed in
[run 45072091356](https://github.com/Bepoadewale/davdeploy/actions/runs/45072091356).
Its source-only policy covers one-to-one SQS source/DLQ pairs, bounded retries,
exact DLQ allow lists, retention/visibility, and direct same-plan Lambda
consumer permissions. It is not deployed. Merged PR #446 fixes a Terraform
creation-order race and records direct SQS delivery, five source receives,
automatic DLQ transition, and isolated teardown in [`test446.md`](../test/test446.md).
PR #447 records five actual Lambda invocations/errors and delivery of
the same failed message to the paired DLQ at receive count six; the six-resource
stack and generated log group were independently confirmed absent. This proves
direct service behavior for that test shape, not Nova dispatch, idempotency,
producer authorization, complete effective permissions, or cost completeness.
Request pricing assumptions include source, retry, and DLQ requests; Lambda
usage and material transfer costs must still be separately bounded.

PR #438 template hosting and PR #441's SQS encryption rule remain source-only.
Merged PR #448 records direct SQS/Lambda/DynamoDB idempotency and redrive
recovery; its seven-resource stack and local state are confirmed absent. Merged
PR #449 records one exact-topic SNS-to-SQS delivery; its four-resource stack
and local state are confirmed absent. Merged PR #450 adds source-only
generated-plan binding checks for an exact planned SNS topic, SQS queue,
attached queue-policy URL, and conditional `SendMessage` grant; it is not
deployed. Merged PRs #451 and #452 add source-only EventBridge-to-SQS plan
binding, bounded retry, and exact DLQ checks.
KMS-backed queue encryption, unsupported consumer-policy shapes, and complete
regional cost coverage remain open. Nova authorization/dispatch evidence is a
separate product-integration gap; it is not a prerequisite for accepting
properly isolated direct customer-side lifecycle evidence for a tested shape.
PR #452's direct EventBridge-to-SQS test observed failure routing to a
rule-scoped DLQ, permission repair, successful recovery delivery, and cleanup;
see [`test452.md`](../test/test452.md). Its eight-resource test stack and
local state are absent, and the run monitor has no active operations. This
does not establish Nova dispatch or hosted execution.
PR #463 adds source-only KMS key-type, usage, rotation, Region-scope, and
deletion-window checks. It does not test AWS KMS or establish key-policy,
consumer-binding, cost, or lifecycle coverage; see
[`ticket463.md`](../tickets/ticket463.md).
PR #465 adds source-only SecureString, Standard-tier, and optional KMS key
reference checks for Parameter Store. Secret values can still be present in
Terraform state; no runtime retrieval or secret lifecycle is established. See
[`ticket465.md`](../tickets/ticket465.md).
PR #466 adds source-only OpenSearch module-shape, VPC-mode, encryption, HTTPS,
and TLS checks. Subnet/security-group binding, effective access, search
workload, lifecycle, and price remain unproven; see
[`ticket466.md`](../tickets/ticket466.md).
PR #468 adds source-only ACM request checks for DNS validation, RSA_2048, and
disabled export; domain ownership, DNS publication, issuance, renewal, and
production TLS remain unproven. See [`ticket468.md`](../tickets/ticket468.md).
PR #470 adds source-only Route 53 zone-name, VPC-association, and record-safe
deletion checks; ownership, delegation, record/failover behavior, lifecycle,
and cost remain open. See [`ticket470.md`](../tickets/ticket470.md).
PR #471 verifies an AppConfig environment binds to one same-plan application.
It adds no feature profile or deployment; flag lifecycle and price remain
unproven. See [`ticket471.md`](../tickets/ticket471.md).
Merged PR #454's direct Step Functions test records a Lambda task failure,
Catch recovery, a separate normal success path, and cleanup; see
[`test454.md`](../test/test454.md). The five-resource test stack and local
state are absent. This service evidence does not establish state-machine role
policy safety or Nova dispatch.
Current AWS reads found no tested
DavDeploy SageMaker endpoint, model, or endpoint configuration. The four
previously recorded tagged Batch definitions remain inactive, and PR #458's
test job definition is also inactive after exact teardown. The SageMaker
lineage action/context remain as retained audit evidence. The PR #443, #447, and #448 temporary resources
are absent; PR #448's local Terraform state is empty. The Terraform run
monitor has 41 terminal records and no active operations. Preserve the
protected untracked
`--only-show-errors`, `.venv-pr399/`, and retained lineage evidence.

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
- For the general Nova goal, the owner accepts PR #437's isolated ECS Express
  runs as customer-side plan/apply/health/update/recovery/teardown evidence under
  the required control-plane isolation. The runs used direct Terraform and do
  not establish Nova generation/dispatch, cross-account isolation, or
  Nova-originated lifecycle evidence.
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
| Nova intent provenance | Backend source PRs #425–#427 bound schema-repair attempts to 0–2, record the final validated proposal version/digest, and record a versioned digest of the original intent context across repairs. The context digest is attached to intent metadata and workload provenance without adding raw customer text. PR #429 separately binds the supported Terraform provider-schema format and canonical full-document digest to generated-plan evidence. | These changes are in backend `main` but not the deployed hosted runtime. Digests identify inputs; they do not prove model correctness, repeatability, prompt-injection resistance, or safe execution. Provider documentation retrieval provenance and pinned live Nova evaluation remain incomplete. |
| Proposal/schema checks | `generated_provider_validation.py` checks generated resource types and arguments against the initialized, locked AWS provider schema. PR #429 records that schema document's supported format version and canonical digest in the plan result and integrity-checked manifest. [`ticket309.md`](../tickets/ticket309.md) records a synthetic S3 schema check; [`test311.md`](../test/test311.md) records the later authenticated S3 saved-plan run with the locked provider schema. | This verifies Terraform schema shape and the identity of the schema input, not service semantics, customer security, cost, or lifecycle behavior. It does not map the capability/root registries to per-module supported schema evidence. |
| Customer apply-role scope | PR #443 [test evidence](../test/test443.md) records same-account ExternalId assumption using a temporary broker and the checked-in apply-role template. Exact-plan scopes were exercised for S3, SQS, and DynamoDB create/read, SQS update, and separate destroy; out-of-scope creates and unrelated EC2 access were denied. | Direct SDK calls did not use Nova’s credential broker or dispatcher. This covers only the tested services/actions in one account; cross-account trust, all effective policy layers, and Nova-originated execution remain unverified. |
| Generated-plan policy | `generated_plan_policy.py` binds trusted account/region and proposal inventory; reviews destructive and sensitive changes; checks policy-critical unknowns for a finite list of Terraform types; and contains S3, SQS encryption/queue-policy/retry/DLQ/Lambda-consumer, IAM, network ingress, EC2 metadata, relational-database, bounded EKS cluster/node-group rules (merged PR #499), and bounded VPC route/NAT rules (merged PR #500). Merged PR #445 remains source-only, not deployed. PRs #401/#402/#404 are merged and deployed to the control plane; [`test401.md`](../test/test401.md), [`test402.md`](../test/test402.md), and [`test404.md`](../test/test404.md) record their evidence. | Partial shared rules only. PR #445 requires one-to-one plan-bound source/DLQ pairs with 5–10 receives, exact DLQ source allow lists, and sufficient retention; its Lambda mapping rule supports direct same-plan references and inline role policies only. It does not prove delivery, idempotency, producer authorization, managed-policy contents, complete effective permissions, KMS encryption, or all SQS consumers. The EKS node rule applies only when the plan binds a node group to exactly one same-plan launch template whose metadata settings are visible to policy. It does not establish pod metadata isolation, Kubernetes/RBAC or cluster endpoint security. VPC rules cover only the bounded module shape and do not establish ACL association/precedence, endpoints, DNS, VPN, complete egress cost, or effective service reachability. Unknown-value checks cover only paths in `POLICY_CRITICAL_UNKNOWN_PATHS`. No customer Nova plan has exercised these checks. See the resource-family table below. |
| Cost | Backend `main` has regional catalog-backed, assumption-bound pricing for explicitly bounded EBS gp3, S3 Standard, SQS Standard/FIFO, selected single-AZ RDS MySQL, single-region Standard DynamoDB on-demand tables, ZIP Lambda, HTTP API, CloudWatch Standard logs and modeled internet egress. PR #424 adds one Aurora PostgreSQL Serverless v2 writer shape. Merged PR #502 adds source-only NAT hourly, NAT data processing, associated public IPv4, internet egress, and double-direction cross-AZ transfer pricing with exact-address usage assumptions and AWS Price List evidence; all seven checks passed on final PR head `86b4b89` in CI run #45578164764. | PR #502 is not deployment or customer billing evidence. Cost evidence is partial, not a complete quote or hard billing cap. Its VPC model supports one same-plan VPC Elastic IP per public NAT Gateway and assumes customer-declared monthly use; unrelated public addresses and unsupported network resources remain approval blockers. Every unpriced material resource, unknown assumption, unsupported configuration, missing regional price, or material supporting cost blocks approval. Fixture ranges and Cost Explorer history are not generated-plan price evidence. |
| Workload health | `certification_factory.py` declares textual readiness probes for eight scenario names. PR #437 [test evidence](https://github.com/Bepoadewale/davdeploy/pull/437) records direct ECS Express v1/v2 `/healthz` probes and rollback recovery; the owner accepts this as general-goal customer-side evidence. | The test does not prove Nova generated or dispatched the plan. Scenario declarations do not prove that a hosted worker ran probes. The current `CertificationEvidence` is five booleans; it does not record controlled failure, cost, source/artifact digest, or evidence link. |
| Update/recovery/cleanup | Service-level evidence includes healthy v1-to-v2 update, ECS circuit-breaker rollback of an unhealthy revision to v2, saved-plan teardown, and independent absence for ECS Express in [PR #437](https://github.com/Bepoadewale/davdeploy/pull/437). The owner accepts this isolated customer-side result for the general lifecycle gate for that tested shape. | Evidence does not generalize beyond the resource shapes and behaviors actually exercised. Nova dispatch is a separate product-integration property. |
| Hosted execution | The repository records a legacy App Runner pilot in [`test42.md`](../test/test42.md), and the direct customer-side ECS Express pilot in [PR #437](https://github.com/Bepoadewale/davdeploy/pull/437). PR #314 added durable saved-plan storage and administrator approval; its ticket states that path's hosted worker has no caller and apply/destroy are unavailable. | The two service pilots were not Nova-generated execution. Properly isolated direct customer-side tests count for the general plan/apply/lifecycle evidence gate for their tested shape; they do not prove Nova authorization, dispatch, or credential path. Hosted control-plane health is not workload health. |

## Acceptance record required for every entry

The two inventories below remain separate: 26 architecture capabilities and 30
Terraform roots. A semantic candidate root is not an executable binding. Every
row must eventually satisfy the evidence fields in the acceptance crosswalk
below before it can be described as hosted-supported. An explicit additional
test means the existing eight scenario names do not fully exercise that entry.

For each planned case, preserve the Nova proposal/model/prompt/context digests,
source commit and generated artifact digest; validated Terraform configuration,
provider lock and version, exact saved-plan digest, versioned policy result and
regional cost inputs/source timestamp; tenant/account/region ownership record;
build artifact and typed outputs; timestamped probe result/log reference;
update and injected-failure/recovery outcome; and destroy manifest plus an
independent absence result or named retained data. Keep sensitive plan/state
values encrypted and out of this index. A cost record must identify usage
assumptions and supporting costs; unknown or unsupported material usage stays
unpriced and blocks approval. The current source evaluator's existence does not
mean that each row has a price or that approval/apply is enabled.

## Architecture-entry acceptance crosswalk — all 26

These are required future acceptance cases, not claims that the factory or
hosted executor currently runs them. Each row needs its own cost/unknown-cost
record and the common evidence bundle above. All rows currently have **no
Nova-hosted plan, lifecycle, or cleanup proof**.

| Architecture entry | Scenario or additional acceptance test | Policy and observed behavior required | Cost and artifact evidence required |
|---|---|---|---|
| `aws-observability` | Additional observability/recovery: emit a controlled signal and prove alarm delivery and recovery. | Bind project log/metric destinations, enforce retention and prevent secret logging; observe alarm transition. | Log/metric/alarm/notification rates and retention; alarm configuration and delivery timestamps. |
| `aws-secrets-config` | Additional secret lifecycle: resolve a typed reference, rotate, verify new use and revoked old use. | Reject literals/unbound IDs; prove values are absent from Nova, plan, state and logs and access is scoped. | Secret/KMS/request/rotation rates; redacted ARN/version and access-denial evidence. |
| `aws-edge-https` | `multi-region` plus domain/TLS validation and failover. | Bind domain/certificate ownership and approved origins; probe hostname, certificate, primary and secondary endpoints. | DNS/certificate/health-check/request/transfer rates; domain, certificate and probe evidence. |
| `aws-static-web` | `web-application`: build, fetch over HTTPS, update content, verify new version and origin privacy. | Require private bucket/origin and safe cache policy; prove expected content and no stale response after update. | Storage/request/CDN/transfer rates; source/build digest, object version and HTTP probe. |
| `aws-serverless-api` | `web-application` plus `saas-backend`: authenticated API write/read and queue processing. | Check route auth, scoped function role, secret references, exposure and bounded egress; invoke allow/deny paths. | Invocation/duration/API/log/transfer assumptions; source/package digest, route IDs and traces. |
| `aws-managed-application` | `saas-backend`: build/serve app, write/read data, upload file, process job, update. | Bind immutable image, task role, ingress, secret references and dependencies; probe every dependency. | Compute/image/log/request/data/transfer rates; image digest, service outputs and probe logs. |
| `aws-container-service` | Additional ECS/Fargate API-worker case with update, injected task failure and recovery. | Enforce image digest, least-privilege task roles, private ingress, capacity bounds and health checks. | vCPU/memory, load balancer, image, log, storage and transfer assumptions; task and target-health records. |
| `aws-virtual-machine-service` | Additional VM case: launch, serve request, patch/update, fail/recover and destroy. | Require IMDSv2, approved AMI, encrypted disks, scoped profile and restricted ingress; probe guest health. | Instance/EBS/snapshot/network rates; AMI/template/instance IDs and patch/probe evidence. |
| `aws-kubernetes-platform` | `kubernetes`: deploy, invoke service, update, fail pod, recover and clean up. | Check endpoint/RBAC, node metadata, image provenance, network policy and workload identity; probe readiness. | Control-plane/node/LB/storage/log/transfer costs; cluster/image/deployment manifest and observations. |
| `aws-identity` | `web-application` plus identity: sign in, authorize, revoke and prove subsequent denial. | Check issuer/client/redirect ownership, MFA/session requirements and tenant authorization. | Active-user/auth/SMS/email/log rates; redacted allow/deny flow and auth-policy digest. |
| `aws-relational-data` | `saas-backend`: SQL insert/read/update plus restore and checksum comparison. | Require private/encrypted DB, bounded retention, deletion protection and safe final snapshot. | Instance/storage/I/O/backup/transfer/secret rates; migration/query/restore IDs and checksum. |
| `aws-nosql-data` | `saas-backend`: put/get/update plus point-in-time restore and item comparison. | Require encryption, scoped access, recovery and deletion settings; inspect exact restored item. | Capacity/request/storage/backup/replication rates; table/key schema, request and restore records. |
| `aws-file-storage` | `web-application` and `ai-rag`: authorized upload/download/update and unauthorized denial. | Require private storage, encryption, scoped access and retention; compare checksum and owner/non-owner access. | Storage-class/request/retrieval/egress rates; object version/checksum and access result. |
| `aws-jobs-events` | `saas-backend` and `async-data`: enqueue, process, retry, DLQ, redrive and idempotency. | Bind event source, consumer, encryption, retry/DLQ and duplicate behavior; observe every message transition. | Queue/event/workflow/compute/log/transfer rates; event IDs, attempts and DLQ evidence. |
| `aws-realtime` | Additional WebSocket/AppSync case: connect, publish, receive, reconnect and revoke. | Authorize connection/subscription, isolate tenant channels and enforce message limits; assert cross-tenant denial. | Connection-minute/message/resolver/log/transfer rates; redacted connection/message trace. |
| `aws-search` | `ai-rag` plus search: index, query, update/delete and prove tenant isolation. | Require private access, encryption and document-level authorization; test allowed and denied query. | Node/OCU/storage/ingest/query/backup rates; index digest and query trace. |
| `aws-payments-webhooks` | Additional signed synthetic webhook, replay rejection and idempotent processing; never simulate settlement. | Check signature age, replay, secret reference, data minimization and least privilege; observe accept/reject outcomes. | API/compute/queue/secret/log/network assumptions; redacted request IDs and dedupe record. |
| `aws-ai-retrieval` | `ai-rag`: ingest synthetic document, return grounded application result, deny cross-tenant access, update/delete. | Bind model/guardrail/data permissions, private ingestion and tenant corpus; test grounded and denied response. | Tokens/embedding/index/storage/request/log/transfer rates; model/prompt/corpus and trace digests. |
| `aws-managed-ml` | `machine-learning`: invoke meaningful synthetic input, update model, recover and destroy. | Verify artifact provenance, endpoint auth/network, quota, encryption and redaction; assert output contract. | Instance-hours/storage/requests/data/log/transfer rates; model and endpoint digests plus invocation. |
| `aws-cpu-inference` | Additional CPU inference: invoke representative input, validate output/latency, update and recover. | Enforce model/image digest, compute bounds, endpoint access and scaling cap; redact sensitive input. | CPU/memory/scaling/storage/request/log/transfer assumptions; invocation and latency record. |
| `aws-gpu-inference` | Additional GPU inference: real synthetic invocation, output/latency, update, recovery and destroy. | Verify accelerator, artifact, quota and maximum capacity/spend before plan review. | GPU-hours/storage/transfer/idle cost; quota result, model/image digest and invocation evidence. |
| `aws-data-analytics` | `async-data` plus analytics: ingest partition, run query/job, compare output, retry failure. | Scope data/catalog/job role, encrypt results and protect query output; verify row count/checksum. | Storage/requests/scanned bytes/job/log/transfer rates; input/output digests and query/job IDs. |
| `aws-stream-processing` | `async-data` plus stream: publish, consume, checkpoint, fail/replay and check ordering. | Bound retention, encryption, producer/consumer access, throughput and checkpoint policy. | Shard/throughput/retention/consumer/storage/log/transfer rates; event IDs, offsets and replay results. |
| `aws-media` | Additional media pipeline: upload, transcode, validate, deliver HTTPS, update and delete. | Bind source/output, transcode role/profile, private origin, access and retention. | Storage/transcode/CDN/egress/log rates; checksums, job ID and playback probe. |
| `aws-private-connectivity` | `hybrid-network`: disposable peer, encrypted routed traffic, break/restore route. | Check peer, tunnel crypto, routes, ACL/SG, egress and ownership; probe only approved private addresses. | VPN/TGW/endpoint hours and processed/cross-AZ/egress traffic; peer/route manifest and probe timestamps. |
| `aws-backup-recovery` | `multi-region` plus backup case: create recovery point, restore, compare app data, measure RPO/RTO. | Enforce vault scope, retention, encryption, restore role and explicit retained-data behavior. | Protected GB-month, requests, restore and regional transfer; recovery-point IDs, checksum and RPO/RTO record. |

## Terraform-root acceptance crosswalk — all 30

Each root is independently gated even where a candidate architecture mapping
exists. Every case must use Nova proposal, schema/policy checks, isolated saved
planning, and eventually the hosted executor. No root currently has Nova-hosted
plan, lifecycle, or independent cleanup evidence. The common artifact bundle
above applies to every row.

| Root | Scenario or targeted acceptance test | Root-specific policy/health and cost evidence required |
|---|---|---|
| `aws-dns-zone` | `multi-region` plus domain ownership case | Reject unowned/unsafe targets; resolve expected record and failover; price zone, query, health check and transfer. |
| `aws-acm-certificate` | `web-application` TLS case | Bind domain and service region; verify issuance and HTTPS hostname; record certificate, DNS validation and linked edge costs. |
| `aws-kms-key` | Additional key-consumer rotation/recovery | Check policy, rotation and deletion window; encrypt/decrypt then safely rotate/disable; price key-month and requests. |
| `aws-parameter-config` | `aws-secrets-config` rotation | Bound name/tier/type/access; runtime update/retrieval and revoked denial; price tier, API, KMS and logs. |
| `aws-feature-flags` | Additional AppConfig rollout | Bind app/profile/deployment strategy; observe staged flag and rollback; price config, deployment, fetch and monitoring. |
| `aws-s3-private-storage` | `web-application` / `ai-rag` object case | Check public access, encryption, ownership, policy and retention; checksum upload/read/update/delete; price storage/request/retrieval/egress. |
| `aws-cloudfront-delivery` | `web-application` HTTPS/private-origin update | Check origin/TLS/cache/access; fetch, update/invalidate and compare versions; price requests, transfer, functions and origin. |
| `aws-api-gateway-http` | `web-application` API case | Review route auth, stage, throttling and integration; invoke allowed/denied requests; price API, data, logs and authorizer. |
| `aws-lambda-service` | `web-application` / `saas-backend` function case | Bound runtime/memory/time/concurrency, role, references and artifact; invoke and inspect redacted output; price requests/duration/logs/VPC/egress. |
| `aws-ecr-image` | Additional image provenance case | Require immutable digest, approved source/build, scan and scoped pull; run exact image; price storage, transfer, scan and requests. |
| `aws-aurora-postgres` | `saas-backend` relational case | Require private encryption, backups/deletion and secret contract; query/restore/checksum; price instances, storage, I/O, backup, network and secret. |
| `aws-dynamodb-table` | `saas-backend` NoSQL case | Require encryption, PITR, deletion protection and ownership; put/get/restore; price capacity or request mode, storage, backup and streams. Merged and deployed PR #414 prices single-region Standard on-demand request units, table storage and PITR. Provisioned capacity, indexes, replicas, streams and other omitted charges remain blockers. |
| `aws-elasticache-redis` | Additional cache case | Require private encrypted/authenticated access and failover; set/get/reconnect; price node-hours, backup, storage and transfer. |
| `aws-opensearch` | `ai-rag` search case | Check private access, encryption, scoped index permissions and capacity; query/update/delete plus tenant denial; price OCU/node, storage, ingest/query. |
| `aws-efs-shared-storage` | Additional shared-file case | Check encryption, mount security, access point identity and retention; authorized clients read/write, other denied; price storage, throughput, backup, transfer. |
| `aws-sqs-queue` | `saas-backend` / `async-data` worker | PR #441 requires known SQS-managed encryption. Merged PRs #445/#446 add plan safety and fix queue ordering. PR #447 records a direct Lambda failure/retry/DLQ cycle. PR #448 records duplicate-safe successful processing, Lambda update, managed DLQ redrive, recovery, and independently verified cleanup. |
| `aws-eventbridge-bus` | `async-data` routing | Restrict bus/rules/target/account; prove only intended target receives event; price events, archive/replay, invocation and transfer. |
| `aws-step-functions` | `async-data` workflow | Restrict state role, tasks, retries and logged inputs; execute success and injected retry/failure; price transitions, duration, logs, integrations. |
| `aws-sns-notifications` | Additional notification delivery | Restrict topic/subscription and require confirmation; deliver to real approved endpoint; price publish, protocol, delivery and transfer. |
| `aws-ses-email` | Additional email case with verified domain and real recipient | Enforce identity, recipient, suppression and secret controls; record actual delivery/bounce; price sends/data/compute. |
| `aws-bedrock-runtime` | `ai-rag` model invocation | Bind model/region/guardrail and data boundary; invoke synthetic prompt and observe response; price input/output tokens, guardrail and retrieval. |
| `aws-bedrock-knowledge-base` | `ai-rag` ingest/retrieval | Restrict source/role/vector store/tenant corpus; ingest, retrieve grounded result and delete; price embedding, tokens, storage, index, requests. |
| `aws-sagemaker-endpoint` | `machine-learning` invocation | Verify artifact, endpoint access, accelerator quota/cap and data encryption; meaningful inference; price instance/GPU hours, storage and transfer. |
| `aws-kinesis-stream` | `async-data` stream | Bound encryption, retention, capacity and consumer; publish/consume/checkpoint/replay; price throughput, shard, retention, fan-out and transfer. |
| `aws-batch-compute` | `async-data` job | Restrict queue, image, role, retries, capacity and egress; run/fail/retry/compare result; price vCPU/memory/GPU, storage, logs and transfer. |
| `aws-eks-cluster` | `kubernetes` service | Check endpoint, IAM/RBAC, IMDSv2, image, network and quota; deploy/invoke/fail/recover; price cluster/nodes/LB/storage/logs/transfer. |
| `aws-ec2-autoscaling` | Additional VM/scaling case | Require IMDSv2, AMI, encrypted disks, scoped role and max capacity; serve and observe bounded scale/recovery; price instances/EBS/LB/network. |
| `aws-vpc-private-network` | `hybrid-network` and private app path | Merged PR #500 checks a bounded private IPv4 topology, paired public/private subnets, explicit route associations, IGW/NAT default routes, and same-plan NAT/EIP bindings. Still check ACL associations/precedence, SG reachability, endpoints, ownership, allow/deny probes, and price NAT/endpoints/addresses/cross-AZ/traffic. |
| `aws-site-to-site-vpn` | `hybrid-network` VPN | Bind peer, tunnel and routes; observe encrypted probe, outage and restoration; price tunnel-hours, processing, addresses and transfer. |
| `aws-multi-region-dns` | `multi-region` failover | Bind approved regions/endpoints; fail primary and probe secondary service, then restore; price zone, checks, queries, regional copies and transfer. |

For roots with no executable pricing model, the required cost outcome is an
explicit **unpriced / approval blocked** result until regional products and
usage assumptions are implemented and independently checked. Row-level cost
design does not mean that a rate is currently available.

### Resource families checked by the current generated-plan policy

| Check | What code checks | What it does not establish |
|---|---|---|
| Scope and plan | Trusted account and region guard; declared-resource inventory; malformed/non-applyable plans; destructive changes and sensitive changes require review. | Resource ownership for every AWS type, quota availability, or workload suitability. |
| S3 | Requires all four public-access-block flags for planned buckets; denies public ACLs and public bucket policies; merged PRs #434–#436 require same-plan TLS-deny policies, explicit default encryption, and `BucketOwnerEnforced` ownership controls. | This does not validate every bucket use pattern, KMS key authorization, object-level upload enforcement, existing object encryption, or retention. Unknown-value checks cover listed S3 policy-critical fields only. |
| SQS | PR #441 requires known SQS-managed encryption. Merged PR #445 adds 0–43,200 second visibility bounds, 60 second–14 day retention, one-to-one redrive pairs with `maxReceiveCount` 5–10, exact `byQueue` allow policy, and six-times-Lambda-timeout-plus-batch-window checks. A same-plan Lambda consumer needs inline `ReceiveMessage`, `DeleteMessage`, and `GetQueueAttributes` on the exact source ARN. Merged PR #446 fixes source-after-DLQ ordering. PR #447 records Lambda retries/DLQ delivery; merged PR #448 records direct duplicate suppression, code update, managed redrive, recovered processing, and verified teardown. | Policy remains source-only, not hosted. Direct SQS/Lambda tests do not prove Nova dispatch. Managed-policy contents, module-output bindings, KMS encryption, non-Lambda consumers, producer authorization, full effective permissions, and complete retry/DLQ cost usage remain unproven. |
| AWS Batch | Merged PR #498 adds one managed Fargate compute environment capped at 6 vCPUs, one queue bound to that same-plan environment, and one digest-pinned container job capped at 2 vCPUs, 3 attempts, and a 3,600-second timeout. It rejects unsupported CPU/memory pairs, privileged containers, cross-account/wildcard role ARNs, and secret-like or reserved plaintext environment variables; public-IP use triggers review. | Source-only and not deployed. It does not prove effective role permissions, submission-time overrides, full cost, non-Fargate compute, retry filters, or Nova dispatch. |
| IAM | Denies broad wildcard privileges, wildcard trust, unknown policy attachments, and application `AdministratorAccess`. | Complete least-privilege analysis across service-specific policies, resource-based policies, permission boundaries, and all generated trust relationships. |
| Network | Reviews public security-group and network-ACL web/general ingress; denies all-protocol and listed sensitive-port exposure; unknown ACL ingress sources fail closed. Merged PRs #477/#481 require EFS NFS/2049 ingress to use exact TCP from a security-group source, with #481 binding the rule target to a group attached to a same-plan mount target. Merged PR #479 requires Redis/6379 exact TCP security-group ingress bound to the replication group. Merged PR #500 bounds the module VPC to paired public/private subnets across two or three AZs, exact IGW/NAT default-route bindings, and one same-plan VPC EIP/NAT; NAT and transfer costs require human review. Globally routable source ranges are recognized. | ACL association and rule-precedence reachability, endpoints, DNS, TLS, VPN, multi-region, effective service-to-service reachability, and complete egress pricing remain unsupported. |
| Databases and unknowns | Denies public RDS/Redshift, requires encryption for the listed relational types, and checks unknown critical fields for the bounded resource/path list. | Backup restore evidence, workload data integrity, every database product, every retention setting, or unknown values on unlisted types. |

## Architecture catalogue: all 26 entries

`Candidate roots` are semantic references only; there is no authoritative
catalogue-to-root dispatch binding. The policy column refers to the shared
checks above and names the closest implemented resource-family checks. The
source evaluator has local regional price evidence for a bounded subset of
resources; this matrix has **no hosted customer plan-price evidence**. Direct
isolated AWS lifecycle evidence is recorded per tested shape below; Nova
dispatch remains a separate integration property and is not implied by that
evidence.

| Architecture module | Existing scenario | Candidate implementation roots | Shared policy evidence / gap | Service-level evidence (not hosted Nova proof) | Remaining health/lifecycle evidence |
|---|---|---|---|---|---|
| `aws-observability` | — | No matching observability root | No CloudWatch/OTel-specific plan rule | No mapped workload probe | No module-specific alert delivery, health-history, update, recovery, or cleanup proof |
| `aws-secrets-config` | — | `aws-kms-key`, `aws-parameter-config` | IAM checks apply to IAM resources; PR #465 requires known `SecureString` type, Standard tier, and known optional KMS key identity. Terraform state can still contain the parameter value; no secret retrieval/exposure policy is mapped to this module. | No mapped secret/config workload probe | No secret rotation, runtime retrieval, redaction-at-use, update, or recovery proof |
| `aws-edge-https` | `multi-region` | `aws-dns-zone`, `aws-acm-certificate`, `aws-cloudfront-delivery`, `aws-multi-region-dns` | Merged PRs #432/#433 add source-only viewer HTTPS and custom-origin TLS rules. No certificate or DNS ownership/failover policy | [`test253.md`](../test/test253.md) HTTPS content; [`test254.md`](../test/test254.md) ACM/SES DNS validation; [`test260.md`](../test/test260.md) public failover | No Nova-hosted edge lifecycle or per-plan TLS/domain cost evidence |
| `aws-static-web` | `web-application` | `aws-s3-private-storage`, `aws-cloudfront-delivery` | S3 public-access and merged PRs #434–#436 transport, encryption, and ownership checks apply. PRs #432/#433 cover viewer and custom-origin TLS only. No private-origin access, cache, or deployment policy suite | [`test253.md`](../test/test253.md) served HTTPS content | No Nova-hosted source-to-site build, update/rollback, or cleanup proof |
| `aws-serverless-api` | `web-application` | `aws-api-gateway-http`, `aws-lambda-service` | Shared IAM/network rules only; no API auth, throttling, or Lambda runtime-specific plan policy | [`test268.md`](../test/test268.md) real isolated HTTP 200 and teardown through a separate serverless renderer root | No Nova-hosted plan/apply or composed API/data/queue health proof |
| `aws-managed-application` | `saas-backend` | No root in the 30-entry registry; separate App Runner renderer | Shared IAM/network checks only; no App Runner-specific policy map | [`test42.md`](../test/test42.md) records a separate App Runner customer workload pilot | No Nova-generated App Runner plan evidence; the pilot does not prove composed Nova execution |
| `aws-container-service` | `kubernetes` | `aws-ecr-image` (partial; ECS/Fargate and ALB roots are absent from the 30-root registry) | Shared IAM/network checks only; no container image, task role, or service deployment policy | [`test255.md`](../test/test255.md) is EKS. [PR #437](https://github.com/Bepoadewale/davdeploy/pull/437) records isolated ECS Express create, health, update, failed-revision rollback, and teardown; accepted for the general customer-side gate but not Nova execution. | No ECS/Fargate API-plus-worker behavior, Nova-generated plan, or catalog-root binding proof |
| `aws-virtual-machine-service` | — | `aws-ec2-autoscaling` | Merged source PR #402 checks IMDSv2 for planned EC2 shapes and requires regional metadata defaults to require tokens; PR #483 bounds one same-plan `t3.micro` Auto Scaling profile. | [`test244.md`](../test/test244.md) records the zero-capacity profile; merged PR #485 [`test485.md`](../test/test485.md) records direct same-account capacity 1→2→1 and EC2 system/instance checks; PR #486 [`test486.md`](../test/test486.md) records encrypted root-volume cycles and teardown. | No guest application health, image provenance, scoped instance-role evidence, update/recovery, complete cost, or Nova dispatch; metadata defaults can be overridden and are not account-wide enforcement |
| `aws-kubernetes-platform` | `kubernetes` | `aws-eks-cluster`, `aws-ecr-image`, `aws-vpc-private-network` | Merged PR #499 adds source-only private endpoint, supported-version, control-plane log, same-plan cluster/role/template, and bounded managed-node checks. It does not cover Kubernetes RBAC, admission, image provenance, or workload identity. | [`test255.md`](../test/test255.md) deployed a workload and probed its service | No Nova-hosted cluster lifecycle, upgrade/failure recovery, or independent cleanup proof |
| `aws-identity` | `web-application` | No Cognito or application-identity root | No customer-identity tenant/MFA/session policy in generated-plan policy | No customer workload identity probe mapped to this module | No Nova-hosted sign-up, authorization, revocation, or identity-recovery proof |
| `aws-relational-data` | `saas-backend` | `aws-aurora-postgres` | RDS public-access/encryption checks; unknown deletion-protection/final-snapshot fields are bounded | [`test244.md`](../test/test244.md) records Aurora available before teardown; no application query is recorded | No application read/write, restore/integrity, migration, update, or hosted cleanup proof |
| `aws-nosql-data` | `saas-backend` | `aws-dynamodb-table` | PR #473 requires known table/partition-key identity, on-demand billing, server-side encryption, deletion protection, and enabled PITR; recovery-contract policy is in PR #363 | [`test244.md`](../test/test244.md) records encryption and PITR configuration; merged PR #487 [`test487.md`](../test/test487.md) records direct same-account source writes, PITR restore, restored-table reads, and teardown | No hosted application read/write, Nova dispatch, tenant authorization, or full cost proof |
| `aws-file-storage` | `ai-rag` | `aws-s3-private-storage`, `aws-efs-shared-storage` | Merged PRs #434–#436 add source-only S3 transport, encryption, and ownership enforcement; no EFS mount/access or file-retention policy map | [`test262.md`](../test/test262.md) used private S3 input for KB ingestion; [`test244.md`](../test/test244.md) recorded EFS available; draft PR #491 [`test491.md`](../test/test491.md) verifies the exact artifact-module bucket and synthetic object-version lifecycle | No customer upload/download authorization, tenant isolation, file-retention policy, or hosted cleanup proof |
| `aws-jobs-events` | `saas-backend`, `async-data` | `aws-sqs-queue`, `aws-eventbridge-bus`, `aws-step-functions`, `aws-sns-notifications`, `aws-ses-email` | Merged PR #445 checks SQS retry/DLQ and direct Lambda consumer binding/permissions. Merged PR #450 adds source-only exact SNS-to-SQS topic, queue, queue-policy URL, and source-conditions checks. Merged PRs #451/#452 bind EventBridge rule/target/queue policy, bounded retries, and exact EventBridge DLQ policy, with direct failure/recovery evidence. Merged PR #456 adds exact role trust and Lambda invoke scope for one Standard Step Functions task shape; it is source-only and not deployed. SES delivery, other producer authorization, unsupported workflow integrations, and broader application composition remain open. | [`test257.md`](../test/test257.md) proves EventBridge-to-SQS; [`test256.md`](../test/test256.md) proves a Step Functions execution; merged PR #454's [`test454.md`](../test/test454.md) records direct Step Functions Catch recovery and cleanup; [`test449.md`](../test/test449.md) proves one direct SNS-to-SQS delivery and cleanup; [`test452.md`](../test/test452.md) records direct EventBridge failure, DLQ, repair, recovery, and cleanup | No Nova-dispatched event, consumer-to-application completion, SES delivery, or hosted recovery proof |
| `aws-realtime` | — | No WebSocket or AppSync root; DynamoDB root is only a partial resource overlap | No subscription authorization/message fan-out policy | No mapped real-time probe | No connect/publish/receive, reconnect, update, or cleanup evidence |
| `aws-search` | `ai-rag` | `aws-opensearch` | Shared IAM/network checks only; no index/document authorization or exposure policy suite | [`test262.md`](../test/test262.md) proves KB retrieval using OpenSearch Serverless; [`test244.md`](../test/test244.md) records an OpenSearch domain ready | No general application-search query, reindex/update, recovery, or hosted proof |
| `aws-payments-webhooks` | — | `aws-api-gateway-http`, `aws-lambda-service`, `aws-sqs-queue` are only generic building blocks | No provider-signature, replay, idempotency, payment-data, or webhook abuse policy | No external payment/webhook behavior is evidenced | No provider-backed event delivery, reconciliation, retry, update, or cleanup proof |
| `aws-ai-retrieval` | `ai-rag` | `aws-bedrock-runtime`, `aws-bedrock-knowledge-base`, `aws-s3-private-storage`, `aws-opensearch`, `aws-lambda-service` | Shared S3/IAM/network checks; merged PRs #434–#436 add source-only transport, encryption, and ownership enforcement; no end-to-end prompt/data access policy suite | [`test262.md`](../test/test262.md) ingested a synthetic document and returned grounded text; [`test244.md`](../test/test244.md) records guardrail readiness only | No hosted customer application, authorization, model cost, update, recovery, or cleanup proof |
| `aws-managed-ml` | `machine-learning` | `aws-sagemaker-endpoint` | Shared IAM/S3/network checks only; no model artifact provenance, endpoint access, or inference cost policy | [`test261.md`](../test/test261.md) records real SageMaker inference and teardown | No Nova-hosted training/model deployment or update/recovery proof |
| `aws-cpu-inference` | — | `aws-sagemaker-endpoint` is a possible resource overlap; no CPU-specific implementation | No inference image, endpoint access, scaling, or model-data policy | [`test261.md`](../test/test261.md) is a SageMaker endpoint test, not evidence for this planner capability | No CPU-inference selection, load, update, recovery, or hosted proof |
| `aws-gpu-inference` | — | `aws-sagemaker-endpoint`, `aws-eks-cluster`, `aws-ec2-autoscaling` are partial overlaps | No GPU quota, accelerator, artifact, endpoint, or spend guard | No GPU inference evidence found | No GPU workload, cost, health, update, recovery, or cleanup proof |
| `aws-data-analytics` | `async-data` | `aws-s3-private-storage`, `aws-batch-compute`; Glue/Athena roots are absent | Shared S3/IAM checks only; no data catalog, query exposure, or retention policy | [`test252.md`](../test/test252.md) proves a Batch job, not a Glue/Athena analytics pipeline | No ingestion-to-query result, update, recovery, or hosted proof |
| `aws-stream-processing` | `async-data` | `aws-kinesis-stream`; MSK root is absent | PR #475 adds source-only checks for the module's single provisioned shard, 24-hour retention, KMS encryption, and AWS-managed Kinesis key. No consumer/producer authorization or checkpoint policy is added. | [`test258.md`](../test/test258.md) proves one Kinesis record was accepted | No consumer processing, replay, failure/recovery, or hosted proof |
| `aws-media` | — | `aws-s3-private-storage`, `aws-cloudfront-delivery`; MediaConvert root is absent | Shared S3/network rules only; no media ingest/transcode/access/retention policy | No media workload evidence found | No upload/transcode/playback, update, failure recovery, pricing, or cleanup proof |
| `aws-private-connectivity` | `hybrid-network` | `aws-vpc-private-network`, `aws-site-to-site-vpn` | Shared security-group ingress rule only; no route, peer, egress, or tunnel-policy suite | [`test263.md`](../test/test263.md) proves encrypted routed probe traffic | No Nova-hosted customer network, route change/recovery, or independent cleanup proof |
| `aws-backup-recovery` | `multi-region` | No AWS Backup vault/plan/restore implementation root; S3 and DNS roots are not backup proof | No backup-retention/restore-integrity policy or RPO/RTO enforcement | [`test260.md`](../test/test260.md) proves DNS failover, not backup or restore | No backup creation, restore/data-integrity drill, recovery timing, or cleanup proof |

## Terraform implementation registry: all 30 roots

The `catalogue candidate` column is descriptive only; the implementation
registry does not declare these relationships. The `policy` column lists only
current generated-plan checks that apply by resource type. Source-level
regional price evidence exists for a bounded subset; no root has **hosted
customer plan-price evidence**. Linked direct tests count toward the general
customer-side lifecycle gate only for their exact tested shapes and recorded
behaviors; they do not establish Nova dispatch or hosted execution.

| Implementation ID | Terraform root | Catalogue candidate / existing scenario | Current applicable plan-policy checks | Existing service-level evidence |
|---|---|---|---|---|
| `aws-dns-zone` | `modules/dns-zone` | `aws-edge-https` / `multi-region` | PR #470 requires known zone name, no VPC associations, and `force_destroy=false`. It does not verify ownership, records, delegation, failover, or DNS cost. | [`test260.md`](../test/test260.md), [`test244.md`](../test/test244.md); neither proves this module's complete customer lifecycle |
| `aws-acm-certificate` | `modules/acm-certificate` | `aws-edge-https` / `multi-region` | PR #468 requires known domain, DNS validation, RSA_2048, and export disabled. It does not verify domain ownership, certificate issuance/renewal, or DNS record publication. | [`test254.md`](../test/test254.md) records ACM/SES DNS validation; it does not certify this module's complete lifecycle |
| `aws-kms-key` | `modules/kms-key` | `aws-secrets-config` (candidate; KMS not listed in module services) / no scenario | PR #463 requires known symmetric `ENCRYPT_DECRYPT` keys, automatic rotation, regional scope, and a 30-day deletion window. It does not validate the key policy or consumer binding. | `test244` used AWS-managed KMS encryption for Kinesis, not this customer-managed-key root; no root-specific evidence found. No customer-managed-key apply because AWS charges for keys and deletion has a 7–30 day waiting period. |
| `aws-parameter-config` | `modules/parameter-config` | `aws-secrets-config` / no scenario | PR #465 requires `SecureString`, Standard tier, and a known optional KMS key reference. It does not protect the value from Terraform state, validate consumer access, or handle rotation. | Merged PR #493's [`test493.md`](../test/test493.md) records exact-module synthetic version 1→2 retrieval, in-memory redacted verification, monitored destroy, independent absence, and retained mode-600 state/plans; no Nova dispatch. |
| `aws-feature-flags` | `modules/feature-flags` | No matching catalogue module / no scenario | PR #471 binds an AppConfig environment to one same-plan application. Open draft PR #495 adds a feature-flag profile, rollout strategy, same-plan bindings, and source policy for its bounded shape; final-head checks passed. | [`test495.md`](../test/test495.md) records a direct tagged AppConfig rollout to `COMPLETE`, followed by rollback to `REVERTED`. Its exact test resources remain pending approved teardown; no Nova dispatch is claimed. |
| `aws-s3-private-storage` | `modules/artifacts` | `aws-file-storage`, `aws-static-web`, `aws-ai-retrieval` / `ai-rag`, `web-application` | S3 block-public-access/public ACL checks; merged PRs #434–#436 require same-plan TLS-deny, default encryption, and `BucketOwnerEnforced`. Not a complete private-upload policy | [`test262.md`](../test/test262.md) private source bucket; draft PR #491 [`test491.md`](../test/test491.md) records exact `modules/artifacts` settings, synthetic v1/v2 reads, and monitored teardown; no Nova dispatch |
| `aws-cloudfront-delivery` | `modules/cloudfront-delivery` | `aws-edge-https`, `aws-static-web` / `multi-region`, `web-application` | Merged PRs #432/#433 deny unknown or cleartext viewer policies and check custom-origin HTTPS/TLS 1.2; standard S3 origins rely on viewer HTTPS. Source-only. No response-header, private-origin-access, or cache-safety policy | [`test253.md`](../test/test253.md) |
| `aws-api-gateway-http` | `modules/api-gateway-http` | `aws-serverless-api`; generic API building block for payments / `web-application` | Shared network/IAM checks only; no route auth, authorizer, throttling, or WAF rule | [`test268.md`](../test/test268.md) |
| `aws-lambda-service` | `modules/lambda-service` | `aws-serverless-api`, `aws-ai-retrieval`; generic building block for other APIs / `web-application`, `ai-rag` | Merged PR #503 adds source-only bounds for the priced ZIP shape: supported runtime, known code hash, same-account role, exact same-plan Lambda trust (or human review for an external role), architecture, memory, timeout, environment size, scoped same-account/region Secrets Manager ARN environment values, and unsupported VPC/layer/concurrency/event settings. Final PR head `08ace0b` passed all seven checks in run #45582032631; automated review found no issues. It is not deployed. | [`test268.md`](../test/test268.md) exercises Lambda through a separate serverless renderer root; merged PR #489 [`test489.md`](../test/test489.md) records exact-module v1 invoke, in-place v2 code update, teardown, and independent absence verification. No Nova dispatch evidence. |
| `aws-ecr-image` | `modules/ecr` | `aws-managed-application`, `aws-container-service`, `aws-kubernetes-platform` / `saas-backend`, `kubernetes` | PR #461 adds source checks for immutable image tags, declared scan-on-push, AES256 repository encryption, and `force_delete=false`. AWS now deprecates repository-level scan configuration in favor of registry-level scanning, so this field is configuration intent, not proof scanning is active. No image-provenance or repository-policy scope is enforced. | [`test461.md`](../test/test461.md) records direct same-account creation, setting verification, and teardown of this module's empty repository; [`test239.md`](../test/test239.md) records ECR settings in a combined stack. Neither test pushes/runs an image. | No verified image digest/source provenance, registry-level scan result, scoped pull/run, full application lifecycle, or complete ECR cost |
| `aws-aurora-postgres` | `modules/aurora-postgres` | `aws-relational-data` / `saas-backend` | RDS public access/encryption and bounded deletion/final-snapshot unknown checks | [`test244.md`](../test/test244.md): Aurora available; no app query or restore |
| `aws-dynamodb-table` | `modules/dynamodb-table` | `aws-nosql-data` / `saas-backend` | PR #473 requires known table/partition-key identity, `PAY_PER_REQUEST`, server-side encryption, deletion protection, and enabled PITR with a bounded recovery period. This source-only policy does not cover indexes, streams, replicas, consumer permissions, or all usage costs. | [`test244.md`](../test/test244.md): SSE and PITR configuration; merged PR #487 [`test487.md`](../test/test487.md): direct same-account source writes, restore to a captured PITR time, restored-table reads, and isolated teardown. No Nova dispatch. |
| `aws-elasticache-redis` | `modules/elasticache-redis` | No cache module in catalogue / no scenario | Merged PR #479 requires source-only checks for Redis OSS 7.1, one `cache.t4g.micro` node, AUTH token marked sensitive with `SET`, at-rest/TLS encryption, same-plan subnet/security-group references, and exact TCP/6379 ingress bound to the Redis security group. The token may enter Terraform plan/state. This does not prove client authorization, failover, lifecycle, or complete costs. | [`test244.md`](../test/test244.md): replication group available; no client operation |
| `aws-opensearch` | `modules/opensearch` | `aws-search`, `aws-ai-retrieval` / `ai-rag` | PR #466 bounds plans to the module's one-node `t3.small.search`, 10 GiB gp3, VPC-mode, encrypted-at-rest/node-to-node, HTTPS/TLS 1.2 shape. It does not verify the subnet/SG attachment chain, access policy, index permissions, or current price. | [`test244.md`](../test/test244.md) domain ready; [`test262.md`](../test/test262.md) uses OpenSearch Serverless for KB retrieval; neither verifies this module's complete lifecycle |
| `aws-efs-shared-storage` | `modules/efs-shared-storage` | No explicit EFS catalogue module; possible `aws-file-storage` overlap / no exact scenario mapping | Merged PR #477 adds source-only encryption, General Purpose performance, Bursting throughput, and exact TCP/2049 source checks. Merged PR #481 binds each mount target to a same-plan security group and NFS ingress rule. This does not prove mounted file read/write, access-point identity, file permissions, lifecycle, or full costs. | [`test244.md`](../test/test244.md): EFS available; no file read/write |
| `aws-sqs-queue` | `modules/sqs-queue` | `aws-jobs-events`, `aws-payments-webhooks` / `saas-backend`, `async-data` | PR #441 requires known `sqs_managed_sse_enabled=true`; queue policies reject public/unverified principals and unbounded resource scope. Merged PRs #445/#446 add plan safety and correct dependency ordering. PR #447 adds a Lambda retry/DLQ cycle. PR #448 adds idempotent processing, code update, managed redrive, recovery, and cleanup. Merged PR #450 binds exact SNS subscription/queue-policy scope; merged PRs #451/#452 bind EventBridge target grants, bounded retries, and exact standard DLQ policy. KMS-backed encryption, managed-policy contents, other producers and non-Lambda consumers remain open. | [`test257.md`](../test/test257.md): EventBridge delivery; [`test446.md`](../test/test446.md): delivery, retries, DLQ transition, teardown; [`test447.md`](../test/test447.md): Lambda retries and paired DLQ; [`test448.md`](../test/test448.md): duplicate suppression, update, redrive, recovery, teardown; [`test449.md`](../test/test449.md): SNS delivery and teardown; [`test452.md`](../test/test452.md): EventBridge failure, DLQ, repair, recovery, teardown. None proves Nova dispatch. |
| `aws-eventbridge-bus` | `modules/eventbridge-bus` | `aws-jobs-events` / `saas-backend`, `async-data` | Merged PR #451 binds exact planned bus/rule, SQS target, attached queue policy URL, EventBridge principal, `sqs:SendMessage`, queue ARN, and rule source ARN. Merged PR #452 adds known bounded retry policy and a distinct planned standard SQS DLQ with exact rule-scoped grant. EventBridge target roles and unknown/cross-account target shapes are unsupported. | [`test257.md`](../test/test257.md): same-account EventBridge-to-SQS delivery; [`test452.md`](../test/test452.md): failure-to-DLQ, repair, recovery, and teardown | No Nova-dispatched event, target-role policy, broader target families, or hosted recovery proof |
| `aws-step-functions` | `modules/step-functions` | `aws-jobs-events` / `saas-backend`, `async-data` | Merged PR #456 requires Standard workflows, exact `states.amazonaws.com` trust scoped to the state machine ARN/account, and inline `lambda:InvokeFunction` grants limited to same-plan Lambda task ARNs. Other integrations, logging, Map/Parallel, and managed policies fail closed. | [`test256.md`](../test/test256.md): execution completed; merged PR #454's [`test454.md`](../test/test454.md): Lambda task failure, Catch recovery, normal success, and exact cleanup |
| `aws-sns-notifications` | `modules/sns-notifications` | `aws-jobs-events` / `saas-backend`, `async-data` | Merged PR #450 adds source-only exact planned SNS-to-SQS subscription and queue-policy binding checks; no full topic configuration, fan-out, or cost policy | [`test449.md`](../test/test449.md) proves one direct same-account SNS-to-SQS delivery and teardown | No Nova-dispatched notification, multi-subscriber behavior, SES delivery, or hosted recovery proof |
| `aws-ses-email` | `modules/ses-email` | Notification/email gap under `aws-jobs-events` / no exact scenario binding | Shared checks only; no deliverability, recipient, or sandbox-exit policy | [`test254.md`](../test/test254.md): identity/DKIM verification, not application email delivery |
| `aws-bedrock-runtime` | `modules/bedrock-runtime` | `aws-ai-retrieval` / `ai-rag` | Shared IAM checks only; no model access, guardrail invocation, or token-cost policy | [`test244.md`](../test/test244.md): guardrail resource ready; no model/guardrail request |
| `aws-bedrock-knowledge-base` | `modules/bedrock-knowledge-base` | `aws-ai-retrieval` / `ai-rag` | Shared S3/IAM/network checks; no ingestion-role/index/data-access policy suite | [`test262.md`](../test/test262.md): ingestion and real retrieval |
| `aws-sagemaker-endpoint` | `modules/sagemaker-endpoint` | `aws-managed-ml`; possible CPU/GPU overlap / `machine-learning` | Shared IAM/S3/network checks only; no model artifact, endpoint exposure, quota, or inference cost policy | [`test261.md`](../test/test261.md): real endpoint inference and teardown |
| `aws-kinesis-stream` | `modules/kinesis-stream` | `aws-stream-processing` / `async-data` | PR #475 bounds plans to one provisioned shard, 24-hour retention, KMS encryption, and the AWS-managed Kinesis key. The policy does not cover consumers, producer authorization, checkpoints/replay, or complete regional costs. | [`test258.md`](../test/test258.md): one record accepted; no consumer processing |
| `aws-batch-compute` | `modules/batch-compute` | `aws-jobs-events`, `aws-data-analytics` / `saas-backend`, `async-data` | Merged PR #498 implements source-only bounds for a managed Fargate compute environment, one same-plan queue, digest-pinned container, supported CPU/memory pairs, retries, runtime, same-account role ARNs, and plaintext/reserved environment checks; public-IP use requires review. | [`test252.md`](../test/test252.md): controlled disposable Batch job; merged PR #458 [`test458.md`](../test/test458.md): first-attempt failure, automatic retry, success, and exact teardown. These direct tests do not prove the new policy or Nova dispatch. |
| `aws-eks-cluster` | `modules/eks` | `aws-kubernetes-platform`, `aws-gpu-inference` / `kubernetes` | Merged PR #499 adds source-only private-endpoint, supported-version, control-plane log, same-plan role/template, and bounded managed-node checks. It does not cover Kubernetes/RBAC, admission, pod identity, quota, or complete cost. | [`test255.md`](../test/test255.md): workload service probe through EKS |
| `aws-ec2-autoscaling` | `modules/ec2-autoscaling` | `aws-virtual-machine-service`, possible GPU compute / no scenario for VM/GPU | Merged PR #483 adds source-only policy for `0 <= min <= desired <= max <= 3`, one same-plan launch template with a fixed `latest_version`, known AMI ID, `t3.micro`, and IMDSv2. Open PR #486 implements encrypted root-volume plan checks; all seven checks passed on `bb374e8`, but its clean-room artifact/volume/network cleanup is pending explicit approval. AMI provenance, scoped instance role, guest health, update/recovery, complete price, and Nova dispatch remain unproven. | [`test244.md`](../test/test244.md): zero-capacity ASG reached service-valid state; merged PR #485 [`test485.md`](../test/test485.md): direct isolated `t3.micro` capacity 1→2→1, EC2 checks, and teardown; PR #486 [`test486.md`](../test/test486.md): encrypted root-volume create/health/teardown cycles. Both test EC2 records are terminated. |
| `aws-vpc-private-network` | `modules/vpc` | `aws-private-connectivity` / `hybrid-network` | Merged PR #500 adds source-only bounds for one private IPv4 VPC, paired public/private subnets in two or three AZs, explicit associations, one public-to-IGW route, one private-to-NAT route, and a same-plan VPC EIP/NAT binding. Merged PR #502 adds source-only monthly pricing for NAT hours, data processing, one public IPv4 address, declared internet egress, and cross-AZ payload, using regional AWS Price List products; all seven checks passed on final PR head `86b4b89` in CI run #45578164764. It does not establish runtime traffic or a complete bill. VPC endpoints, IPv6, peering, transit gateways, VPN, DNS reachability, ACL precedence, and effective service reachability remain unsupported. | [`test244.md`](../test/test244.md) VPC for EKS; [`test263.md`](../test/test263.md) includes routed topology; no exact-module lifecycle proof is recorded here |
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
6. **Evidence is shape-specific:** properly isolated direct AWS tests count
   toward the general customer-side lifecycle gate for the exact resource
   shapes and behaviors they exercise. They do not prove Nova authorization,
   dispatch, or credential issuance, nor support for other roots or composed
   scenarios. Record create/invoke/observe/update/failure recovery/teardown and
   independent absence where applicable; do not infer an outcome from a
   scenario name.
7. **Certification record is too small for the goal gate:** record a durable
   test ID, exact main/deployed commit and artifact digests, target account and
   region, cost estimate/actual delayed bill note, resource ownership manifest,
   each behavior result, rollback/recovery result, retained resources, and
   independent absence check. Add update and controlled-failure outcomes rather
   than inferring them from a single `rollback_proven` boolean.

## Status rule

Update individual rows only when the linked evidence exists. Use separate
labels for catalogued, contract-tested, provider-schema-validated,
plan-policy-tested, isolated-AWS-tested, isolated-lifecycle-tested,
hosted-plan-tested, hosted-lifecycle-tested, and cleanup-verified.
`isolated-lifecycle-tested` counts toward the general customer-side lifecycle
gate only for the exact tested shape and observed behaviors. Keep Nova
dispatch evidence separate. Do not promote a root to hosted customer support
based on documentation, CI, Terraform validation, or an isolated test. Runtime
eligibility still requires the applicable renderer and hosted execution gates.
