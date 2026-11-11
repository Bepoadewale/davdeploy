# ticket359 — bind untaggable AWS resources to exact remote state

PR: [#359](https://github.com/Bepoadewale/davdeploy/pull/359) (draft; number reserved)
Branch: `security/untaggable-ownership-359`
Base: `main`

## Problem / goal

Trusted ownership currently requires every generated AWS resource to accept a
reserved `tags` map. Some resources, including `aws_apigatewayv2_route`, do not
support that argument. Continue to deny unsupported resources and support the
explicitly allowlisted API Gateway route only when its exact Terraform address
and type are tied to the trusted, tenant-scoped remote-state identity and
saved-plan manifest.

## Current repo state

- Backend `main` is `4de1022592fdf65cdd38f32386cbccbce5a40071` (PR #358).
- The plan runner verifies the tenant state-scope digest before supplying the
  server-issued HTTP backend. Remote state remains disabled in production.
- `inject_trusted_ownership_tags()` adds reserved tags where supported and now
  derives an exact state-backed ownership record for the allowlisted
  `aws_apigatewayv2_route` type.
- Plan artifacts bind the remote-state ID/scope and saved-plan digest; manifest
  version 6 now also binds exact non-taggable addresses and resource types.

## Research / references used

- [Terraform AWS `aws_apigatewayv2_route`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/apigatewayv2_route): route resources expose authorization settings and do not define a tags argument.
- DavDeploy's trusted state boundary: `apps/api/src/davdeploy/terraform_state.py` and `nova_plan_codebuild.py` validate the state-scope digest before planning.

## Work planned for the PR

- Derive exact non-taggable API Gateway route addresses/types only from the
  validated proposal and pinned provider schema; keep other untaggable types
  denied.
- Fail closed without a server-issued remote state whose tenant scope matches
  the trusted organization, project, environment, account, and region.
- Pass the derived ownership records into actual-plan policy and bind them,
  along with the state ID/scope, into the immutable saved-plan manifest.
- Require each API Gateway route to use a typed `api_id` reference to exactly
  one API declared in the same proposal and present in the actual plan. Routes
  targeting external or unproven APIs are denied.
- Keep child-expanding resource types denied unless their individual AWS
  resources have independently verifiable ownership.
- Carry the bounded ownership inventory through the CodeBuild result envelope
  and independently reconstruct it when the service verifies the manifest.

## Acceptance criteria

- [x] Taggable resources retain exact reserved tag checks.
- [x] Untaggable resources are denied without remote state or with a mismatched
  state scope; proposal-invented ownership metadata is rejected.
- [x] Allowed untaggable addresses are exact, bounded, included in the manifest,
  and covered by the approved manifest digest.
- [x] Unproposed and unsupported actions remain denied; replacement/deletion
  still requires human review.
- [ ] Focused tests, full clean-room proof, documentation conventions, and all
  required hosted CI pass.
- [x] No AWS customer plan/apply or infrastructure mutation is performed.

## Acceptance status

Implementation is locally verified and the clean-room proof passed. Hosted CI
and independent review are pending. The feature still does not enable remote
state or customer execution.

## Tests / validation performed

- `tests/test_generated_plan_ownership.py`,
  `tests/test_generated_plan_artifacts.py`,
  `tests/test_generated_plan_policy.py`,
  `tests/test_generated_terraform_plan.py`,
  `tests/test_nova_plan_dispatch.py`, and `tests/test_nova_plan_runs.py`:
  273 focused tests passed before the final API-target regression was added;
  the policy suite then passed all 113 tests.
- `DAVDEPLOY_DATABASE_URL=sqlite+pysqlite:///:memory: make verify`:
  968 tests passed; Ruff, OpenAPI, Actions configuration, and Compose checks
  passed. This run includes the API-target regression.
- Clean-room `make local-proof` after the API-target change passed: 968 tests,
  API contract, customer-plan E2E, demo seed, trace check, OpenAPI, Actions,
  Ruff, and Compose validation. One existing Starlette/httpx deprecation
  warning remains. Project `davdeploy-pr359` containers were stopped; the
  worktree and generated test volume/database were retained.

## Evidence files produced

- This ticket tracks the implementation and validation for PR #359.

## Boundaries

This change does not enable hosted Nova planning or apply. Remote state remains
disabled unless the existing feature gates and tenant isolation checks are
enabled. It does not authorize importing arbitrary external AWS resources.

## Follow-up work

Finish the hosted plan-role permission verification, exact cost evidence,
approval/apply path, lifecycle behavior, and composed workload certification.
