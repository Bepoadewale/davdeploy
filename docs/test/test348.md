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
control-plane API. The API accepts requests only through a dedicated AWS
Identity and Access Management (IAM) authenticated route, validates the
authenticated CodeBuild role and exact active build against the durable run,
reads the immutable staged input, revalidates current revision and approval,
and returns 15-minute credentials for the exact customer plan role with a
proposal-scoped explicit-deny session policy. The CodeBuild role has no
customer-plan-role `sts:AssumeRole` grant. All new Terraform feature flags
default off.

## Commands executed

- Focused broker, worker, infrastructure-contract, customer-connection and
  product tests: **124 passed**.
- `make verify`: **899 passed**; Ruff, configuration checks, OpenAPI snapshot
  and Docker Compose configuration passed. One existing Starlette/httpx
  deprecation warning remains.
- `terraform fmt -check -recursive infrastructure/terraform/serverless-control-plane`:
  passed.
- `terraform -chdir=infrastructure/terraform/serverless-control-plane init
  -backend=false -lockfile=readonly` and `terraform ... validate`: passed.
- `git diff --check`: passed.
- No AWS or Bedrock calls were made. No customer role was assumed and no AWS
  resource was created or changed.

## Observed result

The control-plane API and fixed worker contract passed the local automated
tests. The configured production path remains disabled, and no hosted plan or
customer role assumption was attempted.

## Resources created

None. Tests used local fakes and did not start containers or contact AWS.

## Limitations

These tests use mocks for CodeBuild, S3, Secrets Manager and STS. They do not
prove the hosted API Gateway SigV4 integration, deployed Lambda package,
customer-role installation, regional pricing, saved-plan approval, or a
customer workload. The credential broker and Nova runner remain disabled in
hosted AWS. The PR does not grant a general CodeBuild caller access: the AWS
IAM policy requires the fixed project's `codebuild:BuildArn`, and the API
matches the authenticated `AWSCodeBuild-<build-UUID>` session to the requested
live build. GitHub CI and independent review are still pending.

## Teardown

No cloud or local infrastructure resources were created for these checks; no
teardown was required.

## Final boundary

Passing local tests show the implemented contract behaves as tested with
mocks. They do not establish deployed availability, customer readiness, or
Nova workflow completion.
