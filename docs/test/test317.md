# test317 Trusted plan ownership evidence

Date: 2026-11-04

Execution type: Local focused/unit tests and clean-room Compose fixture run.
Terraform runner tests use a fake Terraform executable. No AWS or real
Terraform operations were run.

Customer repository: None. This PR contains no customer workload test.

Test ID: `pr317-nova-trusted-ownership`.

Repository: `Bepoadewale/davdeploy`, branch `feat/nova-ownership-tags-317`.

Commit: See PR #317 history.

AWS account: None. No AWS request or mutation was made.

AWS region: None.

## Resources created

No customer or AWS resources. The isolated local Compose fixture created nine
project containers and one network; Postgres used tmpfs, and Compose reported
no named volumes.

## Commands executed

- `uv run --extra dev --python 3.12 pytest -q tests/test_generated_plan_ownership.py tests/test_generated_plan_policy.py tests/test_generated_terraform_plan.py tests/test_generated_deployment_contract.py tests/test_generated_plan_artifacts.py tests/test_generated_plan_review.py` — 126 passed, 1 existing Starlette deprecation warning.
- `make VENV=/tmp/davdeploy-pr317-venv PY=/tmp/davdeploy-pr317-venv/bin/python verify` — passed: Actions config, Ruff, all 658 tests, OpenAPI snapshot and Compose config.
- `COMPOSE_PROJECT_NAME=davdeploy-pr317-cleanroom COMPOSE_FILE=docker-compose.yml:/tmp/davdeploy-pr317-compose-override.yml:/tmp/davdeploy-pr317-build-override.yml make VENV=/tmp/davdeploy-pr317-venv PY=/tmp/davdeploy-pr317-venv/bin/python local-proof` — passed: smoke, API contract, customer-plan E2E, demo seeding, trace check, config check, Ruff, all 658 tests, OpenAPI snapshot and Compose config. A temporary build overlay copied this PR's source into images with already-installed dependencies; the stack used a fresh tmpfs database.
- `python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- GitHub Actions CI — pending.

## Observed result

Trusted tags are injected only after the pinned provider schema confirms a
writable `map(string)` resource `tags` attribute. Tags include hashed
organization/workspace/project/plan/revision identities from server-trusted
scope; runner persistence and approval independently recompute and compare that
scope. Existing resources may retain a prior well-formed source-revision tag
for updates, deletes and replacements only while their stable owner tags still
match; desired values must carry the exact currently approved revision. Unknown
managed AWS action sets fail closed. The policy checks existing and desired
resource values, including deletes and replacements, and checks final planned
values. Untaggable resources stop before Terraform planning. Known
child-resource expansion paths
(`aws_instance`, launch configuration/template, Auto Scaling, EC2/Spot Fleet,
EKS node group, Batch compute environment, CloudFormation stack, ECS service and
Lambda function) also stop before planning because parent tags do not prove
child ownership. Safe typed references still pass their contract and
provider-schema checks.

## Teardown

No AWS or customer resources were created. After the final verification, all nine
`davdeploy-pr317-cleanroom` Compose containers were stopped and removed. No
named Docker volumes were created. The isolated Compose network, three
PR-specific images, temporary Python environment, and three temporary
Compose override/build files remain on the machine because deleting
non-container resources was not authorized.

## Final boundary

This is source-level plan validation only. Unit tests use a fake Terraform
executable. No customer resources were created. This does not prove that every
AWS service accepts tags, that tags cover every service-created AWS child
object, or connect the runner to the hosted worker. The explicit expansion
resource list remains unsupported until nested or propagated ownership tags
are validated or another exact ownership mechanism exists. AWS tags are mutable
and spoofable metadata, so they are ownership/recovery correlators, not an
authorization boundary. Remote state keys, tenant authorization and IAM
isolation must be the authoritative ownership mechanism when hosted lifecycle
is added. Because this runner uses `-backend=false`, the evidence proves new-plan
tag binding only, not hosted update/destroy ownership. The isolated local
network, images, temporary environment and override/build files are retained; no
existing local volumes or repository environments were deleted.
