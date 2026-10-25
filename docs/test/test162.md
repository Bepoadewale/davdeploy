# test162 — Private App Runner HTTPS egress

Date: 2026-10-25
Execution type: Local Terraform and focused regression validation
Customer repository: Not applicable
Commit: Pending PR commit
AWS account: Validation used ai-platform-pilot-key
AWS region: us-east-1

## Resources created

- None.

## Commands executed

- `.venv/bin/pytest -q tests/test_cloud_execution.py tests/test_customer_cloud_lifecycle.py`
- `terraform fmt infrastructure/terraform/customer-workload-app-runner-pilot`
- `AWS_PROFILE=ai-platform-pilot-key terraform -chdir=infrastructure/terraform/customer-workload-app-runner-pilot validate`

## Observed result

The module validates with a private-subnet NAT route and HTTPS-only connector egress rule.

## Teardown

No resources were created or deleted by validation.

## Final boundary

The change preserves private workload placement and does not enable destroy.
