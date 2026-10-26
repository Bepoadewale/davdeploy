# Terraform operations bootstrap

This root creates only the low-cost prerequisites used by the manually dispatched Terraform plan
and apply workflows:

- encrypted saved-plan and immutable release buckets;
- dedicated KMS keys;
- separate GitHub OIDC roles for planning and applying.

The apply role can create only the AWS service-linked roles required by the managed RDS and
Cognito-email integrations. It cannot create general-purpose IAM roles outside the named
DavDeploy runtime roles.

It adopts the existing davdeploy state bucket, lock table, and GitHub OIDC provider as data
sources. It does not create or apply the serverless control plane.

The OIDC trust uses GitHub's configured immutable subject form with owner and repository IDs. If
the repository is transferred or recreated, update `github_oidc_repository_subject` through a
reviewed PR before running either workflow.

Initialize this root against the existing remote backend:

```bash
terraform init -reconfigure \
  -backend-config="bucket=davdeploy-tfstate-654654474502" \
  -backend-config="key=terraform-operations-bootstrap/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=davdeploy-terraform-locks" \
  -backend-config="encrypt=true"
```

Always review a saved plan before applying this bootstrap. Configure GitHub environments only from
the verified Terraform outputs.
