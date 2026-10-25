# ticket135: Retry migration after Aurora wake-up

PR: #135
Branch: fix/terraform-migration-wakeup-retry

## Problem / goal

Make the guarded Terraform apply workflow tolerate Aurora Serverless resuming from
auto-pause before it verifies database migrations.

## Current repo state

Terraform apply run `40011947189` applied the saved infrastructure plan, then the
migration Lambda returned Aurora's `DatabaseResumingException`. A manually retried,
idempotent migration invocation succeeded once Aurora was available.

## Research / references used

- The failed migration verification log from workflow run `40011947189`.
- The successful bounded manual migration verification after Aurora resumed.
- The existing workflow's post-apply migration contract.

## Work planned for the PR

- Retry only the post-apply migration verification up to six times.
- Wait ten seconds between unsuccessful attempts.
- Preserve a hard failure with the final migration response after the bounded retry.

## Acceptance criteria

- [x] Normal Aurora resume does not falsely mark a completed Terraform apply as failed.
- [x] The retry is bounded to at most one minute.
- [x] A real migration failure still fails the workflow and prints the final response.
- [ ] Focused validation and required CI pass.

## Acceptance status

Implementation is complete. Focused validation and GitHub CI remain pending.

## Tests / validation performed

- Pending: YAML parse, documentation conventions, diff check, and CI.

## Evidence files produced

- `docs/tickets/ticket135.md`
- Existing real customer workload evidence remains in `docs/test/test130.md`.

## Boundaries

This does not retry Terraform apply or change any customer workload action. The
workflow still fails after six unsuccessful migration attempts.

## Follow-up work

- Run the next guarded Terraform apply through this bounded verification.
- Continue the fresh customer Terraform plan, apply, observation, destroy, and
  absence-verification cycle.
