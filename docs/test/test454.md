# test454 — Step Functions failure and Catch recovery

Date: 2026-11-23

Execution type: Planned controlled disposable AWS workload validation.

Customer repository: None; direct same-account AWS service test.

Commit: Pending initial test commit.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

No AWS resources have been created yet. The pinned fixture plans one Lambda
execution role, one Lambda function, one
Step Functions execution role with a single exact-function invoke grant, one
Standard state machine, and one inline role policy. The exact prefix is
`davdeploy-nova-stepfn-recovery-454-nov23a2`. State, plan files, and the
packaged Lambda artifact stay outside the repository.

## Commands executed

No AWS command or mutation has been run. Planned sequence: open the draft PR
with its ticket and test record; verify account/region, exact-name absence,
and idle Terraform monitor; review the exact five-resource create plan; run
the failure/recovery and normal success probes; review and run the exact
five-resource destroy plan through the PID monitor; independently verify
resource absence and empty state.

## Acceptance criteria

- [ ] The controlled Lambda error is recorded as a failed task event.
- [ ] The Catch transition reaches the recovery task and the execution succeeds
      with the expected marker.
- [ ] The separate non-failing execution succeeds without taking the recovery
      branch.
- [ ] The probe prints no execution input/output or exception message.
- [ ] The exact stack is destroyed through the Terraform monitor and AWS
      absence is independently verified.
- [ ] Local checks and all seven required PR checks pass.
- [ ] Evidence is described as direct same-account service behavior, not Nova
      dispatch or hosted execution.

## Observed result

Pending the controlled disposable run. No AWS resource has been created for
this test.

## Teardown

Pending. The planned destroy is limited to the exact five-resource test root;
the hosted control plane, production resources, and other customer resources
are out of scope.

## Final boundary

This is direct Step Functions and Lambda behavior evidence for one Standard
state-machine shape. It does not establish Nova dispatch, Step Functions role
policy safety for other integrations, hosted execution, or general customer
certification.
