# ticket374 — deny unbound Secrets Manager value reads

PR: [#374](https://github.com/Bepoadewale/davdeploy/pull/374) (draft)  
Branch: `security/deny-unbound-secret-reads-374`

## Problem / goal

The actual generated-plan IAM check validates role escalation and broad
wildcards, but it does not reject a Lambda role policy that grants
`secretsmanager:GetSecretValue` or `BatchGetSecretValue`. The proposal contract
permits a typed RDS-managed secret ARN reference in a Lambda environment value,
but the policy checker does not bind an IAM statement's `Resource` to that
reference. A model-authored exact ARN or wildcard must not create a runtime
secret-read grant until that binding is deterministic and verified.

## Current repo state

- Backend `main` is `65ca746ebbf54b57755b8af718429fecffc7af0e`; merged-main CI
  run `43158439965` passed all seven jobs.
- PR #367 supports a bounded RDS-managed secret ARN output reference for a
  Lambda `_SECRET_ARN` environment variable. It does not resolve secret values
  or authorize runtime reads.
- The generated-plan IAM policy check currently has no dedicated
  Secrets Manager value-read deny.
- Hosted Nova planning, exact costed approval and apply remain disabled; this
  PR must not change those gates or claim a customer workload.

## Research / references used

- [AWS Secrets Manager `GetSecretValue` API](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html): retrieves the encrypted secret value and requires `secretsmanager:GetSecretValue`.
- [AWS Secrets Manager `BatchGetSecretValue` API](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_BatchGetSecretValue.html): retrieves secret values in batches and requires both batch and per-secret get permissions.
- [AWS Secrets Manager Service Authorization Reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_secretsmanager.html): authoritative action/resource mapping for the retrieval APIs.
- `apps/api/src/davdeploy/generated_plan_policy.py` and
  `tests/test_generated_plan_policy.py`.

## Work planned for the PR

- Reject IAM allow-action patterns that match Secrets Manager value-retrieval
  actions, including exact actions and wildcards, regardless of ARN scope.
- Preserve safe metadata reads such as `DescribeSecret`.
- Add positive and negative cases for exact, batched, service-wildcard and
  action-wildcard secret access.
- Update the Nova backlog to record this fail-closed runtime-permission gate
  and its future typed-binding follow-up.

## Acceptance criteria

- [x] Secret value read actions and wildcard patterns that include them are
  denied by actual-plan policy.
- [x] Metadata-only `DescribeSecret` remains eligible for human review.
- [x] No policy values, secret values, or raw plan payloads enter findings.
- [x] Focused tests and full `make verify` pass.
- [x] Isolated clean-room proof passes.
- [ ] Documentation conventions, current-head review and final-head CI pass.
- [x] No AWS role, customer plan, approval, apply, or workload is changed.

## Acceptance status

- [x] Implementation and focused/full tests complete.
- [x] Clean-room proof passes.
- [ ] Documentation, review and final-head CI pass.
- [x] No runtime/AWS/customer workload mutation is in scope or performed.

## Tests / validation performed

Focused policy tests passed (149). `make verify` passed (1,044 tests, Ruff,
Actions configuration, OpenAPI snapshot and Compose config). Full isolated
clean-room proof passed from `58bd8d4`; all project containers are stopped.
The external virtual environment, worktree, bind-mounted Postgres data, network
and images are retained. No named volume or AWS resources were created.
Documentation checks pass; final-head review and CI remain pending.

## Evidence files produced

- `docs/tickets/ticket374.md`
- `docs/test/test374.md`

## Boundaries

This intentionally leaves runtime secret retrieval unavailable until a future
change binds each generated application permission to a trusted, exact secret
reference and its owner. It does not change the proposal contract, plan
approval, Nova execution flags, role templates, or AWS resources.

## Follow-up work

Implement a restricted representation for runtime secret-read policy that can
bind an IAM role permission to an owned RDS-managed secret output without
allowing model-authored policy JSON to select an arbitrary secret.
