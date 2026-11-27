# ticket544 — Specific safe Nova resource validation feedback

PR: #544 (draft)
Branch: `fix/nova-specific-feedback-544`

## Goal

Make known Nova resource argument validation failures actionable for both the
bounded repair attempt and an administrator reviewing safe diagnostics. Preserve
strict validation and never reveal generated values or raw validator messages.

## Current state

- Main is `f508951645327e0d2b77d0904d17d44a783e1e57`; PR #543's v8 prompt and
  fixed generic resource guidance are deployed by protected apply run
  `45955715362`.
- The one authorized v8 retry of hosted run
  `137ab46f-f5ee-4fa8-80cf-363ffc5f2736` failed before CodeBuild with
  `proposal_invalid`, 2 attempts, 1 repair, and one safe `value_error` at
  `resources[*]`. No plan or workload exists. This run must not be retried again.
- Six control-plane Lambdas match the versioned package for the deployed main
  commit; migration verification and `/healthz` passed.

## Work planned

- Classify only exact known resource validator causes into fixed safe issue
  codes and cause-specific fixed guidance.
- Preserve an allowlist at both model-feedback and hosted diagnostic boundaries.
- Bump the prompt version to v9 and add focused tests for every classification.
- After merge and protected deployment, create a fresh plan-only generation
  run; never approve or apply the customer workload.

## Acceptance criteria

- [ ] Known resource errors return specific allowlisted issue codes and fixed
  corrective guidance.
- [ ] Raw error causes, field names, generated values, and secrets remain hidden.
- [ ] Focused tests, lint, docs checks, and all required CI pass.
- [ ] A new post-deployment hosted run provides an inspectable plan or a more
  specific bounded failure. No customer workload is applied.

## Validation and evidence

- Local checks: pending.
- Hosted CI: pending.
- Hosted v8 failure and later v9 outcome: `docs/test/test544.md`.

## Boundaries

- Never weaken validation or relax provider/account/region/policy constraints.
- Do not retry the failed v8 run again.
- Do not approve or apply any customer workload.
- Never print or persist raw model proposals, plan values, or credentials.

## Follow-up

- Continue to exact-plan policy and pricing checks if the new run reaches a
  saved plan; otherwise use only bounded diagnostics to select another fix.
- The Nova goal remains incomplete until all hosted apply, behavior, lifecycle,
  recovery, cleanup, and capability matrix gates are evidenced.
