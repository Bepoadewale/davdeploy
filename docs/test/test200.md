# test200 — Retain immutable customer connection templates

Date: 2026-10-29
Execution type: Terraform template-host validation and production plan review.
Customer repository: None; this covers the public AWS connection template host.
Commit: Pull request #200.
AWS account: 654654474502
AWS region: us-east-1

## Resources created

None by this pull request. The reviewed follow-up apply will add one new
immutable template object while retaining the existing one.

## Commands executed

```sh
terraform -chdir=infrastructure/terraform/connection-template-host validate
scripts/customer-aws-template-host.sh plan
uv run pytest tests/test_customer_aws_connection_contract.py tests/test_terraform_validation.py -q
```

## Observed result

The production plan showed one template object to add, zero changes and zero
deletions. The prior object is moved into deletion-protected retained state.
Eight focused tests passed.

## Teardown

No resources were deleted.

## Final boundary

The public template contains no secret or customer data. This evidence does not
deploy a workload or alter an existing customer CloudFormation stack.
