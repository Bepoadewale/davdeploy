# test152 — Private GitHub App onboarding secret boundary

Date: 2026-10-24
Execution type: Local focused runtime and Terraform validation
Customer repository: Not applicable; no customer repository was read or changed by this validation
Commit: Pending PR commit
AWS account: No AWS mutation performed
AWS region: Not applicable

## Resources created

- None.

## Commands executed

- `.venv/bin/python -m pytest -q tests/test_integration_contracts.py`
- `.venv/bin/ruff check apps/api/src/davdeploy/integrations.py tests/test_integration_contracts.py`
- `.venv/bin/python scripts/check_actions_configuration.py`
- `terraform -chdir=infrastructure/terraform/serverless-control-plane init -backend=false -input=false`
- `terraform -chdir=infrastructure/terraform/serverless-control-plane validate`
- `terraform fmt -check -recursive infrastructure/terraform/serverless-control-plane`
- `git diff --check`

## Observed result

The focused integration suite passed with nine tests. The live GitHub App factory accepts a
dedicated Secrets Manager reference, reads only `private-key.pem` into process memory, and rejects
ambiguous file-path and secret-ARN configuration. Terraform validates the non-secret runtime
references and a conditionally scoped `secretsmanager:GetSecretValue` permission.

## Teardown

No AWS secret, Lambda configuration, customer repository, cloud connection, or workload resource
was created, updated, or deleted.

## Final boundary

This validation proves code and Terraform contracts only. Production enablement remains a reviewed
deployment followed by creation of a dedicated secret value outside Terraform state. GitHub writes
remain disabled.
