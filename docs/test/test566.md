# test566 — Hosted Nova plan-profile rejection and repair follow-up

Date: 2026-11-28

Execution type: Real hosted AWS plan-only run; no customer workload apply was attempted.

Customer repository: Synthetic Nova validation repository in the authenticated workspace.

Commit: `82fcd604ec3ed2e7272bc411bae903e8ca4bdfc9` (deployed baseline before PR #566).

AWS account: `654654474502`

AWS region: `us-east-1`

## Resources created

None. The hosted request failed before producing a saved Terraform plan. No
customer workload resources were created.

## Commands executed

- Authenticated hosted CLI/API: submit a fresh unapproved review-only revision
  and request one plan-only run using the exact revision digest.
- AWS CodeBuild read-only inspection: retrieve the build status, configured
  versioned package reference, and the fixed allowlisted failure code.

## Observed result

This PR moves the fixed customer plan access-profile check into the existing
bounded Nova proposal-repair loop. CodeBuild keeps its independent copy of the
same policy check before it assumes the customer plan role.

- AWS account: `654654474502`; region: `us-east-1`.
- Backend main before this PR: `82fcd604ec3ed2e7272bc411bae903e8ca4bdfc9` (PR #565).
- Review-only revision: `7c66aac5-50f1-4d74-bee2-1341ddc86bc9`; its content
  digest matched the established synthetic architecture. It had no approval.
- Plan-only run: `33afa2d7-9ce3-402e-86fc-e0cbd134c958`; terminal state
  `FAILED`, API code `CODEBUILD_FAILED`.
- CodeBuild build: `davdeploy-nova-plan-only:ca70f7f7-8b94-465b-a16e-8b16e9d602a8`.
  It used the versioned release package for exact commit `82fcd604...` and logged
  fixed code `PLAN_PERMISSION_PROFILE_DENIED`.
- No saved-plan artifact was produced. The proposal and its values were not
  retrieved into this evidence. No Terraform apply/destroy or customer workload
  mutation was requested. No workload is claimed as applied or certified.

## Local verification

- Focused generation, access-profile, plan-run and customer-review suites:
  181 passed.
- Full `make verify`: 2,103 passed; Ruff, Actions configuration, OpenAPI
  snapshot, and `docker compose config --quiet` passed. This only validated the
  Compose file; no local application containers were started.
- Documentation conventions and `git diff --check` passed.
- Final-head CI passed all seven checks; post-deployment v27 hosted plan-only
  verification remains pending.

## Teardown

No customer workload resources existed to remove. The failed plan-only run is
retained as audit evidence.

## Final boundary

No customer plan was approved, applied, destroyed, or certified. A successful
saved plan and full hosted lifecycle evidence remain unmet acceptance gates.

## Interpretation and limits

The hosted failure confirms that generated proposals can still reach CodeBuild
before the fixed profile rejects them. The exact, fixed failure code does not
identify a safe repair category. PR #566 adds bounded pre-staging feedback, but
this local fixture evidence does not prove Nova can correct the real hosted
proposal or that a valid saved plan will be produced. No customer approval,
apply, health, update, recovery, destroy, or absence verification is claimed.

## Required follow-up

After PR #566 merges and its exact commit is deployed through the protected
saved-plan release, create a fresh unapproved review-only revision with the same
trusted architecture digest and request one plan-only run. Inspect only the
sanitized status/diagnostics and value-free saved-plan summary. Do not approve,
apply, or destroy the synthetic customer workload as part of this evidence.

PR #566's final-head CI run `46132450063` passed all seven checks. Automated
review requires the full local clean-room cycle (`make local-proof` followed by
`make clean-local`) before merge. It has not run. In an isolated Compose project
`davdeploy-nova-pr566`, cleanup would remove the generated PR-worktree paths
`.venv` and `.local` and the dedicated volume
`davdeploy-nova-pr566-davdeploy-postgres`. No containers are currently running.
