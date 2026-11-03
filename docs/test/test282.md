# test282 — Deploy durable worker claims to hosted control plane

Date: 2026-11-03

Execution type: Protected production control-plane Terraform apply.

Customer repository: None. No customer workload was deployed.

Commit: `2d77ee2206a425813b8169eed460aff9b5634dc2` (PR #281 documentation merge).

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

No resources were created or destroyed. Terraform updated six Lambda code
packages in place: `davdeploy-api`, `davdeploy-worker`, `davdeploy-migrate`,
`davdeploy-policy`, `davdeploy-cognito-link`, and
`davdeploy-cognito-email-sender`. All six reported the same release code hash.

## Commands executed

- `gh workflow run terraform-plan.yml --ref main -f confirmation=PLAN_SERVERLESS_CONTROL_PLANE`
  — plan run [41716352953](https://github.com/Bepoadewale/davdeploy/actions/runs/41716352953)
  passed.
- `gh workflow run terraform-apply.yml --ref main -f confirmation=APPLY_SAVED_SERVERLESS_PLAN`
  — apply run [41716835229](https://github.com/Bepoadewale/davdeploy/actions/runs/41716835229)
  passed after approval of the protected `terraform-apply` environment.
- Terraform result: 0 added, 6 changed, 0 destroyed.
- Workflow migration check: completed successfully.
- Read-only RDS Data API query:
  `SELECT MAX(version) AS schema_version FROM schema_migrations` — returned 24.
- Read-only AWS Lambda listing: all six package hashes matched; Lambda functions
  were active with successful updates.
- `curl -fsS https://api.davdeploy.tech/healthz` — returned
  `{"status":"ok","product":"davdeploy"}`.

## Observed result

PRs #277, #278 and #280 are deployed in the control-plane package, and the
database is at schema version 24. The existing customer execution boundary did
not change: App Runner remains the only enabled hosted renderer; the Lambda/API
renderer remains disabled; multi-module runs remain rejected.

## Teardown

None required. The apply created and destroyed no resources and did not run a
customer workload.

## Final boundary

This verifies deployed worker-lease and single-renderer outcome persistence. It
does not certify a multi-module graph scheduler or enable arbitrary customer
deployments.
