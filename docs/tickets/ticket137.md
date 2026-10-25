# ticket137: Permit bounded customer tag observation

PR: #137
Branch: fix/customer-workload-tag-observation

## Problem / goal

Allow Terraform to read ownership tags on already-created, customer-scoped resources
while it constructs the next signed plan.

## Current repo state

The fresh, plan-only CodeBuild run correctly stopped before creating anything new
because the role did not allow `logs:ListTagsForResource` on the tagged log group
created by the prior guarded apply.

## Research / references used

- The real plan-run CodeBuild failure for run `190fcfa3-2894-4d5d-9626-7a0ac6803754`.
- Terraform AWS provider reconciliation behavior for tagged Log Groups, App Runner
  services, and VPC connectors.
- The existing tag-gated customer execution contract.

## Work planned for the PR

- Add read-only CloudWatch Logs tag listing.
- Add read-only App Runner tag listing for the same Terraform reconciliation path.
- Add contract assertions for both actions.

## Acceptance criteria

- [x] Only tag-read actions are added.
- [x] No create, update, delete, network, credential, or image-push authority is added.
- [ ] Focused tests, CloudFormation validation, and GitHub CI pass.
- [ ] The immutable onboarding template and existing test customer connection stack are updated.

## Acceptance status

Implementation is complete. Validation, template publication, stack update, and a
fresh signed Terraform plan remain.

## Tests / validation performed

- Pending: focused lifecycle tests, CloudFormation template validation, documentation
  conventions, diff check, and required CI.

## Evidence files produced

- `docs/tickets/ticket137.md`
- Live customer workload evidence continues in `docs/test/test130.md`.

## Boundaries

The actions are read-only and serve Terraform state reconciliation only. They do not
change the trusted runner boundary or authorize any cloud mutation.

## Follow-up work

- Publish the versioned template and update the customer connection stack.
- Run a fresh cloud plan and only then evaluate a reviewed apply.
