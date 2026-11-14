# Backlog

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
- [x] Define the typed execution lifecycle, bounded renderer registry, and CodeBuild dispatcher (PRs #264–#270). The deployed dispatcher remains App Runner-only and rejects multiple modules. PR #303 fixes the DynamoDB input allowlist in merged source; that fix is not in the latest hosted package yet.
- [x] Add an isolated Lambda + HTTP API renderer and certify HTTP 200 plus teardown (PRs #267–#269). This is isolated AWS evidence, not hosted customer-runner certification; the renderer remains disabled in hosted execution.
- [x] Persist typed module-instance rows and single-renderer queue/worker/CodeBuild outcomes (PRs #277/#278); add durable worker leases, heartbeat and reconciliation-required state for uncertain outcomes (PR #280). These changes are deployed by reviewed apply run `41716835229`; the customer execution gates remain disabled by default.
- [x] Correct lifecycle terminal-evidence checks (PR #287), validate serialized lifecycle graphs before renderer selection (PR #289), calculate dependency-safe dispatch waves (PR #290), and persist per-module state/output/evidence outcomes (PR #291). These code foundations are merged but are not wired into multi-module worker dispatch.
- [x] PR #320 adds bounded semantic repair for Nova proposal validation failures; PR #321 denies generated EBS volumes unless encryption is known to be enabled. Both are included in the deployed control-plane package; no Nova-generated customer plan has been deployed.
- [x] PR #322 marks generated-plan pricing unavailable and blocks approval unless complete region-bound cost evidence is present. This fail-closed approval gate is deployed; it is not a pricing evaluator. No Nova-generated customer plan has been deployed.
- [x] PR #393 binds proposal health assertions, recovery requirements, cost assumptions, assumptions and limitations into the exact saved-plan manifest with explicit proposed/unvalidated/unexecuted status. PR #395 adds a typed bounded assertion catalog and compatible-resource checks. Both are source-only and neither executes probes, records observed customer health, or supplies pricing.
- [x] PR #397 preserves the exact generated Terraform configuration, provider lockfile and initialized workspace as a separately KMS-encrypted, versioned artifact bound to the saved plan. The approval path verifies both exact objects. It is merged source only and does not add or enable Terraform apply; pricing still blocks approval. Evidence: `docs/test/test397.md`.
- [x] PRs #401/#402 add bounded actual-plan network ACL ingress and EC2 IMDSv2 checks; PR #404 requires EKS managed node groups to bind a same-plan launch template whose metadata settings require IMDSv2. All are merged source with synthetic/local and hosted CI evidence only; #401/#402/#404 are not deployed or exercised on customer plans. ACL topology, broader EKS security, hosted planning/apply, pricing and workload lifecycle remain open. Evidence: `docs/test/test401.md`, `docs/test/test402.md`, `docs/test/test404.md`.
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
- [ ] Finish the hosted Nova plan-only customer journey and tenant-scoped remote-state path. The isolated runner, plan review, credential broker and state API are deployed, but no authenticated customer request has produced a hosted plan. A disposable IAM policy simulation is evidence only; real customer-role assumption, effective permissions, and service-limit checks remain incomplete. PRs #371/#372 add RDS planner metadata access and PR #379 adds bounded VPC/subnet/security-group metadata reads. No Nova-generated customer plan has been applied.
- [ ] Integrate and verify a trusted regional pricing evaluator that supplies complete cost evidence. PR #318 is closed; its pricing approach remains unresolved. Until pricing is integrated, PR #322's gate blocks generated-plan approval.
- [ ] Define and implement tenant-scoped secret references: bind customer-approved secret identifiers to the trusted deployment context, keep secret values out of Nova prompts and Terraform state, scope runtime reads, and cover rotation/revocation. PRs #365/#367 constrain generated literals and a narrow RDS ARN-reference path; PR #374 denies runtime secret-value grants until policy permissions can be bound to a verified typed reference. Runtime reads remain unavailable.
- [ ] Wire per-module conditional claims, dispatch waves, outcomes, build/result identities, typed output binding, authenticated CodeBuild/SQS reconciliation, bounded safe retries, partial-failure recovery and reverse graph cleanup into the hosted worker.
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
