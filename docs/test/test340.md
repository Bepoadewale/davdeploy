# test340 — customer Nova plan-role permission profile

Date: 2026-11-11
Execution type: Local code and policy validation for PR #340. Its implementation
tests made no customer AWS API calls, changed no customer resources, and made no
Nova model calls. The later protected production control-plane release is
recorded separately in [test341](test341.md).
Customer repository: Not applicable; this PR changes the DavDeploy backend and customer-role setup template.
PR implementation head: `d46fe7fd60b6ba5bfa31cb319318d6417d2c6b1b`.
Commit: `d46fe7fd60b6ba5bfa31cb319318d6417d2c6b1b` — `feat: constrain Nova customer planning permissions`.
AWS account: None used for this test.
AWS region: None used for this test.

## Resources created

No customer resources. No customer role was assumed. The subsequent release
updated six DavDeploy control-plane Lambda packages; see [test341](test341.md).

## Commands executed

- Focused Nova plan-access, CodeBuild contract, customer connection template,
  generated-plan manifest, and related service tests — 34 passed before the
  final composed-profile regression was added; the final regression is covered
  by the full suite below.
- `.venv/bin/ruff check apps/api/src tests scripts` — passed.
- `make verify` — passed: 877 tests; Ruff, Actions configuration, OpenAPI
  snapshot, and Docker Compose configuration checks passed. One existing
  Starlette/httpx deprecation warning was reported.
- Isolated clean-room `make local-proof` at the exact implementation commit —
  passed: 877 tests; API readiness, worker and executor readiness, API/CORS
  contract, customer-plan end-to-end fixture, trace check, Actions config,
  Ruff, OpenAPI, and Compose configuration checks passed.
- `python3.12 scripts/check_doc_conventions.py` — passed for the final evidence
  text.
- `git diff --check` — passed.

## Observed result

The worker constructs a versioned, deterministic STS session policy before
assuming the customer plan role. Unsupported resource types and unsafe resource
identifiers fail before the role assumption. Policy resource scopes are derived
from the trusted account, region, and proposal; S3 also has an explicit
resource-account deny. The access-policy version and digest are included in
the saved-plan manifest and independently recomputed before the API accepts
the result.

The first composed profile contains API Gateway v2, Lambda/SQS async work,
private S3, DynamoDB, and scoped IAM role policy resources. The regression
test confirms it remains under the 2,048-character AWS STS inline policy
limit.

## Teardown

No customer AWS resources were created. After the clean-room run, only its dedicated
Docker Compose project `davdeploy_pr340_20261111` was stopped and removed,
including its containers, generated network, and generated PostgreSQL volume.
The clean-room worktree's generated `.venv` and `.local` were also removed by
`make clean-local`. No other worktrees, containers, volumes, customer
resources, or shared production resources were removed.

## Final boundary

Passing local policy tests do not attest an installed customer role policy,
AWS organization policies, customer account permissions, hosted worker
behavior, regional pricing, approval, apply, health, recovery, or teardown.
Hosted feature gates remain disabled. The production release did not change an
existing customer setup role; the revised customer template is not installed
until a customer applies it. The production release and its exact evidence are
recorded in [test341](test341.md).
