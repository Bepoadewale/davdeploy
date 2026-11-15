# test413 — source and hosted-state reconciliation

Date: 2026-11-15
Execution type: read-only source, GitHub, AWS control-plane identity, and HTTPS health verification; documentation-only PR
Customer repository: None
Source: backend `main` `017e53e329ff7c9be41f7a30e3c6c3451b3e4387`
AWS account: `654654474502`
AWS region: `us-east-1`

## Commands and evidence

- `gh pr list --state open --limit 20`: only PR #399 was open before this PR.
- `gh pr view 399`: draft head `1085da7faf67e10d70bfa7fa64abf1819e6ec6f9`; seven required checks passed in CI run `43702530096`. The PR remains an unwired, disabled exact-plan boundary.
- `gh pr view 411`: merged as backend main `a9c5ca127e8e93845b215c795dd6755e6683869f`.
- `gh run view 43685318088`: Terraform apply for PR #411 source completed successfully, including exact saved-plan verification and database migration steps. Matching plan run: `43664906950`.
- Read-only `AWS_PROFILE=ai-platform-pilot-key aws sts get-caller-identity` confirmed account `654654474502`.
- Read-only `aws lambda list-functions` / `get-function-configuration` found all six `davdeploy-*` functions with code hash `DN7QMWh1lCNtB9bK8AA0uWHRyMTEVwF7qKTmzB/JbhU=` and update time `2026-11-15T08:13Z`.
- `curl -fsS -o /tmp/davdeploy-health.txt -w 'HTTP %{http_code}\\n' https://api.davdeploy.tech/healthz` returned HTTP 200 and `{"status":"ok","product":"davdeploy"}`.
- `gh run list --workflow 'Terraform apply'` and `gh run list --workflow 'Terraform plan'`: latest runs completed successfully; no active Terraform run was listed.

## Result and limits

The source snapshot is PR #412, while the hosted package is PR #411. This confirms
control-plane version and availability only. It does not confirm pricing for
PR #412 is deployed, an authenticated customer plan has run, or any Nova
customer workload has been applied, operated, observed, recovered, or destroyed.
No AWS resources were created or changed during this reconciliation.
