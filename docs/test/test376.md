# test376 — deploy merged Nova planning policy and RDS metadata boundaries

Date: 2026-11-12  
Execution type: Protected serverless control-plane Terraform saved-plan apply and read-only post-release verification  
Customer repository: N/A; no customer repository or workload was used  
Backend source: `7722ea339fd03dd6c137d28b5702b67bc5c42671`  
Commit: `7722ea339fd03dd6c137d28b5702b67bc5c42671`  
Terraform root: `infrastructure/terraform/serverless-control-plane`  
AWS account: `654654474502`  
AWS region: `us-east-1`

## Purpose

Deploy the exact merged backend source after PR #375. This releases the merged
RDS planner metadata boundary (#371–#372) and fail-closed denial for unbound
Secrets Manager value reads (#374). It does not enable hosted customer
planning, approval, apply, or workload execution.

## Protected release evidence

- Protected plan [43166003130](https://github.com/Bepoadewale/davdeploy/actions/runs/43166003130)
  succeeded for the exact backend source commit above.
- Sanitized plan summary: complete/applyable, no errors; 0 additions, 6
  in-place Lambda package updates, 0 destroys/replacements, one reported drift
  item, and 8 output changes.
- Drift was on the observed `aws_iam_role.api` inline-policy metadata: the
  remote role included the expected PR #369 `davdeployPlan-*` verification
  statement conditioned on external ID and role session name. The planned IAM
  role and policy resources were no-ops; no IAM policy change was in this plan.
- Saved-plan manifest SHA-256:
  `6d09462f38186ce1f2f857c107edac085dc99e54bdbde3c5d093f7c7629ebb1f`.
- Exact saved-plan apply [43167867502](https://github.com/Bepoadewale/davdeploy/actions/runs/43167867502)
  succeeded as deployment `7730096971`. The workflow verified the manifest and
  saved-plan digest; database migrations completed successfully.
- Merged-main CI run
  [43164941399](https://github.com/Bepoadewale/davdeploy/actions/runs/43164941399)
  passed all seven required jobs.

## Post-release observations

- AWS caller identity was account `654654474502`.
- All six control-plane Lambdas are Active with `LastUpdateStatus=Successful`
  and common `CodeSha256=rDLJBuzr4P+pnynzB1bJUTU2kqzW5c3IL5I9DEd3lCY=`.
- `/healthz` returned HTTP 200 with
  `{"status":"ok","product":"davdeploy"}`.
- `DAVDEPLOY_NOVA_PLAN_ROLE_VERIFY_ENABLED=true`; the plan runner, credential
  broker, plan reviews, and Terraform state API remain `false`.
- No customer plan role was installed or verified. No customer plan, customer
  workload, or customer AWS resource was created or changed.

## Commands executed

Checks performed:

- `gh run watch 43166003130 --interval 300 --exit-status --compact`
- `gh run watch 43167867502 --interval 300 --exit-status --compact` (the
  watcher encountered a network error after the run; `gh run view` independently
  confirmed the apply job and all steps succeeded)
- Read-only AWS caller identity, Lambda configuration, and API health checks.
- Terraform plan JSON was streamed through an allowlisted summary filter; raw
  sensitive plan contents were not printed.

## Resources created

No customer or disposable AWS resources were created. The six existing
control-plane Lambda packages were updated in place by the protected release.

## Teardown

Not applicable. This was a control-plane release and created no disposable
resources.

## Observed result

The exact saved-plan deployment and migrations succeeded, all six control-plane
Lambdas report successful updates, and the API health endpoint is healthy. Only
plan-role trust/account verification is enabled; hosted customer planning and
workload lifecycle remain unavailable and unproven.

## Final boundary

This release deploys source and policy changes only. It does not attest
customer-role effective permissions, enable the Nova plan worker or state API,
provide complete regional pricing, allow exact-cost approval, or prove a
customer workload's apply, health, recovery, or teardown. Those gates remain
incomplete.
