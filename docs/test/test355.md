# test355 — protected control-plane release for PR #355

Date: 2026-11-11
Execution type: Real AWS control-plane Terraform saved-plan apply; no customer workload.
Customer repository: Not applicable; this was DavDeploy's control-plane release, not a customer workload repository.
Commit: `6e60da0075e22092c0b5278d68bb592114f21f61`
AWS account: `654654474502`
AWS region: `us-east-1`

## Resources created

No customer AWS resources, roles, or workloads were created. The protected
release updated six existing control-plane Lambda functions in place and
published the versioned control-plane package and saved-plan artifact.

## Commands executed

- Dispatched `.github/workflows/terraform-plan.yml` with
  `PLAN_SERVERLESS_CONTROL_PLANE` for exact merged `main` commit `6e60da0`.
- Reviewed the plan's bounded hosted summary before applying it.
- Dispatched `.github/workflows/terraform-apply.yml` with
  `APPLY_SAVED_SERVERLESS_PLAN` for the exact successful saved-plan run.
- Approved the `terraform-apply` environment under the user's standing
  automatic-approval instruction after reviewing the summary.
- `aws sts get-caller-identity --profile ai-platform-pilot-key`
- Read-only Lambda configuration checks selected state, update status, package
  digest and allowlisted Nova safety flags; no other environment values were
  emitted.
- `curl -fsS --max-time 20 https://api.davdeploy.tech/healthz`

## Observed result

The plan was applyable and complete: zero additions, six in-place Lambda
updates, zero destroys, zero drift, and eight output changes. The six updates
were control-plane package/environment changes. Nova plan runner, customer
role verification, credential broker, plan review, Terraform state and hosted
certification flags remained false. The protected workflow verified the
source commit, selected plan run, manifest, and saved-plan digest before
Terraform applied the exact saved plan. Database migration verification
passed.

- Plan workflow: [run 43078429737](https://github.com/Bepoadewale/davdeploy/actions/runs/43078429737)
- Saved-plan manifest SHA-256: `87eb2d74b4beae068b756e68e2497211c7beb9df7cf57c9ffa23ced67204cb9a`
- Apply workflow: [run 43079436769](https://github.com/Bepoadewale/davdeploy/actions/runs/43079436769)
- Deployment: `7718460093`
- All six functions (`davdeploy-api`, `davdeploy-worker`, `davdeploy-migrate`,
  `davdeploy-policy`, `davdeploy-cognito-link`, and
  `davdeploy-cognito-email-sender`) are `Active` with
  `LastUpdateStatus=Successful`.
- All six report `CodeSha256=YLhr0Q+LtKnufa3IyfAYdDTVxDIP9iPoSoww1J9QJ0s=`.
- `GET https://api.davdeploy.tech/healthz` returned
  `{"status":"ok","product":"davdeploy"}`.
- Read-only configuration confirms all Nova saved-plan/runtime feature flags
  remain false or absent; legacy cloud-execution flags do not enable Nova
  execution.

## Teardown

No disposable customer resources were created, so customer teardown did not
apply. Versioned control-plane plan/package artifacts remain as release
evidence.

## Final boundary

This was a control-plane release only. It deployed the actual-plan SQS
wildcard/`NotPrincipal` policy check from PR #355 and the sanitized Terraform
plan log workflow from PR #354. No customer AWS role, workload, or resource
was created, changed, or destroyed. No Nova-generated customer plan has been
applied, operated, or certified. Regional pricing and exact cost-bound
approval remain unavailable; hosted customer health, recovery, and teardown
remain unproven.
