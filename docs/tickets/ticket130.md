# Ticket 130: Live customer cloud pilot evidence

## Goal

Record one governed, customer-style AWS workload lifecycle using DavDeploy's public API contracts: cloud connection verification, plan review, approved apply, observation, governed destroy, and absence verification.

## Current state

The customer cloud connection is verified. An App Runner Terraform plan was rendered, preflighted, approved, and executed as a plan-only CodeBuild run. Its encrypted, checksum-bound plan artifact is stored in the control-plane state bucket.

## Work

- Reconcile the completed authenticated plan artifact through the event-driven worker.
- Start an apply only after that review is recorded.
- Record actual output ingestion and observed state.
- Produce, review, and execute a separately saved destroy plan.
- Verify workload-resource absence while retaining the customer connection.

## Acceptance criteria

- [ ] Plan-only artifact is attached to the approved revision.
- [ ] Apply uses the saved, reviewed plan artifact.
- [ ] Outputs and observed state are recorded from the real run.
- [ ] Destroy uses its own reviewed saved destroy plan.
- [ ] Absence verification succeeds.
- [ ] `docs/test/test130.md` contains the complete real-AWS evidence without secrets.

## Boundaries

No customer credentials, external IDs, access keys, or unreviewed Terraform applies are recorded or used. This pilot uses a scoped customer-style role in the account designated by the connection.

## Validation and references

The API, worker, CodeBuild runner, and Terraform controls are defined by the merged control-plane PRs through #129. This ticket is updated with the exact evidence and outcome before review.

