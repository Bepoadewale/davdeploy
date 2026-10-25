"""Versioned platform contracts for scale-ready davdeploy boundaries.

These contracts are deliberately transport-neutral.  They can be carried by the
current PostgreSQL worker and later by SQS/EventBridge, an external model
provider, or an isolated execution runner without changing their meaning.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

CONTRACT_VERSION = "2026-10-1"


class ContractBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: str = CONTRACT_VERSION


class ContractEnvelope(ContractBase):
    """Versioned wrapper for legacy/domain payloads during schema evolution."""

    contract_type: str = Field(min_length=1, max_length=120)
    tenant: TenantScope
    project_id: str | None = Field(default=None, max_length=160)
    environment_id: str | None = Field(default=None, max_length=160)
    payload: dict[str, Any] = Field(default_factory=dict)
    source_evidence: tuple[EvidenceRef, ...] = ()
    provenance: dict[str, str] = Field(default_factory=dict)
    policy_version: str | None = Field(default=None, max_length=120)
    catalog_version: str | None = Field(default=None, max_length=160)
    plan_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TenantScope(ContractBase):
    """Mandatory scope carried through every platform operation."""

    organization_id: str = Field(min_length=1, max_length=160)
    workspace_id: str = Field(min_length=1, max_length=160)
    project_id: str | None = Field(default=None, max_length=160)
    environment_id: str | None = Field(default=None, max_length=160)
    actor_id: str = Field(min_length=1, max_length=160)
    cell_id: str = Field(default="local", min_length=1, max_length=120)
    home_region: str = Field(default="local", min_length=1, max_length=80)


class EvidenceKind(StrEnum):
    USER_CONFIRMED = "user_confirmed"
    REPOSITORY = "repository"
    AWS_API = "aws_api"
    PRICING_CATALOG = "pricing_catalog"
    MODEL_INFERENCE = "model_inference"
    POLICY = "policy"
    OBSERVATION = "observation"
    FIXTURE = "fixture"


class EvidenceRef(ContractBase):
    """A pointer to evidence; raw secrets and large payloads stay elsewhere."""

    evidence_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    tenant: TenantScope
    kind: EvidenceKind
    source: str = Field(min_length=1, max_length=240)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    content_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    location: str | None = Field(default=None, max_length=500)
    freshness_seconds: int | None = Field(default=None, ge=0)
    limitations: tuple[str, ...] = ()


class ModelPurpose(StrEnum):
    INTENT_EXTRACTION = "intent_extraction"
    CLARIFICATION = "clarification"
    PLAN_EXPLANATION = "plan_explanation"
    EVIDENCE_SUMMARY = "evidence_summary"
    TERRAFORM_GENERATION = "terraform_generation"


class ModelRequest(ContractBase):
    """Safe metadata for a model call; prompt content is never execution authority."""

    request_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    tenant: TenantScope
    purpose: ModelPurpose
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=160)
    prompt_version: str = Field(min_length=1, max_length=120)
    input_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    timeout_seconds: int = Field(default=60, ge=1, le=900)
    max_output_tokens: int = Field(default=2_000, ge=1, le=100_000)
    data_policy: str = Field(default="customer-data-controlled", max_length=120)


class ModelUsage(ContractBase):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    retry_count: int = Field(default=0, ge=0)
    measured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ModelResponse(ContractBase):
    request: ModelRequest
    output: dict[str, Any]
    evidence: tuple[EvidenceRef, ...] = ()
    usage: ModelUsage | None = None
    finish_reason: str = Field(default="stop", min_length=1, max_length=80)
    safety_result: str = Field(default="validated-schema-only", min_length=1, max_length=120)


class JobKind(StrEnum):
    INTENT = "intent"
    PLANNING = "planning"
    GITHUB = "github"
    AWS_DISCOVERY = "aws_discovery"
    TERRAFORM = "terraform"
    OBSERVATION = "observation"
    BILLING = "billing"
    NOTIFICATION = "notification"
    REMEDIATION = "remediation"


class ExecutionOperation(StrEnum):
    """Operations an isolated runner may perform; never arbitrary commands."""

    PLAN = "plan"
    APPLY = "apply"
    OBSERVE = "observe"
    DESTROY = "destroy"


class ExecutionPlacement(ContractBase):
    """Cell-ready placement metadata without coupling the domain to a topology."""

    cell_id: str = Field(default="local", min_length=1, max_length=120)
    region: str = Field(default="local", min_length=1, max_length=80)
    provider: str = Field(default="local", min_length=1, max_length=80)
    isolation_class: str = Field(default="tenant-cell", min_length=1, max_length=80)


class ExecutionContext(ContractBase):
    """Bounded execution input. It carries references, never reusable credentials."""

    execution_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    tenant: TenantScope
    placement: ExecutionPlacement = Field(default_factory=ExecutionPlacement)
    plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    operation: ExecutionOperation
    allowed_operations: tuple[ExecutionOperation, ...] = ()
    credential_reference: str | None = Field(default=None, max_length=240)
    requested_commands: tuple[str, ...] = ()
    timeout_seconds: int = Field(default=900, ge=1, le=86_400)
    network_policy: str = Field(default="isolated-runner", min_length=1, max_length=120)
    filesystem_policy: str = Field(default="ephemeral-workspace", min_length=1, max_length=120)
    credential_scope: str = Field(default="reference-only", min_length=1, max_length=120)


class ExecutionOutcome(ContractBase):
    """Observed runner result with safe outputs only."""

    execution_id: str
    tenant: TenantScope
    state: str = Field(min_length=1, max_length=80)
    observed: bool = False
    outputs: dict[str, str] = Field(default_factory=dict)
    failure_reason: str | None = None
    runner: str = Field(min_length=1, max_length=120)


class JobEnvelope(ContractBase):
    """Transport-neutral durable job metadata."""

    job_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    tenant: TenantScope
    kind: JobKind
    idempotency_key: str = Field(min_length=8, max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)
    attempt: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1, le=20)
    timeout_seconds: int = Field(default=900, ge=1, le=86_400)
    trace_id: str | None = Field(default=None, max_length=128)
    not_before: datetime | None = None


class CapabilityKind(StrEnum):
    COMPUTE = "compute"
    DATABASE = "database"
    STORAGE = "storage"
    NETWORKING = "networking"
    SECURITY = "security"
    OBSERVABILITY = "observability"
    AI_RUNTIME = "ai_runtime"
    EXECUTION = "execution"


class CapabilityRequirement(ContractBase):
    kind: CapabilityKind
    name: str = Field(min_length=1, max_length=120)
    required: bool = True
    constraints: dict[str, Any] = Field(default_factory=dict)
    evidence: tuple[EvidenceRef, ...] = ()


class ProviderCapability(ContractBase):
    provider: str = Field(min_length=1, max_length=80)
    kind: CapabilityKind
    name: str = Field(min_length=1, max_length=120)
    regions: tuple[str, ...] = ()
    limits: dict[str, Any] = Field(default_factory=dict)
    operational_complexity: int = Field(ge=1, le=5)
    catalog_version: str = Field(min_length=1, max_length=160)
    evidence: tuple[EvidenceRef, ...] = ()


class CostEvidence(ContractBase):
    currency: str = Field(default="USD", min_length=3, max_length=3)
    monthly_low: float = Field(ge=0)
    monthly_high: float = Field(ge=0)
    catalog_version: str = Field(min_length=1, max_length=160)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    assumptions: tuple[str, ...] = ()
    actual_billing: bool = False

    @field_validator("monthly_high")
    @classmethod
    def high_not_below_low(cls, value: float, info: Any) -> float:
        low = info.data.get("monthly_low")
        if low is not None and value < low:
            raise ValueError("monthly_high cannot be below monthly_low")
        return value


class PlanningEvidence(ContractBase):
    """Evidence inputs used to explain a recommendation."""

    tenant: TenantScope
    repository: tuple[EvidenceRef, ...] = ()
    inventory: tuple[EvidenceRef, ...] = ()
    pricing: CostEvidence | None = None
    capabilities: tuple[EvidenceRef, ...] = ()
    limitations: tuple[str, ...] = ()
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def references(self) -> tuple[EvidenceRef, ...]:
        return self.repository + self.inventory + self.capabilities


class UsageEvent(ContractBase):
    """Metering input; billing is a later consumer, not an authority here."""

    event_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    tenant: TenantScope
    event_type: str = Field(min_length=1, max_length=120)
    quantity: float = Field(default=1, gt=0)
    unit: str = Field(min_length=1, max_length=60)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = Field(min_length=1, max_length=120)
    correlation_id: str | None = Field(default=None, max_length=160)
    metadata: dict[str, str] = Field(default_factory=dict)


class Entitlement(ContractBase):
    """Tenant-scoped admission rule; billing systems may consume it later."""

    entitlement_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    tenant: TenantScope
    event_type: str = Field(min_length=1, max_length=120)
    limit: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=60)
    window_seconds: int = Field(default=86_400, ge=1, le=31_536_000)
    policy_version: str = Field(default="local-v1", min_length=1, max_length=80)


class UsageDecision(ContractBase):
    """Deterministic admission result. It is not a billing invoice."""

    tenant: TenantScope
    event_type: str
    allowed: bool
    consumed: float = Field(ge=0)
    limit: float = Field(gt=0)
    unit: str
    remaining: float = Field(ge=0)
    reason: str = Field(min_length=1, max_length=240)
    policy_version: str = Field(min_length=1, max_length=80)


class DomainContractV1(ContractBase):
    """Common envelope for durable, externally versioned domain records."""

    tenant: TenantScope
    project_id: str | None = Field(default=None, max_length=160)
    environment_id: str | None = Field(default=None, max_length=160)
    actor_id: str = Field(min_length=1, max_length=160)
    source_evidence: tuple[EvidenceRef, ...] = ()
    provenance: dict[str, str] = Field(default_factory=dict)
    policy_version: str = Field(default="local-v1", min_length=1, max_length=120)
    catalog_version: str = Field(default="local-v1", min_length=1, max_length=160)
    plan_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WorkloadSpecV1(DomainContractV1):
    contract_type: str = "WorkloadSpec.v1"
    workload_type: str = Field(min_length=1, max_length=120)
    requirements: dict[str, Any] = Field(default_factory=dict)


class ArchitecturePlanV1(DomainContractV1):
    contract_type: str = "ArchitecturePlan.v1"
    architecture_family: str = Field(min_length=1, max_length=160)
    components: tuple[str, ...] = ()
    used_evidence: tuple[str, ...] = ()
    inferences: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    rejected_alternatives: tuple[str, ...] = ()
    policy_reasons: tuple[str, ...] = ()
    decision_scores: dict[str, int] = Field(default_factory=dict)


class DeploymentPlanV1(DomainContractV1):
    contract_type: str = "DeploymentPlan.v1"
    target: str = Field(min_length=1, max_length=160)
    operations: tuple[ExecutionOperation, ...] = ()
    runner_id: str | None = Field(default=None, max_length=160)


class ApprovalV1(DomainContractV1):
    contract_type: str = "Approval.v1"
    approval_id: str = Field(min_length=1, max_length=160)
    operation: str = Field(min_length=1, max_length=120)
    decision: str = Field(min_length=1, max_length=80)
    scope: dict[str, str] = Field(default_factory=dict)
    reason: str | None = Field(default=None, max_length=500)


class ExecutionJobV1(DomainContractV1):
    contract_type: str = "ExecutionJob.v1"
    job: JobEnvelope
    runner_limits: dict[str, Any] = Field(default_factory=dict)


class ObservedStateV1(DomainContractV1):
    contract_type: str = "ObservedState.v1"
    state: str = Field(min_length=1, max_length=80)
    resources: tuple[str, ...] = ()
    health: str = Field(default="unknown", min_length=1, max_length=80)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditEventV1(DomainContractV1):
    contract_type: str = "AuditEvent.v1"
    event_id: str = Field(min_length=1, max_length=160)
    event_type: str = Field(min_length=1, max_length=160)
    entity_type: str = Field(min_length=1, max_length=120)
    entity_id: str = Field(min_length=1, max_length=160)
    details: dict[str, str] = Field(default_factory=dict)


class CostEstimateV1(DomainContractV1):
    contract_type: str = "CostEstimate.v1"
    estimate: CostEvidence
    complexity_score: int = Field(default=1, ge=1, le=5)
    risk_score: int = Field(default=1, ge=1, le=5)
    reliability_score: int = Field(default=1, ge=1, le=5)
    capacity_score: int = Field(default=1, ge=1, le=5)


class RecommendationV1(DomainContractV1):
    contract_type: str = "Recommendation.v1"
    recommendation_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)
    rationale: str = Field(min_length=1, max_length=2_000)
    outcome_reference: str | None = Field(default=None, max_length=240)


class ResourceRecordV1(DomainContractV1):
    contract_type: str = "ResourceRecord.v1"
    resource_id: str = Field(min_length=1, max_length=160)
    resource_type: str = Field(min_length=1, max_length=120)
    provider: str = Field(default="local", min_length=1, max_length=80)
    ownership: str = Field(default="customer", min_length=1, max_length=80)
    health: str = Field(default="unknown", min_length=1, max_length=80)
    last_verified_at: datetime | None = None
    evidence_links: tuple[str, ...] = ()


class EnvironmentOutputV1(DomainContractV1):
    contract_type: str = "EnvironmentOutput.v1"
    output_id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=160)
    value: str = Field(min_length=1, max_length=4_000)
    sensitive: bool = False
    source_resource_id: str | None = Field(default=None, max_length=160)


class EvidenceDecisionV1(DomainContractV1):
    contract_type: str = "EvidenceDecision.v1"
    decision_id: str = Field(min_length=1, max_length=160)
    used_evidence: tuple[str, ...] = ()
    inferences: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    rejected_alternatives: tuple[str, ...] = ()
    policy_reasons: tuple[str, ...] = ()
    outcome_reference: str | None = Field(default=None, max_length=240)


ContractEnvelope.model_rebuild()
