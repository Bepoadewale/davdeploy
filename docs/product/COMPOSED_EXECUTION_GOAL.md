# Composed AWS execution goal handoff

Updated: 2026-11-24. This handoff tracks the Nova-led infrastructure goal
without claiming launch readiness. Source, hosted control-plane state,
customer-side AWS evidence, Nova execution, application behavior, and per-entry
lifecycle coverage remain distinct.

## Current source and acceptance status — 2026-11-24

The source baseline for this reconciliation is backend `main` at
`5691f070400ac882c9291885668ba3d0150e48a2` (PR #489). The last
hosted backend release remains PR #420 commit
`9951caa9244128b1551fea3af66b1bdbf884c800`, applied by
[run 43982396577](https://github.com/Bepoadewale/davdeploy/actions/runs/43982396577)
after plan
[run 43981566184](https://github.com/Bepoadewale/davdeploy/actions/runs/43981566184).
This reconciliation did not access or change the hosted control plane. The
recorded health observation belongs to the earlier deployment check and was
not repeated here.

PR #477 passed all seven checks on its final head in CI run
[45341680734](https://github.com/Bepoadewale/davdeploy/actions/runs/45341680734).
Merged-main CI run
[45342278085](https://github.com/Bepoadewale/davdeploy/actions/runs/45342278085)
also passed all seven checks. The source-only package requires encrypted EFS,
General Purpose performance, Bursting throughput, and TCP/2049 ingress from a
security-group source. It does not prove mount-target binding, file access,
tenant isolation, lifecycle, complete pricing, or Nova execution. No AWS or
hosted control-plane resource was changed.

PR #479 passed all seven checks on its final head in CI run
[45373475770](https://github.com/Bepoadewale/davdeploy/actions/runs/45373475770);
merged-main CI run
[45374665792](https://github.com/Bepoadewale/davdeploy/actions/runs/45374665792)
also passed all seven checks. It adds source-only Redis plan constraints for
AUTH, TLS, the bounded Redis OSS 7.1 single-node profile, and security-group-
bound TCP/6379 ingress. No Redis workload or hosted control-plane resource was
changed. Client behavior, failover, lifecycle, full price, and Nova dispatch
remain unproven; the AUTH token may enter protected plan/state artifacts.

PR #481 passed all seven checks on final head in CI run
[45381617316](https://github.com/Bepoadewale/davdeploy/actions/runs/45381617316)
and merged-main run
[45382317009](https://github.com/Bepoadewale/davdeploy/actions/runs/45382317009).
It binds each EFS mount target and its NFS/2049 ingress rule to same-plan
security groups. This is source-only; no EFS or hosted resource changed. File
access, authorization, lifecycle, full pricing, and Nova dispatch remain
unproven.

PR #485 merged as `13e34c4c29d72b72cee3b553176e1b93059e3244`; its final-head CI
run [45449491450](https://github.com/Bepoadewale/davdeploy/actions/runs/45449491450)
and merged-main CI run
[45450437306](https://github.com/Bepoadewale/davdeploy/actions/runs/45450437306)
passed all seven checks. It records isolated same-account Auto Scaling lifecycle evidence
for the bounded PR #483 profile. Direct Terraform observed capacity one, two,
then one; EC2 system and instance checks passed at both capacities. The
no-egress test stack was destroyed and its service/network resources were
independently verified absent. This is exact-shape customer-side evidence, not
Nova dispatch, guest application health, or cross-account isolation. The merge
added no AWS resources.

PR #486 remains open at `d8f0d7aff2851815cb46150fb187f01bd5ba9782`; its
final-head CI run
[45466557590](https://github.com/Bepoadewale/davdeploy/actions/runs/45466557590)
passed all seven checks. Two same-account cycles verified encrypted 8 GiB gp3
root volumes and teardown. Its final clean-room cleanup remains pending
approval to remove generated artifacts and Compose volumes in that specific
worktree; those artifacts are preserved.

PR #487 merged as `426d81da901555b3fdabbde19d2c2d971319212d`. Its final-head
CI run [45476895398](https://github.com/Bepoadewale/davdeploy/actions/runs/45476895398)
and merged-main run
[45477538617](https://github.com/Bepoadewale/davdeploy/actions/runs/45477538617)
passed all seven checks. The exact DynamoDB module test verified on-demand
billing, encryption, deletion protection, PITR recovery of a baseline, absence
of a later write in the restored table, and independent cleanup. This direct
test is customer-side evidence for that exact shape; it does not prove Nova
dispatch or live source-read assertions.

PR #488 reconciled canonical status through PR #487. PR #489 merged as
`5691f070400ac882c9291885668ba3d0150e48a2`; final-head CI run
[45487279034](https://github.com/Bepoadewale/davdeploy/actions/runs/45487279034)
and merged-main run
[45488186730](https://github.com/Bepoadewale/davdeploy/actions/runs/45488186730)
passed all seven checks. The exact Lambda-service module test verified a
reviewed four-resource create, synthetic v1 invocation, in-place v2 code
update, monitored destroy, and independent function/role/log-group absence.
This is direct customer-side evidence for the tested Lambda shape; it is not
Nova authorization, dispatch, or customer workload certification.

PR #483 passed all seven checks on final head in CI run
[45425670662](https://github.com/Bepoadewale/davdeploy/actions/runs/45425670662)
and merged-main run
[45426759569](https://github.com/Bepoadewale/davdeploy/actions/runs/45426759569).
It adds source-only Auto Scaling capacity bounds, one same-plan fixed-version
launch template, known AMI-ID, `t3.micro`, and IMDSv2 checks. No AWS or hosted
resource changed. Instance-image provenance, encrypted volumes, role scope,
application health, scaling/recovery, teardown, cost, and Nova dispatch remain
unproven.

PR #399 merged as `ff6ffae9ab88a37facbc443dfb35efe8c11b598d`; all seven checks
passed in [run 44598735006](https://github.com/Bepoadewale/davdeploy/actions/runs/44598735006).
Its exact-plan apply path, credential route, and customer apply-role template
remain source-only and default-off. No Nova apply build, Nova-issued customer
credentials, or Nova-dispatched workload is claimed.

PR #437's isolated same-account ECS Express runs used direct Terraform and
local state. They verified v1/v2 health, unhealthy-revision rollback, and
teardown with independent absence checks. The goal owner accepts a properly
isolated same-account customer test as general lifecycle evidence for the
exact tested resource shape, including when Terraform is run directly rather
than through Nova. The PR #437 evidence meets the general customer-side
plan/apply/health/update/recovery/teardown gate under control-plane isolation.
This is distinct from Nova-dispatch evidence and does not establish
cross-account isolation or support for untested resource shapes.

PR #443 merged as `e63d3ec`; all seven checks passed on final head
`2d15f39d494931c251fd86d1a227693086ea2135` in
[run 45065309558](https://github.com/Bepoadewale/davdeploy/actions/runs/45065309558).
It removes a redundant maximum-action list from the exact-plan STS session
policy while retaining exact-resource denial. A temporary same-account role
and broker used the checked-in role template and exact-plan session policies to
test S3, SQS, and DynamoDB create/read, an SQS update, and a separate
three-service destroy. Out-of-scope S3/SQS/DynamoDB creates and unrelated EC2
access were denied. The test roles, stack, bucket, queue, and table were
independently verified absent. This validates those actions only; Nova did not
issue credentials or dispatch the test, and cross-account trust remains
unverified. See [test443](../test/test443.md).

PR #438's append-only template-host change remains source-only; the protected
state plan showed four address moves and zero resource changes. PR #441's
source-only SQS encryption rule remains undeployed. PR #445 merged source-only
retry/DLQ/visibility and direct Lambda-consumer policy checks. Merged PR #446
fixes source-after-DLQ creation ordering and records isolated SQS delivery,
retry, automatic DLQ transition, and teardown. PR #447 records an actual
same-account Lambda event-source mapping failure/retry/DLQ lifecycle: five
invocations and errors, then the same message in the paired DLQ at receive
count six. Its six-resource test stack and generated Lambda log group were
destroyed and independently confirmed absent. This SQS test does not establish
Nova dispatch, idempotency, composed application health, or hosted SQS
execution. Merged PR #448 records same-account SQS/Lambda/DynamoDB success,
duplicate suppression, failure-to-DLQ, a Lambda-only code update, SQS-managed
redrive, and idempotent recovery. Its exact seven-resource destroy completed;
the queue/table/Lambda/mapping/role/log group are independently confirmed
absent, the local state is empty, and the run monitor has no active work. Its
seven required CI checks passed in [run 45084339682](https://github.com/Bepoadewale/davdeploy/actions/runs/45084339682).
KMS-backed encryption, unsupported consumer-policy shapes, and complete SQS
cost coverage remain incomplete.

PR #449 merged as `c5f7a2c`; all seven checks passed in run `45198632115`.
Its bounded SNS-to-SQS fixture used exact source-topic queue authorization. The
isolated test published and received one synthetic message, verified the exact
payload without printing its body, and emptied the queue. The four-resource
destroy succeeded and the exact AWS topic, queue, and subscription are
independently confirmed absent; local state is empty. It adds direct service
evidence only and does not change hosted control-plane behavior.

PR #450 merged as `8f6f94e`; all seven checks passed in run `45203312830`. Its
source-only generated-plan policy binds planned SNS-to-SQS subscriptions to one
exact topic, queue, attached queue-policy URL, and SNS `SendMessage` grant with
exact source ARN and account conditions. It is not deployed and does not alter
AWS or hosted control-plane state or enable Nova execution.

PR #451 merged as `2400086`; all seven checks passed in run `45207695073`. Its
source-only generated-plan checks bind EventBridge SQS targets to an exact
same-plan bus/rule, queue, attached queue-policy URL, and `events.amazonaws.com`
`SendMessage` grant scoped to the exact rule ARN. EventBridge target roles and
unplanned or unknown target identities fail closed. This does not change AWS
or hosted control-plane state.

PR #452 merged as `6a19316`; all seven checks passed in run `45217552598`. It
adds explicit EventBridge retry bounds and requires a separate planned
standard SQS dead-letter queue (DLQ) with an exact rule-scoped grant. The
controlled direct-service test routed a failure to the EventBridge DLQ,
restored delivery after repairing the exact rule grant, and destroyed the
eight-resource stack with independent absence checks. This remains
customer-side service evidence, not Nova dispatch or hosted execution.
EventBridge target IAM roles and unknown or cross-account target shapes remain
unsupported by the current plan policy.

PR #454 merged as `6791344`; all seven checks passed on final head
`a1a07882e767ae5f05e9a338f63ca7eed3d92138` in run
[45229243421](https://github.com/Bepoadewale/davdeploy/actions/runs/45229243421).
Its direct Step Functions test records a controlled Lambda failure, Catch
recovery, a separate normal success path, and verified cleanup. This does not
establish Step Functions role-policy safety, Nova dispatch, or hosted execution.

PR #456 merged as `d2a9b54`; all seven checks passed on final head
`0bc9935297f00d0a5f9f525e05bd6909e4d8d602` in run
[45235335526](https://github.com/Bepoadewale/davdeploy/actions/runs/45235335526).
It adds source-only generated-plan checks for one Step Functions shape: Standard workflows with direct same-plan Lambda task ARNs, a dedicated
role trusted by the exact state-machine ARN/account, and inline invoke grants
restricted to those functions. It rejects other integrations, logging,
Map/Parallel states, wildcard permissions, and attached managed policies until
their policies are separately covered. This follows AWS's execution-role and
Lambda permission guidance; it does not enable or deploy Step Functions.

PR #458 merged as `b2956ac`; all seven checks passed in run
[45245276054](https://github.com/Bepoadewale/davdeploy/actions/runs/45245276054).
It records a disposable AWS Batch Fargate retry test. The first
attempt exited `1`, the automatic retry exited `0`, and the job succeeded. The
exact stack was destroyed through the run monitor and independently checked
absent; an AWS-managed inactive job definition remains subject to documented
180-day retention. This is direct service evidence, not Nova dispatch or a
hosted customer apply. The hosted control plane remained outside its scope.

Read-only AWS checks on 2026-11-24 in account `654654474502`, region `us-east-1`,
returned no tested DavDeploy SageMaker endpoint, model, endpoint configuration,
execution role, or artifact bucket. Batch listing returned no DavDeploy-named
job queue or compute environment, and five DavDeploy-named job definitions
were inactive: four earlier test definitions plus PR #458's test definition.
This is a name-filtered test-resource inventory, not a complete account
inventory. The test SageMaker lineage action/context remain as audit evidence.
The PR #443
temporary roles and workload resources are absent. PR #446 and #447 test queue
prefixes are absent; the existing production-tagged queue remains. The PR #447
Lambda, event mapping, test role, and generated log group are absent. PR #448
queues, table, Lambda, mapping, role, and generated log group are also absent.
PR #449's four-resource test stack and local state are absent. PR #452's
eight-resource stack and PR #454's five-resource stack and local state are
absent. PR #458's test compute environment, queue, IAM roles, security group,
and log group are absent; one inactive AWS Batch job definition is retained by
AWS. Its local state lists zero resources.

PR #461 merged as `d10a9f6`; all seven checks passed in run
[45262237567](https://github.com/Bepoadewale/davdeploy/actions/runs/45262237567).
It adds ECR repository safety checks and records a direct same-account test of
the exact `modules/ecr` root. One empty repository was created with immutable
tags, declared scan-on-push, and AES256 encryption, then destroyed and
independently confirmed absent. No image was pushed, so image provenance,
effective registry scanning, pull/run behavior, and image pricing remain open.
See [test461](../test/test461.md). The control plane was untouched.

PR #463 merged at `f33ff46`; all seven checks passed on the final head in
[run 45266750554](https://github.com/Bepoadewale/davdeploy/actions/runs/45266750554).
It adds source-only generated-plan checks for symmetric `ENCRYPT_DECRYPT`
keys, automatic rotation, single-Region scope, and a 30-day deletion window,
and makes those settings explicit in the KMS module. No customer-managed key
was created because AWS bills these keys and imposes a 7–30 day deletion wait.
Key-policy safety, consumer binding, and root-specific customer lifecycle
evidence remain open. The hosted control plane was not changed; see
[`ticket463`](../tickets/ticket463.md).

PR #465 adds source-only SSM parameter checks for `SecureString`, Standard
tier, and a known optional KMS key reference. Standard is explicit in the
module. The Terraform state can still contain plaintext parameter values, and
runtime retrieval, rotation, and lifecycle evidence remain open. No AWS
parameter was created; see [`ticket465`](../tickets/ticket465.md).

PR #466 adds source-only OpenSearch checks for the module's one-node
`t3.small.search` and 10 GiB gp3 shape, VPC mode, encryption, HTTPS, and TLS
policy. It does not establish effective network access, query behavior,
lifecycle, or pricing. No AWS domain was created; see
[`ticket466`](../tickets/ticket466.md).

PR #468 adds source-only ACM request checks for a known domain, DNS
validation, RSA_2048, and disabled certificate export. It does not prove
domain ownership, DNS record publication, issuance, renewal, or production
TLS behavior. No ACM or DNS resource was changed; see
[`ticket468`](../tickets/ticket468.md).

PR #470 adds source-only Route 53 checks for known zone names, absence of VPC
associations, and `force_destroy=false`. It does not prove ownership,
delegation, record behavior, failover, or cost. No hosted zone was created;
see [`ticket470`](../tickets/ticket470.md).

PR #471 verifies a same-plan reference from each AppConfig environment to one
application. It does not create or deploy configuration profiles or flags,
and no AppConfig workload or lifecycle was tested; see
[`ticket471`](../tickets/ticket471.md).

The tested ECR repository and local Terraform state are absent. The Terraform
monitor has 57 records and no active operations. The PR #489 Lambda test
function, role, and log group are absent.
Preserve the protected untracked `--only-show-errors`, `.venv-pr399/`, and
lineage evidence.

The product path remains Nova proposal -> deterministic schema/policy and
preflight -> isolated saved plan -> plan-level policy and cost -> authorized
human approval -> exact-plan execution -> observed application health and
lifecycle evidence. Model output cannot authorize execution. Direct isolated
customer tests may satisfy the general lifecycle gate only for their recorded
resource shapes and observed behaviors. Remaining product work includes
Nova-specific authorization/dispatch/credential-path evidence, persistent
customer-role provisioning, cross-account and broader effective-permission
proof, complete cost and policy coverage, Nova-driven application recovery,
and the full scenario matrix. The
[capability evidence matrix](NOVA_CAPABILITY_EVIDENCE_MATRIX.md) retains all 26
architecture entries and 30 implementation roots. The accepted ECS evidence
meets the general customer-side lifecycle gate for that ECS shape; it does not
close other per-entry requirements or prove Nova-originated execution.

## Historical renderer-oriented checklist — superseded by the Nova-led path

The following 2026-11-04 checklist preserves earlier implementation evidence.
Its renderer-by-renderer sequencing is historical and is not the active
execution strategy. Dated release details below remain historical records.

## Ordered execution checklist — historical baseline 2026-11-04

| Step | Status | Evidence and next action |
|---|---|---|
| 1. Reconcile baseline and deploy certification scaffolding | `AWS verified` | PR #270 is merged; required CI passed in run [41670185868](https://github.com/Bepoadewale/davdeploy/actions/runs/41670185868), and its typed CodeBuild dispatcher was applied in run [41671744510](https://github.com/Bepoadewale/davdeploy/actions/runs/41671744510). The latest hosted package is PR #302 commit `7d087d0`, applied by [41781326222](https://github.com/Bepoadewale/davdeploy/actions/runs/41781326222) after plan [41781048128](https://github.com/Bepoadewale/davdeploy/actions/runs/41781048128): 0 adds, 6 changes, 0 destroys; migrations passed and `/healthz` is healthy. PR #303 (`ea9de3a`) is merged and its seven checks passed in [41782907889](https://github.com/Bepoadewale/davdeploy/actions/runs/41782907889), but it is newer than the hosted package. PRs #304 and #305 reconcile deployed/source versions and current cleanup evidence. No hosted customer workload is claimed. The local monitor still has 40 historical `FINISHED_UNKNOWN_EXIT` records; no Terraform process is active. AWS's current `Purpose=davdeploy-module-validation` inventory contains four inactive Batch job-definition records and two SageMaker lineage records marked `DELETING`; no active certification workload was found. Historical monitor exit statuses remain unknown and are not rewritten as successes. |
| 2. Maintain implementation-to-evidence matrix | `implemented` | See `EXECUTION_READINESS_MATRIX.md`. It enumerates all 26 catalogue modules and 30 implementation entries, separating underlying AWS evidence from hosted renderer evidence. Next: enrich each entry with exact accepted inputs/outputs/dependencies, recovery and cleanup proof, pricing source, role, region and quotas as each renderer is implemented. |
| 3. Durable execution engine | `in progress` | PRs #277, #278 and #280 are deployed by protected apply run [41716835229](https://github.com/Bepoadewale/davdeploy/actions/runs/41716835229), including per-module rows, single-renderer outcomes, leases and reconciliation-required state. PR #287 corrected operation-specific terminal evidence. PR #289 validates durable graphs, #290 computes dispatch waves, and #291 persists module-specific outcomes. PR #293 (merged as `87793a7`) separates module type from instance identity. PR #294 (merged as `6e8fb3d`) adds typed reference-only ports. PR #295 (merged as `464dd0b`) validates typed outputs and resolves dependency references without reading secret contents. PR #296 (merged as `9d14bd1`) persists unique per-module CodeBuild identity; PR #297 (merged as `e28fa23`) validates and persists renderer-specific typed outputs. PR #298 (merged as `42200c0`) adds one-at-a-time dependency scheduling and callback advancement. PR #300 (merged as `afd6736`) resolves a validated S3 bucket output into its selected Lambda/API consumer; PR #301 adds a gated DynamoDB renderer and PR #302 adds its typed API input. The #302 code was deployed by plan run `41781048128` and apply run `41781326222` (0 adds, 6 changes, 0 destroys; migrations passed). PR #303 (`ea9de3a`) fixes the `table_name` dispatcher allowlist and is merged/CI-verified, but not deployed. The routes remain gated and no DynamoDB customer workload has run. Worker restart/reconciliation proof, bounded retry policy, partial-failure compensation and real composed cleanup evidence remain. |
| 4. Hosted Lambda/API lifecycle | `in progress` | PR #283 binds renderer dispatch to the persisted certification mode. PR #284 adds typed single-module lifecycle requests, exact prior-run/artifact/saved-plan chaining, apply/destroy confirmations, and an allowlist. PR #285 wires that setting into Terraform. All three are merged and deployed with the gate off. The live hosted lifecycle still needs an authenticated test workspace, pinned compatible source, real HTTP request, destroy and independent cleanup verification. |
| 5. Genuine module composition | `in progress` | PRs #293–#297 add graph identity, typed references/outputs, exact callback matching and output persistence. PR #298 (merged as `42200c0`) schedules one dependency-ready module at a time. PR #299 (merged as `982bb50`) adds a private S3 renderer, still disabled and without real AWS lifecycle evidence. PR #300 (merged as `afd6736`) resolves a validated S3 bucket output into its Lambda/API consumer and scopes Lambda access to that bucket. PR #301 (`5b067b0`) adds a gated DynamoDB table renderer and PR #302 binds its table name to the Lambda/API renderer. PR #303 (`ea9de3a`) fixes the dispatcher allowlist in source; it must be deployed before the DynamoDB binding can run through hosted CodeBuild. Repeated renderer state isolation, hosted worker restart/reconciliation, and composed data-flow/failure/recovery proof remain. |
| 6. Renderer families 1–8 | `in progress` | The full ordering and module scope are in `EXECUTION_READINESS_MATRIX.md`: storage/data/queues; web/edge; containers/VM; databases/cache; async; search/analytics/streaming; AI/ML; Kubernetes/networking/failover. PR #299 is the first checked-in private S3 lifecycle renderer, still gated and locally validated only. PR #300 adds narrow S3-to-Lambda input delivery and scoped Lambda permissions. PR #301 adds a gated DynamoDB renderer; PR #302 adds the table-to-API binding. PR #303 fixes the dispatcher input mismatch in merged source but is not deployed. The repo already has `NovaTerraformGenerator`, which emits a typed Terraform resource graph but is stored as plan-only and is not connected to CodeBuild; it may reduce service-specific renderer code after provider-schema, policy, IAM, cost, saved-plan and lifecycle controls are added. Its existence does not replace real application and cleanup validation. |
| 7. Planning, artifact, pricing and preflight | `not started` | Planner and constraints exist, but the matrix records fixture inputs/pricing and the current Lambda source contract is narrow. Add timestamped regional pricing and quota/permission evidence, bind deployed artifact to reviewed source, and clearly label assumptions. |
| 8. Browser, CLI and MCP parity | `not started` | Shared backend APIs exist; frontend execution remains App Runner-specific and deployment capabilities are not fully surfaced consistently. Align all clients with the same server-authorized lifecycle and observed states. |
| 9. Real application certification harness | `implemented` | A scenario catalogue/runner exists and standalone real AWS workload evidence covers several services. The current runner primarily validates service roots, not composed applications through the hosted runner. Extend it with traffic, update/recovery, cleanup, and machine-readable evidence for all eight scenarios. |
| 10. Security and operational resilience | `not started` | Add adversarial coverage for tenant boundaries, approvals, artifact tampering, duplicate jobs, concurrency, revoked roles, worker restart, partial failures, quotas, callback authenticity, redaction, alarms and cleanup isolation. |
| 11. Hosted browser/CLI/MCP customer acceptance | `not started` | Use the deployed site/control plane and synthetic customer data. Prove intent → plan/cost → authorized decision → apply → real health → update/recovery → destroy → independently confirmed absence across browser, CLI and MCP. |
| 12. Final evidence and closeout | `not started` | Produce the final capability matrix with commits, PRs, workflow IDs and evidence links. Reconcile docs and ensure no unexplained test resources or active processes remain. |

## Active implementation

- Backend `main` is `5691f070400ac882c9291885668ba3d0150e48a2` (PR #489). The last
  recorded hosted release remains PR #420, applied by run `43982396577` after
  plan run `43981566184`; PR #399 has not been deployed to the control plane.
- PR #399 merged with seven checks passing in run `44598735006`. It adds a
  default-off Nova apply worker, credential broker, and customer apply-role
  template. A temporary same-account role test verified ExternalId-based
  assumption, one plan-scoped S3 lifecycle, and an explicit unrelated EC2
  denial; all test resources were removed. This is not complete effective
  permission or cross-account verification. No persistent customer role,
  Nova apply build, or Nova credential issuance is claimed. Both execution
  gates remain disabled.
- PR #437 merged as `7481c1f` after final head `e2c968b`; its seven checks
  passed in run `44586955606`. The isolated customer-side ECS Express runs
  prove v1/v2 health, failed-revision rollback to v2, and teardown. The owner
  accepts this direct-Terraform evidence for the general-goal customer-side
  plan/apply/health/update/recovery/teardown gate; it did not use Nova.
- PR #438 merged as `cb78865`; its seven checks passed in run `44593771329`.
  Its append-only template-host change remains source-only; the protected-state
  plan showed four address moves and zero resource changes.
- PR #441 merged as `48911bf`; its seven checks passed in run `44608565238`.
  It requires known SQS-managed encryption in generated queue plans. The policy
  is source-only and has not been deployed to the hosted control plane.
- The Terraform run monitor has no active runs and retains terminal history. The ECS test
  left no Terraform-managed workload resources; AWS retains inactive service
  history and an empty cluster record. Preserve the protected untracked files
  and retained lineage evidence. Browser/CLI/MCP lifecycle parity and the full
  per-entry capability matrix remain open.

## Verified boundary — historical detail, read with current status above

- Backend main is commit `ea9de3a` (PR #303). The latest hosted release is still PR #302 commit `7d087d0`, deployed by apply run `41781326222`; the reviewed plan changed 6 Lambda packages in place with 0 additions or removals. PR #303 fixes the DynamoDB dispatcher input allowlist in source and passed CI, but is not yet deployed. Renderer routes remain gated. PR #295 validates typed outputs and exposes dependency-output resolution as a library helper; PR #298 schedules one ready module at a time; PR #299 adds a gated private S3 renderer; PR #300 resolves one S3 bucket-name input into Lambda with bucket-scoped IAM; PR #301 adds a gated DynamoDB table renderer; PR #302 binds its table name to Lambda. No hosted composed customer workload has run. PR #275 (`ff5103f`) adds
  project-scoped Lambda/API Terraform state, artifacts, saved plans, results,
  deterministic resource identity and project tags. Its local proof is in
  `docs/test/test275.md`.
- PRs #277, #278 and #280 add deployed module-instance rows, single-renderer
  outcome transitions and durable worker leases, deployed by apply run
  `41716835229`. PR #287 fixes operation-specific evidence checks. PR #289
  validates durable graphs, #290 calculates dependency dispatch waves, and #291
  persists per-module state/output/evidence. These three are merged but not
  connected to the hosted worker.
- PR #280 adds versioned worker leases and refuses to replay an uncertain
  operation. It is merged, CI-verified, and deployed.
- The Lambda/API renderer is still disabled for general hosted customer execution. PR #284's certification route remains off by default with an empty workspace allowlist. Code and disabled configuration are deployed; there is no hosted AWS workload lifecycle evidence yet.
- App Runner remains the only renderer enabled for customer execution.
- PR #293 adds distinct module-type and instance identities. PR #294 adds typed,
  reference-only ports; PR #295 validates typed outputs and resolves declared
  references in library code; and PR #296 persists an exact per-module CodeBuild
  identity and reconciles a callback to that node. PR #297 merged renderer
  output validation and persistence. PR #298 adds durable, one-node-at-a-time
  dependency scheduling to worker claims and callbacks. PR #299 adds a private
  S3 renderer, disabled for execution and without real AWS lifecycle evidence.
  PR #300 resolves a validated bucket reference into Lambda. Repeated/shared
  Terraform state roots, hosted enablement, and composed AWS workload
  certification remain incomplete and fail closed.
- Individual service-level AWS tests do not establish a hosted composed
  customer journey.
- The live API endpoint returning 401 without its required origin and user
  authorization is not a health check. Record only authenticated, authorized
  observations as runtime evidence.

## Nova plan-only runner milestone

- PR #328 merged as `64bfd2c55cf22b61c20305106dcbcec65ef48352` on 2026-11-10.
  Its fixed, versioned, disabled-by-default backend-free planning code is
  included in the November 10 release. Its artifacts are review-only,
  unapprovable, and non-deployable; regional pricing remains unavailable.
- Durable remote state remains a blocker. Proposed ADR-013 selects Terraform's
  built-in HTTP backend, with DavDeploy enforcing tenant/workspace/project/
  environment access and storing encrypted versioned state objects in a
  dedicated S3 bucket, plus locks in PostgreSQL. CodeBuild receives no direct
  state-bucket access. The ADR is a design proposal, not implementation or
  enablement; size, availability, and interrupted-write recovery must be tested
  before customer apply. Direct S3 backend roles remain a fallback, using native
  `use_lockfile=true` and bucket versioning rather than deprecated DynamoDB
  locking. No backend-free plan may count as stateful deployment evidence.
- Plan-runner object access is scoped to the exact CodeBuild ARN in S3 resources;
  the API-only request prefix is inaccessible to CodeBuild. The shared CodeBuild
  role's STS permission still matches the `davdeployPlan-*` role-name pattern.
  The fixed runner binds the ARN to the validated connection/account, each
  customer trust requires its exact ExternalId, and those customer roles deny
  all service actions. Cross-tenant trust tests are mocked contracts, not a live
  IAM simulation. Keep the runner disabled by default, and require an isolated
  per-tenant broker before any plan role receives customer service permissions.

## Evidence update rule

For each step, link the exact PR, merged commit, CI run, evidence file, AWS
account/region and observed results. Never advance a status because code was
written, Terraform validated, a workflow merged, or resource creation
succeeded without the relevant application behavior and cleanup proof.
