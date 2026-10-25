# ticket130 — Live customer cloud pilot evidence

PR: [#130 — docs: record live customer cloud pilot evidence](https://github.com/Bepoadewale/davdeploy/pull/130)
Branch: `docs/live-customer-pilot-evidence`

## Problem / goal

Record one governed, customer-style AWS workload lifecycle using DavDeploy's public API contracts: cloud connection verification, plan review, approved apply, observation, governed destroy, and absence verification.

## Current repo state

The original customer workspace has a verified customer-cloud connection. Its bounded runner
created the customer-sandbox foundation from an approved, checksum-bound Terraform plan
(`9187d820-c769-40dd-93ff-01b90f804fd9`) and built an immutable customer image
(`70935f5c-1f71-43fc-9d1e-561c2b47f43d`). The VPC, subnets, security group, VPC connector,
log group, and ECR repository remain intentionally present. No App Runner service has been
created and no destroy plan or destroy has run.

On 2026-10-24, the founder account authenticated successfully, but has no customer plan or
cloud-connection records. The existing customer workspace was subsequently restored with its
stored Cognito refresh session and contains the approved pilot revision and verified connection.
The GitHub App (`5159790`) is installed for `Bepoadewale` as installation `167128937`, but the
production API remains in fixture mode until the separate GitHub App runtime deployment is merged
and applied.

## Research / references used

- Cloud execution results and saved-plan objects in the protected customer state bucket.
- AWS tagged-resource, ECR, App Runner, CodeBuild, Lambda, API Gateway, Aurora, Cognito and
  Cloudflare Pages read-only checks performed on 2026-10-24.
- Merged product controls through PR #151 and the public API contract.

## Work planned for the PR

- Reconcile the completed authenticated plan artifact through the event-driven worker.
- Merge and apply the least-privilege GitHub App runtime configuration before claiming private
  repository onboarding.
- Create a fresh customer plan using live private-repository discovery and current pricing
  provenance; the existing approved revision retains fixture pricing evidence.
- Start the service-enabled apply only after a reviewed saved plan is recorded.
- Record actual service outputs and observed state.
- Produce, review, and execute a separately saved destroy plan.
- Verify workload-resource absence while retaining the customer connection.

## Acceptance criteria

- [x] Customer-sandbox foundation apply uses a saved, reviewed plan artifact.
- [x] Foundation outputs are ingested from the real run.
- [x] Existing customer tenant access is restored through a short-lived refreshed session.
- [ ] Private GitHub onboarding uses the installed, non-fixture GitHub App in production.
- [ ] Customer tenant approval workflow is revalidated against the fresh live-evidence revision.
- [ ] Service-enabled apply uses a saved, reviewed plan artifact.
- [ ] Service outputs and observed state are recorded from the real run.
- [ ] Destroy uses its own reviewed saved destroy plan.
- [ ] Absence verification succeeds.
- [ ] `docs/test/test130.md` contains the complete real-AWS evidence without secrets.

## Acceptance status

Partially complete. Foundation apply and immutable image delivery are evidenced. The customer
session and an installed GitHub App are available, but the App configuration must be deployed and
a fresh plan must replace the prior fixture-pricing evidence before service apply, observation,
and governed destroy.

## Tests / validation performed

- Read-only AWS resource and execution-artifact inspection.
- Cognito founder authentication and authenticated `/api/v1/me` request.
- Authenticated founder GitHub, customer-plan and cloud-connection API checks.
- API health and Cloudflare Pages production health checks.
- Local documentation-convention and diff validation before review.

## Evidence files produced

- `docs/test/test130.md`

## Boundaries

No customer credentials, external IDs, access keys, or unreviewed Terraform applies are recorded
or used. Destruction of the retained customer-sandbox resources requires a separate explicit
owner approval after the service smoke test.

## Follow-up work

The API, worker, CodeBuild runner, and Terraform controls are defined by merged control-plane PRs
through #151. Live account, CodeBuild, S3 artifact, API, Cognito, GitHub and Cloudflare checks are
recorded in `docs/test/test130.md`. Deploy the GitHub App runtime configuration, create the fresh
private-repository plan and execute the remaining service and destruction stages with fresh
evidence.

## Final status — 2026-10-25

The cloud lifecycle is complete. The customer-specific `AdministratorAccess` execution role,
external-ID broker trust, reviewed saved apply plan, real image delivery, service apply, output
ingestion, and direct health check all succeeded. A distinct reviewed destroy plan then destroyed
the workload and returned `DESTROYED_VERIFIED` / `confirmed_absent`; independent AWS reads verified
the VPC/ECR absence and terminal deletion states.

Private GitHub onboarding is also complete. Installation `167128937` now exposes
`Bepoadewale/davdeploy-private-pilot` and `main` through the production GitHub-App API. Project
`private-github-pilot` (`3e977ff8-3e88-4e37-a8d7-2c71d03fdaf0`) recorded bounded, read-only
manifest analysis with `EXECUTED_READ_ONLY`.

