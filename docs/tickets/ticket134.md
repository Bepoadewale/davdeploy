# ticket134: Permit bounded customer resource creation before tagging

PR: #134
Branch: fix/customer-execution-create-policy

## Problem / goal

Allow the trusted customer runner to create only the reviewed App Runner foundation resources when Terraform applies ownership tags in a subsequent API call.

## Current repo state

The customer execution role already had a fixed action list and tag-gated deletion. Its create actions required request tags, but the Terraform AWS provider calls CreateVpc, CreateRepository, and CreateLogGroup before its tag APIs. Real CodeBuild failed before any workload resource completed.

## Research / references used

- The real CodeBuild failure output for EC2 VPC, ECR repository, and CloudWatch log-group creation.
- The provider module's explicit post-create tags.
- The existing CloudFormation role trust, tag, deletion, and `iam:PassRole` boundaries.

## Work planned for the PR

- Split bounded create actions from subsequent tag actions.
- Constrain create actions to the connection stack's selected AWS region.
- Retain request-tag checks for tag operations and resource-tag checks for deletion.
- Add a static contract regression check and validate the CloudFormation template.

## Acceptance criteria

- [x] Only the fixed App Runner foundation create actions are permitted before tagging.
- [x] Create actions require the selected CloudFormation stack region.
- [x] Tagging and deletion retain their connection ownership conditions.
- [x] Focused tests and CloudFormation validation pass locally.
- [ ] Required GitHub CI passes.
- [ ] The public versioned template and existing customer connection stack are updated before a new plan/apply attempt.

## Acceptance status

Implementation and focused local validation are complete. CI, template publication, stack update, and a fresh reviewed customer plan remain.

## Tests / validation performed

- `.venv/bin/python -m pytest -q tests/test_customer_cloud_lifecycle.py tests/test_customer_aws_connection_contract.py tests/test_same_account_pilot.py` passed: 13 tests.
- `aws cloudformation validate-template --template-body file://infrastructure/cloudformation/customer-discovery-role.yaml` passed.
- `git diff --check` passed.

## Evidence files produced

- `docs/tickets/ticket134.md`
- Live customer-pilot evidence continues in `docs/test/test130.md`.

## Boundaries

This does not add an unrestricted administrator role, any new AWS service, arbitrary command input, or broad deletion authority. The role remains assumable only by the configured DavDeploy broker with the per-connection external ID.

## Follow-up work

- Publish the new immutable public CloudFormation template object.
- Update the existing customer connection stack to this template.
- Generate a new customer Terraform plan and execute it only after review.
