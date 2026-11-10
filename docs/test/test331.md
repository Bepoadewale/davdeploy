# test331 — PR #331 local implementation evidence

Date: 2026-11-10
Execution type: Local unit, API, migration, infrastructure-contract, and Terraform validation; no customer workload
Customer repository: N/A; no customer repository or workload was used
Commit: Draft work in progress; source commit will be recorded before review-ready
AWS account: N/A; no AWS calls
AWS region: N/A; no AWS calls

This evidence is local only. No AWS state bucket was provisioned, no remote
CodeBuild worker called the state API, and no customer state or infrastructure
was created, changed, or deleted. The Nova runner and state API feature remain
disabled.

## Source and status

- Repository: `Bepoadewale/davdeploy`
- Branch: `feat/tenant-isolated-terraform-state-331`
- PR: [#331](https://github.com/Bepoadewale/davdeploy/pull/331), draft
- State: local code and test evidence; not deployed or customer verified
- AWS execution: none

## Validation performed

- `uv run pytest tests/test_terraform_state.py tests/test_nova_plan_only_infra.py tests/test_serverless_runtime.py -q` — 56 passed after exact build-attempt binding and tenant-environment checks.
- `make verify` — passed: 834 tests, Ruff, Actions configuration, OpenAPI snapshot, and Docker Compose configuration.
- `make terraform-validate` — passed for all roots selected by `scripts/terraform-validate.sh`.
- `python scripts/check_doc_conventions.py` — passed for the updated ticket and evidence.
- `git diff --check` — passed.

## Resources created

No AWS resources, customer state, workloads, containers, or persistent local
services were created. Terraform validation used local provider/module caches.

## Observed result

The local validation recorded below passed. The API feature and CodeBuild
runner remain disabled, and no customer or AWS execution occurred.

## What these checks cover

- State scope digests require explicit organization, project, environment,
  AWS account, and region; a missing environment is denied.
- State and lock JSON shape/size checks, credential digest/expiry handling,
  and exact assumed-role matching.
- The bootstrap endpoint defaults to disabled and rejects an untrusted role
  before attempting a CodeBuild lookup.
- Additive migration from schema version 32 and idempotent state-table setup.
- Fake-S3 tests for KMS-encrypted, versioned state writes, exact-version reads,
  lock ownership, serial checks, and recovery after a lost upload response.
- Static infrastructure checks for an exact AWS-IAM bootstrap route, trusted
  API Gateway identity mapping, an exact CodeBuild role invoke grant, and
  Basic-auth state routes behind the edge-origin guard.
- Optional state storage defaults off. If explicitly provisioned, it uses a
  private versioned S3 bucket with KMS encryption and TLS-only access; the API
  role receives access only to its state prefix. The state API feature itself
  remains disabled, and the runner does not use this storage yet.

## Not established

- No real S3 bucket, KMS permissions, API Gateway deployment, CodeBuild
  bootstrap request, or HTTP backend round trip has been verified.
- The runner has not been changed to request the temporary credential or use
  the HTTP backend. It still runs with `-backend=false`.
- The API feature flag is hard-disabled in Terraform and its state API URL is
  empty. The separately controlled state bucket defaults off; no bucket or KMS
  key was provisioned during this work.
- Cross-tenant route behavior, successful active-build credential issuance,
  concurrent database races, worker restart recovery, and Terraform CLI retry
  behavior still need dedicated tests. Stale-lock release is unit-tested with
  exact terminal-build evidence, but its AWS CodeBuild lookup is not.
- The clean-room lifecycle gate for this database/authentication/Terraform
  change has not been run. PR #331 remains draft and must not be treated as
  deployment-ready.

## Commands executed

```text
uv run pytest tests/test_terraform_state.py tests/test_nova_plan_only_infra.py tests/test_serverless_runtime.py -q
make verify
make terraform-validate
git diff --check
python scripts/check_doc_conventions.py
```

## Teardown

No cloud teardown was needed. No persistent local test services were started.

## Final boundary

This is partial local evidence for an open draft. It does not prove a deployed
state API, remote Terraform planning, customer approval, apply, health,
recovery, or teardown.
