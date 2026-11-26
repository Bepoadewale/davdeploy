# ticket521 — Keep the hosted Lambda environment within AWS limits

PR: #521
Branch: `feat/lambda-env-budget-520`

## Problem / goal

Allow the current control-plane release to deploy without exceeding AWS
Lambda's 4 KiB environment-variable limit. Keep disabled Nova apply features
closed, preserve explicit external OpenID Connect configuration, and avoid
changing hosted behavior beyond deriving Cognito's standard JWKS URL.

## Current repo state

- Backend `main` is `dbbf7c135b7be97c832927d5c1758bc1faab805d`; PR #519 is a
  separate open draft.
- Protected plan run `45885643638` was applyable with 0 additions, 8 updates,
  and 0 destroys. Protected apply run `45886527901` partially applied, then
  failed when AWS rejected the API, worker, and migration Lambda environment
  maps at 4,487 bytes (limit 4,096).
- The three affected functions remain active on the prior package. Other
  functions, the Nova plan-only CodeBuild project, and its scoped policy
  updated. A fresh Terraform plan is required after this PR merges; the old
  saved plan must not be reused.
- Terraform's `enable_nova_exact_plan_apply_runner` and
  `enable_nova_apply_role_onboarding` default to false. Runtime code reads
  their flags with false/empty defaults. The control plane currently supplies
  both `DAVDEPLOY_OIDC_ISSUER` and the derivable Cognito
  `DAVDEPLOY_JWKS_URL`.

## Research / references used

- AWS Lambda environment variable quota:
  https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html
- Cognito original and updated issuer formats, and JWKS path:
  https://docs.aws.amazon.com/cognito/latest/developerguide/federation-endpoints.html
- Cognito token verification and JWKS guidance:
  https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-tokens-verifying-a-jwt.html
- Lambda environment map and default-off Terraform gates:
  `infrastructure/terraform/serverless-control-plane/main.tf` and
  `variables.tf`
- Failure evidence: protected GitHub apply run `45886527901`.

## Work planned for the PR

1. Build the shared Lambda environment map with conditionally merged Nova
   exact-apply and apply-role onboarding settings, so disabled capabilities do
   not consume environment bytes or accidentally become enabled.
2. Derive the standard Cognito JWKS endpoint from original or updated Cognito
   issuer formats when no explicit URL is supplied; keep explicit URLs
   supported for other identity providers.
3. Add tests for disabled-feature omission and Cognito derivation, while
   retaining checks that apply features remain disabled by default.
4. Run focused tests, full verification, Terraform format/validation, docs
   conventions, and the required clean-room release proof.

## Acceptance criteria

- [x] Disabled apply runner and apply-role onboarding settings are omitted
  from the Lambda map; runtime defaults remain false/empty.
- [x] Enabling either feature includes all settings required by that feature.
- [x] Cognito issuer produces the exact standard JWKS URL; an explicit JWKS
  URL remains authoritative for non-Cognito providers.
- [ ] The resulting hosted environment fits within Lambda's 4 KiB limit with
  measured margin in a fresh protected plan.
- [x] Focused tests, full verification, Terraform validation, docs checks,
  and clean-room proof pass locally; required CI remains pending.
- [ ] A fresh exact saved plan has no unexpected destroys and passes review
  before a new protected apply attempt.

## Acceptance status

Source implementation is complete and locally verified. A fresh protected
plan must confirm the measured environment size before apply. The failed
hosted apply is recorded above; its saved plan will not be reused.

## Tests / validation performed

- `GITHUB_PR_NUMBER=521 python3 scripts/check_doc_conventions.py`: passed.
- Focused tests: `test_security_identity.py`,
  `test_nova_exact_plan_apply_infra.py`, and `test_terraform_plan_summary.py`;
  40 passed, including original and updated Cognito issuer formats.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python`:
  passed, 1,974 tests; one existing Starlette/httpx deprecation warning.
- Terraform format check, backend-free initialization, and validation passed.
- `make local-proof`: clean-room bootstrap, smoke, API contract, customer-plan
  E2E, data seeding, trace check, and full verify passed. `make clean-local`
  passed after the Cognito issuer update. `make clean-local` removed only this
  worktree's project-prefixed Compose services, network, volume, and generated
  `.venv`/`.local` artifacts.
- `git diff --check`: passed.

## Evidence files produced

- Protected workflow run `45886527901` is the current failure evidence.
- No workload test or fresh post-fix protected plan has run yet.
- `docs/test/test521.md` will record a later fresh plan/apply and deployment
  health verification if that workflow is completed.

## Boundaries

- Keep exact saved-plan apply and apply-role onboarding disabled.
- Do not enable Nova customer apply or hosted certification.
- Do not modify customer connections, customer workloads, control-plane state
  directly, credentials, MFA, or CloudFormation stacks in this PR.
- Do not reuse failed run `45886527901`'s saved plan. Reconcile its partial
  state through a fresh protected plan after merge.
- Preserve all untracked root checkout files and existing test evidence.

## Follow-up work

- Failure evidence: GitHub apply run `45886527901`; three Lambda environment
  updates were rejected at 4,487 bytes. Read-only reconciliation confirmed
  prior API/worker/migration packages and no active Terraform operation.
- Fresh plan/apply and post-deploy health, package, and template URL checks
  will be recorded in a PR-numbered `docs/test/test521.md` evidence file after
  the hosted workflow runs.
