# Execution readiness matrix

Audit originally captured 2026-11-04 at backend main commit `c2c6279` (PR #315). Current hosted deployment evidence is updated below; dated entries that follow remain historical where explicitly stated. App Runner remains the only enabled customer renderer; the Lambda, S3 and DynamoDB renderer routes remain gated off.

## Current backend source — 2026-11-12, PR #363

Backend `main` is merge commit `4d5997c45c2858c4d5f5b9151ebf793d685f5353`;
merged-main CI run
[43123201873](https://github.com/Bepoadewale/davdeploy/actions/runs/43123201873)
passed all seven jobs. PR #363 adds actual-plan DynamoDB point-in-time
recovery checks, but has not been deployed; the hosted control plane remains at
PR #361 below. Frontend PR #102 locally implements paginated plan history and
latest run status, but remains a draft, is not deployed, and has no authenticated
production customer journey. No Nova-generated customer plan or workload has
been applied, operated, health-checked, recovered, or destroyed.

## Current hosted release — 2026-11-11, PR #361

Backend `main` commit `5775d766584f31f8a31b6b22e8e523b4e8a3f257` (PR #361) was
applied by protected Terraform plan
[43111051028](https://github.com/Bepoadewale/davdeploy/actions/runs/43111051028)
and exact saved-plan apply
[43112125588](https://github.com/Bepoadewale/davdeploy/actions/runs/43112125588),
deployment `7722764924`. The reviewed plan reported 0 additions, 6 in-place
Lambda package updates, 0 destroys, 0 replacements or other changes, 0 drift,
and 8 output changes. Migrations passed after one retry while Aurora resumed.
All six Lambdas are Active/Successful and share
`CodeSha256=29j5jv6Gefv883KmJnN2DyKTo8VH9Ma8pck8uE63AHQ=`. Read-only identity was
account `654654474502` in `us-east-1`; `/healthz` returned
`{"status":"ok","product":"davdeploy"}`. PR #361 adds fail-closed RDS
backup-retention validation, review when an RDS DB instance disables automated
backups, and review or denial for RDS deletes/replacements according to final
snapshot settings. Nova runner, role verification, credential broker,
Terraform state API, plan reviews, and hosted certification remain `false`.
Legacy cloud-execution, `ALLOW_CLOUD_PLAN`, and `ALLOW_CLOUD_APPLY` remain
`true`; they are not Nova plan/apply gates. No Nova customer plan or workload
was applied, operated, health-checked, or certified. Release evidence:
[`test361.md`](../test/test361.md).

## Historical hosted release — 2026-11-11, PR #359

Backend `main` commit `d734547a0551e85c5eafcc7349561e3ea7790589` (PR #359) was
applied by protected Terraform plan
[43098415855](https://github.com/Bepoadewale/davdeploy/actions/runs/43098415855)
and exact saved-plan apply
[43101777948](https://github.com/Bepoadewale/davdeploy/actions/runs/43101777948),
deployment `7721332861`. The reviewed plan reported 0 additions, 6 in-place
Lambda package updates, 0 destroys, 0 replacements or other changes, 0 drift,
and 8 output changes. Migrations passed. All six Lambdas were Active with
successful updates and shared
`CodeSha256=vg52ZDcTSAhZ3hK7dra2Ou7oExSdzGDPjMBjoNQe4ZM=`. Read-only identity was
account `654654474502` in `us-east-1`; `/healthz` returned
`{"status":"ok","product":"davdeploy"}`. The deployment included PR #359's
exact state-backed ownership for untaggable API Gateway routes. No Nova
customer plan or workload was applied, operated, health-checked, or certified.
Release evidence: [`test359.md`](../test/test359.md).

## Historical hosted release — 2026-11-11, PR #358

Backend commit `4de1022592fdf65cdd38f32386cbccbce5a40071` (PR #358) was applied
by protected plan `43088843169` and exact saved-plan apply `43091195912`,
deployment `7720114909`. Its plan reported 0 additions, 6 in-place Lambda
updates, 0 destroys, no drift, and 8 output changes. Migrations passed. All
six Lambdas were Active/Successful with
`CodeSha256=ow5dokRWRp4rsyxb3NnPpkjIfil1xps+G4/OwLcgV9g=`; `/healthz` returned
`{"status":"ok","product":"davdeploy"}`. Nova execution gates remained off.
PR #358 added actual-plan API Gateway route authorization policy. Evidence:
[`test358.md`](../test/test358.md).

## Historical hosted release — 2026-11-11, PR #356

Backend `main` commit `11e66e878933a69638128a8bab80115c051d230a` was applied
by protected Terraform plan [43081890092](https://github.com/Bepoadewale/davdeploy/actions/runs/43081890092)
and apply [43082767507](https://github.com/Bepoadewale/davdeploy/actions/runs/43082767507),
deployment `7718925708`. Saved-plan manifest SHA-256:
`e6b6babaa01f0e4ebcf2b30023231e47e45f2edc2c142ff71a905bcc005efecf`.
Reviewed summary: 0 additions, 6 in-place Lambda updates, 0 destroys, no drift,
and 8 output changes. Migrations passed; all six Lambdas were Active and
Successful with `CodeSha256=qdnufg4s7uxN9qJyxhyWs8rD/GXgt+PzXeKlKLYyt3g=`;
`/healthz` returned HTTP 200. The Nova plan runner, customer-role verification,
broker, plan reviews, state API and hosted certification remained false or
absent. No customer Nova plan/workload was created, applied, operated, or
certified. Full release evidence is in [`test356.md`](../test/test356.md).

### PR #359 initial plan attempt and successful retry

PR #359 merged as `d734547a0551e85c5eafcc7349561e3ea7790589` after all seven
final-head checks passed (PR run `43093754779`; merged-main run
`43094436034`). Its first rollout attempt `43095354497` ended
`startup_failure` with no job or Terraform execution. The successful retry is
plan `43098415855` and apply `43101777948`, recorded above. The first attempt
was not treated as a plan or deployment.

## Historical hosted release — 2026-11-11, PR #351

Backend commit `512c9a89c977a338a839f5496d8273380cd39eb8` (PR #351) was
applied by protected Terraform plan [43054392241](https://github.com/Bepoadewale/davdeploy/actions/runs/43054392241)
and apply [43056460175](https://github.com/Bepoadewale/davdeploy/actions/runs/43056460175), deployment `7715227677`. The exact saved plan manifest digest was `e6ce53b3200b3b27bd7fab14d897843aaf2d546f3e57c344e857a3c1ee8c04aa`. The plan updated six Lambda functions in place, with 0 additions and 0 destroys; database migration verification passed. Read-only checks confirmed all six functions Active with successful updates and common `CodeSha256` `kQ4bt+RXAYn9up4SM+dR8qlXdqxnz33YIW/Oprv10Mg=`, and `/healthz` returned HTTP 200. PR #351 exposes a customer-safe plan-role setup readiness hint in the connection API. Runtime values for plan runner readiness, role verification, the credential broker, Terraform state API, and plan reviews remain `false`; the hint does not attest effective customer permissions or enable planning. The plan-role setup path remains unavailable until the required runtime gates and configuration are deliberately enabled and a customer role is verified. No Nova customer plan or workload has been created, applied, operated, or certified.

Earlier the same day, backend commit `a533d131b50add04b9a9d3501ebba07d76ffbd52` (PR #348) was applied by protected Terraform plan [43033942614](https://github.com/Bepoadewale/davdeploy/actions/runs/43033942614) and apply [43034517260](https://github.com/Bepoadewale/davdeploy/actions/runs/43034517260). The plan reported 2 additions, 7 in-place changes, and 0 deletions. Apply used that exact saved plan and verified database migrations. All six Lambda functions were Active with successful updates and shared deployed `CodeSha256` `JfulBnszTNX+JkZ2iUZG31R9QYwlYbu+0Gl0jxRq8YA=`, matching the versioned control-plane artifact from that commit (S3 version `HxTxhux_5PFgg4SriG5okf4dh85FAcmY`). `/healthz` returned HTTP 200. The credential route and integration were deployed, but live flags for the broker, plan runner, plan-role verification, state API and plan reviews were all `false`. PR #349 later merged a workflow variable mapping with a `false` default; it did not change the deployed Lambda package. The dedicated versioned SSE-KMS state bucket remains provisioned, and the API Lambda has no access to Terraform state objects. PRs #333/#334 plan-history APIs, #340's bounded plan-role metadata-read/session-policy contract, and #346's paginated customer revision-history API are deployed in control-plane code. PR #344 published the versioned f3d9e1 customer plan-role template and retained the previous 7e setup URL; the protected control-plane URL points to f3d9e1. The template has not been installed for a customer, and effective customer permissions are not attested. The new #346 API was not called with an authenticated customer identity; the customer history UI has not integrated it. No Nova customer plan or workload has been applied, operated, or certified.

Current Nova source also includes the isolated CodeBuild plan boundary (#324), durable plan requests (#325), customer plan-role contract (#326), pinned initial planner (#328), remote state API and isolated-state wiring (#331–#332), tenant-scoped run history (#333–#334), the fixed customer plan-access profile (#340), paginated customer revision history (#346), the run-scoped credential broker (#348), and actual-plan hardening for IAM, SQS, Lambda invocation, and API Gateway routes (#353, #355–#356, #358–#359). PR #359's exact ownership record for untaggable API Gateway routes is now deployed. The bounded protected plan-log summary is deployed (#354). The broker API code is deployed but disabled; PR #349 exposes its protected workflow flag with a default of `false`. The state bucket is provisioned, but the state API, plan worker, role verification, credential broker and plan reviews remain disabled. The customer plan-role template allows bounded metadata reads; the control plane applies an explicit-deny session policy scoped to declared proposal resources before returning short-lived credentials to the exact active CodeBuild run. Customer role installation and effective account permissions remain unverified. Tenant-specific remote-state path isolation is not active. The initial runner remains non-approvable because complete regional pricing and exact cost-bound approval are unavailable. No Nova-generated customer plan or workload has been run, applied, health-checked, recovered, or destroyed. PR #313 closed unmerged and is superseded by #314; PR #318 pricing work remains held after being closed by the account owner.

## Hosted deployment evidence

PR #270 was deployed by Terraform apply run [41671744510](https://github.com/Bepoadewale/davdeploy/actions/runs/41671744510). The reviewed plan applied 0 creates, 7 updates and 0 destroys. The workflow reported database migrations complete. A read-only AWS query then showed `davdeploy-api` active with a successful update and the executor package pinned to commit `93c895e`. The live CodeBuild project buildspec invokes `scripts/customer-workload-dispatcher.sh`.

An unauthenticated request to `https://api.davdeploy.tech/health` returned HTTP 401. This endpoint is protected by the edge origin header and normal authorization. That probe does not establish application health; use the deployed status/health path with its required origin and auth context.

On 2026-11-03, `https://api.davdeploy.tech/healthz` returned HTTP 200 with
`{"status":"ok","product":"davdeploy"}` through the Cloudflare edge. AWS
reported `davdeploy-api` Active with LastUpdateStatus Successful; its deployed
release is now commit `2d77ee2206a425813b8169eed460aff9b5634dc2`, deployed by
Terraform plan run [41716352953](https://github.com/Bepoadewale/davdeploy/actions/runs/41716352953)
and apply run [41716835229](https://github.com/Bepoadewale/davdeploy/actions/runs/41716835229).
The plan applied 0 creates, 6 in-place Lambda package changes and 0 destroys;
database schema version 24 is deployed. PRs #277, #278 and #280 are now deployed.
PRs #283–#285 are also included in the hosted release, with the serverless
certification gate disabled and its workspace allowlist empty.

## Execution summary

| Layer | Current evidence | State |
|---|---|---|
| Natural-language planning and typed architecture catalogue | 26 `ArchitectureModule` definitions in `module_catalogue.py` | Implemented; planning inputs/pricing still include fixtures |
| Model-generated Terraform | Typed proposal and provider-schema checks; fixed initial planner; tenant plan-request/history APIs; saved-plan and approval contracts; isolated CodeBuild boundary; dedicated encrypted state storage; proposal-scoped customer plan access plus actual-plan policy hardening for IAM, SQS, Lambda invocation, API Gateway route authorization, RDS retention/final snapshots and DynamoDB point-in-time recovery (#314, #324–#334, #340, #353–#356, #358–#359, #361, #363) | #361's control-plane policy is deployed; #363 is merged source only. Hosted generation remains disabled. The current runner is non-approvable; the state API, worker, role verification and plan review are off. Customer role installation/effective permissions are unverified. Pricing is unavailable, so approval remains blocked. No customer apply, health, recovery or destroy is available on this path. |
| Internal Terraform implementation registry | 30 `ModuleImplementation` entries in `module_implementations.py` | Catalogued; entries default disabled |
| Renderer registry | `aws-managed-application` enabled; `aws-serverless-api`, `aws-file-storage` and `aws-nosql-data` disabled | One customer renderer enabled; S3 and DynamoDB renderer routes remain gated; PR #303's allowlist correction is included in the November 10 backend release |
| CodeBuild dispatcher | Fixed registry mapping; unknown, disabled, malformed, unresolved input bindings, repeated renderer types and shared Terraform state roots fail closed. PR #297 aligns adapter identity/reference fields; #298 adds dependency-ready one-node scheduling; #299 adds the gated S3 dispatch mapping; #300 adds a validated S3 bucket input for Lambda; #301 adds the gated DynamoDB dispatch route; #302 adds its `table_name` input; #303 corrects the source allowlist for that input. | #303 is deployed with renderer gates still disabled; live composed lifecycle remains unproven |
| Customer workload execution | Existing App Runner plan/apply/observe/destroy path | Controlled pilot; not a general composed engine |
| Durable module-instance outcomes | PRs #277/#278/#280 deployed; #287 adds operation-specific evidence, #289 validates serialized graphs, #290 computes dependency waves, #291 persists per-module outcomes, #293 separates type and instance identity, #294 adds typed input references, #295 validates typed outputs, #296 stores exact CodeBuild identity per module instance, #297 persists normalized renderer outputs, and #298 schedules dependency-ready work | Older rows/leases deployed by apply run [41716835229](https://github.com/Bepoadewale/davdeploy/actions/runs/41716835229); current backend code through #334 is included in apply run [42902934302](https://github.com/Bepoadewale/davdeploy/actions/runs/42902934302) |
| Worker claim and recovery | PR #280 adds conditional one-owner claims, persisted lease version/token/expiry, heartbeats, and `RECONCILIATION_REQUIRED` after uncertain outcomes | Merged as `ef60ac3` and deployed by apply run [41716835229](https://github.com/Bepoadewale/davdeploy/actions/runs/41716835229); never blindly replays an uncertain apply/destroy |
| Lambda + HTTP API | Isolated AWS HTTP 200 and teardown in `docs/test/test268.md`; PR #284 adds an allowlisted typed hosted-certification lifecycle | Hosted code path in progress; feature is off by default; no hosted AWS lifecycle evidence yet |
| Lambda project isolation | PR #275; local clean-room evidence in `docs/test/test275.md` | State, saved plans, artifact/result keys, names and tags now include connection/project scope; hosted execution remains disabled |
| Multi-module composition | Typed graph validation, operation-aware dispatch-wave selection, per-module outcomes, typed references, exact CodeBuild callback identity, safe renderer output mapping, durable one-ready-node scheduling, gated S3/DynamoDB renderers, and S3/DynamoDB inputs to Lambda are merged | PRs through #303 are deployed; repeated renderer state isolation and composed AWS workload evidence remain absent |
| Browser, CLI and MCP lifecycle parity | Shared plan/history APIs exist. Frontend PR #102 locally presents paginated plan history and latest Nova run status, but remains draft/unmerged/unreleased and does not provide authenticated production or lifecycle completion evidence. | Partial; CLI/MCP parity, hosted customer plan status and apply/health/recovery/destroy journey remain unproven |
| Eight certification scenarios | Scenario catalogue, plan-only Terraform runner and selected isolated AWS service tests | None proves the Nova hosted customer lifecycle. Real composed application create/invoke/observe/update/failure recovery/destroy/independent absence remains outstanding |

## Architecture catalogue (26)

The stage reflects the planner catalogue, not an execution entitlement. Except for `aws-managed-application`, no entry is an enabled hosted renderer through CodeBuild.

| Module | Catalogue stage | Hosted renderer / evidence |
|---|---|---|
| `aws-observability` | catalogued | No module renderer |
| `aws-secrets-config` | catalogued | No module renderer |
| `aws-edge-https` | planning | No module renderer |
| `aws-static-web` | planning | No module renderer |
| `aws-serverless-api` | planning | Isolated renderer certified; hosted execution disabled |
| `aws-managed-application` | pilot | Enabled App Runner renderer; per-workload evidence still required |
| `aws-container-service` | planning | No module renderer |
| `aws-virtual-machine-service` | planning | No module renderer |
| `aws-kubernetes-platform` | planning | No module renderer |
| `aws-identity` | catalogued | No module renderer |
| `aws-relational-data` | catalogued | No module renderer |
| `aws-nosql-data` | catalogued | PR #301 adds a gated DynamoDB renderer; PR #302 adds its typed API input; PR #303's dispatcher allowlist fix is deployed; no hosted AWS lifecycle evidence |
| `aws-file-storage` | catalogued | PR #299 adds a gated private S3 renderer; no AWS lifecycle evidence |
| `aws-jobs-events` | catalogued | No module renderer |
| `aws-realtime` | catalogued | No module renderer |
| `aws-search` | catalogued | No module renderer |
| `aws-payments-webhooks` | catalogued | No module renderer; third-party payment integration needs provider setup |
| `aws-ai-retrieval` | planning | No customer renderer; underlying service certification is not composed execution |
| `aws-managed-ml` | catalogued | No customer renderer; underlying service certification is not composed execution |
| `aws-cpu-inference` | planning | No module renderer |
| `aws-gpu-inference` | planning | No module renderer |
| `aws-data-analytics` | catalogued | No module renderer |
| `aws-stream-processing` | catalogued | No module renderer |
| `aws-media` | catalogued | No module renderer |
| `aws-private-connectivity` | catalogued | No module renderer |
| `aws-backup-recovery` | catalogued | No module renderer |

## Terraform implementation registry (30)

These entries identify resource roots or module paths. None is automatically a complete customer lifecycle renderer. Underlying real AWS test evidence is recorded in the individual `docs/test/` files and does not prove hosted orchestration.

| Implementation | Terraform path | Hosted lifecycle |
|---|---|---|
| `aws-dns-zone` | `modules/dns-zone` | none |
| `aws-acm-certificate` | `modules/acm-certificate` | none |
| `aws-kms-key` | `modules/kms-key` | none |
| `aws-parameter-config` | `modules/parameter-config` | none |
| `aws-feature-flags` | `modules/feature-flags` | none |
| `aws-s3-private-storage` | `modules/artifacts` | none |
| `aws-cloudfront-delivery` | `modules/cloudfront-delivery` | none |
| `aws-api-gateway-http` | `modules/api-gateway-http` | none |
| `aws-lambda-service` | `modules/lambda-service` | none |
| `aws-ecr-image` | `modules/ecr` | none |
| `aws-aurora-postgres` | `modules/aurora-postgres` | none |
| `aws-dynamodb-table` | `modules/dynamodb-table` | none |
| `aws-elasticache-redis` | `modules/elasticache-redis` | none |
| `aws-opensearch` | `modules/opensearch` | none |
| `aws-efs-shared-storage` | `modules/efs-shared-storage` | none |
| `aws-sqs-queue` | `modules/sqs-queue` | none |
| `aws-eventbridge-bus` | `modules/eventbridge-bus` | none |
| `aws-step-functions` | `modules/step-functions` | none |
| `aws-sns-notifications` | `modules/sns-notifications` | none |
| `aws-ses-email` | `modules/ses-email` | none |
| `aws-bedrock-runtime` | `modules/bedrock-runtime` | none |
| `aws-bedrock-knowledge-base` | `modules/bedrock-knowledge-base` | none |
| `aws-sagemaker-endpoint` | `modules/sagemaker-endpoint` | none |
| `aws-kinesis-stream` | `modules/kinesis-stream` | none |
| `aws-batch-compute` | `modules/batch-compute` | none |
| `aws-eks-cluster` | `modules/eks` | none |
| `aws-ec2-autoscaling` | `modules/ec2-autoscaling` | none |
| `aws-vpc-private-network` | `modules/vpc` | none |
| `aws-site-to-site-vpn` | `modules/site-to-site-vpn` | none |
| `aws-multi-region-dns` | `modules/multi-region-dns` | none |

## Legacy renderer compatibility context

The standalone `infrastructure/terraform/customer-workload-serverless-api` root has isolated AWS evidence, but its `aws-serverless-api` renderer is disabled for ordinary hosted customer execution. PR #275 adds project isolation; PR #284 adds a certification-only API lifecycle guarded by a disabled-by-default flag and explicit workspace allowlist. It remains unproven in hosted AWS. PR #299 adds a separately gated private S3 renderer; it is not customer-enabled and has no real AWS lifecycle evidence. PR #300 adds a single typed S3 bucket-name input and scoped Lambda policy, but it does not enable customer execution. PR #301 adds a gated DynamoDB renderer; PR #302 adds the table-to-API binding; PR #303's dispatcher allowlist correction is deployed. App Runner remains the only generally enabled customer renderer. No hosted AWS lifecycle evidence exists for these gated renderers.

## Active Nova-led work that remains

1. Install and verify the versioned plan-role template in a disposable/customer account; keep role trust/account verification separate from effective-permission claims. PR #340 adds the bounded metadata profile and proposal-scoped session policy, but hosted role verification is disabled and customer installation is not evidenced.
2. Inject tenant-scoped remote state through the isolated state API and plan worker, with locking, verified identity and artifact boundaries; current infrastructure storage exists, but runtime access and worker dispatch remain disabled.
3. Integrate complete, trusted, region-specific pricing and usage assumptions before exact-plan approval. PR #318 remains held for account-owner direction; do not replace that work without direction.
4. Safely enable and prove hosted Nova planning end to end, including Nova generation, validation, saved plan, plan history and useful failure reporting.
5. Add separately authorized apply of the exact approved saved plan, with durable identity, leases, idempotency, restart reconciliation, bounded retries and exact state/artifact scoping.
6. Add deterministic health probes, update and failure recovery, data-recovery evidence, exact destroy and independent absence checks.
7. Run composed application scenarios through the hosted Nova path and align browser, CLI and MCP with the same lifecycle. Existing isolated AWS tests are reusable evidence, not proof of hosted customer execution.

See `docs/test/test268.md` and `docs/tickets/ticket270.md` for legacy pilot evidence and boundaries.

The technical PR evidence is recorded in PR tickets and `docs/test/` files; latest state-storage rollout evidence is in `docs/tickets/ticket337.md`, `docs/test/test337.md`, `docs/tickets/ticket338.md`, and `docs/test/test338.md`.
