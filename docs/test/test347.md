# test347 — deployed customer plan history evidence

PR: [#347](https://github.com/Bepoadewale/davdeploy/pull/347)

Date: 2026-11-11
Execution type: Documentation evidence reconciliation; references prior protected production release
Customer repository: `Bepoadewale/davdeploy`
Commit: pending documentation commit
AWS account: `654654474502` (read-only post-apply checks from PR #346 release)
AWS region: `us-east-1`

## Resources created

PR #347 creates no resources. Its documentation records PR #346's verified
control-plane release: six Lambda functions updated in place, no additions or
destroys, and no customer workload resources.

## Commands executed

- `python3.12 scripts/check_doc_conventions.py`
- `git diff --check`
- `curl -fsS https://api.davdeploy.tech/healthz`
- `curl -fsS https://api.davdeploy.tech/openapi.json | python3.12 -c '…'` (HTTP 401; no authenticated route check)
- AWS Lambda `get-function-configuration` read-only queries for the six deployed functions.
- GitHub Actions Terraform plan run [42992799853](https://github.com/Bepoadewale/davdeploy/actions/runs/42992799853) and apply run [42993697793](https://github.com/Bepoadewale/davdeploy/actions/runs/42993697793) are the deployment evidence being documented, not operations performed by this PR.

## Observed result

The API health check returned HTTP 200. All six Lambda functions were Active
with `LastUpdateStatus=Successful`. The apply workflow verified database
migrations. Unauthenticated access to `openapi.json` returned HTTP 401, so an
authenticated customer request to the new history endpoint is not claimed.
No Nova customer workload was applied, operated, or destroyed.

## Teardown

No resources were created by PR #347; no teardown was required.

## Final boundary

This is deployment and documentation evidence for the backend history API.
The frontend has not integrated the endpoint, and the customer lifecycle still
lacks cost-bound approval, apply, application health, recovery, and teardown
certification.
