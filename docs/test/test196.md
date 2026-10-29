# test196 — Hosted administrator-pilot verification policy fix

Date: 2026-10-29
Execution type: Terraform policy contract and live connection-verification remediation.
Customer repository: None; this verifies the hosted control-plane identity boundary.
Commit: Pull request #196.
AWS account: 654654474502
AWS region: us-east-1

## Resources created

No resource is created by this pull request. The prior controlled connection
stack contains IAM roles only; it does not contain a workload.

## Commands executed

```sh
terraform fmt infrastructure/terraform/serverless-control-plane/main.tf
uv run pytest tests/test_customer_aws_connection_contract.py tests/test_serverless_runtime.py -q
make verify
```

## Observed result

The pre-fix live connection verification returned `AccessDenied` for the
separate execution role. The updated policy was deployed through a reviewed
Terraform plan/apply; after the template trust correction, live verification
succeeded. Thirty-three focused tests and the 305-test full suite passed locally.

## Teardown

No resources were deleted.

## Final boundary

Deployment still needs the standard reviewed Terraform apply. This evidence does
not perform a customer-cloud apply or destroy.
