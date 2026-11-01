# ticket214

PR: [#214](https://github.com/Bepoadewale/davdeploy/pull/214)

Branch: `fix/migration-resume-retry`

## Problem / goal

Make Terraform deployment verification tolerant of Aurora Serverless resuming
after an idle period, without hiding real migration failures.

## Current repo state

Production Terraform apply run `41285714614` completed all infrastructure
updates, but its migration verification stopped after six ten-second retries
while Aurora was still resuming. A read-only follow-up Lambda invocation then
returned `migrations-complete`.

## Research / references used

- GitHub Actions run `41285714614` migration logs.
- The deployed migration Lambda response showing `DatabaseResumingException`.
- Existing Terraform apply workflow and Aurora runbook.

## Work planned for the PR

- Retry only the documented transient Aurora resume response.
- Allow a bounded six-minute resume window.
- Stop immediately and preserve the migration response for non-retryable
  migration failures.

## Acceptance criteria

- [x] The workflow identifies `DatabaseResumingException` as retryable.
- [x] The workflow allows up to 24 attempts, fifteen seconds apart.
- [x] Other migration failures stop immediately with diagnostics.
- [x] No infrastructure, customer data, or customer workload is changed by
  this source update.
- [ ] Required GitHub CI and reviewed deployment complete.

## Acceptance status

Local static validation passed: documentation conventions and 310 backend tests.
GitHub CI and deployment remain pending.

## Tests / validation performed

See `docs/test/test214.md`.

## Evidence files produced

- `docs/test/test214.md`

## Boundaries

This changes only GitHub Actions retry behavior after a saved Terraform plan
has been applied. It does not change database schema, Aurora capacity, Lambda
code, customer data, or access permissions.

## Follow-up work

After merge, run a reviewed Terraform plan and apply to verify the new
bounded-retry behavior during a future Aurora resume.
