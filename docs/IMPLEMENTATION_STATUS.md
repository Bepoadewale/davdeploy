# Implementation Status

## Executed locally

| Scale-ready platform boundaries | Versioned tenant, evidence, model, job, capability, cost and usage contracts are implemented. Durable PostgreSQL jobs, provider-neutral model gateway, typed planning evidence, fail-closed isolated execution context/cell placement, tenant entitlements and deterministic planner regression scenarios are locally tested. These boundaries support future scale evolution; they do not claim million-customer capacity today. |

| Capability | Evidence |
| --- | --- |
| Intent to typed specification | Provider interface, deterministic fixture, optional Nova 2 Lite/Bedrock adapter, local schema validation, bounded semantic repair (PR #320), provenance, usage metadata and material follow-up questions. A capped two-case live synthetic Nova evaluation passed in the pilot account; customer activation remains gated on the broader benchmark, pricing catalog and tenant rollout controls. |
| Nova proposal policy and execution boundary | PR #321 adds fail-closed policy for generated EBS volumes unless encryption is known to be enabled. Merged PR #322 marks regional pricing unavailable and blocks approval until complete region-bound cost evidence is present. PR #328 adds a disabled-by-default initial plan runner; PRs #331–#332 add gated state API and isolated-state wiring, while #333–#334 add tenant-scoped plan request history. PR #340 adds a bounded customer metadata-read role profile, proposal-scoped explicit-deny STS session policy, and manifest binding. PR #351 adds the connection API's fail-closed `plan_role_setup_available` hint. PR #353 adds fail-closed IAM escalation checks to actual generated-plan policy; its source is deployed by protected apply run [43071712182](https://github.com/Bepoadewale/davdeploy/actions/runs/43071712182). The setup hint does not attest role permissions. PR #344 publishes the current versioned customer role template; it has not been installed in a customer account. The dedicated encrypted/versioned state bucket is provisioned, but the state API, runner, plan review and role verification remain disabled. Customer role installation/effective permissions are unverified. The runner cannot yet produce an approvable plan because complete regional pricing and exact cost-bound approval are unavailable. PR #318 is closed and its pricing approach remains held for account-owner direction. No Nova-generated AWS plan has been applied. |
| Architecture and cost proposal | Constrained AWS V1 candidate planner: hard-constraint rejection, fixture inventory reuse, component cost ranges, complexity scores, rejected alternatives and upgrade triggers |
| Governance | Live OPA policy, immutable SHA-256 plan hash, independent approval and audit |
| Durable state | PostgreSQL in Compose; SQLite only in fast unit tests |
| Customer AWS discovery and pilot access | Implemented: customer-managed role attachment or a versioned CloudFormation setup link; default read-only discovery; Secrets Manager ExternalId contract; durable server-side STS verification; and credential-free inventory storage. The explicitly selected administrator-pilot path requires a server-enforced acknowledgement, creates a separate execution role, and verifies that both roles can be assumed into the selected account. DavDeploy stores no customer credentials. |
| Customer AWS Quick Create | Implemented and live-verified for read-only discovery: UI target picker/account-ID flow, API setup contract, public versioned CloudFormation template host, hosted runtime, and separate broker identities. The hosted runtime assumed a temporary customer read-only discovery role, stored a live snapshot, and the temporary customer role/stack plus per-connection ExternalId secret were deleted afterward. Administrator-pilot setup has automated contract coverage but has not deployed a customer workload. |
| Hosted control-plane persistence | Executed: the serverless hosted mode rejects SQLite and uses private encrypted Aurora PostgreSQL through RDS Data API with AWS-managed credentials, backups and deletion protection. The database is available and the release migration Lambda has completed. Restore, load and recovery drills remain follow-up evidence. |
| Hosted identity binding | Executed for controlled Cognito password-plus-authenticator/API/CLI/MCP acceptance: hosted mode requires JWKS/OIDC configuration, local fixture login is disabled, password is the sole first factor, software-token MFA is required, and verified external subjects resolve to server-side workspace membership. JWT organization/role claims are not trusted for authorization. A full human browser invitation-to-approval journey remains release evidence. |
| Private-beta control plane | Durable tenant-scoped invitation records, hashed scoped API credentials with revocation, usage records, immutable plan comments, support tickets, and export/deletion request records are exposed through versioned APIs and audited. Resend invitation delivery is deployed with a verified sender domain and a runtime-only Parameter Store key. Hosted SSO, billing collection, deletion execution, and a recorded full browser journey remain follow-up work. |
| Guarded App Runner execution worker | Implemented / locally verified: administrator-only exact-digest cloud runs can enter a durable queue and a trusted worker invokes only the configured App Runner adapter. The default adapter is disabled; live Terraform/AWS execution remains explicitly gated and unexecuted in routine CI. |
| GitHub desired-state PR publishing | Implemented / unexecuted against live customer repos by default: approved plan revisions can publish a desired-state package. Fixture mode records a local PR contract; guarded live mode uses a GitHub App installation token to create a branch, commit package files, open a PR and post review status only when explicitly enabled. davdeploy never merges the PR. |
| GitHub repository discovery and intelligence | Executed: the selected GitHub App installation issued a short-lived token to read `Bepoadewale/ai-platform-control-plane` metadata. Implemented: safe manifest analysis for runtime, framework, database, secret and deployment hints; persisted repository-analysis records; planner/review binding. Local signed webhook fixtures persist installation state, delivery dedupe/replay protection and UI-visible revoked/missing-permission/repository/branch states. The live adapter refuses writes and PR publication; real public webhook delivery remains unexecuted. |
| Connection experience | Local UI/API lists deterministic GitHub App installations, permitted repositories and branches; it persists the selected branch and credential-free repository analysis with a project. The existing live adapter can list configured-installation repositories, branches and selected manifests using a short-lived token. AWS target detail/status and disconnect are tenant-scoped and credential-free. |
| One AWS customer-plan review | A local typed review draft binds repository branch, AWS target/region, workload spec, cost, security and policy findings. It presents one selected AWS design, never a customer-facing alternatives list. Draft and rejected reviews can create new edited constraint revisions with visible diffs before submission. Prometheus-compatible metrics and Amazon Managed Grafana are mandatory typed components with coverage, access boundary, limitations and estimated monitoring cost. |
| Customer-plan decision workflow | Creator-only submission validates the typed AWS review and freezes its digest. Workspace administrators approve or reject only the submitted digest; rejection requires a reason; rejected plans can create a new immutable draft revision from explicit user constraints. Administrator self-approval is explicitly recorded. Filtered review queues cover pending, approved, rejected and self-approved revisions. Every path is approval-only and never deploys. |
| Customer-plan local dry run | Approved customer-plan revisions can be explicitly queued into the bounded local fixture executor. Environments record the originating revision/digest, execution mode, estimated cost and observed READY/FAILED/DEGRADED state. Production destroy uses the existing destroy plan, administrator approval and observed DESTROYED path. No AWS resources are created or deleted. |
| Deployment outputs and resource inventory | Local dry-run execution now persists first-class environment outputs and observed resources. Review and environment APIs expose application URL, App Runner ARN, log group, Grafana dashboard reference, resource identity/status/tags and destroyed-state history. Secret-like values are represented as references or masked display values rather than raw secrets. |
| Cloud execution run history | Approved App Runner customer-plan revisions can create administrator-only cloud execution run records. Runs bind the approved digest, Terraform render, cloud-readiness preflight and Terraform plan-only review, then record the guarded App Runner execution command sequence and blockers. Default/local mode is blocked and cannot apply Terraform. |
| Execution evidence export | Cloud execution run history can be listed and exported as structured evidence containing attempt, digest, source repository/branch/commit placeholder, target account/region, Terraform command status, outputs/resources placeholders, destroy proof and failure reason. Tenant isolation is enforced. |
| Durable module-instance execution outcomes | PRs #277/#278 add run-scoped module-instance records and persist queue, worker, and trusted CodeBuild outcomes with digest/project checks and idempotent replay. Deployed in production by apply run [41716835229](https://github.com/Bepoadewale/davdeploy/actions/runs/41716835229); schema v24 completed. The current dispatcher remains single-renderer only. |
| Worker claim and uncertain-run handling | PR #280 (`ef60ac3`) adds conditional claims, versioned lease tokens, heartbeat renewal, and a reconciliation-required state if an operation's outcome is uncertain. Fifty focused tests and full verification (397 tests) pass; clean-room passes at code commit `3f32dc9`; all seven CI jobs passed in run [41713672566](https://github.com/Bepoadewale/davdeploy/actions/runs/41713672566). Deployed by apply run [41716835229](https://github.com/Bepoadewale/davdeploy/actions/runs/41716835229). It deliberately does not retry potentially applied infrastructure work. |
| Desired-state PR publication | Approved customer-plan revisions can create a persisted fixture PR publication. The package binds the exact approved digest, repository/branch, selected AWS profile and profile-specific delivery contract. A workspace administrator can record local fixture check state such as `CHECKS_PASSED` for demo proof. davdeploy cannot merge and the live GitHub adapter still refuses writes. |
| App Runner Terraform contract rendering | Approved `aws-app-runner` customer-plan revisions can render and persist a plan-only Terraform module-input contract. The preview binds service/source/IAM/secret/HTTPS/Prometheus/Grafana/tag/account/region fields to the exact approved digest. Offline `terraform init -backend=false` and `terraform validate` pass against the renderer root. No Terraform plan/apply/destroy or AWS API call is exposed. |
| Cloud-readiness guardrails | Approved customer-plan revisions can run a persisted local preflight that checks exact digest, policy, plan-only Terraform contract, absence of apply command, expected account, allowed region, required tags, budget ceiling, reviewed desired-state PR state, runtime identity and dry-run/plan-only execution mode. The result is a `would_deploy` preview plus `BLOCKED_*` or `READY_FOR_AUTHORIZED_CLOUD_PLAN` state. |
| Terraform plan-only review gate | Workspace administrators can record a digest-bound Terraform plan-only review after approval, App Runner contract rendering and cloud-readiness preflight. Local mode records the only allowed `terraform init`/`terraform plan` command shape and keeps apply unavailable. Authenticated mode is blocked unless both the request and `ALLOW_CLOUD_PLAN=true` are explicitly set. No AWS plan/apply/destroy is executed in automated validation. |
| Customer-plan E2E proof | Separate local developer and administrator HTTP sessions prove submission, administrator approval, self-approval, rejection/revision, stale-digest rejection, developer/tenant denial, fixture PR publication/check recording, App Runner Terraform rendering, ready cloud-readiness preflight, Terraform plan-only review, approved-plan local dry-run execution, readiness failure, governed local destroy, audit evidence and persistence after API restart. The backend API/CORS contract and separate frontend workflows are independently tested. |
| Bounded fixture execution | API persists a `QUEUED` job; a separate trusted worker invokes either the fixed local HTTP fixture or hosted stateless fixture adapter and records READY, FAILED or DESTROYED evidence. Neither adapter has customer-cloud authority. |
| Day-2 change loop | Deterministic latency evidence → explanation → immutable `CHANGE` plan → production approval → durable worker → observed recovery and audit |
| Customer decision view | Browser renders one selected AWS plan, with its fixture cost range, security, Prometheus/Grafana contract, assumptions, risks and deployment boundary; internal alternatives remain planner evidence only |
| Incident evidence | PostgreSQL persists local degraded-health incidents and the recommendation lifecycle from proposed to applied/resolved |
| Identity boundary | Local signed-token fixture coverage plus hosted Cognito JWKS/OIDC verification; browser tokens are resolved to server-side membership and never grant cloud authority |
| Workspace views | Separate signed local developer and administrator fixture identities; backend-enforced current-user, tenant-scoped dashboard and administrator-only review APIs; browser sign-in/sign-out, filtered administrator queues, rich review evidence, explicit approved-not-deployed banners and seedable demo records |
| Audit evidence | Human-readable audit evidence endpoint and UI timeline with actor, role, action label, revision, digest, decision reason and export-ready structure for governance review |
| UI and monitoring | Static React/TypeScript client in the public `davdeploy-frontend` repository; this control plane exposes `/metrics`, Prometheus, business OTel spans, Tempo and Grafana datasources/dashboard for request, plan-policy and observed-execution outcomes |
| Agent clients | Authenticated REST API, thin CLI, and stdio MCP server. They use the same API and do not expose approval, cloud credentials, shell, Terraform, Kubernetes, or secrets. The full local Compose proof exercises MCP tool discovery. |

## Simulated

- Natural-language understanding uses deterministic parsing by default. A governed Nova 2 Lite adapter is implemented and its basic live transport/response shape was verified with two synthetic cases, but it remains disabled for customers until current pricing, broader evaluation and tenant rollout gates are configured. Generated-plan pricing remains unavailable and PR #322 blocks approval until a trusted region-bound pricing evaluator supplies complete evidence.
- The default planner inventory and pricing remain local fixtures. The separately recorded customer discovery snapshot is live, read-only evidence; it does not grant deployment permission.
- Customer-plan dry-run deployment, destroy and Day-2 change application are bounded local fixtures, not AWS, Terraform, Docker or Kubernetes execution.
- Deployment outputs/resource inventory are currently populated from the bounded fixture observer. Real AWS App Runner outputs were proven in PR #42 scripts/evidence, but they are not yet ingested through the product UI execution path.
- Cloud execution runs currently record the product-side execution boundary/history only. They do not invoke Terraform apply or create AWS resources unless a later PR wires an explicitly enabled operator apply path.
- The selected AWS review, cost and monitoring configuration are deterministic local planning fixtures, not live AWS pricing, managed Prometheus/Grafana provisioned resources, or a deployed workload.
- The App Runner Terraform renderer and Terraform plan-only review gate are implemented and locally validated, but they have not run an authenticated customer-workload AWS plan and cannot apply resources.
- Cloud-readiness preflight is local guardrail evidence. The hosted runtime identity is now applied and verified for read-only discovery only; this does not prove live GitHub checks, Terraform workload plan/apply, GitOps sync or workload readiness.
- Local signed JWT, developer/administrator sign-in, and workspace dashboards remain deterministic fixture coverage. Hosted Cognito OIDC/JWKS verification and exact-origin browser access are configured; broad enterprise identity acceptance remains follow-up work.

## Roadmap only

GitHub OAuth/install initiation, live GitHub webhooks/reviewed PR writes/checks, authenticated Terraform workload plan execution and apply through the product UI, product-ingested real AWS deployment outputs/resource inventory, real GitOps/Argo execution, enterprise identity, external agent-client installation, subscription billing, model runtime controls and automated remediation.

## Statically validated cloud contract

Terraform describes separate state/lock/budget guardrails plus a private VPC, EKS, ECR, RDS, Secrets Manager and IRSA foundation. Kubernetes describes hardened API replicas, probes, a PDB, default-deny policy and placeholder-only secret/image references. Argo CD describes reviewed desired-state reconciliation. Terraform format, offline-backend initialisation and validation passed. None of those resources or controllers has run in AWS.

GitHub Actions runs lint, tests, OpenAPI drift checks, dependency audit, secret scan, OPA tests, SBOM, filesystem scan, image build, Terraform/Kubernetes contract checks, realistic demo seeding and the full local proof (simple, complex, degraded, Day-2, customer-plan dry-run/destroy, policy/readiness failure, traces and MCP tool discovery). Frontend static-hosting tests run independently in `davdeploy-frontend`. The manual GitHub OIDC workflow has exact plan/apply/destroy confirmations and an account check, and its reviewed saved-plan path has deployed the hosted serverless control plane. It remains distinct from unexecuted customer-workload plan/apply authority.
# Current hosted execution status — 2026-11-11, after PR #353 rollout

Backend `main` commit `0896ae6106fe1e7526dba90105639f894d5534b8` (PR #353)
is deployed by protected Terraform plan run [43067874795](https://github.com/Bepoadewale/davdeploy/actions/runs/43067874795)
and apply run [43071712182](https://github.com/Bepoadewale/davdeploy/actions/runs/43071712182),
deployment `7717369668`. The saved-plan digest was
`534d53f8a25efaa3ff24f84cbafbadb916688f6c1b0f012cb18737429d811814`;
the reviewed summary was 0 additions, 6 in-place Lambda updates and 0
destroys. Database migration verification passed. All six Lambdas are Active
with successful updates and share `CodeSha256`
`AYMfASSOQwXh35Mn64rq4qFKnJAXb53JrlIXE0G8+bg=`. Read-only AWS identity was
account `654654474502` in `us-east-1`, and `/healthz` returned
`{"status":"ok","product":"davdeploy"}`.

The plan-only runner, customer-role verification, credential broker, plan
reviews, Terraform state API, and hosted certification flags remain `false`.
The legacy cloud-execution command and `ALLOW_CLOUD_PLAN`/`ALLOW_CLOUD_APPLY`
values remain `true`; they do not enable the separate Nova saved-plan path.
No Nova-generated customer plan or customer workload has been applied,
operated, or certified. Regional pricing remains unavailable, and no
cost-bound customer approval, health/recovery lifecycle, or teardown is
certified. Release evidence is in [`test353.md`](test/test353.md).

# Historical hosted execution status — 2026-11-11, after PR #351 rollout

Backend `main` commit `512c9a89c977a338a839f5496d8273380cd39eb8` (PR #351) is
deployed by protected Terraform plan run [43054392241](https://github.com/Bepoadewale/davdeploy/actions/runs/43054392241)
and apply run [43056460175](https://github.com/Bepoadewale/davdeploy/actions/runs/43056460175),
deployment `7715227677`. The plan manifest digest is
`e6ce53b3200b3b27bd7fab14d897843aaf2d546f3e57c344e857a3c1ee8c04aa`; its
reviewed action summary was 0 additions, 6 in-place Lambda package updates,
and 0 destroys. Migration verification passed. All six Lambdas are Active
with successful updates and share `CodeSha256`
`kQ4bt+RXAYn9up4SM+dR8qlXdqxnz33YIW/Oprv10Mg=`. Read-only AWS identity was
account `654654474502` in `us-east-1`, and `/healthz` returned
`{"status":"ok","product":"davdeploy"}`.

PR #351 adds `plan_role_setup_available` to the customer connection response.
This is a display hint only. Plan reviews, the plan-only runner, plan-role
verification, credential broker, and state API still read `false` at runtime;
the setup action remains unavailable until its runtime prerequisites are
deliberately enabled and a real customer role is verified. Regional pricing
remains unavailable, so a generated plan cannot receive final cost-bound
approval. No Nova customer plan or workload has been run or applied, and no
customer health, recovery, or teardown has been certified.

# Historical hosted execution status — 2026-11-11, after PR #345 rollout

Backend `main` commit `10103149d444805877b464ae4e9afe056f8af3f8` is deployed
by protected apply run [42985628568](https://github.com/Bepoadewale/davdeploy/actions/runs/42985628568).
PR #344 published the new immutable customer Quick Create template while
retaining the former 7e URL. Both old and new public URLs returned HTTP 200;
the S3 objects remain versioned and AES256-encrypted. The protected
`terraform-plan` environment now points to the new f3d9e1 URL. Control-plane
plan run [42985045247](https://github.com/Bepoadewale/davdeploy/actions/runs/42985045247)
and its exact saved-plan apply changed six Lambda functions in place with zero
creates or destroys. The plan manifest digest is
`c6a7f6577ee92645dd8f570e5736f2fee64fdea00819385048b5ed041cd78733`.
Database migration verification passed. All six functions are Active with
successful updates, and `/healthz` returned `{"status":"ok","product":"davdeploy"}`.

The Nova plan-review, plan-only runner, plan-role verification, and Terraform
state API flags remain `false`. The existing legacy `ALLOW_CLOUD_APPLY=true`
configuration was not changed by this rollout and does not enable the Nova
saved-plan path. No Nova-generated customer plan or customer workload has been
applied, operated, or certified. Pricing remains unavailable for approval;
Nova plan generation, exact costed approval, customer health, recovery, and
teardown remain incomplete. Full template-host and protected release evidence
is in `docs/test/test345.md`.

# Historical hosted execution status — 2026-11-11, PR #340

Backend PR #340 merged as `8d3b4764bcefae8cb9f93a930b064e10fd893762` and is
deployed in the protected control-plane release. Exact plan/apply and post-
release evidence is in `docs/test/test341.md`. The release updated six Lambda
packages in place (zero creates, deletes, or replacements), migration
verification passed, all six functions are active with successful updates, and
`/healthz` returned `{"status":"ok","product":"davdeploy"}`. Plan reviews,
the plan-only runner, customer role verification, and the state API remain
disabled. The updated customer plan-role template has not been installed in a
customer account; no customer role or workload was changed. PR #340's fixed
proposal-scoped session policy is deployed as code, but no hosted customer plan
has run and regional pricing remains unavailable. No Nova-generated AWS
workload has been applied, operated, or certified.

The plan reported one Terraform state-drift record on parent bucket metadata
for the Nova state bucket; its separately managed policy, versioning, and
encryption resources were no-ops, and the bucket had no planned action. The
saved plan's exact digest and redacted action summary are retained in
`docs/test/test341.md`.

# Historical hosted execution status — 2026-11-10

PR #328 merged to `main` as `64bfd2c55cf22b61c20305106dcbcec65ef48352`. Its fixed Nova runner for backend-free initial Terraform plans is included in the November 10 hosted backend release, but remains disabled by default; its artifacts cannot be approved or applied. The runner has no remote state or lock, and it does not integrate regional pricing. The customer plan role denies customer service actions. No Nova-generated AWS workload has been applied, operated, or certified. Durable tenant-isolated state, costed exact-plan approval, scoped apply, health observations, recovery, and teardown remain incomplete.

PR #328's final PR head `8929956` passed seven CI checks in run `42802196788`; full local and isolated verification passed 820 tests. The November 10 protected release for backend `main` commit `f0c6f3af36a0ab14a5dafb9a1684c41140da7eef` was planned in run [42902031985](https://github.com/Bepoadewale/davdeploy/actions/runs/42902031985) and applied in run [42902934302](https://github.com/Bepoadewale/davdeploy/actions/runs/42902934302). The reviewed plan had 6 additions, 8 in-place changes, and 0 destroys; database migration verification passed. Read-only checks observed `davdeploy-api` Active at `2026-11-10T21:48:25Z`, `GET /healthz` HTTP 200, and an unauthenticated request to the new plan-history route HTTP 401. The Lambda package CodeSha256 was `yu14QmQKQN4NYV2BUHt2/rP/Xf3ZHYQMk9SHcM/Aphw=`. Nova plan review, runner readiness, role verification, and state API flags remain false; no state bucket is configured. PRs #333 and #334 plan-history APIs are deployed, but an authenticated customer journey has not been verified. No AWS customer workload or customer infrastructure was created or changed by this release. PR #318's pricing work remains held for account-owner direction.

# Historical hosted execution status — 2026-11-04

The control plane remains active. The latest protected Terraform apply is run [41781326222](https://github.com/Bepoadewale/davdeploy/actions/runs/41781326222) for PR #302 commit `7d087d06aa97df4596e97b4eef7871c70c8a9cc8`. Its reviewed plan updated six Lambda packages in place with zero creates and zero destroys. Migration verification passed and `https://api.davdeploy.tech/healthz` returned `{"status":"ok","product":"davdeploy"}`. PR #303 (`ea9de3a8211b37518205300f8cfd5384c5814f20`) merged after that apply; it fixes the CodeBuild dispatcher allowlist for the typed DynamoDB `table_name` input. Its seven required checks passed in [run 41782907889](https://github.com/Bepoadewale/davdeploy/actions/runs/41782907889), but that source change is not yet deployed. No customer workload was created by the latest release.

PR #283 binds renderer dispatch to persisted certification mode. PR #284 adds a typed single-module Lambda/API lifecycle, chained to exact approved runs and pinned artifact/saved-plan digests. PR #285 wires a protected workspace allowlist into Terraform. The Lambda/API route is not yet AWS-certified through the hosted control plane. App Runner remains the only generally enabled hosted renderer, and multi-module CodeBuild work remains rejected.

PRs #277, #278 and #280 add durable per-module run rows, outcome persistence,
worker leases and reconciliation-required state after uncertain outcomes.
These are deployed. They do not yet provide a dependency-aware graph scheduler,
partial-failure recovery or multi-module cleanup proof.

PRs #289–#303 add further graph, scheduler, output-binding and gated renderer
code. The PR #302 package is deployed; PR #303 only corrects dispatcher source
and still needs a separately reviewed Terraform deployment. These changes do
not yet establish hosted composition, restart/resume, partial-failure recovery,
or independent cleanup verification.

The older dated sections below describe implementation and validation at their stated time. Read them as historical evidence, not as the current deployment state.
