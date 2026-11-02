# test252 — Real AWS Batch workload certification

Date: 2026-11-02

Execution type: Controlled disposable AWS workload validation.

Customer repository: None.

Commit: `698d156` plus documentation correction in progress.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

A disposable AWS Batch Fargate compute environment, queue, job definition,
CloudWatch log group, IAM roles and security group, all tagged with a unique
test ID.

## Commands executed

## Initial execution

AWS account: `654654474502`  
AWS region: `us-east-1`  
Test ID: `certbatchworkload20261102a`

The initial disposable environment was applied and an Amazon Linux Fargate
Batch job was submitted. It failed before the container began with
`ResourceInitializationError`: the task could not reach the configured
CloudWatch logging destination. The environment was destroyed; Terraform
recorded `Destroy complete! Resources: 8 destroyed.`

## Corrective validation

AWS account: `654654474502`  
AWS region: `us-east-1`  
Test ID: `certbatchworkload20261102c`

`scripts/terraform_run_monitor.py start apply infrastructure/terraform/module-validation/batch --run-id cert-batch-20261102c --terraform-arg='-var=test_id=certbatchworkload20261102c'`

`aws batch submit-job --job-name davdeploy-certification --job-queue davdeploy-certbatchworkload20261102c --job-definition davdeploy-certbatchworkload20261102c`

`scripts/terraform_run_monitor.py start destroy infrastructure/terraform/module-validation/batch --run-id cert-batch-destroy-20261102c --terraform-arg='-var=test_id=certbatchworkload20261102c'`

## Observed result

- The Fargate job `eddc2d70-ab74-412c-91aa-8a6930dbec4f` reached `SUCCEEDED`
  with exit code `0`.
- Its CloudWatch stream emitted `davdeploy-certification`.
- Terraform recorded `Destroy complete! Resources: 9 destroyed.`
- A direct Batch compute-environment lookup returned no matching environment
  after teardown.

## Teardown

Terraform recorded `Destroy complete! Resources: 9 destroyed.` A direct Batch
compute-environment lookup returned no matching environment after teardown.

## Final boundary

The validation proves public-subnet Fargate networking and execution logging
for the module's minimal workload. It does not certify every customer image,
private networking topology or application-level retry policy.
