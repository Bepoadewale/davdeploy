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

- Backend `main` is `dbbf7c135b7be97c832927d5c1758bc1faab805d`, merged PR #518;
  its PR and merged-main CI passed all seven checks.
- `infrastructure/terraform/customer-workload-ecs-express-pilot` is an
  isolated single-service ECS Express root. It currently uses local state and
  does not integrate with the product's project-scoped saved-plan runner.
- `docs/test/test437.md` records direct same-account AWS create, health,
  in-place update, failed-health rollback, recovery, and cleanup. It does not
  prove Nova dispatch or cross-account isolation.
- `module_renderers.py` currently has no `aws-container-service` renderer and
  `renderer_for_profile` does not map `aws-ecs-fargate` to a renderer.
- Current cloud-execution gates and hosted control-plane configuration must
  remain untouched by this PR.

## Research / references used

- AWS ECS Express Mode overview:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html
- AWS ECS Express service creation:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-create-full.html
- HashiCorp AWS provider resource contract:
  https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/ecs_express_gateway_service
- Existing direct AWS evidence: `docs/test/test437.md`
- Existing renderer contract: `apps/api/src/davdeploy/module_renderers.py`

## Work planned for the PR

1. Add a fixed ECS Express renderer root and command mapping without enabling
   customer execution by default.
2. Define a remote-state configuration path scoped to customer connection,
   project, and region while preserving the root's isolated local-test path.
3. Implement bounded plan, saved-plan apply, observe/readiness,
   destroy-plan, saved-plan destroy, and cleanup-verification operations.
4. Pin images by digest; validate account, region, tenant/run identifiers,
   artifact paths, plan digest, and returned resource identifiers.
5. Bind outputs and health evidence to the immutable run and avoid emitting
   credentials, environment values, or unbounded AWS responses.
6. Keep the renderer disabled until the new contract has passed focused tests,
   clean-room CI, cost/policy review, and an authorized isolated cloud cycle.
7. Record any cloud run in `docs/test/test519.md`; no cloud run is authorized by
   this source-only package itself.

## Acceptance criteria

- [ ] Renderer catalogue has one fixed ECS Express root and exact command map.
- [ ] Unknown operations and malformed tenant/run/artifact bindings fail closed.
- [ ] Saved-plan apply and destroy verify the approved SHA-256 digest before
  Terraform execution.
- [ ] Service readiness is verified through an independent bounded HTTP check
  against the planned service endpoint and expected health response.
- [ ] Cleanup verification checks service and all owned resources and does not
  claim absence when an AWS read fails.
- [ ] Customer execution remains disabled until all prerequisites are met.
- [ ] Focused regression tests, documentation conventions, Terraform
  validation, and all required PR CI checks pass.
- [ ] No hosted control-plane, runtime, Terraform state, or lock resource is
  accessed or mutated.

## Acceptance status

Bootstrap design is recorded. Implementation and validation remain pending.

## Tests / validation performed

- Read-only `git status` confirmed a clean `main` before branching.
- Terraform monitor snapshot: 75 terminal records, zero active operations.
- Existing AWS evidence is `docs/test/test437.md`; it will not be relabeled as
  Nova-run evidence.
- No new AWS resources or hosted control-plane changes are part of the current
  bootstrap commit.

## Boundaries

- Do not mutate the hosted DavDeploy control plane, runtime, state, or locks.
- Do not enable unrestricted execution or bypass exact saved-plan approval.
- Do not claim direct ECS evidence as Nova dispatch or cross-account proof.
- Preserve unrelated local files and directories.
- Any paid workload validation needs a fresh exact manifest, current cost and
  quota preflight, explicit resource/runtime bounds, monitored Terraform
  operations, and independent cleanup verification.

## Evidence files produced

- No new customer-workload evidence file exists in this bootstrap commit.
- Existing direct evidence remains `docs/test/test437.md`.

## Follow-up work

After implementation, review whether ECS Express's generated supporting
resources and public endpoint behavior fit the approved profile. Keep the
renderer gated until the complete evidence package is reviewed.
