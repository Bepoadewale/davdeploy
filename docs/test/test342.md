# test342 — Nova plan-role setup boundary wording

Date: 2026-11-11

Execution type: Local source and contract validation only. No customer AWS API
calls, role changes, AWS resource changes, or Nova model calls.

Customer repository: Not applicable; this PR changes the DavDeploy backend and
customer-role setup template.

Commit: `a7c7df1fbba39c333418afd86b24b793a36c00f1` — `fix: explain Nova plan role session limits`.

AWS account: None used for this test.

AWS region: None used for this test.

## Resources created

None. No AWS resources were created or changed.

## Commands executed

- Initial focused run failed because the new template-description regression
  selected the wrong YAML line by index. The assertion was changed to locate
  the `Description` field by its key.
- `.venv/bin/pytest -q tests/test_product.py::test_plan_only_quick_create_reuses_connection_external_id_and_stores_separate_role_arn tests/test_customer_aws_connection_contract.py` — 10 passed.
- `.venv/bin/ruff check apps/api/src/davdeploy/service.py apps/api/src/davdeploy/integrations.py tests/test_product.py tests/test_customer_aws_connection_contract.py` — passed.
- `python3.12 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Full `make verify` and `make local-proof` were not run: this PR changes only
  customer-facing wording, a verifier docstring, a CloudFormation description,
  and regression assertions; no executable permissions or lifecycle behavior
  changed. Required hosted CI remains pending.

## Observed result

The setup flow now accurately explains the template's bounded metadata reads,
the planner's proposal-scoped explicit-deny session, and the limits of
trust/account verification. No customer role was created, changed, or assumed.

## Teardown

None required; this is a local wording and test change.

## Final boundary

The setup wording distinguishes bounded role metadata reads from the
proposal-scoped STS session policy. Neither role trust verification nor this
text attests effective customer permissions or enables hosted planning.
