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

- Backend `main` is `2dec62484f3c7ec52859dab23c0b4b37acf9f45e` (PR #494).
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
- AWS [Systems Manager and AppConfig pricing](https://aws.amazon.com/systems-manager/pricing/): current published rates are $0.0000002 per configuration request and $0.0008 per configuration received. Limit the test to at most 50 configuration requests and 10 returned configurations, an estimated AppConfig data charge below $0.01; this is an estimate, not a bill or spending cap.
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

- [ ] Module builds a hosted feature-flag profile and a bounded rollout
  strategy from known, same-application identities.
- [ ] Actual-plan policy rejects unknown/missing/cross-plan or cross-app
  references, malformed feature-flag JSON, and unsafe strategy values.
- [ ] Regression tests cover valid configuration and each fail-closed case.
- [ ] Isolated AWS evidence observes disabled → enabled progressive rollout →
  rollback → disabled, using synthetic data and the exact test ID.
- [ ] Monitored destroy and independent AWS reads confirm exact test resources
  absent; local state and plans are retained with mode 600.
- [ ] The 26 architecture entries and 30 implementation roots remain intact;
  the matrix links this exact test and keeps Nova dispatch/hosted execution
  gaps explicit.
- [ ] The estimate uses bounded request/response counts and records the
  current price source; no claim of an actual bill or hard cap is made.
- [ ] Focused tests, `make verify`, Terraform validation, documentation
  conventions, clean-room gate, final-head CI, and review pass.
- [ ] No hosted control-plane, remote-state, lock, unrelated AWS, or customer
  data is accessed or changed. No Nova dispatch or customer workload
  certification is claimed.

## Acceptance status

Ticket-first draft. No implementation or AWS mutation has started.

## Tests / validation performed

- Read-only main, matrix, module, and policy inspection completed.
- Read-only AWS identity was previously verified for account
  `654654474502`; recheck identity immediately before the disposable test.
- Current AWS AppConfig pricing and AWS/HashiCorp primary references were
  reviewed on 2026-11-25.

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
