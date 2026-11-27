# test534 — Bounded Nova generation failure diagnostics

Date: 2026-11-27
Execution type: Focused local generator and hosted-run service tests
Customer repository: `Bepoadewale/fitness-backend` (synthetic acceptance input)
Commit: `f300676aa3af32a76136947c4f4870cee498b5e6` base; PR implementation pending
AWS account: `654654474502` (the referenced hosted plan-only test only)
AWS region: `us-east-1`

## Resources created

No AWS resources were created. The referenced hosted run
`0b1e4807-7532-45df-ad99-8edde41a82f4` failed before CodeBuild started and
produced no plan artifact. It did not apply or destroy resources.

## Commands executed

- `uv run --project . --extra dev pytest -q tests/test_terraform_generation.py tests/test_nova_plan_runs.py` — 65 passed.
- `uv run --project . --extra dev ruff check apps/api/src/davdeploy/terraform_generation.py apps/api/src/davdeploy/service.py tests/test_terraform_generation.py tests/test_nova_plan_runs.py` — passed.
- `git diff --check` — passed.

## Observed result

- Generator failures retain one of the fixed failure categories and at most 12
  sanitized validation code/field pairs.
- The exact generated-plan run status can include model and prompt version,
  bounded attempt/retry totals, usage, and validation diagnostics.
- Tests confirm private provider/error values and arbitrary field names do not
  enter the returned run status. No raw prompt or proposal data is persisted
  in the new diagnostic payload.
- The existing hosted run remains `FAILED` / `NOVA_GENERATION_FAILED` with no
  artifact. It cannot be retroactively diagnosed; the new behavior needs a
  post-deployment run to prove hosted visibility.

## Teardown

No AWS resources were created; no teardown was required.

## Final boundary

This is local evidence for sanitized failure reporting only. It does not prove
Nova can produce a valid Terraform proposal, that the hosted plan runner
succeeds, or that any customer workload was applied, operated, or certified.
