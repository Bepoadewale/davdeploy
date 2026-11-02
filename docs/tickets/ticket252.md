# ticket252 — Real AWS Batch workload certification

PR: [#252](https://github.com/Bepoadewale/davdeploy/pull/252)

Branch: `test/real-batch-workload`

## Problem / goal

Prove that a disposable Fargate AWS Batch workload can start, write its
CloudWatch execution log, finish successfully and be removed cleanly.

## Current repo state

The initial real submission reached Batch but failed during Fargate resource
initialisation because the task had no explicit public-network configuration
or CloudWatch log group. The failed validation environment was destroyed.

## Work planned for the PR

Add the network and logging contract required by public-subnet Fargate tasks,
then rerun the disposable job and record its observed result and teardown.

## Acceptance criteria

- [x] The submitted Batch job reaches `SUCCEEDED`.
- [x] CloudWatch receives the task output.
- [x] All resources tagged with the test ID are destroyed.

## Boundaries

This validates a minimal public-subnet Fargate Batch workload. Private-only
networking, custom images, retries and customer workload scheduling remain
separately testable deployment concerns.
