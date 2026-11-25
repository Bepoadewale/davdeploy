# test495 — AppConfig feature-flag rollout evidence

Date: 2026-11-25

Execution type: Real AWS execution; direct isolated customer-side Terraform test

Customer repository: `Bepoadewale/davdeploy`

Commit: `a4c629c` (implementation source used for the recorded AWS lifecycle)

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
creation. A retry with credentials exported failed because the saved plan had
become stale after the failed apply persisted the caller-identity data source
into local state. Run `appconfig-ff-495-create-retry-20261125` exited 1;
supervisor PID `20775`, Terraform PID `20776`, log
`/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/appconfig-ff-495-create-retry-20261125.log`.
The state contained only `data.aws_caller_identity.current`; no AWS workload
resource existed. Its mode was corrected to `0600`. A fresh plan showed six
creates, zero updates, and zero deletes. Monitored run
`appconfig-ff-495-create-final-20261125` started at `2026-11-25T01:17:21Z`,
supervisor PID `22869`, Terraform PID `22870`, and succeeded at
`2026-11-25T01:17:27Z` with six adds, zero changes, and zero destroys. Its
root was
`/private/tmp/davdeploy-appconfig-rollout-495/docs/test/fixtures/nova-appconfig-rollout-495`;
log `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/appconfig-ff-495-create-final-20261125.log`,
monitor log `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/appconfig-ff-495-create-final-20261125.monitor.log`.

The exact IDs are application `caucj5h`, environment `xkxlxyi`, profile
`3eqb088`, and strategy `ugs3vlo`. Mode-600 result
`/tmp/davdeploy-appconfig-rollout-495-20261125-a1b2c3/initial-disabled-verified-2.json`
records hosted version 1 and deployment 1 as `COMPLETE`, flag `nova_demo=false`,
and one AppConfig Data configuration response.

An initial enabled plan was retained and not applied because it proposed
replacing hosted version 1. AppConfig adds service-managed timestamps to
feature-flag content. The module now preserves the moved baseline version,
ignores provider-added content changes for immutable revision keys, and keeps
the active deployment at a stable address. Reviewed plan
`/tmp/davdeploy-appconfig-rollout-495-20261125-a1b2c3/append-only-enabled-v2.tfplan`
moves version 1 without replacement, adds the enabled revision, and replaces
only the deployment resource. The pinned provider's deployment delete is a
no-op, preserving completed AWS deployment history. Monitored run
`appconfig-ff-495-enabled-append-only-20261125` started at
`2026-11-25T01:40:16Z`; supervisor PID `32237`, root
`/private/tmp/davdeploy-appconfig-rollout-495/docs/test/fixtures/nova-appconfig-rollout-495`,
log `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/appconfig-ff-495-enabled-append-only-20261125.log`,
monitor log `/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/appconfig-ff-495-enabled-append-only-20261125.monitor.log`.
It succeeded at `2026-11-25T01:40:20Z`; Terraform PID `32238`; two added,
zero changed, one destroyed. The replacement removed only the old Terraform
deployment record; AWS deployment history is retained by the provider. The
first progressive verifier timed out after observing `BAKING`. A separate
bounded verifier confirmed deployment 2 `COMPLETE` and `nova_demo=true` with
one data read. After rollback, a third verifier confirmed deployment 2
`REVERTED` and `nova_demo=false` with one data read. The mode-600 JSON results
and the timeout log are retained in the evidence directory.

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
profile, the first reviewed saved plan showed exactly six creates, zero
updates, and zero deletes, all for the tagged test manifest. After Terraform
state was refreshed by the failed apply, a new reviewed plan again showed
exactly six creates, zero updates, and zero deletes. Its path is
`/tmp/davdeploy-appconfig-rollout-495-20261125-a1b2c3/initial-replan.tfplan`
and mode is `0600`; older plan files are retained.

## Cost estimate and bounds

AWS's published AppConfig Data pricing reviewed on 2026-11-25 is $0.0000002 per
configuration request and $0.0008 per configuration received. The four
verification attempts are bounded to at most 20 `GetLatestConfiguration` calls
and four session starts (24 requests total), with at most 11 returned
configurations. This includes the first progressive verifier that timed out,
the successful completion read, and the rollback read. At those maxima, the
modeled data charge is `24 × $0.0000002 + 11 × $0.0008 = $0.0088048`, below
$0.01. The timed-out helper did not emit its actual counters; its explicit
request and response caps bound its contribution. This is an estimate, not a
bill, spending cap, or estimate of all account costs. Deployment and other
service charges, if any, are not included.

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
because the monitor process did not inherit the profile. The next apply
failed on a stale plan. All failed runs and logs are retained. The fresh plan
was reviewed against current local state.

```sh
export AWS_PROFILE=ai-platform-pilot-key
export AWS_REGION=us-east-1
export TF_VAR_test_id=20261125-a1b2c3
ROOT=docs/test/fixtures/nova-appconfig-rollout-495
EVIDENCE=/tmp/davdeploy-appconfig-rollout-495-20261125-a1b2c3
umask 077
terraform -chdir="$ROOT" show -no-color "$EVIDENCE/initial-replan.tfplan"
python3 scripts/terraform_run_monitor.py start apply "$ROOT" --run-id appconfig-ff-495-create-final-20261125 --terraform-arg "$EVIDENCE/initial-replan.tfplan"
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
--timeout-seconds 120 --poll-interval-seconds 15 --max-get-latest-calls 8
--max-configuration-responses 1 --profile
ai-platform-pilot-key`. Never print or save AppConfig Data session tokens.

For the enabled revision, create and inspect a saved plan with
`-var='flag_revisions={baseline=false,rollout=true}' -var='active_revision=rollout'`.
The reviewed plan moved version 1 to the stable `baseline` address without
replacement, added version 2 at the `rollout` address, and replaced only the
deployment resource. Start the helper concurrently for deployment 2 with
`--expected-enabled true --require-progressive-state`. It observed `BAKING`
but timed out before `COMPLETE`; a second bounded read then verified deployment
2 `COMPLETE` and the enabled flag. The monitor run ID, root, PID, and logs are
recorded above.

Revert only deployment number 2 with
`aws appconfig stop-deployment --application-id <application-id>
--environment-id <environment-id> --deployment-number 2 --allow-revert`.
Verify the deployment state is `REVERTED` and the AppConfig Data value is
disabled using `--max-get-latest-calls 8 --max-configuration-responses 4`.
Do not print or save AppConfig Data session tokens.

## Local clean-room validation

At code commit `07860e0`, a fresh detached worktree at
`/tmp/davdeploy-cleanroom-pr495` ran the full local sequence with isolated
Compose project `davdeploy-pr495-cleanroom`: bootstrap, smoke, API contract,
customer-plan end-to-end, seed data, simple/complex/degraded/Day-2 demos,
policy failure, readiness failure, trace check, and `make verify`. The
sequence passed, including 1,788 tests. The first bootstrap attempt hit host
port 8181, already used by the separate PR #486 clean-room stack; no unrelated
container was changed. The retry used dedicated host ports 48080, 48090,
48181, 49090, 43200, and 43000. The isolated containers are stopped. Final
`make clean-local` was not run: it would delete this worktree's `.venv`,
`.local`, and Postgres Docker volume. Those generated artifacts remain pending
owner approval for cleanup. The protected main-worktree `.venv-pr399/` was
restored to its original editable repository path and was not deleted.

The refreshed saved destroy plan is
`/tmp/davdeploy-appconfig-rollout-495-20261125-a1b2c3/exact-destroy-current.tfplan`
(SHA-256 `324180ee8c840ed77a4d794af14046888b3effba76d9c4603263d2c655fb2323`).
It contains zero additions, zero updates, zero replacements, and seven destroys
for this test ID: the application, environment, profile, strategy, both hosted
versions, and deployment 2. Applying it removes the tagged test application
and its resources. AWS documents that deleting the application deletes its
subresources, including hosted versions and environments. The provider's
deployment-resource delete is a no-op; AWS documentation does not establish
whether deployment history remains accessible after the application and
environment are removed. This report and the retained local evidence preserve
the observed deployment details. The plan is not applied pending owner
approval. After approval, apply only this hash-verified plan through the
repository monitor, then run the exact-ID absence helper for deployments 1 and
2 and independent AWS reads.

## Resources created

Observed: one tagged AppConfig application, environment, hosted feature-flag
profile, two hosted versions (1 disabled, 2 enabled), strategy, and completed
deployments 1 and 2. Deployment 2 is `REVERTED`; the AppConfig Data read
returned the disabled value. Application `caucj5h`, environment `xkxlxyi`,
profile `3eqb088`, and strategy `ugs3vlo` are exact IDs.

## Observed result

Monitored create, initial disabled read, `BAKING` observation, completed
enabled read, rollback, and reverted disabled read all succeeded. The exact
destroy plan is ready; applying it and verifying absence remain pending owner
approval.

## Teardown

Deployment 2 has been reverted. The seven-destroy plan is reviewed and ready,
but has not been applied because it deletes the exact test application,
profile, strategy, both hosted versions, environment, and deployment history.
After explicit approval, apply it through the Terraform run monitor and run
exact-ID absence checks for deployments 1 and 2. Preserve the local state,
plans, verifier outputs, and run logs as evidence.

## Final boundary

This evidence covers the exact AppConfig shape and synthetic flag above. It
does not prove Nova dispatch, cross-account credential delivery, hosted
control-plane operation, customer application integration, alarm-driven
rollback, full AWS cost, or customer workload certification.
