# ticket565 — Surface safe Nova plan-runner failure codes

PR: #565
Branch: `fix/nova-runner-failure-codes-565`

## Problem / goal

The first hosted v26 plan-only request reached CodeBuild, then failed in its
`BUILD` phase. The product status exposed only `CODEBUILD_FAILED` and a fixed
generic summary; the CodeBuild log also emitted only a generic runner failure.
That is not enough to tell whether the exact customer role, tenant state
bootstrap, Terraform pipeline, policy, or artifact storage stopped the run.

Emit a bounded, allowlisted failure code for known Nova plan-runner failures so
the operator can choose the next fix from evidence. Keep exception text,
proposals, credentials, saved-plan data, and state out of logs. This is
diagnostic evidence only; it does not make a failed plan successful or
approvable.

## Current repo state

- Source main and deployed control-plane release are
  `a5d38166bbc30942ac4ea82622712221446e1343` (PR #564).
- Protected plan `46124569024` and exact saved-plan apply `46125147226` passed;
  database migrations passed, all six control-plane Lambdas matched the
  versioned release package, and `/healthz` returned HTTP 200.
- Authenticated CLI session for the selected workspace administrator remains
  valid. The same-account planning connection is `VERIFIED`; its planning-role
  profile and policy are `PROFILE_VERIFIED`.
- Fresh v26 review-only revision `f017ecba-22c2-4a01-9074-8632b505839c` and
  plan-only run `5a917d8b-93ba-4a85-8d7e-258e0b753ebe` were created from the
  existing synthetic API/storage/database/async intent. Content digest matched
  the previous review; `decision=null` and execution was
  `UNEXECUTED_APPROVAL_ONLY`.
- The run is terminal `FAILED` / `CODEBUILD_FAILED`, with no plan artifact.
  CodeBuild build `davdeploy-nova-plan-only:68cd98fd-633a-4e8d-9bda-750a6ab6dd7f`
  failed in the fixed `BUILD` command. The safe API summary is generic, and the
  log contains only the generic failure line. No Terraform plan, apply, or
  workload resource creation was observed.
- The architecture plan remains `APPROVAL_REQUIRED`; no customer decision or
  execution was recorded. Prior failed runs remain immutable evidence.

## Research / references used

- `apps/api/src/davdeploy/nova_plan_codebuild.py` — fixed CodeBuild runner and
  fail-closed entry point.
- `apps/api/src/davdeploy/service.py` — durable run reconciliation and safe
  status payload.
- `tests/test_nova_plan_codebuild.py` and `tests/test_nova_plan_runs.py` —
  runner and hosted status behavior.
- `docs/test/test565.md` — sanitized evidence for the v26 hosted run.

## Work planned for the PR

1. Add stable internal codes for the runner's known fixed failure messages.
2. Print only the code and a constant prefix when a known runner error occurs;
   use one generic code for unexpected exceptions.
3. Test known and unknown exceptions, proving their messages and arbitrary
   input are never written to the output.
4. Preserve all result, policy, approval, retry, and plan-only boundaries.
5. Deploy only through the protected saved-plan workflow. Create a fresh
   review-only revision and one plan-only run after deployment, then use the
   safe code to select the next dependency-ready fix.

## Acceptance criteria

- [x] Known runner failures emit an allowlisted stable code without exception
  text.
- [x] Unexpected failures emit one generic code without exception text.
- [x] Tests cover code mapping and output redaction.
- [x] Full required verification and documentation checks pass.
- [ ] Final-head CI passes and review has no unresolved findings.
- [ ] The merged version is deployed via the exact protected saved plan, and a
  fresh hosted plan-only run records a safe, actionable outcome.
- [ ] No customer workload is approved, applied, destroyed, or certified by
  this PR.

## Acceptance status

- [x] Allowlisted codes cover the runner's fixed known failures.
- [x] Unknown exception text is never emitted.
- [x] Focused and full verification pass.
- [ ] Final-head CI and review pass.
- [ ] A fresh deployed hosted plan-only run yields a safe outcome.

## Tests / validation performed

- The baseline failure was inspected through the authenticated status API,
  CodeBuild phase metadata, and bounded CloudWatch log classification. No raw
  proposal, saved plan, state, or exception text was retrieved.
- `PYTHONPATH=apps/api/src /Users/adewale/Projects/davdeploy/.venv/bin/python -m pytest tests/test_nova_plan_codebuild.py -q` — 28 passed.
- `PYTHONPATH=apps/api/src make verify PY=/Users/adewale/Projects/davdeploy/.venv/bin/python` — 2,100 passed; Ruff, Actions configuration, OpenAPI snapshot, and Compose checks passed. One existing Starlette/httpx deprecation warning remains.
- `GITHUB_PR_NUMBER=565 python3 scripts/check_doc_conventions.py` and `git diff --check` — passed.

## Evidence files produced

- `docs/test/test565.md` — sanitized real hosted plan-only baseline.
- This ticket — scope, acceptance status, boundaries, and follow-up.

## Boundaries and follow-up

No auth, policy, IAM, state, approval, retry, or Terraform behavior changes are
in scope. Do not retry run `5a917d8b-93ba-4a85-8d7e-258e0b753ebe`; it is
terminal. Any diagnostic that cannot be matched to a fixed code remains
generic. After a new run identifies the first concrete blocker, implement that
fix through its own evidence-backed PR.

## Boundaries

Do not log exception strings, model input/output, credentials, Terraform plan
values, state, object keys, or signed URLs. Do not change policy, IAM,
authorization, approval, retry, or execution behavior. Never mark a CodeBuild
failure successful based on a diagnostic code.

## Follow-up work

Use the safe runner code from the next fresh v26 hosted plan-only run to select
the first concrete blocker. Continue the hosted application path only after a
reviewable saved plan passes the exact account, ownership, pricing, and policy
checks.
