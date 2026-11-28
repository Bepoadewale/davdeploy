# test569 — Nova managed database secret repair feedback

Date: 2026-11-28

Execution type: Real hosted AWS plan-only generation failure; no customer
workload apply was attempted.

Repository: `Bepoadewale/davdeploy`

Customer repository: Synthetic Nova validation workspace repository; source
contents were not retrieved.

Deployed baseline: PR #568 merge
`53ec7c71c6738ff3e46ffbe1a1d5a81e7cf1a7d1`.

Commit: deployed baseline `53ec7c71c6738ff3e46ffbe1a1d5a81e7cf1a7d1`.

AWS account: `654654474502`

AWS region: `us-east-1`

## Hosted v29 baseline

- The source architecture plan
  `539f558d-16cf-4359-921a-9205a7e81bfe` remains `APPROVAL_REQUIRED` with no
  decision.
- Fresh revision `ec61602a-c4f9-4e2b-9f8d-e2e22f6f1c43` retained the established
  digest, is `SUBMITTED`, has `decision=null`, and remains
  `UNEXECUTED_APPROVAL_ONLY`.
- The single v29 plan-only run
  `4685348a-b260-4ce5-8fd6-3b38f09397a5` failed before a Terraform plan after
  two Nova attempts and one bounded repair. Prompt version:
  `terraform-nova2-contract-v29`; model: `us.amazon.nova-2-lite-v1:0`; input
  tokens: 14,556; output tokens: 7,211; latency: 39,960 ms; estimated cost
  unavailable.
- Sanitized feedback reported `credential_value`. Its fixed guidance requires
  an AWS-managed RDS master secret and a typed Lambda secret ARN reference.
  The model did not produce a validated proposal. Raw proposal and credential
  values were not retrieved.
- No Terraform plan artifact or customer workload resources were produced.
  No approval, apply, destroy, or certification occurred.

## PR #569 changes and validation

- Prompt v30 gives a direct credential correction sequence, supports the
  existing `aws_db_instance` and `aws_rds_cluster` contract, forbids literal
  password arguments and credential-bearing `DATABASE_URL`, and preserves the
  safe limitation path.
- A synthetic bounded repair regression confirms that a fake credential value
  is absent from repair feedback and the accepted managed-secret proposal.
- Focused suites passed (155 tests). Full `make verify` passed (2,108 tests),
  Ruff, Actions configuration, OpenAPI, and Compose syntax; documentation
  conventions and diff checks passed. CI, review, protected deployment, and one
  fresh hosted plan-only v30 result remain pending.

## Resources created

None. The hosted request stopped during Nova proposal validation before
Terraform initialization or planning. The review revision is unapproved.

## Commands executed

- Authenticated `create-customer-review` and `submit-customer-review` for the
  source architecture plan; output was limited to review ID, state, digest,
  decision, and execution boundary.
- One hosted generated-plan-run API request with the established content
  digest and a unique idempotency key.
- Read-only generated-plan-run polling at 60-second intervals; output limited
  to safe state and generation diagnostics.
- Local Terraform monitor and GitHub Terraform workflow reconciliation before
  the hosted request.

## Observed result

The request returned HTTP 202, queued, then failed as
`NOVA_GENERATION_FAILED` / `proposal_invalid` with safe `credential_value`
feedback. No CodeBuild plan artifact was produced.

## Teardown

No AWS resources or local containers were created by this hosted run; no
teardown was needed. Existing control-plane infrastructure and audit evidence
were preserved.

## Boundaries

The hosted run remains unapproved and plan-only. Do not retrieve raw Nova
proposals, plan values, Terraform state, tokens, or signed URLs. Do not apply or
destroy the synthetic workload. A valid Terraform plan would remain review
evidence only; it would not prove application behavior or lifecycle support.

## Final boundary

No customer workload was applied, operated, destroyed, or certified. The v30
attempt is pending until the PR is merged, deployed through the protected
workflow, and one fresh hosted plan-only request is examined.
