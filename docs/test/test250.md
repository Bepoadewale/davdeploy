# test250 — Real workload certification evidence

Date: 2026-11-02

Execution type: Local helper validation.

Customer repository: None.

Commit: In progress.

AWS account: None.

AWS region: None.

## Resources created

None.

## Commands executed

`scripts/terraform_run_monitor.py start apply infrastructure/terraform/module-validation/delivery --run-id cert-web-20261102a --terraform-arg='-var=test_id=certwebworkload20261102a'`

`scripts/verify_workload_evidence.py https://ppweqfrb94.execute-api.us-east-1.amazonaws.com --evidence /tmp/cert-web-health.json`

`scripts/terraform_run_monitor.py start destroy infrastructure/terraform/module-validation/delivery --run-id cert-web-destroy-20261102a --terraform-arg='-var=test_id=certwebworkload20261102a'`

## Observed result

The disposable Lambda/API Gateway workload returned HTTP 200 with
`{"ok":true}`. The monitored destroy removed all 13 resources, including the
API, Lambda, ECR repository, private S3 bucket and IAM role.

## Teardown

No resources were created.

## Final boundary

A response health check is evidence, not deployment authority. CloudFront,
identity and DNS/TLS still require their own composed workload tests.
