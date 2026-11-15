# test413 — source and hosted-state reconciliation

Date: 2026-11-15
Execution type: read-only source, GitHub, AWS control-plane identity, and HTTPS health verification; documentation-only PR
Customer repository: None
Commit: implementation `ce7d0f375771cac408e411e93fb69144632468a5`; final evidence follow-up commit follows
AWS account: `654654474502`
AWS region: `us-east-1`

## Commands executed

- `gh pr list --state open --limit 20`: only PR #399 was open before this PR.
- `gh pr view 399`: draft head `1085da7faf67e10d70bfa7fa64abf1819e6ec6f9`; seven required checks passed in CI run `43702530096`. The PR remains an unwired, disabled exact-plan boundary.
- `gh pr view 411`: merged as backend main `a9c5ca127e8e93845b215c795dd6755e6683869f`.
- `gh run view 43685318088`: Terraform apply for PR #411 source completed successfully, including exact saved-plan verification and database migration steps. Matching plan run: `43664906950`.
- Read-only `AWS_PROFILE=ai-platform-pilot-key aws sts get-caller-identity` confirmed account `654654474502`.
- Read-only `aws lambda list-functions` / `get-function-configuration` found all six `davdeploy-*` functions with code hash `DN7QMWh1lCNtB9bK8AA0uWHRyMTEVwF7qKTmzB/JbhU=` and update time `2026-11-15T08:13Z`.
- `curl -fsS https://api.davdeploy.tech/healthz` returned HTTP 200 and `{"status":"ok","product":"davdeploy"}`.
- `gh run list --workflow 'Terraform apply'` and `gh run list --workflow 'Terraform plan'`: latest runs completed successfully; no active Terraform run was listed.
- `.venv/bin/python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- Inventory comparison script — all 26 architecture IDs and all 30 root IDs
  match their respective acceptance crosswalks exactly.
- GitHub Actions run [43766999267](https://github.com/Bepoadewale/davdeploy/actions/runs/43766999267)
  passed `docs-conventions`, `python`, `secrets`, `policy`,
  `cloud-contracts`, `supply-chain`, and `local-e2e` on PR head
  `d2caf0ea69861dde735607b67338b7eb3438925f`. A final-head run is required
  after this evidence update.
- GitHub Actions run [43767479485](https://github.com/Bepoadewale/davdeploy/actions/runs/43767479485)
  passed all seven required checks on PR head
  `4af292aa017e3f664900268dc81cd392c4b221eb`, which contains the complete
  matrix, status, ticket, and reconciliation evidence. The PR status rollup
  remains the authority for its final evidence-only commit.

## Resources created

None. All AWS calls were read-only control-plane queries; no customer resources or local application stack were created.

## Teardown

Not applicable. No resource was created, and no local or cloud resource was deleted.

## Observed result

The source snapshot is PR #412, while the hosted package is PR #411. This confirms
control-plane version and availability only. It does not confirm pricing for
PR #412 is deployed, an authenticated customer plan has run, or any Nova
customer workload has been applied, operated, observed, recovered, or destroyed.
No AWS resources were created or changed during this reconciliation.

## Limitations

The Lambda package identity and `/healthz` result establish the hosted control
plane release only. They are not customer plan, workload, health, recovery,
cleanup, or pricing evidence.

## Final boundary

This documentation update neither enables apply nor advances any capability's
execution status. Customer execution and lifecycle remain unproven.
