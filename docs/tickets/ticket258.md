# ticket258 — Real Kinesis workload certification

PR: Pending creation.

Branch: `test/real-kinesis-workload`

## Problem / goal

Prove the Kinesis module accepts a real KMS-encrypted record and cleans up.

## Current repo state

The validation root creates an encrypted one-shard stream but had no workload
evidence.

## Research / references used

Amazon Kinesis Data Streams put-record API and existing module-validation root.

## Work planned for the PR

Create a disposable stream, write one record, record the returned shard and
sequence number, then destroy the stream.

## Acceptance criteria

- [x] An encrypted record is accepted by Kinesis.
- [x] The disposable stream is destroyed.

## Acceptance status

Complete.

## Tests / validation performed

Recorded in `docs/test/test258.md`.

## Evidence files produced

`docs/test/test258.md`

## Boundaries

This validates producer ingestion only, not a consumer or retention replay.

## Follow-up work

Certify a consumer and checkpointing path.
