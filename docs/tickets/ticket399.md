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

Backend `main` is `b2956ac1c56e2e3b7b385a5e0202e81f00f1b87c` (PR #458).
PR #437 adds the isolated customer-side ECS Express pilot; PR #438 adds the
append-only content-hash template collection. PR #438's protected-state plan
was read-only; no template-host apply or live change ran. The PR #399 update
synchronizes with current `main` and places both discovery and default-off Nova
apply-role templates in the same protected content-hash collection. The
current template-host changes remain source-only; no live template-host apply
was run. PR #399 merged as `ff6ffae9ab88a37facbc443dfb35efe8c11b598d` on
2026-11-19; apply/credential gates remain disabled in the hosted runtime.

The owner accepts PR #437's isolated direct-Terraform ECS lifecycle as the
general goal's customer-side plan/apply/health/update/recovery/teardown evidence
under control-plane isolation. It does not exercise Nova generation,
authorization, dispatch, credential issuance, or the dedicated customer apply
role. Apply and credential gates remain disabled; no control-plane mutation,
Nova apply build, customer credential issuance, or Nova-generated customer
workload is claimed. Preserve the protected untracked `--only-show-errors` and
`.venv-pr399/`.

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
- [x] A plan without complete trusted regional pricing and a persisted approval
  bound to its exact immutable manifest cannot reach a credentialed apply step.
  Approval validates the fresh regional price evidence against the persisted
  customer pricing context; apply rechecks evidence freshness, artifact digest,
  and approval binding before STS. A route-level regression now proves that
  even an exactly re-bound approval with unavailable pricing never calls STS.
- [x] The fixed worker verifies and uses exact staged saved-plan and workspace
  versions, their manifest bindings, and tenant-scoped remote state; changed,
  stale, cross-tenant, or mismatched artifacts fail closed. Local tests use
  test doubles; no live CodeBuild or AWS apply has been exercised.
- [x] The durable dispatcher remains idempotent, and the fixed worker records
  uncertain apply outcomes for reconciliation instead of retrying blindly.
- [x] Apply-build recovery returns “no build” only after a complete validated
  CodeBuild search. Malformed or duplicate build IDs, repeated pagination
  tokens, incomplete batch details, and missing/duplicate durable run identity
  fields remain uncertain and fail closed.
- [x] Apply has a separate CodeBuild project and IAM role with explicit denies
  for build override fields; it never reuses `customer_executor`.
- [x] The separate apply credential broker is gated independently and, when
  enabled, issues temporary credentials only to the exact active apply build
  after rechecking current approval, pricing evidence, target role, and AWS
  caller identity. Credentials are audited and returned with no-store headers.
- [x] Source checks the dedicated customer's exact apply-role profile and
  simulates each planned action/resource pair at credential issuance. It also
  supplies a saved-plan-derived STS session policy for the mapped S3 bucket,
  SQS queue, and DynamoDB table types. Unsupported mappings and simulator
  denials fail closed. IAM simulation is supplemental evidence; it does not
  attest every live AWS authorization source or provider resource.
- [x] Apply remains disabled by default and no AWS apply/deployment occurred
  during this source-only work.
- [x] Focused tests, full verification, configured Terraform validation,
  documentation conventions, diff checks, and required hosted CI pass,
  including the fresh-runner `local-e2e` clean integration check.
- [x] A separate full local clean-room cycle passed in an isolated worktree at
  `/private/tmp/davdeploy-pr399-cleanroom-20261117`; its project-specific
  containers were stopped, and its worktree, virtual environment, Compose
  network, database volume, and images were retained. No cleanup target ran.

## Acceptance status

- PR #399 is merged. Source includes the administrator-authorized
  apply-request API, durable run records and worker leases, fixed CodeBuild
  dispatch, exact saved-plan/workspace restoration, tenant-scoped state
  bootstrap, separately gated customer credentials, apply-role onboarding and
  profile verification, an executable fixed worker, encrypted immutable result
  writing, and result reconciliation. The apply-build lookup now treats
  malformed or incomplete CodeBuild responses as uncertain instead of
  permitting a duplicate dispatch. The template-host source now applies the
  append-only key-derived address and `prevent_destroy` policy to both current
  customer templates, including the default-off Nova apply-role template.
- Apply and credential-broker gates remain disabled in hosted runtime. The
  apply-role CloudFormation template validates, but no dedicated customer role
  is installed and no live effective-permission check or customer credential
  issuance has occurred. PR #437 satisfies the general goal's customer-side
  infrastructure lifecycle gate through a separate isolated direct-Terraform
  run; it did not use the Nova apply path. No apply CodeBuild or Nova customer
  workload has run.
- Source verification is strong but not hosted evidence: local `make verify`
  passed 1,494 tests; the focused exact-plan apply suite passed 84; fresh-head
  CI run `44259744310` passed all seven checks on the prior head. The current
  update's focused template-host tests passed (11), Ruff passed, Terraform
  format/validation passed with AWS provider 5.100.0, and documentation
  conventions passed. Fresh-head CI run `44597473742` passed all seven checks on source head `1dea894`.
  The existing full local clean-room proof predates this recovery change; the
  prior code commit's fresh-runner `local-e2e` passed in run `44257747819`.
- Trusted pricing remains limited to the supported resource/settings matrix.
  Unpriced or unsupported material resources still block approval. The direct
  platform-account S3 and ECS tests were isolated customer-side runs. ECS is
  accepted for the general goal's customer-side plan/apply/health/lifecycle
  evidence; neither test proves Nova approval, dispatch, credentials, or a
  Nova-generated workload.

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

### Current-base synchronization — 2026-11-18

- Resolved the S3 policy integration conflicts between PR #399 and current
  `main`, preserving PR #399's account-bound policy checks and main's secure
  transport, default encryption, and bucket ownership checks.
- Merge commit `f677d7a5f36a95472f704f9a15dfd4a7ac6b3fff` brings in main
  `ec937ed257eec5eb0a21f69519df337a90bd79c0`. Focused generated-plan policy
  tests passed (268); full `make verify` passed (1,478); all configured
  `make terraform-validate` roots, documentation conventions, Terraform
  formatting, and diff checks passed.
- Synchronized head `21826297a3c480e0c539f2030b2fe0f8ace67ff9` passed all seven
  required hosted CI checks, including `local-e2e`, in run `44226325612`.
- Ticket evidence update head `744020c6ee45c142cb068c10d410e03485cee183`
  passed all seven hosted checks in run `44226859521`.
- The PR is still draft and apply/credential gates remain disabled. No
  customer target, hosted apply, customer workload, or lifecycle proof is
  available. The hosted result validates source integration only.

### Durable apply worker wake-up — 2026-11-18

- Source commit `5512c5d88c36a8d1d3ef606b7bfd1176d9a8f5c8` now sends the
  non-sensitive SQS wake-up after the apply-run transaction commits. An
  idempotent retry also wakes an existing run while it is still `QUEUED`, so
  a failed message send can be retried without creating another run. The
  durable database remains the worker's source of truth.
- The worker wake helper emits messages only for queued runs. Focused wake-up
  and default-off worker tests passed (2 tests); full `make verify` passed
  (1,479 tests), including Ruff, Actions configuration, OpenAPI snapshot, and
  Compose validation. No customer credentials, CodeBuild runs, AWS applies, or
  customer workload were exercised.
- This closes a source-level queue wake-up gap. It does not enable the worker
  or establish hosted apply, application health, recovery, or cleanup proof.

### Platform-account resource smoke — 2026-11-18

- At the user's direction, account `654654474502` was used as the isolated
  test target while the hosted control plane remained untouched. A copy of
  `customer-workload-private-s3` used local Terraform state and the existing
  AWS profile; no customer role, hosted API, Nova runner, or control-plane
  state was used.
- The test created a uniquely tagged private S3 bucket from a saved plan
  (7 adds, 0 changes, 0 destroys), verified its public-access block, AES256
  encryption, owner-enforced ownership, versioning, non-public policy status,
  and an HTTPS object round-trip, then applied a saved destroy plan (7
  destroys). The initial `terraform destroy <saved-plan>` invocation was
  rejected before mutation; the same plan succeeded through monitored
  `terraform apply <saved-destroy-plan>`.
- Independent account inventory found the bucket absent after cleanup, and
  the isolated Terraform state has no remaining resources. See
  `docs/test/test399.md` for run IDs, logs, and exact evidence. This direct
  smoke test is not a Nova-generated hosted customer workload or certification.
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
profiles. Source now contains a dedicated role profile check and a plan-derived
session policy for the mapped services below. Provisioning and independent
verification of a real customer role, broader effective-permission analysis,
and the full hosted lifecycle evidence remain outstanding. Keep both apply
gates disabled until those gates are met.

### Plan-scoped customer role profile — 2026-11-17

- The source provisions no role. A standalone customer CloudFormation template
  describes a dedicated `davdeployNovaApply-<connection-id>` role with exact
  broker trust, ExternalId, ownership tags, and one fixed inline permission
  ceiling. Broker code assumes the customer role with a role-scoped inspection
  policy and checks the returned account/session identity, trust, tags, session
  duration, boundary, attached policies, and exact inline policy immediately
  before issuing apply credentials.
- Saved Terraform plan JSON is mapped to an inline STS session policy only for
  S3 buckets and listed bucket subresources, SQS queues, and DynamoDB tables.
  Replacement policies scope deletion to the old resource ARN and creation to
  the new ARN. Embedded S3 bucket configuration outside the mapped tag/create
  operations, forced bucket deletion, unsupported types/actions, unscopable
  names, empty apply plans, and policies over the STS 2,048-byte limit are
  marked unavailable. The credential path requires a ready versioned policy
  whose canonical SHA-256 matches the approved manifest. The worker checks the
  broker response carries that same policy version and digest.
- The CloudFormation action ceiling and broker profile are asserted to match.
  Profile verification is a bounded source check, not a complete effective
  permissions attestation: it does not inspect organization SCP/RCP policy,
  resource-based grants, or every service-level authorization nuance. No
  customer role was provisioned or assumed, and no AWS mutation occurred.
- References: [STS AssumeRole session policies](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRole.html),
  [IAM policy evaluation](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html),
  [required S3 API permissions](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-with-s3-policy-actions.html),
  [Terraform plan JSON format](https://developer.hashicorp.com/terraform/internals/json-format),
  and the pinned AWS provider v5.100.0 resource implementations for
  [S3 buckets](https://github.com/hashicorp/terraform-provider-aws/blob/v5.100.0/internal/service/s3/bucket.go),
  [SQS queues](https://github.com/hashicorp/terraform-provider-aws/blob/v5.100.0/internal/service/sqs/queue.go),
  and [DynamoDB tables](https://github.com/hashicorp/terraform-provider-aws/blob/v5.100.0/internal/service/dynamodb/table.go).
- Focused tests passed (94); full `make verify` passed 1,366 tests and its
  Ruff, Actions configuration, OpenAPI, and Compose checks. All configured
  Terraform roots validated, recursive Terraform formatting, documentation
  conventions, and `git diff --check` passed. GitHub Actions run
  `44078718495` passed all seven required checks on implementation commit
  `1a2c507`, including the clean-runner end-to-end job. This evidence update
  is a follow-up documentation commit; that commit's checks also passed in
  run `44095877464`. The credential-route pricing regression added after those
  runs passes the full 1,366-test local verification. GitHub Actions run
  `44103391874` passed all seven checks on implementation commit `ef1e12b`,
  including the fresh-runner end-to-end job. This evidence update gets its own
  fresh-head CI run.
- Apply and broker gates remain disabled. No role, credential, apply build,
  customer workload, or hosted control-plane change was performed. The local
  clean-room cycle remains unrun; its cleanup step would remove retained local
  artifacts without the required explicit deletion approval. Hosted CI's
  clean-runner checks remain required but do not prove AWS behavior.


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

## 2026-11-17 synchronization with Aurora pricing main

- PR #424 merged as `602206ee1fd73b4582015ec30d2b5e472d72baf7`; main CI run
  `44068755226` passed all seven checks. PR #413 is also merged. The PR #399
  source branch was merged with this current main at commit
  `29957e14ce13fb7df7000f3e1a7244cbb1c5154f`; this synchronization is not yet
  pushed to the PR branch.
- PR #399 remains open and draft, and its GitHub base currently points to
  `8c7f1de`. The hosted control plane remains PR #420 (`9951caa`); neither #413
  nor #424 has been deployed. Apply and credential-broker gates remain off.
- On the synchronized worktree, `make verify
  VENV=/Users/adewale/Projects/davdeploy/.venv-pr399` passed 1,342 tests,
  Ruff, Actions configuration, OpenAPI snapshot, and Compose configuration.
  `make terraform-validate`, Terraform formatting, documentation conventions,
  and `git diff --check` passed. Final-head GitHub Actions run
  `44070631960` passed all seven required checks on commit
  `fe86079e5bd917daa99f10e63900093aa25753f4`.
- Read-only AWS checks on 2026-11-17 verified account `654654474502`, no
  matching SageMaker endpoints, models, endpoint configurations, or active
  DavDeploy Batch job definitions, and four matching inactive Batch job
  definitions. The existing SageMaker lineage action and context remain as
  audit evidence; their properties still report `Deleting`. No lineage or
  workload resource was changed. The Terraform run monitor returned `{}`.
- No customer credentials were issued, no CodeBuild apply was started, and no
  customer workload was applied. Dedicated customer apply-role provisioning
  and effective least-privilege validation, followed by hosted apply and full
  lifecycle evidence, remain required.

## Final-head reconciliation — 2026-11-17

- PR #399 is still open and draft at `526220e2662a0bd85b3b2755608929a87535a4b5`,
  based on current `main` `602206ee1fd73b4582015ec30d2b5e472d72baf7`.
- GitHub Actions run `44107574427` passed all seven required jobs on that exact
  head, including `local-e2e`. The source tests include the unavailable-pricing
  credential rejection regression; the run does not exercise AWS credentials,
  CodeBuild apply, or a customer workload.
- Read-only AWS checks verified account `654654474502` in `us-east-1`, no
  dedicated `davdeployNovaApply-*` role, no matching SageMaker endpoint/model/
  configuration, four inactive tagged Batch test definitions, and the retained
  SageMaker lineage action/context. The Terraform run monitor is empty. No AWS
  or control-plane state changed.
- The apply runner and credential gates remain disabled. Customer role setup
  and effective permissions, hosted customer apply, application health,
  recovery, teardown, and independent absence evidence remain unmet. The
  retained local clean-room artifacts and protected files were not removed.

## Customer apply-role onboarding source — 2026-11-17

- Added a separate `nova-apply` customer Quick Create path. It is available
  only to workspace administrators who explicitly acknowledge setup, after
  the same AWS connection is verified and its exact plan-only role is
  `PROFILE_VERIFIED`. The independent
  `DAVDEPLOY_NOVA_APPLY_ROLE_SETUP_ENABLED` runtime flag and published template
  URL are required; the infrastructure variable defaults off.
- The setup link reuses the connection ExternalId, targets the deterministic
  `davdeployNovaApply-<connection-id>` role, returns a content-hash CloudFormation
  template URL, and sets no-store response headers. The audit record contains
  account and stack name only. The customer must review and create the stack in
  their AWS account; the API does not provision it or claim verification.
- The public template host now publishes the separate apply-role template as
  its own content-hash S3 object and exposes the URL as an output. Existing
  discovery template objects remain unchanged. Terraform configures the API
  broker ARN and setup URL independently from both apply gates.
- Focused tests cover default-off behavior, administrator authorization,
  verified plan-role prerequisites, exact account/role/ExternalId bindings,
  audit redaction, API no-store headers, and template-host/config contracts.
  The route checks the customer role profile later during exact active-build
  credential issuance; this change does not add live role verification.
- The role's profile and plan-scoped policy remain limited to mapped S3,
  SQS, and DynamoDB resources. Effective permission gaps and broader module
  support remain open. This does not close the hosted customer lifecycle gate.
- Full `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python`
  passed 1,373 tests, Ruff, Actions configuration, OpenAPI snapshot, and
  Compose validation on the complete current source changes.
- GitHub Actions run `44123626109` passed all seven required checks on
  implementation commit `3967b48d105934eb19d055cc78bb99d0f88281ed`, including
  the fresh-runner `local-e2e` job. No customer AWS role or workload was used.

### Per-plan IAM permission simulation — 2026-11-17

- Immediately before returning apply credentials, the API now submits every
  exact action/resource pair from the approved plan session policy to AWS
  `SimulatePrincipalPolicy`. It supplies that session policy as the simulated
  permissions boundary and requires one `allowed` result per pair with no
  missing context values. An API error, denial, omitted/duplicate result, or
  invalid pagination fails credential issuance closed.
- The customer role and verification-session policy grant
  `iam:SimulatePrincipalPolicy` only for that same role ARN. The plan session
  has an explicit deny outside its planned actions/resources, so this
  inspection permission is unavailable to the Terraform worker session.
- Profile version `nova-apply-role-profile.v2` hashes the role profile, exact
  session-policy digest, and simulated action/resource pairs. The audit path
  stores only that digest/version; policy values and credentials are not
  logged.
- Focused tests cover allowed pairs, denied permissions, wildcard scope,
  missing simulator/context, and the fixed CloudFormation permission ceiling.
  Full local verification passed 1,377 tests, Ruff, OpenAPI snapshot, Actions
  configuration, and Compose validation. These use test doubles; no customer
  role was available for a live simulation. AWS CloudFormation
  `validate-template` accepted the updated template and reported the expected
  named-IAM capability; no stack was created.
- AWS documents that the simulator omits resource control policy support,
  can differ from live authorization, and does not simulate resource policies
  for IAM roles. This is a fail-closed preflight, not proof of actual apply
  permissions or customer lifecycle.
- References: [SimulatePrincipalPolicy API](https://docs.aws.amazon.com/IAM/latest/APIReference/API_SimulatePrincipalPolicy.html),
  [IAM simulator behavior and limitations](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_testing-policies.html),
  and [role-session policy evaluation](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html).
- Source commit `d12ee73cbc7aff0f07026094e195c36ba4325449` passed all seven
  required GitHub Actions checks in run `44128923407`, including the fresh
  runner `local-e2e` and Terraform validation jobs.

### Final documentation-head CI and inventory — 2026-11-17

- Documentation commit `e0df560b99364f82e5a1caf072d5b9e0bd74f0d0` passed all
  seven required GitHub Actions checks in run `44124793410`, including
  `local-e2e` and Terraform validation. This verifies the exact current PR
  head; it does not verify live AWS role permissions or a customer workload.
- PR #399 remains open and draft, based on current `main`
  `602206ee1fd73b4582015ec30d2b5e472d72baf7`, with no review requests and a
  clean merge state. Apply and credential-broker gates remain disabled.
- Read-only AWS inventory again verified account `654654474502` in
  `us-east-1`. SageMaker endpoint, model, and endpoint-configuration lists
  were empty; the four tagged DavDeploy Batch definitions remain inactive.
  The Terraform run monitor returned `{}` and no Terraform apply/destroy
  process was active. No AWS resource, role, credential, hosted control-plane
  state, or lineage evidence was changed.
- Customer-role provisioning and effective permission verification still
  require a customer target account and the approved onboarding/runtime path.
  The current handoff boundary prohibits creating a target role or changing
  the hosted control plane, so those gates remain unmet. No Nova customer
  workload has been applied or certified.

## Data policy wildcard bounds — 2026-11-17

- The actual-plan IAM policy reviewer now rejects wildcard action patterns,
  including service-level forms such as `s3:*`, `sqs:*`, and
  `dynamodb:Put*`. Existing wildcard role-assumption checks retain their
  specific denial finding. Allow statements using `NotResource` are also
  denied because their inverse scope cannot be safely bounded. S3 and SQS
  resource policies reject external or unverified principals and also deny
  inverse `NotAction` grants, even when a principal is specific.
- S3, SQS, and DynamoDB permissions also fail closed when a resource scope is
  unbounded. Exact resource ARNs remain usable; S3 object access may use the
  exact bucket's object suffix, and DynamoDB index access may use the exact
  table's index suffix. Broad buckets, queues, tables, and wildcard resource
  patterns are denied. Incomplete or unrecognized ARN shapes fail closed;
  IAM may expand omitted ARN fields to wildcards.
- S3 bucket and SQS queue resource policies accept only same-account AWS
  identities or verified AWS service principal shapes. Cross-account AWS
  principals are currently denied; the source does not yet model an explicit
  cross-account sharing contract or prove the other account's policy. Their
  `Resource` values must also be complete, service-matching ARNs with bounded
  scopes; an S3 bucket policy cannot use `Resource: "*"` or an incomplete ARN.
- Regression tests exercise wildcard actions, inverse action/resource scopes,
  external resource-policy principals, incomplete and unbounded resource ARNs,
  and allowed exact bucket, object, queue, table, and index scopes. Full local
  verification passed 1,402 tests,
  Ruff, Actions configuration, OpenAPI snapshot, and Compose validation.
- This is source and local test evidence. No live customer role was available
  for authorization checks. It does not establish effective AWS permissions
  or a customer workload; both apply gates remain disabled.
- Follow-up hardening also rejects wildcard or malformed `Resource` ARNs in
  S3 bucket and SQS queue resource policies. Commit
  `9140d45431847cb171ec0bad758fdf69b5e7115c` passed all seven required checks
  in GitHub Actions run `44179449868`, including `local-e2e` and
  `cloud-contracts`.
- Read-only recheck verified AWS account `654654474502`, no
  `davdeployNovaApply-*` role or matching SageMaker endpoint/model/config, and
  four tagged DavDeploy Batch definitions still `INACTIVE`. The Terraform
  monitor was empty. No AWS resource, control-plane runtime, or lineage
  evidence changed.
- Source commit `7b2b84b` passed all seven required GitHub Actions checks in
  run `44177455097`, including fresh-runner `local-e2e` and Terraform
  validation.
- Source commit `24fa893fdd3d77358861e2bc1451dd4b791fbd0e` passed all seven
  required GitHub Actions checks in run `44134431454`, including `local-e2e`
  and Terraform validation.
- Follow-up source commit `9a241e1` adds fail-closed handling for IAM Allow
  statements with `NotResource`. Fresh-head run `44140537111` passed all seven
  required checks, including `local-e2e` and Terraform validation.
- Source commit `33cd509` extends the same denial to S3 bucket and SQS queue
  resource policies with otherwise specific principals. Fresh-head run
  `44142215551` passed all seven required checks, including `local-e2e` and
  Terraform validation.
- A full `make local-proof VENV=.venv` cycle passed in an isolated worktree at
  `9739dd4b8df2785dfd782f710bfd216b97e7b529`: smoke, API contract, customer-plan
  fixture E2E, trace check, and 1,396 tests. Its project containers are stopped;
  the worktree, virtual environment, Compose network, database volume, and
  images are retained. This is local fixture evidence, not hosted customer
  apply or lifecycle proof.
- References: [IAM ARN formats and wildcard behavior](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference-arns.html),
  [IAM policy principals](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_principal.html),
  [S3 IAM resource ARNs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security_iam_service-with-iam.html),
  [SQS cross-account access requirements](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-overview-of-managing-access.html),
  and [DynamoDB table/index IAM resources](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/iam-policy-specific-table-indexes.html).

## 18 November 2026 synchronization after PR #433

- PR #399 is synchronized with backend `main` `9bef966a474d059b2d7e9d123da858707628b07b` through merge commit `4e123069271add460e550ee8ebba17ed0d31a3a6`. The merge preserves the account-bound S3/SQS policy checks and adds PR #432/#433's CloudFront viewer/origin TLS rules.
- Focused generated-plan policy tests passed (232); full `make verify` passed (1,442 tests). Documentation conventions, `git diff --check`, and recursive Terraform formatting passed.
- PR #399 remains open/draft with apply and credential gates disabled. All seven checks passed on synchronized head `0d4d584c4da63ad101854087956f2d16ad94245b` in run `44215860757`. No AWS, Terraform, hosted runtime, customer credential, or customer workload operation occurred.

## Apply-build lookup reconciliation hardening — 2026-11-18

- Review found that `find_build_by_run_id` skipped `ValueError` records and
  accepted incomplete `BatchGetBuilds` responses. An inconclusive lookup could
  therefore look like no build existed and allow a duplicate dispatch attempt.
- The dispatcher now validates project-prefixed unique build IDs, complete
  pagination with non-repeating tokens, complete batch results, exact build
  identities, and exactly one canonical durable run ID field per build. Any
  malformed or incomplete response raises an uncertain `build_start` result;
  only a complete valid search can return no match.
- Focused exact-plan apply suite: 84 passed. Full `make verify` passed with
  1,494 tests, Ruff, Actions configuration, OpenAPI snapshot, and Compose
  validation. Documentation conventions and diff checks passed on the final
  evidence update. No AWS role, credential, apply build, customer
  workload, or hosted control-plane state was changed.
- The full local clean-room cycle has not been rerun for this recovery change.
  Fresh-head CI run `44257747819` passed all seven checks on code commit
  `1a03a577a6420e5f33ef40d44d2fd4432f090334`, including `local-e2e` and
  `cloud-contracts`. Existing retained local clean-room artifacts were not
  cleaned up.

### Customer-side AWS attempt — 2026-11-18

- At the user's direction, a fresh same-account customer sandbox was created
  with isolated local Terraform state. The hosted control plane and its state,
  runtime, and queues were not used or changed.
- Terraform create run `nova-customer-test-create-20261118-a1` succeeded with
  21 resources. The follow-up App Runner service attempt failed because AWS
  returned `Account 654654474502 can't create new App Runner services`; no
  service health or hosted Nova execution was established.
- After the user's explicit cleanup authorization, the exact 21-resource
  destroy plan succeeded in run `nova-customer-test-destroy-20261118-a1`.
  Independent AWS absence checks passed and local Terraform state is empty.
- Full execution detail and limitations are recorded in
  `docs/test/test399.md`. PR #399 remains draft; this direct customer-account
  attempt does not meet its hosted Nova apply/lifecycle acceptance gates.
