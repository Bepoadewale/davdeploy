# ticket142: Assume the scoped customer role in the isolated executor

PR: #142
Branch: fix/customer-executor-assume-role

## Problem / goal

Ensure the isolated CodeBuild executor assumes the verified, scoped customer
execution role before it invokes Terraform or customer-cloud APIs.

## Current repo state

The real customer apply reached the App Runner service-linked-role prerequisite
and failed safely because it was still using the control-plane CodeBuild role.
The customer role and its external ID already exist; the runner fetched the
external ID but did not call AWS STS AssumeRole.

## Research / references used

- `scripts/customer-workload-app-runner-pilot.sh`
- `infrastructure/terraform/serverless-control-plane/main.tf`
- `infrastructure/cloudformation/customer-discovery-role.yaml`

## Work planned for the PR

- Fetch the external ID with the executor's bootstrap credentials.
- Assume only `DAVDEPLOY_CUSTOMER_EXECUTION_ROLE_ARN` using that external ID.
- Export only the short-lived resulting session for customer operations.
- Add static contract coverage.

## Acceptance criteria

- [x] Terraform and AWS customer operations execute with a scoped STS session.
- [x] The external ID is never logged or written to an artifact.
- [x] The bootstrap executor retains only the permissions needed to retrieve the
  secret and assume the approved customer role.
- [ ] Focused tests and required CI pass.
- [ ] The released runner completes a fresh real customer plan and apply.

## Acceptance status

Implementation is complete. Focused local validation passed; required GitHub CI,
guarded release, and a fresh live customer apply remain.

## Tests / validation performed

- `bash -n scripts/customer-workload-app-runner-pilot.sh`
- `.venv/bin/python -m pytest -q tests/test_same_account_pilot.py tests/test_customer_cloud_lifecycle.py tests/test_customer_aws_connection_contract.py`
- `git diff --check`
- `.venv/bin/python scripts/check_doc_conventions.py` pending this ticket-format update.

## Evidence files produced

- Customer live-run evidence will be appended to `docs/test/test130.md` after
  the reviewed lifecycle completes.

## Boundaries

- This PR does not broaden customer-role permissions or accept user-supplied
  commands.

## Follow-up work

- Release the immutable runner through the guarded control-plane workflow.
- Generate a fresh plan and apply using the verified role assumption.
- Implement the separately governed application source delivery and service
  activation stage.
