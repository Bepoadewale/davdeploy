# test268 — Real serverless API renderer certification

Date: 2026-11-03

Execution type: controlled disposable AWS execution with a real Lambda, HTTP API request, and teardown.

Customer repository: None.

Repository: `Bepoadewale/davdeploy`.

Commit: `cf9cb47` (the renderer implementation used for certification).

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

Terraform created 9 resources for test ID `certserverlessapi20261104a`,
including a Lambda function and API Gateway HTTP API. All resources were
tagged by the isolated validation root.

## Commands executed

The repository PID monitor ran `apply` and `destroy` for
`infrastructure/terraform/module-validation/serverless-api` with the exact
test ID, expected account, and a 64-character plan digest. The apply run ID
was `cert-serverless-api-apply-20261104a`; the destroy run ID was
`cert-serverless-api-destroy-20261104a`. A real HTTPS request was sent to the
resulting API endpoint.

## Observed result

The endpoint returned HTTP 200 with body `{"ok":true}` from the packaged test
Lambda handler.

## Teardown

The destroy run completed with `Destroy complete! Resources: 9 destroyed.`
Read-only AWS API checks then confirmed that the Lambda function
`davdeploy-certserverlessapi20261104a-api`, HTTP API `8i52jbdvj5`, and IAM role
`davdeploy-certserverlessapi20261104a-api-lambda` no longer exist.

## Retained resources

No AWS resources from this test remain. Terraform's local state and provider
cache remain in the ignored validation directory for reproducibility and were
not removed.

## Final boundary

The deployment used synthetic test code and no customer account, customer
data, or production workload. This certifies the isolated Terraform renderer
root only; it does not certify dispatcher integration or customer execution.
