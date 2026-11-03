# ticket261 — Real SageMaker endpoint inference certification

PR: [#261](https://github.com/Bepoadewale/davdeploy/pull/261)

Branch: `test/real-sagemaker-inference`

## Problem / goal

Make the SageMaker endpoint module executable with an explicit immutable model
artifact, then add an opt-in disposable AWS certification that uploads a small
locally trained XGBoost artifact, creates an endpoint, invokes it, and destroys
the endpoint and owned artifacts.

## Current repo state

The module created a SageMaker model with an image URI but no `model_data_url`.
SageMaker models require a packaged artifact for this XGBoost deployment path,
so an endpoint could not be honestly certified by resource creation alone.

## Research / references used

- AWS SageMaker XGBoost input/output interface and supported versions.
- AWS SageMaker model artifact packaging requirements.

## Work planned for the PR

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
| Real endpoint invocation and teardown are recorded | Met in `docs/test/test261.md` |

## Acceptance status

Complete: the scoped endpoint module accepted an owned immutable artifact, a
real endpoint served an inference request, and every temporary AWS resource
was destroyed and independently checked absent.

## Tests / validation performed

- `terraform -chdir=infrastructure/terraform/module-validation/sagemaker validate`
- `uv run --extra certification pytest -q tests/test_sagemaker_certification.py tests/test_certify_aws_scenario.py tests/test_universal_execution.py`
- `uv run --extra certification ruff check scripts/certify_sagemaker_endpoint.py scripts/certify_aws_scenario.py tests/test_sagemaker_certification.py`
- Real AWS create, live inference probe, destroy and absence verification in
  `docs/test/test261.md`.

## Evidence files produced

`docs/test/test261.md`

## Boundaries

The live run is recorded in `docs/test/test261.md`. It used only a
temporary, tagged artifact bucket, IAM role, SageMaker model/configuration and
endpoint in account `654654474502`, `us-east-1`. SageMaker retains immutable
training/job history by service design if a training job is used; this
certification instead creates the model artifact locally so all created AWS
resources are owned by and removed through Terraform.

## Follow-up work

This certifies only the bounded real-time XGBoost endpoint path. Customer
training, model registry, private-VPC, GPU and arbitrary-container variants
need their own disposable certification evidence before they can be claimed.
