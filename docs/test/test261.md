# test261 — Real SageMaker endpoint inference certification

Date: 2026-11-03

Execution type: Controlled disposable AWS execution, live inference probe, and verified teardown.

Customer repository: None. This was an isolated platform certification, not a customer workload.

Commit: `d76cd88` plus documentation-convention correction in progress.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

- Private AES256-encrypted S3 artifact bucket
  `davdeploy-certsagemaker20261103a-artifacts`.
- SageMaker execution role `davdeploy-certsagemaker20261103a-endpoint`, scoped
  to that bucket's model prefix and the managed XGBoost image pull.
- SageMaker model, endpoint configuration and `ml.m5.large` real-time endpoint
  `davdeploy-certsagemaker20261103a`.

## Commands executed

The bootstrap and endpoint operations used the repository PID monitor:

```text
AWS_PROFILE=ai-platform-pilot-key \
DAVDEPLOY_DISPOSABLE_CERTIFICATION=certsagemaker20261103a \
python3 scripts/terraform_run_monitor.py start apply \
  infrastructure/terraform/module-validation/sagemaker \
  --run-id cert-sagemaker-bootstrap-20261103a ...

AWS_PROFILE=ai-platform-pilot-key \
DAVDEPLOY_DISPOSABLE_CERTIFICATION=certsagemaker20261103a \
uv run --extra certification python scripts/certify_sagemaker_endpoint.py \
  --test-id certsagemaker20261103a prepare-artifact \
  --bucket davdeploy-certsagemaker20261103a-artifacts

AWS_PROFILE=ai-platform-pilot-key \
DAVDEPLOY_DISPOSABLE_CERTIFICATION=certsagemaker20261103a \
python3 scripts/terraform_run_monitor.py start apply \
  infrastructure/terraform/module-validation/sagemaker \
  --run-id cert-sagemaker-endpoint-20261103a ...

AWS_PROFILE=ai-platform-pilot-key \
DAVDEPLOY_DISPOSABLE_CERTIFICATION=certsagemaker20261103a \
uv run --extra certification python scripts/certify_sagemaker_endpoint.py \
  --test-id certsagemaker20261103a probe \
  --endpoint davdeploy-certsagemaker20261103a
```

The local helper generated a small XGBoost 1.7 model artifact and uploaded it
to `s3://davdeploy-certsagemaker20261103a-artifacts/model/certsagemaker20261103a/model.tar.gz`.

## Observed result

Terraform created the endpoint successfully in 3 minutes 22 seconds. The live
`sagemaker-runtime InvokeEndpoint` CSV probe returned:

```json
{
  "ContentType": "text/csv; charset=utf-8",
  "InvokedProductionVariant": "primary",
  "response_body": "1.8520760536193848"
}
```

## Teardown

The destroy operation used run ID `cert-sagemaker-destroy-20261103a` and
completed with `8 destroyed`. It removed the endpoint, configuration, model,
role policy, role, bucket encryption/public-access configuration, and bucket.

## Final boundary

After the destroy completed, `aws sagemaker describe-endpoint` returned a
validation error for the endpoint name and `aws s3api head-bucket` returned
Not Found for the artifact bucket. This certifies the bounded real-time
XGBoost endpoint path only, not customer training pipelines, GPU inference,
model registry, autoscaling, private VPC endpoints or arbitrary containers.
