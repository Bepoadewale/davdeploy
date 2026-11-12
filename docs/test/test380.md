# test380 — reconcile Nova network plan-access status

- Date: 2026-11-12
- Execution type: Documentation-only source/deployment reconciliation
- Customer repository: N/A
- Commit: `cd54e4f` (documentation reconciliation)
- AWS account: N/A; no AWS API calls made
- AWS region: N/A; no AWS API calls made

## Purpose

Record PR #379 as merged backend source while keeping its status distinct from
the deployed PR #377 control-plane package. The VPC/subnet/security-group
metadata profile and customer role template have not been deployed or
installed, and no effective customer-role permission check has been completed.

## Commands executed

- `python3 scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- No AWS, Nova, Terraform, customer API, or workload commands were run.

## Resources created

None. No source code or infrastructure was changed.

## Observed result

The status docs distinguish backend main `c3046f3` from the latest hosted
release `40439ab`, and record merged-main CI `43249113529`. They retain the
plan runner, state API, pricing, approval, apply, health, recovery, and teardown
gaps.

## Teardown

No teardown applies. No AWS or customer resources were created or changed.

## Final boundary

This PR changes repository documentation only. It does not deploy PR #379,
install a customer role, enable hosted Nova planning, or provide customer
workload evidence. Frontend PR #102 remains draft, and pricing PR #318 remains
closed/held.
