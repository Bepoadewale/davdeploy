# test567 — Hosted v27 HTTP health target failure

Date: 2026-11-28

Execution type: Hosted AWS plan-only generation; no workload apply.

Customer repository: Synthetic Nova validation repository associated with the
source architecture plan; repository contents were not retrieved.

Repository: `Bepoadewale/davdeploy`

Commit: PR #566 merge `5f37cc964d0a8da64bd474629a872bde9943f701` (deployed
baseline before this PR).

AWS account: `654654474502`

AWS region: `us-east-1`

## Resources created

None. The request failed during bounded Nova proposal generation before
CodeBuild, Terraform planning, or workload creation.

## Commands executed

- Authenticated CLI: verify `/api/v1/me`, inspect the verified same-account
  connection and unapproved source architecture, create and submit one fresh
  same-digest review-only revision, and request one v27 plan-only run.
- Authenticated read-only CLI: inspect only the run's allowlisted generation
  diagnostics. No proposal, saved-plan value, Terraform state, or signed URL
  was retrieved.
- GitHub: verify protected plan `46150039182` and exact saved-plan apply
  `46150593146` for the deployed PR #566 merge commit.
- AWS read-only checks: verify caller account, migration run outcome, six
  Lambda package hashes and status, and the API health endpoint.

## Observed result

### Hosted v27 baseline

- Architecture plan: `539f558d-16cf-4359-921a-9205a7e81bfe`, profile
  `aws-lambda-api`; components include Lambda and API Gateway.
- Source architecture plan remains unapproved (`APPROVAL_REQUIRED`, no
  decision); connection `3964addb-9f00-4c87-b829-2c3cd3b0b48c` is
  `VERIFIED` with plan role `PROFILE_VERIFIED` for account
  `654654474502`.
- Review-only revision `4fd24a64-2bca-4ecc-a217-5d0e5d13e02e` has the
  established digest
  `fb7384977baea8ff63b83d19be71ff5e0fcd54d45b19466a4f79a9722779cd4e`, state
  `SUBMITTED`, no decision, and execution `UNEXECUTED_APPROVAL_ONLY`.
- One plan-only run `b12a8f36-08f7-4184-8aaf-859eed337a2e` reached terminal
  state `FAILED`, error `NOVA_GENERATION_FAILED` / `proposal_invalid`, prompt
  `terraform-nova2-contract-v27`, two attempts, two retries, 21,724 input
  tokens, 8,516 output tokens, 30,777 ms, and estimated cost unavailable.
- Sanitized feedback: `value_error` at
  `health_assertions[*].target_resource_id`, issue
  `incompatible_health_target`; assertion kind `http_response`; observed
  target type `aws_lambda_function`. It returned fixed allowed target types
  and did not expose raw proposal values.
- No CodeBuild build, provider plan, or artifact was produced. No workload
  resources were created. No customer plan was approved, applied, or destroyed.

### Control-plane release verification

The PR #566 exact saved-plan apply `46150593146` succeeded for the merge SHA.
Database migrations completed. All six control-plane Lambda functions are
Active/Successful and their package hash matches the versioned exact-commit
release ZIP. `https://api.davdeploy.tech/healthz` returned HTTP 200. The
authenticated CLI verified workspace role `administrator`.

## Local implementation verification

- Focused generation, customer-review, and generated-plan-run suites:
  152 passed.
- Full `make verify`: 2,105 passed; Ruff, Actions configuration, OpenAPI
  snapshot, and `docker compose config --quiet` passed. The Compose command
  parsed configuration only; it did not start containers.
- Documentation conventions and `git diff --check` passed.

## Teardown

No workload resources were created; no workload teardown was needed. The
failed run and submitted review are retained as audit evidence.

## Final boundary

The v27 result is a generation failure, not Terraform plan evidence. It does
not prove that the API integration is deployable, that health was observed, or
that any workload lifecycle succeeded. No customer workload was approved,
applied, destroyed, or certified.

## Next hosted check

After PR #567 merges and its exact control-plane release is deployed, use a
fresh submitted revision with the same digest and one v28 plan-only request.
Keep the revision unapproved. Inspect only allowlisted diagnostics or a
value-free saved-plan summary. Do not approve, apply, destroy, or certify a
customer workload.

## Limits

The v27 result is a generation failure, not Terraform plan evidence. It does
not prove the HTTP API integration is deployable, health was observed, or any
workload lifecycle succeeded.
