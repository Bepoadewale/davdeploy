# Composed AWS execution goal handoff

Updated: 2026-11-03. This checklist tracks the goal in the attached execution
specification. It is not a launch-readiness claim. “Implemented” means code
exists; only “AWS verified” and “deployed” records those stronger states.

Allowed status values: `not started`, `implemented`, `locally verified`,
`AWS verified`, `deployed`.

## Ordered execution checklist

| Step | Status | Evidence and next action |
|---|---|---|
| 1. Reconcile baseline, active operations, PR #270 and deployment | `locally verified` | PR #270 apply run [41671744510](https://github.com/Bepoadewale/davdeploy/actions/runs/41671744510) completed successfully for reviewed commit `93c895e`; `docs/product/EXECUTION_READINESS_MATRIX.md` records 0 creates, 7 updates, 0 destroys and the deployed package/dispatcher evidence. Confirm live version and health through authenticated, origin-authorized probes; an unauthenticated `/health` 401 is not health evidence. No active Terraform operation was found in the local monitor registry on 2026-11-03. |
| 2. Maintain implementation-to-evidence matrix | `implemented` | See `EXECUTION_READINESS_MATRIX.md`. It enumerates all 26 catalogue modules and 30 implementation entries, separating underlying AWS evidence from hosted renderer evidence. Next: enrich each entry with exact accepted inputs/outputs/dependencies, recovery and cleanup proof, pricing source, role, region and quotas as each renderer is implemented. |
| 3. Durable execution engine | `not started` | Existing lifecycle/run records and worker contracts are foundations, not durable multi-instance graph execution. Implement graph instance state, locking, resume, duplicate handling, partial failure/recovery, immutable versions, output redaction and independent cleanup evidence. |
| 4. Hosted Lambda/API lifecycle | `not started` | PR #267 renderer, #268 isolated AWS HTTP/teardown proof, #269 artifact/plan hardening, #273 artifact builder, #274 result reconciliation, and #275 project isolation are foundations. Hosted Lambda run creation remains disabled. Next: connect the typed saved-plan lifecycle to the actual customer CodeBuild path, then certify apply, HTTP traffic, health, update, recovery, destroy and independently verified absence before enabling it. |
| 5. Genuine module composition | `not started` | CodeBuild currently rejects multi-module work. Implement typed output bindings, dependency order, independent state, resume/retry and reverse cleanup. Prove Lambda/API + DynamoDB + SQS + private S3 with real data flow and failure/recovery. |
| 6. Renderer families 1–8 | `not started` | The full ordering and module scope are in `EXECUTION_READINESS_MATRIX.md` and the goal: storage/data/queues; web/edge; containers/VM; databases/cache; async; search/analytics/streaming; AI/ML; Kubernetes/networking/failover. Make each family pass its lifecycle and hosted certification before presenting it as operational. |
| 7. Planning, artifact, pricing and preflight | `not started` | Planner and constraints exist, but the matrix records fixture inputs/pricing and the current Lambda source contract is narrow. Add timestamped regional pricing and quota/permission evidence, bind deployed artifact to reviewed source, and clearly label assumptions. |
| 8. Browser, CLI and MCP parity | `not started` | Shared backend APIs exist; frontend execution remains App Runner-specific and deployment capabilities are not fully surfaced consistently. Align all clients with the same server-authorized lifecycle and observed states. |
| 9. Real application certification harness | `not started` | `certify_aws_scenario.py` primarily handles Terraform apply/destroy. Extend it to real traffic through the hosted runner and machine-readable evidence for the eight named application scenarios, including update/recovery/absence. |
| 10. Security and operational resilience | `not started` | Add adversarial coverage for tenant boundaries, approvals, artifact tampering, duplicate jobs, concurrency, revoked roles, worker restart, partial failures, quotas, callback authenticity, redaction, alarms and cleanup isolation. |
| 11. Hosted browser/CLI/MCP customer acceptance | `not started` | Use the deployed site/control plane and synthetic customer data. Prove intent → plan/cost → authorized decision → apply → real health → update/recovery → destroy → independently confirmed absence across browser, CLI and MCP. |
| 12. Final evidence and closeout | `not started` | Produce the final capability matrix with commits, PRs, workflow IDs and evidence links. Reconcile docs and ensure no unexplained test resources or active processes remain. |

## Current verified boundary

- PR #275 is merged at `ff5103f` and adds project-scoped Lambda/API Terraform
  state, artifacts, saved plans, results, deterministic resource identity and
  project tags. Its local proof is in `docs/test/test275.md`.
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
