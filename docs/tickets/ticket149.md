# ticket149: Governed customer repository delivery

PR: #149
Branch: feat/governed-customer-delivery

## Problem / goal

The customer foundation can be provisioned and destroyed through a reviewed Terraform artifact, but it cannot yet build a selected repository into the customer ECR repository or prove the immutable image that a later service plan may use.

## Current repo state

The bounded CodeBuild runner, customer connection roles, authenticated Terraform plan review, artifact-bound apply, result reconciliation, and absence verification are implemented. The App Runner service remains disabled until a reviewed image-bound service plan is introduced.

## Research / references used

- AWS ECR image push permission model.
- AWS CodeBuild isolated runner contract already present in this repository.
- GitHub public repository commit API, restricted to the repository and branch already selected in the approved plan.

## Work planned for the PR

- Add a governed image-build execution mode to the API, CLI, and MCP boundaries.
- Resolve and pin the selected public GitHub repository branch to one commit before execution.
- Clone only that pinned commit in the bounded runner, build the checked-in container definition, push it to the customer ECR repository, and persist image digest evidence.
- Add least-privilege ECR upload permissions to the customer execution role for its connection-scoped repository.
- Add focused tests and update the operations documentation.

## Acceptance criteria

- An administrator can request and explicitly queue an image build only for an approved plan with a verified customer cloud connection and a successful foundation apply.
- The runner accepts no customer shell command, pins the repository commit, verifies checkout, and records the pushed ECR digest in its immutable result artifact.
- The customer role can push only to its connection-scoped ECR repository.
- API, CLI, and MCP expose the same governed action.

## Acceptance status

Implemented locally. The live customer build remains gated on review, release, and a customer connection-stack update that grants the connection-scoped ECR upload actions.

## Tests / validation performed

- `.venv/bin/python -m pytest -q tests/test_cloud_execution.py tests/test_customer_plan_review.py` passed: 44 tests.
- `.venv/bin/ruff check apps/api/src/davdeploy tests/test_cloud_execution.py` passed.
- `bash -n scripts/customer-workload-app-runner-pilot.sh` pending final release validation.
- `make openapi-update` completed.
- `.venv/bin/python scripts/check_doc_conventions.py` passed.

## Evidence files produced

Live customer execution evidence will be appended to `docs/test/test130.md` after the separate service deployment and destroy cycle.

## Boundaries

This PR does not create an App Runner service. A later reviewed Terraform service plan must bind the returned immutable image digest and receive its own approval.

## Follow-up work

- Image-bound App Runner service plan and apply.
- Live observation, governed destroy, and final pilot evidence.
