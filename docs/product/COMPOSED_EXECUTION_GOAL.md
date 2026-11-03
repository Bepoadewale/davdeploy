# Composed AWS execution goal handoff

Updated: 2026-11-03. This checklist tracks the goal in the attached execution
specification. It is not a launch-readiness claim. “Implemented” means code
exists; only “AWS verified” and “deployed” records those stronger states.

Allowed status values: `not started`, `in progress`, `implemented`,
`locally verified`, `AWS verified`, `deployed`.

## Ordered execution checklist

| Step | Status | Evidence and next action |
|---|---|---|
| 1. Reconcile baseline and deploy certification scaffolding | `deployed` | PRs #283–#285 are merged. Plan run [41729846651](https://github.com/Bepoadewale/davdeploy/actions/runs/41729846651) and apply run [41730396958](https://github.com/Bepoadewale/davdeploy/actions/runs/41730396958) for commit `2e39e4a45fee9bd69b5827a48431c052e5f772e2` completed with 0 creates, 6 in-place Lambda package updates and 0 destroys. Migration completed and `https://api.davdeploy.tech/healthz` returned HTTP 200. The serverless certification flag is false and its workspace allowlist is empty. No customer workload was run. |
| 2. Maintain implementation-to-evidence matrix | `implemented` | See `EXECUTION_READINESS_MATRIX.md`. It enumerates all 26 catalogue modules and 30 implementation entries, separating underlying AWS evidence from hosted renderer evidence. Next: enrich each entry with exact accepted inputs/outputs/dependencies, recovery and cleanup proof, pricing source, role, region and quotas as each renderer is implemented. |
| 3. Durable execution engine | `deployed` | PR #277 (`6c39ad3`) persists per-module graph rows; PR #278 (`8868836`, CI run [41703537515](https://github.com/Bepoadewale/davdeploy/actions/runs/41703537515)) persists scoped single-renderer outcomes. PR #280 (`ef60ac3`) adds atomic worker leases, heartbeats and reconciliation-required state after uncertain outcomes. Protected apply run [41716835229](https://github.com/Bepoadewale/davdeploy/actions/runs/41716835229) deployed the package and schema v24. No uncertain external work is automatically replayed. Dependency scheduling, safe retries after authenticated reconciliation, partial-failure recovery, and graph cleanup verification remain. |
| 4. Hosted Lambda/API lifecycle | `in progress` | PR #283 binds renderer dispatch to the persisted certification mode. PR #284 adds typed single-module lifecycle requests, exact prior-run/artifact/saved-plan chaining, apply/destroy confirmations, and an allowlist. PR #285 wires that setting into Terraform. All three are merged and deployed with the gate off. The live hosted lifecycle still needs an authenticated test workspace, pinned compatible source, real HTTP request, destroy and independent cleanup verification. |
| 5. Genuine module composition | `not started` | CodeBuild currently rejects multi-module work. Implement typed output bindings, dependency order, independent state, resume/retry and reverse cleanup. Prove Lambda/API + DynamoDB + SQS + private S3 with real data flow and failure/recovery. |
| 6. Renderer families 1–8 | `not started` | The full ordering and module scope are in `EXECUTION_READINESS_MATRIX.md` and the goal: storage/data/queues; web/edge; containers/VM; databases/cache; async; search/analytics/streaming; AI/ML; Kubernetes/networking/failover. Make each family pass its lifecycle and hosted certification before presenting it as operational. |
| 7. Planning, artifact, pricing and preflight | `not started` | Planner and constraints exist, but the matrix records fixture inputs/pricing and the current Lambda source contract is narrow. Add timestamped regional pricing and quota/permission evidence, bind deployed artifact to reviewed source, and clearly label assumptions. |
| 8. Browser, CLI and MCP parity | `not started` | Shared backend APIs exist; frontend execution remains App Runner-specific and deployment capabilities are not fully surfaced consistently. Align all clients with the same server-authorized lifecycle and observed states. |
| 9. Real application certification harness | `implemented` | A scenario catalogue/runner exists and standalone real AWS workload evidence covers several services. The current runner primarily validates service roots, not composed applications through the hosted runner. Extend it with traffic, update/recovery, cleanup, and machine-readable evidence for all eight scenarios. |
| 10. Security and operational resilience | `not started` | Add adversarial coverage for tenant boundaries, approvals, artifact tampering, duplicate jobs, concurrency, revoked roles, worker restart, partial failures, quotas, callback authenticity, redaction, alarms and cleanup isolation. |
| 11. Hosted browser/CLI/MCP customer acceptance | `not started` | Use the deployed site/control plane and synthetic customer data. Prove intent → plan/cost → authorized decision → apply → real health → update/recovery → destroy → independently confirmed absence across browser, CLI and MCP. |
| 12. Final evidence and closeout | `not started` | Produce the final capability matrix with commits, PRs, workflow IDs and evidence links. Reconcile docs and ensure no unexplained test resources or active processes remain. |

## Current verified boundary

- Backend main is `2e39e4a` after PR #285. PR #275 (`ff5103f`) adds
  project-scoped Lambda/API Terraform state, artifacts, saved plans, results,
  deterministic resource identity and project tags. Its local proof is in
  `docs/test/test275.md`.
- PRs #277 and #278 add durable module-instance rows and single-renderer run
  outcome transitions. PR #279 improves local Terraform mutation monitoring.
  PR #280 adds durable worker leases. The worker/database changes from #277,
  #278 and #280 are deployed by apply run `41716835229`.
- PR #280 adds versioned worker leases and refuses to replay an uncertain
  operation. It is merged, CI-verified, and deployed.
- The Lambda/API renderer is still disabled for general hosted customer execution. PR #284's certification route remains off by default with an empty workspace allowlist. Code and disabled configuration are deployed; there is no hosted AWS workload lifecycle evidence yet.
- App Runner remains the single hosted renderer.
- Multi-module CodeBuild requests remain fail-closed.
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
