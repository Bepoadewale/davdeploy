# ticket153 — Use valid GitHub App environment variable names

PR: [#153 — fix: use valid GitHub App environment variable names](https://github.com/Bepoadewale/davdeploy/pull/153)
Branch: `fix/github-app-environment-variable-names`

## Problem / goal

GitHub Actions rejects protected-environment variable names beginning with `GITHUB_`. Rename the
non-secret GitHub App deployment metadata so the reviewed Terraform workflow can receive it.

## Current repo state

The dedicated AWS Secrets Manager credential exists, and the enable flag is set in the protected
Terraform-plan environment. The App ID, installation ID and credential-secret ARN were rejected
only because their original environment variable names started with `GITHUB_`.

## Research / references used

- GitHub Actions environment-variable API returned HTTP 422 for the reserved prefix.
- PR #152 established the secret-reference-only runtime contract.

## Work planned for the PR

- Rename the three protected-environment variable references to the `DAVDEPLOY_` namespace.
- Update the Actions configuration classifier.

## Acceptance criteria

- [ ] The workflow uses valid protected-environment variable names.
- [ ] The Actions configuration classifier passes.
- [ ] The GitHub App private key remains absent from GitHub configuration.

## Acceptance status

Implementation in progress.

## Tests / validation performed

- Pending focused Actions configuration validation.

## Evidence files produced

- `docs/test/test153.md`

## Boundaries

This change adjusts metadata names only. It does not change the App key, enable GitHub writes,
apply Terraform, or change customer resources.

## Follow-up work

Set the renamed protected-environment variables, run the reviewed Terraform plan/apply workflow,
then validate live private repository onboarding.
