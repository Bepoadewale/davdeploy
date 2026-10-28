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
