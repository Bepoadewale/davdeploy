# test560 — Lambda health-target feedback

Date: 2026-11-27

Execution type: Hosted plan-only diagnostic baseline; no customer AWS workload

Customer repository: Synthetic DavDeploy acceptance case

Commit: `fe02d62f123e27712fee686db05029de8b7a33af` (deployed baseline)

AWS account: `654654474502` (control-plane release only)

AWS region: `us-east-1`

## Hosted v21 baseline

- Authenticated, read-only `GET /api/v1/generated-plan-runs/d61e0c32-0379-4bd2-a240-a7924f4e98a1`
  returned `FAILED`, prompt `terraform-nova2-contract-v21`, two generation
  attempts, one repair, and no artifact.
- Sanitized feedback identifies `incompatible_health_target` at
  `health_assertions[*].target_resource_id`, with assertion kind
  `container_readiness` and observed resource type `aws_lambda_function`.
- The fixed guidance lists allowed targets but does not explain how to preserve
  an HTTP or asynchronous health requirement when the application runtime is a
  Lambda function. No raw proposal, plan, state, or credential was retrieved.
- The repository Terraform run monitor has 75 historical records and no active
  mutation. AWS identity was verified as account `654654474502`.

## Resources created

No customer workload AWS resources were created or changed. The run failed
before a CodeBuild artifact or Terraform plan. No customer approval, apply, or
destroy occurred. This does not establish application health, pricing, plan
policy, or lifecycle behavior.

## Commands executed

- Authenticated, read-only CLI request for the v21 generated-plan run; output
  was restricted to status, prompt version, counts, artifact ID, and
  allowlisted validation feedback.
- Focused pytest suite (202 passed), full `make verify` (2,090 passed), Ruff,
  Actions configuration, OpenAPI, Compose, documentation convention, and diff
  checks.

## Observed result

The strict contract correctly rejects the incompatible Lambda/container pair.
Fixed feedback now preserves the health requirement and points only to an
already-declared API Gateway HTTP path or the declared SQS/Lambda event path.
When neither exists, the feedback requires a limitation; it never proposes
silently dropping the assertion. These are generation tests only, not proof a
health observer ran.

## Teardown

No customer resources were created, so there was nothing to tear down. Local
verification did not create any AWS resources.

## Implementation verification

The implementation adds allowlisted pair-specific guidance for
`container_readiness` targeting Lambda and includes the same instruction in the
trusted prompt. A bounded repair test moves an HTTP health assertion to a
predeclared API Gateway stage in a proposal whose typed references connect that
stage and integration to the Lambda. A separate test confirms the model gets an
honest limitation instruction when the declared graph has no compatible
alternative; generation still fails closed after its bounded attempts.

- Focused generator, contract, review, and run tests: 202 passed.
- `make VENV=/Users/adewale/Projects/davdeploy/.venv-pr399 verify`: 2,090
  passed; Ruff, Actions configuration, OpenAPI snapshot, and Compose checks
  passed. One existing Starlette/httpx deprecation warning remains.
- Direct Ruff, documentation convention, and `git diff --check` passed.
- Isolated clean-room proof passed on commit
  `003a54f218f7e42ccd079e2425040e1e76be068f`: `make
  VENV=/private/tmp/davdeploy-nova-health-cleanroom-560-venv local-proof`
  passed API smoke/contract, customer-plan E2E, seed and trace checks, Ruff,
  Actions configuration, 2,090 tests, OpenAPI, and Compose.
- `make VENV=/private/tmp/davdeploy-nova-health-cleanroom-560-venv clean-local`
  removed the exact nine containers created for the isolated proof, its Compose
  network/volume, generated `.local`, and external virtual environment.
  Follow-up inventory confirmed all were absent.
- Initial PR CI run `46073624716` passed all seven checks on implementation
  head `003a54f218f7e42ccd079e2425040e1e76be068f`. The evidence update
  triggers fresh final-head checks. Review, protected deployment, and a fresh
  review-only hosted run remain pending.

## Final boundary

This source change improves Nova's bounded repair instruction only. It does
not prove an inspectable Terraform plan, current pricing, plan-policy approval,
application health, or any customer lifecycle. No customer approval, apply,
or destroy occurred.
