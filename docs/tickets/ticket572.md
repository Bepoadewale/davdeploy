# ticket572 — Use GitHub Actions for clean integration proof

PR: #572
Branch: `docs/ci-only-cleanroom-validation-572`

## Problem / goal

Active repository instructions ask contributors or Codex to start a full local
Compose clean-room cycle for selected changes. The required GitHub Actions
`local-e2e` job already builds and tests the app on a fresh runner, then cleans
up its stack. Make that hosted runner the required integration proof and stop
asking for a second manual stack on the developer's machine.

## Current repo state

- Main includes PR #571 merge `89ff857e95bfbccaedad659648f639d574298b10`.
- `.github/workflows/ci.yml` defines a blocking `local-e2e` job on
  `ubuntu-latest`. It bootstraps Compose, runs app integration/failure/demo
  checks and `make verify`, then calls `make clean-local` on the runner.
- `AGENTS.md`, the PR template, `DEFINITION_OF_DONE.md`, `CODEX_DAILY_TASK.md`,
  and the flagship evolution strategy still instruct or imply a manual local
  clean-room run.
- README and demo instructions present `make local-proof` as the default local
  proof path.

## Research / references used

- `.github/workflows/ci.yml` `local-e2e` job: clean GitHub-hosted runner and
  automatic Compose teardown.
- `AGENTS.md` validation gate and root PR template.
- README, `docs/DEMO.md`, `DEFINITION_OF_DONE.md`, `CODEX_DAILY_TASK.md`,
  `docs/strategy/flagship-evolution-plan.md`, and `Makefile` developer help.

## Work planned for the PR

- Remove active instructions to manually launch a full local clean-room stack.
- Define GitHub Actions `local-e2e` as the required fresh-runner integration
  proof for PRs.
- Keep `make local-proof` available only as an optional troubleshooting and
  local development target.
- Preserve the GitHub workflow and historical test evidence unchanged.

## Acceptance criteria

- [x] No active contributor or Codex instruction requires a manual local
      clean-room Compose run as a PR gate.
- [x] Required integration proof remains on the GitHub Actions runner and the
      `local-e2e` workflow continues to clean its own Compose stack.
- [x] Local stack commands are clearly optional developer tools, not merge
      requirements.
- [x] Historical execution records remain intact; docs conventions and diff
      checks pass.
- [ ] Required GitHub CI passes.

## Acceptance status

Active guidance now identifies GitHub Actions `local-e2e` as the required
fresh-runner integration proof. Manual local Compose and `make local-proof` are
optional troubleshooting tools. Historical test records and the CI workflow
are unchanged.

## Tests / validation performed

- Read-only audit found manual clean-room instructions in `AGENTS.md`, the PR
  template, definition of done, daily task, flagship strategy, README, and demo
  guide. Those active instructions now point to GitHub Actions or label local
  targets optional.
- Confirmed `.github/workflows/ci.yml` still runs `local-e2e` on `ubuntu-latest`
  and invokes `make clean-local` in its `always()` cleanup step.
- Historical `docs/test/` evidence, prior tickets, and past execution claims
  remain unchanged.
- No Docker stack, cloud API, Terraform operation, or AWS workload is required
  for this documentation-only change.
- `GITHUB_PR_NUMBER=572 python3 scripts/check_doc_conventions.py` and
  `git diff --check` passed.

## Evidence files produced

- `docs/test/test572.md` — repository instruction audit and validation.

## Boundaries

Do not remove or weaken the GitHub Actions `local-e2e` check. Do not rewrite
historical test evidence as if it had run on GitHub. Do not delete local data,
change Docker resources, mutate AWS, or alter control-plane Terraform.

## Follow-up work

After final documentation checks and GitHub CI pass, merge this PR through the
normal pull-request workflow. Continue Nova release validation with the
protected AWS control-plane deployment and hosted plan-only run; do not use
local Compose as a substitute for that hosted evidence.
