# test356 — protected control-plane release for PR #356

Date: 2026-11-11
Execution type: Real AWS control-plane Terraform saved-plan apply; no customer workload.
Customer repository: Not applicable; this was DavDeploy's control-plane release, not a customer workload repository.
Commit: `11e66e878933a69638128a8bab80115c051d230a`
AWS account: `654654474502`
AWS region: `us-east-1`

## Resources created

No customer AWS resources, roles, or workloads were created. The protected
release updated six existing control-plane Lambda functions in place and
published the versioned control-plane package and saved-plan artifact.

## Commands executed

- Dispatched `.github/workflows/terraform-plan.yml` with
  `PLAN_SERVERLESS_CONTROL_PLANE` for exact merged `main` commit `11e66e8`.
- Reviewed the bounded hosted plan summary before applying.
- Dispatched `.github/workflows/terraform-apply.yml` with
  `APPLY_SAVED_SERVERLESS_PLAN` for the exact successful saved-plan run.
- Approved the `terraform-apply` environment under the user's standing
  automatic-approval instruction after reviewing the saved-plan summary.
- `aws sts get-caller-identity --profile ai-platform-pilot-key`
- Read-only Lambda configuration checks selected state, update status, package
  digest and allowlisted Nova safety flags; other environment values were not
  emitted.
- `curl -fsS --max-time 20 https://api.davdeploy.tech/healthz`

## Observed result

The plan was applyable and complete: zero additions, six in-place Lambda
updates, zero destroys, zero drift, and eight output changes. The protected
workflow verified the source commit, selected plan run, manifest and saved
plan digest before applying. Database migration verification passed.

- Plan workflow: [run 43081890092](https://github.com/Bepoadewale/davdeploy/actions/runs/43081890092)
- Saved-plan manifest SHA-256: `e6b6babaa01f0e4ebcf2b30023231e47e45f2edc2c142ff71a905bcc005efecf`
- Apply workflow: [run 43082767507](https://github.com/Bepoadewale/davdeploy/actions/runs/43082767507)
- Deployment: `7718925708`
- All six functions (`davdeploy-api`, `davdeploy-worker`, `davdeploy-migrate`,
  `davdeploy-policy`, `davdeploy-cognito-link`, and
  `davdeploy-cognito-email-sender`) are `Active` with
  `LastUpdateStatus=Successful`.
- All six report `CodeSha256=qdnufg4s7uxN9qJyxhyWs8rD/GXgt+PzXeKlKLYyt3g=`.
- `GET https://api.davdeploy.tech/healthz` returned
  `{"status":"ok","product":"davdeploy"}`.
- Nova plan runner, role verification, credential broker, plan review, state
  and hosted certification gates remain false or absent.

## Teardown

No disposable customer resources were created, so customer teardown did not
apply. Versioned control-plane plan/package artifacts remain as release
evidence.

## Final boundary

This was a control-plane release only. PR #356's Lambda invocation-policy
checks are deployed, alongside the sanitized Terraform plan logging from
PR #354 and public SQS policy checks from PR #355. No customer AWS role,
workload, or resource was created, changed, or destroyed. No Nova-generated
customer plan has been applied, operated, or certified. Exact regional
pricing and cost-bound approval, customer plan-role installation/effective
permission evidence, hosted customer health, recovery and teardown remain
incomplete.
