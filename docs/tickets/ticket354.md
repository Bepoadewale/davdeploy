# ticket354 — redact hosted Terraform plan output

PR: [#354](https://github.com/Bepoadewale/davdeploy/pull/354) (draft)
Branch: `security/sanitize-terraform-plan-logs-354`
Base: `main`

## Problem / goal

The protected Terraform plan workflow runs `terraform plan -out=tfplan` with
the default human-readable output. The plan can include values unsuitable for
GitHub Actions logs. Replace that output with a bounded summary that shows
resource actions and the Nova feature gates needed for review without printing
resource or variable values.

## Current repo state

- Backend `main` is at `0896ae6106fe1e7526dba90105639f894d5534b8` (PR #353).
- Terraform plan workflow is `.github/workflows/terraform-plan.yml` and uses
  Terraform 1.14.7, a protected OIDC plan role, and an encrypted immutable
  saved-plan manifest. It currently prints the normal `terraform plan`
  rendering to the Actions log.
- The user requires sensitive plan/state data to remain out of logs and model
  context. The protected apply continues to verify the exact saved plan; this
  PR does not change apply behavior or customer execution gates.

## Research / references used

- HashiCorp [`terraform show`](https://developer.hashicorp.com/terraform/cli/commands/show)
  documents JSON inspection of saved plans and warns that sensitive values are
  displayed in JSON. The parser must therefore consume JSON in-process and
  emit only an explicit allowlist of summary fields.
- HashiCorp [Terraform JSON output format](https://developer.hashicorp.com/terraform/internals/json-format)
  describes `resource_changes`, `planned_values`, `applyable` and `errored`.
- HashiCorp [`terraform plan`](https://developer.hashicorp.com/terraform/cli/commands/plan)
  documents saved plan creation with `-out`.

## Work planned for the PR

- Add a bounded parser for `terraform show -json tfplan` output. Emit only
  action counts, safe resource addresses/types/actions, changed attribute
  names, drift/output counts, selected boolean Nova/legacy execution flags,
  and applyability state.
- Fail closed for malformed/oversized plan JSON or a non-applyable, errored,
  or incomplete plan, without echoing Terraform's raw JSON or plan diagnostics.
- Suppress Terraform's normal plan rendering from the workflow log while
  retaining the existing saved-plan hash and manifest path.
- Add regression tests that seed sensitive-looking values in plan JSON and
  prove they do not appear in the summary.

## Acceptance criteria

- [ ] Successful plan logs show the exact resource action summary and selected
  Nova/legacy feature-gate values, but no plan values. A protected plan run on
  a merged commit with this workflow change is still required to prove this.
- [x] Secret-like strings in planned values, prior state, variables, and
  resource diffs never appear in parser output or errors in regression tests.
- [x] Malformed or oversized JSON, non-boolean feature gates, and plans that
  are errored, incomplete, or not applyable fail closed in local tests.
- [x] Saved-plan file, manifest, digest verification, protected environment,
  and apply workflow semantics remain unchanged.
- [x] Focused tests, `make verify`, and docs checks pass locally.
- [ ] Required hosted CI passes on the final PR head.

## Acceptance status

Implementation and local verification are complete; final PR CI, current-head
review, and merge are pending. The protected plan/apply workflow for PR #353
completed while this PR was being implemented. That release is recorded in
`docs/test/test353.md`; it is not an apply by this PR.

## Tests / validation performed

- `uv run pytest tests/test_terraform_plan_summary.py -q` — 12 passed.
- `DAVDEPLOY_DATABASE_URL=sqlite+pysqlite:///:memory: make verify` — 934
  passed; Ruff, Actions configuration, OpenAPI, and Docker Compose checks
  passed. One existing Starlette/httpx deprecation warning remains.
- `GITHUB_PR_NUMBER=354 python3.12 scripts/check_doc_conventions.py` and
  `git diff --check` — passed.
- The new parser has not yet processed a protected hosted plan artifact; that
  integration evidence is required after merge. No apply or customer AWS
  resource mutation was performed for PR #354.

## Evidence files produced

- `docs/test/test353.md` records the separate protected PR #353 control-plane
  release. No customer-workload test evidence applies to this PR.

## Boundaries

This changes only control-plane Terraform plan logging. It does not alter the
Nova customer-plan approval policy, pricing gate, runner, state, or execution
authorization. The exact control-plane deployment after PR #353 is tracked in
the local-only Nova goal ledger.

## Follow-up work

After merge, dispatch a protected plan for the merged commit and verify the
sanitized summary contains actions and explicit feature gates without plan
values. Do not apply until that exact summary has been reviewed.
