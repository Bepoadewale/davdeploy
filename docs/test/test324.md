# test324 - isolated Nova plan-only CodeBuild boundary

Date: 2026-11-04
Execution type: Local static and automated validation; no customer workload
Customer repository: N/A; no customer repository was used
Commit: `8890acf11d6025b188f82b6697d0dbf777880b75` (implementation under test)
AWS account: N/A; no AWS calls
AWS region: N/A; no AWS calls

## Commands executed

```text
PYTHONPATH=apps/api/src /private/tmp/davdeploy-pr322-venv/bin/pytest -q tests/test_nova_plan_only_infra.py
make verify PY=/private/tmp/davdeploy-pr322-venv/bin/python PYTHON=/private/tmp/davdeploy-pr322-venv/bin/python
terraform fmt -check -recursive infrastructure/terraform
make terraform-validate kubernetes-render
/private/tmp/davdeploy-pr322-venv/bin/python scripts/check_doc_conventions.py
git diff --check
gh pr checks 324 --watch --interval 120
```

## Resources created

No AWS resources. Terraform validation uses local initialization with `-backend=false`; unit tests use local fixtures.

## Observed result

Focused infrastructure contract tests passed: 5 tests. `make verify` passed: 688 tests,
Ruff, GitHub Actions variable/secret classification, the OpenAPI snapshot check, and Docker
Compose configuration validation. Recursive Terraform formatting passed; `make
terraform-validate` initialized and validated all configured Terraform roots; Kubernetes
rendering passed. Documentation conventions and `git diff --check` passed. All seven required
GitHub checks passed in [run 41917758576](https://github.com/Bepoadewale/davdeploy/actions/runs/41917758576)
on branch commit `a5e8214` (the evidence-only commit after implementation commit
`8890acf11d6025b188f82b6697d0dbf777880b75`).

## Teardown

Not applicable; no cloud workload or persistent local service stack is in scope.

## Final boundary

No AWS API calls, plan, apply, destroy, or customer workload execution is in scope. The new buildspec must fail closed until the fixed runner interface is wired.

## Known limitations

The future trusted runner must upload request objects with S3 Bucket Keys disabled so KMS
receives the object ARN and the prefix-scoped KMS condition can authorize the object. This PR
does not provide that runner. IAM conditions were checked statically; no AWS IAM simulation or
AWS API call was performed.
