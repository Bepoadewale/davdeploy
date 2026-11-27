# Backlog

## Nova status snapshot — 2026-11-27

Backend `main` is
`fe02d62f123e27712fee686db05029de8b7a33af` (merged PR #559). Protected plan
`46069601185` and exact saved-plan apply `46070230500` deployed that source;
all six control-plane Lambdas are Active/Successful and match the exact versioned
release package, migrations passed, `/healthz` returned HTTP 200, and the
authenticated CLI `/api/v1/me` returned HTTP 200. The release changed only the
control plane; no Nova customer workload was applied.
PRs #507–#514 add source-only bounded Batch prices; PR #515 adds source-only
private endpoint policy. PR #517 adds backward-compatible private Fargate
networking and records a direct same-account lifecycle test: suffix `a` failed
during a queue-cleanup race, while suffix `b` ran once to `SUCCEEDED`, exit
code 0, and emitted the expected CloudWatch marker. Both exact test stacks
were destroyed and independently checked absent. AWS retains both Batch job
definitions as inactive history; the tag index still reports stale deleted
resource ARNs. This evidence covers only the recorded private Batch shape, not
Nova dispatch, cross-account execution, or a general customer workload.
See `docs/test/test517.md`.

The authenticated workspace administrator and verified same-account plan-only
connection remain available at
`3964addb-9f00-4c87-b829-2c3cd3b0b48c`. PR #559 deployed prompt v21; fresh
plan-only run `d61e0c32-0379-4bd2-a240-a7924f4e98a1` failed before artifact
creation with sanitized `incompatible_health_target` feedback identifying
`container_readiness` targeting `aws_lambda_function`. PR #560 is the current
package: provide fixed guidance to preserve application health requirements
using an already-declared compatible API or event path, without adding a
service or weakening validation. The 26/30 capability map remains the finite
scope reference. Approval, apply and destroy remain closed; no Nova customer
workload has been applied, operated, or certified.


PR #493 merged with all seven checks passing in final-head run
[45515203315](https://github.com/Bepoadewale/davdeploy/actions/runs/45515203315).
The exact `modules/parameter-config` test created a tagged synthetic Standard
`SecureString`, updated it from version 1 to 2, verified both decrypted
versions in memory without printing them, then destroyed the exact parameter.
Independent AWS reads confirmed absence; local state and saved plans are
retained with mode 600. This covers only the tested module shape, not consumer
authorization, rotation, complete cost, Nova dispatch, or workload
certification. Merged-main CI passed all seven checks in
[45516309809](https://github.com/Bepoadewale/davdeploy/actions/runs/45516309809).

PR #424's bounded Aurora pricing and PRs #425–#429's Nova provenance/schema
evidence are in backend source but are not deployed by PR #420. Cost coverage
remains partial. PR #399 merged as `ff6ffae9ab88a37facbc443dfb35efe8c11b598d`;
its apply and credential gates remain disabled in the hosted runtime. PR #413
is merged and maps all 26 architecture entries and 30 Terraform roots to
evidence; it does not establish support for every entry. PR #458 records a
direct same-account Batch retry and teardown test; it does not exercise Nova
dispatch.

PR #461 adds source-only ECR generated-plan checks and records direct same-
account creation, safety-setting verification, and teardown of the exact ECR
module root. Its empty repository is independently confirmed absent. No image
was pushed; provenance, effective scanning, pull/run behavior, and complete
ECR pricing remain open. See `docs/test/test461.md`.

PR #463 adds source-only KMS generated-plan checks requiring a known symmetric
encryption key, automatic rotation, single-Region scope, and a 30-day deletion
window. No customer-managed key was created: AWS bills these keys and requires
a 7–30 day deletion wait. Key policy, consumer binding, and root-specific
lifecycle evidence remain open. See `docs/tickets/ticket463.md`.

PR #465 adds source-only SSM parameter checks for known `SecureString`,
Standard tier, and optional KMS key identity, and explicitly pins the module
to Standard tier. It does not protect secret values in Terraform state or
prove runtime access, rotation, or lifecycle. See `docs/tickets/ticket465.md`.

PR #466 adds source-only OpenSearch plan checks for the module's bounded
single-node/10 GiB shape, VPC mode, encryption, and TLS. Effective subnet and
security-group binding, access policy, query lifecycle, and pricing remain
open. No AWS domain was created. See `docs/tickets/ticket466.md`.

PR #468 adds source-only ACM checks requiring a known domain, DNS validation,
RSA_2048, and export disabled. It does not prove domain ownership, DNS
publication, certificate issuance, or renewal. No certificate or DNS record
was created. See `docs/tickets/ticket468.md`.

PR #470 adds source-only Route 53 zone checks for a known name, no VPC
associations, and `force_destroy=false`. It does not verify ownership,
delegation, records, failover, or DNS costs. No hosted zone was created. See
`docs/tickets/ticket470.md`.

PR #471 binds each planned AppConfig environment to exactly one same-plan
application. PR #495 merged as `526d4e1`, adding the feature profile, typed
flag content, bounded rollout strategy, and revision-retention policy. Its
direct same-account rollout and rollback evidence is in
[`test495.md`](docs/test/test495.md); the approved seven-resource teardown and
clean-room cleanup are complete, with independent absence checks. Final-head
CI passed all seven checks in run
[45631497386](https://github.com/Bepoadewale/davdeploy/actions/runs/45631497386).
No Nova dispatch or broad customer certification is claimed. See PR
[#495](https://github.com/Bepoadewale/davdeploy/pull/495).

PR #473 adds source-only DynamoDB plan checks for known table/partition-key
identity, on-demand billing, server-side encryption, deletion protection, and
enabled point-in-time recovery. It explicitly enables deletion protection in
the bounded module; intentional future teardown needs a separate reviewed plan
to disable it. No AWS table was created. Application reads/writes, restore,
complete regional pricing, and broader DynamoDB configurations remain open.
See `docs/tickets/ticket473.md`.

PR #475 adds source-only Kinesis plan checks for a known stream name, one
provisioned shard, 24-hour retention, KMS encryption, and the AWS-managed
Kinesis key. No stream was created. The prior one-record service test still
does not prove consumer processing, replay, full pricing, or Nova dispatch.
See `docs/tickets/ticket475.md`.

PR #477 adds source-only EFS plan checks for encryption, General Purpose
performance, Bursting throughput, and TCP/2049 ingress from a security-group
source. The module does not yet prove the NFS source is bound to its mount
targets or that file access is authorized. No AWS resource or hosted
control-plane resource changed. All seven checks passed in CI run
[45341680734](https://github.com/Bepoadewale/davdeploy/actions/runs/45341680734);
merged-main CI run
[45342278085](https://github.com/Bepoadewale/davdeploy/actions/runs/45342278085)
also passed all seven checks. File read/write, tenant isolation, lifecycle,
complete EFS pricing, and Nova dispatch remain open. See
`docs/tickets/ticket477.md`.

PR #479 adds source-only ElastiCache plan checks for a sensitive Redis AUTH
token, TLS-required Redis OSS 7.1, one `cache.t4g.micro` node, and exact
TCP/6379 security-group ingress bound to the replication group's security
group. Final-head CI run
[45373475770](https://github.com/Bepoadewale/davdeploy/actions/runs/45373475770)
and merged-main CI run
[45374665792](https://github.com/Bepoadewale/davdeploy/actions/runs/45374665792)
passed all seven checks. No Redis workload was created. Client authentication,
failover, lifecycle, full pricing, and Nova dispatch remain unproven. The AUTH
token may be present in protected Terraform plan/state artifacts. See
`docs/tickets/ticket479.md`.

PR #481 binds each planned EFS mount target to a same-plan file system and
security group, requires NFS ingress on each attached target group, and denies
NFS rules aimed at unrelated security groups. It does not prove mounted file
access, authorization, lifecycle, complete pricing, or Nova execution. No AWS
or hosted control-plane resource changed. Final-head CI run
[45381617316](https://github.com/Bepoadewale/davdeploy/actions/runs/45381617316)
and merged-main CI run
[45382317009](https://github.com/Bepoadewale/davdeploy/actions/runs/45382317009)
passed all seven checks. See `docs/tickets/ticket481.md`.

PR #483 adds source-only EC2 Auto Scaling checks for
`0 <= min <= desired <= max <= 3`, one same-plan launch template with a fixed
`latest_version`, known AMI ID, `t3.micro`, and IMDSv2. Final-head CI run
[45425670662](https://github.com/Bepoadewale/davdeploy/actions/runs/45425670662)
and merged-main CI run
[45426759569](https://github.com/Bepoadewale/davdeploy/actions/runs/45426759569)
passed all seven checks. No ASG, EC2 instance, or control-plane resource was
created. AMI provenance, encrypted disks, scoped role, workload health,
update/recovery, teardown, full cost, and Nova execution remain unproven. See
`docs/tickets/ticket483.md`.

PR #485 merged as `13e34c4c29d72b72cee3b553176e1b93059e3244`; final-head CI
run [45449491450](https://github.com/Bepoadewale/davdeploy/actions/runs/45449491450)
and merged-main CI run
[45450437306](https://github.com/Bepoadewale/davdeploy/actions/runs/45450437306)
passed all seven checks. It records isolated direct Auto Scaling lifecycle evidence for the
bounded PR #483 profile. The no-egress test scaled from one `t3.micro` to two
and back, observed healthy ASG/EC2 status checks, then destroyed the test
stack. The group, launch template, and network are absent; both instance
records are terminated and local state is empty. This does not prove guest
application health, recovery, complete pricing, Nova dispatch, or
cross-account isolation. The merge added no AWS resources.

PR #486 merged as `ee3a407`; its final-head and merged-main checks passed and
the approved clean-room cleanup is complete. Its worktree and retained test
state/evidence remain preserved.

PR #487 merged as `426d81da901555b3fdabbde19d2c2d971319212d`; final-head run
[45476895398](https://github.com/Bepoadewale/davdeploy/actions/runs/45476895398)
and merged-main run
[45477538617](https://github.com/Bepoadewale/davdeploy/actions/runs/45477538617)
passed all seven checks. Its exact DynamoDB module test verified the bounded
configuration, restored a baseline while excluding a later write, and removed
both test tables. Local state is retained and empty; Nova dispatch is not
claimed. See `docs/test/test487.md`.

PR #488 reconciles the canonical status files through PR #487. PR #489 merged
as `5691f070400ac882c9291885668ba3d0150e48a2`; its final-head CI run
[45487279034](https://github.com/Bepoadewale/davdeploy/actions/runs/45487279034)
and merged-main run
[45488186730](https://github.com/Bepoadewale/davdeploy/actions/runs/45488186730)
passed all seven checks. Its exact `modules/lambda-service` test recorded a
reviewed create, synthetic v1 invocation, in-place v2 code update, monitored
teardown, and independent absence checks for the function, role, and log group.
Local state is retained and empty. See `docs/test/test489.md`; this is evidence
for the tested shape only and does not prove Nova dispatch.

Read-only recheck confirmed AWS account `654654474502`, no matching test
DynamoDB table, Auto Scaling group, EC2 instance, or PR #489 Lambda resources,
and zero active Terraform monitor operations (57 historical records). The
hosted control plane and its state/locks were not touched.

The plan-only runner, review, role trust verification, and tenant state APIs
are deployed, but no authenticated customer Nova request has produced a
recorded hosted plan. No Nova-dispatched customer workload is certified. The
owner accepts properly isolated direct same-account customer lifecycle tests
for the general lifecycle gate and exact tested resource shapes; this does not
verify Nova authorization or dispatch, or establish support for other shapes.
See [`docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`](docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md)
for the detailed acceptance map.

PR #422's exact customer plan-role trust and bounded policy checks, PR #429's
provider-schema provenance, and PR #424's pricing are source-only. They do not
establish every effective AWS permission layer or Nova-dispatched execution.
Isolated customer-side lifecycle evidence is tracked separately by resource
shape and is accepted for the general lifecycle gate when its plan, observed
behaviors, teardown, and independent absence checks are recorded.

## Three-PR delivery plan

### Developer and administrator workflow

- [x] Audit the current product and add the separate immutable customer-plan revision foundation.
- [x] Add role-aware local sign-in, tenant-scoped workspace dashboards and browser navigation.
- [x] Add GitHub installation/repository/branch and AWS connected-account selection experiences.
- [x] Add GitHub repository intelligence for safe manifest analysis, persisted runtime/framework/data/deployment hints, and planner/review binding.
- [x] Render one AWS plan with required Prometheus/Grafana details and cost estimate.
- [x] Add editable draft/rejected plan constraints, assumption decisions and revision diffs before approval submission.
- [x] Add submit, administrator approval/rejection, self-approval and revision UI/API flows.
- [x] Add administrator queue filters, richer review evidence, approved-not-deployed banners and export-ready audit evidence.
- [x] Add explicit approved-plan local dry-run execution, observed health/cost state, readiness-failure evidence and governed local destroy.
- [x] Add realistic local demo seeding and expanded product E2E coverage for approve/reject/self-approve/dry-run/destroy/persistence.
- [x] Prove the two-session developer/admin journey with browser controls, deterministic API E2E, restart persistence and security-boundary checks.

### Completed hardening — local commercial V1

- [x] Add provider-agnostic intent adapter, deterministic fixture, material-question handling, richer typed inputs, and source provenance.
- [x] Add repository/cloud connection records and local fixtures.
- [x] Add stale-plan/replay/idempotency/restart-recovery, prompt-injection and readiness-failure coverage.
- [x] Complete visible UI constraints, environment health, governed destroy and audit views.
- [x] Add durable worker jobs, local OTel/Tempo business spans and outcome metrics.
- [x] Add independent frontend static CI plus Compose-backed API contract CI and repeat clean project-runtime bootstrap, success, failure, trace and cleanup evidence twice.

### PR 2 — Cloud-pilot architecture and safe runtime contracts

- [x] Add cloud topology, Terraform foundation, private EKS runtime contracts, IRSA, secrets, GitOps, observability and recovery designs. No apply.

### PR 3 — Cloud-pilot operator workflow and final evidence

- [x] Add GitHub OIDC plan/apply/destroy workflows, cloud operator commands, static contract CI and final plain-English evidence review. No apply.

## Existing product roadmap

### Completed foundation

- [x] Rename product internally to davdeploy.
- [x] Build typed intent, architecture, cost, policy, plan, approval, audit and bounded execution paths.
- [x] Build the product UI, then extract it into the public static React
  `davdeploy-frontend` repository with a versioned API boundary.
- [x] Record two local validation cycles; repeat fully cold bootstrap in PR 1.
- [x] Expose the governed product API through a thin CLI and a stdio MCP server without granting agents approval, cloud, shell, Terraform, Kubernetes or secret authority.
- [x] Demonstrate a bounded Day-2 loop: evidence, recommendation, exact change plan, independent approval, observed local change and audit.
- [x] Show the customer why an architecture was selected and prove both simple non-EKS and complex specialised-EKS local scenarios.
- [x] Persist local incident and recommendation evidence for degraded health and governed Day-2 changes.

## P1 — Customer-cloud execution

- [x] Create the davdeploy control-plane GitHub OIDC identity and a real customer discovery connection. Terraform applied only state/lock and IAM resources; STS, inventory and Cost Explorer were verified without a workload.
- [x] Dispatch the hosted GitHub OIDC plan/apply workflow and prove the production trust route. The
  October 2026 control-plane releases used the reviewed saved-plan gate; customer-workload
  permissions remain separately approved.
- [x] Implement the live AWS STS read-only role-assumption adapter with least privilege after the
  discovery-role pilot. It is limited to verified customer discovery, not deployment.
- [x] GitHub App installation/repository/branch discovery and safe manifest intelligence.
- [x] Local GitHub webhook receiver contract with signature verification, delivery dedupe, replay protection, persisted installation states and UI visibility.
- [x] Desired-state PR publisher for approved customer-plan revisions with exact-digest, branch, GitHub-state and profile-contract guardrails. Fixture mode is default; guarded live GitHub PR creation is implemented behind an explicit write flag.
- [x] Local fixture PR check-state action so the product flow can reach ready preflight and Terraform plan-only review without direct database edits.
- [x] Plan-only App Runner Terraform renderer for approved customer-plan revisions, including digest-bound module inputs, UI preview, offline validation and fail-closed tests. No apply path exists.
- [x] Local cloud-readiness guardrails and operator UX: expected account, allowed regions, required tags, budget ceiling, reviewed PR state, runtime identity, dry-run-only mode and blocked/ready preflight evidence. No cloud action exists.
- [x] Terraform plan-only review gate for approved App Runner revisions: admin-only, exact digest, rendered contract, ready preflight, account/region checks, authenticated-mode `ALLOW_CLOUD_PLAN=true` gate and no apply path.
- [x] Hosted Aurora/PostgreSQL persistence: API rejects hosted SQLite and uses AWS-managed RDS
  credentials through Data API. The private encrypted Aurora cluster, backups, deletion protection
  and release migration path are applied; restore/load/recovery drills remain follow-up evidence.
- [x] Hosted identity guardrails: JWKS/OIDC is required in hosted mode, local fixture login is disabled, and external subjects bind to server-side workspace membership rather than caller-selected organization/role claims.
- [x] Durable guarded App Runner execution queue/worker with exact-digest, administrator, account/region, apply/runtime/confirmation gates and a disabled-by-default profile adapter.
- [x] First-class deployment outputs and observed resource inventory for local dry-run environments, including customer-visible URLs/ARNs/log/dashboard references and destroyed-state history.
- [x] Product-side cloud execution run history for approved App Runner revisions: admin-only, exact digest, rendered contract, ready preflight, plan-review binding and blocked-by-default command evidence.
- [x] Execution-history and evidence-export APIs for customer workload runs, including attempt, digest, source, target, Terraform state, output/resource placeholders, destroy proof and failure reason.
- [x] Define the typed execution lifecycle, bounded renderer registry, and CodeBuild dispatcher (PRs #264–#270). The deployed dispatcher remains App Runner-only and rejects multiple modules. PR #303 fixes the DynamoDB input allowlist and is now included in the deployed backend package; the S3/DynamoDB renderer gates remain disabled.
- [x] Add an isolated Lambda + HTTP API renderer and certify HTTP 200 plus teardown (PRs #267–#269). This is isolated AWS evidence, not hosted customer-runner certification; the renderer remains disabled in hosted execution.
- [x] Persist typed module-instance rows and single-renderer queue/worker/CodeBuild outcomes (PRs #277/#278); add durable worker leases, heartbeat and reconciliation-required state for uncertain outcomes (PR #280). These changes are deployed by reviewed apply run `41716835229`; the customer execution gates remain disabled by default.
- [x] Correct lifecycle terminal-evidence checks (PR #287), validate serialized lifecycle graphs before renderer selection (PR #289), calculate dependency-safe dispatch waves (PR #290), and persist per-module state/output/evidence outcomes (PR #291). These code foundations are merged but are not wired into multi-module worker dispatch.
- [x] PR #320 adds bounded semantic repair for Nova proposal validation failures; PR #321 denies generated EBS volumes unless encryption is known to be enabled. Both are included in the deployed control-plane package; no Nova-generated customer plan has been deployed.
- [x] PR #322 marks generated-plan pricing unavailable and blocks approval unless complete region-bound cost evidence is present. This fail-closed approval gate is deployed; it is not a pricing evaluator. No Nova-generated customer plan has been deployed.
- [x] PR #393 binds proposal health assertions, recovery requirements, cost assumptions and limitations into the plan manifest; PR #395 adds typed bounded health assertions; PR #397 preserves and verifies the exact plan-time workspace. These changes are included in the current hosted control-plane package. They do not execute health probes or record customer workload health. Evidence: `docs/test/test393.md`, `docs/test/test395.md`, and `docs/test/test397.md`.
- [x] PRs #401/#402 add bounded actual-plan network ACL ingress and EC2 IMDSv2 checks; PR #404 requires EKS managed node groups to bind a same-plan launch template with IMDSv2. These checks are included in the current control-plane package; no customer plan has exercised them. ACL topology and broader EKS security remain open. Policy evidence: `docs/test/test401.md`, `docs/test/test402.md`, and `docs/test/test404.md`.
- [x] PR #340 adds a versioned customer plan-role metadata-read profile, a proposal-scoped explicit-deny STS session policy, and saved-plan manifest binding. Its control-plane package was deployed with protected Terraform apply run [42985628568](https://github.com/Bepoadewale/davdeploy/actions/runs/42985628568); exact current-release evidence is in `docs/test/test345.md`, with the earlier #340 release recorded in `docs/test/test341.md`. PRs #343–#345 retained the old setup URL, published the current immutable template and updated the hosted URL. At that release the customer setup template was not installed and hosted role verification was disabled; PR #369 later enabled only trust/account verification.
- [x] Harden actual generated-plan policy for IAM escalation (PR #353), public SQS queue policies (PR #355), and wildcard Lambda invocation (PR #356); suppress raw control-plane plan output with a bounded summary (PR #354). PRs #353–#356 are deployed in the control plane by protected apply run [43082767507](https://github.com/Bepoadewale/davdeploy/actions/runs/43082767507). Exact latest evidence is in `docs/test/test356.md`. These controls do not enable the Nova runner, pricing, approval, customer apply, health or teardown.
- [x] Require explicit review for open API Gateway routes (PR #358) and bind untaggable API Gateway routes to the exact tenant-scoped state and a proposal-owned API reference (PR #359). Both are deployed by protected plan [43098415855](https://github.com/Bepoadewale/davdeploy/actions/runs/43098415855) and exact saved-plan apply [43101777948](https://github.com/Bepoadewale/davdeploy/actions/runs/43101777948). This control-plane rollout does not enable the Nova runner or customer workload execution; see `docs/test/test359.md`.
- [x] Require known, bounded RDS backup-retention values in generated plans, review RDS instances with automated backups disabled, and report or deny unsafe final-snapshot settings for deletes/replacements (PR #361). Deployed by protected plan [43111051028](https://github.com/Bepoadewale/davdeploy/actions/runs/43111051028) and exact saved-plan apply [43112125588](https://github.com/Bepoadewale/davdeploy/actions/runs/43112125588); Nova execution gates remain disabled. See `docs/test/test361.md`.
- [x] PR #363 adds fail-closed actual-plan DynamoDB point-in-time recovery checks and proposal-bound backup requirements. Merged as `4d5997c45c2858c4d5f5b9151ebf793d685f5353`; it is included in the current deployment below. See `docs/test/test363.md`.
- [x] PR #365 rejects common literal credential/secret inputs unless they use a typed secret reference. Merged as `def21021a44c5ec39ddafc295c4c8c6b5ee7b896`; it is included in the current deployment below. It does not resolve tenant-owned references or enable runtime secret retrieval. See `docs/test/test365.md`.
- [x] PR #367 restricts secret references to validated RDS-managed master-user secret ARNs consumed by Lambda `_SECRET_ARN` variables. Merged as `0481696d8a9aa1c73d789b2076a23f9c07ccc1fb`; all seven final-head checks passed in run [43136828000](https://github.com/Bepoadewale/davdeploy/actions/runs/43136828000), and merged-main CI passed in [43137760056](https://github.com/Bepoadewale/davdeploy/actions/runs/43137760056). The contract adds no runtime secret retrieval or secret-read permission. Current release evidence is in `docs/test/test368.md`.
- [x] Deploy backend main `0481696d8a9aa1c73d789b2076a23f9c07ccc1fb` through protected plan [43138701232](https://github.com/Bepoadewale/davdeploy/actions/runs/43138701232) and exact saved-plan apply [43139500663](https://github.com/Bepoadewale/davdeploy/actions/runs/43139500663), deployment `7726355215`. The plan reported 0 additions, 6 Lambda updates, 0 destroys and 0 drift; migrations and API health passed, and all Nova execution gates remain disabled. See `docs/test/test368.md`.
- [x] Deploy the plan-role trust/account verification gate through protected plan [43144381303](https://github.com/Bepoadewale/davdeploy/actions/runs/43144381303) and exact saved-plan apply [43145180803](https://github.com/Bepoadewale/davdeploy/actions/runs/43145180803), deployment `7727105514`. The narrow `sts:AssumeRole` permission targets `davdeployPlan-*` and requires a nonempty external ID plus a verification-only session name. No customer role has been verified; this does not attest effective permissions or enable hosted planning. See `docs/test/test369.md`.
- [x] PR #377 adds typed Nova intent scope handling: unrelated requests receive a fixed refusal and do not create workload intents. It is deployed by protected plan [43191437865](https://github.com/Bepoadewale/davdeploy/actions/runs/43191437865) and exact saved-plan apply [43192601048](https://github.com/Bepoadewale/davdeploy/actions/runs/43192601048); no authenticated customer intent journey was exercised. See `docs/test/test378.md`.
- [x] PR #379 adds proposal-gated, region-bounded read metadata access for proposed VPCs, subnets, and security groups; this control-plane source is now deployed in the PR #381 release. PR #381 separately published the customer role template, but it has not been installed in a customer account and effective permissions are unverified. Routes, internet gateways, NAT, and VPC endpoints remain unsupported by this profile. Evidence: `docs/test/test379.md` and `docs/test/test382.md`.
- [x] PR #381 preserves the prior immutable customer plan-role template URL and publishes the content-hash template. PR #392 validates a disposable plan-only role's trust/policy shape and selected IAM simulator decisions, then deletes its exact stack. No persistent customer connection or role was verified; real broker assumption and account-effective permissions remain unproven. Evidence: `docs/test/test382.md` and `docs/test/test392.md`.
- [ ] Complete the first hosted Nova plan. The deployed plan runner, plan review, credential broker, and state API need an authenticated workspace administrator, verified customer connection/role, and durable plan evidence. As of 2026-11-26, the latest DavDeploy TOTP attempt for the selected account was rejected and no authenticated session or hosted plan exists. Continue independent source work; preserve MFA/tenant authorization and do not issue customer execution credentials or enable generic apply before their exact-plan gates pass. PRs #371/#372 add RDS planner metadata access and PR #379 adds bounded VPC/subnet/security-group metadata reads. PRs #437 and #517 provide direct lifecycle evidence for ECS and private Batch shapes, but do not prove Nova dispatch or cross-account trust.
- [ ] Extend the deployed regional pricing evaluator and usage contracts to cover all material supported resources and supporting costs. PRs #407–#416 add bounded evidence for selected families; PR #424 adds source-only pricing for one Aurora PostgreSQL Serverless v2 writer shape and is merged but not deployed. Unsupported or unpriced material resources continue to block approval. PR #318 remains closed and is not used as current pricing evidence.
- [ ] Define and implement tenant-scoped secret references: bind customer-approved secret identifiers to the trusted deployment context, keep secret values out of Nova prompts and Terraform state, scope runtime reads, and cover rotation/revocation. PRs #365/#367 constrain generated literals and a narrow RDS ARN-reference path; PR #374 denies runtime secret-value grants until policy permissions can be bound to a verified typed reference. Runtime reads remain unavailable.
- [ ] Prove worker restart/reconciliation, bounded retries, partial-failure recovery, typed output binding, and reverse graph cleanup in the hosted worker. PR #399 supplies source tests for the fixed apply worker, but no hosted customer build has exercised it.
- [ ] Dispatch compatible approved module graphs through checked-in renderers with typed outputs, dependency ordering and reverse cleanup. CodeBuild remains single-module and fail-closed until this complete path is validated.
- [ ] Certify each hosted renderer and composed workload through the customer execution runner, including health, update/recovery, destroy and independent absence verification.
- [ ] Ingest real App Runner Terraform outputs and AWS resource observations through the product UI/API execution path.
- [x] Browser-side downloadable plan/audit evidence and Activity grouping/filtering by project and environment are implemented in the static frontend. The export is browser-local and contains only API-rendered evidence.
- [x] Scoped GitHub desired-state publication through reviewed pull requests is implemented behind an explicit live-write flag and test-proven with mocked GitHub API calls. Real customer-repo publication remains opt-in and unexecuted in routine local CI.
- [ ] Real GitOps/Argo observer and customer-cloud workload agent.
- [ ] Enterprise OIDC/JWKS adapter and organisation lifecycle.
- [ ] Replace the fixture inventory and pricing catalogue with customer-approved AWS discovery and timestamped pricing sources.
- [ ] Replace deterministic Day-2 telemetry and the fixed change endpoint with tenant-authorised telemetry, policy-bounded execution and independently observed customer-cloud changes.
- [ ] Execute an authenticated Terraform plan-only review for the selected App Runner contract after a real operator enables `ALLOW_CLOUD_PLAN=true`. Do not add apply until separately authorised.
- [x] Harden the AWS-hosted control plane: hosted Cognito/JWKS identity, policy, and durable Aurora
  PostgreSQL are deployed. Recovery drills and customer-workload execution remain separate work.

## P1 — First cloud pilot prerequisites

- [x] Configure Cognito as the trusted hosted issuer and validate the existing JWKS adapter through
  controlled API, CLI, and MCP acceptance. A recorded full human browser journey remains separate.
- [ ] Configure and test the planned GitHub App desired-state publisher and Argo observer.
- [ ] Configure and test the planned AWS Load Balancer Controller, External Secrets Operator and exact browser redirect/CORS origins.
- [ ] Run an explicitly authorised AWS create → validate → destroy pilot, including the failure, recovery, load and cost-evidence drills.

## P2 — Product depth

- [ ] Live pricing catalogue provider and actual billing evidence.
- [ ] Model release, inference controls and AI telemetry as separately approved slices.
- [ ] Commercial packaging, billing and support workflows after market validation.
