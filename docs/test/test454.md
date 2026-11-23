# test454 — Step Functions failure and Catch recovery

Date: 2026-11-23

Execution type: Controlled disposable AWS workload validation in progress.

Customer repository: None; direct same-account AWS service test.

Commit: `bc44e0c` (fixture and initial evidence record).

PR: [#454](https://github.com/Bepoadewale/davdeploy/pull/454), draft. Initial
head `eddbcd6ac3d47846c7e44a0a5ea3bcd9f71f3686` passed all seven checks in run
[45222597413](https://github.com/Bepoadewale/davdeploy/actions/runs/45222597413).

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

- Draft PR #454 and its ticket/test evidence were opened before AWS writes.
- Caller identity was verified as account `654654474502` in `us-east-1`; exact
  Step Functions, Lambda, and role names were absent. The monitor had 31
  records and no active operations.
- Terraform init and validation passed with the pinned AWS `5.100.0` and
  Archive `2.7.1` providers. The saved create plan contains exactly five
  creates, zero updates, and zero deletes. AWS's state-machine-definition
  validator returned `OK` with zero diagnostics.
- Initial monitored create `nova-stepfn-recovery-454-create-nov23a2` failed
  before making AWS calls because the Terraform subprocess did not inherit the
  AWS profile. Exact-name reads confirmed no resources were created. A fresh
  five-create plan was saved and the monitored retry
  `nova-stepfn-recovery-454-create-retry-nov23a2` started at
  `2026-11-23T17:07:41Z` under the verified profile. Its result and subsequent
  probes/teardown are pending.

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

The controlled run is in progress. The first create attempt stopped before
AWS access due to a missing profile environment variable; exact-name checks
confirmed that no resources were created by that attempt.

## Teardown

Pending. The planned destroy is limited to the exact five-resource test root;
the hosted control plane, production resources, and other customer resources
are out of scope.

## Final boundary

This is direct Step Functions and Lambda behavior evidence for one Standard
state-machine shape. It does not establish Nova dispatch, Step Functions role
policy safety for other integrations, hosted execution, or general customer
certification.
