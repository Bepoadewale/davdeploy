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

- [x] A reviewed create plan contains only the tagged exact-module test scope.
- [x] The function invokes the synthetic v1 handler successfully.
- [x] A reviewed Terraform update changes the same function to v2, and live
  invocation observes v2.
- [x] Reviewed monitored teardown removes the function, role/policy, and log
  group; independent AWS reads confirm absence; local state is retained.
- [x] Documentation and capability matrix report the exact evidence and limits.
- [x] Focused tests, Terraform format/validate, docs conventions, and diff
  checks pass locally.
- [ ] Final-head CI passes before merge.
- [x] No control-plane, remote-state, unrelated AWS, or customer workload
  resources change.

## Acceptance status

The tagged create plan contained four creates: the function, role, scoped log
policy, and log group. Monitored create
`nova-lambda-service-489-create-20261124` succeeded (Terraform PID `33754`).
The synthetic `v1` handler returned the expected response. The reviewed update
plan contained one in-place function change and no adds or deletes; monitored
update `nova-lambda-service-489-update-20261124` succeeded (Terraform PID
`35930`), and the same function returned `v2`. Monitored destroy
`nova-lambda-service-489-destroy-20261124` succeeded (Terraform PID `39105`)
from a reviewed four-delete plan. Independent AWS reads confirmed the function,
execution role, and log group absent; Terraform state lists no resources and
is retained; the run monitor has 57 records and zero active operations. No
control-plane or remote-state resource was changed. Final-head CI is pending.

## Tests / validation performed

- Focused lifecycle harness tests: 4 passed.
- Ruff, Terraform formatting and validation, documentation conventions,
  matrix evidence update, and diff checks passed locally.
- Initial implementation CI run `45482372222` passed all seven checks; the
  final evidence content requires a fresh run.

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
