# test489 — Lambda service module lifecycle

Date: 2026-11-24 (in progress)

Execution type: direct same-account AWS module test with local Terraform state.

Customer repository: None.

Commit: PR #489 implementation/evidence commit pending.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

The fixture uses exactly one `modules/lambda-service` instance, one tagged
Lambda execution role with log write permissions scoped to the function's log
group, and one tagged CloudWatch log group with one-day retention. It has no
API Gateway, VPC, ECR, S3, database, or customer application resources.

The same function receives two synthetic code versions. Each handler returns
only its version and the synthetic test ID passed in the invocation event. No
secrets or customer data are used.

## Commands executed

1. Verify AWS account `654654474502`, ensure the unique function, role, and log
   group names are absent, and confirm no active monitor operation exists.
2. Review the create plan (`4 to add, 0 to change, 0 to destroy`), then apply
   it through `scripts/terraform_run_monitor.py`. Run ID:
   `nova-lambda-service-489-create-20261124`; Terraform PID `33754`; finish
   time `2026-11-24T20:36:33Z`.
3. Invoke the function with the synthetic test ID and verify the `v1` response.
4. Review the update plan (`0 to add, 1 to change, 0 to destroy`), then apply
   through the monitor. Run ID: `nova-lambda-service-489-update-20261124`;
   Terraform PID `35930`; finish time `2026-11-24T20:43:49Z`. Invoke the same
   function and verify the `v2` response.
5. Review the destroy plan (`0 to add, 0 to change, 4 to destroy`) and apply
   it through the monitor. Run ID:
   `nova-lambda-service-489-destroy-20261124`; Terraform PID `39105`; finished
   at `2026-11-24T20:54:34Z`.

## Observed result

The create plan contained four creates and zero updates/deletes. Monitored
create `nova-lambda-service-489-create-20261124` used Terraform PID `33754`,
finished at `2026-11-24T20:36:33Z`, and logged to
`/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-lambda-service-489-create-20261124.log`.
The helper verified the `v1` response.

The reviewed update plan contained zero adds, one in-place function update,
and zero deletes. Monitored update
`nova-lambda-service-489-update-20261124` used Terraform PID `35930`, finished
at `2026-11-24T20:43:49Z`, and logged to
`/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-lambda-service-489-update-20261124.log`.
The same function returned the expected `v2` response. The helper printed
only the function name, verified version, and result status; it did not print
the synthetic payload.

## Teardown

The reviewed destroy plan contained zero adds, zero changes, and four deletes.
Monitored destroy `nova-lambda-service-489-destroy-20261124` used Terraform
PID `39105`, succeeded at `2026-11-24T20:54:34Z`, and logged to
`/var/folders/p1/wtz8hss162jgrh2bgrn3fwn40000gn/T/davdeploy-terraform-runs/nova-lambda-service-489-destroy-20261124.log`.
Independent AWS reads in account `654654474502`, region `us-east-1`, returned
no matching Lambda function, execution role, or log group. The Terraform state
list returned empty; local state is retained. The monitor has 57 records and
no active operations. Generated archives and local provider files remain
retained.

## Final boundary

This test can prove the exact module's direct Lambda invoke, code update, and
teardown for a small synthetic function. It does not prove API Gateway routing,
customer authorization, VPC access, concurrency, pricing completeness, Nova
dispatch, or hosted execution. The control plane remains untouched.
