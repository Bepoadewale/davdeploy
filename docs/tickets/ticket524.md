# ticket524 — Correct ECS Express pricing evidence after PR #522

PR: #524  
Branch: `feat/ecs-express-pricing-522`

## Problem / goal

PR #522 added the bounded ECS Express price model and was merged after all
seven final-head CI checks passed. Its ticket records a live price evaluation
as “approval-eligible,” but the evaluation used a synthetic persisted-context
digest and did not include a customer's persisted budget. The evidence must
state the price-model result accurately without implying that this test plan
can authorize a customer workload.

## Scope

- Correct `docs/tickets/ticket522.md` to distinguish a complete live-price
  model evaluation from customer approval evidence.
- Record the capture time, test-plan digest, estimated range, and synthetic
  context limitation.
- Do not change pricing implementation, AWS resources, Terraform state, or
  the hosted control plane.

## Current repo state

- Backend `main` is `a456b84aa17600daf2b2c0bfe51d3bddb67e59ba`, which includes
  merged PR #522.
- PR #522's final-head CI passed all seven checks in run `45900573713`.
- PR #519 remains the open default-off renderer/runner package. Its IAM scope
  and isolated lifecycle evidence remain separate from this documentation
  correction.

## Research / references used

- [`ticket522.md`](ticket522.md) — original ECS Express cost-model evidence.
- [`NOVA_ECS_EXPRESS_PRICING.md`](../product/NOVA_ECS_EXPRESS_PRICING.md) —
  supported shape, usage assumptions, and regional price coverage.
- [AWS Price List `GetProducts` API](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_pricing_GetProducts.html)
  — regional product lookup used by the evaluator.

## Work planned for the PR

1. Correct the claim about approval eligibility in the merged pricing ticket.
2. Preserve the complete estimate and its exact source-plan identity while
   labeling the context as synthetic.
3. Run documentation and whitespace checks; require final-head CI before
   merging.

## Evidence checked

- PR #522 merged as commit `a456b84aa17600daf2b2c0bfe51d3bddb67e59ba` after
  final-head CI run `45900573713` passed all seven checks.
- The retained local provider-generated create plan has SHA-256
  `73e9596b651cdeb9095ae39bb1d182ea286dd4362a0495d2782e9011ff6e804e`.
- Read-only regional AWS Price List evaluation at `2026-11-26T21:55:12Z`
  returned `COMPLETE`, with 12 modeled lines and a monthly estimate of USD
  1.27–415.81 under the documented synthetic usage assumptions.
- The evaluation used a synthetic persisted-context digest and no customer
  budget. It is not bound to a persisted customer revision, is not approval
  evidence, and does not impose a hard spending limit.
- No AWS workload, hosted-control-plane resource, remote Terraform state, or
  lock was changed or accessed.

## Acceptance criteria

- [x] The merged #522 ticket no longer calls the synthetic test evaluation
  customer-approval-eligible.
- [x] The estimate, capture time, 12-line coverage, plan digest, and synthetic
  context limitation are recorded.
- [x] The distinction between estimated usage and an enforced billing cap is
  explicit.
- [x] No runtime, infrastructure, customer configuration, or control-plane
  behavior is changed.
- [x] Documentation conventions, whitespace checks, and final-head CI pass.

## Acceptance status

The evidence correction is recorded. Documentation validation and all seven
final-head CI checks passed in run `45907870966`. `COMPLETE` describes coverage
of the modeled price lines for this test plan and synthetic assumptions; it
does not pass customer approval or permit execution.

## Tests / validation performed

- `GITHUB_PR_NUMBER=524 python3 scripts/check_doc_conventions.py`: passed.
- `git diff --check`: passed.
- Final-head GitHub Actions run
  [45907870966](https://github.com/Bepoadewale/davdeploy/actions/runs/45907870966)
  passed all seven checks.

## Validation plan

- Run the repository documentation-convention checker with PR number 524.
- Run `git diff --check`.
- Require all final-head GitHub Actions checks to pass.

## Boundaries

- Do not treat the synthetic pricing context as a customer approval artifact.
- Do not claim this estimate is a hard cap or measured customer spend.
- Do not mutate AWS or the hosted control plane.
- Do not delete retained plans, evidence, worktrees, or branches.

## Evidence files produced

No `docs/test/test524.md` is required: this documentation-only correction
performed no customer workload test or cloud mutation.

## Follow-up work

Use an actual integrity-checked customer revision and explicit customer budget
for any approval-bound price evidence. Separately complete effective IAM
review, isolated remote-state runner lifecycle evidence, and Nova-originated
execution proof before enabling the renderer.
