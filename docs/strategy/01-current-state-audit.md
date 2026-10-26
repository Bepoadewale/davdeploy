# Current-state audit

**Review date:** 2026-10-14  
**Scope:** historical read-only review of the merged davdeploy repository at commit `d118210` (PR #49 branch state). No application code or AWS resources were changed by this review.

> Historical snapshot: this audit predates the deployed Aurora serverless control plane, canonical
> `davdeploy.tech` origin, and active Resend invitation sender. For current operating status, use
> the root README, `PROJECT_STATUS.md`, [hosted persistence](../architecture/hosted-persistence.md),
> and [email operations](../EMAIL_OPERATIONS.md).

## Executive finding

davdeploy is no longer a strategy-only repository. It is a modular FastAPI product with a plain browser UI, PostgreSQL persistence, typed workload and architecture schemas, a deterministic AWS planner, OPA policy, plan approval, audit, local execution, GitHub/AWS integration contracts, Terraform renderers, and an explicitly gated App Runner execution adapter.

The strongest existing asset is the governed decision pipeline, not the current natural-language parser. The parser and pricing/inventory catalog are deterministic fixtures; the hosted identity and durable-RDS contracts are implemented but not fully operated as production SaaS. No live customer workload is currently running in the reviewed AWS account.

## Capability evidence

| Capability | Status | Evidence |
|---|---|---|
| Typed intent and provenance | Implemented and tested locally | `apps/api/src/davdeploy/domain.py:WorkloadSpec`, `intent.py:DeterministicIntentProvider`, `tests/test_product.py` |
| AWS candidate planning | Implemented and tested locally | `planner.py:AwsV1Planner`, `tests/test_planner_decisions.py` |
| Non-EKS-first selection | Implemented and tested locally | `tests/test_planner_decisions.py::test_tiny_stateless_api_is_not_eks`, `test_kubernetes_requested_for_status_is_not_selected_without_need` |
| Cost estimation | Implemented as fixture estimate | `domain.py:CostRange`, `planner.py`; not live AWS Pricing evidence |
| Complexity scoring | Implemented as transparent heuristic | `planner.py:_complexity_reasons`, `ArchitectureCandidate.operational_complexity` |
| Repository analysis | Implemented; fixture and guarded GitHub App read mode | `integrations.py`, `models.py:StoredRepositoryAnalysis`, `tests/test_connection_experience.py` |
| AWS connection/discovery | Live read-only path verified; no deployment permission | `scripts/customer-aws-connection.sh`, `service.py`, `tests/test_customer_aws_connection_contract.py` |
| Tenant/RBAC boundary | Implemented locally; production IdP not connected | `security.py`, `models.py:ProductUser`, `tests/test_security_identity.py`, `tests/test_workspace_dashboards.py` |
| Plan lifecycle | Implemented and persisted | `models.py:InfrastructurePlan*`, `service.py:submit_infrastructure_plan`, `decide_infrastructure_plan`, `tests/test_infrastructure_plan_lifecycle.py` |
| Admin self-approval | Implemented by explicit policy | `ADR-010`, `tests/test_infrastructure_plan_lifecycle.py::test_administrator_can_self_approve_and_audits_exception` |
| Audit | Implemented and queryable | `models.py:AuditEvent`, `/api/v1/audit-events`, `/api/v1/audit-evidence` |
| Local execution/observation/destroy | Implemented and tested with fixture executor | `fixture_executor.py`, `tests/test_customer_plan_review.py` |
| Cloud execution boundary | Implemented but disabled by default | `cloud_execution.py`, `worker.py`, `tests/test_cloud_execution.py` |
| Terraform | Plan-contract renderers and static validation; authenticated plan/apply not routinely executed | `infrastructure/terraform/renderers/app-runner-plan`, `tests/test_customer_plan_review.py` |
| Prometheus/Grafana | Local stack and mandatory plan components | `docker-compose.yml`, `platform/prometheus`, `platform/grafana`, `planner.py:MonitoringSpecification` |
| Real workload monitoring/cost evidence | Absent | Current Day-2 path is deterministic fixture evidence |
| Hosted persistence | RDS contract implemented, not applied to current runtime | `docs/architecture/hosted-persistence.md`, `tests/test_db_config.py` |
| Production authentication | Server-side JWKS membership boundary exists; real issuer/session/invite flow absent | `security.py`, `tests/test_security_identity.py` |

## What is partial or misleading if read without the status docs

- `DeterministicIntentProvider` is not a general LLM integration. It extracts a small set of fields with regular expressions and asks for missing values.
- `AwsV1Planner` is an auditable catalog, not a live AWS architecture optimizer. Prices and service constraints are fixture assumptions.
- `CloudInventorySnapshot` supports live read-only snapshots, but normal local planning uses fixture inventory unless a trusted discovery result is supplied.
- The browser is a plain JavaScript UI by deliberate decision (`docs/decisions/ADR-009-plain-web-ui.md`), not a TypeScript/Next.js application.
- `EnvironmentOutput` and `ObservedResource` are first-class local/observed records, but real cloud output ingestion is not yet wired to the product worker.
- `AppRunnerCloudExecutionAdapter` is a narrow subprocess boundary. It is not proof that the hosted product can safely execute customer infrastructure end to end.

## Strengths to preserve

1. **Approval is separate from execution.** This is a meaningful trust boundary and must not be collapsed for an “agentic” UX.
2. **Plans are typed, hashed, immutable after submission, and tenant-scoped.** This is more defensible than free-form Terraform generation.
3. **The planner is explicitly non-EKS-first.** The candidate tests demonstrate a product principle, not only a UI claim.
4. **The control plane has reusable seams.** `IntentProvider`, planner inputs, provider/integration adapters, execution profiles, observer records, and MCP/API clients allow model and provider changes without rewriting governance.
5. **Evidence discipline is unusually strong.** `docs/test/`, `docs/tickets/`, CI conventions, and executed/simulated/unexecuted labels reduce credibility risk.

## Critical gaps

1. Live pricing, quotas, service availability, and workload telemetry are not inputs to recommendation quality.
2. The intent parser does not inspect code deeply enough to safely infer framework, ports, build, secrets, persistence, or runtime constraints.
3. There is no expert-reviewed benchmark or regression gate for architecture quality.
4. The planner has a fixed service catalog and heuristic costs; it can be wrong outside its narrow supported workload envelope.
5. The hosted runtime still needs a real external identity provider and applied durable persistence before it should be presented as production SaaS.
6. A real deployment path exists only as a guarded adapter; output ingestion, failure recovery, and destroy proof need a complete product-driven pilot.
7. Prometheus/Grafana are mandatory in the selected plan, but that requirement may be too expensive or operationally mismatched for every small workload. The product should preserve the customer requirement while making the monitoring cost and fit explicit.

## Recommended reuse/refactor boundary

- Retain `domain.py`, `models.py`, `security.py`, `policy.py`, `service.py`, audit, approval, and state-machine code.
- Refactor `intent.py` behind a provider-agnostic structured extraction interface with repository evidence and confidence per field.
- Refactor `planner.py` into deterministic capability matching plus live-data adapters for price, quota, regional availability, and inventory.
- Keep the modular monolith; do not introduce a model-serving cluster or microservice fleet for the MVP.
- Treat Terraform and provider adapters as render/validate/execute backends, never as the source of business authorization.

## Shortest credible path

1. Freeze a narrow workload envelope and benchmark it.
2. Add repository evidence ingestion and current AWS catalog/pricing adapters in read-only mode.
3. Replace fixture-only recommendation confidence with evidence-backed uncertainty and explicit “cannot determine” outcomes.
4. Operate hosted Postgres and real identity before customer data is accepted.
5. Run one product-driven App Runner pilot with output capture, independent observation, destroy, and evidence.
6. Only then expand workload families or autonomous Day-2 actions.

