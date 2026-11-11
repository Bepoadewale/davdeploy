# test342 — Nova plan-role setup boundary wording

Date: 2026-11-11

Execution type: Local source and contract validation only. No customer AWS API
calls, role changes, AWS resource changes, or Nova model calls.

Customer repository: Not applicable; this PR changes the DavDeploy backend and
customer-role setup template.

Commit: Pending final implementation commit.

AWS account: None used for this test.

AWS region: None used for this test.

## Resources created

None. No AWS resources were created or changed.

## Commands executed

Pending focused tests, full verification, documentation checks, and final-head
CI.

## Observed result

Pending final local and hosted validation.

## Teardown

None required; this is a local wording and test change.

## Final boundary

The setup wording must distinguish bounded role metadata reads from the
proposal-scoped STS session policy. Neither the role trust check nor this text
attests effective customer permissions or enables hosted planning.
