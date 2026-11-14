# Ticket 411: bounded RDS plan pricing

## Status

In progress. The implementation and focused regression cases are on draft PR #411. Hosted CI has not yet been reconciled. This PR does not deploy workloads or make the exact-plan apply runner operational.

## Objective

Price a narrow, explicitly supported RDS configuration from the initialized Terraform plan and current AWS regional price catalog, using usage assumptions stored in the integrity-checked customer revision. Bind those assumptions into the price evidence and approval check.

## Scope

- Support RDS for MySQL on non-burstable M/R instance classes, private Single-AZ deployment, GP3 storage, and declared monthly backup storage range.
- Price instance hours and allocated storage from AWS Price List. Report backup cost as a range from zero to the full declared usage because account-level backup allowance is shared.
- Reject unsupported or unknown material RDS cost/safety settings.
- Persist assumptions through the customer revision flow and expose them in the OpenAPI contract.
- Preserve prior pricing evidence parsing formats.

## Evidence required

- Hosted focused and full required CI pass on the final PR head.
- Review that approval eligibility checks the persisted assumptions and their digest.
- No AWS workload apply is part of this PR. The exact-plan apply path remains fail-closed and unwired as documented in PR #399.

## Limitations

This does not price multi-AZ, burstable classes, customer-managed keys, monitoring, log exports, restore operations, data transfer, or every RDS option. Backup storage charges depend on account-wide usage and free allowance. The estimate is not a bill forecast or a hard spend cap.
