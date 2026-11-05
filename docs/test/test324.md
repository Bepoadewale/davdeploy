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
`8890acf11d6025b188f82b6697d0dbf777880b75`). The final evidence update also passed all seven
checks in [run 41918524417](https://github.com/Bepoadewale/davdeploy/actions/runs/41918524417).

## Teardown

Not applicable; no cloud workload or persistent local service stack is in scope.

## Final boundary

No AWS API calls, plan, apply, destroy, or customer workload execution is in scope. The new buildspec must fail closed until the fixed runner interface is wired.

## Known limitations

The future trusted runner must upload request objects with S3 Bucket Keys disabled so KMS
receives the object ARN and the prefix-scoped KMS condition can authorize the object. This PR
does not provide that runner. IAM conditions were checked statically; no AWS IAM simulation or
AWS API call was performed.

## Review findings follow-up — commit `bddaeb92f37d306498292f5c2cba974a470aaecc`

The operations apply role can now update, tag, untag, and delete the exact
`davdeploy-nova-plan-only` project. Its log-group lifecycle permissions are limited to
`/aws/codebuild/davdeploy-nova-plan-only`. The existing `RuntimeRoles` statement already
covers the exact role name through `role/davdeploy-*`, including create/delete, policy
attachment, and CodeBuild `iam:PassRole`; no duplicate IAM grant was added. AWS's current
[CodeBuild authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_codebuild.html)
does not define a resource type for `CreateProject`, so the action remains on `Resource="*"`
with required `Product=davdeploy` and `ManagedBy=Terraform` request-tag conditions. The
CodeBuild and CloudWatch Logs resource ARNs are otherwise project/group specific.

Focused operations-bootstrap and serverless-runtime tests passed: 40 tests (one existing
Starlette/httpx deprecation warning). `make verify` passed 689 tests, Ruff, Actions
configuration, OpenAPI snapshot, and Compose validation. Recursive Terraform formatting,
`make terraform-validate kubernetes-render`, and documentation conventions passed. All seven
required GitHub checks passed in [run 41924494545](https://github.com/Bepoadewale/davdeploy/actions/runs/41924494545).

### Fresh clean-room validation

The cycle ran at commit `bddaeb9` in detached worktree
`/private/tmp/davdeploy-cleanroom-pr324-20261104` with Compose project
`davdeploy-pr324-cleanroom`. A fresh external virtual environment lives at
`/private/tmp/davdeploy-pr324-venv`. A temporary Compose override replaced PostgreSQL's
named volume with `tmpfs`; `docker compose config` confirmed an empty named-volume map. The
initial clean check found no worktree `.venv` or `.local`, no project containers, and no
project volumes.

The following commands passed in the isolated worktree, in order:

```text
COMPOSE_PROJECT_NAME=davdeploy-pr324-cleanroom COMPOSE_FILE=docker-compose.yml:docker-compose.cleanroom.yml make clean-local
COMPOSE_PROJECT_NAME=davdeploy-pr324-cleanroom COMPOSE_FILE=docker-compose.yml:docker-compose.cleanroom.yml make VENV=/private/tmp/davdeploy-pr324-venv bootstrap-local
COMPOSE_PROJECT_NAME=davdeploy-pr324-cleanroom COMPOSE_FILE=docker-compose.yml:docker-compose.cleanroom.yml make VENV=/private/tmp/davdeploy-pr324-venv smoke api-contract
/private/tmp/davdeploy-pr324-venv/bin/python scripts/customer_plan_e2e.py --state-file /private/tmp/davdeploy-pr324-customer-plan-e2e.json
COMPOSE_PROJECT_NAME=davdeploy-pr324-cleanroom COMPOSE_FILE=docker-compose.yml:docker-compose.cleanroom.yml make VENV=/private/tmp/davdeploy-pr324-venv seed-demo-data demo-simple demo-complex demo-day2 demo-degraded demo-failure demo-readiness-failure trace-check verify
```

Smoke/readiness, API contract, customer-plan E2E, seed, all demos, trace check, all Terraform
roots, and Kubernetes rendering passed. The clean-room `make verify` passed 689 tests with
one existing deprecation warning, Ruff, Actions configuration, OpenAPI, and Compose checks.
No AWS calls or Terraform apply occurred.

The following repository checks also passed from the PR branch worktree:

```text
/private/tmp/davdeploy-pr322-venv/bin/pytest -q tests/test_terraform_operations_bootstrap.py tests/test_serverless_runtime.py
make VENV=/private/tmp/davdeploy-pr322-venv verify
terraform fmt -check -recursive infrastructure/terraform
make terraform-validate kubernetes-render
python3.12 scripts/check_doc_conventions.py
git diff --check
```

The run generated `.local`; it and the worktree, external virtual environment, and test state
file were retained. After verification, the isolated Compose containers and network were
removed with:

```text
docker compose -p davdeploy-pr324-cleanroom -f docker-compose.yml -f docker-compose.cleanroom.yml down --remove-orphans
```

A follow-up `docker ps` and `docker volume ls`, both filtered to
`davdeploy-pr324-cleanroom`, returned no matching containers or volumes. Compose created no
named volume; PostgreSQL used `tmpfs`. No AWS resource or generated local file was deleted.

## IAM auto-retry follow-up

The `StartBuild` policy now explicitly denies the supported `codebuild:autoRetryLimit`
condition key. CodeBuild does not expose IAM condition keys for every optional StartBuild
field, including timeout and debug-session options; the dependent PR #325 adds a static
source contract test proving its fixed dispatcher sends only the project name, idempotency
token, and trusted run-ID environment override.

```text
.venv/bin/python -m pytest tests/test_nova_plan_only_infra.py -q
terraform fmt -check -diff infrastructure/terraform/serverless-control-plane/main.tf
terraform validate
git diff --check
```

The focused contract tests passed (5 tests), Terraform formatting and validation passed, and
`git diff --check` passed. Terraform validation used the existing initialized local providers;
no AWS calls or apply were performed. The protected untracked `--only-show-errors` file was
preserved.
