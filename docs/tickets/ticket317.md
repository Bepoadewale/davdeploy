# ticket317 Bind Nova plans to trusted resource ownership

PR: https://github.com/Bepoadewale/davdeploy/pull/317 (draft)
Branch: `feat/nova-ownership-tags-317`

## Problem / goal

Bind generated Terraform plans to server-owned organization, workspace, project,
environment and plan identity. Require supported AWS resources to carry those
immutable ownership markers, and fail closed when plan evidence is missing,
unknown or mismatched. Preserve safe typed references within one proposal.

## Current repo state

This PR branch's code baseline is `c2c6279` (main at PR #315). Documentation
follow-ups #316 and #319 have since merged to main. At this baseline, the Nova
plan runner injects the trusted AWS account guard and region. The generated-plan
policy verifies the resource inventory, region and account guard, but does not
verify resource ownership tags. Typed references are already constrained to
declared resources, acyclic dependencies, and declared provider outputs with
matching type and sensitivity.

## Research / references used

- Terraform AWS provider default tags: https://registry.terraform.io/providers/hashicorp/aws/latest/docs#default_tags-configuration-block
- AWS resource tagging overview: https://docs.aws.amazon.com/tag-editor/latest/userguide/tagging.html
- Local implementation: `generated_terraform_plan.py`,
  `generated_plan_policy.py`, `generated_provider_validation.py`, and
  `generated_deployment_contract.py`.

## Work planned for the PR

- Pass a validated immutable server-owned ownership scope to the plan runner;
  Nova cannot choose or override it.
- Inject fixed ownership tags per resource only after the pinned provider schema
  confirms a writable `map(string)` `tags` field. No universal provider
  default-tag assumption is made.
- Check exact known tags in existing (`before`) and desired (`after`) values,
  including deletes and replacements, and in final planned values. Missing,
  unknown, or mismatched ownership is denied. Existing resources may carry an
  older well-formed source-revision hash only when organization/workspace,
  project, stable plan ID and environment still match; desired values must match
  the exact current approved revision.
- Reject resource types whose child AWS objects are not covered by a verified
  tag-propagation contract: `aws_instance`, `aws_launch_configuration`,
  `aws_launch_template`, `aws_autoscaling_group`, `aws_ec2_fleet`,
  `aws_spot_fleet_request`, `aws_eks_node_group`,
  `aws_batch_compute_environment`, `aws_cloudformation_stack`,
  `aws_ecs_service`, and `aws_lambda_function`.
- Prevent Nova from setting reserved `DavDeploy*` tag keys. Keep valid same-plan
  typed references working and preserve existing rejection of invalid references.
- Hash tenant, plan and revision IDs before writing them as tag values. The
  hashes are stable correlators, not anonymization. `DavDeployPlanId` is
  derived from the immutable infrastructure-plan ID and
  `DavDeploySourceRevision` from its approved revision ID. The saved Terraform
  plan hash remains bound separately to the artifact and is not part of its
  own configuration.
- Bind the ownership-scope digest and hashed plan ID into manifest version 2.
  Artifact persistence and approval recompute the expected scope from the
  authenticated organization, its workspace mapping, authorized project,
  immutable infrastructure-plan ID, approved revision and environment.

## Acceptance criteria

- [x] Trusted organization/workspace/project/environment/plan scope is validated
  and cannot be supplied or changed by Nova.
- [x] The runner injects deterministic ownership tags from trusted scope only.
- [x] Supported direct AWS resource blocks with absent, unknown, or mismatched
  ownership tags are denied; unsupported or child-expanding types stop before
  Terraform planning.
- [x] Existing-resource ownership is checked for updates, deletes and
  replacements, including resources absent from final `planned_values`; prior
  source-revision tags are accepted only with the same stable owner scope.
- [x] Unknown managed AWS action sets fail closed.
- [x] The immutable artifact manifest includes ownership and plan-ID digests;
  persistence and approval compare them with the current authorized scope.
- [x] Safe same-plan references continue to validate; invalid reference shapes
  remain rejected.
- [x] Focused tests, full local verification, and documentation checks pass.
- [x] No AWS resources are created or changed; no apply/destroy path is added.
- [ ] Required GitHub CI passes; PR is left ready for review, not merged.

## Acceptance status

Implementation and local validation are complete. Required GitHub CI is pending.
No AWS calls, real Terraform CLI, apply, or destroy ran; runner tests use a fake
Terraform executable.

## Tests / validation performed

- Focused suite: 126 passed across ownership, plan policy, plan runner,
  generated-plan artifacts, review/persistence, and typed deployment-contract
  tests.
- `make verify`: passed with 658 tests, Ruff, Actions configuration, OpenAPI
  snapshot and Compose configuration checks.
- Isolated `make local-proof` passed with 658 tests, smoke checks, API contract,
  customer-plan E2E, seeded demo records, trace check, Ruff, Actions config,
  OpenAPI and Compose checks.
- `python3 scripts/check_doc_conventions.py`: passed.
- `git diff --check`: passed.
- The isolated Compose containers were removed after stopping. No named volumes
  were created. Its network, images, temporary Python environment, and three
  override/build files remain because deleting non-container resources was not
  authorized.
- GitHub Actions CI: pending.

## Evidence files produced

- `docs/test/test317.md` records focused and full local verification results.

## Boundaries

This PR strengthens source-only plan generation and review. It does not connect
the runner to the hosted worker, authorize apply, or prove AWS tagging behavior
through a live resource lifecycle. AWS tags are mutable and spoofable metadata,
so they are ownership/recovery correlators, not an authorization boundary.
Remote state keys, tenant authorization and IAM isolation must remain the
authoritative ownership mechanism when hosted lifecycle is added. Because this
runner plans with `-backend=false`, this PR proves new-plan tag binding only; it
does not prove hosted update/destroy ownership. Verified tags cover direct
Terraform-managed AWS resource blocks, not every provider-created side effect. ECS task
propagation and Lambda's default log-group creation are not proven here and are
blocked along with the other types listed above. Persistence and approval derive
the expected scope from the authenticated organization, its current
workspace-as-organization mapping, the authorized project and plan, approved
revision and environment, then compare it to runner and manifest evidence.

## Follow-up work

Connect the trusted, plan-bound runner to the hosted worker without widening the
plan-only boundary. Build specific nested-tag ownership contracts for blocked
expansion types before enabling them in generated plans.
