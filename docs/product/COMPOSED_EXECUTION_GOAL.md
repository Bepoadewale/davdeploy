# Composed AWS execution goal handoff

Updated: 2026-11-11. This checklist tracks the goal in the private execution
specification. It is not a launch-readiness claim. “Implemented” means code
exists; only “AWS verified” and “deployed” records those stronger states.

## Current deployed status — 2026-11-10

Backend `main` commit `f0c6f3af36a0ab14a5dafb9a1684c41140da7eef` was deployed
by protected plan run [42902031985](https://github.com/Bepoadewale/davdeploy/actions/runs/42902031985)
and apply run [42902934302](https://github.com/Bepoadewale/davdeploy/actions/runs/42902934302).
The saved plan reported 6 additions, 8 in-place changes, and 0 destroys;
migrations passed. The deployed API returned HTTP 200 from `/healthz`; its
unauthenticated plan-history route returned HTTP 401. PRs #333 and #334 are
deployed, so exact-revision plan history is available behind authentication.
An authenticated customer history journey remains unverified. Nova plan
reviews, plan-runner readiness, role verification, and the state API remain
disabled; no state bucket is configured. No Nova-generated customer workload
has been applied, health-checked, recovered, or destroyed. Costed exact-plan
approval, customer apply, application health, recovery, teardown, and composed
certification remain incomplete.

The ordered checklist below preserves the 2026-11-04 baseline as historical
evidence. Where it says PR #303 was not deployed or describes the prior hosted
release as current, use this dated status and the readiness matrix instead.

Allowed status values: `not started`, `in progress`, `implemented`,
`locally verified`, `AWS verified`, `deployed`.

## Ordered execution checklist — historical baseline 2026-11-04

| Step | Status | Evidence and next action |
|---|---|---|
| 1. Reconcile baseline and deploy certification scaffolding | `AWS verified` | PR #270 is merged; required CI passed in run [41670185868](https://github.com/Bepoadewale/davdeploy/actions/runs/41670185868), and its typed CodeBuild dispatcher was applied in run [41671744510](https://github.com/Bepoadewale/davdeploy/actions/runs/41671744510). The latest hosted package is PR #302 commit `7d087d0`, applied by [41781326222](https://github.com/Bepoadewale/davdeploy/actions/runs/41781326222) after plan [41781048128](https://github.com/Bepoadewale/davdeploy/actions/runs/41781048128): 0 adds, 6 changes, 0 destroys; migrations passed and `/healthz` is healthy. PR #303 (`ea9de3a`) is merged and its seven checks passed in [41782907889](https://github.com/Bepoadewale/davdeploy/actions/runs/41782907889), but it is newer than the hosted package. PRs #304 and #305 reconcile deployed/source versions and current cleanup evidence. No hosted customer workload is claimed. The local monitor still has 40 historical `FINISHED_UNKNOWN_EXIT` records; no Terraform process is active. AWS's current `Purpose=davdeploy-module-validation` inventory contains four inactive Batch job-definition records and two SageMaker lineage records marked `DELETING`; no active certification workload was found. Historical monitor exit statuses remain unknown and are not rewritten as successes. |
| 2. Maintain implementation-to-evidence matrix | `implemented` | See `EXECUTION_READINESS_MATRIX.md`. It enumerates all 26 catalogue modules and 30 implementation entries, separating underlying AWS evidence from hosted renderer evidence. Next: enrich each entry with exact accepted inputs/outputs/dependencies, recovery and cleanup proof, pricing source, role, region and quotas as each renderer is implemented. |
| 3. Durable execution engine | `in progress` | PRs #277, #278 and #280 are deployed by protected apply run [41716835229](https://github.com/Bepoadewale/davdeploy/actions/runs/41716835229), including per-module rows, single-renderer outcomes, leases and reconciliation-required state. PR #287 corrected operation-specific terminal evidence. PR #289 validates durable graphs, #290 computes dispatch waves, and #291 persists module-specific outcomes. PR #293 (merged as `87793a7`) separates module type from instance identity. PR #294 (merged as `6e8fb3d`) adds typed reference-only ports. PR #295 (merged as `464dd0b`) validates typed outputs and resolves dependency references without reading secret contents. PR #296 (merged as `9d14bd1`) persists unique per-module CodeBuild identity; PR #297 (merged as `e28fa23`) validates and persists renderer-specific typed outputs. PR #298 (merged as `42200c0`) adds one-at-a-time dependency scheduling and callback advancement. PR #300 (merged as `afd6736`) resolves a validated S3 bucket output into its selected Lambda/API consumer; PR #301 adds a gated DynamoDB renderer and PR #302 adds its typed API input. The #302 code was deployed by plan run `41781048128` and apply run `41781326222` (0 adds, 6 changes, 0 destroys; migrations passed). PR #303 (`ea9de3a`) fixes the `table_name` dispatcher allowlist and is merged/CI-verified, but not deployed. The routes remain gated and no DynamoDB customer workload has run. Worker restart/reconciliation proof, bounded retry policy, partial-failure compensation and real composed cleanup evidence remain. |
| 4. Hosted Lambda/API lifecycle | `in progress` | PR #283 binds renderer dispatch to the persisted certification mode. PR #284 adds typed single-module lifecycle requests, exact prior-run/artifact/saved-plan chaining, apply/destroy confirmations, and an allowlist. PR #285 wires that setting into Terraform. All three are merged and deployed with the gate off. The live hosted lifecycle still needs an authenticated test workspace, pinned compatible source, real HTTP request, destroy and independent cleanup verification. |
| 5. Genuine module composition | `in progress` | PRs #293–#297 add graph identity, typed references/outputs, exact callback matching and output persistence. PR #298 (merged as `42200c0`) schedules one dependency-ready module at a time. PR #299 (merged as `982bb50`) adds a private S3 renderer, still disabled and without real AWS lifecycle evidence. PR #300 (merged as `afd6736`) resolves a validated S3 bucket output into its Lambda/API consumer and scopes Lambda access to that bucket. PR #301 (`5b067b0`) adds a gated DynamoDB table renderer and PR #302 binds its table name to the Lambda/API renderer. PR #303 (`ea9de3a`) fixes the dispatcher allowlist in source; it must be deployed before the DynamoDB binding can run through hosted CodeBuild. Repeated renderer state isolation, hosted worker restart/reconciliation, and composed data-flow/failure/recovery proof remain. |
| 6. Renderer families 1–8 | `in progress` | The full ordering and module scope are in `EXECUTION_READINESS_MATRIX.md`: storage/data/queues; web/edge; containers/VM; databases/cache; async; search/analytics/streaming; AI/ML; Kubernetes/networking/failover. PR #299 is the first checked-in private S3 lifecycle renderer, still gated and locally validated only. PR #300 adds narrow S3-to-Lambda input delivery and scoped Lambda permissions. PR #301 adds a gated DynamoDB renderer; PR #302 adds the table-to-API binding. PR #303 fixes the dispatcher input mismatch in merged source but is not deployed. The repo already has `NovaTerraformGenerator`, which emits a typed Terraform resource graph but is stored as plan-only and is not connected to CodeBuild; it may reduce service-specific renderer code after provider-schema, policy, IAM, cost, saved-plan and lifecycle controls are added. Its existence does not replace real application and cleanup validation. |
| 7. Planning, artifact, pricing and preflight | `not started` | Planner and constraints exist, but the matrix records fixture inputs/pricing and the current Lambda source contract is narrow. Add timestamped regional pricing and quota/permission evidence, bind deployed artifact to reviewed source, and clearly label assumptions. |
| 8. Browser, CLI and MCP parity | `not started` | Shared backend APIs exist; frontend execution remains App Runner-specific and deployment capabilities are not fully surfaced consistently. Align all clients with the same server-authorized lifecycle and observed states. |
| 9. Real application certification harness | `implemented` | A scenario catalogue/runner exists and standalone real AWS workload evidence covers several services. The current runner primarily validates service roots, not composed applications through the hosted runner. Extend it with traffic, update/recovery, cleanup, and machine-readable evidence for all eight scenarios. |
| 10. Security and operational resilience | `not started` | Add adversarial coverage for tenant boundaries, approvals, artifact tampering, duplicate jobs, concurrency, revoked roles, worker restart, partial failures, quotas, callback authenticity, redaction, alarms and cleanup isolation. |
| 11. Hosted browser/CLI/MCP customer acceptance | `not started` | Use the deployed site/control plane and synthetic customer data. Prove intent → plan/cost → authorized decision → apply → real health → update/recovery → destroy → independently confirmed absence across browser, CLI and MCP. |
| 12. Final evidence and closeout | `not started` | Produce the final capability matrix with commits, PRs, workflow IDs and evidence links. Reconcile docs and ensure no unexplained test resources or active processes remain. |

## Active implementation

- Backend `main` is `f0c6f3af36a0ab14a5dafb9a1684c41140da7eef`, deployed by
  apply run `42902934302` after plan run `42902031985`. The deployed plan
  history APIs from #333/#334 remain behind authentication; the authenticated
  customer journey is not yet verified.
- PR #303 is included in the November 10 release. Renderer routes remain
  gated; no hosted composed customer workload has run. Plan pricing, exact
  costed approval, customer apply, health observation, recovery, teardown, and
  independent absence evidence remain outstanding.

## Verified boundary — historical detail, read with current status above

- Backend main is commit `ea9de3a` (PR #303). The latest hosted release is still PR #302 commit `7d087d0`, deployed by apply run `41781326222`; the reviewed plan changed 6 Lambda packages in place with 0 additions or removals. PR #303 fixes the DynamoDB dispatcher input allowlist in source and passed CI, but is not yet deployed. Renderer routes remain gated. PR #295 validates typed outputs and exposes dependency-output resolution as a library helper; PR #298 schedules one ready module at a time; PR #299 adds a gated private S3 renderer; PR #300 resolves one S3 bucket-name input into Lambda with bucket-scoped IAM; PR #301 adds a gated DynamoDB table renderer; PR #302 binds its table name to Lambda. No hosted composed customer workload has run. PR #275 (`ff5103f`) adds
  project-scoped Lambda/API Terraform state, artifacts, saved plans, results,
  deterministic resource identity and project tags. Its local proof is in
  `docs/test/test275.md`.
- PRs #277, #278 and #280 add deployed module-instance rows, single-renderer
  outcome transitions and durable worker leases, deployed by apply run
  `41716835229`. PR #287 fixes operation-specific evidence checks. PR #289
  validates durable graphs, #290 calculates dependency dispatch waves, and #291
  persists per-module state/output/evidence. These three are merged but not
  connected to the hosted worker.
- PR #280 adds versioned worker leases and refuses to replay an uncertain
  operation. It is merged, CI-verified, and deployed.
- The Lambda/API renderer is still disabled for general hosted customer execution. PR #284's certification route remains off by default with an empty workspace allowlist. Code and disabled configuration are deployed; there is no hosted AWS workload lifecycle evidence yet.
- App Runner remains the only renderer enabled for customer execution.
- PR #293 adds distinct module-type and instance identities. PR #294 adds typed,
  reference-only ports; PR #295 validates typed outputs and resolves declared
  references in library code; and PR #296 persists an exact per-module CodeBuild
  identity and reconciles a callback to that node. PR #297 merged renderer
  output validation and persistence. PR #298 adds durable, one-node-at-a-time
  dependency scheduling to worker claims and callbacks. PR #299 adds a private
  S3 renderer, disabled for execution and without real AWS lifecycle evidence.
  PR #300 resolves a validated bucket reference into Lambda. Repeated/shared
  Terraform state roots, hosted enablement, and composed AWS workload
  certification remain incomplete and fail closed.
- Individual service-level AWS tests do not establish a hosted composed
  customer journey.
- The live API endpoint returning 401 without its required origin and user
  authorization is not a health check. Record only authenticated, authorized
  observations as runtime evidence.

## Nova plan-only runner milestone

- PR #328 merged as `64bfd2c55cf22b61c20305106dcbcec65ef48352` on 2026-11-10.
  Its fixed, versioned, disabled-by-default backend-free planning code is
  included in the November 10 release. Its artifacts are review-only,
  unapprovable, and non-deployable; regional pricing remains unavailable.
- Durable remote state remains a blocker. Proposed ADR-013 selects Terraform's
  built-in HTTP backend, with DavDeploy enforcing tenant/workspace/project/
  environment access and storing encrypted versioned state objects in a
  dedicated S3 bucket, plus locks in PostgreSQL. CodeBuild receives no direct
  state-bucket access. The ADR is a design proposal, not implementation or
  enablement; size, availability, and interrupted-write recovery must be tested
  before customer apply. Direct S3 backend roles remain a fallback, using native
  `use_lockfile=true` and bucket versioning rather than deprecated DynamoDB
  locking. No backend-free plan may count as stateful deployment evidence.
- Plan-runner object access is scoped to the exact CodeBuild ARN in S3 resources;
  the API-only request prefix is inaccessible to CodeBuild. The shared CodeBuild
  role's STS permission still matches the `davdeployPlan-*` role-name pattern.
  The fixed runner binds the ARN to the validated connection/account, each
  customer trust requires its exact ExternalId, and those customer roles deny
  all service actions. Cross-tenant trust tests are mocked contracts, not a live
  IAM simulation. Keep the runner disabled by default, and require an isolated
  per-tenant broker before any plan role receives customer service permissions.

## Evidence update rule

For each step, link the exact PR, merged commit, CI run, evidence file, AWS
account/region and observed results. Never advance a status because code was
written, Terraform validated, a workflow merged, or resource creation
succeeded without the relevant application behavior and cleanup proof.
