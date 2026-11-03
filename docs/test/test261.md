# PR #261: Real SageMaker endpoint inference certification

## Classification

Real disposable AWS execution. This is not a customer workload and it did not
use customer credentials or data.

## Scope

- Repository/commit under test: `Bepoadewale/davdeploy`, PR #261 branch
  `test/real-sagemaker-inference` at `b091f8d` plus this evidence commit.
- Account/region: `654654474502`, `us-east-1`.
- Test ID: `certsagemaker20261103a`.
- Opt-in boundary: `DAVDEPLOY_DISPOSABLE_CERTIFICATION=certsagemaker20261103a`.

## Created resources

- Private AES256-encrypted S3 artifact bucket
  `davdeploy-certsagemaker20261103a-artifacts`.
- SageMaker execution role
  `davdeploy-certsagemaker20261103a-endpoint`, scoped to that bucket's model
  prefix and the AWS-managed XGBoost image pull.
- SageMaker model, endpoint configuration and `ml.m5.large` real-time endpoint
  `davdeploy-certsagemaker20261103a`.

## Commands and observed result

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
Terraform created the endpoint successfully in 3 minutes 22 seconds. The live
`sagemaker-runtime InvokeEndpoint` CSV probe returned:

```json
{
  "ContentType": "text/csv; charset=utf-8",
  "InvokedProductionVariant": "primary",
  "response_body": "1.8520760536193848"
}
```

## Teardown and absence checks

The destroy operation used run ID `cert-sagemaker-destroy-20261103a` and
completed with `8 destroyed`. It removed the endpoint, configuration, model,
role policy, role, bucket encryption/public-access configuration, and bucket.

After the destroy completed, both independent checks passed:

```text
aws sagemaker describe-endpoint --endpoint-name davdeploy-certsagemaker20261103a
# ValidationException: endpoint absent

aws s3api head-bucket --bucket davdeploy-certsagemaker20261103a-artifacts
# Not Found: bucket absent
```

## Limitations

This certifies the bounded SageMaker real-time XGBoost endpoint module: owned
artifact, create, successful inference, and cleanup. It does not certify
customer training pipelines, GPU inference, model registry, autoscaling,
private VPC endpoints, or arbitrary model containers.
