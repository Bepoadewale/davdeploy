# Project Status

## Current state

**As of 2026-11-24, backend `main` is
`426d81da901555b3fdabbde19d2c2d971319212d` (PR #487). The hosted control plane
remains deployed from PR #420 commit `9951caa9244128b1551fea3af66b1bdbf884c800`,
using plan [43981566184](https://github.com/Bepoadewale/davdeploy/actions/runs/43981566184)
and exact saved-plan apply [43982396577](https://github.com/Bepoadewale/davdeploy/actions/runs/43982396577).
Both jobs succeeded, including database migrations. Read-only checks found all
six backend Lambdas on code hash `GL+7py0mhfOeY0RcD/BC7RZ0cWS+buxedxhrwtNzps0=`
and `/healthz` returned HTTP 200 in account `654654474502`, region
`us-east-1`. This is control-plane deployment evidence only. This status
refresh did not access or change the hosted control plane. The older runtime
health observation above is historical and was not rechecked here.**

Source includes durable plan requests, isolated Terraform state, plan review,
actual-plan policy, typed health/recovery requirements, exact workspace
artifacts, and bounded regional pricing for selected resource families. Cost
coverage remains partial; unknown or unpriced material resources block
approval. PR #413's 26-capability/30-root evidence ledger is merged.

PR #399 merged with all seven checks passing in
[run 44598735006](https://github.com/Bepoadewale/davdeploy/actions/runs/44598735006).
It adds default-off apply credential/input routes, exact-artifact staging, a
fixed apply worker, and result reconciliation. The apply and credential gates
remain disabled. No Nova-issued customer credential or Nova-dispatched
workload is claimed.

PR #437's isolated same-account ECS Express lifecycle is accepted by the goal
owner for the general customer-side plan/apply/health/update/recovery/teardown
gate under control-plane isolation. It was applied with direct Terraform, not
Nova, and does not prove cross-account isolation.

PR #443 merged with all seven checks passing in
[run 45065309558](https://github.com/Bepoadewale/davdeploy/actions/runs/45065309558).
A temporary same-account broker and customer role were used to test exact-plan
S3/SQS/DynamoDB create/read, SQS update, and separate destroy permissions.
Out-of-scope S3/SQS/DynamoDB creates and unrelated EC2 access were denied.
The stack, roles, bucket, queue, and table were removed and independently
verified absent. This proves only the tested direct role actions; Nova's
credential path, cross-account trust, full effective permissions, and hosted
apply remain unverified.

PR #473 merged with seven passing checks in CI run
[45284594649](https://github.com/Bepoadewale/davdeploy/actions/runs/45284594649).
It adds source-only DynamoDB plan checks for known table identity, on-demand
billing, encryption, deletion protection, and point-in-time recovery. No AWS
table or hosted control-plane resource was changed. It does not prove table
operations, restore, full cost, or Nova dispatch.

PR #475 merged with seven checks passing in CI run
[45288480162](https://github.com/Bepoadewale/davdeploy/actions/runs/45288480162).
Its source-only Kinesis policy checks one provisioned shard, 24-hour retention,
and encryption with the AWS-managed Kinesis key. No stream or hosted
control-plane resource was changed. This does not prove consumer behavior,
complete pricing, lifecycle, or Nova dispatch.

PR #477 merged with all seven checks passing in CI run
[45341680734](https://github.com/Bepoadewale/davdeploy/actions/runs/45341680734);
merged-main CI run
[45342278085](https://github.com/Bepoadewale/davdeploy/actions/runs/45342278085)
also passed all seven checks. It adds source-only EFS checks for encryption,
General Purpose performance, Bursting throughput, and exact TCP/2049 NFS
ingress from a security-group source. No EFS or control-plane resource changed.
Mount-target binding, file I/O, access authorization, lifecycle, complete
pricing, and Nova dispatch remain unproven.

PR #479 merged with all seven checks passing in CI run
[45373475770](https://github.com/Bepoadewale/davdeploy/actions/runs/45373475770)
and merged-main CI run
[45374665792](https://github.com/Bepoadewale/davdeploy/actions/runs/45374665792).
It adds source-only Redis plan checks for a sensitive AUTH token, TLS-required
Redis OSS 7.1, one `cache.t4g.micro` node, and exact security-group-bound
TCP/6379 ingress. No Redis or hosted control-plane resource changed. Client
authorization, failover, lifecycle, complete pricing, and Nova dispatch remain
unproven; Terraform plan/state may contain the token.

PR #481 merged with all seven checks passing in CI run
[45381617316](https://github.com/Bepoadewale/davdeploy/actions/runs/45381617316)
and merged-main CI run
[45382317009](https://github.com/Bepoadewale/davdeploy/actions/runs/45382317009).
It binds the EFS mount-target security groups to same-plan NFS rules. This is
source-only; no EFS or control-plane resource changed, and file access,
authorization, lifecycle, full pricing, and Nova dispatch remain unproven.

PR #483 merged as `72009437bd567f3e3b0a948efdf9451848523475`. Final-head CI
run [45425670662](https://github.com/Bepoadewale/davdeploy/actions/runs/45425670662)
and merged-main CI run
[45426759569](https://github.com/Bepoadewale/davdeploy/actions/runs/45426759569)
passed all seven checks. It adds source-only Auto Scaling bounds, same-plan
fixed launch-template version binding, known AMI-ID shape, `t3.micro`, and
IMDSv2 requirements. No EC2/ASG or hosted control-plane resource was changed.
AMI provenance, encrypted disks, scoped role, guest health, scaling/recovery,
full cost, and Nova execution remain unproven.

PR #485 merged as `13e34c4c29d72b72cee3b553176e1b93059e3244`; its final-head
CI run [45449491450](https://github.com/Bepoadewale/davdeploy/actions/runs/45449491450)
and merged-main CI run
[45450437306](https://github.com/Bepoadewale/davdeploy/actions/runs/45450437306)
passed all seven checks. It records direct same-account lifecycle evidence for PR #483's
bounded EC2 Auto Scaling profile. The isolated no-egress stack reached
capacity one and two with healthy ASG and EC2 checks, returned to one, and was
destroyed with independent absence checks. Both EC2 records are terminated;
the local Terraform state is retained and empty. No Nova dispatch or guest
application health is claimed. The merge added no AWS or control-plane
resources.

PR #486 remains open and unmerged at
`d8f0d7aff2851815cb46150fb187f01bd5ba9782`. Its final-head CI run
[45466557590](https://github.com/Bepoadewale/davdeploy/actions/runs/45466557590)
passed all seven checks. Two isolated direct same-account cycles verified an
encrypted 8 GiB gp3 root volume, healthy ASG/EC2 checks, and teardown with
independent absence checks. Its remaining review finding requires final
clean-room cleanup; that cleanup would remove the clean-room worktree's
generated `.venv`, `.local`, and Compose volumes and remains pending explicit
approval. Those local artifacts are preserved.

PR #487 merged as `426d81da901555b3fdabbde19d2c2d971319212d`. Final-head CI
run [45476895398](https://github.com/Bepoadewale/davdeploy/actions/runs/45476895398)
and merged-main CI run
[45477538617](https://github.com/Bepoadewale/davdeploy/actions/runs/45477538617)
passed all seven checks. Its exact `modules/dynamodb-table` test observed
on-demand billing, encryption, deletion protection, and enabled 35-day PITR;
a captured restore returned the baseline item and omitted a later synthetic
write. Monitored cleanup removed the restored and source tables; independent
AWS inventory found no test table, and retained local state lists no
resources. The evidence proves source writes and restored-table reads, not
Nova dispatch or live source-read assertions.

PR #445 merged with all seven checks passing in
[run 45072091356](https://github.com/Bepoadewale/davdeploy/actions/runs/45072091356).
It adds source-only generated-plan checks for one-to-one SQS retry/DLQ pairs
and direct same-plan Lambda consumers; it has not been deployed to the hosted
control plane. Draft PR #446 adds the SQS module creation-order dependency and
records an isolated SQS message-to-DLQ lifecycle. The test queues were
destroyed and independently confirmed absent. This is direct service evidence,
not Nova dispatch or customer application certification.

Read-only inventory on 2026-11-24 in account `654654474502`, region `us-east-1`,
found no tested SageMaker endpoint, model, endpoint configuration, execution
role, or artifact bucket. Batch listing returned no DavDeploy-named job queue
or compute environment, and five DavDeploy-named job definitions were
inactive: four earlier test definitions plus PR #458's test definition. This
is a name-filtered test-resource inventory, not a complete account inventory.
SageMaker lineage evidence remains retained. The SQS test prefix is absent;
the existing production-tagged queue remains. A later read-only recheck
verified account `654654474502`, no matching DynamoDB test table or Auto
Scaling group, no matching EC2 test instance, and 54 monitor records with no
active run. Preserve `--only-show-errors`,
`.venv-pr399/`, and lineage evidence. The frontend status remains based on
the 2026-11-17 read-only snapshot and is not refreshed by this PR.

## What is implemented

- Multi-organisation product domain and PostgreSQL persistence.
- Signed local development identity fixture, tenant checks and a production-facing JWT/JWKS verifier interface.
- Natural-language intent fixture → typed `WorkloadSpec`.
- Small, auditable AWS V1 catalogue that considers static, serverless, managed application, managed containers, VM, Kubernetes, managed-AI, CPU and GPU options. It rejects hard-constraint failures, reuses fixture-approved resources, and selects the lowest-complexity option in the configurable cheapest viable cost band.
- OPA policy, immutable plan hashes, independent production approval and durable audit.
- Tenant-scoped GitHub repository and AWS BYOC connection metadata. No reusable cloud credentials are stored.
- Durable local execution jobs processed by a separate bounded worker, with observed READY, FAILED and DESTROYED states.
- A separately versioned static React frontend in the public `davdeploy-frontend` repository, consuming this API through a committed OpenAPI contract and exact-origin CORS; Prometheus metrics, OpenTelemetry business traces, Tempo and Grafana dashboard provisioning remain here.
- One governed REST API shared by the browser, a thin CLI, and a stdio MCP server. Agent clients can analyse, plan, compare, estimate, inspect, request eligible execution, create desired-state PR publications, and create a destroy plan; they cannot self-approve, merge GitHub PRs, or receive cloud, shell, Terraform, Kubernetes, or secret access.
- GitHub App repository discovery, repository intelligence, webhook workflow contract, and guarded desired-state PR publication. The selected `Bepoadewale/ai-platform-control-plane` repository was read through a short-lived installation token. The adapter can inspect safe repository metadata plus selected manifest files, persists credential-free runtime/framework/data/deployment hints, and can create a reviewed desired-state branch/PR only when `DAVDEPLOY_GITHUB_APP_WRITES_ENABLED=true` is explicitly configured. Signed fixture webhooks now persist installation state and deduplicated deliveries; default local publication remains fixture-only.
- Executed customer-AWS discovery connection: Terraform created an encrypted, versioned davdeploy state bucket, a DynamoDB lock table, GitHub OIDC control-plane identity, one read-only discovery role and one empty future-execution role. STS role chaining, real account inventory and Cost Explorer discovery were proved. No workload, network, database or compute resource was created.
- Customer AWS connection UI is implemented and live-verified through an AWS-hosted App Runner runtime: a user can choose an AWS target, enter an account ID, open a CloudFormation Quick Create review, and queue server-side STS verification. Connection external IDs are protected through a control-plane secret-store interface; the browser and normal connection record never hold them. A separate App Runner runtime IAM role prevents the GitHub Actions role from being the production runtime identity. The public CloudFormation template host is applied and verified as a versioned S3 object.
- Hosted persistence is active: the API runs with `DAVDEPLOY_HOSTED_MODE=true` and resolves its PostgreSQL connection through an AWS Secrets Manager RDS credential. The Aurora PostgreSQL cluster is private, encrypted, available, and configured with backups and deletion protection. This does not by itself prove a customer workload deployment.
- Hosted identity binding is now hardened: `DAVDEPLOY_HOSTED_MODE=true` requires JWKS/OIDC configuration, local fixture login is rejected, and verified external subjects map to server-side workspace membership. Caller-provided organization and role claims cannot elevate access. Cognito requires password plus authenticator-app TOTP; invitation delivery is deployed. Enterprise federation, a recorded browser journey, and broader lifecycle operations remain follow-up work.
- API edge protection is active: `api.davdeploy.tech` is a Cloudflare Worker proxy carrying a secret origin header, and the direct API Gateway endpoint rejects requests without that header. Cloudflare free custom WAF and rate-limit rules protect common probes and excessive API requests.
- CloudTrail management-event auditing is active: a multi-region, log-file-validated trail writes to a private encrypted S3 bucket with public access blocked.
- Hosted invitation delivery is active: the verified Resend domain sends invitations from `notify@davdeploy.tech`, replies route to `support@davdeploy.tech`, and the sending-only key is held in a Standard SSM SecureString readable only by the API role. This proves sender delivery and reply routing, not yet the complete browser invitation-acceptance journey.
- Approved App Runner cloud runs now have a durable execution boundary: an administrator can queue an exact-digest run only after all account/region/apply/runtime/confirmation gates pass, and the trusted worker invokes only the configured App Runner adapter. The default adapter is disabled and no live workload is executed by routine local/CI paths.
- PRs #299–#303 add gated S3 and DynamoDB renderer bindings and typed Lambda/API inputs. PR #303 (`ea9de3a`) fixes the dispatcher allowlist for `table_name` and is included in later hosted control-plane releases. These gated renderers still lack hosted composed customer workload evidence.
- Nova proposal repair, generated-plan policy, durable requests, remote state, saved-plan review and exact workspace artifacts are implemented and included in the current control-plane release. The plan-only runner and review APIs are deployed, but there is no recorded authenticated customer request producing a Nova plan. The App Runner customer renderer remains the only generally enabled workload path; Nova S3/DynamoDB and serverless renderers remain gated, and hosted multi-module composition is not certified.
- Merged PRs #407–#416 add regional pricing for selected bounded resource families and expose the assumptions in plan review. Merged PRs #417–#420 make the protected control-plane plan summaries inspectable while keeping values redacted. These changes are deployed in PR #420's release, but unpriced material costs still block approval.
- Draft PR #399 contains the source-level exact-plan apply credential/input APIs, staged artifacts, fixed apply worker and result reconciliation. Its gates remain disabled; the customer apply role, hosted apply and full workload lifecycle have not been verified.
- Backend PR #279 improves the local Terraform run monitor. PR #280 adds atomic worker claims, lease heartbeats and explicit reconciliation for uncertain outcomes. Protected Terraform apply run `41716835229` deployed the merged worker/database changes from PRs #277, #278 and #280. Customer-execution gates remain unchanged.
- A bounded Day-2 loop: deterministic latency evidence, a transparent replica recommendation, immutable `CHANGE` plan, independent production approval, durable worker, observed result and audit. It is local fixture evidence, not autonomous remediation or cloud monitoring.
- One selected AWS customer-plan review with durable submit, administrator approval/rejection, editable draft/rejected constraint revisions, filtered administrator review queues, rich review evidence and explicit self-approval audit paths. Approval remains separate from execution.
- Approved customer-plan revisions can be explicitly executed as bounded local dry runs. The trusted worker independently observes READY, FAILED or DEGRADED evidence, ties each local environment back to the approved revision/digest, and supports a governed local destroy request/approval/observed-destroy path. This is local fixture execution only and does not create or delete AWS resources.
- Local dry-run environments now persist customer-facing deployment outputs and observed resource inventory as first-class records. The review/API/UI show outputs such as application URL, App Runner service ARN, log group and Grafana dashboard reference plus observed resources and statuses. Destroy keeps the historical records and marks them `DESTROYED`.
- Approved App Runner customer-plan revisions can now create administrator-only cloud execution run records from the product UI/API. Each run is bound to the exact approved digest, Terraform render, cloud-readiness preflight and Terraform plan-only review. Local/default mode records execution-history and command evidence only; it does not apply Terraform or create AWS resources.
- Cloud execution runs are now available through execution-history and evidence-export APIs. Evidence bundles include attempt number, approved digest, source repository/branch/commit status, target account/region, Terraform command/status, outputs/resources placeholders, destroy proof and failure reason without claiming cloud deployment when none occurred.
- Approved customer-plan revisions can also create a persisted desired-state PR publication. The package binds the exact approved digest, selected repository/branch, selected architecture profile and profile-specific delivery contract. Fixture mode stores a local `fixture-pr://` record. Guarded live mode creates a dedicated `davdeploy/desired-state-<digest>` branch, commits the package files, opens a GitHub pull request and posts an davdeploy status. davdeploy still never merges code or deploys infrastructure from that PR.
- Approved `aws-app-runner` customer-plan revisions can render a plan-only Terraform deployment contract. The UI/API preview includes service, source/ECR boundary, IAM, environment variables, secret references, HTTPS assumptions, Prometheus/Grafana monitoring, required tags, account, region and exact plan digest. It is offline validation only: no authenticated Terraform plan, apply, destroy, AWS API call or workload deployment occurs.
- Approved customer-plan revisions can run a workspace-administrator-only local cloud-readiness preflight. It checks exact digest, policy, Terraform contract, no apply command, expected account, allowed region, tags, budget, reviewed PR state, runtime identity and dry-run/plan-only mode, then records a blocked or ready-for-future-plan result. This is guardrail evidence only; it does not execute cloud actions.
- Workspace administrators can now record a Terraform plan-only review from the approved digest, generated App Runner contract and cloud-readiness preflight. Local mode records the permitted `terraform init`/`terraform plan` command shape and keeps apply unavailable. Authenticated mode is gated behind explicit request approval plus `ALLOW_CLOUD_PLAN=true`; no authenticated AWS plan was executed in this PR.
- The [governed workload-adapter catalogue](docs/architecture/adapter-catalogue.md) defines the bounded AWS workload families, AI/ML patterns, composition rules and release cadence. It explicitly distinguishes catalogue/planning scope from separately proven pilot execution.
- Terraform contracts for a separate state/lock/budget foundation and private VPC, EKS, ECR, RDS, Secrets Manager and IRSA runtime.
- Hardened Kubernetes and Argo CD desired-state contracts, External Secrets and artifact-storage contracts, plus planned private observability/recovery controls.
- Customer-facing infrastructure-plan records now have separate draft, submitted, approved and rejected revision states. They are distinct from bounded execution plans: approval never deploys. Workspace-administrator self-approval is explicitly recorded and tenant-scoped.

## Boundaries

- Latest hosted deployment: backend source `9951caa9244128b1551fea3af66b1bdbf884c800` (PR #420; main has since advanced through source-only PR #422), plan run [43981566184](https://github.com/Bepoadewale/davdeploy/actions/runs/43981566184), and exact saved-plan apply [43982396577](https://github.com/Bepoadewale/davdeploy/actions/runs/43982396577). Migration verification passed. The six backend Lambda packages share code hash `GL+7py0mhfOeY0RcD/BC7RZ0cWS+buxedxhrwtNzps0=` and `/healthz` returned HTTP 200. This is control-plane health only.
- PR #303's `table_name` dispatcher fix and the later bounded pricing and plan-summary changes are now included in the hosted package. The Nova apply worker from draft PR #399 is source-only and gated off.
- The hosted dispatcher still rejects multi-module runs. App Runner is the only generally enabled renderer. The Lambda/API renderer has isolated real AWS evidence (`docs/test/test268.md`) but remains gated; S3 and DynamoDB renderer paths are also gated and lack hosted lifecycle evidence. See `docs/product/EXECUTION_READINESS_MATRIX.md` for all 26 catalogue entries, 30 implementation entries, and remaining execution gaps.

- Routine product operation still does **not** deploy a customer workload into AWS or a customer account. Customer-AWS discovery is live and read-only; it is not deployment permission. Customer-plan dry runs execute only against the local fixture worker. PR #42 separately executed and destroyed a guarded App Runner customer workload pilot twice using scripts/Terraform evidence. The current hosted control plane is the serverless Lambda/Aurora deployment, with password-plus-authenticator Cognito access and server-side workspace membership; it is a controlled private-beta control plane, not production workload execution. Cost Explorer values are delayed billing data, not settled cost evidence.
- Terraform plan-only review records are governance evidence unless a future operator deliberately enables and runs authenticated plan mode. They are not apply, destroy or workload-readiness evidence.
- The local identity issuer, intent provider and execution target are fixtures. The JWKS adapter is implemented but not connected to an enterprise issuer.
- Hosted identity has a server-side membership boundary, Cognito password-plus-authenticator access, and Resend invitation delivery. A recorded full human browser invitation-to-approval journey, enterprise federation, and broader lifecycle operations remain follow-up work.
- GitHub OAuth/install initiation, real public webhook delivery, live reviewed desired-state PR writes/checks, profile-specific customer-workload deployment permission, GitOps/Argo execution, enterprise IdP, external agent-client installation and billing are next work, not evidence.
- Role-aware local sign-in, `/me`, tenant-scoped workspace dashboards and administrator-only review queues are implemented for pending, approved, rejected and self-approved plan revisions. Customer-plan submission, administrator approval/rejection and revision APIs/UI are locally implemented with separate signed fixtures; they are not enterprise sign-in. A deterministic two-session E2E script exercises developer submission, administrator decision, self-approval, rejection/revision, access denial, fixture PR/check review, App Runner Terraform rendering, ready preflight, Terraform plan-only review, approved local dry-run execution, readiness failure, governed local destroy and restart persistence without touching AWS.
- The local product flow can list a GitHub App installation's authorized repositories and branches, preserve the selected branch with the project, analyze safe repository manifests, and show/disconnect tenant-owned AWS connection metadata. Fixture mode is locally verified; the existing GitHub App adapter can perform the same repository/branch/manifest reads with a configured short-lived installation token and has a separately gated reviewed-PR publisher. AWS remains read-only discovery only.
- The create-plan screen produces exactly one selected AWS customer-plan review draft. It binds the selected GitHub branch, AWS target, region, typed workload specification and available inventory snapshot. The creator can revise editable constraints before submission or after rejection, with a new digest and visible diff. Prometheus-compatible metrics and Amazon Managed Grafana are required typed review components with private-access, coverage, limitation and estimated-cost information. The creator can submit the immutable review; an administrator can inspect requester/repository/AWS target/digest/policy/monitoring/cost/risk evidence and approve or reject the exact digest, including self-approval. After approval, a separate local dry-run button queues the fixture executor and shows observed environment health, estimate and destroy state. None of those decisions or dry runs deploy cloud resources.
- `make seed-demo-data` can populate a fresh local workspace with realistic draft, submitted, approved, rejected, self-approved and dry-run records for hand demos. It uses only the local API and fixture executor.
- The generated App Runner Terraform contract preview appears only after approval and remains labeled `PLAN_ONLY_NOT_APPLIED`.
- The cloud-readiness preflight appears only after approval for workspace administrators and remains labeled local/preflight-only. In the local fixture demo, an administrator can record reviewed PR/check state and enable the runtime-identity checkbox to produce `READY_FOR_AUTHORIZED_CLOUD_PLAN`; this remains governance evidence only, not cloud execution.
- The AWS execution run card appears only after approval for workspace administrators and remains blocked by default as `BLOCKED_CLOUD_EXECUTION_NOT_ENABLED`. It records command/evidence history and the required App Runner execution sequence, but automated/local mode cannot run Terraform apply.

## Next delivery sequence

1. Run and record the controlled human browser invitation-to-approval journey, then conduct an explicitly approved Aurora recovery drill.
2. Wire the guarded App Runner execution run to an explicitly enabled operator apply/destroy path and ingest real Terraform/AWS outputs into the output/resource inventory model.
3. Browser download/export controls are implemented. Wire real App Runner apply/destroy output ingestion into the existing execution evidence model.

## Nova deployment workflow next gates

1. Define and verify the customer-owned least-privilege apply role for a bounded supported plan; keep trust/account checks separate from effective-permission and service-limit evidence.
2. Prove the hosted Nova plan and exact cost-bound approval journey for a supported configuration; unsupported or unpriced resources must continue to block approval.
3. Complete PR #399 review after current CI; keep apply and credential gates disabled until the customer role and exact-plan path are independently verified.
4. Run the first authorized hosted lifecycle: apply the saved plan, probe the real application, perform an update and controlled failure/recovery, then destroy and independently verify absence.
5. Extend composition and renderer coverage and align browser, CLI, and MCP behavior. No Nova customer workload has been applied or certified yet.

## Clean-room reproducibility

Status: the earlier V1 proof completed two clean local-runtime cycles plus one rebuilt-image confirmation. The frontend separation is independently verified and this backend uses an API/CORS contract in place of the retired embedded-browser contract. Cached Docker images are not treated as runtime state.

## Cloud contract validation

On 2026-10-09, authenticated Terraform plans and identity-only applies completed for the davdeploy state foundation, control-plane identity and one customer discovery connection. On 2026-10-13, Terraform applied the hosted App Runner control-plane runtime, ECR repository, runtime IAM role and runtime signing secret. The hosted runtime assumed a temporary customer read-only discovery role, recorded a live inventory snapshot, then the temporary customer stack/role and per-connection ExternalId secret were deleted. This is executed control-plane/discovery evidence only; no customer workload runtime was applied.

## Future operator workflow

CI validates Terraform and Kubernetes contracts. The manual GitHub OIDC saved-plan workflow has been
dispatched successfully for the hosted serverless control-plane releases. That proves the platform
trust route only; it does not authorise a customer-workload Terraform apply or destroy.

## Previous hosted Nova plan-only control-plane deployment — 2026-11-13

Backend `main` commit `ae9ec4450d527141081e95707a1c3ee05126b683` (PR #390)
was deployed using protected plan [43388286514](https://github.com/Bepoadewale/davdeploy/actions/runs/43388286514)
and exact saved-plan apply [43389226372](https://github.com/Bepoadewale/davdeploy/actions/runs/43389226372).
The reviewed plan had 1 addition, 8 in-place changes, and 0 destroys or
replacements. Database migration verification passed. Read-only verification
confirmed the fixed `nova-plan-only-start-build-overrides` policy is attached
to `davdeploy-api`, the API Lambda is Active/Successful with
`CodeSha256=E1O6BxLyyxTN/epgvT0pyCkQU1bE4QXi+drUAp+cE+I=`, and `/healthz`
returned HTTP 200 in account `654654474502`, region `us-east-1`. The isolated
plan-only CodeBuild project uses its fixed service role and pinned runner
release. Nova plan reviews, runner readiness, role verification, credential
broker, and state storage/API are enabled in the hosted control plane; hosted
certification remains disabled. A disposable plan-only role passed IAM policy
simulation for bounded metadata reads and explicit denials, then its exact test
stack was deleted. This does not prove a real DavDeploy role assumption or
customer-account effective permissions. No customer plan or workload was run;
pricing approval and customer lifecycle certification remain incomplete.
Evidence: [`test391.md`](docs/test/test391.md) and
[`test392.md`](docs/test/test392.md).
