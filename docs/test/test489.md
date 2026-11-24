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

1. Verify the AWS caller account and ensure no active Terraform monitor
   operation exists.
2. Review a create plan containing exactly the function, role, scoped policy,
   and log group, then apply it through `scripts/terraform_run_monitor.py`.
3. Invoke the function and verify the `v1` response without printing payloads.
4. Review a Terraform update plan for the same function, apply it through the
   monitor, and verify the same function ARN returns `v2`.
5. Review and apply the destroy plan through the monitor. Independently verify
   the function, role, and log group are absent; retain local state and archive
   files.

## Observed result

Live AWS creation, invocation, update, and teardown are pending.

## Teardown

Terraform and AWS teardown are pending. Local Terraform state and generated
Lambda archives will be retained.

## Final boundary

This test can prove the exact module's direct Lambda invoke, code update, and
teardown for a small synthetic function. It does not prove API Gateway routing,
customer authorization, VPC access, concurrency, pricing completeness, Nova
dispatch, or hosted execution. The control plane remains untouched.
