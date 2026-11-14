# test406 — post-deployment verification

Date: 2026-11-14
Execution type: Hosted control-plane release verification
Customer repository: None; this deployment updates the DavDeploy control plane
Commit: `74016e70aa7a702ebf3338cf1fbb43d4f563a838`
AWS account: `654654474502`
AWS region: `us-east-1`

## Resources created

No new AWS resources. The reviewed plan updated the fixed Nova plan-only
CodeBuild environment, two scoped IAM policies, and six Lambda functions.

## Commands executed

- `gh run view 43565505292` and `gh run view 43566319945`
- Read-only AWS queries for Lambda package identities, runtime feature flags,
  and the plan-only CodeBuild project.
- `curl https://api.davdeploy.tech/healthz`

## Observed result

- Source: backend `main` commit
  `74016e70aa7a702ebf3338cf1fbb43d4f563a838` (PR #405).
- Merged-main CI: run
  [43565090000](https://github.com/Bepoadewale/davdeploy/actions/runs/43565090000),
  all seven required jobs passed.
- Terraform root: `infrastructure/terraform/serverless-control-plane`.
- AWS account/region: `654654474502` / `us-east-1`.
- Saved plan: [43565505292](https://github.com/Bepoadewale/davdeploy/actions/runs/43565505292),
  succeeded for the exact main commit.
- Exact saved-plan apply:
  [43566319945](https://github.com/Bepoadewale/davdeploy/actions/runs/43566319945),
  succeeded. It verified the saved-plan manifest and checksum, applied only
  that plan, and reported successful database migrations.

The safe plan summary reported 0 additions, 9 updates, and 0 destroys or
replacements. The nine updates were the plan-only CodeBuild environment, two
scoped artifact policies, and six Lambda package updates. The summary also
reported separate drift on the API and plan-only IAM role metadata; read-only
policy-name inspection matched the expected attached and inline policy names.
No drift was hidden or rewritten as an apply action.

After apply, all six `davdeploy-*` Lambda functions were Active and shared
`CodeSha256=oN2XezDmrH9YrIQVe47NZG9IsfSeI+zOd4tJIXMU2Kw=`. The API's Nova plan
runner, plan reviews, customer role verification, credential broker and
Terraform state API flags were `true`. The dedicated
`davdeploy-nova-plan-only` CodeBuild project exists with `NO_SOURCE` and its
fixed pinned-artifact loader. `https://api.davdeploy.tech/healthz` returned
HTTP 200 and `{"status":"ok","product":"davdeploy"}`.

## Teardown

No disposable workload resources were created, so no workload teardown was
needed. The control-plane release remains deployed.

## Final boundary

This release deploys control-plane and plan-only infrastructure. It does not
show that an authenticated customer created a Nova plan, installed or passed
effective-permission verification for a customer plan role, received a
trusted complete price, approved a plan, applied a workload, observed real
application health, recovered a failure, or destroyed resources. No
Nova-generated customer workload was created or mutated by this release.
PR #318 remains closed/held; PR #399 remains draft. The feature gates being
enabled do not substitute for these missing customer-flow results.

