# ticket356 — review unscoped Lambda invocation permissions in Nova plans

PR: [#356](https://github.com/Bepoadewale/davdeploy/pull/356) (merged)
Branch: `security/lambda-public-invoke-policy-356` (deleted after merge)
Base: `main`

## Problem / goal

The Nova plan access profile supports `aws_lambda_permission`, but generated
Terraform plan policy did not inspect its actual invocation principal or
source restriction. A wildcard principal with no source ARN can permit
unbounded function invocation. Unknown security-relevant permission values
must not be treated as safe.

## Current repo state

- PR #356 merged as `11e66e878933a69638128a8bab80115c051d230a` and was
  deployed through the protected control-plane workflow.
- Backend `main` includes the SQS public-policy hardening from PR #355.
- Generated-plan policy has separate deterministic checks for IAM, S3, SQS,
  databases, network ingress and EBS encryption.
- The customer Nova plan runner and approval gates remain disabled. The
  control-plane release updates the existing DavDeploy service only; it does
  not create or mutate customer infrastructure.

## Research / references used

- AWS [Lambda permissions](https://docs.aws.amazon.com/lambda/latest/dg/access-control-resource-based.html)
  documents resource-based invocation grants and source ARN restrictions.
- Terraform [JSON output format](https://developer.hashicorp.com/terraform/internals/json-format)
  defines `after_unknown` metadata used to reject unknown policy-critical
  values.

## Work planned for the PR

- Include Lambda permission action, function, principal, organization, source,
  and function-URL authentication fields in policy-critical unknown checks.
- Deny wildcard-principal invocation without a nonempty, non-wildcard source
  ARN.
- Mark a wildcard principal with a source ARN for explicit human review.
- Keep the fixed policy findings free of raw permission values.

## Acceptance criteria

- [x] Wildcard principal without a scoped source is denied.
- [x] Wildcard principal with a source restriction requires human review.
- [x] A specific service principal is not classified as wildcard public access.
- [x] Unknown principal, organization, source account/ARN, action, function,
  and function-URL authentication metadata is denied.
- [x] Focused tests, full verification, Ruff, docs checks and diff checks pass
  locally.
- [x] Isolated `make local-proof` passes without AWS or customer-resource
  mutation.
- [x] Required hosted CI passes on the final PR head.

## Acceptance status

Merged, locally verified, clean-room verified, and deployed. Final-head PR CI
run `43081014081` passed all seven required jobs. Codex review found no
blocker. Protected release evidence is in [`test356.md`](../test/test356.md).

## Tests / validation performed

- `uv run pytest tests/test_generated_plan_policy.py -q` — 101 passed.
- `DAVDEPLOY_DATABASE_URL=sqlite+pysqlite:///:memory: make verify` — 952
  passed; Ruff, Actions configuration, OpenAPI, and Compose checks passed.
- `COMPOSE_PROJECT_NAME=davdeploy-pr356-final-proof
  DAVDEPLOY_DATABASE_URL=sqlite+pysqlite:///:memory: make local-proof` — passed
  (952 tests, API contract, customer-plan E2E, seeded demo, trace check and
  Compose validation). Its dedicated project containers are stopped; the
  isolated worktree and seeded local database are retained for reproducibility.
- Focused Ruff, docs conventions and diff checks passed.
- Control-plane plan `43081890092` and exact saved-plan apply
  `43082767507` deployed merge commit `11e66e8`; migrations completed, all six
  Lambdas are Active/Successful, and `/healthz` returned HTTP 200. No customer
  plan, role, workload or resource was created or changed.

## Evidence files produced

- `docs/tickets/ticket356.md` records scope, tests and rollout boundary.
- The generated-plan policy regression tests are in
  `tests/test_generated_plan_policy.py`.
- `docs/test/test356.md` records the exact protected release and post-deployment
  health evidence.

## Boundaries

This is a deterministic plan-policy change. It does not enable customer plan
execution, infer API authentication safety, configure resource permissions,
approve a plan, or apply customer infrastructure. It does not claim complete
analysis of all Lambda, API Gateway or service resource policies.

## Follow-up work

Continue regional pricing, exact cost-bound approval, customer role
installation/effective permission verification, hosted state/runner apply,
health, recovery, teardown and composed workload certification.
