# test195 — Hosted administrator-pilot role verification

Date: 2026-10-29
Execution type: Terraform policy contract and live connection-verification remediation.
Customer repository: None; this verifies the hosted control-plane identity boundary.
Commit: Recorded by pull request #196 for issue #195.
AWS account: 654654474502
AWS region: us-east-1

## Commands executed

```text
terraform fmt infrastructure/terraform/serverless-control-plane/main.tf
uv run pytest tests/test_customer_aws_connection_contract.py tests/test_serverless_runtime.py -q
```

## Observed result

- Before the change, live administrator-pilot verification failed with
  `AccessDenied` when the hosted API attempted to assume
  `davdeployExecution-b9e6faf1-d28e-4064-a341-587f2eede77d`.
- The Terraform policy now allows only the explicit
  `arn:aws:iam::*:role/davdeployExecution-*` pattern in addition to the
  pre-existing discovery-role pattern.
- 33 focused tests passed.

## Resources created

The prior controlled connection update created only IAM roles in the named AWS
account: a read-only discovery role, a separate administrator-pilot execution
role, and the App Runner service roles. No workload was deployed by this test.

## Teardown

No resources were deleted. The connection is retained as controlled acceptance
evidence; deletion requires explicit owner approval.

## Final boundary

This is not an apply/destroy acceptance run. A workload remains gated by an
approved immutable plan, authenticated Terraform-plan artifact, verified
connection, explicit operation confirmation, and bounded worker execution.
