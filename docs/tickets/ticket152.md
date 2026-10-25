# ticket152 — Enable private GitHub App onboarding

PR: [#152 — feat: enable private GitHub App onboarding](https://github.com/Bepoadewale/davdeploy/pull/152)
Branch: `feat/live-github-app-integration`

## Problem / goal

Connect DavDeploy to the existing GitHub App installation for read-only private repository
onboarding, without placing the App private key in source control, Lambda environment variables,
browser configuration, logs, or Terraform state.

## Current repo state

The existing GitHub App (`5159790`) is installed for `Bepoadewale` as installation `167128937` and
can read the selected repositories `Bepoadewale/ai-platform-control-plane` and
`Bepoadewale/davdeploy`. The deployed DavDeploy API has no GitHub App environment configuration
and correctly falls back to its fixture connection.

## Research / references used

- Existing `GitHubAppReadOnlyConnection` in `apps/api/src/davdeploy/integrations.py`.
- Existing local App-key validation against GitHub's installation API.
- Serverless control-plane Terraform and Lambda runtime IAM policies.

## Work planned for the PR

- Load the App private key from a dedicated Secrets Manager secret at Lambda runtime.
- Add least-privilege runtime permission and non-secret environment references.
- Pass non-secret App identifiers and the dedicated secret ARN only through protected Terraform
  workflow variables.
- Preserve fixture behaviour when live App mode is not explicitly configured.
- Add focused tests and a deployment/operator handoff for the secret prerequisite.

## Acceptance criteria

- [ ] Lambda reads the configured App key only from a dedicated secret reference.
- [ ] Private repository and branch discovery work through the existing App installation.
- [ ] The key is absent from source, Terraform state, public configuration and logs.
- [ ] Fixture mode remains available when live App mode is disabled.
- [ ] Focused tests and required CI pass.

## Acceptance status

Implementation complete locally; review, CI and a separate production deployment are pending.

## Tests / validation performed

- Read-only verification of the existing GitHub App installation and selected repositories.
- Focused integration tests, Ruff, Terraform initialization/validation, format check and diff
  validation passed locally.

## Evidence files produced

- `docs/test/test152.md`

## Boundaries

This change enables read-only repository onboarding only. It does not enable GitHub writes,
create cloud resources, apply Terraform, or destroy customer resources.

## Follow-up work

After deployment, configure the dedicated secret and validate the customer workspace can select a
private repository before resuming the service deployment lifecycle.
