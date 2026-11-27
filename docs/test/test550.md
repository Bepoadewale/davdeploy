# test550 — Hosted Nova v13 graph validation failure

- Date: 2026-11-27
- Execution type: authenticated CLI review submission and hosted Nova plan-only
  generation
- Control-plane commit: `e8fc9ab8f391f22d889a119e9e3a64a47d4db09f`
- Commit: `319378be56cf830f159095c6b08fa8cf3bbad712`
- Pull request: [#550](https://github.com/Bepoadewale/davdeploy/pull/550)
- AWS account: `654654474502` (control plane only; no workload apply)
- AWS region: `us-east-1`
- Customer repository: `Bepoadewale/fitness-backend` (synthetic acceptance project)
- Run: `71ce7def-79ec-4128-adf3-e2de6973354e`
- Review revision: `fafb7ec2-2173-4ce8-a191-0b5a93a448d6`

## Resources created

The v13 control-plane release updated six Lambda packages, the Nova plan-only
CodeBuild project, and its plan-role policy under the exact reviewed saved plan.
It added/destroyed zero control-plane resources. The hosted Nova run created no
CodeBuild build, saved Terraform plan, or customer workload.

## Commands executed

- Verified protected plan `45991858852` and apply `45992221348` for the exact
  merge commit. Migrations passed; all six Lambda package hashes matched the
  versioned release artifact; `/healthz` returned HTTP 200.
- Authenticated the saved CLI session and confirmed workspace administrator
  access.
- Created and submitted a fresh review-only revision based on the same
  synthetic deployment recommendation, then queued run
  `71ce7def-79ec-4128-adf3-e2de6973354e`.
- Retrieved only safe run state and bounded generation diagnostics.

## Observed result

Run `71ce7def-79ec-4128-adf3-e2de6973354e` used prompt
`terraform-nova2-contract-v13` and failed with `NOVA_GENERATION_FAILED` after
2 attempts and 1 semantic repair. Safe feedback contained `value_error` at
`proposal` and the allowlisted generic resource-graph guidance. No CodeBuild
build or review-only artifact was created. No customer workload was approved
or applied.

A request to create a fresh run from the original revision returned the same
failed run because exact revision requests are deduplicated. A new review
revision was submitted instead; its own run failed as recorded above.

## Teardown

No customer workload resources were created. Run and review-revision metadata
remain as audit evidence; no cloud teardown was needed.

## Final boundary

This documents one bounded hosted generation failure and its diagnostics. It
does not establish a valid plan, approval, apply, application behavior,
lifecycle, or certification.

## Source regression verification

The v14 source maps each known graph validator cause to a distinct fixed issue
code and guidance, while unknown graph causes retain generic safe guidance.
Validation remains strict. Raw validator messages remain absent from feedback.

- Focused generation/run/review suites: 114 passed.
- Full `make verify`: config check, lint, 2,044 tests, OpenAPI snapshot, and
  Docker Compose configuration passed. One unrelated Starlette deprecation
  warning was emitted.
- PR CI run `45995049620` passed all seven checks.
