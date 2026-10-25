# ticket139: Permit App Runner service-linked role bootstrap

PR: #139
Branch: fix/apprunner-service-linked-role

## Problem / goal

Allow the first approved App Runner VPC connector in a customer account to create
the AWS-managed App Runner service-linked role it requires.

## Current repo state

The latest approved apply created the customer VPC, subnets, security group, ECR
repository, and log group, then App Runner rejected VPC connector creation because
the account has no App Runner service-linked role and the bounded role cannot create it.

## Research / references used

- The real CodeBuild failure for reviewed apply run
  `69025b25-c7b7-4263-bda9-7406543a9528`.
- AWS's App Runner API error identifying `iam:CreateServiceLinkedRole` with
  `apprunner.amazonaws.com` as the required first-use permission.
- The existing per-connection execution-role policy.

## Work planned for the PR

- Add only `iam:CreateServiceLinkedRole`.
- Constrain it to the `apprunner.amazonaws.com` service name.
- Add static contract assertions.

## Acceptance criteria

- [x] The runner cannot create service-linked roles for any other AWS service.
- [x] No customer IAM user, policy, arbitrary role, or broader pass-role authority is added.
- [ ] Focused tests, CloudFormation validation, and GitHub CI pass.
- [ ] The template and existing test customer connection stack are updated.

## Acceptance status

Implementation is complete. Validation, template publication, stack update, and a
fresh reviewed plan remain.

## Tests / validation performed

- Pending: focused lifecycle tests, CloudFormation template validation, documentation
  conventions, diff check, and required CI.

## Evidence files produced

- `docs/tickets/ticket139.md`
- Live customer workload evidence continues in `docs/test/test130.md`.

## Boundaries

The service-linked role is an AWS-managed App Runner prerequisite, not a DavDeploy
execution role. This cannot create service-linked roles for another service.

## Follow-up work

- Publish the immutable template and update the customer stack.
- Generate another exact plan before another apply.
