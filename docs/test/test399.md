# test399 — isolated local apply-state authorization groundwork

## Base synchronization — 2026-11-14

PR #399 was merged with current `main` at commit
`af1c19356b3d93df3ca35431771c9e0e7c119521`. All seven required CI jobs passed
for that head in run `43576086458`. This CI result confirms source integration;
it does not exercise a Nova apply dispatcher or execute a customer workload.

Date: 2026-11-13
Execution type: two isolated local Docker and fixture proofs only
Customer repository: `Bepoadewale/davdeploy`
Branch: `feat/nova-exact-plan-apply-399`
Commit: `3ad0086` (PR #399 branch merged with latest main; final ticket/evidence update pending)
AWS account: none (no AWS execution)
AWS region: none (no AWS execution)

## Run boundary

The run exercised the local fixture application and schema/authentication tests.
It did not invoke AWS, Bedrock, Terraform plan/apply, or customer workload
resources. The apply-run state credential code is source-only and remains
behind disabled runtime gates; no apply request or CodeBuild apply run exists.

## Resources created and retained

The first proof used Compose project `davdeploy-pr399`; the second used a fresh
project and database, `davdeploy-pr399-status`. Each has a separate Postgres
volume, network, and project-specific API, worker, and fixture-executor images.
The first used ports 18080, 18090, 18181, 19090, 13200, and 13000. The second
used ports 18180, 18190, 18281, 19190, 13210, and 13100. The retained
overrides are `/tmp/davdeploy-pr399-isolated-compose.yml` and
`/tmp/davdeploy-pr399-status-compose.yml`. Their fixture state files are
`/tmp/davdeploy-pr399-customer-plan-e2e.json` and
`/tmp/davdeploy-pr399-status-customer-plan-e2e.json`. A dedicated
`.venv-pr399` was created and retained.

Only the containers in `davdeploy-pr399` and `davdeploy-pr399-status` were
stopped with `docker compose stop`. Their containers remain stopped. Both
projects' named volumes, networks, images, temporary Compose files, and fixture
state files, along with `.venv-pr399`, were retained. The pre-existing
`davdeploy` Compose stack and database were not restarted or modified.

## Commands executed

- `make local-proof VENV=.venv-pr399`, with the `davdeploy-pr399` Compose
  project, alternate ports, and temporary fixture state path: passed.
- Repeated `make local-proof VENV=.venv-pr399` with fresh project
  `davdeploy-pr399-status`, ports 18180/18190/18281/19190/13210/13100, and a
  separate fixture state path: passed.

## Observed result

- Fresh isolated image build and Compose configuration: passed.
- Smoke check: API, worker, fixture executor, Prometheus, Grafana, Tempo, and
  OPA reported ready.
- API contract: passed against `http://127.0.0.1:18080`.
- Customer-plan fixture flow: developer submission, administrator decision,
  self-approval, local dry-run, readiness failure, governed fixture destroy,
  and audit checks passed.
- Demo data seeding and Tempo trace check: passed against the isolated stack.
- `make verify`: 1,113 tests passed; Ruff, Actions configuration, OpenAPI, and
  Compose checks passed. One existing Starlette/httpx deprecation warning.
- Latest focused apply-run status/access tests: `2 passed`; Ruff passed.
- Latest `make verify`: 1,115 tests passed; Ruff, Actions configuration,
  OpenAPI, and Compose checks passed. One existing Starlette/httpx deprecation
  warning. Documentation convention and `git diff --check` also passed.

## Combined mainline verification — 2026-11-14

The PR #399 branch merged current `origin/main` at PR #403 merge commit
`0e07f6b` with no conflicts. Combined `make verify VENV=.venv-pr399` passed
1,144 tests, Ruff, Actions configuration, OpenAPI, and Docker Compose checks.
One existing Starlette/httpx deprecation warning remains. This merge adds the
source-only #401/#402 actual-plan policy checks; it does not add apply
dispatch, enable an apply gate, or establish trusted pricing.

The local proof uses the existing fixture executor. It is not evidence that a
customer AWS plan was applied, that application health was observed, or that
hosted update, recovery, teardown, or independent AWS absence checks work.

## Teardown

Stopped only the containers in Compose projects `davdeploy-pr399` and
`davdeploy-pr399-status`. Kept their volumes, networks, images, fixture state,
temporary overrides, and the virtual environment. No customer AWS resource
was created, changed, or deleted.

## Final boundary

This records local fixture evidence only. It does not claim hosted customer
apply, health, recovery, or teardown readiness.


## Fixed dispatcher validation — 2026-11-15

PR #399 head `d239e37` adds a disabled-by-default CodeBuild dispatcher that
starts only the configured apply project with a durable run ID, and can locate
an existing build for reconciliation. It is currently an isolated source
component: no service route calls it, no apply-run is created by user action,
and the fixed CodeBuild buildspec exits before Terraform. No AWS API, Terraform,
or customer workload was invoked.

Hosted CI run `43696075794` failed in Ruff on the new dispatcher and the
downstream `local-e2e` job, which reached the same lint failure. The next head
fixed lint but run `43696455615` exposed three dispatcher test failures: the
fake swallowed an empty response, omitted a second build from its lookup page,
and allowed a non-canonical uppercase UUID through. The current follow-up
fixes response-type handling, rejects non-canonical UUIDs, and repairs those
fixtures.

Local checks on the follow-up source:

- `.venv/bin/pytest -q tests/test_nova_apply_dispatch.py`: 11 passed.
- `.venv/bin/ruff check apps/api/src/davdeploy/nova_apply_dispatch.py tests/test_nova_apply_dispatch.py`: passed.
- `make verify`: 1,260 passed; Actions configuration, Ruff, OpenAPI snapshot,
  and Compose configuration passed. One existing Starlette/httpx deprecation
  warning.
- `git diff --check`: passed.

An isolated full local clean-room cycle was attempted in
`/private/tmp/davdeploy-pr399-cleanroom`. It stopped at the initial
`make clean-local`: Docker Compose returned HTTP 500 from the local Docker
socket while listing containers. No stack was brought up and the command did
not proceed to bootstrap. This is an environment limitation; the hosted
fresh-runner `local-e2e` result for the follow-up commit is still pending.

No AWS account or region was used. No resources were created, changed, or
deleted. This is source and local-test evidence only, not proof of hosted
apply, health, recovery, destroy, or independent absence.

The integrated PR head `4d81b7e` passed all seven required GitHub CI jobs in
run `43696947968`, including `local-e2e` on a fresh runner. This is clean-room
source verification only; the apply buildspec still exits before Terraform,
and no customer workload was applied.

The current PR head `498e5ca` adds explicit tests for empty CodeBuild responses
and ambiguous run lookup. All seven required checks passed in run
`43697213134`, including the fresh-runner `local-e2e` job. This still does not
execute the disabled apply worker or a customer workload.

## Hosted branch verification — 2026-11-14

After GitHub updated this PR branch to the latest mainline, run
`43638007038` passed all seven required checks on commit
`44fa76f6e3e85fa0bddce26ddc0f25e724b03209`: Python, cloud contracts,
policy, documentation conventions, secrets, supply chain, and the hosted
`local-e2e` job. The first synchronized run exposed stale test fixtures that
did not carry the new digest-bound regional pricing evidence and a bootstrap
guard that recognized only the plan-runner role. The apply bootstrap guard now
admits the configured fixed apply role only when the apply feature flag is
enabled; exact-run, current approval, and administrator checks remain in the
route. The fixtures now use structurally valid, fresh pricing evidence.

No local tests were run for this update. No AWS workload or customer apply was
started. The saved-plan apply worker remains intentionally unwired and
fail-closed, and PR #399 remains a draft because material pricing and hosted
lifecycle acceptance are incomplete. The earlier local fixture evidence above
is historical and is not a substitute for hosted AWS execution evidence.


## Hosted dispatcher validation — 2026-11-15

Repository: `Bepoadewale/davdeploy`
Commit: `498e5cae8989a8ac2547e133fe2b96b2b11a768b`
Execution type: GitHub-hosted CI only; no customer workload or AWS apply.

Hosted run `43697213134` passed all seven required CI jobs. This run includes the new fixed CodeBuild dispatcher tests. The tests validate only request construction and build identity handling with test doubles; they do not start a real CodeBuild project.

No AWS resources were created by this change. No apply run was dispatched. The worker integration and real hosted lifecycle proof remain outstanding.

## 2026-11-15 request and worker dispatch evidence

- Code commit: 4a8ee3d32ac3fdc407f37e2170a2775c06549e9c.
- Hosted CI: run 43767690333, all seven jobs passed, including Python, local end-to-end, OpenAPI contract, policy, supply-chain, and cloud-contract checks.
- Added tests verify the apply request is rejected while runner readiness is closed and the worker does not claim apply work while readiness is false.
- The worker implementation uses the fixed CodeBuild dispatcher, durable idempotency token, atomic claim/version lease, and direct build lookup/status checks. Expired or uncertain dispatches are held for reconciliation; failed apply builds are not retried automatically.
- No CodeBuild apply was started and no AWS resources were created or changed by this test run.
- Limitations: the CodeBuild apply buildspec still exits before Terraform; no hosted callback, real apply, application health, update/recovery, destroy, or independent absence evidence exists. The readiness gate remains closed.

## 2026-11-17 apply credential broker source evidence

- The internal apply credential route is separately default-off and requires
  the fixed active CodeBuild apply identity plus a current, unexpired approved
  exact-plan manifest with complete pricing evidence and current workspace
  administrator authorization.
- Local test `test_state_bootstrap_binds_exact_plan_apply_to_active_approved_build`
  passed with test doubles. It verified the disabled gate, successful credential
  contract and no-store headers, rejected a mismatched STS account and expired
  credentials, and rejected issuance after administrator authorization was
  revoked. It also verified the dedicated role ARN is selected instead of the
  legacy administrator-pilot execution role.
- `make verify VENV=/Users/adewale/Projects/davdeploy/.venv-pr399` passed
  (1,291 tests); `make terraform-validate`, Ruff, Terraform format check, and
  `git diff --check` passed. This is local source evidence only; no real
  credentials were issued, no apply build was started, and no AWS resource was
  created or changed.
- Limitation: provisioning and least-privilege validation of the dedicated
  `davdeployNovaApply-<connection-id>` role are not implemented, and no hosted
  apply worker/buildspec, callback,
  health, recovery, destroy, or independent absence proof exists. Both apply
  readiness and the credential broker remain disabled.

The branch was then synchronized with current backend `main` at merge commit
`57f061f24cbb98dba12edd6b7a0e99406f9d5398`. On that head, `make verify`
passed 1,298 tests, `make terraform-validate` passed all configured roots,
and documentation conventions, Terraform formatting, and diff checks passed.
Fresh-head hosted CI is required after push.

## 2026-11-17 exact apply input contract source evidence

- Added an AWS IAM authenticated, default-off API Gateway route for the fixed
  apply build to fetch a fresh exact-plan request contract. The handler checks
  build identity, current approval/admin/pricing state, immutable request
  digest, exact artifact versions, tenant state scope, and a five-minute
  authorization window before auditing and returning the no-store response.
- Focused test `test_state_bootstrap_binds_exact_plan_apply_to_active_approved_build`
  uses test doubles and validates the returned contract with the production
  contract validator. It checks the disabled runner gate and successful
  request; it does not call AWS or start CodeBuild.
- The fixed buildspec remains fail-closed. No AWS credentials were issued and
  no apply, deploy, health, recovery, or destroy action occurred.
- Current local validation passed `make verify` (1,298 tests), all configured
  Terraform roots, documentation conventions, formatting, and diff checks.
  These tests used mocks and did not exercise AWS or CodeBuild.

## 2026-11-17 apply artifact isolation

- Execution type: local unit and infrastructure-contract tests only. No AWS
  request, artifact copy, customer credentials, CodeBuild apply, or workload
  mutation occurred.
- The apply input route now copies the approved saved-plan and workspace object
  versions into the active build's versioned, KMS-encrypted artifact prefix.
  Source version, digest, checksum, run identity, owner, and encryption are
  checked. Staging is recorded in the audit log before the copy. The apply
  CodeBuild IAM policy can read only this build-specific staged prefix, not
  other tenants' source artifacts.
- Focused validation passed: 23 tests across `test_nova_apply_artifacts.py`,
  `test_nova_apply_contract.py`, `test_nova_apply_workspace.py`, the active
  apply input/state route, and `test_nova_exact_plan_apply_infra.py`. Ruff
  passed on all changed Python files.
- `make verify VENV=/Users/adewale/Projects/davdeploy/.venv-pr399` passed
  (1,301 tests); `make terraform-validate` passed all configured roots.
  Documentation conventions, Terraform format, OpenAPI snapshot, Compose
  configuration, Ruff, and `git diff --check` passed. GitHub CI run
  `43988367335` passed all seven jobs on the preceding commit; fresh-head CI
  remains required after this change.
- This provides source evidence only. The apply buildspec still fails closed;
  no fixed worker execution, AWS apply, application health, recovery, destroy,
  or independent absence evidence is established.

## 2026-11-17 fixed apply worker and callback source evidence

- Execution type: local source tests and static Terraform validation using
  test doubles. No AWS credential was issued, no CodeBuild apply was started,
  and no customer resource was created or changed.
- The fixed buildspec fetches the exact version of the reviewed application
  archive, verifies Terraform 1.14.7 against a pinned SHA-256 checksum, and
  invokes `davdeploy.nova_apply_codebuild`. The worker restores the exact
  staged artifacts, binds the tenant state, requests customer credentials only
  after initialization, verifies the returned role identity, and invokes only
  `terraform apply` with the saved plan. It refuses to start unless the state
  and customer credentials outlast the full 12-minute apply bound plus a
  30-second margin.
- The worker writes a bounded KMS-encrypted, versioned result with a
  create-only condition. The API reconciler reads and validates the exact
  build-scoped result version, checksum, KMS metadata, plan/workspace digests,
  account, region, state scope, and toolchain before recording
  `APPLIED_UNVERIFIED`. Missing or mismatched results stay in
  `RECONCILIATION_REQUIRED`; build success is not application health.
- Focused checks passed: 52 tests across the apply dispatcher, client, worker,
  state API, and infrastructure gate. `make verify
  VENV=/Users/adewale/Projects/davdeploy/.venv-pr399` passed 1,312 tests,
  Ruff, Actions configuration, OpenAPI snapshot, and Compose config.
- `make terraform-validate` passed all configured roots;
  `terraform fmt -check -recursive infrastructure/terraform`, documentation
  conventions, and `git diff --check` passed.
- Apply and credential-broker flags remain false by default; dispatch readiness
  requires both. Dedicated customer-role provisioning/effective permission
  checks and hosted apply, health, recovery, destroy, and independent absence
  evidence remain incomplete.

## Final-head CI — 2026-11-17

- Commit: `33727c46a025a2440a7393d6a6d331dc84917058`.
- GitHub Actions run `43995850553` passed all seven required checks,
  including the hosted clean-runner `local-e2e` check.
- This is source and CI evidence only. No customer credentials, apply build,
  workload deployment, health observation, or teardown occurred.
- PR #399 remains draft and both apply gates remain disabled.

## Current main synchronization — 2026-11-17

- PR #399 source commit `e01eee2` merges backend `main` through `8c7f1de`,
  including PRs #422 and #423. The control plane remains deployed from PR #420;
  this merge is source-only.
- `make verify` passed 1,332 tests, Ruff, Actions configuration, OpenAPI, and
  Compose configuration. Documentation conventions and `git diff --check`
  passed. One existing Starlette/httpx deprecation warning remains.
- GitHub run `44060781429` passed all seven required checks, including the
  hosted clean-runner `local-e2e` check.
- This sync does not enable either apply gate. No AWS resource was changed,
  no customer credential was issued, and no apply build or workload ran.

## Current main synchronization after PR #424 — 2026-11-17

- Backend `main` is `602206ee1fd73b4582015ec30d2b5e472d72baf7` after PR #424
  (bounded Aurora Serverless v2 pricing) and PR #413 (coverage ledger) merged.
  The PR #399 branch was merged with that main at
  `29957e14ce13fb7df7000f3e1a7244cbb1c5154f`.
- Read-only GitHub reconciliation confirms PR #399 remains open and draft at
  `fe86079e5bd917daa99f10e63900093aa25753f4`, based on current main
  `602206e`. Fresh-head GitHub Actions run `44070631960` passed all seven
  required checks.
- Read-only AWS checks verified account `654654474502` in `us-east-1`; no
  matching SageMaker endpoint, model, endpoint configuration, or active
  DavDeploy Batch job definition was found. Four tagged DavDeploy Batch job
  definitions remain inactive. The existing SageMaker lineage action and
  context remain; their recorded properties report `Deleting`. The attempted
  association-list command was unsupported by the installed AWS CLI, so this
  check does not establish the association inventory. No AWS resources or
  lineage records were changed.
- The Terraform run monitor returned `{}`. Protected local files and retained
  clean-room artifacts were left untouched. PR #413 and #424 are merged; the
  hosted runtime remains PR #420. Apply/broker gates remain off; no customer
  credential, apply build, or Nova workload was used.
- `make verify VENV=/Users/adewale/Projects/davdeploy/.venv-pr399` passed
  1,342 tests, Ruff, Actions configuration, OpenAPI snapshot, and Compose
  configuration. `make terraform-validate`, recursive Terraform formatting,
  documentation conventions, and `git diff --check` passed. One existing
  Starlette/httpx deprecation warning remains.

## Plan-scoped apply role source checks — 2026-11-17

- Execution type: local tests, static infrastructure checks, and read-only AWS
  inventory only. The checks ran against the PR #399 synchronized worktree;
  no customer role or permission policy was installed or assumed.
- The source builds a per-plan STS session policy for mapped S3 bucket,
  bucket-subresource, SQS queue, and DynamoDB table changes. It rejects
  unsupported types/actions, unscopable names, empty mutation plans, and
  policies over 2,048 bytes. Replacement tests confirm the old ARN receives
  delete actions and the new ARN receives create actions. The dedicated role
  verifier checks exact broker trust and ExternalId, tags, role identity,
  session duration, no boundary or managed policies, and the fixed inline
  policy. The template and broker policy action ceilings are tested for drift.
- The base S3 bucket resource includes its provider's bucket-scoped read
  permissions, permits bucket create/tag/delete operations only, and rejects
  changed embedded settings outside that map or `force_destroy` deletion.
- Credential issuance rejects incomplete price evidence before calling STS,
  even when the test rebinds the apply run and stored approval digest to the
  incomplete manifest. The regression also verifies no credential-issued
  audit event is added. Approval itself validates the pricing evidence against
  the persisted customer context and freshness window.
- After this regression, `make verify` passed 1,366 tests, Ruff, Actions
  configuration, OpenAPI, and Compose checks. Documentation conventions and
  `git diff --check` passed; all configured Terraform roots had passed
  `make terraform-validate` earlier in this same source package.
- S3 deletion operations use their documented IAM authorization action; for
  example, deleting bucket CORS, lifecycle, ownership, public-access-block,
  and encryption settings is authorized with the corresponding `Put...`
  permission. See [AWS's S3 API permission reference](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-with-s3-policy-actions.html).
- Focused command: `python -m pytest -q tests/test_nova_apply_access.py
  tests/test_nova_apply_role_profile.py tests/test_nova_apply_contract.py
  tests/test_nova_apply_clients.py tests/test_nova_apply_codebuild.py
  tests/test_generated_plan_artifacts.py tests/test_nova_plan_codebuild.py
  tests/test_terraform_state.py::test_state_bootstrap_binds_exact_plan_apply_to_active_approved_build
  tests/test_nova_exact_plan_apply_infra.py` — 94 passed.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python`
  passed 1,366 tests, Ruff, Actions configuration, OpenAPI snapshot, and
  Compose configuration. `make terraform-validate` passed all configured
  roots. Recursive Terraform formatting, documentation conventions, and
  `git diff --check` passed.
- AWS CloudFormation `validate-template` parsed the customer role template;
  this validated template syntax only and created or changed no AWS resource.
- This profile check is not a complete AWS effective-permissions attestation;
  it does not inspect organization SCP/RCP policy, resource-based grants, or
  all service authorization behavior. Only the mapped resource families can
  receive an apply session policy; unsupported plans remain uncredentialed.
- AWS account `654654474502` was rechecked read-only in `us-east-1`; the
  matching SageMaker endpoint/model/configuration queries were empty and four
  tagged Batch test definitions remained INACTIVE. The Terraform monitor
  registry was empty. SageMaker lineage evidence was preserved. No AWS
  resource, lineage record, credential, apply build, or control-plane state was
  changed. Apply and credential-broker gates remain off.
- GitHub Actions run `44078718495` passed all seven checks on implementation
  commit `1a2c507`, including its clean-runner end-to-end job. This section is
  a documentation-only follow-up and has its own required PR check run.
- The full local clean-room cycle was not run because its cleanup would delete
  retained artifacts without current explicit deletion approval. No customer
  workload was applied or certified.
- This pricing-gate regression was added after runs `44078718495` and
  `44095877464`; both ran before the regression. Local validation has since
  passed. GitHub Actions run `44103391874` then passed all seven checks on
  implementation commit `ef1e12b`, including the fresh-runner end-to-end job.
  The follow-up evidence commit was then verified by run `44107574427` on exact
  head `526220e2662a0bd85b3b2755608929a87535a4b5`; all seven required jobs
  passed, including `local-e2e`.

## Final-head AWS and CI recheck — 2026-11-17

- PR #399 head `526220e2662a0bd85b3b2755608929a87535a4b5` remains an open
  draft based on current `main` `602206ee1fd73b4582015ec30d2b5e472d72baf7`.
- GitHub Actions run `44107574427` passed all seven required jobs on that
  exact head: documentation conventions, secrets, supply chain, local end to
  end, cloud contracts, policy, and Python.
- Read-only AWS identity verification returned account `654654474502` in
  `us-east-1`. No `davdeployNovaApply-*` role or active DavDeploy Batch
  definition was present; the four tagged Batch test definitions remain
  inactive. SageMaker endpoint, model, and endpoint-configuration lists were
  empty. The retained DavDeploy SageMaker lineage action and context remain.
- The Terraform run monitor registry is `{}` and no Terraform apply/destroy
  process is active. No AWS resource, lineage record, customer credential,
  apply build, control-plane state, or customer workload was changed.
- This is source/CI and read-only inventory evidence. It does not prove
  customer-role effectiveness, hosted apply, health, recovery, teardown, or
  independent absence. Both apply gates remain disabled.

## Customer apply-role onboarding source validation — 2026-11-17

- Added a default-off `nova-apply` Quick Create path for a workspace
  administrator after discovery verification and exact plan-role profile
  verification. The setup link binds the connection ExternalId and target
  account to the dedicated apply role, and the API returns it with
  `Cache-Control: no-store` and `Pragma: no-cache`.
- The API audit record omits the ExternalId and URL. The role template is
  published as a separate content-hash S3 object; Terraform exposes the URL
  and keeps the onboarding flag disabled by default. Creating a setup link
  does not create or verify a customer role, issue credentials, start
  CodeBuild, or enable apply.
- Full `make verify
  PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python` passed 1,373
  tests, Ruff, Actions configuration, OpenAPI snapshot, and Compose config.
- `make terraform-validate` passed every configured Terraform root;
  `terraform fmt -check -recursive infrastructure/terraform`, documentation
  conventions, and `git diff --check` passed. AWS CloudFormation
  `validate-template` parsed the role template and reported the named-IAM
  capability; no stack was created.
- GitHub Actions run `44123626109` passed all seven required checks on
  implementation commit `3967b48d105934eb19d055cc78bb99d0f88281ed`, including
  the fresh-runner `local-e2e` job.
- This is source/static/local-test evidence only. The full local clean-room
  cycle was not run because cleanup would remove retained local artifacts
  without current deletion approval. No AWS resource, template-host object,
  control-plane state, role, customer credential, apply build, or workload was
  changed. Apply and credential-broker gates remain disabled.

## Final documentation-head CI and AWS recheck — 2026-11-17

- Exact PR head `e0df560b99364f82e5a1caf072d5b9e0bd74f0d0` passed all seven
  GitHub Actions checks in run `44124793410`, including the fresh-runner
  `local-e2e` and Terraform validation jobs.
- Read-only AWS identity remained account `654654474502` in `us-east-1`.
  SageMaker endpoint/model/configuration lists were empty; four tagged
  DavDeploy Batch definitions remained inactive. The Terraform monitor was
  empty and no Terraform apply/destroy process was active.
- No customer role, credential, apply build, workload, hosted control-plane
  state, or SageMaker lineage record was created, issued, started, changed, or
  deleted. Existing lineage evidence remains preserved.
- This is source, CI, and read-only inventory evidence only. Customer-role
  effectiveness and the hosted plan/apply/health/recovery/teardown lifecycle
  remain unproved. Apply gates remain off; no Nova customer workload is
  certified.

## Per-plan customer permission preflight — source validation

- Before returning apply credentials, the API now checks the exact customer
  role profile and runs IAM `SimulatePrincipalPolicy` over every action/resource
  pair in the approved plan scope. The candidate STS session policy is supplied
  as a simulated permissions boundary. Every pair must be allowed, complete,
  and returned without pagination errors; failures stop credential issuance.
- The apply role grants simulator access only for its own role ARN. The apply
  session policy explicitly denies IAM simulator calls, keeping this
  inspection permission out of the Terraform worker session.
- Focused tests passed (28); full `make verify
  PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python` passed 1,377
  tests, Ruff, Actions configuration, OpenAPI snapshot, and Compose config.
- AWS CloudFormation `validate-template` accepted the updated apply-role
  template and reported the expected named-IAM capability; no stack was
  created. `git diff --check` and documentation conventions passed.
- GitHub Actions run `44128923407` passed all seven required jobs on source
  commit `d12ee73cbc7aff0f07026094e195c36ba4325449`, including clean-runner
  `local-e2e` and Terraform validation.
- No customer apply role exists in the verified inventory, so no live IAM
  simulation was run. Tests use a fake IAM client. AWS documents that
  simulation can differ from live authorization, omits resource control policy
  support, and cannot simulate resource policies attached to IAM roles. This
  check does not certify effective permissions or a workload.
- No AWS resource, credential, apply build, control-plane state, or lineage
  evidence changed. Both apply gates remain disabled; no Nova customer
  workload has been applied or certified.

## IAM data policy wildcard bounds — 2026-11-17

- `tests/test_generated_plan_policy.py`: 207 focused tests passed, including
  new cases rejecting `s3:*`, `sqs:*`, and `dynamodb:Put*`; wildcard or
  incomplete S3/SQS/DynamoDB resource ARNs; IAM Allow statements using
  `NotResource` and `NotAction` in identity, S3 bucket, and SQS queue policies;
  external AWS principals and unbounded Resource ARNs in S3/SQS policies; and
  cases retaining exact S3 bucket/object, SQS queue, and DynamoDB table/index
  scopes.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python`:
  passed 1,402 tests, Ruff, Actions configuration, OpenAPI snapshot, and
  Compose validation. `git diff --check` passed.
- These tests validate source policy evaluation only. They use no live
  customer AWS role and do not establish effective permissions or apply
  behavior. No AWS resource, control-plane state, credential, or lineage
  evidence was changed.
- Fresh-head GitHub Actions run `44134431454` passed all seven required checks
  on commit `24fa893fdd3d77358861e2bc1451dd4b791fbd0e`, including
  `local-e2e` and Terraform validation.
- Follow-up commit `9a241e1`, including the `NotResource` regression, passed
  all seven checks in fresh-head run `44140537111`.
- Source commit `33cd509` passed all seven checks in fresh-head run
  `44142215551`, including the S3 and SQS inverse-resource regressions.
- Source commit `7b2b84b` passed all seven checks in fresh-head run
  `44177455097`, including the cross-account principal regressions.
- Final source commit `9140d45431847cb171ec0bad758fdf69b5e7115c` passed all
  seven fresh-head GitHub Actions checks in run `44179449868`, including the
  local end-to-end and cloud-contract jobs. The PR remains draft; no customer
  role or workload was exercised.

## Isolated local clean-room proof — 2026-11-17

- Worktree `/private/tmp/davdeploy-pr399-cleanroom-20261117`, detached at
  `9739dd4b8df2785dfd782f710bfd216b97e7b529`, ran `make local-proof
  VENV=.venv` with Compose project `davdeploy-pr399-cleanroom-20261117`,
  subnet `10.251.253.0/24`, and alternate host ports. Compose configuration,
  service smoke checks, versioned API/CORS contract, customer-plan fixture
  end-to-end flow, demo seed, Tempo trace check, and full verification passed;
  verification reported 1,396 tests passed and one existing
  Starlette/httpx deprecation warning.
- The proof used local fixture data only; it did not call AWS, issue customer
  credentials, run Terraform, change hosted state, or execute a customer
  workload. It does not prove hosted apply, health, recovery, destroy, or
  independent absence.
- `docker compose stop` stopped this project's containers. They are all
  stopped; no `down`, cleanup target, file removal, volume deletion, or image
  deletion ran. The isolated worktree, `.venv`, Compose override, project
  network `davdeploy-pr399-cleanroom-20261117_default`, database volume
  `davdeploy-pr399-cleanroom-20261117_davdeploy-postgres`, and project images
  remain retained.

## Platform-account private S3 smoke — 2026-11-18

At the user's direction, AWS account `654654474502`, region `us-east-1`, was
used as the test target. The hosted control plane, its Terraform state, and its
runtime were not changed. This was a direct Terraform smoke test using profile
`ai-platform-pilot-key`, not a Nova-generated or hosted apply. No dedicated
`davdeployNovaApply-*` role or CodeBuild runner was used.

The source root `infrastructure/terraform/customer-workload-private-s3` was
copied to `/private/tmp/davdeploy-platform-account-test-20261118-1d8d82b4b8d9`.
The copy's S3 backend declaration was removed so it used isolated local state;
the DavDeploy Terraform state bucket and lock table were not used. The unique
connection/project tags were `nova-test-1d8d82b4b8d94ca5` and
`private-s3-smoke-1d8d82b4b8d94ca5`. The generated bucket was
`davdeploy-654654474502-us-east-1-32a75065270f7d5ca247`.

### Create and live checks

- Saved Terraform plan: 7 adds, 0 changes, 0 destroys. The account guard read
  caller account `654654474502` before creating resources.
- Monitored create run `nova-platform-s3-create-20261118-1d8d82b4b8d9`:
  Terraform PID `17594`, supervisor PID `17593`, exit code 0. Log:
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-platform-s3-create-20261118-1d8d82b4b8d9.log`.
- AWS readback confirmed all four public-access-block settings `true`, default
  encryption `AES256`, object ownership `BucketOwnerEnforced`, versioning
  `Enabled`, and `PolicyStatus.IsPublic=false`.
- A 33-byte object uploaded and downloaded over HTTPS with expected bucket
  owner `654654474502`. Both local file SHA-256 values matched:
  `2d5d5368503ca5b6c5e8832d115b58e538cdd7776cac80b2fb99cce7bff2be16`.
  S3 reported `AES256`. The exact object version was deleted before bucket
  teardown; `list-object-versions` then returned no versions or delete markers.

### Cleanup and absence

- A saved destroy plan contained only the 7 test resources. The first
  monitored attempt used `terraform destroy <saved-plan>` and failed before
  mutation because Terraform requires `terraform apply <saved-destroy-plan>`.
- The same saved plan then succeeded through monitored run
  `nova-platform-s3-destroyplan-apply-20261118-1d8d82b4b8d9`: Terraform PID
  `22831`, supervisor PID `22830`, exit code 0; 0 added, 0 changed, 7
  destroyed. Log:
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-platform-s3-destroyplan-apply-20261118-1d8d82b4b8d9.log`.
- Independent `s3api list-buckets` lookup returned no matching bucket.
  `terraform state list` returned no resources and `terraform output -json`
  returned `{}`.
- The first failed monitor record is
  `nova-platform-s3-destroy-20261118-1d8d82b4b8d9` (exit code 1); its log
  `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-platform-s3-destroy-20261118-1d8d82b4b8d9.log`
  records only the command-shape error. The successful create/destroy run
  records and isolated local plans/state were retained.

### Limits

This verifies the checked-in private-S3 Terraform root against live AWS for
this one isolated resource set. It does not verify Nova proposal generation,
trusted pricing, hosted approval, the dedicated apply role, CodeBuild
credential brokering, the Nova worker, application health, or recovery. No
Nova customer workload is claimed as applied or certified.

## Apply-build lookup reconciliation hardening — 2026-11-18

Execution type: local source tests and static review; no AWS workload run.

Review found the apply dispatcher ignored malformed build records and did not
require `BatchGetBuilds` to return every ID from the paginated lookup. That
could make an inconclusive search appear empty during restart reconciliation.
The dispatcher now validates project identity, unique build IDs, pagination
tokens, complete batch results, and exactly one canonical durable run ID in
each build record. Malformed or incomplete responses are reported as uncertain
and cannot authorize a replacement dispatch.

- Focused apply tests:
  `/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python -m pytest -q tests/test_nova_apply_clients.py tests/test_nova_apply_workspace.py tests/test_nova_apply_artifacts.py tests/test_nova_apply_role_profile.py tests/test_nova_apply_dispatch.py tests/test_nova_apply_codebuild.py tests/test_nova_apply_access.py tests/test_nova_apply_contract.py`
  — 84 passed.
- Full verification:
  `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python`
  — 1,494 tests passed; Ruff, Actions configuration, OpenAPI snapshot, and
  Compose validation passed. One existing Starlette/httpx deprecation warning.
- This patch did not call AWS or alter the hosted control plane. Fresh-head
  GitHub Actions run `44257747819` passed all seven checks on code commit
  `1a03a577a6420e5f33ef40d44d2fd4432f090334`, including `local-e2e` and
  `cloud-contracts`. The full local clean-room cycle was not rerun for this
  recovery change; existing retained clean-room artifacts were left intact.

No Nova customer workload has been applied or certified by this source test.
