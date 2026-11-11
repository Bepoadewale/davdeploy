# ticket354 — redact hosted Terraform plan output

PR: [#354](https://github.com/Bepoadewale/davdeploy/pull/354) (merged)
Branch: `security/sanitize-terraform-plan-logs-354` (deleted after merge)
Base: `main`

## Problem / goal

The protected Terraform plan workflow runs `terraform plan -out=tfplan` with
the default human-readable output. The plan can include values unsuitable for
GitHub Actions logs. Replace that output with a bounded summary that shows
resource actions and the Nova feature gates needed for review without printing
resource or variable values.

## Current repo state

- PR #354 merged as `9532983a768b1b47713363dd82eb7155ed09c4a2`; current
  `main` has since advanced through PR #355.
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

- [x] A successful protected plan log shows the bounded resource action
  summary and selected Nova/legacy feature-gate values, without plan values.
- [x] Secret-like strings in planned values, prior state, variables, and
  resource diffs never appear in parser output or errors in regression tests.
- [x] Malformed or oversized JSON, non-boolean feature gates, and plans that
  are errored, incomplete, or not applyable fail closed in local tests.
- [x] Saved-plan file, manifest, digest verification, protected environment,
  and apply workflow semantics remain unchanged.
- [x] Focused tests, `make verify`, and docs checks pass locally.
- [x] Required hosted CI passes on the final PR head.

## Acceptance status

Merged and locally/hostedly verified. The post-merge protected plan check
passed against exact commit `9532983a768b1b47713363dd82eb7155ed09c4a2` in run
`43077213967`. It emitted the bounded summary only: 0 additions, 6 updates,
0 destroys, 0 drift, and 8 output changes. The Nova runner, role verification,
credential broker, plan review, state and hosted-certification gates were
false. This saved plan was not applied after PR #355 advanced `main`; a new
plan for the current source is required before a control-plane deployment.

## Tests / validation performed

- `uv run pytest tests/test_terraform_plan_summary.py -q` — 12 passed.
- `DAVDEPLOY_DATABASE_URL=sqlite+pysqlite:///:memory: make verify` — 934
  passed; Ruff, Actions configuration, OpenAPI, and Docker Compose checks
  passed. One existing Starlette/httpx deprecation warning remains.
- `GITHUB_PR_NUMBER=354 python3.12 scripts/check_doc_conventions.py` and
  `git diff --check` — passed.
- Required final-head CI run `43075119402` passed all seven jobs. PR #354 was
  merged at `9532983a768b1b47713363dd82eb7155ed09c4a2`.
- Protected plan run `43077213967` completed successfully on that merged
  commit. Its log was checked for the sanitized summary; no raw plan values
  were surfaced. This was a control-plane plan only, not an apply.

## Evidence files produced

- `docs/test/test353.md` records the separate protected PR #353 control-plane
  release. No customer-workload test evidence applies to this PR.

## Boundaries

This changes only control-plane Terraform plan logging. It does not alter the
Nova customer-plan approval policy, pricing gate, runner, state, or execution
authorization. The exact control-plane deployment after PR #353 is tracked in
the local-only Nova goal ledger.

## Follow-up work

Before applying current `main`, dispatch and review a fresh protected plan
that includes PR #355's SQS policy code (and any intervening merged policy
changes). The exact successful PR #354 plan is now stale for current `main`.
