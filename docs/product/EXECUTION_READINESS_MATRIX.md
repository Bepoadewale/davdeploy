# Execution readiness matrix

Audit as of 2026-11-03, backend main commit `93c895e6e40e80f20b71a6f3a21e3186ca63d576`.

## Hosted deployment evidence

PR #270 was deployed by Terraform apply run [41671744510](https://github.com/Bepoadewale/davdeploy/actions/runs/41671744510). The reviewed plan applied 0 creates, 7 updates and 0 destroys. The workflow reported database migrations complete. A read-only AWS query then showed `davdeploy-api` active with a successful update and the executor package pinned to commit `93c895e`. The live CodeBuild project buildspec invokes `scripts/customer-workload-dispatcher.sh`.

An unauthenticated request to `https://api.davdeploy.tech/health` returned HTTP 401. This endpoint is protected by the edge origin header and normal authorization. That probe does not establish application health; use the deployed status/health path with its required origin and auth context.

## Execution summary

| Layer | Current evidence | State |
|---|---|---|
| Natural-language planning and typed architecture catalogue | 26 `ArchitectureModule` definitions in `module_catalogue.py` | Implemented; planning inputs/pricing still include fixtures |
| Internal Terraform implementation registry | 30 `ModuleImplementation` entries in `module_implementations.py` | Catalogued; entries default disabled |
| Renderer registry | `aws-managed-application` enabled; `aws-serverless-api` disabled | One customer renderer enabled |
| CodeBuild dispatcher | One typed item; fixed registry mapping; unknown, disabled, malformed, dependency-bearing and multi-item work fail closed | Deployed |
| Customer workload execution | Existing App Runner plan/apply/observe/destroy path | Controlled pilot; not a general composed engine |
| Lambda + HTTP API | Isolated AWS HTTP 200 and teardown in `docs/test/test268.md` | Isolated AWS certified; hosted execution disabled |
| Multi-module composition | typed graph and dependency ordering helpers exist; CodeBuild rejects runs with more than one module | Not implemented as durable hosted orchestration |
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

The standalone `infrastructure/terraform/customer-workload-serverless-api` root has isolated AWS evidence, but its `aws-serverless-api` renderer is disabled in the hosted registry. App Runner is currently the only registered hosted renderer.

## Work that remains

1. Implement durable hosted deployment/module-instance state, locking, idempotency, retries/resume, dependency inputs/outputs, partial-failure recovery, output redaction and independent cleanup verification.
2. Replace the App Runner-only service gate and single-module CodeBuild limitation with graph orchestration that resolves each module to a checked-in renderer. Do not add arbitrary scripts, roots or Terraform input.
3. Integrate the Lambda/API renderer through the actual customer CodeBuild path; run hosted apply, real HTTP traffic, observations, update, intentional recovery, destroy and independently verified absence before enabling it.
4. Add hosted renderer families in the order in the active execution-engine goal: storage/data/queues; static web and edge; containers/VM; relational and cache; async; search/analytics/streaming; AI/ML; Kubernetes/networking/multi-region.
5. Turn the certification scenarios into hosted application tests that prove behavior, update/recovery and teardown, not only Terraform resource creation.
6. Replace fixture pricing/inventory with timestamped provider data and customer-approved discovery, and ensure the built artifact matches the reviewed repository commit.
7. Align frontend, CLI and MCP flows with the same provider-neutral API lifecycle and truthful observed evidence.
8. Run the final browser, CLI and MCP AWS acceptance journey and reconcile status docs from its results.

See `docs/test/test268.md`, `docs/tickets/ticket270.md`, and the active goal handoff for detailed evidence and boundaries.
