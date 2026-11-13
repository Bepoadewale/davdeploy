# test391 — hosted Nova plan-only control-plane deployment

Date: 2026-11-13
Execution type: Real AWS control-plane deployment; no customer workload
Customer repository: None; this verifies DavDeploy's control plane only
Commit: `ae9ec4450d527141081e95707a1c3ee05126b683` (PR #390)
AWS account: `654654474502`
AWS region: `us-east-1`

## Resources created

- The operations-bootstrap rollout created the fixed IAM managed policy
  `nova-plan-only-start-build-overrides` (recorded in PR #390).
- The control-plane plan added its attachment to `davdeploy-api` and made
  eight in-place changes; it planned zero destroys or replacements.
- No customer resources were created.

## Commands executed

- Protected Terraform plan run
  [43388286514](https://github.com/Bepoadewale/davdeploy/actions/runs/43388286514).
- Exact saved-plan apply run
  [43389226372](https://github.com/Bepoadewale/davdeploy/actions/runs/43389226372).
- Read-only AWS CLI checks verified account identity, API Lambda state and
  code digest, managed-policy attachment, and fixed CodeBuild project settings.
- `curl -sS -o /dev/null -w '%{http_code}\n' https://api.davdeploy.tech/healthz`.

## Observed result

The reviewed control-plane plan was applyable and had 1 addition, 8 in-place
changes, and no destroys or replacements. Apply completed successfully and
its database migration step passed. In account `654654474502`,
`davdeploy-api` reported `State=Active`, `LastUpdateStatus=Successful`, and
`CodeSha256=E1O6BxLyyxTN/epgvT0pyCkQU1bE4QXi+drUAp+cE+I=`. The fixed deny
policy was attached to the API role. The isolated `davdeploy-nova-plan-only`
CodeBuild project uses its fixed service role and pinned release package.
The health endpoint returned HTTP 200.

The Nova plan review, runner readiness, role verification, credential broker,
and Terraform state API gates are enabled. Hosted certification remains
disabled. The deployment did not establish effective permissions for a
customer role or complete pricing evidence.

## Teardown

No disposable customer workload resources were created. The persistent
DavDeploy control-plane release and its policy attachment were not removed.

## Final boundary

This is control-plane deployment evidence, not customer-workload execution.
No customer role was installed or exercised, no customer plan was submitted,
and no customer AWS workload was created, applied, health-checked, updated,
recovered, or destroyed. Final cost-bound approval remains blocked until
trusted complete regional pricing evidence is integrated.
