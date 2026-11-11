# test338

Date: 2026-11-11
Execution type: Local automated and Terraform validation plus post-merge protected control-plane Terraform plan/apply. No customer workload was created.
Customer repository: Not applicable; control-plane Terraform IAM conditions only.
PR implementation head: `2ce0fa045efcfca55ba7da82a01535d7ed82a8f1`; merged as `5af94dbc413a82f4d8965467a5064f16020f05d3`.
Commit: `5af94dbc413a82f4d8965467a5064f16020f05d3` (merged backend main).
AWS account: `654654474502`.
AWS region: `us-east-1`

## Resources created

The merged storage-only rollout created `davdeploy-tfstate-654654474502-us-east-1`, bucket controls, and `alias/davdeploy-nova-terraform-state` targeting existing KMS key `bff87a70-bd0d-4336-ad64-5a1b49937be9`. It changed six control-plane Lambda packages/configurations in place. No customer workload, customer state bucket, or customer infrastructure was created.

## Commands executed

- `.venv/bin/python -m pytest tests/test_nova_plan_only_infra.py -q` — 10 passed.
- `.venv/bin/ruff check tests/test_nova_plan_only_infra.py` — passed.
- `terraform fmt -check -recursive infrastructure/terraform/serverless-control-plane` — passed.
- `terraform -chdir=infrastructure/terraform/serverless-control-plane validate` — passed.
- `make verify` — 867 passed; ruff, OpenAPI, Actions configuration, and Compose configuration checks passed. One existing Starlette/httpx deprecation warning remains.
- `python3.12 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- `COMPOSE_PROJECT_NAME=davdeploy_pr338_20261111 make local-proof` in `/private/tmp/davdeploy-pr338-cleanroom-20261111` — passed (867 tests), with API/worker/executor/monitoring health, local customer-plan E2E, trace checks, OpenAPI, Actions and Compose checks passing.
- `COMPOSE_PROJECT_NAME=davdeploy_pr338_20261111 make clean-local` — removed the isolated stack, volume, network, `.venv`, and `.local`; follow-up absence checks pending.

## Observed result

The storage flag no longer grants API Lambda S3 state-object or KMS permissions by itself. Those permissions require both storage and state API flags; the HTTP state API route and its independent gates remain off in the reviewed storage-only configuration. The plan from run `42955035771` was not applied because it included the prior access coupling; no AWS resources changed. All seven required CI checks passed for the merged PR head in [run 42956841361](https://github.com/Bepoadewale/davdeploy/actions/runs/42956841361).

The fresh reviewed plan [42957384890](https://github.com/Bepoadewale/davdeploy/actions/runs/42957384890) completed successfully and was applied exactly by [42958408176](https://github.com/Bepoadewale/davdeploy/actions/runs/42958408176): 7 creates, 6 in-place updates, 0 destroys. Read-only checks observed versioning, SSE-KMS, bucket keys, owner-enforced ownership, four public-access blocks, and an insecure-transport deny. All six Lambda functions in scope were Active with successful updates. The Nova state API, runner, plan-role verification, and plan review remained disabled; the API Lambda policy had no state-bucket access. `/healthz` returned `{"status":"ok","product":"davdeploy"}`.

## Teardown

The isolated clean-room stack was removed with `make clean-local`; its follow-up absence checks initially remained pending in the earlier test record. A read-only check during this documentation update confirmed the named Docker containers, network, volume, `.venv`, and `.local` are absent. The dedicated encrypted control-plane state bucket and alias are retained as infrastructure for later gated work, not temporary test resources.

## Final boundary

The earlier plan [42955035771](https://github.com/Bepoadewale/davdeploy/actions/runs/42955035771) was not applied because it granted state-object/KMS access while the state API was disabled. The corrected merged plan and exact apply are recorded above. This rollout provisions storage only: it does not enable hosted planning, customer approval, apply, health monitoring, recovery, or teardown.
