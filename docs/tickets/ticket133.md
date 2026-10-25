# ticket133: Align customer execution resource tags

PR: #133
Branch: fix/customer-execution-tag-contract

## Problem / goal

Align the App Runner workload module's ownership tag with the scoped customer execution role's required request and resource tag policy.

## Current repo state

The isolated CodeBuild runner reached Terraform but the customer role rejected initial VPC, ECR, and log-group creates before any workload resource completed. The role allows only requests tagged `ManagedBy=davdeploy` for its connection, while the module used `ManagedBy=terraform`.

## Research / references used

- The customer CloudFormation execution role policy and tag conditions.
- The App Runner customer Terraform module resource tags.
- The real CodeBuild failure, which shows no successful workload resource creation.

## Work planned for the PR

- Change the workload module ownership tag to `ManagedBy=davdeploy`.
- Add a contract test tying the module tag to the connection role policy.

## Acceptance criteria

- [x] Module resources use the policy-required ownership tag.
- [x] The module keeps the per-connection tag required by the role policy.
- [x] Focused customer contract tests and Terraform validation pass locally.
- [ ] Required GitHub CI passes.
- [ ] Updated template is published and the existing customer connection stack is updated before a fresh plan/apply.

## Acceptance status

Implementation and focused local validation are complete. CI, template publication, customer stack update, and a fresh reviewed plan remain.

## Tests / validation performed

- `.venv/bin/python -m pytest -q tests/test_same_account_pilot.py tests/test_customer_cloud_lifecycle.py tests/test_customer_aws_connection_contract.py` passed: 13 tests.
- `.venv/bin/python -m ruff check tests/test_same_account_pilot.py` passed.
- `terraform -chdir=infrastructure/terraform/customer-workload-app-runner-pilot fmt -check` passed.
- `terraform -chdir=infrastructure/terraform/customer-workload-app-runner-pilot validate` passed.
- `git diff --check` passed.

## Evidence files produced

- `docs/tickets/ticket133.md`
- Live customer-pilot evidence continues in `docs/test/test130.md`.

## Boundaries

This preserves the existing bounded role design. It grants no new services, broad roles, or arbitrary Terraform commands; it only makes the reviewed resource tags satisfy the existing policy.

## Follow-up work

- Publish the signed/versioned connection template via the protected deployment flow.
- Update the existing customer connection stack through CloudFormation.
- Create a fresh saved plan and governed apply, then continue observation and destroy evidence.
