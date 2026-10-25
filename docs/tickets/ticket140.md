# ticket140: Bootstrap App Runner prerequisite in approved runner

PR: #140
Branch: fix/runner-apprunner-prerequisite

## Problem / goal

Make the approved customer runner create the one-time, AWS-managed App Runner
service-linked role before it applies the exact reviewed Terraform artifact.

## Current repo state

The role policy allows only App Runner service-linked-role creation, but
`CreateVpcConnector` still failed when App Runner attempted its first-use bootstrap.
The terminal cannot assume the customer role, by design, so the prerequisite must run
inside the trusted isolated runner.

## Research / references used

- The real VPC connector failure for reviewed apply run
  `136f0a59-4d21-4c8b-8985-78f1074c1974`.
- The scoped `iam:CreateServiceLinkedRole` permission in customer template PR #139.
- The existing artifact-bound `apply-saved-plan` runner boundary.

## Work planned for the PR

- Add a bounded helper that requests only the App Runner service-linked role.
- Treat the AWS "already exists" response as idempotent success.
- Run it only after saved-plan digest verification and immediately before apply.
- Add a static regression check.

## Acceptance criteria

- [x] No plan-only or destroy operation creates the prerequisite.
- [x] The helper cannot request a service-linked role for another AWS service.
- [x] The saved-plan checksum is verified before the prerequisite and Terraform apply.
- [ ] Focused tests and GitHub CI pass.
- [ ] The updated runner artifact is released through the guarded control-plane workflow.

## Acceptance status

Implementation is complete. Validation, CI, guarded release, and a fresh customer
plan/apply remain.

## Tests / validation performed

- Pending: same-account pilot checks, focused tests, shell syntax, documentation
  conventions, diff check, and required CI.

## Evidence files produced

- `docs/tickets/ticket140.md`
- Live customer workload evidence continues in `docs/test/test130.md`.

## Boundaries

The helper uses the existing customer execution role and only the App Runner AWS
service name. It does not expose credentials, execute user input, or alter a plan.

## Follow-up work

- Release the immutable runner through the manual Terraform plan/apply gate.
- Generate a fresh plan before the next customer apply.
