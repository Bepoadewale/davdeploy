# test495 — AppConfig feature-flag rollout evidence

Date: 2026-11-25

Execution type: Real AWS execution; direct isolated customer-side Terraform test

Customer repository: `Bepoadewale/davdeploy`

Commit: `24c32f4` (implementation commit pushed to draft PR #495; update this field with the final evidence commit before merge)

AWS account: `654654474502`

AWS region: `us-east-1`

## Run status

The first monitored apply failed before AWS mutation because the monitor
process did not inherit `AWS_PROFILE`. Run `appconfig-ff-495-create-20261125`
exited 1; supervisor PID `18445`, Terraform PID `18446`, root
`/private/tmp/davdeploy-appconfig-rollout-495/docs/test/fixtures/nova-appconfig-rollout-495`,
log `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/appconfig-ff-495-create-20261125.log`,
monitor log `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/appconfig-ff-495-create-20261125.monitor.log`.
The run failed during credential lookup before provider refresh or resource
creation. A retry was started with the profile exported to the monitor at
`2026-11-25T01:10:33Z` as
`appconfig-ff-495-create-retry-20261125`; supervisor PID `20775`, root
`/private/tmp/davdeploy-appconfig-rollout-495/docs/test/fixtures/nova-appconfig-rollout-495`,
log `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/appconfig-ff-495-create-retry-20261125.log`,
monitor log `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/appconfig-ff-495-create-retry-20261125.monitor.log`.
Its terminal status and Terraform PID are pending; exact resource inventory
will be rechecked after it terminates.

## Scope and exact target

- Run type: real AWS execution, direct isolated customer-side Terraform test.
- Repository: `Bepoadewale/davdeploy`, branch `feat/appconfig-rollout-495`.
- AWS account: `654654474502` (identity rechecked before the run).
- Region: `us-east-1`.
- Exact test ID: `20261125-a1b2c3`.
- Application name: `davdeploy-nova-ff-495-20261125-a1b2c3`.
- Purpose tag: `temporary-appconfig-feature-flag-validation`.
- Synthetic flag: `nova_demo`, initially disabled, then enabled for rollout,
  then reverted to disabled.
- Terraform state: local only; no hosted state or lock resources.
- Hosted control plane and its state, locks, roles, buckets, and runtime are
  outside scope and must remain untouched.

The application and deployment strategy name prefix were checked in account
`654654474502` before the run and returned no matches. The Terraform run
monitor had 62 records and zero active operations. No mutation was performed
during those checks. The first plan attempt failed before mutation because
`AWS_PROFILE` was scoped to the identity command and not exported to
Terraform; its mode-600 plan artifact was retained. After exporting the
profile, the reviewed saved plan showed exactly six creates, zero updates,
and zero deletes, all for the tagged test manifest. The reviewed plan is
`/tmp/davdeploy-appconfig-rollout-495-20261125-a1b2c3/initial-retry.tfplan`
with mode `0600`.

## Cost estimate and bounds

AWS's published AppConfig Data pricing reviewed on 2026-11-25 is $0.0000002 per
configuration request and $0.0008 per configuration received. The test limits
AppConfig Data polling to at most 50 requests and 10 received configurations,
for a modeled charge below $0.01. This is an estimate, not a bill, spending
cap, or estimate of all account costs. Deployment and other service charges,
if any, are not included.

Source: [AWS Systems Manager and AppConfig pricing](https://aws.amazon.com/systems-manager/pricing/).
The pinned v5.100.0 provider implementation treats deployment deletion as a
no-op, preserving AWS deployment history:
[HashiCorp AWS provider v5.100.0 `deployment.go`](https://github.com/hashicorp/terraform-provider-aws/blob/v5.100.0/internal/service/appconfig/deployment.go).

## Commands executed

The test ID and application/strategy names are exact and unique. Read-only
preflight in the selected account returned the expected identity and no
matching application or strategy. The fixture had no Terraform state file.
There were 62 Terraform monitor records and zero active operations.

```sh
AWS_PROFILE=ai-platform-pilot-key aws sts get-caller-identity --query '{Account:Account,Arn:Arn}' --output json
AWS_PROFILE=ai-platform-pilot-key aws appconfig list-applications --query 'Items[?starts_with(Name, `davdeploy-nova-ff-495-20261125-a1b2c3`)].{Id:Id,Name:Name}' --output json
AWS_PROFILE=ai-platform-pilot-key aws appconfig list-deployment-strategies --query 'Items[?starts_with(Name, `davdeploy-nova-ff-495-20261125-a1b2c3`)].{Id:Id,Name:Name}' --output json
terraform -chdir=docs/test/fixtures/nova-appconfig-rollout-495 state list
```

The first plan failed before mutation because the AWS profile was scoped only
to the identity command. The first monitored apply failed before mutation
because the monitor process did not inherit the profile. Both failed runs and
logs are retained. With the profile exported, the saved plan showed exactly
six creates, zero updates, and zero deletes. The plan file is mode `0600`.

```sh
export AWS_PROFILE=ai-platform-pilot-key
export AWS_REGION=us-east-1
export TF_VAR_test_id=20261125-a1b2c3
ROOT=docs/test/fixtures/nova-appconfig-rollout-495
EVIDENCE=/tmp/davdeploy-appconfig-rollout-495-20261125-a1b2c3
umask 077
terraform -chdir="$ROOT" show -no-color "$EVIDENCE/initial-retry.tfplan"
AWS_PROFILE="$AWS_PROFILE" python3 scripts/terraform_run_monitor.py start apply "$ROOT" --run-id appconfig-ff-495-create-retry-20261125 --terraform-arg "$EVIDENCE/initial-retry.tfplan"
```

Run logs, helper logs, and plans are under
`/tmp/davdeploy-appconfig-rollout-495-20261125-a1b2c3/`. Terraform state is
local to the fixture. The monitor adds `-auto-approve` and `-input=false`.
Never run another Terraform operation against this root until the active
monitor run is terminal.

The initial plan creates only the tagged AppConfig application, environment,
hosted feature-flag profile/version, bounded strategy, and deployment. Confirm
disabled state using local Terraform output IDs with
`scripts/appconfig_feature_flag_lifecycle.py --phase present --account-id
654654474502 --region us-east-1 --test-id 20261125-a1b2c3 --application-id
<application-id> --environment-id <environment-id> --profile-id <profile-id>
--strategy-id <strategy-id> --deployment-number 1 --expected-enabled false
--timeout-seconds 120 --poll-interval-seconds 15 --profile
ai-platform-pilot-key`. Never print or save AppConfig Data session tokens.

For the enabled revision, create and inspect a saved plan with
`-var flag_enabled=true`. Start the helper in present mode for deployment
number 2 with `--expected-enabled true --require-progressive-state
--timeout-seconds 120 --poll-interval-seconds 15`, then apply the reviewed plan
through `scripts/terraform_run_monitor.py`. The helper must observe
`DEPLOYING` or `BAKING`, then `COMPLETE`, and the enabled flag. Retain the
monitor run ID, root, PID, and log path.

Revert only deployment number 2 with
`aws appconfig stop-deployment --application-id <application-id>
--environment-id <environment-id> --deployment-number 2 --allow-revert`.
Verify the deployment state is `REVERTED` and the AppConfig Data value is
disabled. Do not print or save AppConfig Data session tokens.

Create and review an exact destroy plan, then apply that saved plan using the
repository Terraform run monitor. Run the independent exact-ID absence helper
and AWS reads afterward. AppConfig deployment history is append-only evidence
in the pinned AWS provider; if it remains after destroy, record its exact
state and binding as retained audit history rather than attempting a separate
delete.

## Resources created

The retry may be creating the following exact planned manifest: one AppConfig application,
production environment, hosted feature-flag profile and version, deployment
strategy, and deployment; all use test ID `20261125-a1b2c3`.

## Observed result

Pending successful monitored create, disabled flag read, progressive enabled
deployment and flag read, rollback observation, and exact absence check.

## Teardown

Pending. Revert only deployment number 2, review an exact destroy plan, apply
it through the Terraform run monitor, run exact-ID AWS absence checks, and
retain any service-managed deployment history as audit evidence.

## Final boundary

This evidence covers the exact AppConfig shape and synthetic flag above. It
does not prove Nova dispatch, cross-account credential delivery, hosted
control-plane operation, customer application integration, alarm-driven
rollback, full AWS cost, or customer workload certification.
