# Composed AWS execution goal handoff

Updated: 2026-11-03. This checklist tracks the goal in the attached execution
specification. It is not a launch-readiness claim. “Implemented” means code
exists; only “AWS verified” and “deployed” records those stronger states.

Allowed status values: `not started`, `implemented`, `locally verified`,
`AWS verified`, `deployed`.

## Ordered execution checklist

| Step | Status | Evidence and next action |
|---|---|---|
| 1. Reconcile baseline, active operations, PR #270 and deployment | `deployed` | PR #270 apply run [41671744510](https://github.com/Bepoadewale/davdeploy/actions/runs/41671744510) completed successfully for reviewed commit `93c895e`; it applied 0 creates, 7 updates and 0 destroys and completed database migrations. On 2026-11-03, AWS reported `davdeploy-api` Active/Successful (last updated 16:27 UTC), the live CodeBuild project invoked the typed dispatcher, and `https://api.davdeploy.tech/healthz` returned HTTP 200 `{"status":"ok","product":"davdeploy"}` through the Cloudflare edge. The local monitor registry has no active process, but 40 legacy records remain `FINISHED_UNKNOWN_EXIT`; their missing exit codes are not retroactively claimed as success. |
| 2. Maintain implementation-to-evidence matrix | `implemented` | See `EXECUTION_READINESS_MATRIX.md`. It enumerates all 26 catalogue modules and 30 implementation entries, separating underlying AWS evidence from hosted renderer evidence. Next: enrich each entry with exact accepted inputs/outputs/dependencies, recovery and cleanup proof, pricing source, role, region and quotas as each renderer is implemented. |
| 3. Durable execution engine | `implemented` | PR #277 (`6c39ad3`) persists per-module graph rows; PR #278 (`8868836`, CI run [41703537515](https://github.com/Bepoadewale/davdeploy/actions/runs/41703537515)) persists scoped single-renderer outcomes. PR #280 adds atomic worker leases, heartbeats and reconciliation-required state after uncertain outcomes; 50 focused tests and full verification (397) pass; clean-room passes at code commit `3f32dc9`; CI run [41711545894](https://github.com/Bepoadewale/davdeploy/actions/runs/41711545894) passes all seven jobs. No uncertain external work is automatically replayed. Dependency scheduling, safe retries after authenticated reconciliation, partial-failure recovery, and graph cleanup verification remain. |
| 4. Hosted Lambda/API lifecycle | `not started` | PR #267 renderer, #268 isolated AWS HTTP/teardown proof, #269 artifact/plan hardening, #273 artifact builder, #274 result reconciliation, and #275 project isolation are foundations. Hosted Lambda run creation remains disabled. Next: connect the typed saved-plan lifecycle to the actual customer CodeBuild path, then certify apply, HTTP traffic, health, update, recovery, destroy and independently verified absence before enabling it. |
| 5. Genuine module composition | `not started` | CodeBuild currently rejects multi-module work. Implement typed output bindings, dependency order, independent state, resume/retry and reverse cleanup. Prove Lambda/API + DynamoDB + SQS + private S3 with real data flow and failure/recovery. |
| 6. Renderer families 1–8 | `not started` | The full ordering and module scope are in `EXECUTION_READINESS_MATRIX.md` and the goal: storage/data/queues; web/edge; containers/VM; databases/cache; async; search/analytics/streaming; AI/ML; Kubernetes/networking/failover. Make each family pass its lifecycle and hosted certification before presenting it as operational. |
| 7. Planning, artifact, pricing and preflight | `not started` | Planner and constraints exist, but the matrix records fixture inputs/pricing and the current Lambda source contract is narrow. Add timestamped regional pricing and quota/permission evidence, bind deployed artifact to reviewed source, and clearly label assumptions. |
| 8. Browser, CLI and MCP parity | `not started` | Shared backend APIs exist; frontend execution remains App Runner-specific and deployment capabilities are not fully surfaced consistently. Align all clients with the same server-authorized lifecycle and observed states. |
| 9. Real application certification harness | `implemented` | A scenario catalogue/runner exists and standalone real AWS workload evidence covers several services. The current runner primarily validates service roots, not composed applications through the hosted runner. Extend it with traffic, update/recovery, cleanup, and machine-readable evidence for all eight scenarios. |
| 10. Security and operational resilience | `not started` | Add adversarial coverage for tenant boundaries, approvals, artifact tampering, duplicate jobs, concurrency, revoked roles, worker restart, partial failures, quotas, callback authenticity, redaction, alarms and cleanup isolation. |
| 11. Hosted browser/CLI/MCP customer acceptance | `not started` | Use the deployed site/control plane and synthetic customer data. Prove intent → plan/cost → authorized decision → apply → real health → update/recovery → destroy → independently confirmed absence across browser, CLI and MCP. |
| 12. Final evidence and closeout | `not started` | Produce the final capability matrix with commits, PRs, workflow IDs and evidence links. Reconcile docs and ensure no unexplained test resources or active processes remain. |

## Current verified boundary

- Backend main is `07e3916` after PR #279. PR #275 (`ff5103f`) adds
  project-scoped Lambda/API Terraform state, artifacts, saved plans, results,
  deterministic resource identity and project tags. Its local proof is in
  `docs/test/test275.md`.
- PRs #277 and #278 add durable module-instance rows and single-renderer run
  outcome transitions. PR #279 improves local Terraform mutation monitoring.
  These changes are merged; #278 remains undeployed to the hosted control plane.
- Draft PR #280 adds versioned worker leases and refuses to replay an uncertain
  operation. It remains unmerged and undeployed; only focused tests have run.
- The Lambda/API renderer is still disabled for hosted customer execution.
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
