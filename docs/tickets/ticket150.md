# ticket150: Complete scoped ECR image push permissions

PR: #150
Branch: fix/customer-ecr-build-read

## Problem / goal

The first real bounded customer image build pushed layers but AWS denied `ecr:BatchGetImage` during Docker's final image completion check.

## Current repo state

PR #149 introduced a connection-scoped ECR upload policy. The actual customer connection stack was updated and the first build confirmed that all upload actions work until the final read action.

## Research / references used

- The AWS CodeBuild output from the governed customer image-build run.
- Amazon ECR Docker push permission requirements.

## Work planned for the PR

- Add only `ecr:BatchGetImage` to the existing connection-scoped ECR repository policy.
- Add a static contract assertion for the exact ECR action set.

## Acceptance criteria

- The connection execution role can complete a Docker push only for its connection-scoped ECR repository.
- No broad ECR repository or account mutation permission is introduced.

## Acceptance status

Implemented locally. The live connection-stack update and governed retry remain gated on review and release.

## Tests / validation performed

- `.venv/bin/python -m pytest -q tests/test_customer_connection_template.py tests/test_cloud_execution.py` passed: 14 tests.
- `.venv/bin/python scripts/check_doc_conventions.py` passed.
- `git diff --check` passed.

## Evidence files produced

The retry and its result will be recorded in `docs/test/test130.md` after the full lifecycle.

## Boundaries

This PR changes one IAM action. It does not create an App Runner service or broaden the deployment role beyond the customer connection's repository.

## Follow-up work

- Retry the immutable image build.
- Create and review the image-bound App Runner service plan.
