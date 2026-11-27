# test551 — Nova v14 unknown-schema feedback and v15 follow-up

- Date: 2026-11-27
- Execution type: authenticated hosted Nova plan-only generation; no CodeBuild
  start or customer workload
- Repository: `Bepoadewale/davdeploy`
- Commit: control-plane code `edf8d2425e0a76015067a5c28b306493f7c2abb7`
- Pull request: [#551](https://github.com/Bepoadewale/davdeploy/pull/551)
- AWS account: `654654474502` (control-plane release only)
- AWS region: `us-east-1`
- Customer repository: `Bepoadewale/fitness-backend` (synthetic acceptance case)
- Submitted review revision: `a96bdf2d-6c44-4ba6-a813-53da9f2f4251`
- Content digest: `fb7384977baea8ff63b83d19be71ff5e0fcd54d45b19466a4f79a9722779cd4e`
- Generated plan run: `ec8a79ce-3c5c-4e2e-9b66-d16da1f0f6ab`

## Purpose

Record the first fresh hosted generation attempt using deployed v14 and identify
the next safe feedback improvement. The plan-only run cannot apply or destroy
resources.

## Commands executed

- PR #550 was merged as `edf8d2425e0a76015067a5c28b306493f7c2abb7` after all
  seven final-head checks passed in run `45996291773`.
- Protected plan `45997786571` and exact saved-plan apply `45998758698` deployed
  that commit. The plan had 0 adds, 8 in-place changes, 0 destroys, and no
  replacements. Database migrations completed. All six Lambda functions were
  Active/Successful and their `CodeSha256` matched the release ZIP
  (`s1FLtwSvmTutQ7x8d8itRKXkj46yK1lqxs+QlXG2OlQ=`). `/healthz` returned HTTP
  200.
- Authenticated CLI/API calls confirmed the workspace administrator, source
  plan, and submitted review-only revision. The architecture has nine modules
  marked unsupported for execution and fixture-only cost data; it is not an
  acceptance-ready plan input.
- A new customer review revision was created from the existing source plan,
  submitted with no approval decision, and queued with a fresh idempotency key.
- Only the generated-plan run's safe status and allow-listed diagnostics were
  read. No raw proposal, validator message, saved-plan bytes, or credential was
  retrieved.
- PR #551 implementation commit `5a11f3ce8f5b3528b11211348617e761130bc217`
  preserves canonical paths for unknown validator codes, truncates untrusted
  path suffixes, and selects fixed guidance by contract-field category.
- `/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python -m pytest
  tests/test_terraform_generation.py -q` — 39 passed.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python` —
  passed: 2,051 tests, Ruff, Actions configuration, OpenAPI snapshot, and Docker
  Compose configuration. One existing Starlette deprecation warning.
- `GITHUB_PR_NUMBER=551
  /Users/adewale/Projects/davdeploy/.venv-pr399/bin/python
  scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Initial full verification found two stale v14 prompt-version assertions; both
  were updated, and the final full verification above passed.

## Observed result

Run `ec8a79ce-3c5c-4e2e-9b66-d16da1f0f6ab` failed as
`NOVA_GENERATION_FAILED` / `proposal_invalid` before CodeBuild after 2 attempts
and 1 semantic repair. It used prompt
`terraform-nova2-contract-v14`; usage was 12,350 input tokens, 4,557 output
tokens, and 15,917 ms; estimated cost was unavailable. Safe diagnostics
reported:

- `string_pattern_mismatch` at `resources[*].resource_id`, with fixed guidance
  describing the lowercase 1–24 character ID rule and examples.
- Two `invalid` entries at `proposal`, each with fixed generic typed-contract
  guidance. Their raw validator codes and messages remain unknown.

No artifact was returned, no CodeBuild build started, and no Terraform plan or
customer workload was created. The review revision remains submitted and
unapproved.

## Resources created

- The control-plane release changed six Lambda packages and two in-place
  control-plane resources; it created and destroyed zero resources.
- The hosted Nova run created no AWS workload resources. Review and run metadata
  remain as audit evidence.
- The workspace discovery and plan-only customer role stacks remain in place
  for the isolated same-account test and are not part of this run's cleanup.

## Teardown

No customer AWS workload resources were created, so no workload teardown was
needed. The customer review/run metadata remains as audit evidence.

## Final boundary

PR #551 makes unknown typed-validator errors safer and more actionable by
preserving only allowlisted schema paths and fixed field-specific guidance. A
new v15 run is pending PR merge and protected deployment. Do not approve or
apply the synthetic workload. Even a successful generated plan will
not close the hosted-plan acceptance gate until it contains supported private
storage, database, and asynchronous processing with current regional pricing,
passes exact plan policy, and yields inspectable saved-plan evidence.
