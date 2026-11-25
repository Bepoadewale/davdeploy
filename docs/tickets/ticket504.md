# ticket504 — Register the queued AI infrastructure platform goal

PR: https://github.com/Bepoadewale/davdeploy/pull/504 (draft)
Branch: `docs/ai-infrastructure-platform-goal`

## Problem / goal

Register a durable, detailed future engineering goal for evolving DavDeploy
into a governed AI infrastructure and operations platform. Keep it explicitly
queued behind the active Nova-led infrastructure deployment goal. This PR is
documentation-only: it must not start implementation, enable execution, or
change cloud resources.

## Current repo state

- The active goal and its evidence/status handoff are
  [`COMPOSED_EXECUTION_GOAL.md`](../product/COMPOSED_EXECUTION_GOAL.md); it
  remains authoritative until its own acceptance criteria pass.
- The Nova handoff distinguishes direct customer-side lifecycle evidence from
  Nova-originated execution. The accepted direct ECS lifecycle covers only its
  exact recorded shape. Remaining Nova acceptance work includes Nova-specific
  authorization and dispatch, customer credential/role provisioning, broader
  cross-account and effective-permission evidence, complete cost and policy
  coverage, Nova-driven recovery, and the remaining capability matrix.
- The existing [Nova evidence matrix](../product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md)
  maps 26 architecture entries and 30 implementation roots. It is the starting
  point for Phase 1 reuse and gap analysis; it must be reconciled again only
  after the Nova goal completes.
- Existing product architecture includes a serverless hosted control plane,
  a typed plan/approval boundary, AWS-first customer workload paths, and
  OpenTelemetry/Prometheus/Grafana/Tempo/CloudWatch observability. Their actual
  release and evidence state must be rechecked at transition; this ticket does
  not certify production readiness.
- Open PRs #502 and #503 at registration add source-only network/NAT pricing
  and Lambda plan bounds. They are not presumed merged or deployed by this
  queued-goal registration.

## Research / references used

The goal document records official starting references for Bedrock, IAM,
EKS/GPU, CUDA/NCCL, inference engines, Kubernetes, distributed training,
MLflow, model evaluation, agent tooling, and OpenTelemetry GenAI conventions.
These are research leads, not selected dependencies. Before each phase is
started, verify current versions, licenses, security advisories, regional
availability, quotas, pricing, and compatibility against DavDeploy's then
current implementation. Prefer official vendor/project documentation.

## Work planned for the PR

1. Add `docs/product/AI_INFRASTRUCTURE_PLATFORM_GOAL.md` with the objective,
   architecture principles, phased scope, acceptance criteria, evidence rules,
   cost/execution controls, and a future-session handoff contract.
2. Link it from `docs/README.md`, `docs/product/roadmap.md`, and the active Nova
   handoff without reducing, replacing, or reordering the active Nova gates.
3. Record its state as queued and explicitly prohibit implementation until the
   Nova goal is genuinely complete.
4. Do not create a separate repository, provision infrastructure, install
   services, enable model providers, or modify hosted/customer AWS resources.

## Acceptance criteria

- [x] The goal document comprehensively records all eight phases and the final
  success conditions from the request.
- [x] The document preserves minimum-necessary infrastructure, Nova's
  propose/validate/authorize/execute boundary, human approval, tenant
  isolation, least privilege, short-lived credentials, immutable evidence,
  independent observation, cost controls, and cleanup rules.
- [x] Phase 1 requires an audit and reuse of the completed Nova implementation
  before any new execution engine or adapter is considered.
- [x] Cloud, GPU, EKS, model-provider, training, or other billable experiments
  require bounded cost, quota/capacity checks, specific authorization, runtime
  limits, and independent cleanup verification.
- [x] Acceptance distinguishes source, static/local/simulated evidence,
  authenticated plans, direct cloud tests, DavDeploy-driven execution,
  cross-account evidence, hosted deployment, and production use.
- [x] `docs/README.md`, `docs/product/roadmap.md`, and
  `docs/product/COMPOSED_EXECUTION_GOAL.md` link to the new document and mark
  it queued behind the active Nova goal.
- [x] No Nova criterion is weakened and no new-goal implementation or cloud
  mutation occurs in this PR.
- [x] Documentation conventions and diff checks pass.
- [x] Required PR checks pass on the current final head.

## Acceptance status

- [x] Goal document complete.
- [x] Documentation links and queue ordering complete.
- [x] Required CI checks pass on the final PR head.
- [ ] PR reviewed and merged.

## Tests / validation performed

`GITHUB_PR_NUMBER=504 python3 scripts/check_doc_conventions.py` passed.
`git diff --check` passed. No executable behavior changes are in scope. All
seven required checks passed on final-head commit `8ee91feb` in
[CI run 45566249082](https://github.com/Bepoadewale/davdeploy/actions/runs/45566249082).

## Evidence files produced

- `docs/product/AI_INFRASTRUCTURE_PLATFORM_GOAL.md` — queued future goal and
  resume instructions.
- `docs/product/COMPOSED_EXECUTION_GOAL.md` — active-goal handoff link only;
  its acceptance remains unchanged.
- No customer workload evidence file is required or produced.

## Boundaries

Do not start this goal until the active Nova handoff records every genuine
acceptance gate as met with evidence. At transition, re-audit both backend and
frontend state, active PRs, hosted release, workload evidence, authorized
cloud boundaries, open Terraform runs, cost controls, and retained resources.
Then convert the first unmet dependency into a separate PR and numbered ticket.
All later implementation remains subject to the current repository workflow
and execution authorization; this registration is not advance authorization
for any cloud mutation.

## Follow-up work

After PR #504 merges, continue the active Nova goal. Activate this queued goal
only after the Nova handoff records all acceptance evidence and explicitly
closes that goal. Then complete the activation audit in the queued document and
select one dependency-ready implementation package.
