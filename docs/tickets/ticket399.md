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

Backend main is `4bd4c55d1c6343546ca5cc2b70886d15fae36b31` after PR #400;
merged-main CI run `43473967717` passed all seven jobs. PR #397 persists the
encrypted/versioned workspace artifact beside the exact saved plan. Generated
plan approval still fails closed because complete trusted regional pricing is
unavailable; PR #318 is closed and held for account-owner direction. No Nova
customer workload has been applied. The protected untracked `--only-show-errors`
file must remain untouched.

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
- [ ] A plan without complete trusted regional pricing and a persisted approval
  bound to its exact immutable manifest cannot reach a credentialed apply step.
- [ ] Apply verifies and uses the exact saved-plan and workspace versions and
  their manifests; changed, stale, cross-tenant, or mismatched artifacts fail
  closed. Contract and workspace restore checks are implemented. The contract
  also rejects plans without tenant-scoped remote state; apply dispatch and
  execution are not implemented.
- [ ] The worker is idempotent and reports uncertain outcomes for reconciliation
  instead of retrying an apply blindly.
- [ ] Apply uses a separate CodeBuild project and IAM role with explicit denies
  for build override fields; it never reuses `customer_executor`.
- [ ] Apply remains disabled by default and no AWS apply/deployment occurs.
- [ ] Focused tests, full verification, clean-room proof, Terraform validation,
  documentation conventions, diff checks, and required hosted CI pass.

## Acceptance status

- In progress on draft PR #399. The pure preflight contract is implemented;
  exact encrypted, version-pinned artifact download and bounded workspace
  restoration are implemented. Source now also contains a disabled-by-default
  separate apply CodeBuild project, isolated service role, restricted artifact
  paths, an IAM-authenticated credential route permission, fixed run-ID-only
  dispatch policy, and explicit StartBuild override denies. Its fixed buildspec
  exits because the worker is not wired; no API dispatcher, apply credential
  broker, CodeBuild callback consumer, or Terraform execution exists yet.
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

## Tests / validation performed

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

After this source boundary is complete, integrate trusted regional pricing only
after the user clarifies the held PR #318 direction; verify actual customer-role
execution permissions and hosted plan behavior; then prove apply, health,
update, recovery, destroy and independent absence through the hosted API.
