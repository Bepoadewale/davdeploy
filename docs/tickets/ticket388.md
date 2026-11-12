# ticket388 — keep the plan runner IAM policy within AWS limits

PR: pending
Branch: `fix/split-plan-runner-iam-policy-388`

## Problem / goal

Protected exact-plan apply `43301905882` failed when adding inline policy
`nova-plan-only-codebuild`: AWS rejected the API role's aggregate inline
policies for exceeding its 10,240-byte limit. The apply was partial: the fixed
CodeBuild project, its isolated role, artifact/bootstrap policies, event
resources, Lambda package updates, API runtime gates, and worker queue policy
were applied. Do not retry the stale saved plan. Store the fixed CodeBuild
`StartBuild` override-deny list in a separate IAM managed policy and produce a
fresh plan against the partially updated remote state.

## Current repo state

- Backend `main`: `ce173d8751454811141454ec1df58772d0fdfe29` (PR #387 merge).
- Apply `43301905882` is terminal failure due to IAM inline policy size. The
  failure happened after successful resource changes; its exact log states
  `Maximum policy size of 10240 bytes exceeded for role davdeploy-api`.
- Read-only AWS checks confirm the Nova runner, broker, plan review, state API,
  and role verification flags are true; hosted certification remains false.
  `ALLOW_CLOUD_APPLY=true` was already true before this deployment and remains
  unchanged. The plan-only CodeBuild project exists; API role policy
  `nova-plan-only-codebuild` was not created, so the API cannot start it.
- No customer Nova plan or workload has been applied. No destroy occurred.
- Protected untracked `--only-show-errors` remains untouched.

## Research / references used

- `infrastructure/terraform/serverless-control-plane/main.tf`
- `tests/test_nova_plan_only_infra.py`
- AWS IAM role inline-policy aggregate limit error from apply run `43301905882`.
- Original plan `43299990193` and manifest digest verified before its apply.

## Work planned for the PR

- Keep the API allow policy for only the fixed Nova CodeBuild project and run ID
  override as a small inline policy.
- Move the explicit per-override `StartBuild` Deny statements into one
  separately attached managed policy, preserving every existing deny key.
- Add checks that all fixed override keys remain denied and the managed-policy
  document remains under AWS's 6,144-character limit.
- Do not dispatch another apply using run `43299990193`; first create and
  inspect a fresh plan against the current state.

## Acceptance criteria

- [ ] API `StartBuild` allow remains limited to the fixed Nova plan project and
  trusted run ID environment override.
- [ ] Every override-presence deny remains attached to the API role.
- [ ] Managed policy is within its AWS size limit; focused tests and full
  verification pass.
- [ ] Required CI passes and PR merges.
- [ ] Fresh protected plan reconciles the partial apply, shows the expected
  remaining actions with no unrelated destroys, and stores a new plan.
- [ ] Exact new plan is reviewed before applying; no stale-plan retry occurs.

## Acceptance status

- [ ] Implementation and local verification pending.

## Tests / validation performed

- None yet.

## Evidence files produced

- `docs/tickets/ticket388.md`

## Boundaries

Keep the plan-only worker separate from `customer_executor`. This PR does not
enable customer apply approval, hosted certification, or pricing approval.
Do not weaken the fixed override-deny checks.

## Follow-up work

Apply only a fresh saved plan after exact action and runtime-gate review, then
verify live Lambda package identities, Nova gate values, API health, and the
CodeBuild runner's fixed configuration.
