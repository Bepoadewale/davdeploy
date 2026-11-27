# test543 — Nova resource validation feedback

Date: 2026-11-27
Execution type: Hosted plan-only generation failure (no Terraform plan or AWS workload)
Customer repository: `Bepoadewale/fitness-backend` (synthetic acceptance project)
Commit: control-plane prompt-v7 release based on `0292907e4c3b10287c753a010fba9982a7e677c9`
AWS account: `654654474502` (verified test connection; no workload operation)
AWS region: `us-east-1`

## Resources created

None. Generation failed before CodeBuild, saved-plan creation, or AWS execution.

## Commands executed

- Authenticated `POST /api/v1/intents` for the synthetic API application with
  private file storage, relational database reads/writes, and async jobs.
- Authenticated `POST /api/v1/intents/{intent_id}/plans`, created a review-only
  revision, submitted it, and queued generated-plan run
  `137ab46f-f5ee-4fa8-80cf-363ffc5f2736`.
- Retrieved only the generated run's safe status and diagnostics.
- Authenticated retry of the older prompt-v6 run returned HTTP 409; that run
  remains failed and was not requeued.

## Observed result

The prompt-v7 run failed as `NOVA_GENERATION_FAILED` after two model attempts
and one repair. Diagnostics reported two `value_error` entries at
`resources[*]`; the safe API omitted validator messages and raw proposal text.
Usage was 11,459 input tokens, 3,907 output tokens, 14,713 ms, with estimated
cost unavailable. No CodeBuild build or plan artifact exists.

The corrected submitted intent has `file_storage`, `relational_data`, and
`jobs` capability requirements, is stateful and event-driven, and has no
unanswered questions. Its architecture still reports fixture pricing and a
resource breakdown limited to the API base; this is not live pricing or proof
that the application behaviors were planned.

## Teardown

Not applicable. No AWS resources, Terraform workspaces, builds, or plan
artifacts were created. Review and run records remain as audit evidence.

## Final boundary

This is hosted generation failure evidence only. It does not establish a valid
saved plan, customer approval, apply, application behavior, lifecycle, or
certification. The control plane remains healthy and the workload remains
unapproved and unapplied.

## PR #543 local verification

- Focused suite: 101 passed (`test_terraform_generation.py`,
  `test_nova_plan_runs.py`, `test_customer_plan_review.py`).
- Ruff, documentation convention checks, and `git diff --check`: passed.
- One pre-existing Starlette deprecation warning was reported by the test
  environment.
- GitHub Actions run `45953221246` passed all seven required checks for head
  `afc97c77482c1d4d526b932125e30bc3de03bfcf`.
- The post-deployment plan-only retry remains pending.
