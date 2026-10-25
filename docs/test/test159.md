# test159 — Resource-scoped App Runner pass-role policy

Date: 2026-10-25
Execution type: CloudFormation template validation
Customer repository: Not applicable
Commit: Pending PR commit
AWS account: No AWS mutation performed
AWS region: us-east-1

## Resources created

- None.

## Commands executed

- `aws cloudformation validate-template --template-body file://infrastructure/cloudformation/customer-discovery-role.yaml`

## Observed result

The policy permits passing only the connection-scoped ECR access and runtime roles.

## Teardown

No resources were created or deleted.

## Final boundary

No destroy permission is added.
