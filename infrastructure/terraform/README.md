# Terraform cloud-pilot contract

The current owner-controlled pilot uses two explicit placements in the same AWS
account. The platform runtime uses VPC `10.42.0.0/16` and state key
`davdeploy/platform/app-runner-runtime.tfstate`; the customer sandbox uses
VPC `10.84.0.0/16` and state key
`davdeploy/customer-sandbox/workload-app-runner.tfstate`. This is not a
cross-account isolation claim. See the
[same-account pilot boundary](../../docs/architecture/same-account-pilot.md).

**State: statically validated design. Nothing here has been applied to AWS.**

`bootstrap/` describes a separate encrypted/versioned state bucket, DynamoDB lock and budget guardrail. `terraform-operations-bootstrap/` adopts the existing state, lock and GitHub OIDC resources and creates the encrypted saved-plan storage, immutable release storage and environment-scoped plan/apply roles required by the manual GitHub workflows. `customer-connection/` describes customer-account IAM roles only: a discovery role and an empty future-execution role. `connection-template-host/` describes the separate, public-but-non-secret versioned template object that AWS CloudFormation needs for Quick Create. `pilot/` describes the private VPC, EKS, ECR, RDS, Secrets Manager and workload-identity foundation. Every resource uses project tags.

The bootstrap root requires a state-bucket name, AWS region, monthly budget and budget-notification email as values supplied outside Git. Do not commit a real `.tfvars` file.

Run static checks only:

```bash
make terraform-validate
```

See [the customer AWS connection](customer-connection/README.md) before using its authenticated plan command. It must be reviewed before its separately confirmation-gated apply.

A future cloud operator supplies account-specific values outside Git, reviews an authenticated plan and uses Terraform for both creation and teardown. The product API never runs Terraform.

The template host is deliberately separate from Terraform state. Its bucket exposes only `s3:GetObject` for versioned YAML below `cloudformation/`; it does not expose state, customer data, object listing or write permissions. Published objects use SHA-256-derived keys, stable key-derived Terraform addresses, an append-only key manifest, and `prevent_destroy` from creation. See [the append-only publishing design](../../docs/architecture/append-only-template-publishing.md). Run `make customer-aws-template-host-plan` before any separately confirmed apply.
