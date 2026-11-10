# test332 — PR #332 remote Terraform state worker evidence

Date: 2026-11-10
Execution type: Local unit tests and static Terraform validation; no customer workload
Customer repository: N/A; no customer repository or workload was used
Commit: runtime implementation `674654173b7e6b90ec72542afd4f52be9a781134`; merged-main revalidation `eb10860`; evidence update `4c39156`
AWS account: N/A; no AWS calls
AWS region: N/A; no AWS calls

This file records local implementation evidence only. The worker feature and
state API remain disabled by default. No CodeBuild bootstrap request, remote
Terraform state request, customer plan, or AWS mutation occurred.

## Resources created

No AWS or customer resources were created. GitHub Actions run `42860462692`
created the repository's Docker Compose test stack and volume on its fresh
runner; the job ran `make clean-local` before completing. Local unit tests use
mocked AWS responses and temporary test directories.

## Commands executed

```text
uv run ruff check apps/api/src/davdeploy tests/test_nova_terraform_state_client.py tests/test_generated_terraform_plan.py tests/test_nova_plan_codebuild.py tests/test_generated_plan_review.py tests/test_nova_plan_only_infra.py tests/test_nova_plan_runs.py
uv run pytest tests/test_nova_terraform_state_client.py tests/test_generated_terraform_plan.py tests/test_nova_plan_codebuild.py tests/test_generated_plan_artifacts.py tests/test_nova_plan_runs.py tests/test_generated_plan_review.py tests/test_nova_plan_only_infra.py tests/test_terraform_state.py -q
make terraform-validate
python scripts/check_doc_conventions.py
git diff --check
```

## Observed result

- Focused tests passed: 134 tests.
- Full `make verify` passed: 849 tests, Ruff, OpenAPI snapshot, Actions
  configuration, and Compose configuration checks.
- Terraform validation passed across all configured roots.
- Documentation convention validation and `git diff --check` passed.
- GitHub Actions runs `42856971505` (implementation baseline `0e0f24e`) and
  `42859321640` (tenant-scope guard `bbf7e42`) passed all seven required
  checks.
- GitHub Actions run `42860462692` passed all seven required checks for
  implementation commit `6746541`; its `local-e2e` job completed from a fresh
  runner and ran the repository's full bootstrap, demo, restart, recovery,
  trace, verification, and cleanup sequence.
- GitHub Actions run `42861740002` passed all seven required checks for the
  final evidence commit `4277831`.
- GitHub Actions run `42883208366` passed all seven required checks for the
  merged-main source and current evidence, including fresh-runner `local-e2e`
  and `cloud-contracts`.
- No clean-room cycle was run on the developer's Mac. The fresh GitHub runner
  completed the repository's clean-room lifecycle sequence, which provides
  the required isolated proof without deleting local project artifacts.
- The worker now recomputes the expected tenant state-scope digest from the
  immutable request and rejects a mismatched bootstrap response before
  Terraform runs. A focused negative test verifies this fail-closed path.
- SigV4 now uses the region parsed from the trusted API Gateway endpoint,
  separately from the customer's deployment region. A regression test signs
  to the `us-east-1` control-plane API while the target deployment region is
  `eu-west-1`; malformed non-API-Gateway hosts are rejected.
- An independent static security review of PR #332 found no blocking
  protocol/security findings; hosted AWS behavior remains unverified.
- No AWS or Bedrock calls were made.

## Teardown

The GitHub Actions runner executed `make clean-local`, removing its isolated
Compose containers, network, and volume. No cloud teardown was needed.
Temporary local test directories are handled by the test framework.

## Final boundary

This evidence does not establish a live SigV4 call, API Gateway identity
mapping, CodeBuild IAM role permission, remote-state HTTP round trip, persisted
state recovery, hosted customer plan, pricing, approval, apply, health,
recovery, or teardown. PR #332 remains draft.

## Revalidation on merged `main`

PR #331 merged into `main` at `c3067ea`; PR #332 now incorporates it through
merge commit `eb10860`. On that combined source, `make verify` passed 861
tests, `make terraform-validate` passed all configured roots, documentation
convention checks passed, and `git diff --check` passed. GitHub run
`42883208366` subsequently passed all seven required checks for the
merged-main source and evidence head. No AWS
calls, CodeBuild bootstrap, remote-state request, or infrastructure mutation
occurred.

PR #332 now targets `main` and no longer depends on an open PR #331. Hosted
remote-state behavior, customer planning, pricing, approval, apply, health,
recovery, and teardown remain unverified or unimplemented.
