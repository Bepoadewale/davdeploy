# Test evidence for PR 411

## Status

Pending GitHub Actions on the final PR head. No local test commands were run; this change is being validated through hosted CI.

## Automated coverage added

- RDS instance, GP3 storage, and backup cost-range calculation.
- Approval-context binding for persisted RDS backup assumptions.
- Missing backup assumptions and unsupported public, multi-AZ, burstable, customer-managed KMS, and unknown storage values fail closed before price lookup.
- Integrity-checked revision extraction for RDS assumptions.
- Existing generated-plan pricing tests continue to cover prior evidence formats, budgets, price catalog validation, and other priced resources.

## Cloud activity

No AWS workload was created, applied, or destroyed for this PR. Price lookups in the application use the AWS public Price List API. The apply runner remains unwired and disabled under PR #399.

## Hosted CI

- Final PR head: pending.
- Run ID and job outcomes: pending.
- Hosted focused/full verification: pending.
