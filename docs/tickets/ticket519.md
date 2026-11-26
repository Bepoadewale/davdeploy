# ticket519 — Nova ECS Express renderer lifecycle

PR: #519
Branch: `feat/ecs-express-renderer-519`

## Problem / goal

Connect the existing bounded ECS Express customer-sandbox profile to Nova's
fixed lifecycle renderer contract. The profile has direct same-account
create, readiness, update, rollback, and cleanup evidence, but no Nova renderer
binding or product runner. This package must not claim Nova-originated
execution.

## Current repo state

- Backend `main` is `a456b84aa17600daf2b2c0bfe51d3bddb67e59ba`, after merged
  PRs #520 and #522. This PR branch remains at
  `403ea5a331e7e29b611d4a2f04b7aeb9a7d111ed`; its final-head run
  `45884741945` passed all seven checks.
- `infrastructure/terraform/customer-workload-ecs-express-pilot` is an
  isolated single-service ECS Express root. This PR adds an optional S3
  backend, project/region-scoped names and tags, and an explicit customer
  provider profile. The backend path is configured with customer-owned state
  resources; direct tests continue to initialize with `-backend=false`.
- `docs/test/test437.md` records direct same-account AWS create, health,
  in-place update, failed-health rollback, recovery, and cleanup. It does not
  prove Nova dispatch or cross-account isolation.
- `module_renderers.py` now has a disabled, pilot-specific
  `aws-ecs-express-pilot` renderer bound to the ECS Express root. It does not
  reuse the broad `aws-container-service` module contract. The broader
  `aws-ecs-fargate` planning profile does not resolve to this single-container
  pilot. Customer execution remains unavailable pending effective IAM review
  and isolated runner certification.
- Merged PR #520 added the exact-shape actual-plan policy and evaluated the
  provider-generated pilot plan with three human-review findings and no
  policy denials. Merged PR #522 added the regional pricing model, including
  both target-tracking alarms. Its fresh 12-line price evaluation used
  synthetic persisted context and no customer budget, so it is not
  approval-bound customer pricing evidence; draft PR #524 corrects the
  existing ticket wording.
- Current cloud-execution gates and hosted control-plane configuration must
  remain untouched by this PR.

## Research / references used

- AWS ECS Express Mode overview:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html
- AWS ECS Express service creation:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-create-full.html
- HashiCorp AWS provider resource contract:
  https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecs_express_gateway_service
- HashiCorp S3 backend (SSE-KMS, versioning, and S3-native lockfile contract):
  https://developer.hashicorp.com/terraform/language/backend/s3
- AWS ECS infrastructure IAM role and `iam:PassRole` guidance:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/infrastructure_IAM_role.html
- AWS-managed ECS Express infrastructure policy:
  https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AmazonECSInfrastructureRoleforExpressGatewayServices.html
- Existing direct AWS evidence: `docs/test/test437.md`
- Existing renderer contract: `apps/api/src/davdeploy/module_renderers.py`

## Work planned for the PR

1. Add a fixed ECS Express renderer root and command map for the narrow pilot
   profile while leaving customer execution disabled.
2. Scope remote state in a customer-owned bucket, and generated resource names,
   to connection, project, and region. Use S3-native locking and require
   versioning, public-access blocks, bucket-owner enforcement, and SSE-KMS;
   preserve `-backend=false` local validation.
3. Implement bounded plan, saved-plan apply, observe/readiness, artifact build,
   destroy-plan, saved-plan destroy, and independent cleanup verification.
4. Pin images by digest and use a separate customer image-publisher role for
   ECR writes; validate account, region, project/run identifiers, artifact
   paths, and plan digest.
5. Bind outputs and health evidence to the run and bound HTTP response size.
6. Keep the renderer disabled until IAM policy, cost coverage, focused tests,
   clean-room validation, and an authorized isolated cloud cycle are reviewed.
7. Record any future cloud run in `docs/test/test519.md`; no AWS workload was
   created by this PR.

## Acceptance criteria

- [x] Renderer catalogue has one fixed ECS Express root and exact command map,
  with customer execution disabled.
- [x] Unknown operations and malformed tenant/run/artifact bindings fail closed.
- [x] Saved-plan apply and destroy verify the approved SHA-256 digest before
  Terraform execution.
- [x] Service readiness uses a bounded HTTP request to the Terraform-recorded
  HTTPS endpoint and checks the expected health response.
- [x] Cleanup verification checks service, VPC, ECR, IAM roles, and log group;
  failed AWS reads do not produce an absence claim.
- [x] Customer execution remains disabled until external prerequisites pass.
- [x] Focused tests, documentation conventions, and Terraform validation pass.
- [x] Customer remote-state bucket preflight requires versioning, complete
  public-access blocking, bucket-owner enforcement, and the configured KMS key.
- [x] The source actual-plan policy and regional pricing model are merged and
  evaluated against a provider-generated pilot plan.
- [ ] Effective customer execution-role permissions are independently
  reviewed, and approval-bound pricing is tied to an integrity-checked customer
  revision and budget.
- [ ] The renderer passes a clean-room local lifecycle cycle and an authorized
  isolated cloud cycle using project-scoped remote state.
- [x] Final-head GitHub Actions run 45884741945 passed all seven checks; rerun
  required after this ticket update is pushed.
- [x] No hosted control-plane, runtime, Terraform state, or lock resource was
  accessed or mutated by this PR.

## Acceptance status

The project-scoped Terraform contract, disabled renderer binding, and bounded
runner source are implemented. The provider-generated plan policy and price
model are merged and exercised. Effective execution-role permissions,
customer-context approval evidence, clean-room validation, the isolated
remote-state runner cycle, and this PR's refreshed final-head CI remain open;
the renderer is not enabled for customer execution.

## Tests / validation performed

- `bash -n scripts/customer-workload-ecs-express-pilot.sh`: passed.
- `.venv/bin/python -m pytest tests/test_adapter_catalogue.py tests/test_module_renderers.py tests/test_ecs_express_renderer_contract.py tests/test_renderer_dispatcher.py -q`: 25 passed.
- `terraform -chdir=infrastructure/terraform/customer-workload-ecs-express-pilot init -backend=false -input=false`: passed.
- `terraform -chdir=infrastructure/terraform/customer-workload-ecs-express-pilot validate`: passed.
- `GITHUB_PR_NUMBER=519 .venv/bin/python scripts/check_doc_conventions.py`: passed.
- `git diff --check`: passed.
- Terraform monitor snapshot: 75 terminal records, zero active operations.
- Existing AWS evidence remains `docs/test/test437.md`; it is not relabeled as
  Nova-run evidence. No AWS or hosted-control-plane resource was changed.

## Boundaries

- Do not mutate the hosted DavDeploy control plane, runtime, state, or locks.
- Do not enable unrestricted execution or bypass exact saved-plan approval.
- Do not claim direct ECS evidence as Nova dispatch or cross-account proof.
- Preserve unrelated local files and directories.
- Any paid workload validation needs a fresh exact manifest, current cost and
  quota preflight, explicit resource/runtime bounds, monitored Terraform
  operations, and independent cleanup verification.

## Evidence files produced

- No new customer-workload evidence file exists because this PR performed no
  cloud workload test.
- Existing direct evidence remains `docs/test/test437.md`.

## Follow-up work

After implementation, review whether ECS Express's generated supporting
resources and public endpoint behavior fit the approved profile. Keep the
renderer gated until the complete evidence package is reviewed.
