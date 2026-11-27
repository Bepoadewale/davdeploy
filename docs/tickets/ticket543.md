# ticket543 — Safe Nova resource validation repair guidance

PR: #543
Branch: `fix/nova-resource-feedback-543`

## Problem / goal

The hosted prompt-v7 run failed after two Nova attempts because two generated
resources failed a known resource-level validation check. Its safe diagnostic
reported only `value_error` at `resources[*]`; existing repair guidance covered
identifier and whole-graph failures but not resource arguments or outputs.
Give those known validator errors fixed, allowlisted guidance and version the
prompt contract.

## Current repo state

- Main is `0292907e4c3b10287c753a010fba9982a7e677c9`, with prompt v7 deployed.
- PR #542 merged as that commit; the protected apply completed, migration
  succeeded, all six Lambda packages matched the release, and API health was
  HTTP 200.
- Fresh, corrected submitted revision
  `efa863ee-d2d0-4256-871f-ecf05bbb61fd` requests private files, relational
  writes/reads, and asynchronous background jobs. It is unapproved and
  unexecuted.
- Hosted run `137ab46f-f5ee-4fa8-80cf-363ffc5f2736` failed under prompt v7
  before CodeBuild. It used two model attempts and one repair; safe feedback
  contained two `value_error` entries at `resources[*]`. Usage was 11,459 input
  tokens, 3,907 output tokens, and 14,713 ms; estimated cost was unavailable.
  No build, Terraform plan, or AWS workload was created.
- The earlier v6 run's explicit retry returned HTTP 409 and remains failed. Do
  not exceed its retry limit; PR #543 will retry only the fresh v7 run once
  after deployment.

## Research / references used

- Resource-level validators in
  `apps/api/src/davdeploy/generated_deployment_contract.py`.
- Safe feedback construction in `apps/api/src/davdeploy/terraform_generation.py`.
- Hosted v7 diagnostics recorded in `docs/test/test543.md` without raw proposal
  text or secrets.

## Work planned for the PR

- Map only fixed, known `GeneratedResource` validation causes to fixed
  argument/output correction guidance.
- Continue stripping raw validator messages and untrusted model guidance.
- Bump the recorded Nova contract prompt version to v8.
- Add tests for resource argument and output feedback plus persisted diagnostic
  allowlisting.

## Acceptance criteria

- [x] Known resource argument/output validator errors receive fixed guidance.
- [x] Guidance is emitted only for exact allowlisted validator causes and
      remains allowlisted at the hosted diagnostic boundary.
- [x] The prompt version identifies the changed repair behavior as v8.
- [x] All seven required hosted CI checks pass.
- [ ] Deploy the merged control-plane update and retry the fresh run once;
      inspect its bounded outcome.

## Acceptance status

Implementation is locally verified; hosted CI, protected deployment, and the
hosted retry are pending. No valid plan or customer workload is claimed.

## Tests / validation performed

- Prior hosted v7 run and safe diagnostics: `docs/test/test543.md`.
- Focused tests: 101 passed, 1 existing Starlette deprecation warning.
- Ruff, documentation conventions, and `git diff --check` passed.
- GitHub Actions run `45953221246`, head `afc97c77482c1d4d526b932125e30bc3de03bfcf`:
  all seven required checks passed.
- Required GitHub Actions checks: pending.

## Evidence files produced

- `docs/test/test543.md` — hosted v7 generation failure and boundaries.
- Safe diagnostics from the v8 retry will be appended after deployment.

## Boundaries

- No approval or apply of the synthetic customer workload.
- No Terraform operation, customer resource, or control-plane change is part of
  the implementation until the PR is merged and the protected deployment is
  reviewed.
- Never return raw validator messages, model output, secrets, saved plans, or
  state.
- Preserve the failed v6 run and its retry cap, all audit evidence, and local
  worktrees.

## Follow-up work

- Retry fresh run `137ab46f-f5ee-4fa8-80cf-363ffc5f2736` once after v8 is
  deployed.
- If the saved plan is generated, verify its resources cover the API, private
  file roundtrip, relational write/read, and async job completion, plus live
  regional pricing and all exact-plan policy evidence before any approval.
- Continue to report the goal incomplete until hosted apply, lifecycle,
  recovery, destruction, and independent absence gates are evidenced.
