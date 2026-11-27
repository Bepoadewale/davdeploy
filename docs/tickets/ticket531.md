# ticket531 — Record the authenticated Nova hosted-plan attempt

PR: #531
Branch: `docs/nova-hosted-plan-evidence-531`

## Problem / goal

The current implementation ledger predates the workspace CLI login, the
verified plan-only customer connection, and the first hosted generic plan
attempt. Record the observed results and blockers without claiming a valid
Terraform plan or customer workload.

## Current repo state

- Backend main before this documentation change is PR #530 merge
  `1270b88ac573dff4c0c569cd8d46d6dc66af0ccb`.
- PRs #528 and #530 add CLI authentication and exact-manifest artifact approval.
- The hosted plan-only role is profile-verified, but Nova generation failed
  before a saved-plan artifact was produced.

## Research / references used

- Authenticated hosted DavDeploy API results for the exact test connection,
  architecture plan, customer revision, and generated-plan run.
- AWS CloudFormation stack/resource, IAM role-tag, caller identity, and
  connection-verification results in `docs/test/test531.md`.
- `docs/IMPLEMENTATION_STATUS.md` and the current exact-plan readiness flags.

## Work planned for the PR

- Correct the current implementation snapshot.
- Preserve exact AWS and hosted run outcomes, including failure and retention.
- State the next required work and avoid claiming apply or certification.

## Acceptance criteria

- [x] Source main, runtime observation, and API health are reconciled with
  package-to-source mapping left explicitly unresolved.
- [x] Exact test connection, role stacks, architecture-plan limitations, and
  generic run failure are recorded.
- [x] No credentials, ExternalId, setup URL, plan bytes, or MFA values are
  included.
- [x] Documentation conventions and all seven required hosted CI checks pass.

## Acceptance status

- [x] Evidence is recorded without converting a failed run into success.
- [x] Required hosted CI passes (run `45921643669`; seven checks succeeded).

## Tests / validation performed

`uv run --project . python scripts/check_doc_conventions.py` and `git diff
--check` passed locally. GitHub Actions run `45921643669` passed all seven
checks: docs conventions, policy, Python, secrets, supply chain, cloud
contracts, and local end-to-end.

## Evidence files produced

- `docs/test/test531.md`
- Updated current snapshot in `docs/IMPLEMENTATION_STATUS.md`

## Boundaries

- This is documentation of one synthetic, same-account acceptance attempt.
- No workload Terraform plan, approval, apply, health check, lifecycle recovery,
  destroy, or independent workload absence proof succeeded in this attempt.
- The discovery and plan-only role stacks are retained for the next test phase.

## Follow-up work

Restore authenticated CLI API access, analyze the repository before creating a
fresh intent, correct Nova's missing private-storage/database/queue architecture,
and produce a policy- and pricing-valid saved plan before approval or apply.
