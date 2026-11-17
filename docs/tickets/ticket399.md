# ticket399 — separate Nova exact-plan apply boundary

PR: https://github.com/Bepoadewale/davdeploy/pull/399
Branch: `feat/nova-exact-plan-apply-399`

## Problem / goal

Nova currently preserves and verifies the exact saved plan and Terraform
workspace but has no safe generic apply path. Add a distinct, disabled-by-default
apply boundary that can consume only the exact fully priced and administrator-
approved plan and workspace. It must remain separate from both the plan-only
CodeBuild project and `customer_executor`.

## Current repo state

Backend `main` is `8c7f1deab9e9b9865a25d0fffaf87be2066b8ea4` after PRs #422 and
#423. The hosted control plane remains on PR #420 commit
`9951caa9244128b1551fea3af66b1bdbf884c800`, deployed by plan run `43981566184`
and apply run `43982396577`; PR #422 is source-only. PR #399 is open and draft,
now based on current `main` through merge commit `e01eee2fbb395ef4421bc30c6459ce6cf4f89a8a`.
Apply gates remain disabled. Mainline has bounded regional price evidence for
supported S3, SQS, RDS MySQL, Lambda/API, and DynamoDB configurations, but
material unsupported or unpriced resources still block approval and PR #318
remains closed/held. No Nova customer workload has been applied. The protected
untracked `--only-show-errors` and `.venv-pr399/` must remain untouched.

## Research / references used

- `apps/api/src/davdeploy/nova_plan_codebuild.py`
- `apps/api/src/davdeploy/nova_plan_dispatch.py`
- `apps/api/src/davdeploy/nova_plan_credentials.py`
- `apps/api/src/davdeploy/generated_plan_artifacts.py`
- `apps/api/src/davdeploy/service.py` (`approve_generated_plan_artifact`)
- `infrastructure/terraform/serverless-control-plane/main.tf`
- `infrastructure/terraform/terraform-operations-bootstrap/main.tf`
- [CodeBuild StartBuild API](https://docs.aws.amazon.com/codebuild/latest/APIReference/API_StartBuild.html)
- [CodeBuild IAM condition keys](https://docs.aws.amazon.com/codebuild/latest/userguide/action-context-keys.html)
- [Terraform apply command and saved-plan behavior](https://developer.hashicorp.com/terraform/cli/commands/apply)

## Work planned for the PR

- Add a fixed apply worker that verifies the durable approved-manifest record,
  complete fresh pricing evidence, exact saved-plan and workspace object
  versions/digests, tenant/target binding, and current approval authorization.
- Restore only the bounded archived plan-time workspace, verify the pinned
  Terraform/provider toolchain and lockfile, then invoke only fixed saved-plan
  apply arguments. Never regenerate a plan at apply time.
- Add an apply-specific CodeBuild project, service role, artifact access,
  credential issuance and callback/idempotency boundary. It must not reuse the
  plan-only project or `customer_executor`.
- Deny all caller-supplied buildspec, source, role, and execution environment
  overrides; pass only a server-generated durable run ID.
- Keep all apply feature gates false. No Terraform apply, deployment, or AWS
  mutation is in scope for this PR.

## Acceptance criteria

- [x] A strict request contract binds the build/run identity, tenant, target,
  source plan run, administrator approval, pricing status, and exact versioned
  plan/workspace object digests and ownership keys.
- [x] Terraform state bootstrap recognizes an apply build only when a durable
  apply-run record binds the exact project, role, build ID/ARN, run ID, active
  status, current workspace administrators, verified AWS target, remote-state
  scope, saved-plan manifest, approval, and complete-pricing marker. Schema
  version 35 adds the apply-run record and credential binding. The marker check
  does not establish pricing provenance or freshness; trusted pricing remains
  an unmet gate and this path is not enabled.
- [x] Customers can retrieve safe apply-run status by run ID or paginated
  project/revision history. Tenant and requester visibility is enforced; raw
  request/result metadata, artifact locations, and build internals are omitted.
  The response distinguishes runner status from application health or confirmed
  cleanup.
- [ ] A plan without complete trusted regional pricing and a persisted approval
  bound to its exact immutable manifest cannot reach a credentialed apply step.
- [x] The fixed worker verifies and uses exact staged saved-plan and workspace
  versions, their manifest bindings, and tenant-scoped remote state; changed,
  stale, cross-tenant, or mismatched artifacts fail closed. Local tests use
  test doubles; no live CodeBuild or AWS apply has been exercised.
- [x] The durable dispatcher remains idempotent, and the fixed worker records
  uncertain apply outcomes for reconciliation instead of retrying blindly.
- [x] Apply has a separate CodeBuild project and IAM role with explicit denies
  for build override fields; it never reuses `customer_executor`.
- [x] The separate apply credential broker is gated independently and, when
  enabled, issues temporary credentials only to the exact active apply build
  after rechecking current approval, pricing evidence, target role, and AWS
  caller identity. Credentials are audited and returned with no-store headers.
- [x] Apply remains disabled by default and no AWS apply/deployment occurred
  during this source-only work.
- [ ] Focused tests, full verification, clean-room proof, Terraform validation,
  documentation conventions, diff checks, and required hosted CI pass.

## Acceptance status

- In progress on draft PR #399. The pure preflight contract is implemented;
  exact encrypted, version-pinned artifact download and bounded workspace
  restoration are implemented. Source now also contains a disabled-by-default
  separate apply CodeBuild project, isolated service role, restricted artifact
  paths, an IAM-authenticated credential route permission, fixed run-ID-only
  dispatch policy, and explicit StartBuild override denies. A fixed worker and
  CodeBuild buildspec are now present in source, but remain behind the default-
  off project and credential gates. They have not run against AWS. Dedicated
  customer role setup/effective permissions and callback result verification
  remain incomplete in the committed source at the time of this snapshot.
  The role also has project/build-scoped permission and trusted project
  settings for remote-state credential bootstrap, which exact-plan apply needs;
  The state API now has an apply-run authorization path, but no apply-request
  API or caller creates those records yet. Terraform validate passed for both affected roots, and focused apply
  contract/workspace/infrastructure tests passed (19 tests). These checks do
  not prove AWS IAM behavior or hosted apply.
- The state-credential path rechecks the immutable approval/artifact,
  pricing-complete marker, current administrator roles, latest revision and
  expiry, verified customer account, target, and tenant-scoped remote-state
  digest before issuing or reusing state credentials. Credentials bind both
  the source plan run and apply run, and become unusable when that exact
  CodeBuild build is no longer active. Runtime gates remain disabled, and no
  apply-request API or worker creates these records yet.
- Read-only apply-run detail and project-history routes expose the durable
  record with organization/project/revision scoping, requester/admin
  visibility, bounded cursors, and a fixed safe field projection. No route
  creates or dispatches apply runs; these routes have no real customer
  execution data until dispatch and lifecycle observation are implemented.

### Apply credential broker — 2026-11-17

- Added the internal `POST /api/v1/nova-apply/credentials` route. It requires
  both apply-runner readiness and a separate default-off credential-broker
  gate, the configured apply CodeBuild role/project, the exact active build,
  an unexpired current approved manifest with complete pricing evidence,
  current workspace administrators, and a verified customer execution role
  in the exact target account.
- The broker assumes that customer role using the stored ExternalId reference,
  verifies the returned STS identity and account, records an audit event before
  returning 15-minute credentials, and sets `Cache-Control: no-store` and
  `Pragma: no-cache`. The Terraform variable and Lambda environment setting
  default the broker to disabled. It derives only the dedicated
  `davdeployNovaApply-<connection-id>` role and never falls back to the legacy
  `execution_role_arn` administrator-pilot role.
- Focused route validation: `test_state_bootstrap_binds_exact_plan_apply_to_active_approved_build`
  passed, covering disabled-by-default behavior, valid issuance, wrong-account
  and expired credential rejection, and revoked administrator rejection. Ruff, Terraform
  formatting, and `git diff --check` passed. `make verify
  VENV=/Users/adewale/Projects/davdeploy/.venv-pr399` passed (1,291 tests), and
  `make terraform-validate` passed all configured roots.
- This route is source-only. No credentials were issued to a real build and no
  AWS apply/deployment occurred. Provisioning and least-privilege validation of
  the dedicated customer role remain incomplete; the fixed worker/buildspec,
  callbacks, hosted apply, health, recovery, destroy, and absence proof remain
  incomplete.

### Current-base synchronization — 2026-11-17

- Merged current `main` (`9951caa9244128b1551fea3af66b1bdbf884c800`) into the
  PR branch at merge commit `57f061f24cbb98dba12edd6b7a0e99406f9d5398`.
- On that merged head, `make verify VENV=/Users/adewale/Projects/davdeploy/.venv-pr399`
  passed (1,298 tests), `make terraform-validate` passed all configured roots,
  and documentation conventions, Terraform formatting, and diff checks passed.
- Fresh-head GitHub CI is pending after push. PR #399 remains a draft; apply
  and broker gates remain disabled. Dedicated role provisioning and hosted
  apply/lifecycle proof remain incomplete.

### Exact apply input contract — 2026-11-17

- Added internal `POST /api/v1/nova-apply/input`, available only when the apply
  runner is enabled. API Gateway authenticates it with AWS IAM and overwrites
  the caller header. The handler requires the durable apply ID, exact active
  CodeBuild role/project/build, current approved manifest and pricing,
  administrator authorization, and a matching immutable request digest.
- The response is validated against `davdeploy.nova-apply-request.v1`, including
  exact versioned plan/workspace keys, tenant-scoped remote state, pricing,
  approval and a five-minute authorization expiry. The response is audited and
  returned with no-store headers. Terraform creates the IAM route and
  integration only with the apply runner gate.
- Focused test-double checks cover the disabled gate and successful contract
  validation; no live build or AWS credentials were used. This endpoint is
  source-only. The fixed buildspec still exits, and role provisioning, artifact
  restore in CodeBuild, apply execution, callbacks and lifecycle proof remain
  outstanding.
- Current local checks passed: `make verify` (1,298 tests), all configured
  `make terraform-validate` roots, Ruff, OpenAPI, Compose, documentation
  conventions, Terraform formatting, and `git diff --check`. Fresh-head GitHub
  CI remains required after push.
- PR head `d239e37` (2026-11-15) added a fixed-project CodeBuild
  dispatcher with run-ID-only overrides, bounded build reconciliation, and
  explicit uncertain outcomes. It is not called by the product service and
  does not create durable apply-run rows. The apply buildspec remains
  fail-closed; no Terraform apply is executable through this path.
- Hosted CI run `43696075794` failed in Ruff and consequently in `local-e2e`.
  The next head fixed lint but run `43696455615` then exposed three dispatcher
  test failures: the fake swallowed an empty response, omitted a second build
  from its lookup page, and allowed a non-canonical uppercase UUID through.
  The current follow-up corrects the response-type handling, enforces canonical
  run IDs, and repairs those fixtures. Dispatcher tests pass locally (11);
  full `make verify` passes (1,260 tests). A clean-room attempt in a new
  temporary worktree could not start because Docker Compose returned HTTP 500
  on its initial cleanup command. Fresh-runner hosted `local-e2e` remains
  required.
- Integrated follow-up head `4d81b7e` passed all seven required GitHub CI jobs
  in run `43696947968`, including the fresh-runner `local-e2e` clean-room
  workflow. This validates source integration and tests; it does not execute
  the disabled apply worker or a customer workload.
- Current PR head `498e5ca` adds explicit regressions for empty CodeBuild
  responses and ambiguous build lookup. All seven required checks passed in
  run `43697213134`, including the fresh-runner `local-e2e` job.

## Tests / validation performed

- After PR #406 merged, PR #399 was synchronized with current `main` through merge commit `af1c19356b3d93df3ca35431771c9e0e7c119521`. All seven required CI jobs passed for this synchronized head in run `43576086458` (2026-11-14). This updates source integration evidence only; apply remains unwired and disabled.

- PR #398 merged-main CI `43460570905` passed all seven jobs.
- Focused contract and workspace tests: `14 passed`; Ruff passed on the
  changed files. After adding remote-state scope checks, focused tests pass:
  `16 passed`. The workspace tests use a local fake S3 client and do not
  establish AWS behavior.
- Focused apply contract, workspace, and infrastructure-boundary tests:
  `19 passed`; changed test Ruff checks, Terraform fmt, validate for both
  affected roots, and `git diff --check` passed. The CodeBuild project remains
  disabled by default and its fixed buildspec deliberately fails closed.
- Current full `make verify`: `1,111 passed`; Ruff, Actions configuration,
  OpenAPI, and Compose checks passed. `make terraform-validate` passed across
  the configured Terraform roots. Documentation conventions passed for PR
  #399. These are local source checks only.
- Draft PR #399 head `5989d08` passed all seven required CI jobs in run
  `43476451184`. CI does not enable the feature or prove a live customer apply.
- The remote-state bootstrap permission addition passed 19 focused contract,
  workspace, and apply-infrastructure tests; both affected Terraform roots
  validated and formatting, docs conventions, Ruff, and diff checks passed.
  The state API apply-run binding remains unimplemented.
- Full `make verify`: `1,108 passed`; Ruff, Actions config, OpenAPI, and
  Compose checks passed. One existing Starlette/httpx deprecation warning.
- Schema migration 35, apply-run state-credential authorization, isolated
  Compose URL support, and related tests pass `make verify` (1,113 tests),
  Ruff, Actions configuration, OpenAPI, Compose, documentation convention,
  and `git diff --check`. The local fixture proof is recorded in
  `docs/test/test399.md`; it is not hosted AWS apply evidence.
- Hosted PR #399 checks `43465074051` passed all seven jobs for the earlier
  contract-only head; they do not cover the workspace restore changes.
- Hosted PR #399 checks for artifact restoration commit `ea25be2` passed all
  seven jobs in run `43466898962`.
- Final-head PR CI for `bc0cb47` passed all seven jobs in run `43467601843`.
  Hosted clean-room CI validates the source tree but is not AWS execution
  evidence.
- Documentation follow-up commit `be75264` passed all seven CI jobs in run
  `43468478089`.
- Apply-run status detail/history tests: `2 passed`; Ruff passed on the
  changed runtime and test files. Full `make verify` passed (1,115 tests),
  including Ruff, Actions configuration, OpenAPI snapshot, and Compose checks.
  The isolated local proof for the status API passed in a fresh Compose
  project; final error sanitization and cursor-integrity guards also passed
  the focused tests and full suite.
- Apply-run state credential binding commit `34ac2471f9d0c73925b889ae9baccf2777906082`
  passed all seven final-head checks in run `43484459545`. PR #399 remains a
  draft; these source and CI checks do not establish a hosted customer apply.

## Evidence files produced

- `docs/tickets/ticket399.md`
- The focused contract test is `tests/test_nova_apply_contract.py`.
- The artifact restoration helper and tests are
  `apps/api/src/davdeploy/nova_apply_workspace.py` and
  `tests/test_nova_apply_workspace.py`.
- `docs/test/test399.md` records the isolated local fixture and non-AWS
  boundary evidence.

## Boundaries

This PR must not enable hosted apply or claim that the customer apply lifecycle
is ready. Missing or untrusted pricing remains a hard approval blocker. No
AWS deployment or workload mutation is authorized by this PR.

## Follow-up work

Trusted pricing is now integrated for the currently supported proposal
profiles. The next apply dependency is a dedicated customer apply role whose
effective permissions are checked at credential issuance and constrained to
the approved Terraform plan. The current broker derives the role ARN and
checks its account/session identity, but it does not attest or scope the role's
permissions. Keep both apply gates disabled until that permission boundary and
the full hosted lifecycle evidence are complete.


## Hosted handoff update — 2026-11-14

- Main release `01895d6` is deployed; the hosted API is healthy and the
  Nova plan-only runner is active. This did not deploy or certify a customer
  workload.
- Mainline now has revision-bound S3 and SQS price evidence. AWS Price List
  currently returns `$0.016/hour` for RDS MySQL `db.t4g.micro` Single-AZ
  and `$0.115/GB-month` for MySQL GP3 storage in `us-east-1`; those lookups
  are not yet integrated into Nova pricing and do not cover backup, transfer,
  or other material costs.
- The apply CodeBuild project in this PR intentionally fails closed with an
  unwired buildspec. Do not enable or describe it as an operational apply path.
- GitHub synchronized the PR branch with current mainline. Follow-up fixes for
  the strict pricing evidence shape and the fixed apply-role state bootstrap
  passed all seven checks in run `43638007038` on commit
  `44fa76f6e3e85fa0bddce26ddc0f25e724b03209`.
- Keep this PR in draft until the exact-plan worker is wired and the pricing,
  policy, and hosted lifecycle gates in the Nova goal are met. No local checks
  were run for this update.


## Hosted dispatcher adapter progress — 2026-11-15

Added `NovaExactPlanApplyDispatcher` and focused tests for fixed-project CodeBuild starts, the sole durable run-ID override, exact project/build/ARN identity, bounded lookup, ambiguous matches, and uncertain start outcomes. Hosted CI run `43697213134` passed all seven required jobs on commit `498e5cae8989a8ac2547e133fe2b96b2b11a768b`.

The dispatcher is not connected to a durable apply queue yet. The API worker still does not create/reconcile apply builds, and the CodeBuild buildspec remains fail-closed. The feature flag remains disabled.

## 2026-11-15 exact-plan request and worker dispatch

Status: in progress; the request and dispatch foundation is implemented and CI verified.

- Added an administrator-only, idempotent apply request bound to the approved manifest, current approved revision, target account/region, saved-plan digest, and execution-workspace digest.
- Added durable worker lease claiming for queued apply runs. The worker dispatches only to the configured fixed CodeBuild project with the durable run ID and idempotency token.
- Added direct CodeBuild status reconciliation. Ambiguous dispatches and failed builds enter RECONCILIATION_REQUIRED; a successful build is APPLIED_UNVERIFIED, not healthy.
- The readiness gate remains disabled until the executable apply buildspec and full lifecycle verification are complete.
- Hosted CI run 43767690333 passed all seven jobs for code commit 4a8ee3d32ac3fdc407f37e2170a2775c06549e9c.
- No AWS apply was run. This is not evidence of a deployed worker or a Nova-generated workload.

Next: implement and verify the executable fixed-project buildspec, then prove credential issuance, callback reconciliation, and controlled recovery in the hosted path.

## 2026-11-16 mainline synchronization

- Synchronized the remote PR branch with current `main` using merge commit
  `d801793ebffe8ccbdd59af13bd49e7852551e1c2`. The merge is conflict-free and
  includes PRs #412–#416; the PR remains a draft and the apply gate remains
  disabled.
- Focused tests for apply contracts, dispatch, workspace restore, run history,
  Terraform state, and generated-plan review: 119 passed.
- `make verify VENV=/Users/adewale/Projects/davdeploy/.venv-pr399`: 1,291
  passed; Ruff, Actions configuration, OpenAPI snapshot, and Compose checks
  passed. Documentation conventions and `git diff --check` passed.
- `make terraform-validate` passed seven roots, then stopped because Terraform
  could not reach `registry.terraform.io` while initializing the next provider.
  This is an incomplete local validation; fresh-runner CI remains required.
- A full local clean-room cycle was not run. It would require cleaning its
  generated `.venv`, `.local`, Compose containers, network, and volume; those
  deletions are not approved. No AWS call, deployment, apply, or customer
  workload action occurred.

## 2026-11-17 apply-input and artifact-isolation follow-up

- Added the internal `POST /api/v1/nova-apply/input` contract. It rechecks the
  fixed active CodeBuild build, current approved manifest and pricing,
  administrators, request digest, exact artifact versions, tenant state scope,
  and a five-minute authorization window. The response is audited and
  no-store. API Gateway IAM authentication supplies the trusted caller identity.
- The API stages only those exact source plan/workspace versions to encrypted,
  versioned keys under the active apply build. It validates the source
  object's owner, version, KMS key, SHA-256 checksum, run ID, and manifest
  digest before copying; destination metadata binds the apply run and source
  object version. An audit record is committed before staging.
- The apply CodeBuild role now reads staged artifacts only within its own
  build prefix. It no longer has S3 read access to all source plan artifacts.
  The API's copy permission is limited to saved plans/workspaces and staged
  keys; the build role still has no Terraform-specific AWS permissions.
- Local focused checks passed (23 tests), including source metadata rejection,
  exact staged-prefix validation, workspace restore, active-run API contract,
  and Terraform IAM assertions. `make verify
  VENV=/Users/adewale/Projects/davdeploy/.venv-pr399` passed (1,301 tests),
  and `make terraform-validate` passed for all configured roots. Ruff,
  documentation conventions, Terraform formatting, OpenAPI, Compose config,
  and `git diff --check` passed. GitHub CI run `43988367335` passed all seven
  jobs on the preceding commit; a fresh-head run is required after this change.
- This is not yet an executable apply worker: the CodeBuild buildspec remains
  fail-closed, and role provisioning, Terraform execution, callback
  reconciliation, application health, update/recovery, destroy, and absence
  evidence remain unmet. Feature and credential gates remain disabled; no real
  artifacts were copied, credentials issued, CodeBuild apply started, or AWS
  resources changed.

## 2026-11-17 fixed apply worker and result reconciliation

- The gated CodeBuild buildspec loads the pinned immutable application archive,
  verifies Terraform 1.14.7 against its SHA-256 digest, and invokes the fixed
  `davdeploy.nova_apply_codebuild` entrypoint. The worker validates the exact
  build/run contract, restores only the staged plan/workspace versions,
  rechecks tenant state binding, initializes the remote HTTP backend, and
  applies only `terraform apply <saved.tfplan>`.
- The worker requests customer credentials only after restore and state init,
  verifies the exact temporary role identity, and checks that both state and
  customer credentials outlast the bounded 12-minute apply timeout plus a
  30-second margin. Timeout, nonzero apply, and result-write uncertainty
  require reconciliation. The result object is encrypted, versioned, and
  created conditionally so the same build cannot overwrite it.
- The completion reconciler accepts `APPLIED_UNVERIFIED` only after reading
  the exact build-scoped result object and validating its object version,
  checksum, KMS metadata, run/build identity, saved-plan/workspace digests,
  target, state scope, and toolchain against durable records. Missing or
  mismatched evidence remains `RECONCILIATION_REQUIRED`. Build success does
  not mean application health.
- The worker readiness variable remains closed unless both the separate apply
  runner and credential broker flags are enabled. Both flags default false.
  Customer role creation/effective permission validation and full lifecycle
  evidence remain missing.
- Evidence is test-double and source validation only: no real credential was
  issued, no CodeBuild apply was started, and no customer AWS resource was
  created or changed. See `docs/test/test399.md` for validation and limitations.

## 2026-11-17 final-head worker evidence

- Source commit `33727c46a025a2440a7393d6a6d331dc84917058` adds the fixed
  Terraform apply worker, pinned toolchain verification, exact staged artifact
  restore, customer-role identity check, bounded apply, encrypted conditional
  result write, and fail-closed result reconciliation.
- Local `make verify` passed (1,312 tests), Terraform validation passed all
  configured roots, and formatting, Ruff, OpenAPI, Compose, documentation, and
  diff checks passed. No AWS role credentials were issued and no apply build
  or customer workload was started.
- Fresh-head GitHub run `43995850553` passed all seven required checks.
  PR #399 remains open and draft; the runner and credential broker remain
  disabled. Passing source CI does not prove a customer apply or health.
- Remaining: create and verify the dedicated customer apply role with
  proposal-bound least-privilege permissions; then establish hosted apply,
  health, update/recovery, destroy, and independent absence evidence.

## 2026-11-17 synchronization with current main

- PR #399 branch `feat/nova-exact-plan-apply-399` merged current `main`
  `8c7f1de` through merge commit `e01eee2`. This brings in PR #422 plan-role
  profile verification and PR #423's source/deployed status reconciliation;
  neither changes the hosted release. PR #399 remains open and draft.
- The `main.py` import conflict was resolved by retaining both the apply
  pricing-evidence imports and the plan-role verifier import.
- Current local verification passed 1,332 tests, Ruff, Actions configuration,
  OpenAPI, Compose configuration, documentation conventions, and diff checks.
  The apply reconciliation test now expires its SQLAlchemy identity-map cache
  before reading the committed bulk-update result.
- Final-head GitHub CI run `44060781429` passed all seven required checks.
- No AWS mutation, Terraform operation, customer credential issuance, apply
  build, or customer workload occurred. The apply runner and credential gates
  remain disabled. Dedicated apply-role verification and hosted lifecycle
  evidence remain outstanding.

