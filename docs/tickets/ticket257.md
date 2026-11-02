# ticket257 — Real EventBridge to SQS workload certification

PR: Pending creation.

Branch: `test/real-event-delivery-workload`

## Problem / goal

Prove an application event crosses EventBridge and reaches an encrypted SQS
queue, rather than proving independent resources exist.

## Current repo state

The validation root creates a bus and queue but has no delivery target.

## Research / references used

Amazon EventBridge SQS target and resource-policy guidance.

## Work planned for the PR

Add an exact-source event rule and scoped queue policy, send one test event,
receive it from SQS, and remove all temporary resources.

## Acceptance criteria

- [ ] A submitted EventBridge event arrives in the queue.
- [ ] All test resources are destroyed.

## Acceptance status

In progress.

## Tests / validation performed

Pending controlled AWS execution.

## Evidence files produced

`docs/test/test257.md`

## Boundaries

This tests delivery, not an application consumer or replay policy.

## Follow-up work

Certify a consumer, DLQ transition and retry behaviour.
