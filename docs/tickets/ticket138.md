# ticket138: Permit tagged security group egress removal

PR: #138
Branch: fix/customer-security-group-egress

## Problem / goal

Allow the bounded Terraform runner to remove the default egress rule from the
newly tagged customer workload security group.

## Current repo state

The latest reviewed apply created the replacement VPC and two private subnets, then
stopped while Terraform attempted to revoke the default IPv4 egress rule. The role
did not include `ec2:RevokeSecurityGroupEgress`.

## Research / references used

- The real CodeBuild failure for the reviewed apply run
  `93c24455-1f4a-4528-8b09-aa30826933ed`.
- The workload module's deliberate no-default-egress security-group boundary.
- The role's existing `ManagedBy` and `ConnectionId` resource-tag gate.

## Work planned for the PR

- Add only `ec2:RevokeSecurityGroupEgress` to the tagged-resource reconciliation
  statement.
- Add a static role-contract regression assertion.

## Acceptance criteria

- [x] The role can remove default egress only after DavDeploy ownership tags exist.
- [x] No ingress, egress-authorize, broad EC2, service, image, or deletion authority is added.
- [ ] Focused tests, CloudFormation validation, and GitHub CI pass.
- [ ] The versioned template and existing test customer connection stack are updated.

## Acceptance status

Implementation is complete. Validation, template publication, stack update, and a
fresh signed plan remain.

## Tests / validation performed

- Pending: focused lifecycle tests, CloudFormation template validation, documentation
  conventions, diff check, and required CI.

## Evidence files produced

- `docs/tickets/ticket138.md`
- Live customer workload evidence continues in `docs/test/test130.md`.

## Boundaries

The action is constrained by the existing resource-tag conditions. It preserves the
module's explicit no-default-egress posture and does not allow new network paths.

## Follow-up work

- Publish the immutable template and update the existing customer connection stack.
- Generate another exact Terraform plan before any next apply.
