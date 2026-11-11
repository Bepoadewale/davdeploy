# test348 — run-scoped Nova plan credential broker

PR: [#348](https://github.com/Bepoadewale/davdeploy/pull/348)

Date: 2026-11-11  
Execution type: Local tests and static infrastructure checks  
Customer repository: `Bepoadewale/davdeploy`  
Commit: pending implementation commit  
AWS account: none accessed  
AWS region: none accessed

## Scope

This change moves plan-role assumption and ExternalId lookup into the
control-plane API. The API accepts requests only through dedicated AWS
Identity and Access Management (IAM) authenticated routes, validates the
authenticated CodeBuild role and derives the exact active build ID from its
authenticated session before checking the durable run,
reads the immutable staged input, revalidates current revision and approval,
and returns 15-minute credentials for the exact customer plan role with a
proposal-scoped explicit-deny session policy. The CodeBuild role has no
customer-plan-role `sts:AssumeRole` grant. All new Terraform feature flags
default off.

## Commands executed

- Focused broker, worker, infrastructure-contract, customer-connection and
  product tests: **124 passed** before the final state-bootstrap audit addition;
  focused Terraform-state tests then passed (**26 passed**), including the
  latest assertion that state-credential responses set `Cache-Control:
  no-store` and `Pragma: no-cache`.
- The focused credential client and broker-route suites passed (**58 passed**),
  covering retryable exact-build input publication, bounded backoff, retry
  exhaustion and immediate failure for other authorization responses.
- Before the publication-race follow-up,
  `DAVDEPLOY_DATABASE_URL=sqlite+pysqlite:///:memory: make verify` passed
  **899 tests**; Ruff, configuration checks, OpenAPI snapshot and Docker
  Compose configuration passed. The in-memory database setting kept the
  local runtime database path absent. One existing Starlette/httpx
  deprecation warning remains.
- After adding the publication retry, the same in-memory `make verify` command
  passed **903 tests**; Terraform formatting/validation, docs conventions,
  `git diff --check` and the `.local` absence check also passed.
- `terraform fmt -check -recursive infrastructure/terraform/serverless-control-plane`:
  passed.
- `terraform -chdir=infrastructure/terraform/serverless-control-plane init
  -backend=false -lockfile=readonly` and `terraform ... validate`: passed.
- `git diff --check`: passed.
- At commit `1da2f97` in a fresh detached worktree with the unique Compose
  project `davdeploy-pr348-cleanroom`, `make local-proof` passed. The extra
  `demo-simple`, `demo-complex`, `demo-degraded`, `demo-day2`, `demo-failure`
  and `demo-readiness-failure` targets, `trace-check` and `verify` also passed.
- `make clean-local` removed that exact isolated project's containers,
  network and PostgreSQL volume, plus its generated `.venv` and `.local`; the
  exact worktree was then removed. The pre-existing DavDeploy container was
  verified still running.
- No AWS or Bedrock calls were made. No customer role was assumed and no AWS
  resource was created or changed.

## Observed result

The control-plane API and fixed worker contract passed the local automated
tests. Both the plan-credential broker and Terraform-state bootstrap derive
the build ID from the authenticated CodeBuild session; each signed request
carries only a durable run ID. Their CodeBuild IAM permissions are scoped to
the fixed project's build ARN. Both credential issuances record a non-secret
audit event, committed before credentials are returned. The configured
production path remains disabled, and no hosted plan or customer role
assumption was attempted.

## Resources created

The isolated local Compose stack, network and PostgreSQL volume were created
for this proof and removed after it completed. No AWS or customer resources
were created.

## Limitations

These tests use mocks for CodeBuild, S3, Secrets Manager and STS. They do not
prove the hosted API Gateway SigV4 integration, deployed Lambda package,
customer-role installation, regional pricing, saved-plan approval, or a
customer workload. The credential broker and Nova runner remain disabled in
hosted AWS. The PR does not grant a general CodeBuild caller access: the AWS
IAM policy requires the fixed project's `codebuild:BuildArn`, and the API
derives the build ID from the authenticated `AWSCodeBuild-<build-UUID>` session
instead of accepting it from the request. GitHub CI run `43026767357` passed
all seven required checks for proof/evidence commit `78895ed`; run `43025299664`
passed all seven for implementation commit `1da2f97`. The isolated
local clean-room proof also passed and its temporary resources were removed.
Current-head independent review remains pending. This local fixture workflow
does not exercise the hosted Nova runner or a customer AWS role.

## Teardown

No AWS or customer infrastructure resources were created. The isolated local
test containers, network, volume and worktree were removed after the run;
unrelated DavDeploy resources were retained.

## Final boundary

Passing local tests show the implemented contract behaves as tested with
mocks. They do not establish deployed availability, customer readiness, or
Nova workflow completion.
