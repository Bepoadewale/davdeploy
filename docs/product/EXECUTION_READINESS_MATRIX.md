# Execution readiness matrix

Audit as of 2026-11-04, backend main commit `9d14bd1` (PR #296). The latest hosted AWS release is commit `2e39e4a` after PR #285, applied by run [41730396958](https://github.com/Bepoadewale/davdeploy/actions/runs/41730396958). PRs #289–#296 are merged code-only foundations and are not deployed or connected to the worker.

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
| Internal Terraform implementation registry | 30 `ModuleImplementation` entries in `module_implementations.py` | Catalogued; entries default disabled |
| Renderer registry | `aws-managed-application` enabled; `aws-serverless-api` disabled | One customer renderer enabled |
| CodeBuild dispatcher | Fixed registry mapping; unknown, disabled, malformed, unresolved dependency-bearing and multi-item work fail closed. Draft PR #297 aligns the dispatcher schema with adapter identity/reference fields. | Current hosted dispatcher is deployed; schema alignment remains unmerged and undeployed |
| Customer workload execution | Existing App Runner plan/apply/observe/destroy path | Controlled pilot; not a general composed engine |
| Durable module-instance outcomes | PRs #277/#278/#280 deployed; #287 adds operation-specific evidence, #289 validates serialized graphs, #290 computes dependency waves, #291 persists per-module outcomes, #293 separates type and instance identity, #294 adds typed input references, #295 validates typed outputs, and #296 stores exact CodeBuild identity per module instance | Older rows/leases deployed by apply run [41716835229](https://github.com/Bepoadewale/davdeploy/actions/runs/41716835229); #287–#296 are merged code foundations not wired into hosted scheduling |
| Worker claim and recovery | PR #280 adds conditional one-owner claims, persisted lease version/token/expiry, heartbeats, and `RECONCILIATION_REQUIRED` after uncertain outcomes | Merged as `ef60ac3` and deployed by apply run [41716835229](https://github.com/Bepoadewale/davdeploy/actions/runs/41716835229); never blindly replays an uncertain apply/destroy |
| Lambda + HTTP API | Isolated AWS HTTP 200 and teardown in `docs/test/test268.md`; PR #284 adds an allowlisted typed hosted-certification lifecycle | Hosted code path in progress; feature is off by default; no hosted AWS lifecycle evidence yet |
| Lambda project isolation | PR #275; local clean-room evidence in `docs/test/test275.md` | State, saved plans, artifact/result keys, names and tags now include connection/project scope; hosted execution remains disabled |
| Multi-module composition | Typed graph validation, operation-aware dispatch-wave selection, per-module outcomes, typed references, and exact CodeBuild callback identity exist; PR #297 maps Lambda/API Terraform output JSON into typed module outputs and aligns the runner schema | Local foundations only; CodeBuild still rejects runs with more than one module, and the worker does not yet claim dependency waves |
| Browser, CLI and MCP lifecycle parity | shared APIs exist, but frontend uses App Runner-specific modes and confirmation | Partial |
| Eight certification scenarios | test scenario catalogue plus bounded Terraform runner | Service roots exist; not all real application scenarios exercise hosted customer runner, update, recovery and absence |

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
| `aws-nosql-data` | catalogued | No module renderer |
| `aws-file-storage` | catalogued | No module renderer |
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

The standalone `infrastructure/terraform/customer-workload-serverless-api` root has isolated AWS evidence, but its `aws-serverless-api` renderer is disabled for ordinary hosted customer execution. PR #275 adds project isolation; PR #284 adds a certification-only API lifecycle guarded by a disabled-by-default flag and explicit workspace allowlist. It remains unproven in hosted AWS. App Runner is currently the only enabled customer renderer.

## Work that remains

1. Complete PR #297's typed renderer-output persistence and callback validation. Then wire dispatch-wave selection and per-module outcome persistence into the worker using conditional module claims and one durable build/result identity per dispatched module.
2. Add typed output binding between modules, authenticated reconciliation for stale CodeBuild/SQS outcomes, bounded safe retries, partial-failure compensation and reverse cleanup.
3. Integrate the Lambda/API renderer through the hosted CodeBuild path and prove real traffic, health, update, recovery, destroy and independently verified absence before enabling it.
4. Replace the App Runner-only service gate and single-module CodeBuild limitation as each renderer family is actually certified.
5. Add hosted renderer families in the active execution-goal order; do not equate standalone service tests with composed renderer certification.
6. Extend the scenario harness to exercise composed applications through the hosted runner, including traffic, update/recovery and absence verification.
7. Replace fixture pricing/inventory with timestamped provider data, and align browser, CLI and MCP with the same authorized lifecycle.
8. Run the final hosted browser, CLI and MCP acceptance journey and reconcile closeout evidence.

See `docs/test/test268.md`, `docs/tickets/ticket270.md`, and the active goal handoff for detailed evidence and boundaries.

The step-by-step goal status and next actions are in
[`COMPOSED_EXECUTION_GOAL.md`](COMPOSED_EXECUTION_GOAL.md).
