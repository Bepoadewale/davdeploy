# test392 — disposable Nova plan-only role policy validation

Date: 2026-11-13
Execution type: Real AWS temporary IAM role creation, policy simulation, and teardown; no customer workload
Customer repository: None; this tested the published DavDeploy customer-role template in the DavDeploy AWS account
Commit: `ae9ec4450d527141081e95707a1c3ee05126b683` (template published by PR #381; current API at PR #390 release)
AWS account: `654654474502`
AWS region: `us-east-1`

## Resources created

Exact test ID and CloudFormation connection tag: `nova-plan-role-test-20261113`.
The immutable template URL was
`https://davdeploy-customer-templates-654654474502.s3.us-east-1.amazonaws.com/cloudformation/customer-discovery-role-8c5d1c82682b3bb90ff1f45d121b475e7b33b484f556feabafbf387c335aea4e.yaml`.
Its SHA-256 matches the local source
`infrastructure/cloudformation/customer-discovery-role.yaml`.

The reviewed CloudFormation change set was
`arn:aws:cloudformation:us-east-1:654654474502:changeSet/nova-plan-role-test-20261113-create/99f009cd-e196-4804-9b5c-6ff561fef3e3`.
It contained exactly one `Add`: logical resource `NovaPlanOnlyRole`, type
`AWS::IAM::Role`; no other resources or replacements were planned. It was
executed as stack
`arn:aws:cloudformation:us-east-1:654654474502:stack/davdeploy-NovaPlanRoleTest-20261113/f355e300-df3c-11f1-81e0-12fffc39183f`.
The sole physical resource was `davdeployPlan-nova-plan-role-test-20261113`.
It trusted only `arn:aws:iam::654654474502:role/davdeploy-api` with a
non-empty external ID. The random external ID is intentionally not recorded.

## Commands executed

- `aws cloudformation validate-template --profile ai-platform-pilot-key --template-body file://infrastructure/cloudformation/customer-discovery-role.yaml` — passed; template hash matched the published immutable object.
- Boto3 `CreateChangeSet`, `DescribeChangeSet`, and `ExecuteChangeSet` using `AWS_PROFILE=ai-platform-pilot-key`, `AccessMode=plan-only`, the exact test ID, and the immutable template URL.
- Boto3 IAM `GetRole`, `GetRolePolicy`, and `SimulatePrincipalPolicy` checks. Output omitted the external-ID value.
- Boto3 CloudFormation `DeleteStack`, followed by exact stack and role absence checks.

## Observed result

The created role had the expected `ManagedBy=davdeploy` and exact test-ID tags,
only the `davdeployNovaPlanReadOnlyProfile` inline policy, and a trust statement
for the API broker with an external-ID condition. IAM policy simulation returned:

- Allowed: `ec2:DescribeVpcs`, `iam:GetRole`, and same-account `s3:ListBucket`.
- Explicitly denied: `s3:GetObject`, `s3:PutObject`, `iam:CreateRole`,
  `rds:CreateDBInstance`, and `secretsmanager:GetSecretValue`.

CloudFormation deletion completed. The test role no longer exists and the test
stack is absent from active stack inventory. The two pre-existing
`davdeployDiscovery-*` stacks were not changed.

## Teardown

Deleted only `davdeploy-NovaPlanRoleTest-20261113` after confirming its stack
inventory contained exactly the test role. Verified `DELETE_COMPLETE`, no
active stack with the test name, and `NoSuchEntity` for the test IAM role.

## Final boundary

This validates selected IAM policy simulator decisions and the deployed
CloudFormation template's trust/policy shape. IAM simulation does not prove an
actual API broker role assumption, every service's real API behavior, all
account-level organization controls, or a full effective-permission result.
No DavDeploy customer connection was created or verified; no Terraform plan,
customer workload, apply, health check, recovery, or customer teardown ran.
