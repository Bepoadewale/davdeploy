# test252 — Real AWS Batch workload certification

Date: 2026-11-02

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

Pending after this PR's explicit Fargate public-IP and CloudWatch Logs
configuration is applied.
