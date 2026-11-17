# ticket429 — bind saved-plan evidence to provider schema

PR: https://github.com/Bepoadewale/davdeploy/pull/429
Branch: `feat/pinned-provider-schema-evidence-429`

## Problem / goal

The generated Terraform runner validates each proposal using
`terraform providers schema -json` from its pinned provider installation, but
the saved-plan manifest records only the provider version and lockfile digest.
Add the schema document's supported format version and canonical digest to the
plan result and immutable evidence manifest so reviewers can identify the exact
schema used for the validation.

## Current repo state

Backend `main` is `e1fdb2e66908127b5834175612e85825e46a76a0`. The plan runner
pins Terraform `1.14.7` and AWS provider `5.100.0`, validates generated
resources against the installed provider schema, and records the provider
lockfile digest. PR #399 remains open/draft at
`5ec52533c26e206f8d80a655ace9aba3c95e263c`; all seven current-head checks passed
in run `44195944703`. No customer Nova workload has been run.

## Research / references used

- HashiCorp Terraform `providers schema` command documentation:
  https://developer.hashicorp.com/terraform/cli/commands/providers/schema
- `apps/api/src/davdeploy/generated_provider_validation.py`
- `apps/api/src/davdeploy/generated_terraform_plan.py`
- `apps/api/src/davdeploy/generated_plan_artifacts.py`
- `apps/api/src/davdeploy/service.py`
- `tests/test_generated_provider_validation.py`
- `tests/test_generated_terraform_plan.py`
- `tests/test_generated_plan_artifacts.py`

## Work planned for the PR

- Require and validate Terraform's schema JSON format version, rejecting
  unsupported major versions.
- Compute a canonical digest over the complete schema document used to validate
  the proposal.
- Carry schema format and digest in `GeneratedTerraformPlan` and the
  versioned, integrity-checked saved-plan manifest.
- Validate schema provenance when accepting generated-runner results and when
  verifying stored artifacts, without adding a database migration.
- Add tests for supported/unsupported format versions, digest changes, and
  manifest binding.

## Acceptance criteria

- [x] Unsupported or malformed provider schema format versions fail closed.
- [x] Valid schema format version and canonical schema digest are returned by
  the plan runner.
- [x] Immutable saved-plan manifest carries and validates schema provenance.
- [x] Existing provider lockfile, proposal, context, plan, and workspace digests
  remain bound as before.
- [x] Focused tests, full verification, docs conventions, and diff checks pass.
- [ ] All required GitHub checks pass on the final PR head.

## Acceptance status

Implementation is complete and locally verified. This is a source-only
evidence change; no Terraform or customer workload operation was performed.

## Tests / validation performed

- Focused provider validation, plan runner, artifact, review, and CodeBuild tests:
  92 passed.
- `make verify PY=/Users/adewale/Projects/davdeploy/.venv-pr399/bin/python`:
  1,306 passed; Ruff, configuration, OpenAPI snapshot, and Compose checks passed.
- `GITHUB_PR_NUMBER=429 .venv-pr399/bin/python scripts/check_doc_conventions.py`:
  passed.
- `git diff --check`: passed.
- GitHub checks are pending on the final PR head.
- No customer workload evidence file is required because no customer workload
  was run.

## Evidence files produced

- `docs/tickets/ticket429.md`
- No `docs/test/test429.md` is required because no customer workload was run.

## Boundaries

No AWS API call, Terraform plan/apply/destroy, database migration, hosted
runtime change, credential issuance, or customer workload is included. A schema
digest identifies the validated schema input; it does not prove AWS service
semantics, permissions, pricing, or application health.

## Follow-up work

Official AWS documentation/context provenance, per-module service semantics,
live Nova evaluation, and the first hosted customer lifecycle remain separate
acceptance work. Keep PR #399 draft until its customer account/role and complete
hosted lifecycle gates are satisfied.
