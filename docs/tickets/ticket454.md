# ticket454 — verify Step Functions failure recovery

PR: https://github.com/Bepoadewale/davdeploy/pull/454
Branch: `test/step-functions-recovery-454`

## Current repo state

- Backend `main` is `28ffd9cae0fecff2b94a7ab19039053e93053aca` (PR #453).
- The EventBridge #452 test stack is absent; Terraform monitor has no active
  operations.
- The current Step Functions test `test256.md` records a successful execution,
  but no injected task failure and recovery path.
- The hosted control plane and its Terraform state/locks are out of scope.

## Problem / goal

Current Step Functions evidence confirms only a simple successful execution.
Record one controlled failing Lambda task that Step Functions catches and
recovers, along with a separate ordinary success path and exact teardown.

## Research / references used

- AWS [error handling in Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html)
  documents Task `Retry` and `Catch` transitions.
- AWS [Lambda integration](https://docs.aws.amazon.com/step-functions/latest/dg/connect-lambda.html)
  documents task failure propagation and direct Lambda invocation.
- [`test256.md`](../test/test256.md) — existing simple state-machine execution
  evidence.
- `infrastructure/terraform/modules/step-functions/main.tf` — current root
  input shape and ownership of execution permissions.

## Work planned for the PR

1. Add a pinned Terraform fixture for a Standard state machine and a minimal
   synthetic Lambda worker; grant the state-machine role invoke access only to
   the exact test function.
2. Inject one task error, Catch it into a recovery state, and invoke the
   function again with a unique marker. Also prove the ordinary success path.
3. Redact input, output, exception details, and execution identifiers from
   probe output.
4. Open this draft PR and its evidence records before AWS writes; keep all
   Terraform state and generated archives outside the repository.
5. Destroy the exact test stack through the repository Terraform monitor and
   independently verify AWS absence.

## Acceptance criteria

- [x] Terraform plans exactly five creates with no updates or deletes.
- [x] A controlled Lambda task failure appears in Step Functions history and
      the Catch recovery execution completes with the expected marker.
- [x] A separate normal execution completes without using the recovery path.
- [x] The probe omits all execution input/output, exception text, and
      identifiers.
- [x] The exact five-resource stack is removed through monitored Terraform
      destroy; AWS and local state are independently confirmed empty.
- [x] Focused validation, docs conventions, and all seven required PR checks
      pass.
- [x] No control-plane or production resource is changed and no Nova dispatch
      or hosted execution is claimed.

## Acceptance status

The five-resource fixture created successfully and both probe paths passed
after the probe was corrected to match Lambda-specific history event names.
All four executions ended `SUCCEEDED`. Monitored teardown succeeded; exact
AWS reads and local state confirm cleanup. All seven checks passed on head
`c301c6f8330851c95d5d915b4f418c4d9bcee463` in run `45226919117`; a final-head
CI run will cover the AWS teardown evidence updates.

## Tests / validation performed

- `terraform init`, `terraform validate`, and the exact five-create saved plan
  passed; AWS's Step Functions definition validator returned `OK` with zero
  diagnostics.
- Ruff, Python syntax, Terraform format, documentation conventions, and
  `git diff --check` passed.
- All seven required checks passed on initial PR head `eddbcd6` in run
  `45222597413`; a final-head run is required after the evidence update.
- The first monitored create failed before AWS calls because `AWS_PROFILE` was
  absent from the subprocess environment. Exact-name reads found no partial
  resources. The corrected monitored create added exactly five resources.
- The first probe pass validated the service behavior but used generic task
  history event names. The probe now checks `LambdaFunctionFailed` and
  `LambdaFunctionSucceeded`; its corrected run passed all redacted assertions.
- Reviewed destroy plan: exactly five deletes, zero additions/updates.
- Monitored destroy `nova-stepfn-recovery-454-destroy-nov23a2` succeeded with
  five destroys. AWS confirmed the state machine, Lambda function, and both
  roles absent; Terraform state is empty and there are no active monitor runs.
- Final PR head `c301c6f8330851c95d5d915b4f418c4d9bcee463` passed all seven
  checks in run `45226919117`; final-head CI will rerun after recording the
  teardown and matrix evidence.

## Evidence files produced

- `docs/tickets/ticket454.md`
- `docs/test/test454.md`
- `docs/test/fixtures/nova-stepfn-recovery-454/main.tf`
- `docs/test/fixtures/nova-stepfn-recovery-454/worker.py`
- `docs/test/fixtures/nova-stepfn-recovery-454/probe.py`
- `docs/test/fixtures/nova-stepfn-recovery-454/.terraform.lock.hcl`

## Boundaries

Use only `davdeploy-nova-stepfn-recovery-454-nov23a2` in account
`654654474502`, region `us-east-1`. Keep state, plans, variables, and generated
files outside the repository. Run every Terraform apply/destroy through the
PID-based monitor; review each saved plan and never overlap mutations. Do not
touch the hosted control plane, production resources, customer credentials,
Nova execution gates, or retained lineage evidence. Preserve protected
untracked `--only-show-errors` and `.venv-pr399/`.

## Follow-up work

This covers one same-account Lambda task with a single Catch recovery route.
Other AWS SDK integrations, task-role policy shapes, distributed Map, Express
workflows, retries, redrive, and Nova-hosted execution remain unsupported or
unverified.
