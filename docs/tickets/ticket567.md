# ticket567 — Guide Nova to the HTTP health target for Lambda APIs

PR: #567
Branch: `fix/nova-http-health-target-567`

## Problem / goal

The first post-deployment v27 hosted plan-only request failed after two bounded
generation attempts. Sanitized feedback says `http_response` targeted an
`aws_lambda_function`. The unchanged architecture already includes API
Gateway, so the next repair should point the HTTP health assertion at the
declared API Gateway stage that routes to the Lambda. This PR adds fixed
pair-specific repair guidance and regression coverage without weakening
health requirements, inventing resources, changing policy, or widening IAM.

## Current repo state

- Backend `main` is PR #566 merge `5f37cc964d0a8da64bd474629a872bde9943f701`;
  this PR branch adds the prompt/feedback correction and tests.
- Prompt version `terraform-nova2-contract-v27` is deployed in AWS account
  `654654474502`, region `us-east-1`.
- Fresh revision `4fd24a64-2bca-4ecc-a217-5d0e5d13e02e` retained the established
  content digest and was submitted with no decision and
  `UNEXECUTED_APPROVAL_ONLY`.
- Its only v27 run, `b12a8f36-08f7-4184-8aaf-859eed337a2e`, failed as
  `NOVA_GENERATION_FAILED` / `proposal_invalid` after two attempts. Safe
  feedback is `value_error`, field `health_assertions[*].target_resource_id`,
  issue `incompatible_health_target`, assertion kind `http_response`, observed
  type `aws_lambda_function`. It produced no CodeBuild build or artifact and
  created no workload resources.
- The source architecture plan `539f558d-16cf-4359-921a-9205a7e81bfe` is still
  unapproved. Its selected profile is `aws-lambda-api` and its components
  include both Lambda and API Gateway.

## Research / references used

- `apps/api/src/davdeploy/terraform_generation.py`: typed health assertion
  schemas, `_HEALTH_TARGET_PAIR_GUIDANCE`, bounded repair and sanitized
  feedback.
- `apps/api/src/davdeploy/generated_deployment_contract.py`: allowed health
  assertion target types.
- `docs/test/test566.md`: local proof, cleanup, and deployed v27 baseline.
- `docs/test/test567.md`: exact hosted failure evidence for this package.

## Work planned for the PR

- Add a fixed `http_response` + `aws_lambda_function` feedback pair explaining
  that HTTP health targets the already-declared API Gateway stage only when
  the declared integration graph routes to that Lambda.
- Keep model repair bounded and preserve the original customer requirements
  and trusted context. If the required API Gateway relationship is absent,
  return the existing honest limitation path rather than adding resources just
  to satisfy a check or weakening the assertion.
- Add regression coverage for the fixed guidance, successful correction to an
  existing compatible stage, and unchanged failure behavior when no supported
  relationship exists.
- Bump the Nova prompt version to v28 and record required local/hosted evidence.

## Acceptance criteria

- [x] HTTP response feedback for a Lambda target gives exact fixed stage-target
      and existing-integration guidance.
- [x] A valid declared API Gateway stage can repair the target without changing
      trusted context or customer requirements.
- [x] Missing/incompatible API Gateway relationships fail safely without
      invented resources, weakened checks, or broader policy.
- [ ] Focused tests, full verification, docs conventions, required clean-room
      gate, and all required CI checks pass.
- [ ] One fresh post-deployment v28 plan-only result is recorded with no
      customer workload approval, apply, or destroy.

## Acceptance status

Implementation and focused/full local verification are complete. Clean-room
and hosted v28 checks remain.

## Tests / validation performed

- `PYTHONPATH=apps/api/src /Users/adewale/Projects/davdeploy/.venv-pr399/bin/python -m pytest -q tests/test_terraform_generation.py tests/test_customer_plan_review.py tests/test_nova_plan_runs.py` — 152 passed.
- `GITHUB_PR_NUMBER=567 make verify PYTHON=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python VENV=/Users/adewale/Projects/davdeploy/.venv-pr399` — 2,105 passed; Ruff, Actions configuration, OpenAPI snapshot, and Compose syntax passed. Compose was parsed only; no containers were started by this command.
- `GITHUB_PR_NUMBER=567 python3 scripts/check_doc_conventions.py` and `git diff --check` — passed.
- Read-only hosted v27 result inspection and source-architecture component check are recorded in `docs/test/test567.md`.
- Isolated clean-room verification and GitHub CI are pending.

## Evidence files produced

- `docs/test/test567.md` — deployed v27 failure baseline and the later v28
  plan-only outcome.

## Boundaries

No customer workload resources are approved, applied, or destroyed in this
package. No control-plane change is deployed until the PR passes review and
the exact protected plan is reviewed. Do not retrieve raw Nova proposals,
saved plan values, Terraform state, tokens, or signed URLs.

## Follow-up work

After merge and protected deployment, create a fresh unapproved review-only
revision with the same trusted architecture digest and request one v28
plan-only run. Inspect only sanitized diagnostics or the value-free saved-plan
summary. A plan is not application, lifecycle, or certification evidence.
