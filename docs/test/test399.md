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

