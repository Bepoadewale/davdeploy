# test253 — Real CloudFront content workload certification

Date: 2026-11-02

Execution type: Controlled disposable AWS workload validation.

Customer repository: None.

Commit: `5a6926c` plus evidence update in progress.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

A disposable S3 website bucket, website configuration, public read policy,
CloudFront distribution and test object. Every resource used
`TestId=certcloudfrontworkload20261102a`.

## Commands executed

`scripts/terraform_run_monitor.py start apply infrastructure/terraform/module-validation/cloudfront --run-id cert-cloudfront-20261102a --terraform-arg='-var=test_id=certcloudfrontworkload20261102a'`

`curl --fail --silent --show-error --max-time 30 https://d3kgf1abnl005h.cloudfront.net/`

`scripts/terraform_run_monitor.py start destroy infrastructure/terraform/module-validation/cloudfront --run-id cert-cloudfront-destroy-20261102a --terraform-arg='-var=test_id=certcloudfrontworkload20261102a'`

## Observed result

CloudFront served HTTPS content from the owned test origin:
`<html><body>davdeploy-cloudfront-certification</body></html>`.

## Teardown

Terraform recorded `Destroy complete! Resources: 6 destroyed.`, including the
distribution and the temporary S3 website origin.

## Final boundary

This certifies a public static-origin delivery path. Customer deployments should
prefer a private S3 origin with CloudFront Origin Access Control.
