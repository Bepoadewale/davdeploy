# test353 — protected control-plane release for PR #353

Date: 2026-11-11
Execution type: Real AWS control-plane Terraform saved-plan apply; no customer workload.
Customer repository: Not applicable; this was DavDeploy's control-plane release, not a customer workload repository.
Commit: `0896ae6106fe1e7526dba90105639f894d5534b8`
AWS account: `654654474502`
AWS region: `us-east-1`

## Resources created

No customer AWS resources, roles, or workloads were created. The control-plane
release updated six existing Lambda functions in place and published the
versioned control-plane package and saved-plan artifact required by the
protected workflow.

## Commands executed

- Dispatched `.github/workflows/terraform-plan.yml` with
  `PLAN_SERVERLESS_CONTROL_PLANE` for the exact merged `main` commit.
- Dispatched `.github/workflows/terraform-apply.yml` with
  `APPLY_SAVED_SERVERLESS_PLAN` for the exact successful saved-plan run.
- Approved the `terraform-apply` environment using the user's standing
  automatic-approval instruction after reviewing the saved-plan summary.
- `aws sts get-caller-identity --profile ai-platform-pilot-key`
- Read-only `aws lambda get-function-configuration` checks for all six
  control-plane functions, selecting only state, update status, code digest,
  and explicit feature-gate booleans.
- `curl --fail --silent --show-error https://api.davdeploy.tech/healthz`

## Observed result

The reviewed plan updated six Lambda functions in place with zero additions
and zero destroys. The protected apply completed successfully and its database
migration step passed. The apply workflow verified the source commit, exact
plan run, manifest, and saved-plan digest before applying. AWS identity
confirmed account `654654474502` in `us-east-1`.

- Plan workflow: [run 43067874795](https://github.com/Bepoadewale/davdeploy/actions/runs/43067874795)
- Saved-plan manifest SHA-256: `534d53f8a25efaa3ff24f84cbafbadb916688f6c1b0f012cb18737429d811814`
- Apply workflow: [run 43071712182](https://github.com/Bepoadewale/davdeploy/actions/runs/43071712182)
- Deployment: `7717369668`
- All six functions (`davdeploy-api`, `davdeploy-worker`, `davdeploy-migrate`,
  `davdeploy-policy`, `davdeploy-cognito-link`, and
  `davdeploy-cognito-email-sender`) are `Active` with
  `LastUpdateStatus=Successful`.
- All six report `CodeSha256=AYMfASSOQwXh35Mn64rq4qFKnJAXb53JrlIXE0G8+bg=`.
- `GET https://api.davdeploy.tech/healthz` returned
  `{"status":"ok","product":"davdeploy"}`.
- Read-only function configuration checks show Nova plan runner readiness,
  plan-role verification, credential brokerage, plan review, Terraform state
  API, and hosted certification are all `false`. Existing legacy cloud
  execution command/plan/apply flags remain `true`; they do not enable the
  Nova saved-plan path.

## Teardown

No disposable customer resources were created, so no customer teardown was
applicable. Versioned control-plane plan/package artifacts were retained as
release evidence.

## Final boundary

This was a control-plane release only. No customer AWS account role, workload,
or customer resource was created, changed, or destroyed. No Nova-generated
customer plan was applied. Regional pricing and exact cost-bound approval
remain unavailable; hosted customer health, update/recovery, and teardown
remain unproven. Runtime configuration values are not included beyond the
explicit boolean safety flags recorded above.
