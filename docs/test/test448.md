# test448 — isolated SQS idempotency and redrive recovery

Date: 2026-11-23

Execution type: Controlled disposable AWS workload validation.

Repository: `Bepoadewale/davdeploy`

Customer repository: None; direct same-account AWS service test.

Commit: test fixture revision pending before apply.

AWS account: `654654474502`.

AWS region: `us-east-1`.

## Resources created

None yet. Draft PR #448 was opened before any AWS mutation. The fixture uses
only the unique `davdeploy-nova-sqs-idem-448-nov23a1` resource prefix.

## Commands executed

- Terraform fixture is included at
  `docs/test/fixtures/nova-sqs-lambda-idempotency-448/`.
- Draft PR #448 was opened before any AWS mutation.
- `terraform fmt -check`, provider initialization, and `terraform validate`
  passed against an isolated copy of the fixture under `/tmp`.
- Python syntax parsing passed for both Lambda versions.
- Draft PR #448 and its matching ticket/test evidence were present before any
  AWS write.
- AWS caller is verified as account `654654474502`; the exact queue, table,
  Lambda, and role names are absent, and the monitor has 21 terminal runs with
  no active operation.
- Saved plan `create-final.tfplan` contains seven creates, zero changes,
  and zero destroys. The plan-bound inline role policy is fully known and
  grants only the exact source queue actions and `PutItem` on the exact test
  table. Source visibility is 30 seconds for the three-second Lambda; the
  retry threshold is five.
- Plan, apply, update, retry, redrive, and destroy evidence is pending.

## Observed result

Pending. No AWS resources have been created for this test.

## Teardown

None. No AWS resource was created.

## Final boundary

This direct same-account service test does not establish Nova dispatch,
cross-account isolation, hosted execution, or customer workload certification.
The hosted control plane, its Terraform state/locks, production queues, and
Nova execution gates are not part of this test.
