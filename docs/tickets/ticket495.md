# ticket495 — complete bounded AppConfig feature-flag rollout

PR: [#495 — feat: add bounded AppConfig feature-flag rollout](https://github.com/Bepoadewale/davdeploy/pull/495) (draft).

Branch: `feat/appconfig-rollout-495`.

## Problem / goal

The `aws-feature-flags` Terraform root currently creates only an AppConfig
application and environment. The Nova capability matrix requires a bound
feature-flag profile, a deployment strategy, an observed progressive rollout,
rollback, and cost evidence. Extend the bounded module and actual-plan policy,
then run a disposable direct same-account customer-side lifecycle test.

The test must use synthetic flag data, local Terraform state, an exact test ID,
reviewed saved plans, the Terraform run monitor, independent absence checks,
and retained mode-600 evidence. It must not access or modify the hosted
control plane, its state/locks, or customer data. Direct AWS evidence is for
this exact shape only; it does not prove Nova dispatch.

## Current repo state

- At PR creation, backend `main` was
  `2dec62484f3c7ec52859dab23c0b4b37acf9f45e` (PR #494).
- The `modules/feature-flags` root contains only
  `aws_appconfig_application` and `aws_appconfig_environment`.
- The generated-plan policy binds each AppConfig environment to one same-plan
  application. It does not yet check profile, hosted feature-flag content, or
  a rollout strategy.
- The capability matrix has 26 architecture entries and 30 Terraform roots;
  `aws-feature-flags` has no root-specific workload evidence.
- AWS account `654654474502`, region `us-east-1`; disposable same-account
  validation is isolated from the hosted control plane.

## Research / references used

- AWS AppConfig [configuration profile types](https://docs.aws.amazon.com/appconfig/latest/userguide/appconfig-creating-configuration-profile.html)
  and [feature-flag content schema](https://docs.aws.amazon.com/appconfig/latest/userguide/appconfig-type-reference-feature-flags.html).
- AWS AppConfig [deployment strategies](https://docs.aws.amazon.com/appconfig/latest/userguide/appconfig-creating-deployment-strategy.html)
  and [reverting configuration](https://docs.aws.amazon.com/appconfig/latest/userguide/appconfig-deploying-reverting.html).
- AWS [Systems Manager and AppConfig pricing](https://aws.amazon.com/systems-manager/pricing/): current published rates are $0.0000002 per configuration request and $0.0008 per configuration received. The lifecycle verifier attempts are bounded to at most 24 requests and 11 returned configurations, an estimated AppConfig data charge below $0.01; this is an estimate, not a bill or spending cap.
- HashiCorp AWS provider resources for [`aws_appconfig_configuration_profile`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/appconfig_configuration_profile), [`aws_appconfig_hosted_configuration_version`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/appconfig_hosted_configuration_version), [`aws_appconfig_deployment_strategy`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/appconfig_deployment_strategy), and [`aws_appconfig_deployment`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/appconfig_deployment).
- Existing AppConfig environment policy and regressions in
  `apps/api/src/davdeploy/generated_plan_policy.py` and
  `tests/test_generated_plan_policy.py`.

## Work planned for the PR

1. Extend the module with a hosted `AWS.AppConfig.FeatureFlags` profile, a
   minimal typed synthetic flag configuration, and a bounded linear rollout
   strategy. Expose only the IDs needed for deployment and observation.
2. Extend actual-plan checks and regression tests to bind application,
   environment, profile, hosted configuration version, and strategy to the
   exact same plan; reject missing, unknown, cross-application, or unsafe
   strategy/content values.
3. Add a fixture and redacted test helper. Directly deploy a disabled flag,
   observe it via AppConfig Data, deploy an enabled revision progressively,
   observe deployment state and the new value, revert it, and confirm the
   disabled value is restored.
4. Review exact create/destroy plans, apply and destroy through the PID-based
   Terraform monitor, independently confirm test resources absent, and retain
   state/plans/evidence with mode 600.
5. Update `docs/test/test495.md`, the capability matrix, and this ticket with
   exact commands, resources, observed outcomes, cost assumptions, cleanup,
   and limitations. Run focused and full required checks plus the clean-room
   gate; wait for current-head CI and review before merge.

## Acceptance criteria

- [x] Module builds a hosted feature-flag profile and a bounded rollout
  strategy from known, same-application identities.
- [x] Actual-plan policy rejects unknown/missing/cross-plan or cross-app
  references, malformed feature-flag JSON, and unsafe strategy values.
- [x] Regression tests cover valid configuration and each fail-closed case,
  including append-only version publishing and exact application teardown.
- [x] Isolated AWS evidence observes disabled → enabled progressive rollout →
  rollback → disabled, using synthetic data and the exact test ID.
- [ ] Monitored destroy and independent AWS reads confirm exact test resources
  absent; local state and plans are retained with mode 600.
- [x] The 26 architecture entries and 30 implementation roots remain intact;
  the matrix links this exact test and keeps Nova dispatch/hosted execution
  gaps explicit.
- [x] The estimate uses bounded request/response counts and records the
  current price source; no claim of an actual bill or hard cap is made.
- [x] Focused tests, `make verify`, Terraform validation, and documentation
  conventions pass. The clean-room gate, final-head CI, and review remain.
- [ ] No hosted control-plane, remote-state, lock, unrelated AWS, or customer
  data is accessed or changed. No Nova dispatch or customer workload
  certification is claimed.

## Acceptance status

- [x] Ticket and draft PR opened before substantive implementation.
- [x] Module, generated-plan policy, regression tests, Terraform fixture, and
  redacted lifecycle verifier are implemented locally.
- [x] Focused policy and lifecycle tests pass (533 tests after append-only
  version-retention and exact application-teardown regressions).
- [x] Direct AWS disabled → progressive enabled → reverted lifecycle evidence
  is verified for deployment 2; the failed progressive verifier observed
  `BAKING`, a bounded completion read confirmed `COMPLETE` and enabled, and a
  rollback read confirmed `REVERTED` and disabled.
- [ ] Exact monitored destroy and independent absence check.
- [x] Matrix update, full repository validation, and documentation conventions.
- [ ] Clean-room final cleanup, final-head CI, review, and merge.

Implementation commit `a4c629c` is on the PR branch. The initial six-resource
create succeeded and the disabled flag was independently verified. A reviewed
append-only plan retained hosted version 1, added a new version, and replaced
only the Terraform deployment resource. The enabled revision reached
`BAKING` and `COMPLETE`; rollback returned the flag to disabled. The exact
seven-resource destroy plan is reviewed and awaits approval before apply. PR
#495 remains a draft.

## Tests / validation performed

- Read-only main, matrix, module, and policy inspection completed.
- AWS identity was verified for account `654654474502` before create, rollout,
  and rollback.
- Current AWS AppConfig pricing and AWS/HashiCorp primary references were
  reviewed on 2026-11-25.
- Read-only AWS caller identity returned account `654654474502`; the exact
  application and deployment-strategy name prefixes for test ID
  `20261125-a1b2c3` were absent. The Terraform monitor showed 62 records and
  zero active operations.
- `/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python -m pytest -q
  tests/test_generated_plan_policy.py tests/test_appconfig_feature_flag_lifecycle_script.py`:
  533 passed.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python`:
  1,788 tests passed; lint, Actions configuration, OpenAPI snapshot, and
  Compose configuration checks passed.
- Fresh detached worktree `/tmp/davdeploy-cleanroom-pr495` passed bootstrap,
  smoke, API contract, customer-plan end-to-end, seed data, all canonical and
  failure demos, trace check, and `make verify` with 1,788 tests. Its isolated
  containers are stopped. `make clean-local` remains pending approval because
  it deletes the generated `.venv`, `.local`, and Postgres Docker volume.
- Terraform fixture formatting and validation passed with the pinned lockfile.
- Ruff lint passed. Formatting check reports pre-existing formatting
  differences in large existing files; do not mass-format unrelated code.
- Initial AWS create, disabled-value verification, append-only version 2,
  enabled-value observation, rollback, and disabled-value verification
  succeeded. The exact destroy plan shows seven test resources and remains
  unapplied pending approval; see `docs/test/test495.md`.
- AppConfig Data verification honors AWS's next-poll interval, enforces at
  most eight `GetLatestConfiguration` calls and four responses per phase, and
  returns only counts and a boolean flag value; it never returns tokens.

## Current-main synchronization — 2026-11-25

The PR branch was synchronized first with backend `main` at
`b6b663d87c7f31bebd2baf47f4589d8205ec2b3f` in merge commit `13f32b6`, then
with current `main` at `ee3a407dbe5166b66abea38e47c7a20778f01e90` after PR #486
merged, in merge commit `2a079df`.
The AppConfig policy, lifecycle verifier, and tests remain present. The
capability-matrix conflict was reconciled to retain current-main status and
the PR's revision-retention and exact teardown limitations. Focused policy and
AppConfig tests pass (614 passed); `make verify` passes (1,904 tests, one
existing Starlette/httpx deprecation warning); Ruff, documentation conventions,
and `git diff --check` pass. All seven checks passed on prior head `599fc03`
in run `45604183781`; fresh final-head CI and review are pending after the
second main synchronization.

The account inventory still shows the tagged AppConfig application,
environment, profile, deployment strategy, and `COMPLETE`/`REVERTED` history.
No AWS resource was changed by this source sync. The reviewed seven-resource
destroy plan remains unapplied pending explicit approval; no absence-after-
teardown claim is made. The isolated clean-room run passed through
`make verify`; its final cleanup step remains pending explicit approval because
it would remove generated local files and a Compose volume.

## Evidence files produced

- `docs/tickets/ticket495.md`
- `docs/test/test495.md` (required before any AWS workload apply)
- `docs/test/fixtures/nova-appconfig-rollout-495/`
- Focused generated-plan policy tests and helper tests

## Boundaries

Use unique `davdeploy-nova-feature-flags-495` names and one exact synthetic
test ID. Confirm AWS identity, the exact manifest, and the reviewed create plan
before apply. Use local state only. Do not retrieve or print configuration
tokens or credentials. Do not touch hosted control-plane resources, remote
state, lock resources, unrelated resources, protected local files, or retained
SageMaker lineage evidence. Preserve AWS-managed deployment history if the
service retains it after cleanup, and document it as audit evidence. Direct
same-account evidence does not prove Nova dispatch, cross-account behavior,
customer application integration, or full pricing.

## Follow-up work

AppConfig client integration, alarm-driven automatic rollback, full service
pricing, Nova dispatch, and hosted composed-workload evidence remain separate
gates.
