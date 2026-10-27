# test184 — Remove unused Cognito email KMS alias

Date: 2026-10-27
Execution type: static Terraform validation
Customer repository: none
Commit: pending PR merge
AWS account: not contacted by validation
AWS region: us-east-1 static configuration only

## Resources created

None.

## Commands executed

- `terraform -chdir=infrastructure/terraform/serverless-control-plane fmt -check`
- `terraform -chdir=infrastructure/terraform/serverless-control-plane init -backend=false`
- `terraform -chdir=infrastructure/terraform/serverless-control-plane validate`
- `terraform -chdir=infrastructure/terraform/terraform-operations-bootstrap fmt -check`
- `terraform -chdir=infrastructure/terraform/terraform-operations-bootstrap init -backend=false`
- `terraform -chdir=infrastructure/terraform/terraform-operations-bootstrap validate`

## Observed result

Terraform formatting and static validation passed for both Terraform roots. The configuration keeps the Cognito custom sender on the tagged KMS key ARN without an optional KMS alias. No AWS API operation, email send, or deployment was performed by these commands.

## Teardown

No resources, workloads, credentials, or customer data were created or changed.

## Final boundary

Static validation only. A protected Terraform apply and controlled Cognito code delivery test remain required.
