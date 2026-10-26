# ticket176 — Permit Cognito SES service-role bootstrap

PR: [#176](https://github.com/Bepoadewale/davdeploy/pull/176)
Branch: `fix/cognito-ses-service-role`

## Problem / goal

Enabling Amazon SES for Cognito email delivery requires Cognito to create its AWS-managed email
service-linked role once. The dedicated Terraform apply role allowed the equivalent RDS role but
not the Cognito email role.

## Work planned for the PR

- Permit only `iam:CreateServiceLinkedRole` for Cognito's named email service-linked role.
- Require the exact `email.cognito-idp.amazonaws.com` service name condition.
- Record that narrow boundary in the bootstrap runbook.

## Acceptance criteria

- [x] The Terraform apply role cannot create arbitrary IAM roles through this permission.
- [x] A Cognito user pool can be configured with an SES sender without a manual IAM-policy edit.
- [x] Terraform validates the bootstrap root.

## Tests / validation performed

- `terraform fmt -check infrastructure/terraform/terraform-operations-bootstrap`
- `terraform -chdir=infrastructure/terraform/terraform-operations-bootstrap validate`

## Boundaries

This change does not grant application workloads any IAM role-management permissions.
