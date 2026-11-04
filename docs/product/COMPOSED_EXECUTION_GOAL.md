# Composed AWS execution goal handoff

Updated: 2026-11-04. This checklist tracks the goal in the attached execution
specification. It is not a launch-readiness claim. “Implemented” means code
exists; only “AWS verified” and “deployed” records those stronger states.

Allowed status values: `not started`, `in progress`, `implemented`,
`locally verified`, `AWS verified`, `deployed`.

## Ordered execution checklist

| Step | Status | Evidence and next action |
|---|---|---|
| 1. Reconcile baseline and deploy certification scaffolding | `deployed` | PRs #283–#285 are merged. Plan run [41729846651](https://github.com/Bepoadewale/davdeploy/actions/runs/41729846651) and apply run [41730396958](https://github.com/Bepoadewale/davdeploy/actions/runs/41730396958) for commit `2e39e4a45fee9bd69b5827a48431c052e5f772e2` completed with 0 creates, 6 in-place Lambda package updates and 0 destroys. Migration completed and `https://api.davdeploy.tech/healthz` returned HTTP 200. The serverless certification flag is false and its workspace allowlist is empty. No customer workload was run. |
| 2. Maintain implementation-to-evidence matrix | `implemented` | See `EXECUTION_READINESS_MATRIX.md`. It enumerates all 26 catalogue modules and 30 implementation entries, separating underlying AWS evidence from hosted renderer evidence. Next: enrich each entry with exact accepted inputs/outputs/dependencies, recovery and cleanup proof, pricing source, role, region and quotas as each renderer is implemented. |
| 3. Durable execution engine | `in progress` | PRs #277, #278 and #280 are deployed by protected apply run [41716835229](https://github.com/Bepoadewale/davdeploy/actions/runs/41716835229), including per-module rows, single-renderer outcomes, leases and reconciliation-required state. PR #287 corrected operation-specific terminal evidence. PR #289 validates durable graphs, #290 computes dispatch waves, and #291 persists module-specific outcomes. PR #293 (merged as `87793a7`) separates module type from instance identity. PR #294 (merged as `6e8fb3d`) adds typed reference-only ports. PR #295 (merged as `464dd0b`) validates typed outputs and resolves dependency references without reading secret contents. PR #296 (merged as `9d14bd1`) persists unique per-module CodeBuild identity; PR #297 (merged as `e28fa23`) validates and persists renderer-specific typed outputs. PR #298 (merged as `42200c0`) adds one-at-a-time dependency scheduling and callback advancement. PR #300 (merged as `afd6736`) resolves a validated S3 bucket output into its selected Lambda/API consumer. These newer code foundations have not been deployed. Worker restart/reconciliation proof, bounded retry policy, partial-failure compensation and real composed cleanup evidence remain. |
| 4. Hosted Lambda/API lifecycle | `in progress` | PR #283 binds renderer dispatch to the persisted certification mode. PR #284 adds typed single-module lifecycle requests, exact prior-run/artifact/saved-plan chaining, apply/destroy confirmations, and an allowlist. PR #285 wires that setting into Terraform. All three are merged and deployed with the gate off. The live hosted lifecycle still needs an authenticated test workspace, pinned compatible source, real HTTP request, destroy and independent cleanup verification. |
| 5. Genuine module composition | `in progress` | PRs #293–#297 add graph identity, typed references/outputs, exact callback matching and output persistence. PR #298 (merged as `42200c0`) schedules one dependency-ready module at a time. PR #299 (merged as `982bb50`) adds a private S3 renderer, still disabled and without real AWS lifecycle evidence. PR #300 (merged as `afd6736`) resolves a validated S3 bucket output into its Lambda/API consumer and scopes Lambda access to that bucket. Repeated renderer state isolation, hosted worker restart/reconciliation, and composed data-flow/failure/recovery proof remain. |
| 6. Renderer families 1–8 | `in progress` | The full ordering and module scope are in `EXECUTION_READINESS_MATRIX.md`: storage/data/queues; web/edge; containers/VM; databases/cache; async; search/analytics/streaming; AI/ML; Kubernetes/networking/failover. PR #299 is the first checked-in private S3 lifecycle renderer, still gated and locally validated only. PR #300 adds narrow S3-to-Lambda input delivery and scoped Lambda permissions, still not deployed or AWS certified. PR #301 is adding a gated DynamoDB table renderer. Continue with other renderer roots, then real lifecycle and composition certification before presenting them as operational. |
| 7. Planning, artifact, pricing and preflight | `not started` | Planner and constraints exist, but the matrix records fixture inputs/pricing and the current Lambda source contract is narrow. Add timestamped regional pricing and quota/permission evidence, bind deployed artifact to reviewed source, and clearly label assumptions. |
| 8. Browser, CLI and MCP parity | `not started` | Shared backend APIs exist; frontend execution remains App Runner-specific and deployment capabilities are not fully surfaced consistently. Align all clients with the same server-authorized lifecycle and observed states. |
| 9. Real application certification harness | `implemented` | A scenario catalogue/runner exists and standalone real AWS workload evidence covers several services. The current runner primarily validates service roots, not composed applications through the hosted runner. Extend it with traffic, update/recovery, cleanup, and machine-readable evidence for all eight scenarios. |
| 10. Security and operational resilience | `not started` | Add adversarial coverage for tenant boundaries, approvals, artifact tampering, duplicate jobs, concurrency, revoked roles, worker restart, partial failures, quotas, callback authenticity, redaction, alarms and cleanup isolation. |
| 11. Hosted browser/CLI/MCP customer acceptance | `not started` | Use the deployed site/control plane and synthetic customer data. Prove intent → plan/cost → authorized decision → apply → real health → update/recovery → destroy → independently confirmed absence across browser, CLI and MCP. |
| 12. Final evidence and closeout | `not started` | Produce the final capability matrix with commits, PRs, workflow IDs and evidence links. Reconcile docs and ensure no unexplained test resources or active processes remain. |

## Current verified boundary

- Backend main at the audit baseline includes PR #300 (`afd6736`), #299 (`982bb50`), #298 (`42200c0`), #297 (`e28fa23`), #296 (`9d14bd1`), #295 (`464dd0b`), #294 (`6e8fb3d`), and #293 (`87793a7`). These execution foundations are code-only and have not been deployed. PR #295 validates typed outputs and exposes dependency-output resolution as a library helper; PR #298 schedules one ready module at a time; PR #299 adds a gated private S3 renderer; PR #300 resolves one S3 bucket-name input into Lambda with bucket-scoped IAM. PR #301 is adding a gated DynamoDB table renderer. The latest hosted control-plane release remains commit `2e39e4a` after PR #285. PR #275 (`ff5103f`) adds
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

## Evidence update rule

For each step, link the exact PR, merged commit, CI run, evidence file, AWS
account/region and observed results. Never advance a status because code was
written, Terraform validated, a workflow merged, or resource creation
succeeded without the relevant application behavior and cleanup proof.
