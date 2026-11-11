# test337

Date: 2026-11-11
Execution type: Local validation, isolated local clean-room, and protected control-plane Terraform rollout. No customer workload was created.
Customer repository: Not applicable; this PR updates control-plane Terraform apply permissions.
PR implementation head: `e60aa0f1f6bac6580c525a99c1fd032ff34f9df9`; merged as `4e087724a86839893994354321dadff1c60df336`.
Commit: `4e087724a86839893994354321dadff1c60df336` (merged backend main).
AWS account: `654654474502`.
AWS region: `us-east-1`

## Resources created

The protected control-plane rollout created the dedicated state bucket `davdeploy-tfstate-654654474502-us-east-1`, bucket controls, and alias `alias/davdeploy-nova-terraform-state` targeting existing KMS key `bff87a70-bd0d-4336-ad64-5a1b49937be9`. The operations-bootstrap apply updated two IAM policies. This was DavDeploy control-plane storage setup, not a customer workload. The failed earlier apply and its partial changes remain historical; its saved plan was not replayed.

## Commands executed

- `.venv/bin/python -m pytest tests/test_terraform_operations_bootstrap.py -q` — 7 passed.
- `.venv/bin/ruff check tests/test_terraform_operations_bootstrap.py` — passed.
- `terraform fmt -check -recursive infrastructure/terraform/terraform-operations-bootstrap` — passed.
- `terraform -chdir=infrastructure/terraform/terraform-operations-bootstrap validate` — passed.
- `make verify` — 867 passed; ruff, OpenAPI check, Actions configuration check, and Compose configuration check passed. One existing Starlette/httpx deprecation warning remains.
- `git diff --check` — passed.
- `COMPOSE_PROJECT_NAME=davdeploy_pr337_20261111 make local-proof` in `/private/tmp/davdeploy-pr337-cleanroom-20261111` — passed (867 tests); isolated Compose config check passed.
- `COMPOSE_PROJECT_NAME=davdeploy_pr337_20261111 make clean-local` — removed only PR #337 clean-room containers, network, volume, `.venv`, and `.local`; follow-up checks found all absent.

## Observed result

Focused and full local verification passed. All seven required checks passed in [run 42953078494](https://github.com/Bepoadewale/davdeploy/actions/runs/42953078494) for PR #337's final head. The earlier docs-convention failure was corrected before that run.

The scoped operations-bootstrap permission rollout completed under monitor run `nova-state-permissions-20261111-ops-bootstrap-retry1`; the first attempt failed before AWS changes because Terraform versions did not match the saved plan. A fresh serverless plan from merged PR #338, run [42957384890](https://github.com/Bepoadewale/davdeploy/actions/runs/42957384890), was applied exactly by run [42958408176](https://github.com/Bepoadewale/davdeploy/actions/runs/42958408176). It reported 7 creates, 6 in-place Lambda package/version updates, and 0 destroys. A preceding plan [42955035771](https://github.com/Bepoadewale/davdeploy/actions/runs/42955035771) was deliberately not applied because it granted API state-object/KMS permissions while the state API was disabled.

Read-only post-apply checks confirmed S3 versioning enabled, SSE-KMS with the dedicated key and bucket keys, BucketOwnerEnforced, all four public-access blocks enabled, and a policy denying insecure transport. The alias points to the existing tagged state key. All six Lambda functions in scope were Active with successful updates; the API state API, runner, role-verification, and plan-review flags remained false. The API Lambda policy had no access to the state bucket. `https://api.davdeploy.tech/healthz` returned the expected healthy response. No customer AWS workload or customer state was created.

## Teardown

The isolated test stack was stopped and removed with `make clean-local`; the run-specific Docker objects, generated clean-room files, `.venv`, and `.local` were confirmed absent. No pre-existing shared test stack was removed.

## Final boundary

No customer workload, customer plan worker, Nova state API, plan review, plan-role verification, or customer apply was enabled. The API health check and infrastructure controls do not establish hosted customer planning or deployment readiness.
