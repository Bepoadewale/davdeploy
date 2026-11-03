# Customer serverless API renderer

This root is invoked only by the checked-in bounded runner. It creates one
Lambda function and one HTTP API from a checksum-verified ZIP artifact under
the approved customer role. It accepts no free-form Terraform or IAM input.

The runner separates `plan` and `apply-saved-plan`. Planning stores a Terraform
saved-plan file below the connection, approved-plan-digest, and operation
prefixes and publishes its SHA-256 digest with the change summary. Apply
requires that digest and uses the exact saved plan; it does not generate a
replacement plan.
If the plan object was overwritten or changed, apply fails before mutation.
The checked artifact is restored at a stable plan-specific path on each runner,
matching the file path embedded in Terraform's saved plan.
Destroy follows the same
`destroy-plan` and `destroy-saved-plan` sequence. Cleanup verification checks
the exact Lambda function, execution role, HTTP API name, and Terraform state.

The Terraform backend uses the runner's platform credentials. The AWS provider
uses the named temporary customer profile created after DavDeploy assumes the
approved customer role. The customer account ID is checked before lifecycle
work. This renderer remains outside the executable module registry until its
hosted CodeBuild lifecycle is separately certified.
