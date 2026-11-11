# ticket359 — bind untaggable AWS resources to exact remote state

PR: [#359](https://github.com/Bepoadewale/davdeploy/pull/359) (draft; number reserved)
Branch: `security/untaggable-ownership-359`
Base: `main`

## Problem / goal

Trusted ownership currently requires every generated AWS resource to accept a
reserved `tags` map. Some resources, including `aws_apigatewayv2_route`, do not
support that argument. Continue to deny them without state, and support them
only when their exact Terraform addresses and types are tied to the trusted,
tenant-scoped remote-state identity and saved-plan manifest.

## Current repo state

- Backend `main` is `4de1022592fdf65cdd38f32386cbccbce5a40071` (PR #358).
- The plan runner verifies the tenant state-scope digest before supplying the
  server-issued HTTP backend. Remote state remains disabled in production.
- `inject_trusted_ownership_tags()` currently rejects AWS resources without a
  safely writable `map(string)` tag schema.
- Plan artifacts bind the remote-state ID/scope and saved-plan digest, but do
  not list exact non-taggable resource ownership records.

## Research / references used

- [Terraform AWS `aws_apigatewayv2_route`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/apigatewayv2_route): route resources expose authorization settings and do not define a tags argument.
- DavDeploy's trusted state boundary: `apps/api/src/davdeploy/terraform_state.py` and `nova_plan_codebuild.py` validate the state-scope digest before planning.

## Work planned for the PR

- Derive exact non-taggable resource addresses/types only from the validated
  proposal and pinned provider schema.
- Fail closed without a server-issued remote state whose tenant scope matches
  the trusted organization, project, environment, account, and region.
- Pass the derived ownership records into actual-plan policy and bind them,
  along with the state ID/scope, into the immutable saved-plan manifest.
- Keep child-expanding resource types denied unless their individual AWS
  resources have independently verifiable ownership.

## Acceptance criteria

- [ ] Taggable resources retain exact reserved tag checks.
- [ ] Untaggable resources are denied without remote state or with a mismatched
  state scope; proposal-invented ownership metadata is rejected.
- [ ] Allowed untaggable addresses are exact, bounded, included in the manifest,
  and covered by the approved manifest digest.
- [ ] Unproposed and unsupported actions remain denied; replacement/deletion
  still requires human review.
- [ ] Focused tests, full clean-room proof, documentation conventions, and all
  required hosted CI pass.
- [ ] No AWS customer plan/apply or infrastructure mutation is performed.

## Acceptance status

In progress; bootstrap ticket only. No implementation changes have started.

## Tests / validation performed

- None yet.

## Evidence files produced

- This ticket tracks the implementation and validation for PR #359.

## Boundaries

This change does not enable hosted Nova planning or apply. Remote state remains
disabled unless the existing feature gates and tenant isolation checks are
enabled. It does not authorize importing arbitrary external AWS resources.

## Follow-up work

Finish the hosted plan-role permission verification, exact cost evidence,
approval/apply path, lifecycle behavior, and composed workload certification.
