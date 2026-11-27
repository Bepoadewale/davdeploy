# test552 — Nova v15 health payload diagnosis and v16 feedback fix

- Date: 2026-11-27
- Execution type: authenticated hosted Nova plan-only generation, local
  synthetic contract reproduction and local v16 validation; no CodeBuild plan
  or customer workload
- Repository: `Bepoadewale/davdeploy`
- Commit: v15 deployed control-plane code
  `6f6a1c1e42645327b5ce30006d1f8be39179561f`; v16 PR code `PENDING`
- Pull request: [#552](https://github.com/Bepoadewale/davdeploy/pull/552) (draft)
- AWS account: `654654474502` (control-plane release only)
- AWS region: `us-east-1`
- Customer repository: `Bepoadewale/fitness-backend` (synthetic acceptance case)
- Review revision: `6b542c95-d3c6-4b48-909e-293b4effeff1`
- Content digest: `fb7384977baea8ff63b83d19be71ff5e0fcd54d45b19466a4f79a9722779cd4e`
- Hosted generated-plan run: `7f3eeb66-d8ba-4dae-a097-e1d68ca9fd8e`

## Resources created

- The v15 control-plane release updated six existing Lambda packages and two
  in-place Terraform resources; it added and destroyed zero resources. Exact
  saved-plan apply run `46017348420` completed and database migrations passed.
- The hosted plan-only Nova run created no CodeBuild build, saved plan, or AWS
  customer workload resources. Review and run metadata remain as audit evidence.
- The fresh review revision is `SUBMITTED` and has no approval decision.
- Local v16 tests created no AWS resources.

## Commands executed

- PR #551 merged as `6f6a1c1e42645327b5ce30006d1f8be39179561f`; merged-main CI
  run `46015275549` passed all seven required checks.
- Protected plan `46016249082` and exact saved-plan apply `46017348420` succeeded
  for the merge commit. The six Lambda `CodeSha256` values matched the exact
  versioned release ZIP. `/healthz` returned HTTP 200 and authenticated
  `/api/v1/me` verified workspace administrator role.
- Verified the earlier v14 run was terminally failed and its review revision
  remained submitted and undecided. Created and submitted a fresh review-only
  revision with the same content digest; decision remained null.
- Queued one v15 plan-only run with a fresh idempotency key. No approval or
  apply endpoint was called.
- A local synthetic Pydantic input with `storage_roundtrip` and payload size
  4097 produced validator code `less_than_equal` at
  `health_assertions[*].payload_size_bytes`. Only code and field path were
  printed; no proposal from the hosted run was retrieved.
- Local v16 validation tests cover payload sizes 0 and 4097, reject
  `payload_size_bytes` on `http_response`, and prove unknown validator details
  and submitted values are not returned. Fixed guidance names only the two
  applicable assertion kinds and their inclusive 1–4096 byte range.
- Focused tests across generation, review, and hosted run diagnostics passed:
  125 tests. Full `make verify` passed 2,055 tests plus Ruff, Actions
  configuration, OpenAPI snapshot, and Compose checks. Documentation and diff
  checks passed. PR CI and v16 deployment remain pending.

## Observed result

The v15 run `7f3eeb66-d8ba-4dae-a097-e1d68ca9fd8e` failed before CodeBuild as
`NOVA_GENERATION_FAILED` / `proposal_invalid` after two attempts and one repair.
Safe diagnostics reported prompt v15 and two `invalid` entries at
`health_assertions[*].payload_size_bytes`. Raw validator codes, values, and
proposal content were not returned. Local reproduction identified the
contract's `less_than_equal` upper-bound error for a synthetic value of 4097.

No artifact, build, Terraform plan, or customer workload was created. The v15
hosted run is terminal and must not be retried; v16 will use a fresh review
revision and one plan-only run after deployment.

## Teardown

No customer AWS workload resources were created, so no workload teardown was
needed. Review and run metadata remain as audit evidence.

## Final boundary

PR #552 adds fixed guidance for the `payload_size_bytes` contract limit and the
standard `less_than_equal` validator code. It does not change the contract or
approve/apply a workload. Even an inspectable v16 plan will not satisfy the
first hosted-plan gate unless it includes supported private storage, database
and asynchronous work, current regional pricing, and passes exact plan policy.
