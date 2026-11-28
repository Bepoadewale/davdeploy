# test568 — Nova SQS-to-Lambda event binding feedback

Date: 2026-11-28

Execution type: Real hosted AWS plan-only generation failure; no customer
workload apply was attempted.

Repository: `Bepoadewale/davdeploy`

Customer repository: Synthetic Nova validation workspace repository; source
contents were not retrieved.

Deployed baseline: PR #567 merge `909aba72f49eb5840752380b1dab6414f37b53ef`.

Commit: deployed baseline `909aba72f49eb5840752380b1dab6414f37b53ef`.

PR implementation commit: `8a38f3e8`.

AWS account: `654654474502`

AWS region: `us-east-1`

## Hosted v28 baseline

- Architecture plan `539f558d-16cf-4359-921a-9205a7e81bfe` remains
  `APPROVAL_REQUIRED`; no decision was recorded.
- Fresh review revision `d240f694-ac90-450d-87b6-181c28aea49c` retains the
  established content digest, is `SUBMITTED`, has `decision=null`, and remains
  `UNEXECUTED_APPROVAL_ONLY`.
- One v28 plan-only run `86ccf87c-de06-4287-a1b2-b78fb0a0a77d` failed
  terminally as `NOVA_GENERATION_FAILED` / `proposal_invalid` after two
  attempts and one repair. Prompt: `terraform-nova2-contract-v28`; input
  tokens 14,168; output tokens 5,422; latency 19,132 ms; estimated cost
  unavailable.
- Sanitized feedback is `missing_event_binding` and states that an
  `aws_lambda_event_source_mapping` must reference both the source SQS queue
  and target Lambda. No raw proposal or saved-plan value was retrieved.
- No CodeBuild build, Terraform plan, artifact, or customer workload resource
  was produced. No approval, apply, destroy, or certification occurred.

## Commands executed

- Authenticated CLI read-only checks confirmed the workspace administrator,
  existing revision digest/state, and verified same-account connection.
- Authenticated CLI created and submitted one fresh review-only revision; one
  generated-plan API request was issued with that revision's exact digest.
- Read-only generated-plan status inspection returned only safe diagnostics.
- Protected plan/apply and release package verification for PR #567 merge are
  recorded in the private goal ledger; package bytes were streamed for hashing
  and not saved locally.

## Observed result

The v28 request was rejected by the strict generated proposal contract because
the event-processing assertion had no same-plan SQS-to-Lambda binding. This is
an actionable generation failure, not a saved-plan result.

## Resources created

No customer workload resources were created. The plan-only CodeBuild attempt
ended during generation before Terraform planning.

## Follow-up result

## Local implementation verification

- Prompt version changed to `terraform-nova2-contract-v29`; the validator and
  policy were not changed.
- Focused generation, customer-review, and generated-plan-run tests:
  154 passed.
- Full `make verify`: 2,107 passed; Ruff, Actions configuration, OpenAPI
  snapshot, and `docker compose config --quiet` passed.
- One regression confirms the exact typed references for
  `event_source_arn` and `function_name` repair the existing queued-work
  assertion while preserving trusted context. A second confirms the missing
  binding still fails after two bounded attempts with only fixed feedback.
- Documentation conventions and `git diff --check` passed.
- Required clean-room cycle passed in detached worktree
  `/private/tmp/davdeploy-nova-event-binding-568-clean` at `8a38f3e8`, using
  Compose project `davdeploy-nova-pr568-clean`: clean-local, bootstrap-local,
  smoke, simple/complex/degraded/Day-2 demos, policy failure, readiness failure,
  API contract, customer-plan E2E, fixture seed, trace check, full verify
  (2,107 tests), and clean-local. Fixture seed explicitly reported no AWS,
  authenticated Terraform, Kubernetes, or GitOps execution.
- Cleanup verification confirmed no matching containers or Postgres volume,
  and no clean-room `.venv` or `.local`. Root protected `--only-show-errors`
  and `.venv-pr399/` remained present.
- PR CI run `46157074424` passed all seven checks on implementation commit
  `8a38f3e8`; the evidence update requires a fresh final-head run.
- Protected deployment and one hosted v29 plan-only check remain pending.

## Follow-up result

No v29 hosted result exists yet.

## Teardown

No customer workload resources were created, so there was nothing to tear
down. Retain the failed run and review revision as audit evidence.

## Final boundary

This failure is not a Terraform plan or application lifecycle result. It proves
that the deployed proposal-generation contract still needs a concrete typed
event binding example. No customer workload is applied or certified.
