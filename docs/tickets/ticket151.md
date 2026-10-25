# ticket151: Use scoped ECR image evidence read

PR: #151
Branch: fix/ecr-image-evidence-read

## Problem / goal

The governed build pushed the image successfully but then called a broader ECR describe API to obtain its digest. The bounded customer role correctly denied that extra action.

## Current repo state

The connection-scoped policy from PR #150 permits `ecr:BatchGetImage`, which returns the immutable digest needed for evidence without an additional permission.

## Research / references used

- AWS CodeBuild output from the real customer image-build retry.
- Amazon ECR `BatchGetImage` response contract.

## Work planned for the PR

- Replace the unnecessary `DescribeImages` evidence query with `BatchGetImage`.
- Add a static runner contract assertion.

## Acceptance criteria

- The runner records an immutable ECR digest after push using only the customer connection's existing scoped policy.
- No new IAM permission is introduced.

## Acceptance status

Implemented locally. The live retry remains gated on review and the Terraform-controlled runner release.

## Tests / validation performed

- `bash -n scripts/customer-workload-app-runner-pilot.sh` passed.
- `.venv/bin/python -m pytest -q tests/test_customer_executor_script.py tests/test_cloud_execution.py` passed: 14 tests.
- `.venv/bin/python scripts/check_doc_conventions.py` passed.
- `git diff --check` passed.

## Evidence files produced

The final successful retry will be appended to `docs/test/test130.md` after the full lifecycle.

## Boundaries

This PR does not create a service or alter customer IAM permissions.

## Follow-up work

- Retry the governed immutable image build.
- Bind the resulting digest to a separately reviewed App Runner service plan.
