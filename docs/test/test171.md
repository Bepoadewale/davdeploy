# test171 — Resend runtime parameter activation

Date: 2026-10-26
Execution type: local automated validation
Customer repository: not used
Commit: `88f7af4` plus documentation completion
AWS account: `654654474502` (parameter creation only, not used by local validation)
AWS region: `us-east-1`

## Resources created

- One Standard SecureString parameter named `/davdeploy/runtime/resend-invitation-api-key`. Its secret value is not recorded here.

## Commands executed

```text
uv run ruff check apps/api/src tests
uv run pytest
terraform -chdir=infrastructure/terraform/serverless-control-plane fmt -check
terraform -chdir=infrastructure/terraform/serverless-control-plane validate
```

## Observed result

All static checks passed. The full backend suite passed: 292 tests.

## Teardown

The parameter is retained for the reviewed production activation. It contains the existing sending-only Resend key and costs nothing at the Standard tier.

## Final boundary

No production Lambda configuration, invitation, or Terraform apply is performed during local validation.
