# ticket342 — clarify the Nova plan-role permission boundary

PR: [#342](https://github.com/Bepoadewale/davdeploy/pull/342) (draft)
Branch: `fix/nova-plan-role-permission-copy-342`

## Problem / goal

PR #340 changed the plan role from deny-all to bounded metadata reads, with an
additional proposal-scoped explicit-deny policy on each fixed Nova planning
session. Some CloudFormation and API setup copy still says the role denies all
customer actions. Update that explanation and the verifier docstring without
claiming that DavDeploy attests effective customer permissions.

## Current repo state

- Backend `main` is `8d3b4764bcefae8cb9f93a930b064e10fd893762`; PR #340 is
  deployed under the protected release recorded in `docs/test/test341.md`.
- Plan-role metadata reads are bounded by a fixed action profile. The worker
  adds proposal-derived resources and explicit-deny session statements.
- Hosted runner, plan review, role verification, and state API flags remain
  disabled. No customer role or workload is changed by this PR.

## Research / references used

- [AWS IAM role session and permissions-boundary evaluation](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html): direct resource-policy grants to an assumed-role session are not constrained by implicit session-policy denial; explicit denies remain necessary.
- [AWS session policies](https://docs.aws.amazon.com/IAM/latest/UserGuide/troubleshoot_access-denied.html): a session policy limits the role's identity policy; it does not attest all external policy layers.
- PR #340's access profile is implemented in `apps/api/src/davdeploy/nova_plan_access.py` and the customer setup template is `infrastructure/cloudformation/customer-discovery-role.yaml`.

## Work planned for the PR

- Correct the CloudFormation template description.
- Explain the same boundary in customer-facing Quick Create steps and response
  text.
- Correct the plan-role verifier docstring while preserving the statement that
  it checks trust/account identity only.
- Add regression checks for the customer setup copy and template description.

## Acceptance criteria

- [ ] Template and customer setup copy describe bounded metadata reads and the
  proposal-scoped planner session policy accurately.
- [ ] Copy says effective permissions and later customer policy changes are
  not attested.
- [ ] Plan-role verification continues to check trust/account only and never
  claims policy verification.
- [ ] Focused tests, full `make verify`, docs conventions, and required CI pass.
- [ ] Hosted execution flags remain off; no AWS/customer role changes occur.

## Acceptance status

The template summary line is corrected in bootstrap commit `e386f04`. Remaining
setup copy, verifier documentation, regression tests, and validation are in
progress.

## Tests / validation performed

See `docs/test/test342.md`; exact commands and results will be added before the
PR is review-ready.

## Evidence files produced

- `docs/test/test342.md`

## Boundaries

This PR corrects wording and regression coverage only. It does not change IAM
permissions, trust, resource scoping, plan execution, policy attestation, or
customer feature gates. No customer credentials or AWS API calls are used.

## Follow-up work

Live customer role setup and role identity verification remain gated. Complete
pricing, remote-state planning, exact-plan approval, apply, health, recovery,
and teardown remain separate prerequisites before enabling hosted execution.
