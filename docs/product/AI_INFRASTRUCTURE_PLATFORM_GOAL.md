# DavDeploy AI Infrastructure and Operations Platform Goal

Status: **Queued behind the active Nova-led infrastructure deployment goal.**
This document registers a future engineering objective. It does not authorize
implementation, cloud execution, provider enablement, or infrastructure
provisioning before the current Nova goal is genuinely complete.

Owner: DavDeploy engineering. Revisit only after all acceptance gates in the
[active Nova execution handoff](COMPOSED_EXECUTION_GOAL.md) have been met with
evidence and that goal is explicitly closed. There is no deadline.

## Objective

Evolve the existing DavDeploy product into a commercially useful, governed AI
infrastructure and operations platform. Support the engineering lifecycle of
AI workloads where customer requirements justify them: managed AI applications,
secure agents, model inference, GPU compute, distributed workloads, model
evaluation and release, observability, FinOps, and approved Day-2 operations.
Keep all capabilities in the existing `davdeploy` and `davdeploy-frontend`
repositories. Do not create portfolio repositories or add technologies only
to make a demonstration look broader.

The product should let customers state requirements in ordinary language while
DavDeploy selects and explains a suitable architecture, enforces policy,
obtains explicit authorization, performs bounded operations, and records
independent evidence. Managed AI, CPU inference, a single GPU VM, and Kubernetes
are different options selected from actual requirements and economics; none is
the universal default.

**Product vision:** DavDeploy intelligently plans, provisions, operates,
evaluates, optimizes, and retires cloud and AI workloads while preserving
human authorization, security, reliability, cost efficiency, and
accountability.

## Queue and transition contract

The [composed Nova goal](COMPOSED_EXECUTION_GOAL.md) remains the sole active
engineering priority until its own acceptance criteria pass. This goal is
queued; its phases are not active tasks. Do not use this future scope to weaken,
defer, or redefine any Nova gate.

At transition, the next Codex session must first reconcile current backend and
frontend branches, pull requests, source and deployed versions, the Nova
handoff, capability/evidence matrices, authorized cloud accounts and regions,
Terraform run monitor, retained test resources, and current cost/quota limits.
Re-audit every capability as implemented, proven, partial, simulated, or open.
Reuse the existing execution engine and contracts. Do not duplicate an
execution engine or infer completion from this plan. Select the next
dependency-ready package, create a PR and its numbered ticket, and update this
document's phase ledger with blockers, relevant commits, evidence, and the next
action. Keep the Nova handoff authoritative until it is closed.

## Architecture and operating principles

- **Minimum necessary infrastructure:** choose the simplest, cheapest
  architecture that meets hard customer requirements. Kubernetes, GPUs,
  microservices, training, vector databases, and distributed compute are
  optional tools, never product defaults.
- **Three separate trust domains:** DavDeploy's hosted control plane,
  customer-owned infrastructure/workloads, and explicitly authorized
  engineering test environments remain separate. Keep the hosted control plane
  serverless and cost-efficient unless measured requirements justify a change.
  Run expensive AI infrastructure only in customer accounts or explicitly
  approved test accounts.
- **Authority boundary:** AI proposes; deterministic software validates,
  authorizes, executes, observes, and audits. An LLM must never receive
  unrestricted cloud, shell, Terraform, Kubernetes, customer-secret, or
  administrative authority. Approval does not itself execute a change.
- **Security and evidence:** preserve tenant isolation, least-privilege IAM,
  short-lived credentials, separate discovery/planning/execution/observation
  responsibilities, immutable plan and artifact digests, explicit approval,
  durable execution state, independent observation, audit history, and
  controlled rollback/destruction.
- **Provider scope:** implement AWS first behind appropriate provider-neutral
  interfaces. Add another cloud only after its complete connection,
  discovery, price, policy, plan, execution, observation, recovery, and support
  path is justified and validated.
- **Evidence honesty:** keep catalogued, planning, pilot, and general
  availability states distinct. Keep architecture, source, static validation,
  local/simulated runs, authenticated cloud plans, direct cloud tests,
  DavDeploy-driven execution, same-account pilot, cross-account customer
  evidence, hosted release, and production use distinct.

## Phase 1 — Governed AI workload execution foundation

Begin with an audit of the completed Nova system and its evidence. Inventory
existing lifecycle orchestration, approvals, credential brokering, policy,
pricing, observation, recovery, adapters, test harnesses, and limitations.
Reuse proven paths; implement no competing execution engine. Extend the
existing governed adapter catalogue and retain its catalogued/planning/pilot/
general-availability distinctions.

The shared lifecycle contract for each new AI adapter is: natural-language
requirements → typed specification → architecture choice → regional quota and
capacity validation → cost estimate → Terraform generation and authenticated
plan → deterministic actual-plan policy → approval bound to the exact saved
plan → separately authorized execution → resource provisioning → application
readiness → observation → controlled update → recovery → authorized destroy →
independent absence verification.

Every adapter must document its supported shape, resource and permission
boundaries, security controls, cost model and assumptions, runtime dependencies,
health/readiness contract, failure behavior, rollback, cleanup and retained
resources, and promotion evidence. Acceptance requires repeatable authorized
cloud lifecycle evidence; a generated, approved, or statically checked plan is
not workload execution evidence.

## Phase 2 — Enterprise AI control plane and LLMOps

### Model routing and provider abstraction

Keep Amazon Nova through Bedrock as the primary supported model unless product
requirements and measured evidence justify another default. Extend the existing
serverless model abstraction before considering a continuously running proxy.
Evaluate Bedrock families, authorized Anthropic interfaces, OpenAI-compatible
endpoints, customer-hosted inference, and other providers only when justified.

Implement versioned model/provider configuration, capability discovery,
selection policy, explicitly authorized fallback, timeouts, circuit breakers
when justified, rate limits, token accounting, tenant quotas and budgets,
cost-aware selection, latency/reliability measures, safe caching where
appropriate, and provider-specific privacy/residency rules. A fallback must
never bypass data policy or model restrictions. A failed production request
must not be reported as a successful fixture response.

### Evaluation and regression gates

Build a versioned evaluation set from actual DavDeploy work: simple and
composed deployments, managed AI, GPU inference, distributed ML, ambiguous or
unsupported requests, invalid plans and structured outputs, budget and security
violations, prompt injection, tenant-boundary attacks, hallucinated resources,
bad architecture, and invalid tool calls. Provide deterministic offline
evaluation and separately authorized, cost-capped live evaluation. Evaluate
Promptfoo, pytest, Bedrock model evaluation, or other tools selectively.

Measure intent accuracy, schema validity, architecture and hard-constraint
correctness, Terraform validity, policy detection, invalid tool-call rate,
completion, repair/failure, latency, token use, cost per successful plan, and
regressions. Keep deterministic security assertions separate from probabilistic
quality scores. An LLM judge never replaces deterministic authorization or
policy. CI may gate stable, reproducible cases. Do not send confidential
customer content to external evaluators without explicit authorization.

### Secure agent workflows

Preserve REST, CLI, and Model Context Protocol (MCP) interfaces. Provide typed
tools, scoped capabilities, tenant identities, short-lived authorization,
validated calls, prompt-injection defenses, audit history, approval-bound
actions, replay protection, cancellation, timeouts, resource limits, and
restart recovery. Research hardened containers, gVisor, and Firecracker only
for a real untrusted-code requirement. Ordinary containers are not a virtual
machine security boundary. An agent cannot authorize its own protected change.

### Distributed backend, observability, and FinOps

Strengthen actual workflow needs with atomic claims, durable leases,
idempotency, duplicate prevention, bounded retries with backoff/jitter,
dead-letter and poison-message handling, outbox patterns where appropriate,
backpressure, concurrency limits, crash recovery, restart-safe transitions,
and independent reconciliation. Document delivery guarantees honestly; do
not infer exactly-once behavior from a queue or database.

Extend existing OpenTelemetry, Prometheus, Grafana, Tempo, and CloudWatch paths
for privacy-preserving model, provider, token, tool, workflow, queue, policy,
tenant, cost, and infrastructure observations. Define service-level objectives
and error budgets where useful. Use OpenTelemetry GenAI semantic conventions
with the convention version recorded. Never record prompts, customer data,
credentials, or responses by default.

**Phase acceptance:** demonstrate a functioning hosted AI control plane with
reproducible evaluations, approved routing, cost attribution, secure agent
interfaces, documented recovery, and observable end-to-end workflows.

## Phase 3 — Customer AI applications and inference

### Managed applications and CPU inference

Offer suitable applications using Bedrock, Lambda, ECS, App Runner where
available and appropriate, EC2, S3, OpenSearch, PostgreSQL/pgvector, or other
justified AWS services. Do not require a vector database for every retrieval
application. Select managed AI, CPU, or GPU inference from workload, privacy,
latency, cost, and security constraints.

Build one bounded self-hosted CPU inference profile using a justified runtime
such as ONNX Runtime. Verify actual model load and inference, authentication,
request bounds, readiness, latency, throughput, resource use, recovery, cost,
and teardown.

### Real cloud GPU inference

Start with the simplest appropriate EC2 GPU design before EKS. Before choosing
an accelerator, verify current regional G5/G6 or newer availability, price,
quota/capacity, model memory, and requirements. Use appropriately licensed
open-weight models and vLLM initially; compare SGLang or alternatives only
where measured needs justify it. All accelerators must be cloud-provided; no
personal GPU hardware is available.

The governed profile must address compatible NVIDIA drivers/CUDA, containerized
serving, artifact retrieval and model digest verification, private networking,
authenticated OpenAI-compatible APIs and streaming, concurrency/tenant quotas
when shared, batching, KV cache, precision/quantization, justified autoscaling,
DCGM Exporter/Prometheus observation, real inference readiness, failure
recovery, and authorized teardown.

Create reproducible benchmarks for time to first token, inter-token and total
latency (p50/p95/p99), request and token throughput, concurrency, GPU memory
and utilization, model load/cold start, error rate, cost per million input and
output tokens, cost per successful request, and recovery time. Record exact
model revision, engine, instance/accelerator, region, traffic, context,
concurrency, precision, quantization, and configuration. Compare controlled
experiments only. A fixture is not a GPU benchmark.

**Phase acceptance:** at least one real cloud GPU open-weight model is
provisioned, served, benchmarked, monitored, and destroyed through an
authorized DavDeploy workflow. Evidence includes actual accelerator telemetry
and successful model inference, not only an EC2 instance.

## Phase 4 — Kubernetes AI infrastructure and Go engineering

Add governed EKS GPU profiles only where workload requirements call for them.
Research compatible EKS accelerated AMIs, NVIDIA device plugins or Dynamic
Resource Allocation, GPU Operator, Karpenter, managed node groups, private
endpoints, Pod Identity/IRSA, GitOps, networking/security, and accelerator
metrics. Choose one compatible driver/device-management/autoscaling approach;
avoid overlapping components. Validate the exact EKS version, AMI, GPU family,
and scaler combination.

Cover GPU provisioning/placement, discovery, node health, quotas, workload
isolation, GPU-aware autoscaling, model serving, controlled rollout/rollback,
interruption handling, cost allocation, and full cluster/workload teardown.

Within the existing backend repository, evaluate Kubebuilder and
controller-runtime for a narrow Go controller and custom resource such as
`AIWorkload`, only if it adds real value over native resources. Integrate with
the existing approval/execution boundary. Implement validation, reconciliation,
idempotence, observed generation/status, owner references/finalizers, failure
backoff, leader election if required, cleanup, metrics, and least-privilege
RBAC. It cannot bypass cloud authorization or execute arbitrary customer
changes. Add Go unit, controller-runtime integration, envtest, and real-cluster
tests. Label envtest accurately: it does not prove kubelet, scheduler, GPU, or
workload behavior.

Exercise worker and Pod loss, node interruption, GPU shortage, failed model
startup, invalid specs, and controller restart. **Phase acceptance:** a real
GPU-enabled EKS workload shows actual accelerator allocation, inference,
controller reconciliation, recovery, and verified cleanup.

## Phase 5 — Distributed AI compute and parallel work

Evaluate Kueue and Kubernetes scheduling primitives for multi-tenant GPU
capacity; use Volcano only if a demonstrated gang-scheduling need warrants it.
Do not operate competing schedulers without a concrete reason. Evidence should
distinguish admission from actual Pod scheduling and cover queues, tenant quota,
capacity exhaustion, borrowing, fair sharing, priority/preemption, starvation,
recovery, topology-aware placement where supported, and dynamic capacity.

Benchmark justified inference parallelism: replicas, data/tensor/pipeline
parallelism, multi-GPU and multi-node serving, routing, and communication
overhead. Use vLLM, PyTorch, Ray, or another tool only when requirements fit;
do not deploy Ray as a checklist item.

Support small reproducible customer-controlled training/fine-tuning: single
GPU, DistributedDataParallel, multi-GPU synchronization, dataset distribution,
checkpoints, interruption/recovery, model artifacts, and reproducible configs.
Prefer appropriately sized models and consider parameter-efficient tuning
where commercially useful. Study CUDA allocation/transfer/kernel behavior,
matrix operations, precision, bandwidth/utilization, and NCCL. Claim NVLink,
EFA, RDMA, or InfiniBand only when the selected hardware actually uses it.

**Phase acceptance:** demonstrate authorized real accelerator scheduling and
at least one distributed multi-GPU workload, recording placement, communication,
performance, recovery, utilization, cost, and teardown. If capacity, quota, or
approved budget prevents a run, mark it blocked.

## Phase 6 — MLOps and model lifecycle

Research MLflow, SageMaker AI, and justified alternatives; select the simplest
appropriate design. Implement a governed dataset → training → evaluation →
registration → approval → deployment → monitoring → rollback/retirement path.

Cover versioned datasets and access, integrity, reproducible configurations,
experiment metrics, provenance, artifact digests, checkpoints, model versions,
evaluation, candidate/champion status, eligibility and retirement. Select
quality measures suited to the task: accuracy/precision/recall/F1 only where
appropriate, plus critical slices, latency, resources, cost, safety, and
regression. Do not report model drift without ground truth or a defined proxy.

Model releases need immutable plans, artifact verification, independent
approval, canary/traffic allocation, quality and latency gates, promotion,
rollback, stale-plan checks, lineage, and audit. Monitor latency, throughput,
errors, resources, measurable drift/quality, availability, cost anomalies, and
version behavior.

**Phase acceptance:** a real customer-side training or fine-tuning cycle,
evaluation, registration, approved release, inference, observed monitoring,
controlled rollback, and authorized cleanup.

## Phase 7 — AI reliability and Day-2 operations

Extend existing Day-2 operations to real tenant-authorized telemetry. Cover
inference latency, GPU saturation/memory failure, queue backlog, failed model
startup, serving regression, capacity loss, Kubernetes failure, worker crash,
training interruption, provider outage, and cost anomaly.

For an incident, collect evidence, form hypotheses, verify them deterministically,
recommend a bounded change with cost/risk and rollback assessment, produce an
immutable plan, run policy, require human approval, execute only when separately
authorized, independently verify the result, and retain incident/audit history.
AI recommends remediation; it cannot invent an incident or claim success without
observations. Demonstrate failure injection and recovery in isolated authorized
environments.

## Phase 8 — Commercial validation and product maturity

Integrate proven capabilities into the existing DavDeploy user experience.
Customers should be able to request a managed chatbot, private retrieval app,
single-GPU open model, justified Kubernetes inference platform, temporary
fine-tuning job, distributed training, shared GPU quotas, or AI workload
investigation without first learning every infrastructure technology.

When external customers authorize pilots, record actual customer evidence;
never invent adoption, production usage, or commercial impact. Improve
onboarding, status, architecture/cost explanations, performance dashboards,
support diagnostics, failure messages, security evidence, and offboarding.
Write technical case studies in the existing repository with diagrams,
reproduction steps, measured results, decisions, trade-offs, failures,
limitations, and future improvements.

## Cloud cost and execution gates

Before each paid experiment, verify current official prices, quotas, and
regional capacity; enumerate billable resources; estimate a maximum cost; obtain
authorization under the active execution policy; set a maximum runtime and
resource count; and define teardown plus independent absence checks. Include
GPU/EC2, EKS control plane, EBS/snapshots, NAT/EIP, load balancers, transfer,
model storage, registries, monitoring/logging, databases, and model API usage
as applicable. Use permitted credits and research Spot only for interruptible
work; Spot is not guaranteed and AWS Budgets are not hard spend limits.

Use project-scoped temporary environments, DavDeploy-side restrictions/expiry,
and an independently scheduled cleanup mechanism where justified. Never
destroy resources outside the exact approved environment or remove evidence
explicitly required to be retained.

## Engineering workflow and evidence rules

Follow repository `AGENTS.md`, focused branches, early draft PRs, PR-numbered
tickets, tests and CI, security/cost/reliability review, truthful acceptance
status, merge authorization, and post-merge handoff updates. Each customer
workload run gets `docs/test/testN.md` for its PR number. Respect the existing
two-minute CI interval and Terraform monitor cadence. Avoid duplicate work
across sessions by maintaining the next action and dependencies in this file.

Maintain a capability-to-evidence matrix mapping each capability to source,
tests, deployment/run identifiers, benchmarks, and limitations. Classify every
claim as architecture, source, static, local, simulated, authenticated plan,
direct cloud test, DavDeploy-driven run, same-account pilot, cross-account
customer evidence, hosted release, or real production usage. An EKS cluster is
not proof of GPU scheduling; a GPU instance is not proof of inference; a
training job start is not proof of training/recovery; fixture benchmarks are
not real measurements.

## Research starting points

Use current official documentation before implementing each relevant phase;
confirm release versions, licenses, security advisories, regional services,
pricing, quotas, and compatibility at that time. This list is not a mandate to
adopt the named technology.

- AWS Bedrock [Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html)
  and [model evaluation](https://docs.aws.amazon.com/bedrock/latest/userguide/evaluation.html).
- AWS [cross-account IAM](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_common-scenarios_third-party.html),
  [EKS AI/ML guidance](https://docs.aws.amazon.com/eks/latest/best-practices/aiml-compute.html),
  [accelerated AMIs](https://docs.aws.amazon.com/eks/latest/userguide/ml-eks-optimized-ami.html),
  [GPU device management](https://docs.aws.amazon.com/eks/latest/userguide/device-management-nvidia.html),
  and [Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html).
- NVIDIA [GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/),
  [DCGM Exporter](https://github.com/NVIDIA/dcgm-exporter),
  [CUDA](https://docs.nvidia.com/cuda/), and
  [NCCL](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/).
- Inference: [vLLM](https://docs.vllm.ai/),
  [distributed vLLM serving](https://docs.vllm.ai/en/latest/serving/parallelism_scaling/),
  and [SGLang](https://github.com/sgl-project/sglang).
- Kubernetes: [Kueue](https://kueue.sigs.k8s.io/docs/),
  [Volcano](https://volcano.sh/), [Karpenter](https://karpenter.sh/docs/),
  [Kubebuilder](https://book.kubebuilder.io/), and
  [Kubernetes documentation](https://kubernetes.io/docs/).
- Training and lifecycle: [PyTorch DDP](https://docs.pytorch.org/tutorials/intermediate/ddp_tutorial.html),
  [distributed checkpoints](https://docs.pytorch.org/tutorials/recipes/distributed_checkpoint_recipe.html),
  and [MLflow](https://mlflow.org/docs/latest/).
- Agent/evaluation/telemetry: [LiteLLM](https://docs.litellm.ai/),
  [Promptfoo](https://www.promptfoo.dev/docs/),
  [OpenTelemetry GenAI conventions](https://github.com/open-telemetry/semantic-conventions-genai),
  [OPA](https://www.openpolicyagent.org/docs/), and
  [Model Context Protocol](https://modelcontextprotocol.io/).

## Final success conditions

The full goal is complete only when DavDeploy demonstrates appropriate,
governed lifecycles for managed AI applications; secure agentic workloads; CPU
inference; real cloud GPU inference; Kubernetes accelerator infrastructure;
distributed inference and training; model evaluation, registration, release,
and rollback; AI observability and cost attribution; real incident investigation
and recovery; and authorized destruction with independent absence verification.
Do not close the goal while a critical capability is architecture-only,
simulated, or untested. Maintain separate pilot and general-availability gates;
pilot evidence does not require every profile to be generally available.

## Future handoff ledger

This goal is **queued**. No implementation package is selected yet. When it is
activated after Nova completion, fill in this ledger from the then-current
repository evidence:

| Field | At activation |
|---|---|
| Nova acceptance and closure evidence | Reconcile `COMPOSED_EXECUTION_GOAL.md`; do not infer closure |
| Backend/frontend source, deployment, and open PRs | Reconcile current GitHub state and deployed evidence |
| Existing capability reuse/gaps | Audit the evidence matrix and adapter catalogue |
| Authorized accounts, regions, budgets, quotas, retained resources | Verify under current approval boundaries |
| First dependency-ready PR and ticket | Select only after the audit; preserve PR-only workflow |
| Active work, blockers, next action | Update this ledger after each merged package |
