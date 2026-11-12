# test381 — preserve the currently published customer role template

- Date: 2026-11-12
- Execution type: Local tests and read-only Terraform plan/state inspection
- Repository: `Bepoadewale/davdeploy`
- Customer repository: N/A; this is the DavDeploy customer-template host root.
- Commit: pending final PR head
- Pull request: [#381](https://github.com/Bepoadewale/davdeploy/pull/381) (draft)
- AWS account: `654654474502` (read-only plan and state inspection only)
- AWS region: `us-east-1`

## Purpose

Preserve the current content-hash CloudFormation URL while Terraform publishes
the next customer connection template. Existing CloudFormation stacks and
saved Quick Create links may still reference that URL.

## Commands executed

- `.venv/bin/python -m pytest tests/test_customer_aws_connection_contract.py -q`
  — 9 passed.
- `make verify` — 1,050 passed; Ruff, Actions configuration, OpenAPI snapshot,
  and Docker Compose checks passed. One existing Starlette/httpx deprecation
  warning remains.
- `make terraform-validate` — formatting and validation passed for every
  configured Terraform root.
- `terraform -chdir=infrastructure/terraform/connection-template-host
  fmt -check -recursive` — passed.
- `terraform -chdir=infrastructure/terraform/connection-template-host
  validate` — passed.
- `git diff --check` — passed.
- Read-only Terraform state listing confirmed the current template was
  represented by `aws_s3_object.published_customer_discovery_role` and the
  existing older object keys were in the retained map.
- The initial read-only template-host plan proposed one add and one destroy:
  it would replace the current `f3d9…` template URL. No apply was run.
- The first source correction stopped at Terraform's `Moved object still
  exists` validation because a move source was still declared as the current
  resource. After assigning the new object a fresh `current_…` address, the
  read-only plan proposed one new object, zero changes, and zero destroys. It
  moved the existing `published_…` state address to the retained map at the
  exact `f3d9…` key. No apply was run.
- A fresh clean-room `make local-proof` was not run locally because the
  existing DavDeploy Compose stack occupies its fixed host ports and must be
  preserved. The PR's required CI clean integration proof remains the gate.

## Resources created

None. The new template object was only present in a Terraform plan; it was not
created. No customer AWS role or stack was created.

## Observed result

The current URL remains configured as an immutable retained object with
`prevent_destroy` and `ignore_changes = all`. The new template is only planned;
no S3 object, bucket, IAM role, CloudFormation stack, or customer resource was
created, changed, or deleted. Terraform state was read and released normally.

## Teardown

None. No resource was created by these checks. The local DavDeploy Compose
stack and its volume were left running and untouched.

## Final boundary

This evidence proves only the source configuration and read-only plan for the
template-host root. It does not prove publication, customer role setup,
effective permissions, hosted Nova planning, or any customer workload.
