# ticket348 — run-scoped Nova plan credential broker

PR: [#348](https://github.com/Bepoadewale/davdeploy/pull/348)
Branch: `feat/nova-run-credential-broker-348`
Base: `main`

## Problem / goal

The Nova plan worker currently receives a customer's AWS ExternalId in its
encrypted staged input and calls `sts:AssumeRole` itself. Move that secret
resolution and customer-role assumption into the control plane. The fixed
CodeBuild worker should request short-lived credentials only for its exact
active durable run; the control plane must verify the run, attempt, immutable
revision, organization/project, AWS connection, account/region, proposal digest,
project and live CodeBuild build before issuing them.

## Current repo state

- `service.py` previously read the connection ExternalId and embedded it in staged input.
- `nova_plan_codebuild.py` previously read that value and assumed the customer plan role.
- The API already has an AWS_IAM/SigV4 CodeBuild-only Terraform state bootstrap
  route and run/build verification helpers.
- The API role can assume `davdeployPlan-*` roles for verification and for the
  separate run-scoped credential broker. The customer plan role trusts only
  the control-plane role. Its issued session is bounded by a proposal-scoped,
  explicit-deny policy.
- Hosted plan runner, state API, plan review, apply and customer execution
  remain disabled. This PR must not enable them.

## Research / references used

- `apps/api/src/davdeploy/main.py`: API Gateway IAM bootstrap, durable run and
  active CodeBuild checks.
- `apps/api/src/davdeploy/nova_plan_dispatch.py`: immutable staged-input read.
- `apps/api/src/davdeploy/nova_plan_codebuild.py`: current worker assumption
  and proposal-scoped access policy.
- `apps/api/src/davdeploy/nova_plan_access.py`: fixed policy compiler.
- `apps/api/src/davdeploy/service.py`: plan-run staging and connection-secret
  lookup.
- `infrastructure/terraform/serverless-control-plane/main.tf`: route
  integrations, API and CodeBuild IAM, customer-role verification gates.
- `infrastructure/cloudformation/customer-discovery-role.yaml`: existing
  plan-role trust boundary.
- AWS [CodeBuild IAM condition keys](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html): `codebuild:BuildArn` is present when calls are made by a role assumed by CodeBuild.
- AWS [CodeBuild sandbox troubleshooting](https://docs.aws.amazon.com/codebuild/latest/userguide/sandbox-troubleshooting.html): shows the CodeBuild assumed-role session name format, which is matched to the build UUID.

## Work planned for the PR

- Add a separate AWS_IAM-authenticated credential bootstrap route. API Gateway
  must overwrite the caller-principal header from the authenticated identity.
- Authenticate only the exact fixed Nova CodeBuild role and its build-specific
  role session. Match the request to one active CodeBuild build and one durable
  `BUILD_STARTED` attempt, then
  independently verify the run, revision, tenant, connection, target, input
  version/digest and proposal digest.
- Resolve ExternalId from the control-plane secret store and assume only the
  exact account/connection plan role with the deterministic proposal-scoped
  explicit-deny session policy. Verify the returned STS identity account.
- Return short-lived STS credentials over the SigV4 TLS response; keep them out
  of logs, database rows, artifacts and exception text. Bound response shape
  and credential lifetime. Preserve the current safe state-bootstrap route.
- Remove ExternalId material from staged build input and remove customer-role
  assumption permission from the CodeBuild service role. Make the worker use
  only the broker response; reject secret-bearing staged input and unexpected
  response fields. Keep the feature disabled by default.
- Add negative tests for unauthenticated/wrong-role callers, stale/wrong build,
  cross-tenant or stale revision, connection/account/region mismatch, tampered
  proposal/input, missing secret, invalid STS identity, response leakage and
  credential expiry. Persist a non-secret audit event before returning any
  credentials.

## Acceptance criteria

- [x] Customer ExternalId is absent from both request-stage and build-stage
  artifacts and is never included in model context, logs, results or manifests.
- [x] Only the exact active fixed CodeBuild attempt can receive short-lived
  customer plan-role credentials, and only for the proposal-scoped policy.
- [x] Credential brokerage fails closed on tenant, project, revision, build,
  account, region, connection, digest, role, policy, secret-store or STS errors.
- [x] CodeBuild has no `sts:AssumeRole` permission to customer plan roles.
- [x] Existing state bootstrap behavior and unrelated execution paths remain
  compatible; all Nova planning gates remain off by default.
- [ ] Focused tests, `make verify`, documentation checks, and a fresh
  `make local-proof` pass; GitHub checks and independent review pass.
- [x] No customer role, AWS workload, or infrastructure is mutated by tests.

## Acceptance status

Implementation and focused/full local verification are complete. The isolated
clean-room proof was not run because the existing checkout has active DavDeploy
Docker containers and databases; this PR will not reuse or remove their data.
GitHub checks and independent review remain the merge gate.

## Tests / validation performed

- Focused suite: 124 passed across Terraform state identity, Nova plan worker,
  infrastructure contract, customer connection contract and product tests.
- `make verify`: 899 passed; Ruff, Actions configuration, OpenAPI and Compose
  configuration checks passed.
- Terraform formatting/validation, focused tests, documentation conventions
  and `git diff --check` passed. Isolated `make local-proof`, final-head GitHub
  checks and independent review remain pending. No AWS calls or customer
  infrastructure changes were made.

## Evidence files produced

- `docs/test/test348.md`

## Boundaries

This is credential transport and authorization plumbing for plan-only runs. It
does not attest the customer's installed IAM policy, enable hosted planning,
price or approve a saved plan, apply/destroy infrastructure, or certify a
customer workload. The runner, state service and approval gates stay disabled.

## Follow-up work

- Verify the customer plan-role installation uses the control-plane
  assumption principal for all existing connections before any hosted plan.
- Continue the tenant-isolated remote-state, trusted pricing, exact-plan
  approval, apply, health, recovery, teardown and composed-workload gates.
