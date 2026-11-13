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

Backend main is `bded74a38bea677ed8dc8d9e4dad470892a96a3c` after PR #398;
merged-main CI run `43460570905` passed all seven jobs. PR #397 persists the
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
- Official CodeBuild `StartBuild` override controls and Terraform saved-plan
  behavior, recorded in the private handoff.

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
- [ ] A plan without complete trusted regional pricing and a persisted approval
  bound to its exact immutable manifest cannot reach a credentialed apply step.
- [ ] Apply verifies and uses the exact saved-plan and workspace versions and
  their manifests; changed, stale, cross-tenant, or mismatched artifacts fail
  closed.
- [ ] The worker is idempotent and reports uncertain outcomes for reconciliation
  instead of retrying an apply blindly.
- [ ] Apply uses a separate CodeBuild project and IAM role with explicit denies
  for build override fields; it never reuses `customer_executor`.
- [ ] Apply remains disabled by default and no AWS apply/deployment occurs.
- [ ] Focused tests, full verification, clean-room proof, Terraform validation,
  documentation conventions, diff checks, and required hosted CI pass.

## Acceptance status

- In progress on draft PR #399. The pure preflight contract is implemented;
  no API dispatch, credential broker, CodeBuild apply project, or Terraform
  execution has been added yet.

## Tests / validation performed

- PR #398 merged-main CI `43460570905` passed all seven jobs.
- Focused contract tests: `9 passed`.
- Full `make verify`: `1,100 passed`; Ruff, Actions config, OpenAPI, and
  Compose checks passed. One existing Starlette/httpx deprecation warning.
- Local and hosted PR #399 checks pending.

## Evidence files produced

- `docs/tickets/ticket399.md`
- The focused contract test is `tests/test_nova_apply_contract.py`.
- `docs/test/test399.md` will record the clean-room/non-AWS boundary evidence
  when the complete executable boundary is ready for that gate.

## Boundaries

This PR must not enable hosted apply or claim that the customer apply lifecycle
is ready. Missing or untrusted pricing remains a hard approval blocker. No
AWS deployment or workload mutation is authorized by this PR.

## Follow-up work

After this source boundary is complete, integrate trusted regional pricing only
after the user clarifies the held PR #318 direction; verify actual customer-role
execution permissions and hosted plan behavior; then prove apply, health,
update, recovery, destroy and independent absence through the hosted API.
