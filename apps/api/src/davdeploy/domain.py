from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from davdeploy.contracts import EvidenceRef


class EnvironmentName(StrEnum):
    STAGING = "staging"
    PRODUCTION = "production"


class LifecycleState(StrEnum):
    DRAFT = "DRAFT"
    ANALYZING = "ANALYZING"
    NEEDS_INPUT = "NEEDS_INPUT"
    PLANNED = "PLANNED"
    POLICY_DENIED = "POLICY_DENIED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVED = "APPROVED"
    QUEUED = "QUEUED"
    PROVISIONING = "PROVISIONING"
    DEPLOYING = "DEPLOYING"
    VERIFYING = "VERIFYING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    CHANGE_PROPOSED = "CHANGE_PROPOSED"
    FAILED = "FAILED"
    DESTROY_REQUESTED = "DESTROY_REQUESTED"
    DESTROY_APPROVAL_REQUIRED = "DESTROY_APPROVAL_REQUIRED"
    DESTROYING = "DESTROYING"
    DESTROYED = "DESTROYED"


class PlanAction(StrEnum):
    DEPLOY = "DEPLOY"
    CHANGE = "CHANGE"
    DESTROY = "DESTROY"


class IntentScope(StrEnum):
    INFRASTRUCTURE = "INFRASTRUCTURE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class InfrastructurePlanState(StrEnum):
    """Customer-facing planning lifecycle. Approval never means deployment."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class InfrastructurePlanDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PolicyResult(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


class CandidateClass(StrEnum):
    STATIC = "static"
    SERVERLESS = "serverless"
    MANAGED_APPLICATION = "managed_application"
    MANAGED_CONTAINERS = "managed_containers"
    VIRTUAL_MACHINE = "virtual_machine"
    KUBERNETES = "kubernetes"
    MANAGED_AI = "managed_ai"
    CPU_INFERENCE = "cpu_inference"
    GPU_INFERENCE = "gpu_inference"


class CloudInventorySnapshot(BaseModel):
    """Approved customer context supplied by discovery.

    ``pricing_evidence`` is read-only catalog or Cost Explorer evidence. It is
    intentionally separate from the planner's estimate so the product never
    presents historical spend or a catalog lookup as a guaranteed AWS bill.
    """

    provider: str = "aws"
    region: str = "us-east-1"
    approved_resources: list[str] = Field(default_factory=list)
    approved_regions: list[str] = Field(default_factory=lambda: ["us-east-1", "eu-west-1"])
    discovered_at: datetime
    provenance: str = "fixture"
    pricing_evidence: dict[str, Any] = Field(default_factory=dict)


class WorkloadSpec(BaseModel):
    workload_type: str
    source_repository: str | None = None
    cloud: str = "aws"
    data_classification: str = "unknown"
    average_rps: int | None = Field(default=None, ge=0)
    peak_rps: int | None = Field(default=None, ge=0)
    monthly_budget_usd: int | None = Field(default=None, ge=1)
    environments: list[EnvironmentName] = Field(default_factory=list)
    availability_target: str | None = None
    region_constraints: list[str] = Field(default_factory=list)
    model_requirements: dict[str, Any] = Field(default_factory=dict)
    integration_requirements: list[str] = Field(default_factory=list)
    runtime: str | None = None
    containerized: bool | None = None
    event_driven: bool = False
    stateful: bool = False
    requires_private_connectivity: bool = False
    requires_kubernetes: bool = False
    requires_gpu: bool = False
    multi_service: bool = False
    execution_duration_minutes: int | None = Field(default=None, ge=1)
    capability_requirements: list[str] = Field(default_factory=list, max_length=40)
    existing_approved_resources: list[str] = Field(default_factory=list)
    repository_analysis: dict[str, Any] = Field(default_factory=dict)
    field_status: dict[str, str] = Field(default_factory=dict)
    unknowns: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    provenance: dict[str, str] = Field(default_factory=dict)


class MaterialQuestion(BaseModel):
    field: str
    question: str
    reason: str


class IntentInterpretation(BaseModel):
    spec: WorkloadSpec | None
    questions: list[MaterialQuestion] = Field(default_factory=list)
    model_metadata: dict[str, Any] | None = None
    request_scope: IntentScope = IntentScope.INFRASTRUCTURE


class ArchitectureComponent(BaseModel):
    name: str
    purpose: str
    service: str
    private: bool = True


class ModuleInputBinding(BaseModel):
    """Reference one declared output to one declared input without carrying values."""

    model_config = ConfigDict(extra="forbid")

    input_name: str
    source_instance_id: str
    source_output: str


class ModulePort(BaseModel):
    name: str
    value_type: Literal[
        "resource_name", "aws_arn", "aws_queue_url", "secret_reference", "https_url"
    ]
    secret_reference_only: bool = False


class ArchitectureModule(BaseModel):
    """One selected internal building block in a composed architecture.

    Modules are an internal product boundary.  They are deliberately not an
    AWS-service picker exposed to customers.
    """

    identifier: str
    instance_id: str | None = None
    display_name: str
    purpose: str
    stage: str
    services: list[str]
    depends_on: list[str] = Field(default_factory=list)
    input_bindings: list[ModuleInputBinding] = Field(default_factory=list)
    execution_supported: bool = False


class ModuleContract(BaseModel):
    """Versioned internal desired-state boundary for a selected module."""

    module_id: str
    version: str
    resources: list[str]
    policy_controls: list[str]
    observation: list[str]
    destroy_supported: bool = False
    inputs: list[ModulePort] = Field(default_factory=list)
    outputs: list[ModulePort] = Field(default_factory=list)


class ModuleExecutionContract(BaseModel):
    module_id: str
    execution_state: str
    prerequisites: list[str]
    health_evidence: list[str]
    rollback_strategy: str
    destroy_strategy: str


class OperationalReadiness(BaseModel):
    cost_evidence_state: str
    quota_evidence_state: str
    health_checks: list[str]
    incident_controls: list[str]
    recovery_controls: list[str]


class CommercialReadiness(BaseModel):
    onboarding: list[str]
    support: list[str]
    entitlement_state: str
    billing_boundary: str


class CostRange(BaseModel):
    currency: str = "USD"
    monthly_low: int
    monthly_high: int
    assumptions: list[str]
    catalog_version: str
    estimated_at: datetime


class CostComponent(BaseModel):
    category: str
    monthly_low: int
    monthly_high: int
    reason: str


class MonitoringSpecification(BaseModel):
    metrics_backend: str = "Prometheus-compatible Amazon Managed Service for Prometheus"
    dashboard: str = "Amazon Managed Grafana"
    scrape_targets: list[str]
    baseline_dashboard: str
    access_boundary: str
    coverage: list[str]
    limitations: list[str]
    cost_assumption: str


class ArchitectureCandidate(BaseModel):
    candidate_id: str
    candidate_class: CandidateClass
    display_name: str
    provider: str = "aws"
    region: str
    components: list[ArchitectureComponent]
    cost_estimate: CostRange
    cost_components: list[CostComponent]
    operational_complexity: int = Field(ge=1, le=5)
    complexity_reasons: list[str]
    satisfies: list[str]
    rejected_reasons: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    existing_resources_reused: list[str] = Field(default_factory=list)
    new_resources_required: list[str] = Field(default_factory=list)
    valid: bool = True
    upgrade_triggers: list[str] = Field(default_factory=list)


class ArchitecturePlan(BaseModel):
    profile: str
    cloud: str = "aws"
    region: str
    components: list[ArchitectureComponent]
    modules: list[ArchitectureModule] = Field(default_factory=list)
    module_contracts: list[ModuleContract] = Field(default_factory=list)
    module_execution: list[ModuleExecutionContract] = Field(default_factory=list)
    operational_readiness: OperationalReadiness | None = None
    commercial_readiness: CommercialReadiness | None = None
    dependencies: list[str]
    assumptions: list[str]
    security_controls: list[str]
    cost_estimate: CostRange
    cost_components: list[CostComponent] = Field(default_factory=list)
    observability: MonitoringSpecification
    estimated_capacity: str
    risks: list[str]
    alternatives: list[str]
    operational_characteristics: list[str]
    rollback_strategy: str
    execution_steps: list[str]
    selected_candidate_id: str | None = None
    candidates: list[ArchitectureCandidate] = Field(default_factory=list)
    complexity_score: int | None = Field(default=None, ge=1, le=5)
    recommendation_reason: str | None = None
    simplest_viable_explanation: str | None = None
    existing_resources_reused: list[str] = Field(default_factory=list)
    new_resources_required: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    evidence_limitations: list[str] = Field(default_factory=list)


class TelemetryEvidence(BaseModel):
    """A bounded, explainable telemetry snapshot for the local Day-2 fixture."""

    source: str
    captured_at: datetime
    p95_latency_ms: int = Field(ge=0)
    queue_time_ms: int = Field(ge=0)
    utilization_percent: int = Field(ge=0, le=100)
    current_min_replicas: int = Field(ge=1)


class OptimizationRecommendation(BaseModel):
    recommendation_id: str
    diagnosis: str
    evidence: TelemetryEvidence
    proposed_change: dict[str, Any]
    estimated_monthly_cost_delta: CostRange
    risk: str
    rollback: str
    assumptions: list[str]
    requires_approval: bool
    execution_boundary: str


class IntentRequest(BaseModel):
    project_id: str
    prompt: str = Field(min_length=20, max_length=10_000)
    source_repository: str | None = None
    cloud_connection_id: str | None = None
    idempotency_key: str = Field(min_length=8, max_length=128)


class ProjectRequest(BaseModel):
    name: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9 .,'()&-]{2,63}$",
    )
    repository_url: HttpUrl | None = None
    repository_branch: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._/-]{1,255}$")


class CloudConnectionRequest(BaseModel):
    display_name: str = Field(min_length=3, max_length=100)
    provider: str = Field(default="aws", pattern=r"^aws$")
    connection_mode: str = Field(default="byoc_role_contract", pattern=r"^byoc_role_contract$")


class AwsQuickCreateRequest(BaseModel):
    account_id: str = Field(pattern=r"^[0-9]{12}$")
    access_mode: str = Field(
        default="discovery", pattern=r"^(discovery|plan-only|administrator-pilot)$"
    )
    acknowledge_administrator_access: bool = False


class AwsExistingRoleRequest(BaseModel):
    account_id: str = Field(pattern=r"^[0-9]{12}$")
    discovery_role_arn: str = Field(pattern=r"^arn:aws:iam::[0-9]{12}:role/.+$")
    execution_role_arn: str | None = Field(
        default=None, pattern=r"^arn:aws:iam::[0-9]{12}:role/.+$"
    )


class AwsConnectionVerificationRequest(BaseModel):
    region: str = Field(default="us-east-1", pattern=r"^[a-z]{2}-[a-z]+-\d$")


class CloudInventorySnapshotRequest(BaseModel):
    """Credential-free discovery result received from the trusted discovery worker."""

    region: str = Field(pattern=r"^[a-z]{2}-[a-z]+-\d$")
    provenance: str = Field(min_length=3, max_length=80)
    captured_at: datetime
    snapshot: dict[str, Any]


class ApprovalRequest(BaseModel):
    plan_hash: str = Field(min_length=64, max_length=64)


class GeneratedPlanArtifactApprovalRequest(BaseModel):
    """Human approval binds one immutable generated-plan manifest digest."""

    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class GeneratedPlanRunRequest(BaseModel):
    """Request a generated plan for one exact immutable customer revision."""

    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class TerraformStateCredentialRequest(BaseModel):
    """Only a durable run ID is sent; CodeBuild identity comes from SigV4."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(pattern=r"^[0-9a-f-]{36}$")


class NovaPlanCredentialRequest(BaseModel):
    """Only a durable run ID is caller-provided; build identity comes from SigV4."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(pattern=r"^[0-9a-f-]{36}$")


class GeneratedPlanInputReconciliationRequest(BaseModel):
    """Resolve only an ambiguous S3 input-stage attempt before any build starts."""

    abandon_attempt: bool = False


class GeneratedPlanGenerationReconciliationRequest(BaseModel):
    """Require explicit confirmation before abandoning an uncertain or pre-call attempt."""

    abandon_attempt: Literal[True]


class InfrastructurePlanDecisionRequest(BaseModel):
    decision: InfrastructurePlanDecision
    content_digest: str = Field(min_length=64, max_length=64)
    reason: str | None = Field(default=None, max_length=2_000)


class DesiredStatePublicationRequest(BaseModel):
    content_digest: str = Field(min_length=64, max_length=64)


class DesiredStatePublicationStateRequest(BaseModel):
    content_digest: str = Field(min_length=64, max_length=64)
    state: str = Field(pattern=r"^(CHECKS_PENDING|CHECKS_PASSED|CLOSED)$")


class TerraformPlanRenderRequest(BaseModel):
    content_digest: str = Field(min_length=64, max_length=64)


class CloudReadinessPreflightRequest(BaseModel):
    content_digest: str = Field(min_length=64, max_length=64)
    expected_account_id: str | None = Field(default=None, pattern=r"^[0-9]{12}$")
    allowed_regions: list[str] = Field(default_factory=lambda: ["us-east-1"], max_length=20)
    required_tags: dict[str, str] = Field(default_factory=dict, max_length=20)
    budget_ceiling_usd: int | None = Field(default=None, ge=1)
    execution_mode: str = Field(default="DRY_RUN_ONLY", pattern=r"^(DRY_RUN_ONLY|PLAN_ONLY)$")
    require_reviewed_pr: bool = True
    runtime_identity_configured: bool = False


class TerraformPlanReviewRequest(BaseModel):
    content_digest: str = Field(min_length=64, max_length=64)
    preflight_id: str | None = None
    expected_account_id: str | None = Field(default=None, pattern=r"^[0-9]{12}$")
    expected_region: str | None = Field(default=None, pattern=r"^[a-z]{2}-[a-z]+-\d$")
    mode: str = Field(
        default="LOCAL_CONTRACT_ONLY",
        pattern=r"^(LOCAL_CONTRACT_ONLY|AUTHENTICATED_TERRAFORM_PLAN|AUTHENTICATED_TERRAFORM_DESTROY_PLAN)$",
    )
    allow_cloud_plan: bool = False


class CloudExecutionRunRequest(BaseModel):
    content_digest: str = Field(min_length=64, max_length=64)
    terraform_render_id: str | None = None
    preflight_id: str | None = None
    terraform_plan_review_id: str | None = None
    expected_account_id: str | None = Field(default=None, pattern=r"^[0-9]{12}$")
    expected_region: str | None = Field(default=None, pattern=r"^[a-z]{2}-[a-z]+-\d$")
    mode: str = Field(
        default="GUARDED_CLOUD_EXECUTION",
        pattern=r"^(GUARDED_CLOUD_EXECUTION|AUTHENTICATED_APP_RUNNER_APPLY|AUTHENTICATED_APP_RUNNER_DESTROY|AUTHENTICATED_APP_RUNNER_IMAGE_BUILD|AUTHENTICATED_SERVERLESS_CERTIFICATION)$",
    )
    confirmation: str | None = None
    serverless_operation: str | None = Field(
        default=None,
        pattern=r"^(build-artifact|plan|apply-saved-plan|health|destroy-plan|destroy-saved-plan|verify-cleanup)$",
    )
    prior_run_id: str | None = Field(default=None, min_length=1, max_length=36)
    source_commit: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{40}$")


class CloudExecutionExecuteRequest(BaseModel):
    content_digest: str = Field(min_length=64, max_length=64)
    confirmation: str = Field(min_length=1, max_length=80)


class InfrastructurePlanRevisionRequest(BaseModel):
    """New customer-plan draft content. The preceding revision is never edited."""

    content: dict[str, Any]


class InfrastructurePlanConstraintUpdateRequest(BaseModel):
    """User-editable planning constraints for a new draft revision."""

    monthly_budget_usd: int | None = Field(default=None, ge=1)
    region: str | None = Field(default=None, pattern=r"^[a-z]{2}-[a-z]+-\d$")
    environment: list[EnvironmentName] | None = None
    data_classification: str | None = Field(default=None, pattern=r"^(public|internal|restricted)$")
    availability_target: str | None = Field(default=None, pattern=r"^99\\.(9|99)%$")
    workload_type: str | None = Field(default=None, min_length=2, max_length=80)
    public_access: bool | None = None
    accepted_assumptions: list[str] = Field(default_factory=list, max_length=20)
    rejected_assumptions: list[str] = Field(default_factory=list, max_length=20)


class LocalLoginRequest(BaseModel):
    username: str = Field(min_length=2, max_length=80)


class OnboardingRequest(BaseModel):
    workspace_name: str = Field(min_length=2, max_length=100)
    invitation_token: str | None = Field(default=None, min_length=16, max_length=160)


class InvitationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=240)
    role: str = Field(default="developer", pattern=r"^(developer|operator|administrator)$")


class ApiCredentialRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    scopes: list[str] = Field(default_factory=lambda: ["read"], max_length=12)


class PlanCommentRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class BlogPostRequest(BaseModel):
    slug: str = Field(min_length=3, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=3, max_length=180)
    summary: str = Field(min_length=12, max_length=360)
    body: str = Field(min_length=1, max_length=40_000)
    state: str = Field(default="DRAFT", pattern=r"^(DRAFT|PUBLISHED)$")


class BlogCommentRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class SupportTicketRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=160)
    body: str = Field(min_length=1, max_length=8000)


class SupportTicketStateRequest(BaseModel):
    state: str = Field(pattern=r"^(OPEN|IN_PROGRESS|RESOLVED|CLOSED)$")


class DataLifecycleRequestBody(BaseModel):
    request_type: str = Field(pattern=r"^(EXPORT|DELETE)$")


class MembershipRoleRequest(BaseModel):
    role: str = Field(pattern=r"^(developer|operator|administrator)$")


class SubscriptionRequest(BaseModel):
    plan_name: str = Field(min_length=2, max_length=80)
    state: str = Field(default="ACTIVE", pattern=r"^(TRIAL|ACTIVE|PAST_DUE|CANCELED)$")
    limits: dict[str, int] = Field(default_factory=dict, max_length=20)
