# test186 — Discovery-only AWS connection template

Date: 2026-10-27
Execution type: local and CloudFormation static validation
Customer repository: none
Commit: pending PR merge
AWS account: configured DavDeploy control-plane account
AWS region: us-east-1

## Resources created

None. The previously created controlled stack was deleted.

## Commands executed

- `uv run pytest -q tests/test_customer_aws_connection_contract.py tests/test_customer_cloud_lifecycle.py tests/test_customer_connection_template.py`
- `aws cloudformation validate-template --template-body file://infrastructure/cloudformation/customer-discovery-role.yaml`

## Observed result

11 tests passed and CloudFormation accepted the discovery-only template.

## Teardown

The controlled stack was deleted.

## Final boundary

Static template validation only; deployment remains required.
