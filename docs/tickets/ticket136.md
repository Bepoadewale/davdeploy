# ticket136: Permit bounded customer foundation reconciliation

PR: #136
Branch: fix/customer-foundation-policy-reads

## Problem / goal

Allow the trusted customer Terraform runner to finish a reviewed foundation apply
without widening it beyond the actions observed in the failed live run.

## Current repo state

The guarded apply created only the tagged VPC, ECR repository, and log group, then
failed before service creation. The runner lacked `ec2:ModifyVpcAttribute`,
`ecr:ListTagsForResource`, and `logs:PutRetentionPolicy`.

## Research / references used

- The real CodeBuild failure for cloud run `aeb3474a-c815-4596-a9c7-e8db7b3b15a1`.
- The existing bounded Terraform customer workload module.
- The tagged foundation resources observed in the customer account.

## Work planned for the PR

- Permit the regional VPC DNS-attribute update needed immediately after VPC creation.
- Permit read-only ECR tag inspection.
- Permit log-retention reconciliation only on resources already tagged to this connection.
- Add a static role-contract regression check.

## Acceptance criteria

- [x] Permissions are limited to the observed foundation actions.
- [x] Log-retention mutation remains constrained by DavDeploy and connection tags.
- [x] No service, image-push, network-egress, or deletion authority is added.
- [ ] Focused tests, CloudFormation validation, and GitHub CI pass.
- [ ] The immutable onboarding template and the test customer connection stack are updated.

## Acceptance status

Implementation is complete. Validation, template publication, stack update, and a
fresh signed customer plan remain.

## Tests / validation performed

- Pending: focused lifecycle tests, CloudFormation template validation, documentation
  conventions, diff check, and required CI.

## Evidence files produced

- `docs/tickets/ticket136.md`
- Live customer workload evidence continues in `docs/test/test130.md`.

## Boundaries

This PR changes only the scoped role policy. It does not rerun the failed artifact,
enable App Runner service creation, grant broad read/write permissions, or bypass
approval gates.

## Follow-up work

- Publish the new immutable template and update the existing customer connection stack.
- Generate a fresh plan and apply it only after review.
- Build the separately reviewed service-image and App Runner launch capability.
