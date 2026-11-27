# test549 — Hosted Nova v12 generic-feedback failure

- Date: 2026-11-27
- Execution type: authenticated CLI status/audit reads and one bounded hosted
  Nova plan-only retry
- Control-plane commit: `03d3192a4e5e5ec2c6b86f0c5abb47c8d2c2bdb4`
- Commit: `d428e9f45ec38cb270cda46fa38ab9a845a38c58` (implementation)
- Pull request: [#549](https://github.com/Bepoadewale/davdeploy/pull/549)
- AWS account: `654654474502` (control plane only; no workload apply)
- AWS region: `us-east-1`
- Customer repository: `Bepoadewale/fitness-backend` (synthetic acceptance project)
- Run: `7ed97bc9-4460-40bb-9ca7-7bf8a84b38b2`

## Resources created

The control-plane release updated six existing Lambda packages, one CodeBuild
project, and one Nova plan-role policy according to the exact reviewed saved
plan. It created zero and destroyed zero control-plane resources. No Nova
customer workload, CodeBuild plan, or saved Terraform plan was created by the
v12 retry.

## Commands executed

- Verified the protected saved-plan release and migration run through GitHub
  Actions; all six Lambda `CodeSha256` values matched the release artifact.
- Verified AWS caller account `654654474502` and API `/healthz` HTTP 200.
- Authenticated the stored CLI session through Keychain and verified
  `/api/v1/me` returned the workspace administrator role.
- Queried the exact run and entity-filtered audit events; the run was `FAILED`
  and had zero prior explicit retries before this request.
- Submitted one retry using a fresh `Idempotency-Key`; the API returned the
  same run ID in `QUEUED` state.

## Observed result

The retry used prompt `terraform-nova2-contract-v12` and failed as
`NOVA_GENERATION_FAILED` / `proposal_invalid` after 2 attempts and 1 semantic
repair in 15,069 ms. Safe persisted diagnostics contained no validation feedback
items. The error summary was the generic bounded message. No CodeBuild job or
review-only artifact was created. Estimated model cost was unavailable.

This run has consumed its one explicit retry and must not be retried again.
Source regression tests and v13 follow-up are pending in PR #549. The finding
does not establish plan, approval, apply, application behavior, lifecycle, or
certification.

## Source regression verification

The v13 source maps an unrecognized validator error to fixed generic
`invalid`/`proposal` feedback. Regression coverage checks that private
validator messages, inputs, and codes do not enter the correction feedback or
persisted diagnostics. The validation schema remains strict.

- Focused generation/run/review suites: 107 passed.
- Full `make verify`: config check, lint, 2,037 tests, OpenAPI snapshot, and
  Docker Compose configuration passed. One unrelated Starlette deprecation
  warning was emitted.
- PR CI run `45989952826` passed all seven checks.

## Teardown

The synthetic run created no AWS workload resources and needs no cloud
teardown. Run metadata remains as audit evidence.

## Final boundary

This documents one bounded hosted generation failure. It does not establish a
valid plan, approval, apply, application behavior, lifecycle, or certification.
