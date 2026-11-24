# ticket489 — verify the Lambda service module lifecycle

PR: [#489 — test: verify Lambda service module lifecycle](https://github.com/Bepoadewale/davdeploy/pull/489) (draft)
Branch: `test/lambda-service-lifecycle-489`

## Problem / goal

The capability matrix has real Lambda evidence through a combined HTTP API
renderer, but it does not exercise the exact `modules/lambda-service` Terraform
root alone. Add an isolated same-account test with a synthetic handler, a
least-privilege execution role for its own CloudWatch log group, a live invoke,
a code update, and reviewed teardown.

## Current repo state

- Backend `main` is `6e744ca6d3fea4d8df4cb73064207221979e6e60` (PR #488).
- The hosted control plane and its Terraform state/locks must remain untouched.
- AWS test account is `654654474502`, region `us-east-1`; the run monitor has
  54 terminal records and no active mutation at test start.
- The test will use local Terraform state and unique test tags; it is not a Nova
  dispatch or hosted execution test.

## Research / references used

- `infrastructure/terraform/modules/lambda-service/main.tf`
- `infrastructure/terraform/module-validation/delivery/main.tf`
- `docs/test/test268.md`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`
- AWS Lambda [Invoke API](https://docs.aws.amazon.com/lambda/latest/api/API_Invoke.html)

## Work planned for the PR

1. Add a fresh fixture that uses exactly one `modules/lambda-service` root and
   only its function, scoped role/policy, and explicit log group.
2. Invoke the v1 handler and verify a safe synthetic response; update the
   function code through Terraform and verify v2 from the same function ARN.
3. Destroy only the reviewed test resources through the run monitor and
   independently verify absence; retain local Terraform state.
4. Record exact live results and distinguish this module-root evidence from
   Nova dispatch, API Gateway behavior, customer authorization, and full cost.

## Acceptance criteria

- [ ] A reviewed create plan contains only the tagged exact-module test scope.
- [ ] The function invokes the synthetic v1 handler successfully.
- [ ] A reviewed Terraform update changes the same function to v2, and live
  invocation observes v2.
- [ ] Reviewed monitored teardown removes the function, role/policy, and log
  group; independent AWS reads confirm absence; local state is retained.
- [ ] Documentation and capability matrix report the exact evidence and limits.
- [ ] Focused/full checks, Terraform format/validate, docs conventions, diff
  checks, and final-head CI pass before merge.
- [ ] No control-plane, remote-state, unrelated AWS, or customer workload
  resources change.

## Acceptance status

Ticket-first draft opened before implementation. No AWS mutation has occurred
for PR #489. The package remains incomplete until live evidence and final CI
are recorded.

## Tests / validation performed

- Ticket-first documentation checks and PR creation are pending completion.

## Evidence files produced

- `docs/tickets/ticket489.md`
- `docs/test/test489.md`
- `docs/test/fixtures/nova-lambda-service-489/`
- `scripts/lambda_service_lifecycle.py`
- `tests/test_lambda_service_lifecycle_script.py`
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md`

## Boundaries

Create only the tagged function, role/policy, and log group in the verified
account/region. Use local Terraform state and the run monitor for each
Terraform mutation. Do not touch Nova's control plane, remote state, protected
files, or unrelated AWS resources. Keep handler data synthetic and out of logs.

## Follow-up work

Application API routing, tenant authorization, VPC execution, concurrency,
provisioned capacity, broader Lambda policies, full pricing, and Nova dispatch
remain separate evidence gates.
