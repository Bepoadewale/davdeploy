# PR #261: Certify real SageMaker endpoint inference

## Goal

Make the SageMaker endpoint module executable with an explicit immutable model
artifact, then add an opt-in disposable AWS certification that uploads a small
locally trained XGBoost artifact, creates an endpoint, invokes it, and destroys
the endpoint and owned artifacts.

## Current state

The module created a SageMaker model with an image URI but no `model_data_url`.
SageMaker models require a packaged artifact for this XGBoost deployment path,
so an endpoint could not be honestly certified by resource creation alone.

## Work

- Require the immutable `model_data_url` in the reusable endpoint module.
- Add an isolated SageMaker validation root with an encrypted private artifact
  bucket and a least-privilege endpoint role.
- Add a certification command that builds a minimal XGBoost artifact, invokes
  the live endpoint with a CSV payload, records evidence, and destroys owned
  resources.

## Acceptance criteria

| Criterion | Status |
| --- | --- |
| Module requires a model artifact | Met locally |
| Artifact bucket is private and encrypted | Met locally |
| Endpoint role is scoped to its model artifact and managed image pull | Met locally |
| Real endpoint invocation and teardown are recorded | Pending live run |

## Evidence and boundaries

The live run will be recorded in `docs/test/test261.md`. It uses only a
temporary, tagged artifact bucket, IAM role, SageMaker model/configuration and
endpoint in account `654654474502`, `us-east-1`. SageMaker retains immutable
training/job history by service design if a training job is used; this
certification instead creates the model artifact locally so all created AWS
resources are owned by and removed through Terraform.

## References

- AWS SageMaker XGBoost input/output interface and supported versions.
- AWS SageMaker model artifact packaging requirements.
