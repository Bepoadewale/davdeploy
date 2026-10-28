# ticket190 — Beta readiness operations and GitHub webhook hardening

PR: pending
Branch: `chore/beta-readiness-hardening`

## Problem / goal

Make the current hosted beta boundary reproducible: record the read-only DLQ assessment, provide
operations handoffs, reconcile stale status claims, and harden the local GitHub webhook contract.

## Current repo state

The DLQ root cause had a narrow compatibility fix, but the repository lacked a current clear-state
assessment and a consolidated incident/recovery/support procedure. The webhook contract did not
bound body size.

## Research / references used

Read-only AWS SQS, CloudWatch alarm, Lambda configuration, repository test, and GitHub webhook
contract evidence.

## Work planned for the PR

Record the non-mutating operational assessment, add runbooks, correct identity status language,
and reject oversized webhook bodies before parsing.

## Acceptance criteria

- [x] No SQS message is received, replayed, deleted, or changed during investigation.
- [x] DLQ, worker queue, alarms, and deployed provider configuration are recorded.
- [x] Webhook metadata and body-size rejection are covered by endpoint tests.
- [x] Incident, recovery, and support handoffs preserve the product authority boundary.

## Acceptance status

Local validation passed. CI, review, merge, and the normal hosted-control-plane deployment gate
remain pending.

## Tests / validation performed

Recorded in `docs/test/test190.md`.

## Evidence files produced

- `docs/test/test190.md`
- `docs/OPERATIONS_READINESS.md`

## Boundaries

No public webhook is enabled. No queue message, customer workload, cloud role, or customer data is
changed.

## Follow-up work

Record a separately approved human browser acceptance journey, then conduct a separately approved
recovery drill and any future queue recovery.
