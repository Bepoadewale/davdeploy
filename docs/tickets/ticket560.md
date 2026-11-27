# ticket560 — give Nova precise Lambda health-target repair guidance

PR: [#560](https://github.com/Bepoadewale/davdeploy/pull/560) (draft)

Branch: `fix/nova-lambda-health-feedback-560`

## Problem / goal

The deployed v21 hosted plan-only generation failed because Nova proposed a
`container_readiness` assertion targeting an `aws_lambda_function`. The
contract correctly rejects this pair, but existing feedback lists every
allowed target without explaining which assertion can check the Lambda
application's actual behavior. Add fixed, pair-specific guidance that helps
Nova repair a compatible assertion without changing architecture or weakening
the original health requirement.

## Current repo state

- Backend `main`: `fe02d62f123e27712fee686db05029de8b7a33af` (PR #559 merged).
- Hosted plan-only run `d61e0c32-0379-4bd2-a240-a7924f4e98a1` is terminally
  `FAILED` with prompt `terraform-nova2-contract-v21`, two attempts and one
  repair. Its safe feedback identifies `container_readiness`, the canonical
  target field, and `aws_lambda_function`; it has no artifact.
- No Terraform operation is active. No customer approval, apply, or destroy
  occurred. The authenticated workspace-admin CLI session remains available.

## Research / references used

- `generated_deployment_contract.py` owns the assertion-to-resource-type map.
- `terraform_generation.py` owns fixed prompt text, bounded repair, and the
  allowlisted sanitizer for `IncompatibleHealthTargetError`.
- `test557.md` through `test559.md` record preceding hosted generation
  blockers; this package must preserve those failures and evidence.

## Work planned for the PR

1. Add a fixed instruction for `container_readiness` targeting Lambda. A
   declared, correctly wired API Gateway stage may instead receive an
   `http_response` assertion for the same HTTP health requirement. A declared
   SQS-to-Lambda binding may use `event_processing` for the queue behavior.
2. If the proposal graph does not contain a compatible path, tell Nova to
   report the limitation. Do not invent/add a service, drop a requirement,
   or mislabel Lambda as a container.
3. Use the same fixed guidance in the trusted prompt and sanitized repair
   feedback, bump the prompt version, and add redaction and bounded-repair tests.
4. Reconcile the ledger and evidence, run required verification and clean-room
   proof, and continue through PR review/deployment to one fresh plan-only run.

## Acceptance criteria

- [x] Lambda `container_readiness` feedback contains precise, fixed guidance;
  other incompatible pairs retain the general typed compatibility guidance.
- [x] A bounded repair can select an already-declared compatible health target
  without removing a health requirement or changing trusted context.
- [x] If no declared compatible path exists, guidance requires an honest
  limitation rather than a new architecture or weakened assertion.
- [x] Feedback contains no raw resource ID, proposal value, rationale, or
  untrusted validator/model text.
- [x] Focused tests, full verification, Ruff, Actions configuration, OpenAPI,
  Compose, documentation conventions, and diff checks pass locally.
- [ ] Required isolated clean-room proof, PR review, and all CI checks pass.
- [ ] After protected control-plane deployment, one fresh review-only hosted
  generation reaches an inspectable plan or a precise next blocker. No
  customer-workload approval, apply, or destroy occurs.

## Evidence and boundaries

The v21 failure is recorded in `docs/test/test560.md`. This PR must not change
policy, execution roles, apply gates, tenant controls, or infrastructure
resources. A successful proposal or plan is not application-health or
lifecycle evidence.

## Acceptance status

The pair-specific prompt and feedback, bounded repair/fail-closed tests, full
verification, documentation checks, and hosted v21 baseline evidence are
complete. Isolated clean-room proof, PR review/CI, protected control-plane
deployment, and the next fresh hosted plan-only outcome remain open.

## Tests / evidence files

- `docs/tickets/ticket560.md`
- `docs/test/test560.md`

## Evidence files produced

- `docs/tickets/ticket560.md`
- `docs/test/test560.md`

## Boundaries

No customer approval, workload apply/destroy, control-plane setting expansion,
policy weakening, tenant-control change, or infrastructure-resource change.
Preserve secrets, raw proposals, plans, state, and all prior failure evidence.

## Tests / validation performed

- `pytest -q tests/test_terraform_generation.py tests/test_generated_deployment_contract.py tests/test_customer_plan_review.py tests/test_nova_plan_runs.py` — 202 passed.
- `make VENV=/Users/adewale/Projects/davdeploy/.venv-pr399 verify` — 2,090 passed, Ruff passed, Actions configuration passed, OpenAPI snapshot matched, and Compose config passed.
- Direct Ruff check, documentation convention check, and `git diff --check` passed.
- Clean-room, PR CI/review, protected deployment, and fresh hosted plan-only result remain pending.

## Follow-up work

Use the next hosted result to address the earliest remaining validator, pricing,
plan-policy, state, or execution blocker. Preserve all prior failed run records.
