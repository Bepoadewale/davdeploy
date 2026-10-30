# test211

PR: [#211](https://github.com/Bepoadewale/davdeploy/pull/211)

Date: 2026-10-30

Execution type: local static configuration and unit-test validation

Customer repository: none

Commit: local PR branch validation

AWS account: none contacted by this evidence

AWS region: none

## Resources created

None.

## Commands executed

- `.venv/bin/python -m pytest -q tests/test_serverless_runtime.py`
- `make lint`
- `make test`
- `make terraform-validate`

## Observed result

Focused guard tests passed; full test suite passed with 310 tests. Terraform
validation passed for the control-plane roots.

## Teardown

No resources were created.

## Final boundary

Local static configuration and unit-test validation only. No customer workload
or deployed AWS resource was changed by these tests.

## Known limitations

The public Worker rollout requires a Cloudflare token with Workers Scripts edit
permission. The direct-origin guard is deliberately inactive until the reviewed
Terraform rollout points Lambda at the SSM parameter.
