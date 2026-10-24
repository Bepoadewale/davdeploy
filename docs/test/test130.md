# Test 130: Live customer cloud pilot

## Classification

Real AWS customer-style execution. In progress.

## Safety boundary

The run uses the customer's scoped connection roles, a reviewed immutable plan digest, an approved revision, a checksum-bound saved Terraform plan, and the bounded CodeBuild runner. No credentials or external IDs are included in this record.

## Evidence to record before completion

- Customer repository and pinned commit.
- Account and region.
- Plan-only review result and artifact location class.
- Apply result, actual resources, outputs, and observations.
- Separately reviewed destroy-plan result.
- Destroy result and direct absence checks.
- Retained control-plane and customer-connection resources.
- Known limitations, including any fixture-only evidence.

