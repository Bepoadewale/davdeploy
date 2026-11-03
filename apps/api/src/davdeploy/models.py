from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProductUser(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    subject: Mapped[str] = mapped_column(String(160), unique=True)
    role: Mapped[str] = mapped_column(String(32))


class WorkspaceInvitation(Base):
    """Tenant-scoped, expiring invitation. The raw token is never persisted."""

    __tablename__ = "workspace_invitations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(String(240), index=True)
    role: Mapped[str] = mapped_column(String(32), default="developer")
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    state: Mapped[str] = mapped_column(String(24), default="PENDING", index=True)
    delivery_state: Mapped[str] = mapped_column(String(24), default="PENDING", index=True)
    delivery_provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    send_count: Mapped[int] = mapped_column(default=0)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    invited_by_subject: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApiCredential(Base):
    """Hashed, scoped local API credential; secret material is returned only once."""

    __tablename__ = "api_credentials"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by_subject: Mapped[str] = mapped_column(String(160))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PlanComment(Base):
    __tablename__ = "plan_comments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    revision_id: Mapped[str] = mapped_column(ForeignKey("infrastructure_plan_revisions.id"), index=True)
    author_subject: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(24), default="OPEN", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BlogPost(Base):
    """Public editorial content, authored only by verified DavDeploy team email accounts."""

    __tablename__ = "blog_posts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(180))
    summary: Mapped[str] = mapped_column(String(360))
    body: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(24), default="DRAFT", index=True)
    author_subject: Mapped[str] = mapped_column(String(160), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BlogComment(Base):
    """A signed-in reader's public response to a published editorial post."""

    __tablename__ = "blog_comments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    post_id: Mapped[str] = mapped_column(ForeignKey("blog_posts.id"), index=True)
    author_subject: Mapped[str] = mapped_column(String(160), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UsageRecord(Base):
    __tablename__ = "usage_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    metric: Mapped[str] = mapped_column(String(80), index=True)
    quantity: Mapped[int] = mapped_column(default=1)
    source: Mapped[str] = mapped_column(String(80), default="api")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkspaceSubscription(Base):
    """Provider-neutral commercial state; no payment processor is implied."""

    __tablename__ = "workspace_subscriptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), unique=True, index=True)
    plan_name: Mapped[str] = mapped_column(String(80), default="beta")
    state: Mapped[str] = mapped_column(String(24), default="TRIAL")
    limits: Mapped[dict] = mapped_column(JSON, default=dict)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SupportTicket(Base):
    __tablename__ = "support_tickets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    subject: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(24), default="OPEN", index=True)
    created_by_subject: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataLifecycleRequest(Base):
    __tablename__ = "data_lifecycle_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    request_type: Mapped[str] = mapped_column(String(32), index=True)
    state: Mapped[str] = mapped_column(String(24), default="REQUESTED", index=True)
    requested_by_subject: Mapped[str] = mapped_column(String(160))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    repository_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_project_org_name"),)


class RepositoryConnection(Base):
    __tablename__ = "repository_connections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="github")
    repository_url: Mapped[str] = mapped_column(Text)
    selected_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)


class StoredRepositoryAnalysis(Base):
    """Credential-free GitHub repository facts used by the planner and review."""

    __tablename__ = "repository_analyses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    repository_url: Mapped[str] = mapped_column(Text)
    selected_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    execution: Mapped[str] = mapped_column(String(40))
    analysis: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GitHubAppInstallationState(Base):
    """Tenant-scoped GitHub App installation state derived from signed webhooks."""

    __tablename__ = "github_app_installations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    installation_id: Mapped[str] = mapped_column(String(80), index=True)
    account_login: Mapped[str] = mapped_column(String(160))
    account_type: Mapped[str] = mapped_column(String(40), default="Organization")
    state: Mapped[str] = mapped_column(String(40), default="CONNECTED", index=True)
    repository_selection: Mapped[str] = mapped_column(String(40), default="selected")
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    last_event: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "installation_id", name="uq_github_installation_org"
        ),
    )


class GitHubWebhookDelivery(Base):
    """Deduplicated GitHub webhook delivery audit; payloads never store secrets."""

    __tablename__ = "github_webhook_deliveries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    delivery_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    event: Mapped[str] = mapped_column(String(80))
    action: Mapped[str | None] = mapped_column(String(80), nullable=True)
    installation_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    repository: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="PROCESSED")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CloudConnection(Base):
    __tablename__ = "cloud_connections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="aws")
    display_name: Mapped[str] = mapped_column(String(100))
    connection_mode: Mapped[str] = mapped_column(String(64), default="byoc_role_contract")
    account_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    discovery_role_arn: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A separate customer-approved role. Discovery never receives these permissions.
    execution_role_arn: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A reference to a control-plane secret. Never persist the customer's ExternalId here.
    external_id_secret_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    setup_state: Mapped[str] = mapped_column(String(32), default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StoredCloudInventorySnapshot(Base):
    """A customer-owned, credential-free record returned by a discovery run."""

    __tablename__ = "cloud_inventory_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    cloud_connection_id: Mapped[str] = mapped_column(ForeignKey("cloud_connections.id"), index=True)
    region: Mapped[str] = mapped_column(String(32))
    provenance: Mapped[str] = mapped_column(String(80))
    snapshot: Mapped[dict] = mapped_column(JSON)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CloudDiscoveryJob(Base):
    """Durable, tenant-scoped work item for a read-only AWS discovery run."""

    __tablename__ = "cloud_discovery_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    cloud_connection_id: Mapped[str] = mapped_column(ForeignKey("cloud_connections.id"), index=True)
    requester_subject: Mapped[str] = mapped_column(String(160))
    region: Mapped[str] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PlatformJob(Base):
    """Transport-neutral job record used by the future queue adapter."""

    __tablename__ = "platform_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    workspace_id: Mapped[str] = mapped_column(String(160), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(32), default="QUEUED", index=True)
    envelope: Mapped[dict] = mapped_column(JSON)
    attempt: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=3)
    timeout_seconds: Mapped[int] = mapped_column(default=900)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_platform_job_org_idempotency"
        ),
    )


class WorkloadIntent(Base):
    __tablename__ = "workload_intents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    requester_subject: Mapped[str] = mapped_column(String(160))
    prompt: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(40))
    spec: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_intent_idempotency"),
    )


class StoredArchitecturePlan(Base):
    __tablename__ = "architecture_plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    intent_id: Mapped[str] = mapped_column(ForeignKey("workload_intents.id"), unique=True)
    plan: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InfrastructurePlan(Base):
    """Customer-facing plan container; it is separate from executable DeploymentPlan."""

    __tablename__ = "infrastructure_plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    creator_subject: Mapped[str] = mapped_column(String(160), index=True)
    title: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InfrastructurePlanRevision(Base):
    """An immutable snapshot once submitted, approved, or rejected."""

    __tablename__ = "infrastructure_plan_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    infrastructure_plan_id: Mapped[str] = mapped_column(
        ForeignKey("infrastructure_plans.id"), index=True
    )
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    revision_number: Mapped[int] = mapped_column()
    state: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    content: Mapped[dict] = mapped_column(JSON)
    content_digest: Mapped[str] = mapped_column(String(64), index=True)
    submitted_by_subject: Mapped[str | None] = mapped_column(String(160), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (
        UniqueConstraint(
            "infrastructure_plan_id", "revision_number", name="uq_infrastructure_plan_revision"
        ),
    )


class InfrastructurePlanDecisionRecord(Base):
    __tablename__ = "infrastructure_plan_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    revision_id: Mapped[str] = mapped_column(
        ForeignKey("infrastructure_plan_revisions.id"), unique=True, index=True
    )
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    decision: Mapped[str] = mapped_column(String(16))
    approver_subject: Mapped[str] = mapped_column(String(160))
    creator_subject: Mapped[str] = mapped_column(String(160))
    is_self_approval: Mapped[bool] = mapped_column(default=False)
    approved_digest: Mapped[str] = mapped_column(String(64))
    authorization_policy: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DesiredStatePublication(Base):
    """Fixture PR publication for an approved customer-plan revision."""

    __tablename__ = "desired_state_publications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    revision_id: Mapped[str] = mapped_column(ForeignKey("infrastructure_plan_revisions.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    repository_url: Mapped[str] = mapped_column(Text)
    branch: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(40), default="NOT_CREATED", index=True)
    publication_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_checks: Mapped[dict] = mapped_column(JSON, default=dict)
    package: Mapped[dict] = mapped_column(JSON, default=dict)
    content_digest: Mapped[str] = mapped_column(String(64), index=True)
    created_by_subject: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        UniqueConstraint("revision_id", "content_digest", name="uq_desired_state_revision_digest"),
    )


class TerraformPlanRender(Base):
    """Plan-only Terraform contract generated from an approved customer-plan revision."""

    __tablename__ = "terraform_plan_renders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    revision_id: Mapped[str] = mapped_column(ForeignKey("infrastructure_plan_revisions.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    profile: Mapped[str] = mapped_column(String(80), index=True)
    state: Mapped[str] = mapped_column(String(40), default="PLAN_ONLY_NOT_APPLIED", index=True)
    terraform_root: Mapped[str] = mapped_column(Text)
    module_path: Mapped[str] = mapped_column(Text)
    render: Mapped[dict] = mapped_column(JSON, default=dict)
    content_digest: Mapped[str] = mapped_column(String(64), index=True)
    created_by_subject: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        UniqueConstraint("revision_id", "content_digest", "profile", name="uq_terraform_render_revision_digest_profile"),
    )


class CloudReadinessPreflight(Base):
    """Local-only guardrail evaluation before any future cloud action is reachable."""

    __tablename__ = "cloud_readiness_preflights"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    revision_id: Mapped[str] = mapped_column(ForeignKey("infrastructure_plan_revisions.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    state: Mapped[str] = mapped_column(String(40), default="BLOCKED_CLOUD_RUNTIME_NOT_CONFIGURED", index=True)
    guard: Mapped[dict] = mapped_column(JSON, default=dict)
    checklist: Mapped[dict] = mapped_column(JSON, default=dict)
    would_deploy: Mapped[dict] = mapped_column(JSON, default=dict)
    content_digest: Mapped[str] = mapped_column(String(64), index=True)
    created_by_subject: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TerraformPlanReview(Base):
    """Plan-only Terraform review evidence for an approved customer-plan revision."""

    __tablename__ = "terraform_plan_reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    revision_id: Mapped[str] = mapped_column(ForeignKey("infrastructure_plan_revisions.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    terraform_render_id: Mapped[str | None] = mapped_column(
        ForeignKey("terraform_plan_renders.id"), nullable=True, index=True
    )
    preflight_id: Mapped[str | None] = mapped_column(
        ForeignKey("cloud_readiness_preflights.id"), nullable=True, index=True
    )
    mode: Mapped[str] = mapped_column(String(60), default="LOCAL_CONTRACT_ONLY", index=True)
    state: Mapped[str] = mapped_column(String(60), default="BLOCKED_PREFLIGHT_REQUIRED", index=True)
    command: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    content_digest: Mapped[str] = mapped_column(String(64), index=True)
    created_by_subject: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CloudExecutionRun(Base):
    """Customer-workload execution run requested through the product boundary."""

    __tablename__ = "cloud_execution_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    revision_id: Mapped[str] = mapped_column(
        ForeignKey("infrastructure_plan_revisions.id"), index=True
    )
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    terraform_render_id: Mapped[str | None] = mapped_column(
        ForeignKey("terraform_plan_renders.id"), nullable=True, index=True
    )
    preflight_id: Mapped[str | None] = mapped_column(
        ForeignKey("cloud_readiness_preflights.id"), nullable=True, index=True
    )
    terraform_plan_review_id: Mapped[str | None] = mapped_column(
        ForeignKey("terraform_plan_reviews.id"), nullable=True, index=True
    )
    profile: Mapped[str] = mapped_column(String(80), index=True)
    state: Mapped[str] = mapped_column(String(80), index=True)
    mode: Mapped[str] = mapped_column(String(80), default="GUARDED_CLOUD_EXECUTION")
    attempt: Mapped[int] = mapped_column(default=1)
    worker_claim_version: Mapped[int] = mapped_column(default=0)
    worker_lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    worker_lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    command: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    outputs: Mapped[dict] = mapped_column(JSON, default=dict)
    content_digest: Mapped[str] = mapped_column(String(64), index=True)
    requested_by_subject: Mapped[str] = mapped_column(String(160))
    module_instances: Mapped[list[CloudExecutionModuleInstance]] = relationship(
        back_populates="execution_run", cascade="all, delete-orphan", passive_deletes=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CloudExecutionModuleInstance(Base):
    """Durable, tenant-scoped state for one module instance in an execution graph."""

    __tablename__ = "cloud_execution_module_instances"
    __table_args__ = (
        UniqueConstraint("execution_run_id", "instance_id", name="uq_execution_module_instance"),
        UniqueConstraint("idempotency_key", name="uq_execution_module_idempotency_key"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    execution_run_id: Mapped[str] = mapped_column(
        ForeignKey("cloud_execution_runs.id", ondelete="CASCADE"), index=True
    )
    execution_run: Mapped[CloudExecutionRun] = relationship(back_populates="module_instances")
    instance_id: Mapped[str] = mapped_column(String(128))
    module_id: Mapped[str] = mapped_column(String(100), index=True)
    state: Mapped[str] = mapped_column(String(40), default="NOT_DISPATCHED", index=True)
    operation: Mapped[str] = mapped_column(String(32))
    attempt: Mapped[int] = mapped_column(default=0)
    input_digest: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200))
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    outputs: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DeploymentPlan(Base):
    __tablename__ = "deployment_plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    intent_id: Mapped[str | None] = mapped_column(ForeignKey("workload_intents.id"), nullable=True)
    environment_id: Mapped[str | None] = mapped_column(ForeignKey("environments.id"), nullable=True)
    requester_subject: Mapped[str] = mapped_column(String(160))
    action: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(40))
    plan_hash: Mapped[str] = mapped_column(String(64), unique=True)
    policy_result: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    deployment_plan_id: Mapped[str] = mapped_column(ForeignKey("deployment_plans.id"), index=True)
    plan_hash: Mapped[str] = mapped_column(String(64))
    approver_subject: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExecutionJob(Base):
    __tablename__ = "execution_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    deployment_plan_id: Mapped[str] = mapped_column(ForeignKey("deployment_plans.id"), index=True)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"), index=True)
    state: Mapped[str] = mapped_column(String(40))
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Environment(Base):
    __tablename__ = "environments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    environment_type: Mapped[str] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(40))
    desired_state: Mapped[dict] = mapped_column(JSON)
    observed_state: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EnvironmentOutput(Base):
    """Customer-visible outputs from an observed environment.

    Values are safe display values or secret references. Raw secrets are never
    stored here.
    """

    __tablename__ = "environment_outputs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    output_type: Mapped[str] = mapped_column(String(80))
    value: Mapped[str] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(40), default="customer")
    sensitive: Mapped[str] = mapped_column(String(8), default="false")
    source: Mapped[str] = mapped_column(String(120), default="fixture-observer")
    status: Mapped[str] = mapped_column(String(40), default="ACTIVE")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        UniqueConstraint("environment_id", "name", name="uq_environment_output_name"),
    )


class ObservedResource(Base):
    """Observed cloud/local resources tied to an environment lifecycle."""

    __tablename__ = "observed_resources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    resource_type: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(180))
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="ACTIVE")
    tags: Mapped[dict] = mapped_column(JSON, default=dict)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        UniqueConstraint(
            "environment_id", "provider", "resource_type", "name", name="uq_observed_resource"
        ),
    )


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"), index=True)
    state: Mapped[str] = mapped_column(String(32), default="OPEN")
    summary: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    environment_id: Mapped[str] = mapped_column(ForeignKey("environments.id"), index=True)
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id"), nullable=True)
    deployment_plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("deployment_plans.id"), nullable=True
    )
    state: Mapped[str] = mapped_column(String(32), default="PROPOSED")
    recommendation: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    actor_subject: Mapped[str] = mapped_column(String(160))
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
