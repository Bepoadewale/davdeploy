# ticket340 — constrain customer Nova planning permissions

PR: Draft PR pending creation
Branch: `feat/nova-readonly-plan-scope-340`

## Problem / goal

The customer plan-only role created by the current template denies every customer service action. Trust and account verification do not establish effective policy, and broad read-only managed policies could expose customer data. Define and implement a bounded plan-permission contract so the fixed Nova planner can perform only documented metadata reads for explicitly supported Terraform resource types.

## Current repo state

- The plan-only CloudFormation role has an explicit deny on all customer service actions.
- The CodeBuild runner assumes the exact customer plan role using the connection ExternalId and verifies the target account before planning.
- Terraform resource provider schemas are validated, but proposal resource types are not yet bounded by a customer-plan permission profile.
- The runner, state API, role verification, and plan review are disabled in the hosted environment. Pricing is unavailable and approval is blocked.

## Research / references used

- AWS IAM policy evaluation and permissions boundary guidance: explicit denies override allows; resource-based grants can bypass some implicit-deny boundaries, so boundaries must explicitly deny out-of-profile actions.
- AWS IAM policy simulator documentation: simulated outcomes may differ from live authorization and must not be treated as sole evidence.
- Pinned AWS Terraform provider `5.100.0` resource read implementations and official AWS service authorization references for the supported read actions.

## Work planned for the PR

- Define an explicit resource-type to read-action profile for the first supported Nova planning slice; exclude secret/data-content APIs and all mutation actions.
- Reject unsupported resource types before customer credentials are assumed.
- Pass a trusted, bounded session policy when the CodeBuild worker assumes the customer plan role, including an explicit deny outside the read profile.
- Change the reviewed plan-only role template to grant only the profile needed by the fixed planner and keep any retained boundary deny explicit.
- Add regression tests for allowed metadata reads, denied mutation/data-content actions, unsupported resources, policy tampering/shape, and absence of credentials from logs/results.
- Keep all hosted feature gates disabled; do not claim this attests customer account SCPs or enables plan approval/apply.

## Acceptance criteria

- [ ] Resource types and customer API actions are finite, versioned, documented, and tied to the first supported workload slice.
- [ ] No mutating action, secret value, customer object body, or unrelated service read is granted by the planner profile.
- [ ] Unsupported proposal resources fail before customer credentials are assumed.
- [ ] Runtime credentials are further constrained by a server-generated, explicit-deny session policy.
- [ ] Tests prove tampered/missing profile bindings and policy-evaluation uncertainty fail closed.
- [ ] Hosted runner/state API/review gates remain disabled; pricing and customer apply remain blocked.
- [ ] Focused tests, `make verify`, Terraform checks, clean-room proof if required, docs checks, and required CI pass.

## Acceptance status

Draft scope only. No implementation or AWS changes have occurred.

## Tests / validation performed

Pending.

## Evidence files produced

- `docs/test/test340.md`

## Boundaries

No AWS calls or resource mutations. No hosted feature enablement, plan approval, apply/destroy, pricing implementation, or customer data retrieval. PR #318 pricing work remains held for account-owner direction.

## Follow-up work

This bounded planner permission profile is a prerequisite, not proof of hosted customer execution. After it is reviewed, complete trusted regional pricing and tenant-state execution boundaries before enabling customer plans.
