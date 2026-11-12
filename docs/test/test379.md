# test379 — region-bounded Nova network plan profile

- Date: 2026-11-12
- Execution type: Local verification, local-stack proof, and read-only IAM policy simulation
- Customer repository: N/A; synthetic proposals only
- Commit: `4a292d0` (policy implementation exercised by the recorded local runs)
- Pull request: [#379](https://github.com/Bepoadewale/davdeploy/pull/379) (draft)
- AWS account: `654654474502` (policy simulation only)
- AWS region: `us-east-1` (simulation context only)

## Purpose

Allow the Nova planning role to inspect metadata for proposed VPCs, subnets,
and security groups, while keeping the EC2 read actions restricted to the
trusted region and proposal type. The profile still excludes EC2 mutations,
routes, internet gateways, NAT, and VPC endpoints.

## Commands executed

- `.venv/bin/python -m pytest tests/test_nova_plan_access.py tests/test_customer_aws_connection_contract.py -q`
  — 39 passed.
- `make verify` — 1,050 tests passed; Ruff, OpenAPI snapshot, Actions
  configuration, and Docker Compose configuration checks passed.
- `make terraform-validate` — formatting and validation passed for all
  configured Terraform roots.
- `python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- `COMPOSE_FILE="docker-compose.yml:/tmp/davdeploy-pr379-local-proof-network.yml" make local-proof`
  — passed, including local API/worker/executor readiness, API/CORS contract,
  customer-plan E2E, seeded local data, trace verification, and a second full
  verification run (1,050 tests).
- Verified the AWS caller identity was account `654654474502`, then used
  read-only AWS IAM `SimulateCustomPolicy` with a generated mixed
  S3/VPC/subnet/security-group profile — `ec2:DescribeVpcs` was allowed in `us-east-1`,
  explicitly denied in `us-west-2`, and `ec2:RunInstances` was explicitly
  denied in `us-east-1`.

The default Docker network allocation initially failed because the host had
used all predefined address pools. The local proof was rerun with an explicit
unused `10.253.10.0/24` subnet. No existing Docker networks or volumes were
deleted. The DavDeploy local Compose stack remains running.

## Policy checks

- Supported VPC, subnet, and security-group proposals receive only four fixed
  EC2 metadata actions, with `ec2:Region` equal to the trusted target region.
- The session policy explicitly denies those actions when the region differs.
- Proposals without those network resource types receive no EC2 metadata
  access. Network-only proposals still deny other direct grants to the assumed
  role session.
- Mixed service proposals include read-action families only for services in
  that proposal and remain under the 2,048-character AWS session-policy cap.
- EC2 write actions and wildcard `ec2:Describe*` are absent.

## Resources created

This proof used synthetic local data and project-related Docker containers.
AWS calls were limited to caller identity verification and the read-only IAM
policy simulation above. It did not assume a customer role, deploy the updated
CloudFormation template, create customer resources, or enable hosted Nova
planning. The local stack is left running; no Docker cleanup was performed.

## Observed result

The focused policy tests, full verification, Terraform validation, documentation
checks, local proof, and IAM policy simulation all passed. Hosted planning
remains disabled.

## Teardown

No AWS teardown applies. The local Compose stack remains running; it was not
stopped or deleted. No Docker volumes or networks were deleted. IAM simulation
created no role or other AWS resource.

## Final boundary

Policy simulation verifies this generated policy's action decisions for the
three tested contexts. It does not prove effective customer-role permissions
or hosted Terraform planning. Those remain follow-up acceptance work after
this PR's independent review and CI.
