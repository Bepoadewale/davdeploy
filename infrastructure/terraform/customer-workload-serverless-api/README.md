# Customer serverless API renderer

This root is invoked only by the checked-in bounded runner. It creates one
Lambda function and one HTTP API from a checksum-verified ZIP artifact under
the approved customer role. It accepts no free-form Terraform or IAM input.

The current certification artifact contract is deliberately small: a pinned
public GitHub commit must contain a root `index.py` defining `handler`, with
optional dependency files under `vendor/`. The fixed artifact builder places
those vendored files at the ZIP root. It does not run repository build scripts
or install dependencies. This source build operation is gated for hosted
certification and does not make Lambda/API customer deployments available.

The runner requires a project identifier. Terraform state, saved-plan files,
artifact and result objects, resource names, and ownership tags are scoped by
the verified cloud connection and project. It separates `plan` and
`apply-saved-plan`. Planning stores a Terraform saved-plan file below the
connection/project, approved-plan-digest, and operation prefixes and publishes
its SHA-256 digest with the change summary. Apply
requires that digest and uses the exact saved plan; it does not generate a
replacement plan.
If the plan object was overwritten or changed, apply fails before mutation.
The checked artifact is restored at a stable plan-specific path on each runner,
matching the file path embedded in Terraform's saved plan.
Destroy follows the same
`destroy-plan` and `destroy-saved-plan` sequence. Cleanup verification checks
the exact Lambda function, execution role, HTTP API name, and Terraform state.

This renderer currently keeps one deployed service state per project. Separate
development, staging, and production state selection is not part of its product
run contract yet.

The Terraform backend uses the runner's platform credentials. The AWS provider
uses the named temporary customer profile created after DavDeploy assumes the
approved customer role. The customer account ID is checked before lifecycle
work. This renderer remains outside the executable module registry until its
hosted CodeBuild lifecycle is separately certified.
