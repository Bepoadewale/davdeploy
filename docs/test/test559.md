# test559 — safe secret-reference repair diagnostics

Date: 2026-11-27

Execution type: Hosted plan-only diagnostic and local implementation in progress

Customer repository: Synthetic DavDeploy acceptance case

Commit: `28f229416d7897ec2fe48b3def83ade6b9d4bcaf` (deployed baseline)

AWS account: `654654474502` (control-plane release only)

AWS region: `us-east-1`

## Hosted v20 baseline

- PR #558 (`28f2294`) passed all seven final-head checks in run
  `46061688461`; merged-main CI passed all seven checks in run `46062708393`.
- Protected plan `46063294020` and exact saved-plan apply `46064179578`
  deployed the release. Migration completed; all six control-plane Lambdas
  matched the exact versioned package hash; `/healthz` returned HTTP 200.
- Fresh review-only revision `7dc3915c-f39b-4268-b244-a417e17c83b1` has digest
  `fb7384977baea8ff63b83d19be71ff5e0fcd54d45b19466a4f79a9722779cd4e`, state
  `SUBMITTED`, and no decision. Execution remains unexecuted.
- Plan-only run `886fcf57-a321-455c-9097-4bc90d351be4` used prompt
  `terraform-nova2-contract-v20`, made two bounded attempts, and failed with
  `NOVA_GENERATION_FAILED` / `proposal_invalid` and safe issue
  `invalid_secret_reference_location`. Its fixed guidance says secret
  references are allowed only in Lambda environment variables ending
  `_SECRET_ARN`. No Terraform artifact or customer workload was created.
- Safe final diagnostics do not retain the destination type or location
  category, so the underlying placement cannot be identified without reading
  the raw proposal. Raw proposal, saved plan, Terraform state, and credentials
  were not retrieved.

## Local implementation verification

Pending implementation and verification.

## Final boundary

This result does not establish an inspectable saved plan, complete pricing or
policy acceptance, customer approval, apply, application health, lifecycle
recovery, destroy, or independent absence.

## Resources created

No Nova customer workload resources were created. The only AWS changes are the
protected DavDeploy control-plane release recorded above.

## Commands executed

- PR #558 final-head CI watcher and merged-main CI watcher completed; all seven
  checks passed for each run.
- Protected Terraform plan and apply workflows completed for merge commit
  `28f2294`; AWS identity, Lambda package hashes, API health, and migration
  status were checked without reading credentials or customer workload state.
- Authenticated CLI requests created and submitted a fresh review-only
  revision, then queued one v20 plan-only run. Only safe status and bounded
  diagnostic fields were printed.

## Observed result

The plan-only run failed during Nova generation with the allowlisted issue
`invalid_secret_reference_location`. No artifact was recorded. The final
safe diagnostic did not identify the resource type or secret-reference
location category, so no raw proposal inspection was performed. Implementation
of this follow-up PR remains pending.

## Teardown

No customer workload resources were created, so no teardown was needed.
