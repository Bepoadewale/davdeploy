# test426 — validated Nova intent proposal identity

Date: 2026-11-17
Execution type: source tests
Customer repository: none
Commit: pending implementation
AWS account: none
AWS region: none

Status: ticket and evidence files are established before implementation. No
source changes, model calls, or AWS calls have occurred for this package.

## Resources created

None. No model, AWS, Terraform, or clean-room resources were created.

## Verification

- Planned focused tests cover accepted, repaired, out-of-scope, and fixture
  metadata behavior plus canonical digest stability.
- Full verification, docs conventions, diff checks, and final-head CI are
  pending implementation.

## Commands executed

- Ticket/evidence authoring only.

## Observed result

The current metadata contains model/prompt/input details but no validated
proposal version/digest. The source change will record a digest of the final
validated proposal only.

## Teardown

No teardown was required; no external or runtime resources were created.

## Final boundary

Tests will use gateway fixtures only. They will not call Bedrock, AWS, hosted
services, Terraform, or customer workloads.
