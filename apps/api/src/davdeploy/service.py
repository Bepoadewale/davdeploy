from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import threading
import time
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import boto3
import httpx
from botocore.exceptions import BotoCoreError, ClientError
from httpx import HTTPError
from opentelemetry import trace
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from davdeploy.cloud_execution import (
    CloudExecutionAdapter,
    configured_cloud_execution_adapter,
)
from davdeploy.composed_deployment import ModuleLifecycleOutcome
from davdeploy.connection_secrets import (
    ConnectionSecretStore,
    configured_connection_secret_store,
)
from davdeploy.contracts import EvidenceRef, TenantScope
from davdeploy.day2 import FixtureDay2Advisor
from davdeploy.domain import (
    ArchitectureModule,
    CloudInventorySnapshot,
    EnvironmentName,
    InfrastructurePlanDecision,
    InfrastructurePlanState,
    LifecycleState,
    PlanAction,
    PolicyResult,
    WorkloadSpec,
)
from davdeploy.execution_profiles import execution_profile
from davdeploy.executor import ExecutionAdapter, configured_executor
from davdeploy.generated_deployment_contract import GeneratedDeploymentProposal
from davdeploy.generated_plan_artifacts import (
    GeneratedPlanArtifactError,
    StoredPlanObject,
    canonical_json_digest,
    configured_generated_plan_artifact_store,
    generated_plan_manifest,
    has_complete_pricing_evidence,
    policy_allows_human_review,
    policy_evidence,
)
from davdeploy.generated_plan_ownership import PlanOwnershipScope
from davdeploy.generated_terraform_plan import GeneratedTerraformPlan
from davdeploy.integrations import (
    FixtureAwsDiscovery,
    GitHubConnection,
    PublicGitHubRepositoryReader,
    StsAwsDiscovery,
    configured_github_connection,
    verify_github_webhook_signature,
)
from davdeploy.intent import IntentProvider, configured_intent_provider
from davdeploy.invitation_email import (
    InvitationDeliveryUnavailable,
    InvitationEmailSender,
    configured_invitation_sender,
)
from davdeploy.model_gateway import ModelGatewayUnavailable
from davdeploy.models import (
    ApiCredential,
    Approval,
    AuditEvent,
    BlogComment,
    BlogPost,
    CloudConnection,
    CloudDiscoveryJob,
    CloudExecutionModuleInstance,
    CloudExecutionRun,
    CloudReadinessPreflight,
    DataLifecycleRequest,
    DeploymentPlan,
    DesiredStatePublication,
    Environment,
    EnvironmentOutput,
    ExecutionJob,
    GeneratedPlanApproval,
    GeneratedPlanArtifact,
    GeneratedPlanRun,
    GeneratedPlanRunIdempotencyKey,
    GitHubAppInstallationState,
    GitHubWebhookDelivery,
    Incident,
    InfrastructurePlan,
    InfrastructurePlanDecisionRecord,
    InfrastructurePlanRevision,
    ObservedResource,
    Organization,
    PlanComment,
    ProductUser,
    Project,
    Recommendation,
    RepositoryConnection,
    StoredArchitecturePlan,
    StoredCloudInventorySnapshot,
    StoredRepositoryAnalysis,
    SupportTicket,
    TerraformPlanRender,
    TerraformPlanReview,
    UsageRecord,
    WorkerDispatchState,
    WorkloadIntent,
    WorkspaceInvitation,
    WorkspaceSubscription,
)
from davdeploy.module_ports import (
    normalize_renderer_outputs,
    validate_module_inputs,
    validate_module_outputs,
)
from davdeploy.nova_plan_dispatch import NovaPlanDispatchError, NovaPlanOnlyDispatcher
from davdeploy.planner import AwsV1Planner
from davdeploy.policy import PolicyClient
from davdeploy.security import IdentityClaims, Principal
from davdeploy.state import require_transition
from davdeploy.terraform_generation import (
    NovaTerraformGenerationFailed,
    NovaTerraformGenerator,
    generation_context_digest,
)
from davdeploy.universal_execution import (
    compile_universal_execution_plan,
    lifecycle_work,
    next_dispatchable_work_item,
    resolve_lifecycle_work_inputs,
)

BLOG_AUTHOR_EMAILS = frozenset({"bepoadewale1@gmail.com"})
CLOUD_EXECUTION_WORKER_LEASE_SECONDS = 900
CLOUD_EXECUTION_WORKER_HEARTBEAT_SECONDS = 60
CLOUD_EXECUTION_LEASE_SCAN_SECONDS = 30
NOVA_PLAN_PREPARATION_LEASE_SECONDS = 180
NOVA_PLAN_WORKER_HEARTBEAT_SECONDS = 30
NOVA_PLAN_MAX_EXPLICIT_RETRIES = 3
NOVA_PLAN_UNCERTAIN_ERROR_CODES = frozenset(
    {
        "DISPATCH_UNCERTAIN",
        "INPUT_STAGE_RECONCILIATION_REQUIRED",
        "PROPOSAL_GENERATION_RECONCILIATION_REQUIRED",
        "BUILD_START_RECONCILIATION_REQUIRED",
        "PREPARATION_OUTCOME_UNCERTAIN",
        "PREPARATION_LEASE_EXPIRED",
        "BUILD_STATUS_UNCONFIRMED",
    }
)
_last_cloud_execution_lease_scan = 0.0
_cloud_execution_lease_scan_lock = threading.Lock()


def plan_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _model_evidence_summary(evidence: EvidenceRef) -> dict[str, Any]:
    """Persist only model evidence metadata, never request or response content."""
    return {
        "evidence_id": evidence.evidence_id,
        "kind": evidence.kind.value,
        "source": evidence.source,
        "content_digest": evidence.content_digest,
        "location": evidence.location,
    }


class ProductService:
    def __init__(
        self,
        db: Session,
        policy: PolicyClient | None = None,
        executor: ExecutionAdapter | None = None,
        intent_provider: IntentProvider | None = None,
        connection_secrets: ConnectionSecretStore | None = None,
        github: GitHubConnection | None = None,
        public_github: PublicGitHubRepositoryReader | None = None,
        cloud_execution: CloudExecutionAdapter | None = None,
        invitation_sender: InvitationEmailSender | None = None,
        terraform_generator: NovaTerraformGenerator | None = None,
        generated_plan_artifact_store: Any | None = None,
        nova_plan_dispatcher: NovaPlanOnlyDispatcher | None = None,
    ):
        self.db = db
        self.intent_provider = intent_provider or configured_intent_provider()
        self.planner = AwsV1Planner()
        self.cloud_discovery = FixtureAwsDiscovery()
        self.github = github or configured_github_connection()
        self.public_github = public_github or PublicGitHubRepositoryReader()
        self.day2_advisor = FixtureDay2Advisor()
        self.policy = policy or PolicyClient()
        self.executor = executor or configured_executor()
        self.connection_secrets = connection_secrets or configured_connection_secret_store()
        self.cloud_execution = cloud_execution or configured_cloud_execution_adapter()
        self.invitation_sender = invitation_sender or configured_invitation_sender()
        self.terraform_generator = terraform_generator or NovaTerraformGenerator()
        self.generated_plan_artifact_store = generated_plan_artifact_store
        self.nova_plan_dispatcher = nova_plan_dispatcher

    def _wake_worker(self, kind: str, job_id: str) -> None:
        """Send a non-sensitive wake-up after durable work has committed.

        PostgreSQL remains the source of truth. The SQS message is deliberately
        minimal: the worker claims the next scoped durable record itself and no
        tenant data, credentials, commands, or plan material travels in it.
        """
        queue_url = os.getenv("DAVDEPLOY_WORKER_QUEUE_URL", "").strip()
        if not queue_url:
            if os.getenv("DAVDEPLOY_HOSTED_MODE", "false").lower() == "true":
                raise RuntimeError("hosted worker wake-up queue is not configured")
            return
        try:
            boto3.client("sqs").send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps({"version": 1, "kind": kind, "job_id": job_id}),
            )
        except (BotoCoreError, ClientError) as error:
            raise RuntimeError("worker wake-up could not be queued") from error

    def _trace(self, name: str):
        return trace.get_tracer("davdeploy.product").start_as_current_span(name)

    def seed_local_identity(self) -> None:
        for org_id, name in (("org-demo", "Demo AI Startup"), ("org-other", "Other Tenant")):
            if not self.db.get(Organization, org_id):
                self.db.add(Organization(id=org_id, name=name))
        users = [
            ("user-founder", "org-demo", "developer"),
            ("user-administrator", "org-demo", "administrator"),
            ("user-operator", "org-demo", "operator"),
            ("user-other", "org-other", "developer"),
        ]
        for subject, org_id, role in users:
            if not self.db.scalar(select(ProductUser).where(ProductUser.subject == subject)):
                self.db.add(
                    ProductUser(id=subject, organization_id=org_id, subject=subject, role=role)
                )
        self.db.commit()

    def onboard_identity(
        self,
        identity: IdentityClaims,
        workspace_name: str,
        invitation_token: str | None = None,
    ) -> dict[str, Any]:
        """Create or join a tenant using only a provider-verified identity."""
        existing = self.db.scalar(
            select(ProductUser).where(ProductUser.subject == identity.subject)
        )
        if existing:
            return self.workspace_profile(
                Principal(existing.subject, existing.organization_id, existing.role)
            )
        if not identity.email or not identity.email_verified:
            raise PermissionError("a verified email is required to create or join a workspace")

        invitation = None
        if invitation_token:
            digest = hashlib.sha256(invitation_token.encode()).hexdigest()
            invitation = self.db.scalar(
                select(WorkspaceInvitation).where(
                    WorkspaceInvitation.token_digest == digest,
                    WorkspaceInvitation.state == "PENDING",
                )
            )
            expires_at = invitation.expires_at if invitation else None
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if not invitation or not expires_at or expires_at < datetime.now(UTC):
                raise PermissionError("invitation is invalid or expired")
            if invitation.email.lower() != identity.email.lower():
                raise PermissionError("invitation email does not match the verified identity")
            organization_id = invitation.organization_id
            role = invitation.role
            invitation.state = "ACCEPTED"
        else:
            requested_name = workspace_name.strip()
            name_in_use = self.db.scalar(
                select(Organization.id).where(Organization.name == requested_name)
            )
            organization = Organization(
                name=(
                    requested_name
                    if name_in_use is None
                    else f"{requested_name} ({identity.subject[-8:]})"
                )
            )
            self.db.add(organization)
            self.db.flush()
            organization_id = organization.id
            role = "administrator"

        user = ProductUser(
            organization_id=organization_id,
            subject=identity.subject,
            role=role,
        )
        self.db.add(user)
        self.db.flush()
        principal = Principal(user.subject, user.organization_id, user.role)
        self.audit(
            principal,
            "workspace.identity_onboarded",
            "user",
            user.id,
            {"via_invitation": bool(invitation)},
        )
        self.db.commit()
        return self.workspace_profile(principal)

    def audit(
        self, principal: Principal, action: str, entity_type: str, entity_id: str, detail: dict
    ) -> None:
        self.db.add(
            AuditEvent(
                organization_id=principal.organization_id,
                actor_subject=principal.subject,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                detail=detail,
            )
        )

    def workspace_profile(self, principal: Principal) -> dict[str, Any]:
        """Return only the current tenant's local identity and workspace metadata."""
        user = self.db.scalar(
            select(ProductUser).where(
                ProductUser.subject == principal.subject,
                ProductUser.organization_id == principal.organization_id,
            )
        )
        organization = self.db.get(Organization, principal.organization_id)
        if not user or not organization:
            raise PermissionError("current user is not a member of this workspace")
        role = "administrator" if self._is_workspace_administrator(principal) else "developer"
        return {
            "user": {"id": user.id, "subject": user.subject, "role": role},
            "workspace": {"id": organization.id, "name": organization.name},
        }

    def _require_workspace_admin(self, principal: Principal) -> None:
        if not self._is_workspace_administrator(principal):
            raise PermissionError("workspace administrator role required")

    def invite_workspace_member(
        self, principal: Principal, email: str, role: str
    ) -> dict[str, Any]:
        self._require_workspace_admin(principal)
        normalized_email = email.strip().lower()
        if "@" not in normalized_email:
            raise ValueError("a valid invitation email is required")
        existing = self.db.scalar(
            select(WorkspaceInvitation).where(
                WorkspaceInvitation.organization_id == principal.organization_id,
                WorkspaceInvitation.email == normalized_email,
                WorkspaceInvitation.state == "PENDING",
            )
        )
        if existing:
            raise ValueError("a pending invitation already exists for this email")
        raw_token = secrets.token_urlsafe(24)
        invitation = WorkspaceInvitation(
            organization_id=principal.organization_id,
            email=normalized_email,
            role=role,
            token_digest=hashlib.sha256(raw_token.encode()).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(days=7),
            invited_by_subject=principal.subject,
        )
        self.db.add(invitation)
        self.db.flush()
        self.audit(
            principal,
            "workspace.invitation_created",
            "workspace_invitation",
            invitation.id,
            {"email": invitation.email, "role": role},
        )
        self.db.commit()
        return self._deliver_workspace_invitation(principal, invitation, raw_token)

    @staticmethod
    def _workspace_invitation_payload(invitation: WorkspaceInvitation) -> dict[str, Any]:
        return {
            "id": invitation.id,
            "email": invitation.email,
            "role": invitation.role,
            "state": invitation.state,
            "delivery_state": invitation.delivery_state,
            "delivery_provider": invitation.delivery_provider,
            "send_count": invitation.send_count,
            "last_sent_at": invitation.last_sent_at,
            "expires_at": invitation.expires_at,
        }

    def _deliver_workspace_invitation(
        self, principal: Principal, invitation: WorkspaceInvitation, raw_token: str
    ) -> dict[str, Any]:
        organization = self.db.get(Organization, principal.organization_id)
        if not organization:
            raise PermissionError("workspace not found")
        try:
            delivery = self.invitation_sender.send(
                email=invitation.email,
                role=invitation.role,
                token=raw_token,
                workspace_name=organization.name,
                expires_at=invitation.expires_at,
            )
        except Exception as error:
            invitation.delivery_state = "FAILED"
            invitation.send_count += 1
            self.audit(
                principal,
                "workspace.invitation_delivery_failed",
                "workspace_invitation",
                invitation.id,
                {"provider": type(self.invitation_sender).__name__},
            )
            self.db.commit()
            if isinstance(error, InvitationDeliveryUnavailable):
                raise
            raise InvitationDeliveryUnavailable(
                "workspace invitation email delivery failed"
            ) from error

        invitation.delivery_state = "SENT"
        invitation.delivery_provider = delivery.provider
        invitation.provider_message_id = delivery.message_id
        invitation.send_count += 1
        invitation.last_sent_at = datetime.now(UTC)
        self.audit(
            principal,
            "workspace.invitation_sent",
            "workspace_invitation",
            invitation.id,
            {"provider": delivery.provider, "execution": delivery.execution},
        )
        self.db.commit()
        payload = self._workspace_invitation_payload(invitation)
        if delivery.execution == "SIMULATED":
            payload["invite_token"] = raw_token
        return payload

    def list_workspace_invitations(self, principal: Principal) -> list[dict[str, Any]]:
        self._require_workspace_admin(principal)
        invitations = self.db.scalars(
            select(WorkspaceInvitation)
            .where(WorkspaceInvitation.organization_id == principal.organization_id)
            .order_by(WorkspaceInvitation.created_at.desc())
        ).all()
        return [self._workspace_invitation_payload(invitation) for invitation in invitations]

    def resend_workspace_invitation(
        self, principal: Principal, invitation_id: str
    ) -> dict[str, Any]:
        self._require_workspace_admin(principal)
        invitation = self.db.scalar(
            select(WorkspaceInvitation).where(
                WorkspaceInvitation.id == invitation_id,
                WorkspaceInvitation.organization_id == principal.organization_id,
            )
        )
        if not invitation:
            raise KeyError("workspace invitation not found")
        if invitation.state != "PENDING":
            raise ValueError("only pending invitations can be resent")
        raw_token = secrets.token_urlsafe(24)
        invitation.token_digest = hashlib.sha256(raw_token.encode()).hexdigest()
        invitation.expires_at = datetime.now(UTC) + timedelta(days=7)
        invitation.delivery_state = "PENDING"
        self.db.commit()
        return self._deliver_workspace_invitation(principal, invitation, raw_token)

    def cancel_workspace_invitation(
        self, principal: Principal, invitation_id: str
    ) -> dict[str, Any]:
        self._require_workspace_admin(principal)
        invitation = self.db.scalar(
            select(WorkspaceInvitation).where(
                WorkspaceInvitation.id == invitation_id,
                WorkspaceInvitation.organization_id == principal.organization_id,
            )
        )
        if not invitation:
            raise KeyError("workspace invitation not found")
        if invitation.state != "PENDING":
            raise ValueError("only pending invitations can be cancelled")
        invitation.state = "CANCELLED"
        invitation.cancelled_at = datetime.now(UTC)
        self.audit(
            principal,
            "workspace.invitation_cancelled",
            "workspace_invitation",
            invitation.id,
            {"email": invitation.email},
        )
        self.db.commit()
        return self._workspace_invitation_payload(invitation)

    def list_workspace_members(self, principal: Principal) -> list[dict[str, Any]]:
        self.workspace_profile(principal)
        users = self.db.scalars(
            select(ProductUser)
            .where(ProductUser.organization_id == principal.organization_id)
            .order_by(ProductUser.subject)
        ).all()
        return [{"subject": user.subject, "role": user.role, "state": "ACTIVE"} for user in users]

    def change_workspace_member_role(
        self, principal: Principal, subject: str, role: str
    ) -> dict[str, str]:
        self._require_workspace_admin(principal)
        if subject == principal.subject and role != principal.role:
            raise ValueError("administrators cannot change their own role")
        member = self.db.scalar(
            select(ProductUser).where(
                ProductUser.organization_id == principal.organization_id,
                ProductUser.subject == subject,
            )
        )
        if not member:
            raise KeyError("workspace member not found")
        member.role = role
        self.audit(
            principal,
            "workspace.member_role_changed",
            "user",
            member.id,
            {"subject": subject, "role": role},
        )
        self.db.commit()
        return {"subject": member.subject, "role": member.role}

    def subscription(self, principal: Principal) -> dict[str, Any]:
        self.workspace_profile(principal)
        subscription = self.db.scalar(
            select(WorkspaceSubscription).where(
                WorkspaceSubscription.organization_id == principal.organization_id
            )
        )
        if not subscription:
            subscription = WorkspaceSubscription(
                organization_id=principal.organization_id,
                limits={"plans_created": 25, "repository_analyses": 25, "execution_jobs": 10},
                trial_ends_at=datetime.now(UTC) + timedelta(days=14),
            )
            self.db.add(subscription)
            self.db.commit()
        return {
            "plan_name": subscription.plan_name,
            "state": subscription.state,
            "limits": subscription.limits,
            "trial_ends_at": subscription.trial_ends_at,
        }

    def set_subscription(
        self, principal: Principal, plan_name: str, state: str, limits: dict[str, int]
    ) -> dict[str, Any]:
        self._require_workspace_admin(principal)
        subscription = self.db.scalar(
            select(WorkspaceSubscription).where(
                WorkspaceSubscription.organization_id == principal.organization_id
            )
        )
        if not subscription:
            subscription = WorkspaceSubscription(organization_id=principal.organization_id)
            self.db.add(subscription)
        subscription.plan_name, subscription.state, subscription.limits = plan_name, state, limits
        self.db.flush()
        self.audit(
            principal,
            "billing.subscription_updated",
            "workspace_subscription",
            subscription.id,
            {"plan_name": plan_name, "state": state, "limits": limits},
        )
        self.db.commit()
        return self.subscription(principal)

    def create_api_credential(
        self, principal: Principal, name: str, scopes: list[str]
    ) -> dict[str, Any]:
        self._require_workspace_admin(principal)
        raw_token = f"ac_live_{secrets.token_urlsafe(32)}"
        credential = ApiCredential(
            organization_id=principal.organization_id,
            name=name,
            token_digest=hashlib.sha256(raw_token.encode()).hexdigest(),
            scopes={"items": sorted(set(scopes))},
            created_by_subject=principal.subject,
        )
        self.db.add(credential)
        self.db.flush()
        self.audit(
            principal,
            "api_credential.created",
            "api_credential",
            credential.id,
            {"name": name, "scopes": credential.scopes["items"]},
        )
        self.db.commit()
        return {
            "id": credential.id,
            "name": credential.name,
            "scopes": credential.scopes["items"],
            "token": raw_token,
            "created_at": credential.created_at,
        }

    def revoke_api_credential(self, principal: Principal, credential_id: str) -> None:
        self._require_workspace_admin(principal)
        credential = self.db.scalar(
            select(ApiCredential).where(
                ApiCredential.id == credential_id,
                ApiCredential.organization_id == principal.organization_id,
            )
        )
        if not credential:
            raise KeyError("API credential not found")
        credential.revoked_at = datetime.now(UTC)
        self.audit(principal, "api_credential.revoked", "api_credential", credential.id, {})
        self.db.commit()

    def record_usage(
        self, principal: Principal, metric: str, quantity: int = 1, source: str = "api"
    ) -> UsageRecord:
        record = UsageRecord(
            organization_id=principal.organization_id,
            metric=metric,
            quantity=quantity,
            source=source,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def usage_summary(self, principal: Principal) -> list[dict[str, Any]]:
        self.workspace_profile(principal)
        records = self.db.scalars(
            select(UsageRecord)
            .where(UsageRecord.organization_id == principal.organization_id)
            .order_by(UsageRecord.created_at.desc())
            .limit(200)
        ).all()
        totals: dict[str, int] = {}
        for record in records:
            totals[record.metric] = totals.get(record.metric, 0) + record.quantity
        return [
            {"metric": metric, "quantity": quantity} for metric, quantity in sorted(totals.items())
        ]

    def add_plan_comment(self, principal: Principal, revision_id: str, body: str) -> PlanComment:
        revision = self._infrastructure_revision(principal, revision_id)
        comment = PlanComment(
            organization_id=principal.organization_id,
            revision_id=revision.id,
            author_subject=principal.subject,
            body=body,
        )
        self.db.add(comment)
        self.db.flush()
        self.audit(
            principal,
            "plan.comment_added",
            "infrastructure_plan_revision",
            revision.id,
            {"comment_id": comment.id},
        )
        self.db.commit()
        return comment

    def plan_comments(self, principal: Principal, revision_id: str) -> list[PlanComment]:
        self._infrastructure_revision(principal, revision_id)
        return list(
            self.db.scalars(
                select(PlanComment)
                .where(
                    PlanComment.organization_id == principal.organization_id,
                    PlanComment.revision_id == revision_id,
                )
                .order_by(PlanComment.created_at)
            ).all()
        )

    def can_author_blog(self, principal: Principal) -> bool:
        """Publishing is global and limited to verified team identities."""
        email = (principal.email or "").strip().lower()
        return principal.email_verified and (
            email.endswith("@davdeploy.tech") or email in BLOG_AUTHOR_EMAILS
        )

    def _require_blog_author(self, principal: Principal) -> None:
        if not self.can_author_blog(principal):
            raise PermissionError("DavDeploy team publishing access is required")

    @staticmethod
    def _blog_post_response(post: BlogPost, include_draft: bool = False) -> dict[str, Any]:
        response = {
            "id": post.id,
            "slug": post.slug,
            "title": post.title,
            "summary": post.summary,
            "body": post.body,
            "author_name": "DavDeploy team",
            "created_at": post.created_at,
            "updated_at": post.updated_at,
            "published_at": post.published_at,
        }
        if include_draft:
            response["state"] = post.state
            response["author_subject"] = post.author_subject
        return response

    def public_blog_posts(self) -> list[dict[str, Any]]:
        posts = self.db.scalars(
            select(BlogPost)
            .where(BlogPost.state == "PUBLISHED")
            .order_by(BlogPost.published_at.desc(), BlogPost.created_at.desc())
        ).all()
        return [self._blog_post_response(post) for post in posts]

    def public_blog_post(self, slug: str) -> dict[str, Any]:
        post = self.db.scalar(
            select(BlogPost).where(BlogPost.slug == slug, BlogPost.state == "PUBLISHED")
        )
        if not post:
            raise KeyError("blog post not found")
        return self._blog_post_response(post)

    def team_blog_posts(self, principal: Principal) -> list[dict[str, Any]]:
        self._require_blog_author(principal)
        posts = self.db.scalars(select(BlogPost).order_by(BlogPost.updated_at.desc())).all()
        return [self._blog_post_response(post, include_draft=True) for post in posts]

    def create_blog_post(self, principal: Principal, payload: dict[str, str]) -> dict[str, Any]:
        self._require_blog_author(principal)
        post = BlogPost(author_subject=principal.subject, **payload)
        if post.state == "PUBLISHED":
            post.published_at = datetime.now(UTC)
        self.db.add(post)
        self.db.flush()
        self.audit(principal, "blog.post_created", "blog_post", post.id, {"slug": post.slug})
        self.db.commit()
        return self._blog_post_response(post, include_draft=True)

    def update_blog_post(
        self, principal: Principal, post_id: str, payload: dict[str, str]
    ) -> dict[str, Any]:
        self._require_blog_author(principal)
        post = self.db.get(BlogPost, post_id)
        if not post:
            raise KeyError("blog post not found")
        if post.author_subject != principal.subject:
            raise PermissionError("only the post author can edit this post")
        for key, value in payload.items():
            setattr(post, key, value)
        if post.state == "PUBLISHED" and post.published_at is None:
            post.published_at = datetime.now(UTC)
        self.audit(principal, "blog.post_updated", "blog_post", post.id, {"slug": post.slug})
        self.db.commit()
        return self._blog_post_response(post, include_draft=True)

    @staticmethod
    def _blog_comment_response(comment: BlogComment) -> dict[str, Any]:
        return {
            "id": comment.id,
            "body": comment.body,
            "author_name": "DavDeploy reader",
            "author_subject": comment.author_subject,
            "created_at": comment.created_at,
            "updated_at": comment.updated_at,
        }

    def blog_comments(self, slug: str) -> list[dict[str, Any]]:
        post = self.db.scalar(
            select(BlogPost).where(BlogPost.slug == slug, BlogPost.state == "PUBLISHED")
        )
        if not post:
            raise KeyError("blog post not found")
        comments = self.db.scalars(
            select(BlogComment)
            .where(BlogComment.post_id == post.id)
            .order_by(BlogComment.created_at)
        ).all()
        return [self._blog_comment_response(comment) for comment in comments]

    def create_blog_comment(self, principal: Principal, slug: str, body: str) -> dict[str, Any]:
        post = self.db.scalar(
            select(BlogPost).where(BlogPost.slug == slug, BlogPost.state == "PUBLISHED")
        )
        if not post:
            raise KeyError("blog post not found")
        comment = BlogComment(post_id=post.id, author_subject=principal.subject, body=body)
        self.db.add(comment)
        self.db.flush()
        self.audit(
            principal, "blog.comment_created", "blog_comment", comment.id, {"post_id": post.id}
        )
        self.db.commit()
        return self._blog_comment_response(comment)

    def update_blog_comment(
        self, principal: Principal, comment_id: str, body: str
    ) -> dict[str, Any]:
        comment = self.db.get(BlogComment, comment_id)
        if not comment:
            raise KeyError("blog comment not found")
        if comment.author_subject != principal.subject:
            raise PermissionError("only the comment author can edit this comment")
        comment.body = body
        self.audit(principal, "blog.comment_updated", "blog_comment", comment.id, {})
        self.db.commit()
        return self._blog_comment_response(comment)

    def create_support_ticket(self, principal: Principal, subject: str, body: str) -> SupportTicket:
        ticket = SupportTicket(
            organization_id=principal.organization_id,
            subject=subject,
            body=body,
            created_by_subject=principal.subject,
        )
        self.db.add(ticket)
        self.db.flush()
        self.audit(
            principal, "support.ticket_created", "support_ticket", ticket.id, {"subject": subject}
        )
        self.db.commit()
        return ticket

    @staticmethod
    def _support_ticket_response(ticket: SupportTicket) -> dict[str, Any]:
        return {
            "id": ticket.id,
            "subject": ticket.subject,
            "body": ticket.body,
            "state": ticket.state,
            "created_by_subject": ticket.created_by_subject,
            "created_at": ticket.created_at,
        }

    def support_tickets(self, principal: Principal) -> list[dict[str, Any]]:
        statement = select(SupportTicket).where(
            SupportTicket.organization_id == principal.organization_id
        )
        if not self._is_workspace_administrator(principal):
            statement = statement.where(SupportTicket.created_by_subject == principal.subject)
        return [
            self._support_ticket_response(ticket)
            for ticket in self.db.scalars(statement.order_by(SupportTicket.created_at.desc()))
        ]

    def update_support_ticket_state(
        self, principal: Principal, ticket_id: str, state: str
    ) -> dict[str, Any]:
        if not self._is_workspace_administrator(principal):
            raise PermissionError("workspace administrator required to update support tickets")
        ticket = self.db.scalar(
            select(SupportTicket).where(
                SupportTicket.id == ticket_id,
                SupportTicket.organization_id == principal.organization_id,
            )
        )
        if not ticket:
            raise KeyError("support ticket not found")
        ticket.state = state
        self.audit(
            principal,
            "support.ticket_state_updated",
            "support_ticket",
            ticket.id,
            {"state": state},
        )
        self.db.commit()
        return self._support_ticket_response(ticket)

    def request_data_lifecycle(self, principal: Principal, request_type: str) -> dict[str, Any]:
        self._require_workspace_admin(principal)
        request = DataLifecycleRequest(
            organization_id=principal.organization_id,
            request_type=request_type,
            requested_by_subject=principal.subject,
        )
        self.db.add(request)
        self.db.flush()
        self.audit(
            principal,
            "data_lifecycle.requested",
            "data_lifecycle_request",
            request.id,
            {"request_type": request_type},
        )
        self.db.commit()
        if request_type == "EXPORT":
            return {"id": request.id, "state": "READY", "export": self.audit_evidence(principal)}
        return {"id": request.id, "state": request.state}

    def workspace_dashboard(self, principal: Principal) -> dict[str, Any]:
        """Tenant-scoped dashboard data. Developers see their plans; admins see workspace plans."""
        profile = self.workspace_profile(principal)
        is_admin = self._is_workspace_administrator(principal)
        projects = self.db.scalars(
            select(Project)
            .where(Project.organization_id == principal.organization_id)
            .order_by(Project.created_at.desc())
        ).all()
        connections = self.db.scalars(
            select(CloudConnection)
            .where(CloudConnection.organization_id == principal.organization_id)
            .order_by(CloudConnection.created_at.desc())
        ).all()
        revisions_query = (
            select(InfrastructurePlanRevision, InfrastructurePlan)
            .join(
                InfrastructurePlan,
                InfrastructurePlan.id == InfrastructurePlanRevision.infrastructure_plan_id,
            )
            .where(InfrastructurePlanRevision.organization_id == principal.organization_id)
            .order_by(InfrastructurePlanRevision.created_at.desc())
        )
        if not is_admin:
            revisions_query = revisions_query.where(
                InfrastructurePlan.creator_subject == principal.subject
            )
        revisions = self.db.execute(revisions_query.limit(20)).all()
        project_names = {project.id: project.name for project in projects}
        activities = self.db.scalars(
            select(AuditEvent)
            .where(AuditEvent.organization_id == principal.organization_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(12)
        ).all()
        pending_count = 0
        if is_admin:
            pending_count = len(
                self.db.scalars(
                    select(InfrastructurePlanRevision.id).where(
                        InfrastructurePlanRevision.organization_id == principal.organization_id,
                        InfrastructurePlanRevision.state == InfrastructurePlanState.SUBMITTED,
                    )
                ).all()
            )
        return {
            **profile,
            "projects": [
                {"id": project.id, "name": project.name, "repository_url": project.repository_url}
                for project in projects
            ],
            "cloud_connections": [
                {
                    "id": connection.id,
                    "display_name": connection.display_name,
                    "provider": connection.provider,
                    "account_id": connection.account_id,
                    "setup_state": connection.setup_state,
                }
                for connection in connections
            ],
            "plans": [
                {
                    "id": revision.id,
                    "plan_id": plan.id,
                    "project_id": plan.project_id,
                    "project_name": project_names.get(plan.project_id),
                    "title": plan.title,
                    "revision": revision.revision_number,
                    "state": revision.state,
                    "creator_subject": plan.creator_subject,
                    "created_at": revision.created_at.isoformat() if revision.created_at else None,
                }
                for revision, plan in revisions
            ],
            "pending_approval_count": pending_count,
            "recent_activity": [
                {
                    "id": event.id,
                    "action": event.action,
                    "entity_type": event.entity_type,
                    "entity_id": event.entity_id,
                    "at": event.created_at.isoformat() if event.created_at else None,
                }
                for event in activities
            ],
        }

    def pending_infrastructure_plan_revisions(self, principal: Principal) -> list[dict[str, Any]]:
        if not self._is_workspace_administrator(principal):
            raise PermissionError("workspace administrator role required for pending approvals")
        rows = self._admin_infrastructure_revision_rows(
            principal, InfrastructurePlanState.SUBMITTED
        )
        return [self._admin_plan_queue_item(revision, plan) for revision, plan in rows]

    def admin_infrastructure_plan_revisions(
        self, principal: Principal, state: str | None = None
    ) -> list[dict[str, Any]]:
        if not self._is_workspace_administrator(principal):
            raise PermissionError("workspace administrator role required for plan review")
        normalized: InfrastructurePlanState | None = None
        self_approved_only = False
        if state:
            state_key = state.upper()
            if state_key == "SELF_APPROVED":
                normalized = InfrastructurePlanState.APPROVED
                self_approved_only = True
            else:
                normalized = InfrastructurePlanState(state_key)
        rows = self._admin_infrastructure_revision_rows(principal, normalized)
        items = [self._admin_plan_queue_item(revision, plan) for revision, plan in rows]
        if self_approved_only:
            return [item for item in items if item["is_self_approval"]]
        return items

    def _admin_infrastructure_revision_rows(
        self, principal: Principal, state: InfrastructurePlanState | None
    ) -> list[tuple[InfrastructurePlanRevision, InfrastructurePlan]]:
        statement = (
            select(InfrastructurePlanRevision, InfrastructurePlan)
            .join(
                InfrastructurePlan,
                InfrastructurePlan.id == InfrastructurePlanRevision.infrastructure_plan_id,
            )
            .where(InfrastructurePlanRevision.organization_id == principal.organization_id)
            .order_by(InfrastructurePlanRevision.created_at.desc())
        )
        if state:
            statement = statement.where(InfrastructurePlanRevision.state == state)
        return list(self.db.execute(statement).all())

    def _admin_plan_queue_item(
        self, revision: InfrastructurePlanRevision, plan: InfrastructurePlan
    ) -> dict[str, Any]:
        decision = self.db.scalar(
            select(InfrastructurePlanDecisionRecord).where(
                InfrastructurePlanDecisionRecord.revision_id == revision.id
            )
        )
        content = revision.content or {}
        target = content.get("target") or {}
        application = content.get("application_analysis") or {}
        policy = content.get("policy_findings") or {}
        return {
            "id": revision.id,
            "plan_id": plan.id,
            "title": plan.title,
            "revision": revision.revision_number,
            "state": revision.state,
            "creator_subject": plan.creator_subject,
            "repository": application.get("repository"),
            "branch": application.get("branch"),
            "aws_account_id": target.get("account_id"),
            "region": target.get("region"),
            "content_digest": revision.content_digest,
            "policy_result": policy.get("result"),
            "is_self_approval": bool(decision and decision.is_self_approval),
            "decision": decision.decision if decision else None,
            "submitted_at": revision.submitted_at.isoformat() if revision.submitted_at else None,
            "decided_at": decision.decided_at.isoformat()
            if decision and decision.decided_at
            else None,
            "not_deployed": True,
        }

    def create_project(
        self,
        principal: Principal,
        name: str,
        repository_url: str | None,
        repository_branch: str | None = None,
    ) -> Project:
        project = Project(
            organization_id=principal.organization_id, name=name, repository_url=repository_url
        )
        self.db.add(project)
        self.db.flush()
        if repository_url:
            self.db.add(
                RepositoryConnection(
                    organization_id=principal.organization_id,
                    project_id=project.id,
                    provider="github",
                    repository_url=repository_url,
                    selected_branch=repository_branch,
                )
            )
        self.audit(principal, "project.created", "project", project.id, {"name": name})
        self.db.commit()
        return project

    @staticmethod
    def _is_workspace_administrator(principal: Principal) -> bool:
        # "operator" is the current local fixture name. "administrator" is the product role.
        return principal.role in {"operator", "administrator"}

    def create_infrastructure_plan(
        self,
        principal: Principal,
        project_id: str,
        title: str,
        content: dict[str, Any],
    ) -> InfrastructurePlanRevision:
        """Create a customer-facing DRAFT. It cannot deploy infrastructure."""
        project = self._project(principal, project_id)
        plan = InfrastructurePlan(
            organization_id=principal.organization_id,
            project_id=project.id,
            creator_subject=principal.subject,
            title=title,
        )
        self.db.add(plan)
        self.db.flush()
        revision = self._new_infrastructure_plan_revision(plan, principal, content, 1)
        self.audit(
            principal,
            "infrastructure_plan.draft_created",
            "infrastructure_plan_revision",
            revision.id,
            {
                "plan_id": plan.id,
                "revision": revision.revision_number,
                "digest": revision.content_digest,
            },
        )
        self.db.commit()
        return revision

    def revise_infrastructure_plan(
        self, principal: Principal, plan_id: str, content: dict[str, Any]
    ) -> InfrastructurePlanRevision:
        plan = self._infrastructure_plan(principal, plan_id)
        if plan.creator_subject != principal.subject:
            raise PermissionError("only the plan creator can create a revised draft")
        previous = self.db.scalar(
            select(InfrastructurePlanRevision)
            .where(InfrastructurePlanRevision.infrastructure_plan_id == plan.id)
            .order_by(InfrastructurePlanRevision.revision_number.desc())
            .limit(1)
        )
        if not previous or previous.state not in {
            InfrastructurePlanState.DRAFT,
            InfrastructurePlanState.REJECTED,
        }:
            raise ValueError("a revision can be created only from a draft or rejected plan")
        revision = self._new_infrastructure_plan_revision(
            plan, principal, content, previous.revision_number + 1
        )
        self.audit(
            principal,
            "infrastructure_plan.revised",
            "infrastructure_plan_revision",
            revision.id,
            {
                "plan_id": plan.id,
                "revision": revision.revision_number,
                "digest": revision.content_digest,
            },
        )
        self.db.commit()
        return revision

    def revise_infrastructure_plan_constraints(
        self,
        principal: Principal,
        plan_id: str,
        constraints: dict[str, Any],
    ) -> InfrastructurePlanRevision:
        plan = self._infrastructure_plan(principal, plan_id)
        if plan.creator_subject != principal.subject:
            raise PermissionError("only the plan creator can create a revised draft")
        previous = self.db.scalar(
            select(InfrastructurePlanRevision)
            .where(InfrastructurePlanRevision.infrastructure_plan_id == plan.id)
            .order_by(InfrastructurePlanRevision.revision_number.desc())
            .limit(1)
        )
        if not previous:
            raise ValueError("plan has no revision to update")
        if previous.state not in {
            InfrastructurePlanState.DRAFT,
            InfrastructurePlanState.REJECTED,
        }:
            raise ValueError("a revision can be created only from a draft or rejected plan")
        updated = self._content_with_constraint_updates(previous.content, constraints)
        revision = self.revise_infrastructure_plan(principal, plan_id, updated)
        self.audit(
            principal,
            "infrastructure_plan.constraints_updated",
            "infrastructure_plan_revision",
            revision.id,
            {
                "plan_id": plan.id,
                "revision": revision.revision_number,
                "changed": sorted(
                    key for key, value in constraints.items() if value not in (None, [], {})
                ),
            },
        )
        self.db.commit()
        return revision

    @staticmethod
    def _content_with_constraint_updates(
        content: dict[str, Any], constraints: dict[str, Any]
    ) -> dict[str, Any]:
        updated = json.loads(json.dumps(content))
        workload = updated.setdefault("application_analysis", {}).setdefault("workload_spec", {})
        target = updated.setdefault("target", {})
        summary = updated.setdefault("summary", {})
        previous_constraints = updated.get("user_constraints", {})
        next_constraints = {**previous_constraints}

        if constraints.get("monthly_budget_usd") is not None:
            workload["monthly_budget_usd"] = constraints["monthly_budget_usd"]
            next_constraints["monthly_budget_usd"] = constraints["monthly_budget_usd"]
        if constraints.get("region"):
            workload["region_constraints"] = [constraints["region"]]
            target["region"] = constraints["region"]
            next_constraints["region"] = constraints["region"]
        if constraints.get("environment"):
            environments = [str(item) for item in constraints["environment"]]
            workload["environments"] = environments
            next_constraints["environment"] = environments
        if constraints.get("data_classification"):
            workload["data_classification"] = constraints["data_classification"]
            next_constraints["data_classification"] = constraints["data_classification"]
        if constraints.get("availability_target"):
            workload["availability_target"] = constraints["availability_target"]
            next_constraints["availability_target"] = constraints["availability_target"]
        if constraints.get("workload_type"):
            workload["workload_type"] = constraints["workload_type"]
            next_constraints["workload_type"] = constraints["workload_type"]
        if constraints.get("public_access") is not None:
            workload["requires_private_connectivity"] = not bool(constraints["public_access"])
            next_constraints["public_access"] = bool(constraints["public_access"])

        accepted = constraints.get("accepted_assumptions") or []
        rejected = constraints.get("rejected_assumptions") or []
        updated["assumption_decisions"] = {
            "accepted": accepted,
            "rejected": rejected,
            "note": "Assumption decisions are review inputs; they do not bypass policy or cloud permissions.",
        }
        updated["user_constraints"] = next_constraints
        updated["revision_diff"] = ProductService._revision_diff(content, updated)
        summary["status"] = "DRAFT - revised constraints; not submitted, approved, or deployed"
        return updated

    @staticmethod
    def _revision_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        before_spec = before.get("application_analysis", {}).get("workload_spec", {})
        after_spec = after.get("application_analysis", {}).get("workload_spec", {})
        before_target = before.get("target", {})
        after_target = after.get("target", {})
        fields = {
            "monthly_budget_usd": (
                before_spec.get("monthly_budget_usd"),
                after_spec.get("monthly_budget_usd"),
            ),
            "region": (before_target.get("region"), after_target.get("region")),
            "environments": (before_spec.get("environments"), after_spec.get("environments")),
            "data_classification": (
                before_spec.get("data_classification"),
                after_spec.get("data_classification"),
            ),
            "availability_target": (
                before_spec.get("availability_target"),
                after_spec.get("availability_target"),
            ),
            "workload_type": (before_spec.get("workload_type"), after_spec.get("workload_type")),
            "requires_private_connectivity": (
                before_spec.get("requires_private_connectivity"),
                after_spec.get("requires_private_connectivity"),
            ),
        }
        return {
            field: {"before": old, "after": new}
            for field, (old, new) in fields.items()
            if old != new
        }

    def _new_infrastructure_plan_revision(
        self,
        plan: InfrastructurePlan,
        principal: Principal,
        content: dict[str, Any],
        revision_number: int,
    ) -> InfrastructurePlanRevision:
        revision = InfrastructurePlanRevision(
            infrastructure_plan_id=plan.id,
            organization_id=principal.organization_id,
            revision_number=revision_number,
            state=InfrastructurePlanState.DRAFT,
            content=content,
            content_digest=plan_hash(content),
        )
        self.db.add(revision)
        self.db.flush()
        return revision

    def submit_infrastructure_plan(
        self, principal: Principal, revision_id: str
    ) -> InfrastructurePlanRevision:
        revision = self._locked_infrastructure_revision(principal, revision_id)
        plan = self._infrastructure_plan(principal, revision.infrastructure_plan_id)
        if plan.creator_subject != principal.subject:
            raise PermissionError("only the plan creator can submit a draft")
        if revision.state != InfrastructurePlanState.DRAFT:
            raise ValueError("only a draft revision can be submitted")
        if revision.content_digest != plan_hash(revision.content):
            raise ValueError("draft content integrity check failed")
        self._validate_infrastructure_plan_submission(principal, plan, revision)
        revision.state = InfrastructurePlanState.SUBMITTED
        revision.submitted_by_subject = principal.subject
        revision.submitted_at = datetime.now(UTC)
        self.audit(
            principal,
            "infrastructure_plan.submitted",
            "infrastructure_plan_revision",
            revision.id,
            {
                "plan_id": plan.id,
                "revision": revision.revision_number,
                "digest": revision.content_digest,
            },
        )
        self.db.commit()
        return revision

    def _validate_infrastructure_plan_submission(
        self,
        principal: Principal,
        plan: InfrastructurePlan,
        revision: InfrastructurePlanRevision,
    ) -> None:
        """Validate the review contract before it becomes an immutable submission.

        This is deliberately a planning gate, not an AWS preflight or deployment action.
        A local fixture target remains valid; selected real connections/repositories must
        still belong to the same workspace.
        """
        content = revision.content
        if content.get("kind") != "davdeploy.aws.infrastructure-plan.review.v1":
            raise ValueError("only a complete AWS customer-plan review can be submitted")
        target = content.get("target") or {}
        if target.get("provider") != "aws" or not target.get("region"):
            raise ValueError("submitted plan needs an AWS target and region")
        application = content.get("application_analysis") or {}
        if not application.get("repository"):
            raise ValueError("submitted plan needs a selected repository")
        observability = content.get("observability") or {}
        if not observability.get("metrics_backend") or not observability.get("dashboard"):
            raise ValueError("submitted plan needs Prometheus-compatible metrics and Grafana")
        policy = content.get("policy_findings") or {}
        if policy.get("result") == PolicyResult.DENY:
            raise ValueError("policy denied this infrastructure plan")
        connection_id = target.get("connection_id")
        if connection_id:
            self._cloud_connection(principal, str(connection_id))
        # Generated customer reviews carry their source deployment-plan ID. Those
        # reviews must still point at a live project repository before submission.
        # The lower-level lifecycle API remains usable for independently created
        # typed plan fixtures and migration data.
        if content.get("source_deployment_plan_id"):
            repository = self.db.scalar(
                select(RepositoryConnection).where(
                    RepositoryConnection.organization_id == principal.organization_id,
                    RepositoryConnection.project_id == plan.project_id,
                    RepositoryConnection.repository_url == application["repository"],
                )
            )
            if repository is None:
                raise ValueError("selected repository is no longer connected to this project")

    def infrastructure_plan_revision_detail(
        self, principal: Principal, revision_id: str
    ) -> dict[str, Any]:
        revision = self._infrastructure_revision(principal, revision_id)
        plan = self._infrastructure_plan(principal, revision.infrastructure_plan_id)
        if (
            not self._is_workspace_administrator(principal)
            and plan.creator_subject != principal.subject
        ):
            raise PermissionError("infrastructure plan revision is not visible to this user")
        decision = self.db.scalar(
            select(InfrastructurePlanDecisionRecord).where(
                InfrastructurePlanDecisionRecord.revision_id == revision.id
            )
        )
        content = revision.content or {}
        application = content.get("application_analysis") or {}
        target = content.get("target") or {}
        observability = content.get("observability") or {}
        cost = content.get("cost_estimate") or {}
        policy = content.get("policy_findings") or {}
        risks = content.get("risks_and_limitations") or []
        local_executions = self._customer_plan_environment_summaries(principal, revision.id)
        desired_state_publications = [
            self._desired_state_publication_payload(publication)
            for publication in self.db.scalars(
                select(DesiredStatePublication)
                .where(
                    DesiredStatePublication.organization_id == principal.organization_id,
                    DesiredStatePublication.revision_id == revision.id,
                )
                .order_by(DesiredStatePublication.created_at.desc())
            )
        ]
        terraform_plan_renders = [
            self._terraform_plan_render_payload(render)
            for render in self.db.scalars(
                select(TerraformPlanRender)
                .where(
                    TerraformPlanRender.organization_id == principal.organization_id,
                    TerraformPlanRender.revision_id == revision.id,
                )
                .order_by(TerraformPlanRender.created_at.desc())
            )
        ]
        cloud_preflights = [
            self._cloud_readiness_preflight_payload(preflight)
            for preflight in self.db.scalars(
                select(CloudReadinessPreflight)
                .where(
                    CloudReadinessPreflight.organization_id == principal.organization_id,
                    CloudReadinessPreflight.revision_id == revision.id,
                )
                .order_by(CloudReadinessPreflight.created_at.desc())
            )
        ]
        terraform_plan_reviews = [
            self._terraform_plan_review_payload(review)
            for review in self.db.scalars(
                select(TerraformPlanReview)
                .where(
                    TerraformPlanReview.organization_id == principal.organization_id,
                    TerraformPlanReview.revision_id == revision.id,
                )
                .order_by(TerraformPlanReview.created_at.desc())
            )
        ]
        cloud_execution_runs = [
            self._cloud_execution_run_payload(run)
            for run in self.db.scalars(
                select(CloudExecutionRun)
                .where(
                    CloudExecutionRun.organization_id == principal.organization_id,
                    CloudExecutionRun.revision_id == revision.id,
                )
                .order_by(CloudExecutionRun.created_at.desc())
            )
        ]
        return {
            "id": revision.id,
            "plan_id": plan.id,
            "title": plan.title,
            "creator_subject": plan.creator_subject,
            "revision": revision.revision_number,
            "state": revision.state,
            "content_digest": revision.content_digest,
            "content": content,
            "review_summary": {
                "requester": plan.creator_subject,
                "repository": application.get("repository"),
                "branch": application.get("branch"),
                "aws_account_id": target.get("account_id"),
                "region": target.get("region"),
                "policy_result": policy.get("result"),
                "prometheus": observability.get("metrics_backend"),
                "grafana": observability.get("dashboard"),
                "estimated_cost": cost.get("range"),
                "risks": risks,
                "approved_not_deployed": revision.state == InfrastructurePlanState.APPROVED,
                "execution_boundary": "Approval records a decision only. It does not deploy or mutate AWS resources.",
            },
            "local_executions": local_executions,
            "desired_state_publications": desired_state_publications,
            "terraform_plan_renders": terraform_plan_renders,
            "cloud_readiness_preflights": cloud_preflights,
            "terraform_plan_reviews": terraform_plan_reviews,
            "cloud_execution_runs": cloud_execution_runs,
            "submitted_by_subject": revision.submitted_by_subject,
            "submitted_at": revision.submitted_at.isoformat() if revision.submitted_at else None,
            "decision": None
            if not decision
            else {
                "decision": decision.decision,
                "approver_subject": decision.approver_subject,
                "creator_subject": decision.creator_subject,
                "is_self_approval": decision.is_self_approval,
                "approved_digest": decision.approved_digest,
                "authorization_policy": decision.authorization_policy,
                "reason": decision.reason,
                "decided_at": decision.decided_at.isoformat() if decision.decided_at else None,
            },
            "execution": "UNEXECUTED_APPROVAL_ONLY",
        }

    def execute_customer_plan_dry_run(
        self, principal: Principal, revision_id: str
    ) -> list[Environment]:
        """Queue a bounded local fixture run for an approved customer-plan revision.

        This is deliberately separate from approval and never assumes AWS credentials.
        """
        revision, plan, source_deployment = self._approved_customer_revision(principal, revision_id)
        if (
            not self._is_workspace_administrator(principal)
            and plan.creator_subject != principal.subject
        ):
            raise PermissionError(
                "only the plan creator or a workspace administrator can execute the local dry run"
            )
        existing = self._customer_plan_environments(principal, revision.id)
        active = [
            environment
            for environment in existing
            if LifecycleState(environment.state) != LifecycleState.DESTROYED
        ]
        if active:
            return active
        payload = {
            **source_deployment.payload,
            "execution_mode": "LOCAL_DRY_RUN",
            "customer_plan_revision_id": revision.id,
            "customer_plan_digest": revision.content_digest,
            "customer_plan_approved": True,
            "execution_boundary": "bounded local fixture execution only; no AWS resources are created",
        }
        digest = plan_hash(
            {
                "action": PlanAction.DEPLOY,
                "execution_mode": "LOCAL_DRY_RUN",
                "revision_id": revision.id,
                "digest": revision.content_digest,
                "payload": payload,
            }
        )
        dry_run = self.db.scalar(select(DeploymentPlan).where(DeploymentPlan.plan_hash == digest))
        if not dry_run:
            dry_run = DeploymentPlan(
                organization_id=principal.organization_id,
                intent_id=source_deployment.intent_id,
                requester_subject=principal.subject,
                action=PlanAction.DEPLOY,
                state=LifecycleState.PLANNED,
                plan_hash=digest,
                policy_result=PolicyResult.ALLOW,
                payload=payload,
            )
            self.db.add(dry_run)
            self.db.flush()
            self.audit(
                principal,
                "customer_plan.local_dry_run_plan_created",
                "deployment_plan",
                dry_run.id,
                {"revision_id": revision.id, "digest": revision.content_digest},
            )
        environments = self.execute(principal, dry_run.id)
        self.audit(
            principal,
            "customer_plan.local_dry_run_queued",
            "infrastructure_plan_revision",
            revision.id,
            {
                "deployment_plan_id": dry_run.id,
                "environment_ids": [environment.id for environment in environments],
                "digest": revision.content_digest,
            },
        )
        self.db.commit()
        return environments

    def customer_plan_destroy_plan(
        self, principal: Principal, revision_id: str, environment_id: str
    ) -> DeploymentPlan:
        revision, _, _ = self._approved_customer_revision(principal, revision_id)
        environment = self._environment(principal, environment_id)
        if environment.desired_state.get("customer_plan_revision_id") != revision.id:
            raise PermissionError("environment is not tied to this customer-plan revision")
        if LifecycleState(environment.state) not in {
            LifecycleState.READY,
            LifecycleState.FAILED,
            LifecycleState.DEGRADED,
        }:
            raise ValueError("environment cannot be destroyed in its current state")
        environment.state = LifecycleState.DESTROY_REQUESTED
        requires_approval = environment.environment_type == EnvironmentName.PRODUCTION
        payload = {
            "action": PlanAction.DESTROY,
            "environment_id": environment.id,
            "observed_state": environment.observed_state,
            "customer_plan_revision_id": revision.id,
            "customer_plan_digest": revision.content_digest,
            "execution_mode": "LOCAL_DRY_RUN_DESTROY",
        }
        digest = plan_hash(payload)
        plan = DeploymentPlan(
            organization_id=principal.organization_id,
            environment_id=environment.id,
            requester_subject=principal.subject,
            action=PlanAction.DESTROY,
            state=LifecycleState.DESTROY_APPROVAL_REQUIRED
            if requires_approval
            else LifecycleState.PLANNED,
            plan_hash=digest,
            policy_result=PolicyResult.APPROVAL_REQUIRED
            if requires_approval
            else PolicyResult.ALLOW,
            payload=payload,
        )
        self.db.add(plan)
        self.db.flush()
        self.audit(
            principal,
            "customer_plan.local_destroy_requested",
            "infrastructure_plan_revision",
            revision.id,
            {
                "environment_id": environment.id,
                "deployment_plan_id": plan.id,
                "hash": digest,
                "approval_required": requires_approval,
            },
        )
        self.db.commit()
        return plan

    def _approved_customer_revision(
        self, principal: Principal, revision_id: str
    ) -> tuple[InfrastructurePlanRevision, InfrastructurePlan, DeploymentPlan]:
        revision = self._infrastructure_revision(principal, revision_id)
        plan = self._infrastructure_plan(principal, revision.infrastructure_plan_id)
        if (
            not self._is_workspace_administrator(principal)
            and plan.creator_subject != principal.subject
        ):
            raise PermissionError("infrastructure plan revision is not visible to this user")
        if revision.state != InfrastructurePlanState.APPROVED:
            raise ValueError(
                "customer-plan revision must be approved before local dry-run execution"
            )
        decision = self.db.scalar(
            select(InfrastructurePlanDecisionRecord).where(
                InfrastructurePlanDecisionRecord.revision_id == revision.id
            )
        )
        if not decision or decision.decision != InfrastructurePlanDecision.APPROVED:
            raise ValueError("approved customer-plan revision has no durable approval decision")
        if decision.approved_digest != revision.content_digest:
            raise ValueError("approved customer-plan digest no longer matches the revision")
        source_id = revision.content.get("source_deployment_plan_id")
        if not source_id:
            raise ValueError("customer-plan revision has no source execution contract")
        source = self._plan(principal, str(source_id))
        return revision, plan, source

    def _customer_plan_environments(
        self, principal: Principal, revision_id: str
    ) -> list[Environment]:
        return [
            environment
            for environment in self.db.scalars(
                select(Environment)
                .where(Environment.organization_id == principal.organization_id)
                .order_by(Environment.created_at)
            )
            if environment.desired_state.get("customer_plan_revision_id") == revision_id
        ]

    def _customer_plan_environment_summaries(
        self, principal: Principal, revision_id: str
    ) -> list[dict[str, Any]]:
        return [
            {
                "id": environment.id,
                "name": environment.name,
                "type": environment.environment_type,
                "state": environment.state,
                "execution_mode": environment.desired_state.get("execution_mode"),
                "plan_hash": environment.desired_state.get("plan_hash"),
                "cost_estimate": environment.desired_state.get("cost_estimate"),
                "observed_state": environment.observed_state,
                "outputs": self._environment_outputs(environment.id),
                "resources": self._observed_resources(environment.id),
            }
            for environment in self._customer_plan_environments(principal, revision_id)
        ]

    def _record_environment_observation_assets(
        self, environment: Environment, observation: dict[str, Any]
    ) -> None:
        forced_status = "DESTROYED" if observation.get("state") == "DESTROYED" else None
        if forced_status:
            outputs = list(
                self.db.scalars(
                    select(EnvironmentOutput).where(
                        EnvironmentOutput.environment_id == environment.id
                    )
                )
            )
            resources = list(
                self.db.scalars(
                    select(ObservedResource).where(
                        ObservedResource.environment_id == environment.id
                    )
                )
            )
            for output in outputs:
                output.status = forced_status
            for resource in resources:
                resource.status = forced_status
        for item in observation.get("outputs", []):
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            output = self.db.scalar(
                select(EnvironmentOutput).where(
                    EnvironmentOutput.environment_id == environment.id,
                    EnvironmentOutput.name == name,
                )
            )
            if not output:
                output = EnvironmentOutput(
                    organization_id=environment.organization_id,
                    environment_id=environment.id,
                    name=name,
                    output_type=str(item.get("type") or "value"),
                    value=str(item.get("value") or ""),
                )
                self.db.add(output)
            output.output_type = str(item.get("type") or output.output_type)
            output.value = str(item.get("value") or output.value)
            output.visibility = str(item.get("visibility") or "customer")
            output.sensitive = str(bool(item.get("sensitive", False))).lower()
            output.source = str(item.get("source") or "fixture-observer")
            output.status = forced_status or str(item.get("status") or output.status)
            output.detail = {
                key: value
                for key, value in item.items()
                if key
                not in {
                    "name",
                    "type",
                    "value",
                    "visibility",
                    "sensitive",
                    "source",
                    "status",
                }
            }

        for item in observation.get("resources", []):
            provider = str(item.get("provider") or "unknown")
            resource_type = str(item.get("resource_type") or item.get("type") or "unknown")
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            resource = self.db.scalar(
                select(ObservedResource).where(
                    ObservedResource.environment_id == environment.id,
                    ObservedResource.provider == provider,
                    ObservedResource.resource_type == resource_type,
                    ObservedResource.name == name,
                )
            )
            if not resource:
                resource = ObservedResource(
                    organization_id=environment.organization_id,
                    environment_id=environment.id,
                    provider=provider,
                    resource_type=resource_type,
                    name=name,
                )
                self.db.add(resource)
            resource.external_id = item.get("external_id")
            resource.region = item.get("region")
            resource.status = forced_status or str(item.get("status") or resource.status)
            resource.tags = dict(item.get("tags") or {})
            resource.detail = {
                key: value
                for key, value in item.items()
                if key
                not in {
                    "provider",
                    "resource_type",
                    "type",
                    "name",
                    "external_id",
                    "region",
                    "status",
                    "tags",
                }
            }

    def _environment_outputs(self, environment_id: str) -> list[dict[str, Any]]:
        return [
            {
                "id": output.id,
                "name": output.name,
                "type": output.output_type,
                "value": "***" if output.sensitive == "true" else output.value,
                "visibility": output.visibility,
                "sensitive": output.sensitive == "true",
                "source": output.source,
                "status": output.status,
                "detail": output.detail,
                "updated_at": output.updated_at.isoformat() if output.updated_at else None,
            }
            for output in self.db.scalars(
                select(EnvironmentOutput)
                .where(EnvironmentOutput.environment_id == environment_id)
                .order_by(EnvironmentOutput.name)
            )
        ]

    def _observed_resources(self, environment_id: str) -> list[dict[str, Any]]:
        return [
            {
                "id": resource.id,
                "provider": resource.provider,
                "type": resource.resource_type,
                "name": resource.name,
                "external_id": resource.external_id,
                "region": resource.region,
                "status": resource.status,
                "tags": resource.tags,
                "detail": resource.detail,
                "updated_at": resource.updated_at.isoformat() if resource.updated_at else None,
            }
            for resource in self.db.scalars(
                select(ObservedResource)
                .where(ObservedResource.environment_id == environment_id)
                .order_by(
                    ObservedResource.provider,
                    ObservedResource.resource_type,
                    ObservedResource.name,
                )
            )
        ]

    def decide_infrastructure_plan(
        self,
        principal: Principal,
        revision_id: str,
        decision: InfrastructurePlanDecision,
        provided_digest: str,
        reason: str | None = None,
    ) -> InfrastructurePlanRevision:
        if not self._is_workspace_administrator(principal):
            raise PermissionError("workspace administrator role required for a plan decision")
        revision = self._locked_infrastructure_revision(principal, revision_id)
        plan = self._infrastructure_plan(principal, revision.infrastructure_plan_id)
        if revision.state != InfrastructurePlanState.SUBMITTED:
            raise ValueError("only a submitted revision can be decided")
        if (
            revision.content_digest != provided_digest
            or plan_hash(revision.content) != provided_digest
        ):
            raise ValueError("stale decision: submitted plan digest changed")
        if decision == InfrastructurePlanDecision.REJECTED and not (reason or "").strip():
            raise ValueError("a rejection reason is required")
        record = InfrastructurePlanDecisionRecord(
            revision_id=revision.id,
            organization_id=principal.organization_id,
            decision=decision,
            approver_subject=principal.subject,
            creator_subject=plan.creator_subject,
            is_self_approval=decision == InfrastructurePlanDecision.APPROVED
            and principal.subject == plan.creator_subject,
            approved_digest=provided_digest,
            authorization_policy="workspace-administrator-self-approval-allowed"
            if principal.subject == plan.creator_subject
            else "workspace-administrator",
            reason=reason.strip() if reason else None,
        )
        self.db.add(record)
        revision.state = (
            InfrastructurePlanState.APPROVED
            if decision == InfrastructurePlanDecision.APPROVED
            else InfrastructurePlanState.REJECTED
        )
        self.audit(
            principal,
            f"infrastructure_plan.{decision.lower()}",
            "infrastructure_plan_revision",
            revision.id,
            {
                "plan_id": plan.id,
                "revision": revision.revision_number,
                "digest": provided_digest,
                "is_self_approval": record.is_self_approval,
                "authorization_policy": record.authorization_policy,
                "reason": record.reason,
            },
        )
        self.db.commit()
        return revision

    def request_generated_plan_run(
        self,
        principal: Principal,
        revision_id: str,
        content_digest: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Persist one exact submitted revision and wake the isolated plan worker.

        The route is disabled unless a later reviewed release explicitly marks
        the fixed runner ready. This API records QUEUED work and does not call
        Bedrock, upload runner input, or start CodeBuild.
        """
        dispatcher = self.nova_plan_dispatcher or NovaPlanOnlyDispatcher.from_environment()
        if dispatcher is None:
            raise ModelGatewayUnavailable("hosted Nova plan generation is not enabled")
        if not re.fullmatch(r"[A-Za-z0-9._:-]{16,200}", idempotency_key):
            raise ValueError("Idempotency-Key must contain 16-200 safe characters")

        revision = self._infrastructure_revision(principal, revision_id)
        customer_plan = self._infrastructure_plan(principal, revision.infrastructure_plan_id)
        if (
            not self._is_workspace_administrator(principal)
            and customer_plan.creator_subject != principal.subject
        ):
            raise PermissionError("only the plan creator or a workspace administrator may request a plan")
        if revision.state not in {
            InfrastructurePlanState.SUBMITTED,
            InfrastructurePlanState.APPROVED,
        }:
            raise ValueError("Nova plan generation requires a submitted customer revision")
        if revision.content_digest != content_digest or plan_hash(revision.content) != content_digest:
            raise ValueError("customer revision digest is stale or invalid")
        latest = self.db.scalar(
            select(InfrastructurePlanRevision)
            .where(
                InfrastructurePlanRevision.infrastructure_plan_id == customer_plan.id,
                InfrastructurePlanRevision.organization_id == principal.organization_id,
            )
            .order_by(InfrastructurePlanRevision.revision_number.desc())
            .limit(1)
        )
        if not latest or latest.id != revision.id:
            raise ValueError("Nova plan request refers to a stale customer revision")
        if revision.state == InfrastructurePlanState.APPROVED:
            decision = self.db.scalar(
                select(InfrastructurePlanDecisionRecord).where(
                    InfrastructurePlanDecisionRecord.revision_id == revision.id,
                    InfrastructurePlanDecisionRecord.organization_id == principal.organization_id,
                )
            )
            if (
                not decision
                or decision.decision != InfrastructurePlanDecision.APPROVED
                or decision.approved_digest != content_digest
            ):
                raise ValueError("approved customer revision has no matching approval record")

        content = revision.content or {}
        target = content.get("target") or {}
        connection_id = target.get("connection_id")
        connection = self._cloud_connection(principal, str(connection_id or ""))
        account_id = str(target.get("account_id") or "")
        region = str(target.get("region") or "")
        if (
            connection.provider != "aws"
            or connection.setup_state != "VERIFIED"
            or not connection.account_id
            or account_id != connection.account_id
            or not re.fullmatch(r"\d{12}", account_id)
            or not re.fullmatch(r"[a-z]{2}(?:-[a-z0-9]+)+-\d", region)
        ):
            raise ValueError("plan target must match a verified AWS account and region")
        project = self._project(principal, customer_plan.project_id)
        source_id = content.get("source_deployment_plan_id")
        if not source_id:
            raise ValueError("customer revision has no source deployment plan")
        self._plan(principal, str(source_id))

        request_document = {
            "contract": "davdeploy.nova-plan-request.v1",
            "organization_id": principal.organization_id,
            "project_id": project.id,
            "plan_id": customer_plan.id,
            "revision_id": revision.id,
            "revision_sha256": revision.content_digest,
            "target_account_id": account_id,
            "region": region,
            "generator_model": self.terraform_generator.model_id,
            "runner_project": dispatcher.project_name,
        }
        request_sha256 = canonical_json_digest(request_document)
        idempotency_sha256 = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        existing = self._generated_plan_run_for_idempotency_key(
            principal.organization_id, idempotency_sha256
        )
        if existing:
            if existing.request_sha256 != request_sha256:
                raise ValueError("Idempotency-Key was already used for a different plan request")
            self._wake_generated_plan_run(existing)
            return self.generated_plan_run_detail(principal, existing.id)
        existing_request = self.db.scalar(
            select(GeneratedPlanRun).where(
                GeneratedPlanRun.organization_id == principal.organization_id,
                GeneratedPlanRun.revision_id == revision.id,
                GeneratedPlanRun.request_sha256 == request_sha256,
            )
        )
        if existing_request:
            existing_request = self._bind_generated_plan_run_idempotency_key(
                existing_request,
                principal.organization_id,
                idempotency_sha256,
                request_sha256,
            )
            self._wake_generated_plan_run(existing_request)
            return self.generated_plan_run_detail(principal, existing_request.id)

        run_id = str(uuid.uuid4())
        run = GeneratedPlanRun(
            id=run_id,
            organization_id=principal.organization_id,
            project_id=project.id,
            revision_id=revision.id,
            requester_subject=principal.subject,
            idempotency_key_sha256=idempotency_sha256,
            request_sha256=request_sha256,
            request_document=request_document,
            runner_run_id=run_id,
            codebuild_idempotency_token=run_id,
            revision_sha256=revision.content_digest,
            state="QUEUED",
            codebuild_project=dispatcher.project_name,
            input_key=dispatcher.input_key(run_id),
            result_key=dispatcher.result_key(run_id),
        )
        self.db.add(run)
        self.db.add(
            GeneratedPlanRunIdempotencyKey(
                organization_id=principal.organization_id,
                idempotency_key_sha256=idempotency_sha256,
                request_sha256=request_sha256,
                run_id=run.id,
            )
        )
        self.audit(
            principal,
            "generated_plan_run.requested",
            "generated_plan_run",
            run.id,
            {
                "revision_id": revision.id,
                "revision_sha256": revision.content_digest,
                "request_sha256": request_sha256,
                "runner_project": dispatcher.project_name,
                "state": run.state,
            },
        )
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self._generated_plan_run_for_idempotency_key(
                principal.organization_id, idempotency_sha256
            )
            if existing:
                if existing.request_sha256 != request_sha256:
                    raise ValueError(
                        "Idempotency-Key was already used for a different plan request"
                    ) from None
            else:
                existing = self.db.scalar(
                    select(GeneratedPlanRun).where(
                        GeneratedPlanRun.organization_id == principal.organization_id,
                        GeneratedPlanRun.revision_id == revision.id,
                        GeneratedPlanRun.request_sha256 == request_sha256,
                    )
                )
            if not existing:
                raise ValueError("Nova plan request could not be recorded safely") from None
            if existing.request_sha256 != request_sha256:
                raise ValueError("Idempotency-Key was already used for a different plan request")
            existing = self._bind_generated_plan_run_idempotency_key(
                existing,
                principal.organization_id,
                idempotency_sha256,
                request_sha256,
            )
            self._wake_generated_plan_run(existing)
            return self.generated_plan_run_detail(principal, existing.id)

        self._wake_generated_plan_run(run)
        return self.generated_plan_run_detail(principal, run.id)

    def retry_generated_plan_run(
        self, principal: Principal, run_id: str, idempotency_key: str
    ) -> dict[str, Any]:
        """Explicitly requeue a confirmed failure with a fresh idempotency key.

        The original request remains bound to its run. Retry keys are separately
        recorded so replaying a retry request cannot start another attempt. Runs
        requiring reconciliation are never eligible for retry.
        """
        if not re.fullmatch(r"[A-Za-z0-9._:-]{16,200}", idempotency_key):
            raise ValueError("Idempotency-Key must contain 16-200 safe characters")
        run = self.db.scalar(
            select(GeneratedPlanRun)
            .where(
                GeneratedPlanRun.id == run_id,
                GeneratedPlanRun.organization_id == principal.organization_id,
            )
            .execution_options(populate_existing=True)
        )
        if not run:
            raise PermissionError("generated plan request not found in this organization")
        if not self._is_workspace_administrator(principal) and run.requester_subject != principal.subject:
            raise PermissionError("generated plan request is not visible to this user")

        retry_key_sha256 = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        retry_events = self._generated_plan_run_retry_events(principal.organization_id, run.id)
        if any(
            (event.detail or {}).get("idempotency_key_sha256") == retry_key_sha256
            for event in retry_events
        ):
            if run.state == "QUEUED":
                self._wake_generated_plan_run(run)
            return self.generated_plan_run_detail(principal, run.id)

        if self._generated_plan_run_for_idempotency_key(
            principal.organization_id, retry_key_sha256
        ):
            raise ValueError("Idempotency-Key was already used for another request")
        if run.state != "FAILED" or run.error_code in NOVA_PLAN_UNCERTAIN_ERROR_CODES:
            raise ValueError(
                "only a confirmed failed plan request can be retried; reconcile uncertain work first"
            )
        if len(retry_events) >= NOVA_PLAN_MAX_EXPLICIT_RETRIES:
            raise ValueError("Nova plan retry limit reached")

        now = datetime.now(UTC)
        runner_run_id = str(uuid.uuid4())
        previous = {
            "state": run.state,
            "error_code": run.error_code,
            "codebuild_build_id": run.codebuild_build_id,
        }
        self.db.add(
            GeneratedPlanRunIdempotencyKey(
                organization_id=principal.organization_id,
                idempotency_key_sha256=retry_key_sha256,
                request_sha256=run.request_sha256,
                run_id=run.id,
            )
        )
        try:
            requeued = self.db.execute(
                update(GeneratedPlanRun)
                .where(
                    GeneratedPlanRun.id == run.id,
                    GeneratedPlanRun.organization_id == principal.organization_id,
                    GeneratedPlanRun.state == "FAILED",
                )
                .values(
                    state="QUEUED",
                    proposal_sha256=None,
                    input_sha256=None,
                    input_version_id=None,
                    runner_run_id=runner_run_id,
                    codebuild_idempotency_token=runner_run_id,
                    input_key=NovaPlanOnlyDispatcher.input_key(runner_run_id),
                    result_key=NovaPlanOnlyDispatcher.result_key(runner_run_id),
                    result_metadata=None,
                    codebuild_build_id=None,
                    error_code=None,
                    error_summary=None,
                    preparation_phase=None,
                    preparation_lease_token=None,
                    preparation_lease_expires_at=None,
                    started_at=None,
                    finished_at=None,
                    updated_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            if requeued.rowcount != 1:
                self.db.rollback()
                raise ValueError("plan request is no longer in a confirmed failed state")
            self.audit(
                principal,
                "generated_plan_run.retry_requested",
                "generated_plan_run",
                run.id,
                {
                    "idempotency_key_sha256": retry_key_sha256,
                    "request_sha256": run.request_sha256,
                    "retry_number": len(retry_events) + 1,
                    "previous": previous,
                    "state": "QUEUED",
                },
            )
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            retry_events = self._generated_plan_run_retry_events(
                principal.organization_id, run.id
            )
            if any(
                (event.detail or {}).get("idempotency_key_sha256") == retry_key_sha256
                for event in retry_events
            ):
                refreshed = self.db.scalar(
                    select(GeneratedPlanRun)
                    .where(GeneratedPlanRun.id == run.id)
                    .execution_options(populate_existing=True)
                )
                if refreshed and refreshed.state == "QUEUED":
                    self._wake_generated_plan_run(refreshed)
                return self.generated_plan_run_detail(principal, run.id)
            raise ValueError("Nova plan retry could not be recorded safely") from None

        requeued_run = self.db.scalar(
            select(GeneratedPlanRun)
            .where(GeneratedPlanRun.id == run.id)
            .execution_options(populate_existing=True)
        )
        if requeued_run is None:
            raise ValueError("Nova plan retry could not be recorded safely")
        self._wake_generated_plan_run(requeued_run)
        return self.generated_plan_run_detail(principal, run.id)

    def _generated_plan_run_retry_events(
        self, organization_id: str, run_id: str
    ) -> list[AuditEvent]:
        return list(
            self.db.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.organization_id == organization_id,
                    AuditEvent.action == "generated_plan_run.retry_requested",
                    AuditEvent.entity_type == "generated_plan_run",
                    AuditEvent.entity_id == run_id,
                )
                .order_by(AuditEvent.created_at, AuditEvent.id)
            )
        )

    def next_worker_dispatch_queue_index(self, queue_count: int) -> int:
        """Atomically claim the next queue slot from durable shared state."""
        if not 1 <= queue_count <= 10:
            raise ValueError("worker queue count is invalid")
        cursor = self.db.scalar(
            select(WorkerDispatchState)
            .where(WorkerDispatchState.id == 1)
            .with_for_update()
        )
        if cursor is None:
            self.db.rollback()
            raise RuntimeError("worker dispatch scheduler is not initialized")
        selected_index = cursor.next_queue_index % queue_count
        cursor.next_queue_index = (selected_index + 1) % queue_count
        cursor.updated_at = datetime.now(UTC)
        self.db.commit()
        return selected_index

    def _generated_plan_run_for_idempotency_key(
        self, organization_id: str, idempotency_key_sha256: str
    ) -> GeneratedPlanRun | None:
        alias = self.db.scalar(
            select(GeneratedPlanRunIdempotencyKey).where(
                GeneratedPlanRunIdempotencyKey.organization_id == organization_id,
                GeneratedPlanRunIdempotencyKey.idempotency_key_sha256 == idempotency_key_sha256,
            )
        )
        if alias:
            run = self.db.scalar(
                select(GeneratedPlanRun).where(GeneratedPlanRun.id == alias.run_id)
            )
            if (
                not run
                or run.organization_id != organization_id
                or run.request_sha256 != alias.request_sha256
            ):
                raise ValueError("Nova plan request could not be recorded safely")
            return run
        # The original key is stored directly on the run for compatibility with
        # records created before alias bindings were introduced.
        return self.db.scalar(
            select(GeneratedPlanRun).where(
                GeneratedPlanRun.organization_id == organization_id,
                GeneratedPlanRun.idempotency_key_sha256 == idempotency_key_sha256,
            )
        )

    def _bind_generated_plan_run_idempotency_key(
        self,
        run: GeneratedPlanRun,
        organization_id: str,
        idempotency_key_sha256: str,
        request_sha256: str,
    ) -> GeneratedPlanRun:
        existing = self._generated_plan_run_for_idempotency_key(
            organization_id, idempotency_key_sha256
        )
        if existing:
            if existing.request_sha256 != request_sha256:
                raise ValueError("Idempotency-Key was already used for a different plan request")
            return existing
        if run.organization_id != organization_id or run.request_sha256 != request_sha256:
            raise ValueError("Nova plan request could not be recorded safely")
        if run.idempotency_key_sha256 == idempotency_key_sha256:
            return run

        self.db.add(
            GeneratedPlanRunIdempotencyKey(
                organization_id=organization_id,
                idempotency_key_sha256=idempotency_key_sha256,
                request_sha256=request_sha256,
                run_id=run.id,
            )
        )
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self._generated_plan_run_for_idempotency_key(
                organization_id, idempotency_key_sha256
            )
            if existing and existing.request_sha256 == request_sha256:
                return existing
            if existing:
                raise ValueError(
                    "Idempotency-Key was already used for a different plan request"
                ) from None
            raise ValueError("Nova plan request could not be recorded safely") from None
        return run

    def reconcile_generated_plan_input(
        self, principal: Principal, run_id: str, *, abandon_attempt: bool = False
    ) -> dict[str, Any]:
        """Verify an ambiguous pre-build input or safely abandon its attempt."""
        run = self.db.scalar(
            select(GeneratedPlanRun)
            .where(
                GeneratedPlanRun.id == run_id,
                GeneratedPlanRun.organization_id == principal.organization_id,
            )
            .execution_options(populate_existing=True)
        )
        if not run:
            raise PermissionError("generated plan request not found in this organization")
        if not self._is_workspace_administrator(principal) and run.requester_subject != principal.subject:
            raise PermissionError("generated plan request is not visible to this user")
        if (
            run.state != "RECONCILIATION_REQUIRED"
            or run.error_code != "INPUT_STAGE_RECONCILIATION_REQUIRED"
            or run.codebuild_build_id is not None
            or not run.runner_run_id
            or not run.input_key
            or not run.input_sha256
            or not run.proposal_sha256
        ):
            raise ValueError("only an ambiguous pre-build input attempt can be reconciled here")

        # Keep the input identity from before the external inspection. A retry
        # can update these mutable run fields while this request is in flight.
        attempt_runner_run_id = run.runner_run_id
        attempt_input_key = run.input_key
        attempt_input_sha256 = run.input_sha256
        attempt_proposal_sha256 = run.proposal_sha256

        if abandon_attempt:
            now = datetime.now(UTC)
            abandoned = self.db.execute(
                update(GeneratedPlanRun)
                .where(
                    GeneratedPlanRun.id == run.id,
                    GeneratedPlanRun.organization_id == principal.organization_id,
                    GeneratedPlanRun.state == "RECONCILIATION_REQUIRED",
                    GeneratedPlanRun.error_code == "INPUT_STAGE_RECONCILIATION_REQUIRED",
                    GeneratedPlanRun.codebuild_build_id.is_(None),
                    GeneratedPlanRun.runner_run_id == attempt_runner_run_id,
                    GeneratedPlanRun.input_key == attempt_input_key,
                    GeneratedPlanRun.input_sha256 == attempt_input_sha256,
                    GeneratedPlanRun.proposal_sha256 == attempt_proposal_sha256,
                )
                .values(
                    state="FAILED",
                    error_code="INPUT_ATTEMPT_ABANDONED",
                    error_summary=(
                        "This pre-build input attempt was abandoned. A retry will use a fresh immutable key."
                    ),
                    preparation_phase=None,
                    finished_at=now,
                    updated_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            if abandoned.rowcount != 1:
                self.db.rollback()
                return self.generated_plan_run_detail(principal, run.id)
            self.audit(
                principal,
                "generated_plan_run.input_attempt_abandoned",
                "generated_plan_run",
                run.id,
                {
                    "runner_run_id": attempt_runner_run_id,
                    "input_key": attempt_input_key,
                    "input_sha256": attempt_input_sha256,
                    "state": "FAILED",
                },
            )
            self.db.commit()
            return self.generated_plan_run_detail(principal, run.id)

        dispatcher = self.nova_plan_dispatcher
        if dispatcher is None:
            dispatcher = NovaPlanOnlyDispatcher.from_environment()
        if dispatcher is None:
            raise NovaPlanDispatchError("Nova plan runner is not enabled for input reconciliation")
        expected_key = dispatcher.input_key(attempt_runner_run_id)
        if attempt_input_key != expected_key:
            raise ValueError("stored Nova input key does not match its durable attempt")
        version_id = dispatcher.inspect_staged_input(
            attempt_runner_run_id, attempt_input_key, attempt_input_sha256
        )
        if version_id is None:
            now = datetime.now(UTC)
            absent = self.db.execute(
                update(GeneratedPlanRun)
                .where(
                    GeneratedPlanRun.id == run.id,
                    GeneratedPlanRun.organization_id == principal.organization_id,
                    GeneratedPlanRun.state == "RECONCILIATION_REQUIRED",
                    GeneratedPlanRun.error_code == "INPUT_STAGE_RECONCILIATION_REQUIRED",
                    GeneratedPlanRun.codebuild_build_id.is_(None),
                    GeneratedPlanRun.runner_run_id == attempt_runner_run_id,
                    GeneratedPlanRun.input_key == attempt_input_key,
                    GeneratedPlanRun.input_sha256 == attempt_input_sha256,
                    GeneratedPlanRun.proposal_sha256 == attempt_proposal_sha256,
                )
                .values(
                    state="FAILED",
                    error_code="INPUT_NOT_STAGED",
                    error_summary=(
                        "No input object exists for this attempt. Retry with a fresh idempotency key."
                    ),
                    preparation_phase=None,
                    finished_at=now,
                    updated_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            if absent.rowcount != 1:
                self.db.rollback()
                return self.generated_plan_run_detail(principal, run.id)
            self.audit(
                principal,
                "generated_plan_run.input_confirmed_absent",
                "generated_plan_run",
                run.id,
                {
                    "runner_run_id": attempt_runner_run_id,
                    "input_key": attempt_input_key,
                    "input_sha256": attempt_input_sha256,
                    "state": "FAILED",
                },
            )
            self.db.commit()
            return self.generated_plan_run_detail(principal, run.id)

        now = datetime.now(UTC)
        resumed = self.db.execute(
            update(GeneratedPlanRun)
            .where(
                GeneratedPlanRun.id == run.id,
                GeneratedPlanRun.organization_id == principal.organization_id,
                GeneratedPlanRun.state == "RECONCILIATION_REQUIRED",
                GeneratedPlanRun.error_code == "INPUT_STAGE_RECONCILIATION_REQUIRED",
                GeneratedPlanRun.codebuild_build_id.is_(None),
                GeneratedPlanRun.runner_run_id == attempt_runner_run_id,
                GeneratedPlanRun.input_key == attempt_input_key,
                GeneratedPlanRun.input_sha256 == attempt_input_sha256,
                GeneratedPlanRun.proposal_sha256 == attempt_proposal_sha256,
            )
            .values(
                input_version_id=version_id,
                state="QUEUED",
                error_code=None,
                error_summary=None,
                preparation_phase=None,
                finished_at=None,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        if resumed.rowcount != 1:
            self.db.rollback()
            return self.generated_plan_run_detail(principal, run.id)
        self.audit(
            principal,
            "generated_plan_run.input_reconciled",
            "generated_plan_run",
            run.id,
            {
                "runner_run_id": attempt_runner_run_id,
                "input_key": attempt_input_key,
                "input_sha256": attempt_input_sha256,
                "input_version_id": version_id,
                "state": "QUEUED",
            },
        )
        self.db.commit()
        queued = self.db.scalar(
            select(GeneratedPlanRun)
            .where(GeneratedPlanRun.id == run.id)
            .execution_options(populate_existing=True)
        )
        if queued:
            self._wake_generated_plan_run(queued)
        return self.generated_plan_run_detail(principal, run.id)

    def abandon_generated_plan_generation_attempt(
        self, principal: Principal, run_id: str
    ) -> dict[str, Any]:
        """Mark an uncertain proposal call failed after explicit user confirmation."""
        run = self.db.scalar(
            select(GeneratedPlanRun)
            .where(
                GeneratedPlanRun.id == run_id,
                GeneratedPlanRun.organization_id == principal.organization_id,
            )
            .execution_options(populate_existing=True)
        )
        if not run:
            raise PermissionError("generated plan request not found in this organization")
        if not self._is_workspace_administrator(principal) and run.requester_subject != principal.subject:
            raise PermissionError("generated plan request is not visible to this user")
        uncertain_generation = (
            run.error_code == "PROPOSAL_GENERATION_RECONCILIATION_REQUIRED"
            and run.preparation_phase == "GENERATING_PROPOSAL"
        )
        expired_before_call = (
            run.error_code == "PREPARATION_LEASE_EXPIRED"
            and run.preparation_phase is None
        )
        if (
            run.state != "RECONCILIATION_REQUIRED"
            or not (uncertain_generation or expired_before_call)
            or run.proposal_sha256 is not None
            or run.input_sha256 is not None
            or run.input_version_id is not None
            or run.codebuild_build_id is not None
        ):
            raise ValueError("only an uncertain or pre-call expired attempt can be abandoned here")

        now = datetime.now(UTC)
        abandoned_error_code = (
            "GENERATION_ATTEMPT_ABANDONED"
            if uncertain_generation
            else "PREPARATION_ATTEMPT_ABANDONED"
        )
        abandoned_summary = (
            "The uncertain proposal-generation attempt was explicitly abandoned. "
            "Use the retry action with a fresh idempotency key to start a new attempt."
            if uncertain_generation
            else "The worker lease expired before proposal generation began. "
            "Use the retry action with a fresh idempotency key to start a new attempt."
        )
        abandoned = self.db.execute(
            update(GeneratedPlanRun)
            .where(
                GeneratedPlanRun.id == run.id,
                GeneratedPlanRun.organization_id == principal.organization_id,
                GeneratedPlanRun.state == "RECONCILIATION_REQUIRED",
                GeneratedPlanRun.error_code == run.error_code,
                GeneratedPlanRun.preparation_phase == run.preparation_phase,
                GeneratedPlanRun.runner_run_id == run.runner_run_id,
                GeneratedPlanRun.proposal_sha256.is_(None),
                GeneratedPlanRun.input_sha256.is_(None),
                GeneratedPlanRun.input_version_id.is_(None),
                GeneratedPlanRun.codebuild_build_id.is_(None),
            )
            .values(
                state="FAILED",
                error_code=abandoned_error_code,
                error_summary=abandoned_summary,
                preparation_phase=None,
                preparation_lease_token=None,
                preparation_lease_expires_at=None,
                finished_at=now,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        if abandoned.rowcount != 1:
            self.db.rollback()
            return self.generated_plan_run_detail(principal, run.id)
        self.audit(
            principal,
            "generated_plan_run.generation_attempt_abandoned"
            if uncertain_generation
            else "generated_plan_run.preparation_attempt_abandoned",
            "generated_plan_run",
            run.id,
            {
                "runner_run_id": run.runner_run_id,
                "request_sha256": run.request_sha256,
                "state": "FAILED",
                "error_code": abandoned_error_code,
            },
        )
        self.db.commit()
        return self.generated_plan_run_detail(principal, run.id)

    def reconcile_generated_plan_build_attempt(
        self, principal: Principal, run_id: str
    ) -> dict[str, Any]:
        """Find and bind one exact build after a possibly lost StartBuild response."""
        run = self.db.scalar(
            select(GeneratedPlanRun)
            .where(
                GeneratedPlanRun.id == run_id,
                GeneratedPlanRun.organization_id == principal.organization_id,
            )
            .execution_options(populate_existing=True)
        )
        if not run:
            raise PermissionError("generated plan request not found in this organization")
        if not self._is_workspace_administrator(principal) and run.requester_subject != principal.subject:
            raise PermissionError("generated plan request is not visible to this user")
        uncertain_start = (
            run.state == "RECONCILIATION_REQUIRED"
            and run.error_code == "BUILD_START_RECONCILIATION_REQUIRED"
            and run.preparation_phase == "STARTING_BUILD"
            and bool(run.runner_run_id)
            and run.codebuild_idempotency_token == run.runner_run_id
        )
        uncertain_status = (
            run.state == "RECONCILIATION_REQUIRED"
            and run.error_code
            in {"BUILD_STATUS_UNCONFIRMED", "RUNNER_CONFIGURATION_UNAVAILABLE"}
            and run.preparation_phase is None
            and bool(run.codebuild_build_id)
        )
        if not (uncertain_start or uncertain_status):
            raise ValueError("only an ambiguous CodeBuild start can be reconciled here")

        dispatcher = self.nova_plan_dispatcher or NovaPlanOnlyDispatcher.from_environment()
        if dispatcher is None or dispatcher.project_name != run.codebuild_project:
            raise NovaPlanDispatchError(
                "the exact Nova plan project is unavailable for build reconciliation",
                outcome_uncertain=True,
                phase="build_start",
            )
        if run.codebuild_build_id is not None:
            if not run.codebuild_build_id.startswith(f"{run.codebuild_project}:"):
                raise NovaPlanDispatchError(
                    "the stored Nova plan build ID does not match its durable project",
                    outcome_uncertain=True,
                    phase="build_start",
                )
            self.reconcile_generated_plan_build(run.codebuild_build_id)
            return self.generated_plan_run_detail(principal, run.id)
        # A failed or incomplete search is never evidence that StartBuild did not
        # create a build; leave the durable start-uncertain state intact.
        build = dispatcher.find_build_by_run_id(run.runner_run_id)
        if build is None:
            self.audit(
                principal,
                "generated_plan_run.build_start_lookup_no_match",
                "generated_plan_run",
                run.id,
                {
                    "codebuild_project": run.codebuild_project,
                    "runner_run_id": run.runner_run_id,
                    "state": "RECONCILIATION_REQUIRED",
                },
            )
            self.db.commit()
            return self.generated_plan_run_detail(principal, run.id)
        if (
            build.project_name != run.codebuild_project
            or not isinstance(build.build_id, str)
            or not build.build_id.startswith(f"{run.codebuild_project}:")
        ):
            raise NovaPlanDispatchError(
                "the matched Nova plan build did not match its durable project",
                outcome_uncertain=True,
                phase="build_start",
            )

        now = datetime.now(UTC)
        try:
            bound = self.db.execute(
                update(GeneratedPlanRun)
                .where(
                    GeneratedPlanRun.id == run.id,
                    GeneratedPlanRun.organization_id == principal.organization_id,
                    GeneratedPlanRun.state == "RECONCILIATION_REQUIRED",
                    GeneratedPlanRun.error_code == "BUILD_START_RECONCILIATION_REQUIRED",
                    GeneratedPlanRun.preparation_phase == "STARTING_BUILD",
                    GeneratedPlanRun.codebuild_build_id.is_(None),
                    GeneratedPlanRun.runner_run_id == run.runner_run_id,
                    GeneratedPlanRun.codebuild_idempotency_token
                    == run.codebuild_idempotency_token,
                )
                .values(
                    state="BUILD_STARTED",
                    codebuild_build_id=build.build_id,
                    error_code=None,
                    error_summary=None,
                    preparation_phase=None,
                    preparation_lease_token=None,
                    preparation_lease_expires_at=None,
                    started_at=now,
                    updated_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            if bound.rowcount != 1:
                self.db.rollback()
                return self.generated_plan_run_detail(principal, run.id)
            self.audit(
                principal,
                "generated_plan_run.build_id_recovered",
                "generated_plan_run",
                run.id,
                {
                    "codebuild_project": run.codebuild_project,
                    "codebuild_build_id": build.build_id,
                    "runner_run_id": run.runner_run_id,
                    "state": "BUILD_STARTED",
                },
            )
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise NovaPlanDispatchError(
                "the matched Nova plan build is already bound to another request",
                outcome_uncertain=True,
                phase="build_start",
            ) from None

        # A live build remains BUILD_STARTED. A terminal build is processed by
        # the existing exact-build reconciler before returning the request.
        self.reconcile_generated_plan_build(build.build_id)
        return self.generated_plan_run_detail(principal, run.id)

    def _wake_generated_plan_run(self, run: GeneratedPlanRun) -> None:
        """Wake the durable worker; repeated SQS notifications are safe."""
        if run.state != "QUEUED":
            return
        try:
            self._wake_worker("generated_plan_run", run.id)
        except RuntimeError as error:
            raise NovaPlanDispatchError(
                "Nova plan request is queued, but its worker wake-up could not be confirmed"
            ) from error

    def run_next_generated_plan_run(self) -> bool:
        """Claim and prepare one durable Nova plan request from the SQS wake-up."""
        self._reconcile_expired_generated_plan_run_leases()
        claim = self._claim_next_generated_plan_run()
        if claim is None:
            return False
        run, lease_token = claim
        actor = Principal(run.requester_subject, run.organization_id, "operator")
        dispatcher = self.nova_plan_dispatcher
        if dispatcher is None:
            try:
                dispatcher = NovaPlanOnlyDispatcher.from_environment()
            except NovaPlanDispatchError as error:
                self._finish_generated_plan_run_claim(
                    run,
                    lease_token,
                    state="FAILED",
                    error_code="RUNNER_CONFIGURATION_INVALID",
                    error_summary=str(error),
                    action="generated_plan_run.worker_configuration_failed",
                )
                return True
        if dispatcher is None:
            self._finish_generated_plan_run_claim(
                run,
                lease_token,
                state="FAILED",
                error_code="RUNNER_CONFIGURATION_UNAVAILABLE",
                error_summary="Nova plan generation is not enabled for this worker.",
                action="generated_plan_run.worker_configuration_failed",
            )
            return True

        try:
            revision = self._infrastructure_revision(actor, run.revision_id)
            customer_plan = self._infrastructure_plan(actor, revision.infrastructure_plan_id)
            request_document = run.request_document
            if (
                not isinstance(request_document, dict)
                or canonical_json_digest(request_document) != run.request_sha256
                or request_document.get("organization_id") != run.organization_id
                or request_document.get("project_id") != run.project_id
                or request_document.get("plan_id") != customer_plan.id
                or request_document.get("revision_id") != revision.id
                or request_document.get("revision_sha256") != run.revision_sha256
                or request_document.get("runner_project") != run.codebuild_project
            ):
                raise ValueError("durable Nova plan request did not match its stored digest")
            target = (revision.content or {}).get("target") or {}
            account_id = str(target.get("account_id") or "")
            region = str(target.get("region") or "")
            connection = self._cloud_connection(actor, str(target.get("connection_id") or ""))
            source_plan_id = (revision.content or {}).get("source_deployment_plan_id")
            latest = self.db.scalar(
                select(InfrastructurePlanRevision)
                .where(
                    InfrastructurePlanRevision.infrastructure_plan_id == customer_plan.id,
                    InfrastructurePlanRevision.organization_id == run.organization_id,
                )
                .order_by(InfrastructurePlanRevision.revision_number.desc())
                .limit(1)
            )
            if (
                customer_plan.project_id != run.project_id
                or revision.state
                not in {InfrastructurePlanState.SUBMITTED, InfrastructurePlanState.APPROVED}
                or not latest
                or latest.id != revision.id
                or revision.content_digest != run.revision_sha256
                or plan_hash(revision.content) != run.revision_sha256
                or connection.provider != "aws"
                or connection.setup_state != "VERIFIED"
                or connection.account_id != account_id
                or not re.fullmatch(r"\d{12}", account_id)
                or not re.fullmatch(r"[a-z]{2}(?:-[a-z0-9]+)+-\d", region)
                or request_document.get("target_account_id") != account_id
                or request_document.get("region") != region
                or request_document.get("generator_model") != self.terraform_generator.model_id
                or request_document.get("runner_project") != dispatcher.project_name
                or not source_plan_id
            ):
                raise ValueError("durable Nova plan request no longer matches its submitted revision")
            if revision.state == InfrastructurePlanState.APPROVED:
                decision = self.db.scalar(
                    select(InfrastructurePlanDecisionRecord).where(
                        InfrastructurePlanDecisionRecord.revision_id == revision.id,
                        InfrastructurePlanDecisionRecord.organization_id == run.organization_id,
                    )
                )
                if (
                    not decision
                    or decision.decision != InfrastructurePlanDecision.APPROVED
                    or decision.approved_digest != run.revision_sha256
                ):
                    raise ValueError("approved customer revision has no matching approval record")
            self._plan(actor, str(source_plan_id))
            self._project(actor, customer_plan.project_id)
        except (PermissionError, ValueError, KeyError) as error:
            self._finish_generated_plan_run_claim(
                run,
                lease_token,
                state="FAILED",
                error_code="DURABLE_REQUEST_INVALID",
                error_summary=str(error),
                action="generated_plan_run.worker_validation_failed",
            )
            return True

        heartbeat_stop = threading.Event()
        lease_lost = threading.Event()
        bind = self.db.get_bind()
        is_sqlite_memory = bind.dialect.name == "sqlite" and bind.url.database == ":memory:"
        heartbeat: threading.Thread | None = None
        if not is_sqlite_memory:
            heartbeat = threading.Thread(
                target=self._renew_generated_plan_run_lease,
                args=(run.id, lease_token, heartbeat_stop, lease_lost),
                daemon=True,
                name=f"davdeploy-nova-plan-lease-{run.id[:8]}",
            )
            heartbeat.start()
        try:
            self._prepare_generated_plan_run(
                actor,
                run,
                lease_token,
                revision=revision,
                customer_plan=customer_plan,
                request_document=request_document,
                dispatcher=dispatcher,
                lease_lost=lease_lost,
            )
        except Exception:  # noqa: BLE001 - worker failures require durable reconciliation
            self.db.rollback()
            phase = run.preparation_phase
            if phase in {"STAGING_INPUT", "VERIFYING_INPUT"}:
                error_code = "INPUT_STAGE_RECONCILIATION_REQUIRED"
                error_summary = (
                    "Input storage could not be confirmed. Verify the exact staged object or "
                    "abandon this attempt before retrying."
                )
            elif phase == "GENERATING_PROPOSAL":
                error_code = "PROPOSAL_GENERATION_RECONCILIATION_REQUIRED"
                error_summary = (
                    "Proposal generation could not be confirmed. Explicitly abandon it with "
                    "reconcile-generation before retrying with a new key."
                )
            elif phase == "STARTING_BUILD":
                error_code = "BUILD_START_RECONCILIATION_REQUIRED"
                error_summary = (
                    "CodeBuild may have started without returning a build ID. Do not retry this run; "
                    "use reconcile-build to search for one exact build in the configured project."
                )
            else:
                error_code = "WORKER_OUTCOME_UNCERTAIN"
                error_summary = "The worker stopped before its outcome could be confirmed."
            self._finish_generated_plan_run_claim(
                run,
                lease_token,
                state="RECONCILIATION_REQUIRED",
                error_code=error_code,
                error_summary=error_summary,
                action="generated_plan_run.worker_outcome_uncertain",
            )
        finally:
            heartbeat_stop.set()
            if heartbeat:
                heartbeat.join(timeout=NOVA_PLAN_WORKER_HEARTBEAT_SECONDS + 1)
        return True

    def _claim_next_generated_plan_run(self) -> tuple[GeneratedPlanRun, str] | None:
        """Atomically claim one queued run and attach an expiring lease token."""
        candidate = self.db.scalar(
            select(GeneratedPlanRun)
            .where(GeneratedPlanRun.state == "QUEUED")
            .order_by(GeneratedPlanRun.created_at, GeneratedPlanRun.id)
            .limit(1)
        )
        if candidate is None:
            return None
        now = datetime.now(UTC)
        lease_token = secrets.token_hex(32)
        claimed = self.db.execute(
            update(GeneratedPlanRun)
            .where(
                GeneratedPlanRun.id == candidate.id,
                GeneratedPlanRun.organization_id == candidate.organization_id,
                GeneratedPlanRun.request_sha256 == candidate.request_sha256,
                GeneratedPlanRun.state == "QUEUED",
            )
            .values(
                state="PREPARING",
                preparation_lease_token=lease_token,
                preparation_lease_expires_at=now
                + timedelta(seconds=NOVA_PLAN_PREPARATION_LEASE_SECONDS),
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            self.db.rollback()
            return None
        self.db.commit()
        run = self.db.scalar(
            select(GeneratedPlanRun)
            .where(GeneratedPlanRun.id == candidate.id)
            .execution_options(populate_existing=True)
        )
        return (run, lease_token) if run is not None else None

    def _renew_generated_plan_run_lease(
        self, run_id: str, lease_token: str, stop: threading.Event, lease_lost: threading.Event
    ) -> None:
        """Extend the worker's claim from an independent database session."""
        bind = self.db.get_bind()
        while not stop.wait(NOVA_PLAN_WORKER_HEARTBEAT_SECONDS):
            now = datetime.now(UTC)
            try:
                with Session(bind=bind) as heartbeat_db:
                    renewed = heartbeat_db.execute(
                        update(GeneratedPlanRun)
                        .where(
                            GeneratedPlanRun.id == run_id,
                            GeneratedPlanRun.state == "PREPARING",
                            GeneratedPlanRun.preparation_lease_token == lease_token,
                            GeneratedPlanRun.preparation_lease_expires_at > now,
                        )
                        .values(
                            preparation_lease_expires_at=now
                            + timedelta(seconds=NOVA_PLAN_PREPARATION_LEASE_SECONDS),
                            updated_at=now,
                        )
                        .execution_options(synchronize_session=False)
                    )
                    heartbeat_db.commit()
                if renewed.rowcount != 1:
                    lease_lost.set()
                    return
            except SQLAlchemyError:
                lease_lost.set()
                return

    def _generated_plan_run_lease_is_current(
        self, run_id: str, lease_token: str
    ) -> bool:
        return (
            self.db.scalar(
                select(GeneratedPlanRun.id).where(
                    GeneratedPlanRun.id == run_id,
                    GeneratedPlanRun.state == "PREPARING",
                    GeneratedPlanRun.preparation_lease_token == lease_token,
                    GeneratedPlanRun.preparation_lease_expires_at > datetime.now(UTC),
                )
            )
            is not None
        )

    def _set_generated_plan_run_phase(
        self, run: GeneratedPlanRun, lease_token: str, phase: str
    ) -> bool:
        """Persist the next external boundary before the worker calls it."""
        updated = self.db.execute(
            update(GeneratedPlanRun)
            .where(
                GeneratedPlanRun.id == run.id,
                GeneratedPlanRun.state == "PREPARING",
                GeneratedPlanRun.preparation_lease_token == lease_token,
                GeneratedPlanRun.preparation_lease_expires_at > datetime.now(UTC),
            )
            .values(preparation_phase=phase, updated_at=datetime.now(UTC))
            .execution_options(synchronize_session=False)
        )
        if updated.rowcount != 1:
            self.db.rollback()
            return False
        self.db.commit()
        # The Core update already committed this value. Mark it as committed in
        # the identity map so Session.commit() cannot flush it back over a later
        # compare-and-set update that clears the phase.
        set_committed_value(run, "preparation_phase", phase)
        return True

    def _finish_generated_plan_run_claim(
        self,
        run: GeneratedPlanRun,
        lease_token: str,
        *,
        state: str,
        error_code: str,
        error_summary: str,
        action: str,
        codebuild_build_id: str | None = None,
    ) -> bool:
        """Finish only the claim still owned by this worker."""
        now = datetime.now(UTC)
        values: dict[str, Any] = {
            "state": state,
            "error_code": error_code,
            "error_summary": error_summary,
            "preparation_lease_token": None,
            "preparation_lease_expires_at": None,
            "finished_at": now if state == "FAILED" else None,
            "updated_at": now,
        }
        if state != "RECONCILIATION_REQUIRED":
            values["preparation_phase"] = None
        if codebuild_build_id and codebuild_build_id.startswith(f"{run.codebuild_project}:"):
            values["codebuild_build_id"] = codebuild_build_id
        finished = self.db.execute(
            update(GeneratedPlanRun)
            .where(
                GeneratedPlanRun.id == run.id,
                GeneratedPlanRun.state == "PREPARING",
                GeneratedPlanRun.preparation_lease_token == lease_token,
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        if finished.rowcount != 1:
            self.db.rollback()
            if (
                state == "RECONCILIATION_REQUIRED"
                and codebuild_build_id
                and codebuild_build_id.startswith(f"{run.codebuild_project}:")
            ):
                recovered = self.db.execute(
                    update(GeneratedPlanRun)
                    .where(
                        GeneratedPlanRun.id == run.id,
                        GeneratedPlanRun.state == "RECONCILIATION_REQUIRED",
                        GeneratedPlanRun.error_code == "BUILD_START_RECONCILIATION_REQUIRED",
                        GeneratedPlanRun.preparation_phase == "STARTING_BUILD",
                        GeneratedPlanRun.codebuild_build_id.is_(None),
                    )
                    .values(
                        state="BUILD_STARTED",
                        codebuild_build_id=codebuild_build_id,
                        error_code=None,
                        error_summary=None,
                        preparation_phase=None,
                        preparation_lease_token=None,
                        preparation_lease_expires_at=None,
                        started_at=now,
                        updated_at=now,
                    )
                    .execution_options(synchronize_session=False)
                )
                if recovered.rowcount == 1:
                    self.audit(
                        Principal("system-nova-plan-worker", run.organization_id, "operator"),
                        "generated_plan_run.build_id_recovered",
                        "generated_plan_run",
                        run.id,
                        {
                            "codebuild_project": run.codebuild_project,
                            "codebuild_build_id": codebuild_build_id,
                            "state": "RECONCILIATION_REQUIRED",
                        },
                    )
                    self.db.commit()
                    return True
                self.db.rollback()
            return False
        self.audit(
            Principal("system-nova-plan-worker", run.organization_id, "operator"),
            action,
            "generated_plan_run",
            run.id,
            {
                "state": state,
                "error_code": error_code,
                "codebuild_build_id": codebuild_build_id,
            },
        )
        self.db.commit()
        return True

    def _reconcile_expired_generated_plan_run_leases(self) -> None:
        """Mark abandoned preparation as uncertain; never replay external work."""
        now = datetime.now(UTC)
        expired_runs = list(
            self.db.scalars(
                select(GeneratedPlanRun)
                .where(
                    GeneratedPlanRun.state == "PREPARING",
                    GeneratedPlanRun.preparation_lease_expires_at <= now,
                )
                .order_by(GeneratedPlanRun.preparation_lease_expires_at)
                .limit(100)
            )
        )
        for run in expired_runs:
            self._expire_generated_plan_run_lease(run, now)

    def _expire_generated_plan_run_lease(
        self, run: GeneratedPlanRun, now: datetime | None = None
    ) -> bool:
        """Fence an expired claim and make its uncertain outcome visible."""
        current_time = now or datetime.now(UTC)
        lease_token = run.preparation_lease_token
        if not lease_token:
            return False
        phase = run.preparation_phase
        if phase in {"STAGING_INPUT", "VERIFYING_INPUT"}:
            error_code = "INPUT_STAGE_RECONCILIATION_REQUIRED"
            error_summary = (
                "The worker stopped while staging or verifying input, before any build start. "
                "Verify the exact input object or abandon this attempt before retrying."
            )
        elif phase == "GENERATING_PROPOSAL":
            error_code = "PROPOSAL_GENERATION_RECONCILIATION_REQUIRED"
            error_summary = (
                "The proposal-generation result is uncertain and this request is blocked to avoid "
                "replay. Explicitly abandon it with reconcile-generation before retrying with a new key."
            )
        elif phase == "STARTING_BUILD":
            error_code = "BUILD_START_RECONCILIATION_REQUIRED"
            error_summary = (
                "CodeBuild may have started without returning a build ID. Do not retry this run; "
                "use reconcile-build to search for one exact build in the configured project."
            )
        else:
            error_code = "PREPARATION_LEASE_EXPIRED"
            error_summary = (
                "The worker lease expired before its runner start could be confirmed. "
                "Reconcile the request before retrying."
            )
        expired = self.db.execute(
            update(GeneratedPlanRun)
            .where(
                GeneratedPlanRun.id == run.id,
                GeneratedPlanRun.state == "PREPARING",
                GeneratedPlanRun.preparation_lease_token == lease_token,
                GeneratedPlanRun.preparation_lease_expires_at <= current_time,
            )
            .values(
                state="RECONCILIATION_REQUIRED",
                error_code=error_code,
                error_summary=error_summary,
                preparation_lease_token=None,
                preparation_lease_expires_at=None,
                updated_at=current_time,
            )
            .execution_options(synchronize_session=False)
        )
        if expired.rowcount != 1:
            self.db.rollback()
            return False
        self.audit(
            Principal("system-nova-plan-reconcile", run.organization_id, "operator"),
            "generated_plan_run.preparation_expired",
            "generated_plan_run",
            run.id,
            {"state": "RECONCILIATION_REQUIRED", "error_code": error_code},
        )
        self.db.commit()
        return True

    def _prepare_generated_plan_run(
        self,
        principal: Principal,
        run: GeneratedPlanRun,
        lease_token: str,
        *,
        revision: InfrastructurePlanRevision,
        customer_plan: InfrastructurePlan,
        request_document: dict[str, Any],
        dispatcher: NovaPlanOnlyDispatcher,
        lease_lost: threading.Event,
    ) -> dict[str, Any]:
        if (
            run.organization_id != principal.organization_id
            or run.requester_subject != principal.subject
            or run.state != "PREPARING"
            or run.preparation_lease_token != lease_token
        ):
            return self.generated_plan_run_detail(principal, run.id)
        runner_run_id = run.runner_run_id or run.id
        idempotency_token = run.codebuild_idempotency_token
        expected_input_key = dispatcher.input_key(runner_run_id)
        if (
            run.input_key != expected_input_key
            or run.result_key != dispatcher.result_key(runner_run_id)
            or not isinstance(idempotency_token, str)
            or idempotency_token != runner_run_id
        ):
            raise ValueError("durable Nova plan attempt keys did not match the stored runner ID")
        target = (revision.content or {}).get("target") or {}
        ownership_scope = self._generated_plan_ownership_scope(
            principal,
            customer_plan.project_id,
            customer_plan.id,
            revision.id,
            target.get("environment_id"),
        )
        build = None
        generated = None
        proposal_sha256 = run.proposal_sha256
        input_sha256 = run.input_sha256
        input_version_id = run.input_version_id
        try:
            if lease_lost.is_set() or not self._generated_plan_run_lease_is_current(
                run.id, lease_token
            ):
                raise NovaPlanDispatchError(
                    "Nova plan worker lease was lost before generation", outcome_uncertain=True
                )

            if input_version_id:
                if not proposal_sha256 or not input_sha256:
                    raise ValueError("durable staged Nova input is missing its digest binding")
                if not self._set_generated_plan_run_phase(run, lease_token, "VERIFYING_INPUT"):
                    raise NovaPlanDispatchError(
                        "Nova plan worker lease was lost before input verification",
                        outcome_uncertain=True,
                        phase="input_stage",
                    )
                inspected_version = dispatcher.inspect_staged_input(
                    runner_run_id, run.input_key, input_sha256
                )
                if inspected_version != input_version_id:
                    raise NovaPlanDispatchError(
                        "Nova plan input version no longer matches the durable attempt",
                        outcome_uncertain=True,
                        phase="input_stage",
                    )
            else:
                if not self._set_generated_plan_run_phase(
                    run, lease_token, "GENERATING_PROPOSAL"
                ):
                    raise NovaPlanDispatchError(
                        "Nova plan worker lease was lost before generation",
                        outcome_uncertain=True,
                    )
                generated = self.terraform_generator.generate(
                    approved_plan=revision.content,
                    tenant=TenantScope(
                        organization_id=principal.organization_id,
                        workspace_id=principal.organization_id,
                        project_id=customer_plan.project_id,
                        actor_id=principal.subject,
                    ),
                    source_revision=revision.id,
                )
                proposal = generated.proposal
                if (
                    proposal.source_revision != revision.id
                    or proposal.requirements.region != target.get("region")
                ):
                    raise ValueError("Nova proposal did not match the trusted revision and region")
                proposal_sha256 = canonical_json_digest(proposal.model_dump(mode="json"))
                request_payload = {
                    **request_document,
                    "run_id": runner_run_id,
                    "control_plane_run_id": run.id,
                    "proposal_sha256": proposal_sha256,
                    "ownership_scope": {
                        "organization_id": ownership_scope.organization_id,
                        "workspace_id": ownership_scope.workspace_id,
                        "project_id": ownership_scope.project_id,
                        "plan_id": ownership_scope.plan_id,
                        "revision_id": ownership_scope.revision_id,
                        "environment_id": ownership_scope.environment_id,
                        "scope_sha256": ownership_scope.scope_sha256(),
                        "plan_id_sha256": ownership_scope.plan_id_sha256(),
                        "tags": ownership_scope.tags(),
                    },
                    "proposal": proposal.model_dump(mode="json"),
                    "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                }
                expected_input_sha256 = canonical_json_digest(request_payload)
                if lease_lost.is_set() or not self._generated_plan_run_lease_is_current(
                    run.id, lease_token
                ):
                    raise NovaPlanDispatchError(
                        "Nova plan worker lease was lost before input staging",
                        outcome_uncertain=True,
                    )
                prepared = self.db.execute(
                    update(GeneratedPlanRun)
                    .where(
                        GeneratedPlanRun.id == run.id,
                        GeneratedPlanRun.state == "PREPARING",
                        GeneratedPlanRun.preparation_lease_token == lease_token,
                    )
                    .values(
                        proposal_sha256=proposal_sha256,
                        input_sha256=expected_input_sha256,
                        input_version_id=None,
                        preparation_phase="STAGING_INPUT",
                        updated_at=datetime.now(UTC),
                    )
                    .execution_options(synchronize_session=False)
                )
                if prepared.rowcount != 1:
                    self.db.rollback()
                    raise NovaPlanDispatchError(
                        "Nova plan worker lease was lost before input staging",
                        outcome_uncertain=True,
                    )
                run.proposal_sha256 = proposal_sha256
                run.input_sha256 = expected_input_sha256
                run.input_version_id = None
                run.preparation_phase = "STAGING_INPUT"
                self.audit(
                    Principal("system-nova-plan-worker", run.organization_id, "operator"),
                    "generated_plan_run.input_stage_started",
                    "generated_plan_run",
                    run.id,
                    {
                        "runner_run_id": runner_run_id,
                        "input_key": run.input_key,
                        "input_sha256": expected_input_sha256,
                        "proposal_sha256": proposal_sha256,
                    },
                )
                self.db.commit()

                input_key, input_sha256, input_version_id = dispatcher.stage_input(
                    runner_run_id, request_payload
                )
                if input_key != run.input_key or input_sha256 != expected_input_sha256:
                    raise NovaPlanDispatchError(
                        "Nova plan input did not match its durable digest binding",
                        outcome_uncertain=True,
                        phase="input_stage",
                    )
                staged = self.db.execute(
                    update(GeneratedPlanRun)
                    .where(
                        GeneratedPlanRun.id == run.id,
                        GeneratedPlanRun.state == "PREPARING",
                        GeneratedPlanRun.preparation_lease_token == lease_token,
                    )
                    .values(
                        input_version_id=input_version_id,
                        updated_at=datetime.now(UTC),
                    )
                    .execution_options(synchronize_session=False)
                )
                if staged.rowcount != 1:
                    self.db.rollback()
                    raise NovaPlanDispatchError(
                        "Nova plan worker lease was lost after input staging",
                        outcome_uncertain=True,
                        phase="input_stage",
                    )
                run.input_version_id = input_version_id
                response_usage = generated.response.usage
                self._record_model_usage(
                    principal,
                    {
                        "request_id": generated.response.request.request_id,
                        "provider": generated.response.request.provider,
                        "model": generated.response.request.model,
                        "prompt_version": generated.response.request.prompt_version,
                        "usage": response_usage.model_dump(mode="json") if response_usage else {},
                        "attempt_count": (response_usage.retry_count + 1) if response_usage else 1,
                        "retry_count": response_usage.retry_count if response_usage else 0,
                        "latency_ms": response_usage.latency_ms if response_usage else None,
                        "measured_at": (
                            response_usage.measured_at.isoformat() if response_usage else None
                        ),
                        "estimated_cost_usd": (
                            response_usage.estimated_cost_usd if response_usage else None
                        ),
                    },
                )
                self.audit(
                    Principal("system-nova-plan-worker", run.organization_id, "operator"),
                    "generated_plan_run.input_staged",
                    "generated_plan_run",
                    run.id,
                    {
                        "input_sha256": input_sha256,
                        "input_version_id": input_version_id,
                        "proposal_sha256": proposal_sha256,
                        "state": run.state,
                    },
                )
                self.db.commit()

            if not proposal_sha256 or not input_sha256 or not input_version_id:
                raise ValueError("durable Nova input staging is incomplete")
            if lease_lost.is_set() or not self._generated_plan_run_lease_is_current(
                run.id, lease_token
            ):
                raise NovaPlanDispatchError(
                    "Nova plan worker lease was lost before the runner start",
                    outcome_uncertain=True,
                    phase="input_stage",
                )
            if not self._set_generated_plan_run_phase(run, lease_token, "STARTING_BUILD"):
                raise NovaPlanDispatchError(
                    "Nova plan worker lease was lost before the runner start",
                    outcome_uncertain=True,
                    phase="input_stage",
                )
            build = dispatcher.start_build(runner_run_id, idempotency_token)
            if build.project_name != run.codebuild_project:
                raise NovaPlanDispatchError(
                    "Nova plan build project did not match its durable request",
                    outcome_uncertain=True,
                )
            started_at = datetime.now(UTC)
            started = self.db.execute(
                update(GeneratedPlanRun)
                .where(
                    GeneratedPlanRun.id == run.id,
                    GeneratedPlanRun.state == "PREPARING",
                    GeneratedPlanRun.preparation_lease_token == lease_token,
                )
                .values(
                    codebuild_build_id=build.build_id,
                    state="BUILD_STARTED",
                    preparation_phase=None,
                    started_at=started_at,
                    preparation_lease_token=None,
                    preparation_lease_expires_at=None,
                    error_code=None,
                    error_summary=None,
                    updated_at=started_at,
                )
                .execution_options(synchronize_session=False)
            )
            if started.rowcount != 1:
                self.db.rollback()
                raise NovaPlanDispatchError(
                    "Nova plan build started but could not be bound to its durable request",
                    outcome_uncertain=True,
                )
            self.audit(
                Principal("system-nova-plan-worker", run.organization_id, "operator"),
                "generated_plan_run.build_started",
                "generated_plan_run",
                run.id,
                {
                    "codebuild_project": run.codebuild_project,
                    "codebuild_build_id": build.build_id,
                    "runner_run_id": runner_run_id,
                    "request_sha256": run.request_sha256,
                    "proposal_sha256": proposal_sha256,
                    "input_sha256": input_sha256,
                    "state": run.state,
                },
            )
            self.db.commit()
        except NovaTerraformGenerationFailed as error:
            self.db.rollback()
            generation_uncertain = error.outcome_uncertain
            self._finish_generated_plan_run_claim(
                run,
                lease_token,
                state="RECONCILIATION_REQUIRED" if generation_uncertain else "FAILED",
                error_code=(
                    "PROPOSAL_GENERATION_RECONCILIATION_REQUIRED"
                    if generation_uncertain
                    else "NOVA_GENERATION_FAILED"
                ),
                error_summary=(
                    "The provider response was lost or could not be confirmed. Explicitly abandon "
                    "this attempt with reconcile-generation before retrying with a new key."
                    if generation_uncertain
                    else "Nova could not produce a validated proposal. Review the request and try again."
                ),
                action=(
                    "generated_plan_run.generation_uncertain"
                    if generation_uncertain
                    else "generated_plan_run.generation_failed"
                ),
            )
            self._record_model_usage(
                Principal("system-nova-plan-worker", run.organization_id, "operator"),
                {
                    "provider": "bedrock",
                    "model": self.terraform_generator.model_id,
                    "prompt_version": "terraform-nova2-contract-v3",
                    "usage": error.usage.model_dump(mode="json"),
                    "attempt_count": error.attempt_count,
                    "retry_count": error.usage.retry_count,
                    "latency_ms": error.usage.latency_ms,
                    "measured_at": error.usage.measured_at.isoformat(),
                    "estimated_cost_usd": error.usage.estimated_cost_usd,
                    "failure": "generation_failed",
                    "evidence": [_model_evidence_summary(item) for item in error.evidence],
                },
            )
            self.db.commit()
        except NovaPlanDispatchError as error:
            self.db.rollback()
            uncertain = error.outcome_uncertain
            input_stage_failure = error.phase == "input_stage"
            proposal_uncertain = uncertain and run.preparation_phase == "GENERATING_PROPOSAL"
            build_start_uncertain = uncertain and run.preparation_phase == "STARTING_BUILD"
            self._finish_generated_plan_run_claim(
                run,
                lease_token,
                state="RECONCILIATION_REQUIRED" if uncertain else "FAILED",
                error_code=(
                    "INPUT_STAGE_RECONCILIATION_REQUIRED"
                    if input_stage_failure and uncertain
                    else "INPUT_STAGE_FAILED"
                    if input_stage_failure
                    else "PROPOSAL_GENERATION_RECONCILIATION_REQUIRED"
                    if proposal_uncertain
                    else "BUILD_START_RECONCILIATION_REQUIRED"
                    if build_start_uncertain
                    else "DISPATCH_UNCERTAIN"
                    if uncertain
                    else "DISPATCH_FAILED"
                ),
                error_summary=(
                    "Input storage could not be confirmed. Verify the exact staged object or "
                    "abandon this attempt before retrying."
                    if input_stage_failure and uncertain
                    else str(error)
                    if input_stage_failure
                    else "Proposal generation could not be confirmed. Explicitly abandon it with "
                    "reconcile-generation before retrying with a new key."
                    if proposal_uncertain
                    else "CodeBuild may have started without returning a build ID. Do not retry this run; "
                    "use reconcile-build to search for one exact build in the configured project."
                    if build_start_uncertain
                    else "The build start could not be confirmed. Check the run status before retrying."
                    if uncertain
                    else str(error)
                ),
                action="generated_plan_run.dispatch_failed",
                codebuild_build_id=build.build_id if build else None,
            )
        except ModelGatewayUnavailable as error:
            self.db.rollback()
            generation_uncertain = error.outcome_uncertain
            self._finish_generated_plan_run_claim(
                run,
                lease_token,
                state="RECONCILIATION_REQUIRED" if generation_uncertain else "FAILED",
                error_code=(
                    "PROPOSAL_GENERATION_RECONCILIATION_REQUIRED"
                    if generation_uncertain
                    else "NOVA_GENERATION_UNAVAILABLE"
                ),
                error_summary=(
                    "The provider response was lost or could not be confirmed. Explicitly abandon "
                    "this attempt with reconcile-generation before retrying with a new key."
                    if generation_uncertain
                    else "Nova could not complete this plan request. Try again later."
                ),
                action=(
                    "generated_plan_run.generation_uncertain"
                    if generation_uncertain
                    else "generated_plan_run.generation_unavailable"
                ),
            )
        except ValueError as error:
            self.db.rollback()
            self._finish_generated_plan_run_claim(
                run,
                lease_token,
                state="FAILED",
                error_code="PREPARATION_REJECTED",
                error_summary=str(error),
                action="generated_plan_run.preparation_rejected",
            )
        except SQLAlchemyError:
            self.db.rollback()
            phase = run.preparation_phase
            if build or phase == "STARTING_BUILD":
                error_code = "BUILD_START_RECONCILIATION_REQUIRED"
                error_summary = (
                    "CodeBuild may have started without a durable completion record. Do not retry "
                    "this run; use reconcile-build or reconcile the recorded build ID."
                )
                action = "generated_plan_run.build_start_uncertain"
            elif phase in {"STAGING_INPUT", "VERIFYING_INPUT"}:
                error_code = "INPUT_STAGE_RECONCILIATION_REQUIRED"
                error_summary = (
                    "Input storage could not be confirmed. Verify the exact staged object or "
                    "abandon this attempt before retrying."
                )
                action = "generated_plan_run.input_stage_uncertain"
            elif phase == "GENERATING_PROPOSAL":
                error_code = "PROPOSAL_GENERATION_RECONCILIATION_REQUIRED"
                error_summary = (
                    "Proposal generation could not be confirmed. Explicitly abandon it with "
                    "reconcile-generation before retrying with a new key."
                )
                action = "generated_plan_run.generation_uncertain"
            else:
                error_code = "PREPARATION_OUTCOME_UNCERTAIN"
                error_summary = "The request could not be fully confirmed. Check its status before retrying."
                action = "generated_plan_run.preparation_uncertain"
            self._finish_generated_plan_run_claim(
                run,
                lease_token,
                state="RECONCILIATION_REQUIRED",
                error_code=error_code,
                error_summary=error_summary,
                action=action,
                codebuild_build_id=build.build_id if build else None,
            )
        return self.generated_plan_run_detail(principal, run.id)

    def generated_plan_run_detail(self, principal: Principal, run_id: str) -> dict[str, Any]:
        run = self.db.scalar(
            select(GeneratedPlanRun).where(
                GeneratedPlanRun.id == run_id,
                GeneratedPlanRun.organization_id == principal.organization_id,
            ).execution_options(populate_existing=True)
        )
        if not run:
            raise PermissionError("generated plan request not found in this organization")
        if not self._is_workspace_administrator(principal) and run.requester_subject != principal.subject:
            raise PermissionError("generated plan request is not visible to this user")
        expiry = run.preparation_lease_expires_at
        if run.state == "PREPARING" and expiry:
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=UTC)
            if expiry <= datetime.now(UTC):
                self._expire_generated_plan_run_lease(run)
                refreshed = self.db.scalar(
                    select(GeneratedPlanRun)
                    .where(GeneratedPlanRun.id == run_id)
                    .execution_options(populate_existing=True)
                )
                if refreshed is not None:
                    run = refreshed
        return self._generated_plan_run_payload(run)

    @staticmethod
    def _generated_plan_run_payload(run: GeneratedPlanRun) -> dict[str, Any]:
        return {
            "id": run.id,
            "project_id": run.project_id,
            "revision_id": run.revision_id,
            "revision_sha256": run.revision_sha256,
            "proposal_sha256": run.proposal_sha256,
            "state": run.state,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "error_code": run.error_code,
            "error_summary": run.error_summary,
            "execution_boundary": (
                "A CodeBuild start is not a verified Terraform plan. A completed build remains "
                "unverified until its exact result and saved-plan artifact are validated. "
                "This run cannot apply or destroy resources."
            ),
        }

    def reconcile_generated_plan_build(self, build_id: str) -> bool:
        """Record a completion only for the exact build bound to one plan run."""
        normalized_build_id = build_id.rsplit("/", 1)[-1]
        run = self.db.scalar(
            select(GeneratedPlanRun).where(
                GeneratedPlanRun.codebuild_build_id == normalized_build_id
            )
        )
        if not run:
            return False
        if run.state not in {"BUILD_STARTED", "RECONCILIATION_REQUIRED"}:
            return True
        try:
            dispatcher = self.nova_plan_dispatcher or NovaPlanOnlyDispatcher.from_environment()
        except NovaPlanDispatchError:
            return self._mark_nova_plan_build_status_unconfirmed(
                run,
                normalized_build_id,
                "The configured runner could not be loaded. Retry status reconciliation after fixing its configuration.",
            )
        if dispatcher is None:
            return self._mark_nova_plan_build_status_unconfirmed(
                run,
                normalized_build_id,
                "The configured runner is unavailable. Retry status reconciliation after it is enabled.",
            )
        try:
            build = dispatcher.describe_build(normalized_build_id)
        except NovaPlanDispatchError:
            # The SQS wake-up can be acknowledged after this method returns.
            # Keep the run recoverable through the authenticated exact-build route.
            return self._mark_nova_plan_build_status_unconfirmed(
                run,
                normalized_build_id,
                "The runner result could not be confirmed. Retry status reconciliation.",
            )
        if build.project_name != run.codebuild_project or build.build_id != normalized_build_id:
            return self._mark_nova_plan_build_status_unconfirmed(
                run,
                normalized_build_id,
                "The runner returned a different build identity. Retry status reconciliation after checking its configuration.",
            )
        if build.status in {"IN_PROGRESS", "QUEUED"}:
            return False
        now = datetime.now(UTC)
        terminal_state = "BUILD_SUCCEEDED_UNVERIFIED" if build.status == "SUCCEEDED" else "FAILED"
        terminal_error_code = (
            "PLAN_RESULT_NOT_VERIFIED" if build.status == "SUCCEEDED" else f"CODEBUILD_{build.status}"
        )
        terminal_error_summary = (
            "The build finished, but no trusted result handler is enabled; "
            "no Terraform plan is available for approval."
            if build.status == "SUCCEEDED"
            else "Nova plan generation did not complete successfully."
        )
        # Reconcile with compare-and-set semantics. Another delivery may finish
        # this build while a retry has already started; the old build must not
        # overwrite the new attempt's state.
        reconciled = self.db.execute(
            update(GeneratedPlanRun)
            .where(
                GeneratedPlanRun.id == run.id,
                GeneratedPlanRun.codebuild_project == run.codebuild_project,
                GeneratedPlanRun.codebuild_build_id == normalized_build_id,
                GeneratedPlanRun.state.in_(("BUILD_STARTED", "RECONCILIATION_REQUIRED")),
                or_(
                    GeneratedPlanRun.error_code.is_(None),
                    GeneratedPlanRun.error_code.in_(
                        (
                            "BUILD_START_RECONCILIATION_REQUIRED",
                            "BUILD_STATUS_UNCONFIRMED",
                            "PREPARATION_LEASE_EXPIRED",
                        )
                    ),
                ),
            )
            .values(
                state=terminal_state,
                error_code=terminal_error_code,
                error_summary=terminal_error_summary,
                finished_at=now,
                preparation_lease_expires_at=None,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        if reconciled.rowcount != 1:
            self.db.rollback()
            return True
        if build.status == "SUCCEEDED":
            audit_state = "BUILD_SUCCEEDED_UNVERIFIED"
        else:
            audit_state = "FAILED"
        self.audit(
            Principal("system-nova-plan-worker", run.organization_id, "operator"),
            "generated_plan_run.build_reconciled",
            "generated_plan_run",
            run.id,
            {
                "codebuild_project": run.codebuild_project,
                "codebuild_build_id": normalized_build_id,
                "build_status": build.status,
                "state": audit_state,
                "error_code": terminal_error_code,
            },
        )
        self.db.commit()
        self.db.expire(run)
        return True

    def _mark_nova_plan_build_status_unconfirmed(
        self, run: GeneratedPlanRun, build_id: str, summary: str
    ) -> bool:
        """Preserve recovery for an exact bound build when status cannot be trusted."""
        status_uncertain = self.db.execute(
            update(GeneratedPlanRun)
            .where(
                GeneratedPlanRun.id == run.id,
                GeneratedPlanRun.codebuild_project == run.codebuild_project,
                GeneratedPlanRun.codebuild_build_id == build_id,
                GeneratedPlanRun.state.in_(
                    ("BUILD_STARTED", "RECONCILIATION_REQUIRED")
                ),
                or_(
                    GeneratedPlanRun.error_code.is_(None),
                    GeneratedPlanRun.error_code.in_(
                        (
                            "BUILD_START_RECONCILIATION_REQUIRED",
                            "BUILD_STATUS_UNCONFIRMED",
                            "RUNNER_CONFIGURATION_UNAVAILABLE",
                            "PREPARATION_LEASE_EXPIRED",
                        )
                    ),
                ),
            )
            .values(
                state="RECONCILIATION_REQUIRED",
                error_code="BUILD_STATUS_UNCONFIRMED",
                error_summary=summary,
                updated_at=datetime.now(UTC),
            )
            .execution_options(synchronize_session=False)
        )
        if status_uncertain.rowcount != 1:
            self.db.rollback()
            return True
        self.db.commit()
        self.db.expire(run)
        return True

    def persist_generated_plan_artifact(
        self,
        principal: Principal,
        revision_id: str,
        run_id: str,
        proposal: GeneratedDeploymentProposal,
        generated_plan: GeneratedTerraformPlan,
    ) -> GeneratedPlanArtifact:
        """Persist trusted runner output; this method is deliberately not an HTTP endpoint.

        The current customer-facing revision must be submitted or explicitly
        approved. Only the trusted server runner can call this boundary with a
        typed proposal and its real saved plan. Regional pricing is recorded as
        unavailable until a trusted evaluator is integrated.
        """
        revision = self._infrastructure_revision(principal, revision_id)
        try:
            run_id = str(uuid.UUID(run_id))
        except (AttributeError, ValueError) as error:
            raise ValueError("generated-plan run identifier is invalid") from error
        customer_plan = self._infrastructure_plan(principal, revision.infrastructure_plan_id)
        self._project(principal, customer_plan.project_id)
        if revision.state not in {
            InfrastructurePlanState.SUBMITTED,
            InfrastructurePlanState.APPROVED,
        }:
            raise ValueError("generated Terraform plans require a submitted customer revision")
        latest = self.db.scalar(
            select(InfrastructurePlanRevision)
            .where(
                InfrastructurePlanRevision.infrastructure_plan_id == customer_plan.id,
                InfrastructurePlanRevision.organization_id == principal.organization_id,
            )
            .order_by(InfrastructurePlanRevision.revision_number.desc())
            .limit(1)
        )
        if not latest or latest.id != revision.id:
            raise ValueError("generated Terraform plan is stale because a newer revision exists")
        if revision.content_digest != plan_hash(revision.content):
            raise ValueError("customer revision failed integrity verification")

        target = (revision.content or {}).get("target") or {}
        ownership_scope = self._generated_plan_ownership_scope(
            principal,
            customer_plan.project_id,
            customer_plan.id,
            revision.id,
            target.get("environment_id"),
        )
        connection_id = target.get("connection_id")
        connection = self.db.get(CloudConnection, connection_id) if connection_id else None
        if (
            not connection
            or connection.organization_id != principal.organization_id
            or connection.provider != "aws"
            or connection.setup_state != "VERIFIED"
            or connection.account_id != generated_plan.target_account_id
            or target.get("account_id") != generated_plan.target_account_id
            or target.get("region") != generated_plan.region
            or proposal.requirements.region != generated_plan.region
        ):
            raise ValueError("generated plan target does not match the verified customer account")

        proposal_bytes = json.dumps(
            proposal.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        proposal_sha256 = hashlib.sha256(proposal_bytes).hexdigest()
        expected_context_sha256 = generation_context_digest(revision.content, revision.id)
        try:
            with open(generated_plan.saved_plan_path, "rb") as saved_plan_file:
                saved_plan_sha256 = hashlib.file_digest(saved_plan_file, "sha256").hexdigest()
        except OSError as error:
            raise ValueError("generated Terraform plan file is unavailable") from error
        if (
            generated_plan.proposal_sha256 != proposal_sha256
            or proposal.source_revision != revision.id
            or proposal.context_digest != expected_context_sha256
            or generated_plan.context_sha256 != expected_context_sha256
            or generated_plan.ownership_scope_sha256 != ownership_scope.scope_sha256()
            or generated_plan.ownership_plan_id_sha256 != ownership_scope.plan_id_sha256()
            or generated_plan.saved_plan_sha256 != saved_plan_sha256
            or not policy_allows_human_review(generated_plan.policy)
        ):
            raise ValueError("generated Terraform plan failed trusted runner evidence checks")

        duplicate = self.db.scalar(
            select(GeneratedPlanArtifact).where(
                GeneratedPlanArtifact.organization_id == principal.organization_id,
                GeneratedPlanArtifact.run_id == run_id,
            )
        )
        if duplicate:
            raise ValueError("generated Terraform plan run identifier has already been recorded")

        artifact_store = (
            self.generated_plan_artifact_store or configured_generated_plan_artifact_store()
        )
        if artifact_store is None:
            raise ValueError("generated Terraform plan review storage is not enabled")
        try:
            stored_object = artifact_store.store_saved_plan(
                generated_plan.saved_plan_path,
                organization_id=principal.organization_id,
                project_id=customer_plan.project_id,
                revision_id=revision.id,
                run_id=run_id,
                expected_sha256=generated_plan.saved_plan_sha256,
            )
        except GeneratedPlanArtifactError as error:
            raise ValueError("generated Terraform plan could not be securely persisted") from error

        now = datetime.now(UTC)
        policy_doc, policy_sha256 = policy_evidence(generated_plan.policy)
        manifest = generated_plan_manifest(
            organization_id=principal.organization_id,
            project_id=customer_plan.project_id,
            revision_id=revision.id,
            revision_sha256=revision.content_digest,
            stored_object=stored_object,
            plan=generated_plan,
            policy_digest=policy_sha256,
            created_at=now.isoformat().replace("+00:00", "Z"),
        )
        artifact = GeneratedPlanArtifact(
            organization_id=principal.organization_id,
            project_id=customer_plan.project_id,
            revision_id=revision.id,
            run_id=run_id,
            target_account_id=generated_plan.target_account_id,
            region=generated_plan.region,
            terraform_version=generated_plan.terraform_version,
            aws_provider_version=generated_plan.aws_provider_version,
            provider_lockfile_sha256=generated_plan.provider_lockfile_sha256,
            proposal_sha256=generated_plan.proposal_sha256,
            context_sha256=generated_plan.context_sha256,
            configuration_sha256=generated_plan.configuration_sha256,
            saved_plan_sha256=stored_object.sha256,
            policy_sha256=policy_sha256,
            manifest_sha256=canonical_json_digest(manifest),
            manifest=manifest,
            policy_version=generated_plan.policy.policy_version,
            policy_verdict=generated_plan.policy.verdict.value,
            policy_human_approval_required=generated_plan.policy.human_approval_required,
            policy_findings=policy_doc["findings"],
            safe_summary={
                "create_count": generated_plan.summary.create_count,
                "update_count": generated_plan.summary.update_count,
                "delete_count": generated_plan.summary.delete_count,
                "replacement_count": generated_plan.summary.replacement_count,
                "drift_count": generated_plan.summary.drift_count,
                "contains_sensitive_changes": generated_plan.summary.contains_sensitive_changes,
            },
            artifact_bucket=stored_object.bucket,
            artifact_key=stored_object.key,
            artifact_version_id=stored_object.version_id,
            artifact_size_bytes=stored_object.size_bytes,
            created_by_subject=principal.subject,
            created_at=now,
            expires_at=now + timedelta(days=30),
        )
        self.db.add(artifact)
        self.db.flush()
        self.audit(
            principal,
            "generated_plan_artifact.persisted",
            "generated_plan_artifact",
            artifact.id,
            {
                "revision_id": revision.id,
                "manifest_sha256": artifact.manifest_sha256,
                "policy_verdict": artifact.policy_verdict,
                "pricing_status": (artifact.manifest.get("pricing") or {}).get("status"),
                "expires_at": artifact.expires_at.isoformat(),
            },
        )
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            # The S3 object is intentionally retained for reconciliation. Never
            # delete an object after an uncertain database commit.
            raise
        return artifact

    def generated_plan_artifact_detail(
        self, principal: Principal, artifact_id: str
    ) -> dict[str, Any]:
        artifact = self.db.scalar(
            select(GeneratedPlanArtifact).where(
                GeneratedPlanArtifact.id == artifact_id,
                GeneratedPlanArtifact.organization_id == principal.organization_id,
            )
        )
        if not artifact:
            raise PermissionError("generated plan artifact not found in this organization")
        approval = self.db.scalar(
            select(GeneratedPlanApproval).where(
                GeneratedPlanApproval.artifact_id == artifact.id,
                GeneratedPlanApproval.organization_id == principal.organization_id,
            )
        )
        expires_at = artifact.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        expired = expires_at <= datetime.now(UTC)
        pricing_complete = has_complete_pricing_evidence(artifact.manifest)
        manifest_pricing = artifact.manifest.get("pricing")
        manifest_pricing = manifest_pricing if isinstance(manifest_pricing, dict) else {}
        pricing = {
            "status": manifest_pricing.get("status", "UNAVAILABLE"),
            "region": manifest_pricing.get("region", artifact.region),
            "currency": manifest_pricing.get("currency"),
            "monthly_cost": manifest_pricing.get("monthly_cost"),
            "reason_code": manifest_pricing.get(
                "reason_code", "regional_pricing_evaluator_not_integrated"
            ),
            "approval_allowed": pricing_complete,
        }
        if not pricing_complete:
            pricing["message"] = "Waiting for complete regional cost evidence."
        state = (
            "APPROVED_EXPIRED"
            if approval and expired
            else "APPROVED"
            if approval and pricing_complete
            else "APPROVED_COST_EVIDENCE_MISSING"
            if approval
            else "EXPIRED"
            if expired
            else "WAITING_FOR_COST_EVIDENCE"
            if not pricing_complete
            else "AWAITING_HUMAN_APPROVAL"
        )
        return {
            "id": artifact.id,
            "revision_id": artifact.revision_id,
            "manifest_sha256": artifact.manifest_sha256,
            "target": {"account_id": artifact.target_account_id, "region": artifact.region},
            "toolchain": {
                "terraform_version": artifact.terraform_version,
                "aws_provider_version": artifact.aws_provider_version,
            },
            "policy": {
                "version": artifact.policy_version,
                "verdict": artifact.policy_verdict,
                "human_approval_required": artifact.policy_human_approval_required,
                "findings": artifact.policy_findings,
            },
            "summary": artifact.safe_summary,
            "pricing": pricing,
            "state": state,
            "approval": None
            if not approval
            else {
                "approved_manifest_sha256": approval.approved_manifest_sha256,
                "approver_subject": approval.approver_subject,
                "is_self_approval": approval.is_self_approval,
                "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
            },
            "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
            "expires_at": expires_at.isoformat(),
            "execution": "NOT_APPLIED_REVIEW_ONLY",
        }

    def approve_generated_plan_artifact(
        self, principal: Principal, artifact_id: str, provided_manifest_sha256: str
    ) -> dict[str, Any]:
        if principal.role != "administrator":
            raise PermissionError(
                "workspace administrator role required for a generated plan approval"
            )
        artifact = self.db.scalar(
            select(GeneratedPlanArtifact)
            .where(
                GeneratedPlanArtifact.id == artifact_id,
                GeneratedPlanArtifact.organization_id == principal.organization_id,
            )
            .with_for_update()
        )
        if not artifact:
            raise PermissionError("generated plan artifact not found in this organization")
        if artifact.manifest_sha256 != provided_manifest_sha256:
            raise ValueError("generated plan approval digest does not match this artifact")
        if canonical_json_digest(artifact.manifest) != artifact.manifest_sha256:
            raise ValueError("generated plan manifest failed integrity verification")
        manifest = artifact.manifest
        if not has_complete_pricing_evidence(manifest):
            raise ValueError(
                "complete regional cost evidence is unavailable; generated plan cannot be approved"
            )
        tenant = manifest.get("tenant") or {}
        target = manifest.get("target") or {}
        digests = manifest.get("digests") or {}
        manifest_artifact = manifest.get("artifact") or {}
        if (
            tenant.get("organization_id") != artifact.organization_id
            or tenant.get("project_id") != artifact.project_id
            or tenant.get("revision_id") != artifact.revision_id
            or target.get("account_id") != artifact.target_account_id
            or target.get("region") != artifact.region
            or digests.get("proposal_sha256") != artifact.proposal_sha256
            or digests.get("trusted_context_sha256") != artifact.context_sha256
            or digests.get("configuration_sha256") != artifact.configuration_sha256
            or digests.get("saved_plan_sha256") != artifact.saved_plan_sha256
            or digests.get("policy_sha256") != artifact.policy_sha256
            or (manifest.get("toolchain") or {}).get("terraform_version")
            != artifact.terraform_version
            or (manifest.get("toolchain") or {}).get("aws_provider_version")
            != artifact.aws_provider_version
            or (manifest.get("toolchain") or {}).get("provider_lockfile_sha256")
            != artifact.provider_lockfile_sha256
            or (manifest.get("policy") or {}).get("version") != artifact.policy_version
            or (manifest.get("policy") or {}).get("verdict") != artifact.policy_verdict
            or (manifest.get("policy") or {}).get("human_approval_required")
            != artifact.policy_human_approval_required
            or manifest.get("summary") != artifact.safe_summary
            or manifest_artifact.get("bucket") != artifact.artifact_bucket
            or manifest_artifact.get("key") != artifact.artifact_key
            or manifest_artifact.get("version_id") != artifact.artifact_version_id
            or manifest_artifact.get("size_bytes") != artifact.artifact_size_bytes
        ):
            raise ValueError("generated plan manifest fields do not match their immutable record")
        policy_doc = {
            "version": artifact.policy_version,
            "verdict": artifact.policy_verdict,
            "human_approval_required": artifact.policy_human_approval_required,
            "findings": artifact.policy_findings,
        }
        if (
            canonical_json_digest(policy_doc) != artifact.policy_sha256
            or not artifact.policy_human_approval_required
            or artifact.policy_verdict not in {"REVIEW_REQUIRED", "ELIGIBLE_FOR_HUMAN_REVIEW"}
        ):
            raise ValueError("generated plan policy does not allow human approval")

        revision = self._locked_infrastructure_revision(principal, artifact.revision_id)
        customer_plan = self._infrastructure_plan(principal, revision.infrastructure_plan_id)
        if (
            customer_plan.project_id != artifact.project_id
            or revision.state != InfrastructurePlanState.APPROVED
            or revision.content_digest
            != manifest.get("digests", {}).get("customer_revision_sha256")
            or revision.content_digest != plan_hash(revision.content)
        ):
            raise ValueError("generated plan is no longer bound to the current approved revision")
        latest = self.db.scalar(
            select(InfrastructurePlanRevision)
            .where(
                InfrastructurePlanRevision.infrastructure_plan_id == customer_plan.id,
                InfrastructurePlanRevision.organization_id == principal.organization_id,
            )
            .order_by(InfrastructurePlanRevision.revision_number.desc())
            .limit(1)
        )
        if not latest or latest.id != revision.id:
            raise ValueError("generated plan is stale because a newer revision exists")
        cloud_target = (revision.content or {}).get("target") or {}
        connection = self.db.get(CloudConnection, cloud_target.get("connection_id"))
        if (
            not connection
            or connection.organization_id != principal.organization_id
            or connection.provider != "aws"
            or connection.setup_state != "VERIFIED"
            or connection.account_id != artifact.target_account_id
            or cloud_target.get("region") != artifact.region
        ):
            raise ValueError("generated plan target no longer matches a verified customer account")
        ownership_scope = self._generated_plan_ownership_scope(
            principal,
            customer_plan.project_id,
            customer_plan.id,
            revision.id,
            cloud_target.get("environment_id"),
        )
        if (
            digests.get("ownership_scope_sha256") != ownership_scope.scope_sha256()
            or digests.get("ownership_plan_id_sha256") != ownership_scope.plan_id_sha256()
        ):
            raise ValueError("generated plan ownership scope no longer matches this workspace")

        expiry = artifact.expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        if expiry <= datetime.now(UTC):
            raise ValueError("generated plan artifact has expired")
        if self.db.scalar(
            select(GeneratedPlanApproval.id).where(GeneratedPlanApproval.artifact_id == artifact.id)
        ):
            raise ValueError("generated plan artifact has already been approved")

        artifact_store = (
            self.generated_plan_artifact_store or configured_generated_plan_artifact_store()
        )
        if artifact_store is None:
            raise ValueError("generated Terraform plan review storage is not enabled")
        try:
            artifact_store.verify_stored_plan(
                StoredPlanObject(
                    artifact.artifact_bucket,
                    artifact.artifact_key,
                    artifact.artifact_version_id,
                    artifact.artifact_size_bytes,
                    artifact.saved_plan_sha256,
                ),
                run_id=artifact.run_id,
                organization_id=artifact.organization_id,
                project_id=artifact.project_id,
                revision_id=artifact.revision_id,
            )
        except GeneratedPlanArtifactError as error:
            raise ValueError(
                "stored generated plan is missing or failed integrity verification"
            ) from error

        approval = GeneratedPlanApproval(
            artifact_id=artifact.id,
            organization_id=artifact.organization_id,
            project_id=artifact.project_id,
            revision_id=artifact.revision_id,
            approved_manifest_sha256=provided_manifest_sha256,
            approver_subject=principal.subject,
            creator_subject=artifact.created_by_subject,
            is_self_approval=principal.subject == artifact.created_by_subject,
            authorization_policy="workspace-administrator-self-approval-allowed"
            if principal.subject == artifact.created_by_subject
            else "workspace-administrator",
        )
        self.db.add(approval)
        self.audit(
            principal,
            "generated_plan_artifact.approved",
            "generated_plan_artifact",
            artifact.id,
            {
                "revision_id": artifact.revision_id,
                "manifest_sha256": provided_manifest_sha256,
                "is_self_approval": approval.is_self_approval,
                "authorization_policy": approval.authorization_policy,
            },
        )
        try:
            self.db.commit()
        except Exception as error:
            self.db.rollback()
            raise ValueError("generated plan artifact could not be approved once") from error
        return self.generated_plan_artifact_detail(principal, artifact.id)

    def _infrastructure_plan(self, principal: Principal, plan_id: str) -> InfrastructurePlan:
        plan = self.db.get(InfrastructurePlan, plan_id)
        if not plan or plan.organization_id != principal.organization_id:
            raise PermissionError("infrastructure plan not found in this organization")
        return plan

    def _infrastructure_revision(
        self, principal: Principal, revision_id: str
    ) -> InfrastructurePlanRevision:
        revision = self.db.get(InfrastructurePlanRevision, revision_id)
        if not revision or revision.organization_id != principal.organization_id:
            raise PermissionError("infrastructure plan revision not found in this organization")
        return revision

    def _locked_infrastructure_revision(
        self, principal: Principal, revision_id: str
    ) -> InfrastructurePlanRevision:
        """Use a row lock where supported so concurrent decisions cannot both win."""
        revision = self.db.scalar(
            select(InfrastructurePlanRevision)
            .where(
                InfrastructurePlanRevision.id == revision_id,
                InfrastructurePlanRevision.organization_id == principal.organization_id,
            )
            .with_for_update()
        )
        if not revision:
            raise PermissionError("infrastructure plan revision not found in this organization")
        return revision

    def create_cloud_connection(
        self, principal: Principal, display_name: str, provider: str, connection_mode: str
    ) -> CloudConnection:
        connection = CloudConnection(
            organization_id=principal.organization_id,
            display_name=display_name,
            provider=provider,
            connection_mode=connection_mode,
        )
        self.db.add(connection)
        self.db.flush()
        self.audit(
            principal,
            "cloud_connection.created",
            "cloud_connection",
            connection.id,
            {"provider": provider, "mode": connection_mode},
        )
        self.db.commit()
        return connection

    def cloud_connections(self, principal: Principal) -> list[CloudConnection]:
        return list(
            self.db.scalars(
                select(CloudConnection)
                .where(CloudConnection.organization_id == principal.organization_id)
                .order_by(CloudConnection.created_at)
            )
        )

    def cloud_connection_detail(self, principal: Principal, connection_id: str) -> dict[str, Any]:
        connection = self._cloud_connection(principal, connection_id)
        latest = self.db.scalar(
            select(StoredCloudInventorySnapshot)
            .where(
                StoredCloudInventorySnapshot.organization_id == principal.organization_id,
                StoredCloudInventorySnapshot.cloud_connection_id == connection.id,
            )
            .order_by(StoredCloudInventorySnapshot.captured_at.desc())
            .limit(1)
        )
        snapshot = latest.snapshot if latest else {}
        return {
            "id": connection.id,
            "display_name": connection.display_name,
            "provider": connection.provider,
            "account_id": connection.account_id,
            "role_arn": connection.discovery_role_arn,
            "execution_role_arn": connection.execution_role_arn,
            "setup_state": connection.setup_state,
            "authorized_regions": snapshot.get("approved_regions", []),
            "capabilities": [
                "read-only inventory discovery",
                "read-only Cost Explorer query when customer policy permits",
            ],
            "verified_at": latest.captured_at.isoformat() if latest else None,
            "verification_provenance": latest.provenance if latest else None,
            "credentials_stored": False,
            "deployment_permission": (
                "customer-approved execution role pending verification"
                if connection.execution_role_arn
                else "not granted"
            ),
        }

    def disconnect_cloud_connection(self, principal: Principal, connection_id: str) -> None:
        connection = self._cloud_connection(principal, connection_id)
        self.db.query(CloudDiscoveryJob).filter(
            CloudDiscoveryJob.cloud_connection_id == connection.id
        ).delete(synchronize_session=False)
        self.db.query(StoredCloudInventorySnapshot).filter(
            StoredCloudInventorySnapshot.cloud_connection_id == connection.id
        ).delete(synchronize_session=False)
        self.db.delete(connection)
        self.audit(
            principal,
            "cloud_connection.disconnected",
            "cloud_connection",
            connection_id,
            {"credentials_stored": False},
        )
        self.db.commit()

    def _cloud_connection(self, principal: Principal, connection_id: str) -> CloudConnection:
        connection = self.db.get(CloudConnection, connection_id)
        if not connection or connection.organization_id != principal.organization_id:
            raise PermissionError("cloud connection not found in this organization")
        return connection

    def aws_quick_create_setup(
        self,
        principal: Principal,
        connection_id: str,
        account_id: str,
        access_mode: str = "discovery",
    ) -> dict[str, object]:
        """Generate a one-click AWS Console setup; it does not create AWS resources itself."""
        connection = self._cloud_connection(principal, connection_id)
        discovery_broker_role_arn = os.getenv("DAVDEPLOY_DISCOVERY_BROKER_ROLE_ARN")
        execution_broker_role_arn = os.getenv("DAVDEPLOY_EXECUTION_BROKER_ROLE_ARN")
        # Compatibility is intentionally temporary for pre-split hosted configurations.
        legacy_broker_role_arn = os.getenv("DAVDEPLOY_CONTROL_PLANE_ROLE_ARN")
        discovery_broker_role_arn = discovery_broker_role_arn or legacy_broker_role_arn
        execution_broker_role_arn = execution_broker_role_arn or legacy_broker_role_arn
        template_url = os.getenv("DAVDEPLOY_AWS_CONNECTION_TEMPLATE_URL")
        if (
            not discovery_broker_role_arn
            or not template_url
            or (access_mode == "administrator-pilot" and not execution_broker_role_arn)
        ):
            raise RuntimeError(
                "AWS customer connection setup is not configured with a discovery broker role and hosted template"
            )
        external_id = secrets.token_urlsafe(32)
        stack_name = f"davdeploy-Discovery-{connection.id[:8]}"
        discovery_role_arn = f"arn:aws:iam::{account_id}:role/davdeployDiscovery-{connection.id}"
        parameters = {
            "davdeployDiscoveryBrokerRoleArn": discovery_broker_role_arn,
            "davdeployExecutionBrokerRoleArn": execution_broker_role_arn or "unused",
            "AccessMode": access_mode,
            "ExternalId": external_id,
            "ConnectionId": connection.id,
        }
        quick_create_url = (
            "https://console.aws.amazon.com/cloudformation/home#/stacks/create/review?"
            + urlencode({"templateURL": template_url, "stackName": stack_name})
            + "&"
            + urlencode({f"param_{key}": value for key, value in parameters.items()})
        )
        connection.account_id = account_id
        connection.discovery_role_arn = discovery_role_arn
        connection.execution_role_arn = (
            f"arn:aws:iam::{account_id}:role/davdeployExecution-{connection.id}"
            if access_mode == "administrator-pilot"
            else None
        )
        connection.external_id_secret_ref = self.connection_secrets.put_external_id(
            principal.organization_id, connection.id, external_id
        )
        # Do not retain a plaintext legacy value. Existing values require a new setup link.
        connection.external_id = None
        connection.setup_state = "SETUP_LINK_GENERATED"
        self.audit(
            principal,
            "cloud_connection.aws_quick_create_generated",
            "cloud_connection",
            connection.id,
            {
                "account_id": account_id,
                "stack_name": stack_name,
                "template_published": bool(template_url),
            },
        )
        self.db.commit()
        return {
            "connection_id": connection.id,
            "account_id": account_id,
            "stack_name": stack_name,
            "template_path": "infrastructure/cloudformation/customer-discovery-role.yaml",
            "quick_create_url": quick_create_url,
            "customer_steps": [
                "Open the AWS Quick Create link.",
                "Review the IAM roles and their permissions, then acknowledge IAM resource creation.",
                "Create the stack, then return to davdeploy to verify the connection.",
            ],
            "boundary": "This action only creates a setup link. Discovery is read-only; administrator-pilot creates a separate execution role that can modify customer AWS resources after product approval.",
        }

    def aws_existing_role_setup(
        self,
        principal: Principal,
        connection_id: str,
        account_id: str,
        discovery_role_arn: str,
        execution_role_arn: str | None = None,
    ) -> dict[str, object]:
        """Attach customer-managed roles; verification later proves the trust and permissions."""
        connection = self._cloud_connection(principal, connection_id)
        prefix = f"arn:aws:iam::{account_id}:role/"
        if not discovery_role_arn.startswith(prefix) or (
            execution_role_arn and not execution_role_arn.startswith(prefix)
        ):
            raise ValueError("role ARN must belong to the selected AWS account")
        external_id = secrets.token_urlsafe(32)
        connection.account_id = account_id
        connection.discovery_role_arn = discovery_role_arn
        connection.execution_role_arn = execution_role_arn
        connection.external_id_secret_ref = self.connection_secrets.put_external_id(
            principal.organization_id, connection.id, external_id
        )
        connection.external_id = None
        connection.setup_state = "EXISTING_ROLE_CONFIGURED"
        self.audit(
            principal,
            "cloud_connection.aws_existing_role_attached",
            "cloud_connection",
            connection.id,
            {"account_id": account_id, "execution_role_configured": bool(execution_role_arn)},
        )
        self.db.commit()
        return {
            "connection_id": connection.id,
            "external_id": external_id,
            "verification_required": True,
            "deployment_permission": "pending verification"
            if execution_role_arn
            else "not granted",
        }

    def queue_aws_connection_verification(
        self, principal: Principal, connection_id: str, region: str
    ) -> CloudDiscoveryJob:
        connection = self._cloud_connection(principal, connection_id)
        if not all(
            [
                connection.account_id,
                connection.discovery_role_arn,
                connection.external_id_secret_ref,
            ]
        ):
            raise ValueError("generate a new AWS setup link before verifying this connection")
        if os.getenv("DAVDEPLOY_AWS_LIVE_DISCOVERY_ENABLED", "false").lower() != "true":
            raise RuntimeError("live AWS discovery is not enabled for this control-plane process")
        job = CloudDiscoveryJob(
            organization_id=principal.organization_id,
            cloud_connection_id=connection.id,
            requester_subject=principal.subject,
            region=region,
            state="QUEUED",
            result={"operation": "READ_ONLY_AWS_DISCOVERY"},
        )
        self.db.add(job)
        self.db.flush()
        self.audit(
            principal,
            "cloud_connection.aws_verification_queued",
            "cloud_discovery_job",
            job.id,
            {"connection_id": connection.id, "region": region},
        )
        self.db.commit()
        self._wake_worker("aws_connection_verification", job.id)
        return job

    def cloud_discovery_job(
        self, principal: Principal, connection_id: str, job_id: str
    ) -> CloudDiscoveryJob:
        job = self.db.get(CloudDiscoveryJob, job_id)
        if (
            not job
            or job.organization_id != principal.organization_id
            or job.cloud_connection_id != connection_id
        ):
            raise PermissionError("cloud discovery job not found in this organization")
        return job

    def verify_aws_connection(
        self,
        principal: Principal,
        connection_id: str,
        region: str,
        discovery: StsAwsDiscovery | None = None,
    ) -> StoredCloudInventorySnapshot:
        """Assume only the per-customer read-only role and store no credentials."""
        connection = self._cloud_connection(principal, connection_id)
        if not all(
            [
                connection.account_id,
                connection.discovery_role_arn,
                connection.external_id_secret_ref,
            ]
        ):
            raise ValueError("generate a new AWS setup link before verifying this connection")
        if os.getenv("DAVDEPLOY_AWS_LIVE_DISCOVERY_ENABLED", "false").lower() != "true":
            raise RuntimeError("live AWS discovery is not enabled for this control-plane process")
        external_id = self.connection_secrets.get_external_id(connection.external_id_secret_ref)
        discovery = discovery or StsAwsDiscovery()
        snapshot = discovery.verify(
            connection.id, connection.discovery_role_arn, external_id, region
        )
        discovered_account = next(
            (
                item.removeprefix("aws-account:")
                for item in snapshot.approved_resources
                if item.startswith("aws-account:")
            ),
            None,
        )
        if discovered_account != connection.account_id:
            raise PermissionError("assumed AWS role belongs to a different account")
        execution_verified = False
        if connection.execution_role_arn:
            execution_account = discovery.verify_execution_role(
                connection.id, connection.execution_role_arn, external_id, region
            )
            if execution_account != connection.account_id:
                raise PermissionError("assumed execution role belongs to a different account")
            execution_verified = True
        connection.setup_state = "VERIFIED"
        self.audit(
            principal,
            "cloud_connection.aws_verified",
            "cloud_connection",
            connection.id,
            {
                "account_id": connection.account_id,
                "region": region,
                "provenance": snapshot.provenance,
                "execution_role_verified": execution_verified,
            },
        )
        self.db.commit()
        return self.record_cloud_inventory_snapshot(
            principal,
            connection.id,
            region,
            snapshot.provenance,
            snapshot.discovered_at,
            snapshot.model_dump(mode="json"),
        )

    def run_next_discovery_job(self) -> bool:
        """Process one durable read-only discovery job; no cloud mutation occurs here."""
        job = self.db.scalar(
            select(CloudDiscoveryJob)
            .where(CloudDiscoveryJob.state == "QUEUED")
            .order_by(CloudDiscoveryJob.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if not job:
            return False
        job.state = "RUNNING"
        job.attempts += 1
        self.db.commit()
        principal = Principal(job.requester_subject, job.organization_id, "developer")
        try:
            snapshot = self.verify_aws_connection(principal, job.cloud_connection_id, job.region)
            job.state = "SUCCEEDED"
            job.result = {"snapshot_id": snapshot.id, "provenance": snapshot.provenance}
            job.error = None
            self.audit(
                principal,
                "cloud_connection.aws_verification_succeeded",
                "cloud_discovery_job",
                job.id,
                {"connection_id": job.cloud_connection_id, "snapshot_id": snapshot.id},
            )
        except Exception as error:  # noqa: BLE001 - worker records bounded provider failures safely.
            job.state = "FAILED"
            job.error = str(error)[:300]
            job.result = {}
            self.audit(
                principal,
                "cloud_connection.aws_verification_failed",
                "cloud_discovery_job",
                job.id,
                {"connection_id": job.cloud_connection_id, "reason": job.error},
            )
        self.db.commit()
        return True

    def record_cloud_inventory_snapshot(
        self,
        principal: Principal,
        connection_id: str,
        region: str,
        provenance: str,
        captured_at,
        snapshot: dict[str, Any],
    ) -> StoredCloudInventorySnapshot:
        """Persist metadata discovered through STS; credential material is never accepted."""
        connection = self._cloud_connection(principal, connection_id)
        stored = StoredCloudInventorySnapshot(
            organization_id=principal.organization_id,
            cloud_connection_id=connection.id,
            region=region,
            provenance=provenance,
            captured_at=captured_at,
            snapshot=snapshot,
        )
        self.db.add(stored)
        self.db.flush()
        self.audit(
            principal,
            "cloud_inventory.snapshot_recorded",
            "cloud_inventory_snapshot",
            stored.id,
            {"connection_id": connection.id, "region": region, "provenance": provenance},
        )
        self.db.commit()
        return stored

    def cloud_inventory_snapshots(
        self, principal: Principal, connection_id: str
    ) -> list[StoredCloudInventorySnapshot]:
        connection = self.db.get(CloudConnection, connection_id)
        if not connection or connection.organization_id != principal.organization_id:
            raise PermissionError("cloud connection not found in this organization")
        return list(
            self.db.scalars(
                select(StoredCloudInventorySnapshot)
                .where(
                    StoredCloudInventorySnapshot.organization_id == principal.organization_id,
                    StoredCloudInventorySnapshot.cloud_connection_id == connection_id,
                )
                .order_by(StoredCloudInventorySnapshot.captured_at.desc())
            )
        )

    def github_connection_status(self, principal: Principal) -> dict[str, Any]:
        states = list(
            self.db.scalars(
                select(GitHubAppInstallationState)
                .where(GitHubAppInstallationState.organization_id == principal.organization_id)
                .order_by(GitHubAppInstallationState.updated_at.desc())
            )
        )
        recent_deliveries = list(
            self.db.scalars(
                select(GitHubWebhookDelivery)
                .where(GitHubWebhookDelivery.organization_id == principal.organization_id)
                .order_by(GitHubWebhookDelivery.received_at.desc())
                .limit(5)
            )
        )
        execution = getattr(self.github, "execution", "SIMULATED")
        try:
            installations = [item.__dict__ for item in self.github.installations()]
        except HTTPError as error:
            raise ValueError(
                "GitHub App connection is unavailable, expired, or missing permissions"
            ) from error
        return {
            "mode": "read-only",
            "execution": execution,
            "installations": installations,
            "install_url": os.getenv("DAVDEPLOY_GITHUB_APP_INSTALL_URL"),
            "writes_enabled": False,
            "credentials_stored": False,
            "webhooks_enabled": bool(os.getenv("DAVDEPLOY_GITHUB_WEBHOOK_SECRET"))
            or execution == "SIMULATED",
            "installation_states": [
                {
                    "installation_id": item.installation_id,
                    "account_login": item.account_login,
                    "account_type": item.account_type,
                    "state": item.state,
                    "repository_selection": item.repository_selection,
                    "permissions": item.permissions,
                    "last_event": item.last_event,
                    "updated_at": item.updated_at,
                }
                for item in states
            ],
            "recent_webhook_deliveries": [
                {
                    "delivery_id": item.delivery_id,
                    "event": item.event,
                    "action": item.action,
                    "installation_id": item.installation_id,
                    "repository": item.repository,
                    "status": item.status,
                    "received_at": item.received_at,
                }
                for item in recent_deliveries
            ],
        }

    def receive_github_webhook(
        self,
        *,
        event: str,
        delivery_id: str,
        signature: str,
        body: bytes,
    ) -> dict[str, Any]:
        """Process a signed GitHub App webhook without exposing repository credentials.

        In local fixture mode, ``fixture-sha256=valid`` is accepted so tests can
        exercise product state transitions without a public callback URL.
        In configured mode, the standard GitHub HMAC signature is required.
        """
        if not event or not delivery_id:
            raise ValueError("GitHub event and delivery ID are required")
        execution = getattr(self.github, "execution", "SIMULATED")
        secret = os.getenv("DAVDEPLOY_GITHUB_WEBHOOK_SECRET", "")
        fixture_signature = execution == "SIMULATED" and signature == "fixture-sha256=valid"
        if not fixture_signature and not verify_github_webhook_signature(secret, body, signature):
            raise PermissionError("GitHub webhook signature is invalid")
        duplicate = self.db.scalar(
            select(GitHubWebhookDelivery).where(GitHubWebhookDelivery.delivery_id == delivery_id)
        )
        if duplicate:
            return {
                "status": "DUPLICATE",
                "delivery_id": duplicate.delivery_id,
                "event": duplicate.event,
                "installation_id": duplicate.installation_id,
                "state": "UNCHANGED",
            }
        try:
            payload = json.loads(body.decode() or "{}")
        except json.JSONDecodeError as error:
            raise ValueError("GitHub webhook payload must be valid JSON") from error
        organization_id = self._github_webhook_organization_id(payload)
        installation = payload.get("installation") or {}
        account = installation.get("account") or payload.get("sender") or {}
        repository = payload.get("repository") or {}
        installation_id = str(installation.get("id") or "fixture-installation")
        account_login = str(account.get("login") or "unknown-github-account")
        account_type = str(account.get("type") or "Organization")
        action = payload.get("action")
        repository_name = repository.get("full_name")
        state = self._github_installation_state(event, action, payload)
        permissions = installation.get("permissions") or payload.get("permissions") or {}
        repository_selection = str(installation.get("repository_selection") or "selected")
        install_state = self.db.scalar(
            select(GitHubAppInstallationState).where(
                GitHubAppInstallationState.organization_id == organization_id,
                GitHubAppInstallationState.installation_id == installation_id,
            )
        )
        last_event = {
            "event": event,
            "action": action,
            "repository": repository_name,
            "delivery_id": delivery_id,
            "execution": execution,
        }
        if install_state:
            install_state.account_login = account_login
            install_state.account_type = account_type
            install_state.state = state
            install_state.repository_selection = repository_selection
            install_state.permissions = permissions
            install_state.last_event = last_event
        else:
            install_state = GitHubAppInstallationState(
                organization_id=organization_id,
                installation_id=installation_id,
                account_login=account_login,
                account_type=account_type,
                state=state,
                repository_selection=repository_selection,
                permissions=permissions,
                last_event=last_event,
            )
            self.db.add(install_state)
        delivery = GitHubWebhookDelivery(
            organization_id=organization_id,
            delivery_id=delivery_id,
            event=event,
            action=action,
            installation_id=installation_id,
            repository=repository_name,
            status="PROCESSED",
            detail=last_event,
        )
        self.db.add(delivery)
        self.db.flush()
        self.db.add(
            AuditEvent(
                organization_id=organization_id,
                actor_subject="github-app",
                action=f"github.webhook.{event}",
                entity_type="github_app_installation",
                entity_id=install_state.id,
                detail=last_event | {"state": state},
            )
        )
        self.db.commit()
        return {
            "status": "PROCESSED",
            "delivery_id": delivery_id,
            "event": event,
            "action": action,
            "installation_id": installation_id,
            "repository": repository_name,
            "state": state,
            "execution": execution,
        }

    def _github_webhook_organization_id(self, payload: dict[str, Any]) -> str:
        requested = (payload.get("davdeploy") or {}).get("organization_id")
        organization_id = str(requested or os.getenv("DAVDEPLOY_DEFAULT_WEBHOOK_ORG", "org-demo"))
        if not self.db.get(Organization, organization_id):
            raise PermissionError("GitHub webhook installation is not mapped to a workspace")
        return organization_id

    @staticmethod
    def _github_installation_state(event: str, action: str | None, payload: dict[str, Any]) -> str:
        permissions = (
            (payload.get("installation") or {}).get("permissions")
            or payload.get("permissions")
            or {}
        )
        if permissions and permissions.get("metadata") not in {None, "read"}:
            return "MISSING_PERMISSION"
        if event == "installation" and action == "deleted":
            return "REVOKED"
        if event == "installation" and action == "suspend":
            return "SUSPENDED"
        if event == "repository" and action in {"deleted", "transferred"}:
            return "REPOSITORY_INACCESSIBLE"
        if event == "installation_repositories":
            return "REPOSITORY_ACCESS_CHANGED"
        if event == "push":
            return "BRANCH_UPDATED"
        return "CONNECTED"

    def github_repositories(
        self, principal: Principal, installation_id: str
    ) -> list[dict[str, str]]:
        del (
            principal
        )  # The configured adapter independently scopes access to installation repositories.
        try:
            return [item.__dict__ for item in self.github.repositories(installation_id)]
        except HTTPError as error:
            raise ValueError(
                "GitHub repository list is unavailable, expired, or missing permissions"
            ) from error

    def github_branches(
        self, principal: Principal, installation_id: str, repository: str
    ) -> list[str]:
        del principal
        try:
            return self.github.branches(installation_id, repository)
        except HTTPError as error:
            raise ValueError(
                "GitHub branch list is unavailable, expired, or missing permissions"
            ) from error

    def public_github_repository(self, principal: Principal, repository_url: str) -> dict[str, Any]:
        self.workspace_profile(principal)
        try:
            metadata = self.public_github.inspect_repository(repository_url)
            branches = self.public_github.branches(repository_url)
        except HTTPError as error:
            raise ValueError("public GitHub repository is unavailable") from error
        return {
            "full_name": metadata.repository,
            "html_url": f"https://github.com/{metadata.repository}",
            "default_branch": metadata.default_branch,
            "branches": branches,
            "execution": self.public_github.execution,
        }

    def disconnect_project_repository(self, principal: Principal, project_id: str) -> None:
        project = self._project(principal, project_id)
        self.db.query(RepositoryConnection).filter(
            RepositoryConnection.project_id == project.id,
            RepositoryConnection.organization_id == principal.organization_id,
        ).delete(synchronize_session=False)
        project.repository_url = None
        self.audit(principal, "repository.disconnected", "project", project.id, {})
        self.db.commit()

    def repository_discovery(self, principal: Principal, project_id: str) -> dict[str, Any]:
        project = self._project(principal, project_id)
        if not project.repository_url:
            raise ValueError("project has no repository connection")
        installation_id = getattr(self.github, "installation_id", "fixture-installation")
        connection = self.db.scalar(
            select(RepositoryConnection).where(RepositoryConnection.project_id == project.id)
        )
        selected_branch = connection.selected_branch if connection else None
        authorized_names = {
            item.full_name.lower() for item in self.github.repositories(installation_id)
        }
        repository_name = PublicGitHubRepositoryReader.repository_name(project.repository_url)
        configured_fixture_repository = getattr(
            self.github, "execution", None
        ) == "SIMULATED" and repository_name.lower().startswith("example/")
        if repository_name.lower() in authorized_names or configured_fixture_repository:
            analysis = self.github.analyze_repository(
                installation_id, project.repository_url, selected_branch
            )
            metadata = self.github.inspect_repository(
                installation_id, project.repository_url, selected_branch
            )
            execution = getattr(self.github, "execution", "SIMULATED")
        else:
            try:
                analysis = self.public_github.analyze_repository(
                    project.repository_url, selected_branch
                )
                metadata = self.public_github.inspect_repository(project.repository_url)
            except HTTPError as error:
                raise ValueError("public GitHub repository is unavailable") from error
            execution = self.public_github.execution
        stored = StoredRepositoryAnalysis(
            organization_id=principal.organization_id,
            project_id=project.id,
            repository_url=project.repository_url,
            selected_branch=analysis.selected_branch,
            execution=execution,
            analysis=self._repository_analysis_payload(analysis),
        )
        self.db.add(stored)
        self.audit(
            principal,
            "repository.analyzed",
            "project",
            project.id,
            {
                "provider": metadata.provider,
                "repository": metadata.repository,
                "branch": analysis.selected_branch,
                "execution": execution,
                "manifests": list(analysis.manifests),
            },
        )
        self.db.commit()
        return metadata.__dict__ | {
            "execution": execution,
            "selected_branch": analysis.selected_branch,
            "analysis": stored.analysis,
        }

    @staticmethod
    def _repository_analysis_payload(analysis: object) -> dict[str, Any]:
        payload = analysis.__dict__.copy()
        for key, value in payload.items():
            if isinstance(value, tuple):
                payload[key] = list(value)
        return payload

    def latest_repository_analysis(
        self, principal: Principal, project_id: str
    ) -> StoredRepositoryAnalysis | None:
        project = self._project(principal, project_id)
        return self.db.scalar(
            select(StoredRepositoryAnalysis)
            .where(
                StoredRepositoryAnalysis.organization_id == principal.organization_id,
                StoredRepositoryAnalysis.project_id == project.id,
            )
            .order_by(StoredRepositoryAnalysis.created_at.desc())
            .limit(1)
        )

    def desired_state_publication(
        self, principal: Principal, project_id: str, plan_id: str
    ) -> dict[str, object]:
        """Shape a reviewed desired-state PR without contacting GitHub."""
        project = self._project(principal, project_id)
        plan = self._plan(principal, plan_id)
        if plan.action != PlanAction.DEPLOY or plan.state != LifecycleState.APPROVED:
            raise ValueError("only an approved deployment plan can publish desired state")
        intent = self._intent(principal, plan.intent_id)
        if intent.project_id != project.id or not project.repository_url:
            raise PermissionError("plan does not belong to a repository-connected project")
        publication = self.github.publish_reviewed_desired_state(
            "fixture-installation",
            project.repository_url,
            f"davdeploy/{plan.id}.json",
            json.dumps(plan.payload, sort_keys=True),
        )
        self.audit(
            principal,
            "gitops.desired_state_contract_created",
            "deployment_plan",
            plan.id,
            {"profile": plan.payload["architecture"]["profile"]},
        )
        self.db.commit()
        return publication.__dict__ | {
            "execution": "SIMULATED",
            "profile": plan.payload["architecture"]["profile"],
        }

    def create_desired_state_publication_for_revision(
        self, principal: Principal, revision_id: str, provided_digest: str
    ) -> dict[str, Any]:
        """Create a fixture reviewed-PR publication for an approved customer plan.

        This is the product contract for later GitHub writes. It persists the
        package and PR state locally, but the current adapter still returns a
        fixture URL and never contacts GitHub.
        """
        revision, infrastructure_plan, source_deployment = self._approved_customer_revision(
            principal, revision_id
        )
        if (
            revision.content_digest != provided_digest
            or plan_hash(revision.content) != provided_digest
        ):
            raise ValueError("stale desired-state publication: approved digest changed")
        project = self._project(principal, infrastructure_plan.project_id)
        content = revision.content
        application = content.get("application_analysis") or {}
        repository_url = application.get("repository")
        branch = application.get("branch")
        if not repository_url or not branch:
            raise ValueError("approved plan has no selected repository and branch")
        repository_connection = self.db.scalar(
            select(RepositoryConnection).where(
                RepositoryConnection.organization_id == principal.organization_id,
                RepositoryConnection.project_id == project.id,
                RepositoryConnection.repository_url == repository_url,
            )
        )
        if repository_connection is None:
            raise ValueError("selected repository is no longer connected to this project")
        if (
            repository_connection.selected_branch
            and repository_connection.selected_branch != branch
        ):
            raise ValueError("selected repository branch changed after approval")
        self._assert_github_installation_publishable(principal)
        existing = self.db.scalar(
            select(DesiredStatePublication).where(
                DesiredStatePublication.organization_id == principal.organization_id,
                DesiredStatePublication.revision_id == revision.id,
                DesiredStatePublication.content_digest == revision.content_digest,
            )
        )
        if existing:
            return self._desired_state_publication_payload(existing)
        package = self._desired_state_package(
            revision=revision,
            infrastructure_plan=infrastructure_plan,
            source_deployment=source_deployment,
            repository_url=str(repository_url),
            branch=str(branch),
        )
        installation = self.github.installations()[0]
        publication = self.github.publish_reviewed_desired_state(
            installation.id,
            str(repository_url),
            f"davdeploy/{revision.id}/desired-state-package.json",
            json.dumps(package, sort_keys=True),
        )
        stored = DesiredStatePublication(
            organization_id=principal.organization_id,
            revision_id=revision.id,
            project_id=project.id,
            repository_url=str(repository_url),
            branch=str(branch),
            state="PUBLISHED",
            publication_url=publication.pull_request_url,
            required_checks={"checks": list(publication.required_checks)},
            package=package,
            content_digest=revision.content_digest,
            created_by_subject=principal.subject,
        )
        self.db.add(stored)
        self.db.flush()
        self.audit(
            principal,
            "desired_state.fixture_pr_published",
            "desired_state_publication",
            stored.id,
            {
                "revision_id": revision.id,
                "digest": revision.content_digest,
                "profile": package["profile"],
                "state": stored.state,
                "boundary": (
                    "reviewed desired-state PR only; davdeploy cannot merge or deploy "
                    "from this publication"
                ),
            },
        )
        self.db.commit()
        return self._desired_state_publication_payload(stored)

    def _assert_github_installation_publishable(self, principal: Principal) -> None:
        blocked_states = {"REVOKED", "SUSPENDED", "MISSING_PERMISSION", "REPOSITORY_INACCESSIBLE"}
        state = self.db.scalar(
            select(GitHubAppInstallationState)
            .where(GitHubAppInstallationState.organization_id == principal.organization_id)
            .order_by(GitHubAppInstallationState.updated_at.desc())
            .limit(1)
        )
        if state and state.state in blocked_states:
            raise PermissionError(f"GitHub App installation is not publishable: {state.state}")

    def update_desired_state_publication_state(
        self,
        principal: Principal,
        revision_id: str,
        publication_id: str,
        *,
        content_digest: str,
        state: str,
    ) -> dict[str, Any]:
        """Record local fixture PR/check state for the approved desired-state package.

        This models a human-reviewed PR/check result in local mode. It never
        writes GitHub, never merges, and never deploys.
        """
        if not self._is_workspace_administrator(principal):
            raise PermissionError(
                "only a workspace administrator can update fixture PR review state"
            )
        revision, _, _ = self._approved_customer_revision(principal, revision_id)
        if (
            revision.content_digest != content_digest
            or plan_hash(revision.content) != content_digest
        ):
            raise ValueError("stale desired-state state update: approved digest changed")
        publication = self.db.get(DesiredStatePublication, publication_id)
        if (
            publication is None
            or publication.organization_id != principal.organization_id
            or publication.revision_id != revision.id
            or publication.content_digest != revision.content_digest
        ):
            raise PermissionError("desired-state publication not found for this approved revision")
        allowed = {
            "PUBLISHED": {"CHECKS_PENDING", "CHECKS_PASSED", "CLOSED"},
            "CHECKS_PENDING": {"CHECKS_PASSED", "CLOSED"},
            "CHECKS_PASSED": {"CLOSED"},
            "CLOSED": set(),
            "MERGED": set(),
        }
        if state not in allowed.get(publication.state, set()):
            raise ValueError(f"cannot change fixture PR state from {publication.state} to {state}")
        publication.state = state
        self.audit(
            principal,
            "desired_state.fixture_pr_state_recorded",
            "desired_state_publication",
            publication.id,
            {
                "revision_id": revision.id,
                "digest": revision.content_digest,
                "state": publication.state,
                "boundary": "local fixture PR/check state only; no GitHub write, merge or deployment",
            },
        )
        self.db.commit()
        return self._desired_state_publication_payload(publication)

    def _desired_state_package(
        self,
        *,
        revision: InfrastructurePlanRevision,
        infrastructure_plan: InfrastructurePlan,
        source_deployment: DeploymentPlan,
        repository_url: str,
        branch: str,
    ) -> dict[str, Any]:
        content = revision.content
        profile_name = content["summary"]["selected_profile"]
        profile = execution_profile(profile_name)
        target = content.get("target") or {}
        observability = content.get("observability") or {}
        common = {
            "revision_id": revision.id,
            "plan_id": infrastructure_plan.id,
            "source_deployment_plan_id": source_deployment.id,
            "approved_digest": revision.content_digest,
            "profile": profile_name,
            "repository": repository_url,
            "branch": branch,
            "target": target,
            "required_tags": {
                "ManagedBy": "davdeploy",
                "davdeployPlanDigest": revision.content_digest,
                "davdeployProjectId": infrastructure_plan.project_id,
            },
            "observability": observability,
            "execution_boundary": (
                "Desired-state fixture only. It requires human PR review and does not apply "
                "Terraform, merge GitHub changes or deploy cloud resources."
            ),
        }
        contract = {
            "kind": "davdeploy.desired-state-package.v1",
            **common,
            "delivery": {
                "kind": profile.delivery_kind,
                "terraform_boundary": profile.terraform_boundary,
                "gitops_boundary": profile.gitops_boundary,
                "kubernetes_boundary": profile.kubernetes_boundary,
            },
            "files": [
                {
                    "path": "davdeploy/approved-plan.json",
                    "purpose": "Exact approved customer-plan revision and digest binding.",
                    "content": {
                        "revision_id": revision.id,
                        "digest": revision.content_digest,
                        "content": content,
                    },
                },
                {
                    "path": f"infrastructure/{profile_name}/contract.json",
                    "purpose": f"Profile-specific {profile.delivery_kind} deployment contract.",
                    "content": self._profile_desired_state_contract(profile_name, common),
                },
                {
                    "path": "davdeploy/README.md",
                    "purpose": "Human review note for the fixture PR.",
                    "content": (
                        "# davdeploy desired state\n\n"
                        "This fixture package is generated from an approved plan. "
                        "It is not applied, merged, or executed by davdeploy."
                    ),
                },
            ],
            "pr_state_model": [
                "NOT_CREATED",
                "READY_TO_PUBLISH",
                "PUBLISHED",
                "CHECKS_PENDING",
                "CHECKS_PASSED",
                "MERGED",
                "CLOSED",
            ],
            "merge_boundary": "davdeploy records PR state but never merges customer code or desired state.",
        }
        return contract

    @staticmethod
    def _profile_desired_state_contract(
        profile_name: str, common: dict[str, Any]
    ) -> dict[str, Any]:
        if profile_name == "aws-app-runner":
            return {
                "profile": profile_name,
                "resources": [
                    "aws_apprunner_service",
                    "aws_iam_role",
                    "aws_secretsmanager_secret_reference",
                ],
                "source": "container image or repository source resolved by a later reviewed pipeline",
                "networking": "managed HTTPS ingress with private data/service boundaries where supported",
                "monitoring": common["observability"],
                "tags": common["required_tags"],
            }
        if profile_name == "aws-ecs-fargate":
            return {
                "profile": profile_name,
                "resources": [
                    "aws_ecs_service",
                    "aws_ecs_task_definition",
                    "aws_lb",
                    "aws_iam_role",
                ],
                "source": "immutable image digest from an approved build",
                "networking": "private subnets with narrowly scoped load balancer ingress when required",
                "monitoring": common["observability"],
                "tags": common["required_tags"],
            }
        if profile_name == "aws-eks-governed":
            return {
                "profile": profile_name,
                "resources": ["helm_release", "kubernetes_namespace", "argocd_application"],
                "gitops": "reviewed desired state only; Argo observes after human merge",
                "kubernetes_required": True,
                "monitoring": common["observability"],
                "tags": common["required_tags"],
            }
        return {
            "profile": profile_name,
            "resources": ["profile_specific_contract_pending"],
            "monitoring": common["observability"],
            "tags": common["required_tags"],
            "boundary": "Profile is recognized by the planner but cloud rendering remains plan-only.",
        }

    @staticmethod
    def _desired_state_publication_payload(publication: DesiredStatePublication) -> dict[str, Any]:
        return {
            "id": publication.id,
            "revision_id": publication.revision_id,
            "repository_url": publication.repository_url,
            "branch": publication.branch,
            "state": publication.state,
            "publication_url": publication.publication_url,
            "required_checks": publication.required_checks.get("checks", []),
            "package": publication.package,
            "content_digest": publication.content_digest,
            "created_by_subject": publication.created_by_subject,
            "created_at": publication.created_at.isoformat() if publication.created_at else None,
            "execution": (
                "SIMULATED_FIXTURE_PR"
                if str(publication.publication_url or "").startswith("fixture-pr://")
                else "EXECUTED_GITHUB_PR_CREATED"
            ),
            "merge_boundary": "davdeploy never merges the desired-state PR itself.",
        }

    def create_terraform_plan_render_for_revision(
        self, principal: Principal, revision_id: str, provided_digest: str
    ) -> dict[str, Any]:
        """Generate a plan-only, revision-bound Terraform contract.

        This is a renderer, not an executor. It persists deterministic module
        inputs and file previews for human review and offline validation. It
        never returns an apply command and it never calls AWS.
        """
        revision, infrastructure_plan, source_deployment = self._approved_customer_revision(
            principal, revision_id
        )
        if (
            revision.content_digest != provided_digest
            or plan_hash(revision.content) != provided_digest
        ):
            raise ValueError("stale Terraform render request: approved digest changed")
        content = revision.content
        profile_name = str(content.get("summary", {}).get("selected_profile") or "")
        project = self._project(principal, infrastructure_plan.project_id)
        application = content.get("application_analysis") or {}
        target = content.get("target") or {}
        repository_url = application.get("repository")
        branch = application.get("branch")
        if not repository_url or not branch:
            raise ValueError("approved plan has no selected repository and branch")
        if target.get("provider") != "aws" or not target.get("region"):
            raise ValueError("approved plan has no AWS target region")
        repository_connection = self.db.scalar(
            select(RepositoryConnection).where(
                RepositoryConnection.organization_id == principal.organization_id,
                RepositoryConnection.project_id == project.id,
                RepositoryConnection.repository_url == repository_url,
            )
        )
        if repository_connection is None:
            raise ValueError("selected repository is no longer connected to this project")
        if (
            repository_connection.selected_branch
            and repository_connection.selected_branch != branch
        ):
            raise ValueError("selected repository branch changed after approval")
        existing = self.db.scalar(
            select(TerraformPlanRender).where(
                TerraformPlanRender.organization_id == principal.organization_id,
                TerraformPlanRender.revision_id == revision.id,
                TerraformPlanRender.content_digest == revision.content_digest,
                TerraformPlanRender.profile == profile_name,
            )
        )
        if existing:
            return self._terraform_plan_render_payload(existing)
        if profile_name == "aws-app-runner":
            render = self._app_runner_terraform_contract(
                revision=revision,
                infrastructure_plan=infrastructure_plan,
                source_deployment=source_deployment,
                repository_url=str(repository_url),
                branch=str(branch),
            )
        else:
            render = self._nova_terraform_contract(
                principal=principal,
                revision=revision,
                infrastructure_plan=infrastructure_plan,
                source_deployment=source_deployment,
                repository_url=str(repository_url),
                branch=str(branch),
            )
        stored = TerraformPlanRender(
            organization_id=principal.organization_id,
            revision_id=revision.id,
            project_id=project.id,
            profile=profile_name,
            state="PLAN_ONLY_NOT_APPLIED",
            terraform_root=render["terraform_root"],
            module_path=render["module_path"],
            render=render,
            content_digest=revision.content_digest,
            created_by_subject=principal.subject,
        )
        self.db.add(stored)
        self.db.flush()
        self.audit(
            principal,
            "terraform.plan_only_contract_rendered",
            "terraform_plan_render",
            stored.id,
            {
                "revision_id": revision.id,
                "digest": revision.content_digest,
                "profile": profile_name,
                "status": stored.state,
                "boundary": "plan-only Terraform contract; no plan/apply/destroy command executed",
            },
        )
        self.db.commit()
        return self._terraform_plan_render_payload(stored)

    def _nova_terraform_contract(
        self,
        *,
        principal: Principal,
        revision: InfrastructurePlanRevision,
        infrastructure_plan: InfrastructurePlan,
        source_deployment: DeploymentPlan,
        repository_url: str,
        branch: str,
    ) -> dict[str, Any]:
        """Render a Nova resource graph without making it executable.

        The generated JSON is deliberately stored only in the immutable render
        record.  No apply path accepts this render until a future runner adds
        provider-schema validation, policy evaluation and saved-plan binding.
        """
        target = revision.content.get("target") or {}
        profile_name = str(revision.content.get("summary", {}).get("selected_profile") or "")
        profile = execution_profile(profile_name)
        tenant = TenantScope(
            organization_id=principal.organization_id,
            workspace_id=principal.organization_id,
            project_id=infrastructure_plan.project_id,
            actor_id=principal.subject,
        )
        try:
            generated = self.terraform_generator.generate(
                approved_plan=revision.content,
                tenant=tenant,
                source_revision=revision.id,
            )
        except NovaTerraformGenerationFailed as error:
            self._record_model_usage(
                principal,
                {
                    "request_id": None,
                    "provider": "bedrock",
                    "model": self.terraform_generator.model_id,
                    "prompt_version": "terraform-nova2-contract-v3",
                    "usage": error.usage.model_dump(mode="json"),
                    "attempt_count": error.attempt_count,
                    "retry_count": error.usage.retry_count,
                    "latency_ms": error.usage.latency_ms,
                    "measured_at": error.usage.measured_at.isoformat(),
                    "estimated_cost_usd": error.usage.estimated_cost_usd,
                    "failure": "generation_failed",
                    "evidence": [_model_evidence_summary(item) for item in error.evidence],
                },
            )
            self.db.commit()
            raise
        response = generated.response
        self._record_model_usage(
            principal,
            {
                "request_id": response.request.request_id,
                "provider": response.request.provider,
                "model": response.request.model,
                "prompt_version": response.request.prompt_version,
                "usage": response.usage.model_dump(mode="json") if response.usage else {},
                "attempt_count": (response.usage.retry_count + 1) if response.usage else 1,
                "retry_count": response.usage.retry_count if response.usage else 0,
                "latency_ms": response.usage.latency_ms if response.usage else None,
                "measured_at": (
                    response.usage.measured_at.isoformat() if response.usage else None
                ),
                "estimated_cost_usd": (
                    response.usage.estimated_cost_usd if response.usage else None
                ),
                "evidence": [_model_evidence_summary(item) for item in response.evidence],
            },
        )
        resource_addresses = [
            f"{resource.resource_type}.{resource.name}" for resource in generated.proposal.resources
        ]
        return {
            "kind": "davdeploy.terraform.nova-generated-plan-only-render.v1",
            "profile": profile.profile,
            "delivery_kind": profile.delivery_kind,
            "status": "PLAN_ONLY_NOT_APPLIED",
            "generation": {
                "provider": response.request.provider,
                "model": response.request.model,
                "prompt_version": response.request.prompt_version,
                "input_digest": response.request.input_digest,
                "resource_addresses": resource_addresses,
                "assumptions": generated.proposal.assumptions,
                "limitations": generated.proposal.limitations,
            },
            "execution_boundary": (
                "Nova generated a typed resource graph from an approved revision. This record is "
                "not provider-schema validation, a Terraform plan, apply, destroy, AWS API call, "
                "GitHub write, Kubernetes action or production deployment."
            ),
            "terraform_root": "generated/revision-bound",
            "module_path": "generated-by-nova-no-preexisting-module",
            "commands": [
                "terraform init -backend=false -input=false <reviewed-generated-root>",
                "terraform validate <reviewed-generated-root>",
            ],
            "apply_command_available": False,
            "module_inputs": {
                "project_id": infrastructure_plan.project_id,
                "revision_id": revision.id,
                "source_deployment_plan_id": source_deployment.id,
                "plan_digest": revision.content_digest,
                "profile": profile_name,
                "repository_url": repository_url,
                "repository_branch": branch,
                "aws_account_id": target.get("account_id")
                or "customer-account-selected-at-apply-time",
                "aws_region": target.get("region"),
                "tags": {
                    "ManagedBy": "davdeploy",
                    "davdeployPlanDigest": revision.content_digest,
                    "davdeployRevisionId": revision.id,
                },
            },
            "files": [
                {
                    "path": "main.tf.json",
                    "purpose": "Nova-generated, typed AWS resource graph for review and offline validation.",
                    "content": self.terraform_generator.terraform_json(generated.proposal),
                },
                {
                    "path": "README.md",
                    "purpose": "Human approval boundary.",
                    "content": (
                        "# davdeploy Nova-generated Terraform\n\n"
                        "Generated from one approved revision. Validate and plan only; do not apply directly."
                    ),
                },
            ],
        }

    def _app_runner_terraform_contract(
        self,
        *,
        revision: InfrastructurePlanRevision,
        infrastructure_plan: InfrastructurePlan,
        source_deployment: DeploymentPlan,
        repository_url: str,
        branch: str,
    ) -> dict[str, Any]:
        content = revision.content
        profile = execution_profile("aws-app-runner")
        target = content.get("target") or {}
        observability = content.get("observability") or {}
        workload = content.get("application_analysis", {}).get("workload_spec", {})
        resource_names = [
            resource.get("name", "") for resource in content.get("resource_breakdown", [])
        ]
        if any("eks" in name.lower() or "kubernetes" in name.lower() for name in resource_names):
            raise ValueError("unsupported resources for App Runner renderer")
        service_name = self._terraform_safe_name(infrastructure_plan.title)
        digest = revision.content_digest
        account_id = target.get("account_id") or "customer-account-selected-at-apply-time"
        module_inputs = {
            "project_id": infrastructure_plan.project_id,
            "revision_id": revision.id,
            "source_deployment_plan_id": source_deployment.id,
            "plan_digest": digest,
            "profile": "aws-app-runner",
            "service_name": service_name,
            "repository_url": repository_url,
            "repository_branch": branch,
            "aws_account_id": account_id,
            "aws_region": target["region"],
            "source_boundary": (
                "Plan-only contract expects a later reviewed build to publish an immutable image "
                "to ECR or an explicitly approved App Runner source. This renderer does not build, "
                "push, deploy or grant GitHub write access."
            ),
            "image_repository": f"{account_id}.dkr.ecr.{target['region']}.amazonaws.com/{service_name}",
            "environment_variables": {
                "DAVDEPLOY_PLAN_DIGEST": digest,
                "DAVDEPLOY_PROFILE": "aws-app-runner",
                "APP_ENVIRONMENTS": ",".join(workload.get("environments") or []),
            },
            "secret_references": {
                "application": "aws-secretsmanager://davdeploy/app-runner/application",
            },
            "https_access": {
                "ingress": "managed App Runner HTTPS endpoint",
                "custom_domain": "optional later Route 53/ACM contract",
                "private_data_boundary": "customer data remains in the selected AWS account",
            },
            "iam": {
                "runtime_role": "least-privilege App Runner instance role",
                "deployment_role": "future explicit execution role; unavailable in this local renderer",
            },
            "observability": {
                "metrics_backend": observability.get("metrics_backend"),
                "grafana": observability.get("dashboard"),
                "scrape_targets": observability.get("scrape_targets", []),
                "baseline_dashboard": observability.get("baseline_dashboard", {}),
                "access_boundary": observability.get("access_boundary"),
                "limitations": observability.get("limitations", []),
                "cost_assumption": observability.get("cost_assumption"),
            },
            "tags": {
                "ManagedBy": "davdeploy",
                "davdeployPlanDigest": digest,
                "davdeployProjectId": infrastructure_plan.project_id,
                "davdeployRevisionId": revision.id,
                "davdeployProfile": "aws-app-runner",
            },
        }
        return {
            "kind": "davdeploy.terraform.plan-only-render.v1",
            "profile": profile.profile,
            "delivery_kind": profile.delivery_kind,
            "status": "PLAN_ONLY_NOT_APPLIED",
            "execution_boundary": (
                "Generated deployment contract only. It is not a Terraform plan, apply, destroy, "
                "AWS API call, GitHub write, Kubernetes action or production deployment."
            ),
            "terraform_root": "infrastructure/terraform/renderers/app-runner-plan",
            "module_path": "infrastructure/terraform/modules/app-runner-plan-contract",
            "commands": [
                "terraform fmt -check -recursive infrastructure/terraform",
                "terraform -chdir=infrastructure/terraform/renderers/app-runner-plan init -backend=false -input=false",
                "terraform -chdir=infrastructure/terraform/renderers/app-runner-plan validate",
            ],
            "apply_command_available": False,
            "module_inputs": module_inputs,
            "files": [
                {
                    "path": "main.tf.json",
                    "purpose": "Root module wrapper for offline validation.",
                    "content": {
                        "module": {
                            "davdeploy_app_runner_plan_contract": {
                                "source": "../../modules/app-runner-plan-contract",
                                **module_inputs,
                            }
                        }
                    },
                },
                {
                    "path": "terraform.tfvars.json",
                    "purpose": "Human-readable exact inputs generated from the approved digest.",
                    "content": module_inputs,
                },
                {
                    "path": "README.md",
                    "purpose": "Operator boundary note.",
                    "content": (
                        "# davdeploy App Runner plan-only Terraform contract\n\n"
                        "Generated from an approved customer-plan revision. Validate only; do not apply."
                    ),
                },
            ],
        }

    @staticmethod
    def _terraform_safe_name(value: str) -> str:
        safe = "".join(character.lower() if character.isalnum() else "-" for character in value)
        safe = "-".join(part for part in safe.split("-") if part)
        return safe[:48] or "davdeploy-app"

    @staticmethod
    def _terraform_plan_render_payload(render: TerraformPlanRender) -> dict[str, Any]:
        return {
            "id": render.id,
            "revision_id": render.revision_id,
            "profile": render.profile,
            "state": render.state,
            "terraform_root": render.terraform_root,
            "module_path": render.module_path,
            "render": render.render,
            "content_digest": render.content_digest,
            "created_by_subject": render.created_by_subject,
            "created_at": render.created_at.isoformat() if render.created_at else None,
            "execution": "IMPLEMENTED_UNEXECUTED_PLAN_ONLY",
            "boundary": "No Terraform plan/apply/destroy or AWS mutation is reachable from this renderer.",
        }

    def create_cloud_readiness_preflight(
        self,
        principal: Principal,
        revision_id: str,
        *,
        content_digest: str,
        expected_account_id: str | None,
        allowed_regions: list[str],
        required_tags: dict[str, str],
        budget_ceiling_usd: int | None,
        execution_mode: str,
        require_reviewed_pr: bool,
        runtime_identity_configured: bool,
    ) -> dict[str, Any]:
        """Evaluate local guardrails before any future cloud action can be considered."""
        if not self._is_workspace_administrator(principal):
            raise PermissionError(
                "only a workspace administrator can run cloud-readiness preflight"
            )
        revision, infrastructure_plan, _ = self._approved_customer_revision(principal, revision_id)
        if (
            revision.content_digest != content_digest
            or plan_hash(revision.content) != content_digest
        ):
            raise ValueError("stale cloud preflight request: approved digest changed")
        content = revision.content
        target = content.get("target") or {}
        policy = content.get("policy_findings") or {}
        cost = content.get("cost_estimate", {}).get("range") or {}
        render = self.db.scalar(
            select(TerraformPlanRender)
            .where(
                TerraformPlanRender.organization_id == principal.organization_id,
                TerraformPlanRender.revision_id == revision.id,
                TerraformPlanRender.content_digest == revision.content_digest,
            )
            .order_by(TerraformPlanRender.created_at.desc())
            .limit(1)
        )
        publication = self.db.scalar(
            select(DesiredStatePublication)
            .where(
                DesiredStatePublication.organization_id == principal.organization_id,
                DesiredStatePublication.revision_id == revision.id,
                DesiredStatePublication.content_digest == revision.content_digest,
            )
            .order_by(DesiredStatePublication.created_at.desc())
            .limit(1)
        )
        module_inputs = (render.render.get("module_inputs") if render else {}) or {}
        render_tags = module_inputs.get("tags") or {}
        region = target.get("region")
        account_id = target.get("account_id")
        if not account_id and render:
            rendered_account = module_inputs.get("aws_account_id")
            account_id = (
                None
                if rendered_account == "customer-account-selected-at-apply-time"
                else rendered_account
            )
        checklist = [
            self._preflight_item(
                "approved_digest",
                "Exact approved digest",
                revision.content_digest == content_digest,
                f"approved digest {revision.content_digest}",
            ),
            self._preflight_item(
                "policy_result",
                "Policy allows future execution consideration",
                policy.get("result") != PolicyResult.DENY,
                f"policy result: {policy.get('result', 'unknown')}",
            ),
            self._preflight_item(
                "terraform_contract",
                "Generated Terraform contract",
                bool(render and render.state == "PLAN_ONLY_NOT_APPLIED"),
                "plan-only App Runner contract exists"
                if render
                else "no generated Terraform contract",
            ),
            self._preflight_item(
                "no_apply_command",
                "No apply command is reachable",
                bool(render and render.render.get("apply_command_available") is False),
                "renderer exposes validate-only commands" if render else "renderer missing",
            ),
            self._preflight_item(
                "expected_account",
                "Expected AWS account",
                expected_account_id is None or account_id == expected_account_id,
                f"expected {expected_account_id or 'not supplied'}; plan target {account_id or 'not connected'}",
            ),
            self._preflight_item(
                "allowed_region",
                "Allowed AWS region",
                bool(region and region in allowed_regions),
                f"region {region or 'missing'}; allowed {', '.join(allowed_regions)}",
            ),
            self._preflight_item(
                "required_tags",
                "Required ownership tags",
                all(render_tags.get(key) == value for key, value in required_tags.items()),
                f"required tags {required_tags or {'ManagedBy': 'davdeploy'}}",
            ),
            self._preflight_item(
                "budget_ceiling",
                "Budget ceiling",
                budget_ceiling_usd is None
                or int(cost.get("monthly_high", 0)) <= budget_ceiling_usd,
                f"estimated high ${cost.get('monthly_high', 'unknown')}; ceiling ${budget_ceiling_usd or 'not supplied'}",
            ),
            self._preflight_item(
                "reviewed_pr",
                "Reviewed desired-state PR",
                (not require_reviewed_pr)
                or bool(publication and publication.state in {"CHECKS_PASSED", "MERGED"}),
                f"state {publication.state if publication else 'not created'}",
            ),
            self._preflight_item(
                "runtime_identity",
                "davdeploy runtime identity",
                runtime_identity_configured,
                "not configured in local mode"
                if not runtime_identity_configured
                else "configured by operator",
            ),
            self._preflight_item(
                "execution_mode",
                "Dry-run/plan-only execution mode",
                execution_mode in {"DRY_RUN_ONLY", "PLAN_ONLY"},
                f"mode {execution_mode}; apply remains unavailable",
            ),
        ]
        failures = [item for item in checklist if item["status"] == "FAIL"]
        if not failures:
            state = "READY_FOR_AUTHORIZED_CLOUD_PLAN"
        elif all(item["id"] == "runtime_identity" for item in failures):
            state = "BLOCKED_CLOUD_RUNTIME_NOT_CONFIGURED"
        else:
            state = "BLOCKED_GUARDRAIL_FAILURE"
        guard = {
            "expected_account_id": expected_account_id,
            "allowed_regions": allowed_regions,
            "required_tags": required_tags,
            "budget_ceiling_usd": budget_ceiling_usd,
            "execution_mode": execution_mode,
            "require_reviewed_pr": require_reviewed_pr,
            "runtime_identity_configured": runtime_identity_configured,
        }
        would_deploy = {
            "profile": content.get("summary", {}).get("selected_profile"),
            "aws_account_id": account_id,
            "region": region,
            "terraform_root": render.terraform_root if render else None,
            "terraform_state": render.state if render else None,
            "desired_state_pr_state": publication.state if publication else None,
            "policy_result": policy.get("result"),
            "plan_digest": revision.content_digest,
            "not_deployed": True,
            "boundary": (
                "Preflight only. Cloud execution remains blocked unless a future explicit "
                "operator workflow performs an authenticated plan and a separately approved apply."
            ),
        }
        stored = CloudReadinessPreflight(
            organization_id=principal.organization_id,
            revision_id=revision.id,
            project_id=infrastructure_plan.project_id,
            state=state,
            guard=guard,
            checklist={"items": checklist},
            would_deploy=would_deploy,
            content_digest=revision.content_digest,
            created_by_subject=principal.subject,
        )
        self.db.add(stored)
        self.db.flush()
        self.audit(
            principal,
            "cloud_readiness.preflight_evaluated",
            "cloud_readiness_preflight",
            stored.id,
            {"revision_id": revision.id, "digest": revision.content_digest, "state": state},
        )
        self.db.commit()
        return self._cloud_readiness_preflight_payload(stored)

    @staticmethod
    def _preflight_item(check_id: str, label: str, passed: bool, detail: str) -> dict[str, str]:
        return {
            "id": check_id,
            "label": label,
            "status": "PASS" if passed else "FAIL",
            "detail": detail,
        }

    @staticmethod
    def _cloud_readiness_preflight_payload(preflight: CloudReadinessPreflight) -> dict[str, Any]:
        return {
            "id": preflight.id,
            "revision_id": preflight.revision_id,
            "state": preflight.state,
            "guard": preflight.guard,
            "checklist": preflight.checklist.get("items", []),
            "would_deploy": preflight.would_deploy,
            "content_digest": preflight.content_digest,
            "created_by_subject": preflight.created_by_subject,
            "created_at": preflight.created_at.isoformat() if preflight.created_at else None,
            "execution": "LOCAL_PREFLIGHT_ONLY",
            "boundary": "This preflight cannot run Terraform plan/apply/destroy or mutate AWS.",
        }

    def create_terraform_plan_review_for_revision(
        self,
        principal: Principal,
        revision_id: str,
        *,
        content_digest: str,
        preflight_id: str | None,
        expected_account_id: str | None,
        expected_region: str | None,
        mode: str,
        allow_cloud_plan: bool,
    ) -> dict[str, Any]:
        """Create plan-only Terraform review evidence.

        This is intentionally not an apply path. The default local mode records
        deterministic command evidence only. Authenticated plan mode is blocked
        unless both the request and process environment explicitly opt in.
        """
        if not self._is_workspace_administrator(principal):
            raise PermissionError(
                "only a workspace administrator can request a Terraform plan review"
            )
        revision, infrastructure_plan, _ = self._approved_customer_revision(principal, revision_id)
        if (
            revision.content_digest != content_digest
            or plan_hash(revision.content) != content_digest
        ):
            raise ValueError("stale Terraform plan review request: approved digest changed")
        render = self.db.scalar(
            select(TerraformPlanRender)
            .where(
                TerraformPlanRender.organization_id == principal.organization_id,
                TerraformPlanRender.revision_id == revision.id,
                TerraformPlanRender.content_digest == revision.content_digest,
                TerraformPlanRender.profile == "aws-app-runner",
            )
            .order_by(TerraformPlanRender.created_at.desc())
            .limit(1)
        )
        preflight_query = select(CloudReadinessPreflight).where(
            CloudReadinessPreflight.organization_id == principal.organization_id,
            CloudReadinessPreflight.revision_id == revision.id,
            CloudReadinessPreflight.content_digest == revision.content_digest,
        )
        if preflight_id:
            preflight_query = preflight_query.where(CloudReadinessPreflight.id == preflight_id)
        preflight = self.db.scalar(
            preflight_query.order_by(CloudReadinessPreflight.created_at.desc()).limit(1)
        )
        state = "PLAN_REVIEW_READY"
        blockers: list[str] = []
        authenticated_mode = mode in {
            "AUTHENTICATED_TERRAFORM_PLAN",
            "AUTHENTICATED_TERRAFORM_DESTROY_PLAN",
        }
        destroy_review = mode == "AUTHENTICATED_TERRAFORM_DESTROY_PLAN"
        evidence: dict[str, Any] = {
            "mode": mode,
            "profile": "aws-app-runner",
            "apply_available": False,
            "requested_authenticated_plan": authenticated_mode,
            "requested_destroy_plan": destroy_review,
            "execution_boundary": (
                "Plan-only review evidence. Terraform apply/destroy is unavailable and no AWS "
                "resource creation is reachable from this endpoint."
            ),
        }
        command = {
            "terraform_root": render.terraform_root if render else None,
            "commands": [],
            "apply_command_available": False,
            "executor": "fixture-plan-review",
        }
        if render is None:
            state = "BLOCKED_TERRAFORM_CONTRACT_REQUIRED"
            blockers.append(
                "Generate an App Runner Terraform contract for the approved digest first."
            )
        else:
            render_inputs = render.render.get("module_inputs", {})
            region = render_inputs.get("aws_region")
            account_id = render_inputs.get("aws_account_id")
            command["commands"] = [
                f"terraform -chdir={render.terraform_root} init -backend=false -input=false",
                f"terraform -chdir={render.terraform_root} plan -input=false -refresh=false -lock=false -no-color",
            ]
            evidence.update(
                {
                    "terraform_render_id": render.id,
                    "terraform_root": render.terraform_root,
                    "module_path": render.module_path,
                    "plan_digest_embedded": render_inputs.get("plan_digest")
                    == revision.content_digest,
                    "aws_account_id": account_id,
                    "aws_region": region,
                }
            )
            if expected_account_id and account_id not in {
                expected_account_id,
                "customer-account-selected-at-apply-time",
            }:
                state = "BLOCKED_ACCOUNT_GUARD"
                blockers.append(
                    f"Expected AWS account {expected_account_id}; render targets {account_id}."
                )
            if expected_region and region != expected_region:
                state = "BLOCKED_REGION_GUARD"
                blockers.append(f"Expected AWS region {expected_region}; render targets {region}.")
        if preflight is None:
            state = "BLOCKED_PREFLIGHT_REQUIRED"
            blockers.append("Run a cloud-readiness preflight for this approved digest first.")
        elif preflight.state != "READY_FOR_AUTHORIZED_CLOUD_PLAN":
            state = "BLOCKED_PREFLIGHT"
            blockers.append(f"Cloud-readiness preflight is {preflight.state}.")
            evidence["preflight"] = self._cloud_readiness_preflight_payload(preflight)
        else:
            evidence["preflight"] = self._cloud_readiness_preflight_payload(preflight)
        if authenticated_mode:
            env_allowed = os.getenv("ALLOW_CLOUD_PLAN", "").lower() == "true"
            if not allow_cloud_plan or not env_allowed:
                state = "BLOCKED_CLOUD_PLAN_NOT_ALLOWED"
                blockers.append(
                    "Authenticated Terraform plan requires request allow_cloud_plan=true and ALLOW_CLOUD_PLAN=true."
                )
            command["executor"] = "authenticated-terraform-plan-gated"
            evidence["allow_cloud_plan_request"] = allow_cloud_plan
            evidence["allow_cloud_plan_env"] = env_allowed
        else:
            evidence["fixture_plan_summary"] = (
                "Local contract review only. Commands are recorded as the only allowed plan-only "
                "shape; they are not an authenticated AWS plan and they never include apply."
            )
        if state == "PLAN_REVIEW_READY":
            state = (
                (
                    "AUTHENTICATED_DESTROY_PLAN_ALLOWED_NOT_EXECUTED"
                    if destroy_review
                    else "AUTHENTICATED_PLAN_ALLOWED_NOT_EXECUTED"
                )
                if authenticated_mode
                else "LOCAL_CONTRACT_PLAN_REVIEWED"
            )
            evidence["result"] = (
                "ready for operator-authenticated terraform plan command outside automated tests"
            )
        evidence["blockers"] = blockers
        stored = TerraformPlanReview(
            organization_id=principal.organization_id,
            revision_id=revision.id,
            project_id=infrastructure_plan.project_id,
            terraform_render_id=render.id if render else None,
            preflight_id=preflight.id if preflight else None,
            mode=mode,
            state=state,
            command=command,
            evidence=evidence,
            content_digest=revision.content_digest,
            created_by_subject=principal.subject,
        )
        self.db.add(stored)
        self.db.flush()
        if stored.state in {
            "AUTHENTICATED_PLAN_ALLOWED_NOT_EXECUTED",
            "AUTHENTICATED_DESTROY_PLAN_ALLOWED_NOT_EXECUTED",
        }:
            connection_id = str((revision.content.get("target") or {}).get("connection_id") or "")
            connection = self._cloud_connection(principal, connection_id) if connection_id else None
            runner_bucket = os.getenv("DAVDEPLOY_CUSTOMER_EXECUTION_STATE_BUCKET", "")
            runner_artifact = os.getenv("DAVDEPLOY_CUSTOMER_EXECUTION_ARTIFACT_S3_URI", "")
            runtime_enabled = (
                os.getenv("DAVDEPLOY_ENABLE_APP_RUNNER_EXECUTION", "").lower() == "true"
                and os.getenv("DAVDEPLOY_CLOUD_EXECUTION_COMMAND_ENABLED", "").lower() == "true"
            )
            if (
                not connection
                or connection.setup_state != "VERIFIED"
                or not connection.execution_role_arn
            ):
                stored.state = "BLOCKED_CLOUD_CONNECTION_NOT_VERIFIED"
                stored.evidence = {
                    **stored.evidence,
                    "blockers": [
                        "Authenticated Terraform plan requires a verified customer connection with an execution role."
                    ],
                }
            elif (
                not connection.external_id_secret_ref
                or not runner_bucket
                or not runner_artifact
                or not runtime_enabled
            ):
                stored.state = "BLOCKED_CLOUD_EXECUTION_RUNTIME_NOT_CONFIGURED"
                stored.evidence = {
                    **stored.evidence,
                    "blockers": [
                        "Authenticated Terraform plan runner configuration is incomplete or disabled."
                    ],
                }
            else:
                plan_lifecycle_work = [
                    {
                        "module_id": "aws-managed-application",
                        "operation": "plan",
                        "dependencies": [],
                        "resource_tags": {
                            "ManagedBy": "davdeploy",
                            "DavDeployWorkspace": principal.organization_id,
                            "DavDeployProject": infrastructure_plan.project_id,
                            "DavDeployPlan": revision.content_digest,
                        },
                    }
                ]
                plan_run = CloudExecutionRun(
                    organization_id=principal.organization_id,
                    revision_id=revision.id,
                    project_id=infrastructure_plan.project_id,
                    terraform_render_id=render.id if render else None,
                    preflight_id=preflight.id if preflight else None,
                    terraform_plan_review_id=stored.id,
                    profile="aws-app-runner",
                    state="SUBMITTING",
                    mode=mode,
                    command={
                        "operation": "destroy-plan" if destroy_review else "plan",
                        "artifact_bound_apply": True,
                        "universal_lifecycle_work": plan_lifecycle_work,
                    },
                    evidence={},
                    outputs={"status": "submitting", "resources_created": []},
                    content_digest=revision.content_digest,
                    requested_by_subject=principal.subject,
                )
                self.db.add(plan_run)
                self.db.flush()
                image_identifier = ""
                if not destroy_review:
                    image_build = self.db.scalar(
                        select(CloudExecutionRun)
                        .where(
                            CloudExecutionRun.organization_id == principal.organization_id,
                            CloudExecutionRun.revision_id == revision.id,
                            CloudExecutionRun.content_digest == revision.content_digest,
                            CloudExecutionRun.mode == "AUTHENTICATED_APP_RUNNER_IMAGE_BUILD",
                            CloudExecutionRun.state == "IMAGE_BUILT_AWAITING_SERVICE_PLAN",
                        )
                        .order_by(CloudExecutionRun.created_at.desc())
                        .limit(1)
                    )
                    image_identifier = str(
                        ((image_build.outputs or {}).get("image_build") or {}).get(
                            "image_identifier"
                        )
                        if image_build
                        else ""
                    )
                execution_environment = {
                    "AWS_REGION": str(region or connection.region),
                    "EXPECTED_AWS_ACCOUNT_ID": str(connection.account_id),
                    "TF_STATE_BUCKET": runner_bucket,
                    "TF_LOCK_TABLE": os.getenv("DAVDEPLOY_CUSTOMER_EXECUTION_LOCK_TABLE", ""),
                    "DAVDEPLOY_CUSTOMER_CONNECTION_ID": connection.id,
                    "DAVDEPLOY_CUSTOMER_EXECUTION_ROLE_ARN": connection.execution_role_arn,
                    "DAVDEPLOY_EXTERNAL_ID_SECRET_ARN": connection.external_id_secret_ref,
                    "DAVDEPLOY_CUSTOMER_APP_RUNNER_ECR_ROLE_ARN": f"arn:aws:iam::{connection.account_id}:role/davdeployAppRunnerEcr-{connection.id}",
                    "DAVDEPLOY_CUSTOMER_APP_RUNNER_RUNTIME_ROLE_ARN": f"arn:aws:iam::{connection.account_id}:role/davdeployAppRunnerRuntime-{connection.id}",
                    "DAVDEPLOY_EXECUTION_ARTIFACT_S3_URI": runner_artifact,
                    "DAVDEPLOY_EXECUTION_OPERATION": "destroy-plan" if destroy_review else "plan",
                    "DAVDEPLOY_EXECUTION_RUN_ID": plan_run.id,
                    "DAVDEPLOY_EXECUTION_RESULT_S3_URI": f"s3://{runner_bucket}/davdeploy/customer/{connection.id}/runs/{plan_run.id}/result.json",
                    "DAVDEPLOY_CUSTOMER_PLAN_DIGEST": revision.content_digest,
                    "DAVDEPLOY_CUSTOMER_APP_RUNNER_SERVICE_NAME": f"davdeploy-{connection.id[:8]}-workload",
                }
                if image_identifier:
                    execution_environment.update(
                        {
                            "DAVDEPLOY_CUSTOMER_IMAGE_IDENTIFIER": image_identifier,
                            "DAVDEPLOY_ENABLE_CUSTOMER_SERVICE": "true",
                        }
                    )
                if not execution_environment["TF_LOCK_TABLE"]:
                    stored.state = "BLOCKED_CLOUD_EXECUTION_RUNTIME_NOT_CONFIGURED"
                    stored.evidence = {
                        **stored.evidence,
                        "blockers": ["Customer execution lock table is not configured."],
                    }
                    plan_run.state = "BLOCKED_CLOUD_EXECUTION_RUNTIME_NOT_CONFIGURED"
                else:
                    plan_run.evidence = {
                        "execution_environment": execution_environment,
                        "result_s3_uri": execution_environment["DAVDEPLOY_EXECUTION_RESULT_S3_URI"],
                        "boundary": "A bounded runner may generate a Terraform plan artifact only. It cannot apply this request.",
                    }
                    result = self.cloud_execution.execute(
                        {
                            "run_id": plan_run.id,
                            "environment": execution_environment,
                            "lifecycle_work": plan_lifecycle_work,
                        }
                    )
                    plan_run.state = result.state
                    plan_run.outputs = {
                        **plan_run.outputs,
                        **result.outputs,
                        "operations": list(result.operations),
                        "failure_reason": result.failure_reason,
                    }
                    stored.state = (
                        "AUTHENTICATED_DESTROY_PLAN_SUBMITTED"
                        if destroy_review and result.state == "SUBMITTED"
                        else "AUTHENTICATED_PLAN_SUBMITTED"
                        if result.state == "SUBMITTED"
                        else "BLOCKED_CLOUD_EXECUTION_RUNTIME_NOT_CONFIGURED"
                    )
                    stored.evidence = {
                        **stored.evidence,
                        "execution_run_id": plan_run.id,
                        "runner_state": result.state,
                    }
        self.audit(
            principal,
            "terraform.plan_only_review_recorded",
            "terraform_plan_review",
            stored.id,
            {
                "revision_id": revision.id,
                "digest": revision.content_digest,
                "state": state,
                "mode": mode,
                "apply_available": False,
            },
        )
        self.db.commit()
        return self._terraform_plan_review_payload(stored)

    @staticmethod
    def _terraform_plan_review_payload(review: TerraformPlanReview) -> dict[str, Any]:
        return {
            "id": review.id,
            "revision_id": review.revision_id,
            "terraform_render_id": review.terraform_render_id,
            "preflight_id": review.preflight_id,
            "mode": review.mode,
            "state": review.state,
            "command": review.command,
            "evidence": review.evidence,
            "content_digest": review.content_digest,
            "created_by_subject": review.created_by_subject,
            "created_at": review.created_at.isoformat() if review.created_at else None,
            "apply_available": False,
            "execution": "PLAN_ONLY_REVIEW_NO_APPLY",
            "boundary": "Terraform apply/destroy is unavailable. This record does not create AWS resources.",
        }

    def _create_serverless_certification_run(
        self,
        principal: Principal,
        revision_id: str,
        *,
        content_digest: str,
        operation: str | None,
        prior_run_id: str | None,
        source_commit: str | None,
        expected_account_id: str | None,
        expected_region: str | None,
        confirmation: str | None,
    ) -> dict[str, Any]:
        """Create one allowlisted hosted-certification phase for Lambda/API.

        This narrow path is restricted to an explicitly allowlisted workspace.
        Each follow-on phase consumes a successful, digest-bound prior run; it
        cannot select an arbitrary repository, AWS role, Terraform root, or
        previous plan artifact.
        """
        if not self._is_workspace_administrator(principal):
            raise PermissionError("only a workspace administrator can request certification")
        if (
            os.getenv("DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION", "false").lower()
            != "true"
        ):
            raise ValueError("hosted serverless certification is disabled for this environment")
        allowed_workspaces = {
            value.strip()
            for value in os.getenv("DAVDEPLOY_SERVERLESS_CERTIFICATION_WORKSPACE_IDS", "").split(
                ","
            )
            if value.strip()
        }
        if not allowed_workspaces or principal.organization_id not in allowed_workspaces:
            raise PermissionError("workspace is not allowlisted for hosted renderer certification")
        if operation not in {
            "build-artifact",
            "plan",
            "apply-saved-plan",
            "health",
            "destroy-plan",
            "destroy-saved-plan",
            "verify-cleanup",
        }:
            raise ValueError("a supported serverless certification phase is required")
        revision, infrastructure_plan, _ = self._approved_customer_revision(principal, revision_id)
        if (
            revision.content_digest != content_digest
            or plan_hash(revision.content) != content_digest
        ):
            raise ValueError("stale serverless certification request: approved digest changed")
        content = revision.content
        if (content.get("summary") or {}).get("selected_profile") != "aws-lambda-api":
            raise ValueError("serverless certification requires an approved Lambda API plan")
        module_payload = (content.get("architecture") or {}).get("modules") or []
        if len(module_payload) != 1 or module_payload[0].get("identifier") != "aws-serverless-api":
            raise ValueError("serverless certification requires exactly one Lambda API module")
        connection_id = str((content.get("target") or {}).get("connection_id") or "")
        if not connection_id:
            raise ValueError("serverless certification requires a verified cloud connection")
        connection = self._cloud_connection(principal, connection_id)
        if (
            connection.provider != "aws"
            or connection.setup_state != "VERIFIED"
            or not connection.execution_role_arn
            or not connection.external_id_secret_ref
            or not connection.account_id
        ):
            raise ValueError("cloud connection is not verified for bounded execution")
        account_id = str(connection.account_id)
        region = str((content.get("target") or {}).get("region") or "")
        if expected_account_id and expected_account_id != account_id:
            raise ValueError("expected AWS account does not match the verified connection")
        if expected_region and expected_region != region:
            raise ValueError("expected AWS region does not match the approved plan")
        if not region:
            raise ValueError("approved serverless plan has no AWS region")

        bucket = os.getenv("DAVDEPLOY_CUSTOMER_EXECUTION_STATE_BUCKET", "")
        lock_table = os.getenv("DAVDEPLOY_CUSTOMER_EXECUTION_LOCK_TABLE", "")
        executor_artifact_uri = os.getenv("DAVDEPLOY_CUSTOMER_EXECUTION_ARTIFACT_S3_URI", "")
        if not bucket or not lock_table or not executor_artifact_uri:
            raise ValueError("hosted customer execution runner configuration is incomplete")
        if not re.fullmatch(r"[A-Za-z0-9.-]{3,63}", bucket):
            raise ValueError("hosted customer execution state bucket is invalid")
        project_id = infrastructure_plan.project_id
        prefix = f"s3://{bucket}/davdeploy/customer/{connection.id}/projects/{project_id}/"
        digest_prefix = f"{prefix}{content_digest}/"

        application = content.get("application_analysis") or {}
        repository_url = str(application.get("repository") or "")
        branch = str(application.get("branch") or "")
        repository_connection = self.db.scalar(
            select(RepositoryConnection).where(
                RepositoryConnection.organization_id == principal.organization_id,
                RepositoryConnection.project_id == project_id,
                RepositoryConnection.repository_url == repository_url,
            )
        )
        if not repository_url or not branch or repository_connection is None:
            raise ValueError("approved plan must use a repository connected to this project")
        if (
            repository_connection.selected_branch
            and repository_connection.selected_branch != branch
        ):
            raise ValueError("approved source branch no longer matches the project connection")

        prior: CloudExecutionRun | None = None
        prior_environment: dict[str, Any] = {}
        prior_detail: dict[str, Any] = {}
        required_prior = {
            "build-artifact": None,
            "plan": ({"build-artifact"}, {"ARTIFACT_READY"}),
            "apply-saved-plan": ({"plan"}, {"PLAN_READY_FOR_REVIEW"}),
            "health": ({"apply-saved-plan"}, {"SUCCEEDED_AWAITING_OBSERVATION"}),
            "destroy-plan": (
                {"apply-saved-plan", "health"},
                {"SUCCEEDED_AWAITING_OBSERVATION", "HEALTHY"},
            ),
            "destroy-saved-plan": ({"destroy-plan"}, {"DESTROY_PLAN_READY_FOR_REVIEW"}),
            "verify-cleanup": ({"destroy-saved-plan"}, {"DESTROYED_VERIFIED"}),
        }[operation]
        if required_prior is None:
            if prior_run_id:
                raise ValueError("artifact build must not reference a prior execution run")
        else:
            if not prior_run_id:
                raise ValueError("this lifecycle phase requires its successful prior run")
            prior = self.db.get(CloudExecutionRun, prior_run_id)
            expected_operations, expected_states = required_prior
            if (
                prior is None
                or prior.organization_id != principal.organization_id
                or prior.project_id != project_id
                or prior.revision_id != revision.id
                or prior.profile != "aws-serverless-api"
                or prior.mode != "AUTHENTICATED_SERVERLESS_CERTIFICATION"
                or prior.content_digest != content_digest
                or (prior.command or {}).get("operation") not in expected_operations
                or prior.state not in expected_states
            ):
                raise ValueError("prior lifecycle run is not eligible for this phase")
            if operation in {"apply-saved-plan", "destroy-saved-plan"}:
                prior_consumers = self.db.scalars(
                    select(CloudExecutionRun).where(
                        CloudExecutionRun.organization_id == principal.organization_id,
                        CloudExecutionRun.revision_id == revision.id,
                        CloudExecutionRun.profile == "aws-serverless-api",
                        CloudExecutionRun.mode == "AUTHENTICATED_SERVERLESS_CERTIFICATION",
                        CloudExecutionRun.content_digest == content_digest,
                    )
                )
                if any(
                    (candidate.command or {}).get("prior_run_id") == prior.id
                    and (candidate.command or {}).get("operation") == operation
                    for candidate in prior_consumers
                ):
                    raise ValueError("this saved plan has already been submitted for execution")
            prior_environment = (prior.evidence or {}).get("execution_environment") or {}
            artifact_result = (prior.outputs or {}).get("runner_artifact") or {}
            prior_detail = artifact_result.get("detail") or {}
            if (
                prior_environment.get("DAVDEPLOY_CUSTOMER_CONNECTION_ID") != connection.id
                or prior_environment.get("EXPECTED_AWS_ACCOUNT_ID") != account_id
                or prior_environment.get("AWS_REGION") != region
            ):
                raise ValueError("prior lifecycle run does not match this connection and target")

        confirmation_by_operation = {
            "apply-saved-plan": "APPLY_SERVERLESS_API_SAVED_PLAN",
            "destroy-saved-plan": "DESTROY_SERVERLESS_API_SAVED_PLAN",
        }
        expected_confirmation = confirmation_by_operation.get(operation)
        if expected_confirmation and confirmation != expected_confirmation:
            raise ValueError(f"explicit {expected_confirmation} confirmation is required")
        if not expected_confirmation and confirmation is not None:
            raise ValueError("this serverless lifecycle phase does not accept confirmation text")

        if operation == "build-artifact":
            if not source_commit or not re.fullmatch(r"[a-fA-F0-9]{40}", source_commit):
                raise ValueError("artifact build requires a full immutable source commit")
            try:
                repository_name = self.public_github.repository_name(repository_url)
                response = httpx.get(
                    f"https://api.github.com/repos/{repository_name}/commits/{source_commit}",
                    headers=self.public_github._headers(),
                    timeout=10,
                )
                response.raise_for_status()
                verified_commit = str(response.json().get("sha") or "").lower()
            except (HTTPError, ValueError) as error:
                raise ValueError(
                    "the pinned source commit is not readable from the connected public repository"
                ) from error
            if verified_commit != source_commit.lower():
                raise ValueError("GitHub did not verify the requested source commit")
        else:
            if source_commit is not None:
                raise ValueError(
                    "follow-on phases inherit the commit from their prior artifact run"
                )
            source_commit = str(prior_environment.get("DAVDEPLOY_CUSTOMER_SOURCE_COMMIT") or "")
            if not re.fullmatch(r"[a-f0-9]{40}", source_commit):
                raise ValueError("prior artifact run has no verified immutable source commit")

        artifact_uri = (
            f"{prefix}artifacts/{content_digest}/{prior.id}/lambda.zip"
            if prior and operation != "build-artifact"
            else ""
        )
        artifact_sha256 = str(prior_environment.get("DAVDEPLOY_SERVERLESS_ARTIFACT_SHA256") or "")
        if operation == "plan":
            artifact_uri = str(prior_detail.get("artifact_s3_uri") or "")
            artifact_sha256 = str(prior_detail.get("artifact_sha256") or "")
        elif operation in {
            "apply-saved-plan",
            "health",
            "destroy-plan",
            "destroy-saved-plan",
            "verify-cleanup",
        }:
            artifact_uri = str(prior_environment.get("DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI") or "")
            artifact_sha256 = str(
                prior_environment.get("DAVDEPLOY_SERVERLESS_ARTIFACT_SHA256") or ""
            )
        if operation != "build-artifact" and (
            not artifact_uri.startswith(f"{prefix}artifacts/{content_digest}/")
            or not re.fullmatch(r"[a-f0-9]{64}", artifact_sha256)
        ):
            raise ValueError("prior phase has no valid project-scoped Lambda artifact")

        plan_kind = (
            "destroy"
            if operation in {"destroy-plan", "destroy-saved-plan", "verify-cleanup"}
            else "apply"
        )
        saved_plan_uri = (
            f"{digest_prefix}{plan_kind}/{prior.id}.tfplan"
            if operation in {"apply-saved-plan", "health", "destroy-saved-plan", "verify-cleanup"}
            and prior
            else f"{digest_prefix}{plan_kind}/pending.tfplan"
        )
        saved_plan_sha256 = ""
        if operation in {
            "apply-saved-plan",
            "health",
            "destroy-saved-plan",
        }:
            saved_plan_uri = str(
                prior_environment.get("DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI") or ""
            )
            saved_plan_sha256 = str(
                prior_detail.get("saved_plan_sha256")
                or prior_environment.get("DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256")
                or ""
            )
        elif operation == "verify-cleanup":
            # The cleanup probe requires a syntactically valid apply-plan URI
            # but never downloads or executes this artifact.
            saved_plan_uri = f"{digest_prefix}apply/{prior.id}.tfplan"

        operation_script = {
            "build-artifact": "build-artifact",
            "plan": "plan",
            "apply-saved-plan": "apply-saved-plan",
            "health": "health",
            "destroy-plan": "destroy-plan",
            "destroy-saved-plan": "destroy-saved-plan",
            "verify-cleanup": "verify-cleanup",
        }[operation]
        bucket_base = f"davdeploy/customer/{connection.id}/runs/"
        run = CloudExecutionRun(
            organization_id=principal.organization_id,
            revision_id=revision.id,
            project_id=project_id,
            profile="aws-serverless-api",
            state="READY_FOR_OPERATOR_SERVERLESS_CERTIFICATION",
            mode="AUTHENTICATED_SERVERLESS_CERTIFICATION",
            attempt=1,
            command={
                "operation": operation_script,
                "prior_run_id": prior.id if prior else None,
                "universal_lifecycle_work": [
                    {
                        "module_id": "aws-serverless-api",
                        "operation": {
                            "build-artifact": "build_artifact",
                            "plan": "plan",
                            "apply-saved-plan": "apply",
                            "health": "observe",
                            "destroy-plan": "destroy_plan",
                            "destroy-saved-plan": "destroy",
                            "verify-cleanup": "verify_cleanup",
                        }[operation],
                        "dependencies": [],
                        "resource_tags": {
                            "ManagedBy": "davdeploy",
                            "WorkspaceId": principal.organization_id,
                            "ProjectId": project_id,
                            "PlanDigest": content_digest,
                        },
                    }
                ],
            },
            evidence={},
            outputs={"status": "not_executed", "resources_created": []},
            content_digest=content_digest,
            requested_by_subject=principal.subject,
        )
        self.db.add(run)
        self.db.flush()
        if operation == "build-artifact":
            artifact_uri = f"{prefix}artifacts/{content_digest}/{run.id}/lambda.zip"
        if operation in {"plan", "destroy-plan"}:
            saved_plan_uri = f"{digest_prefix}{plan_kind}/{run.id}.tfplan"
        environment = {
            "AWS_REGION": region,
            "EXPECTED_AWS_ACCOUNT_ID": account_id,
            "TF_STATE_BUCKET": bucket,
            "TF_LOCK_TABLE": lock_table,
            "DAVDEPLOY_CUSTOMER_CONNECTION_ID": connection.id,
            "DAVDEPLOY_CUSTOMER_PROJECT_ID": project_id,
            "DAVDEPLOY_CUSTOMER_EXECUTION_ROLE_ARN": connection.execution_role_arn,
            "DAVDEPLOY_EXTERNAL_ID_SECRET_ARN": connection.external_id_secret_ref,
            "DAVDEPLOY_EXECUTION_ARTIFACT_S3_URI": executor_artifact_uri,
            "DAVDEPLOY_EXECUTION_OPERATION": operation_script,
            "DAVDEPLOY_EXECUTION_RUN_ID": run.id,
            "DAVDEPLOY_EXECUTION_RESULT_S3_URI": f"s3://{bucket}/{bucket_base}{run.id}/result.json",
            "DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI": saved_plan_uri,
            "DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256": saved_plan_sha256,
            "DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI": artifact_uri,
            "DAVDEPLOY_SERVERLESS_ARTIFACT_SHA256": artifact_sha256,
            "DAVDEPLOY_CUSTOMER_PLAN_DIGEST": content_digest,
            "DAVDEPLOY_CUSTOMER_SOURCE_REPOSITORY": repository_url,
            "DAVDEPLOY_CUSTOMER_SOURCE_COMMIT": source_commit.lower(),
        }
        run.evidence = {
            "result_s3_uri": environment["DAVDEPLOY_EXECUTION_RESULT_S3_URI"],
            "execution_environment": environment,
            "prior_run_id": prior.id if prior else None,
            "boundary": "One fixed Lambda/API certification phase runs against the approved revision and verified customer connection.",
        }
        self.db.add(
            CloudExecutionModuleInstance(
                organization_id=principal.organization_id,
                project_id=project_id,
                execution_run_id=run.id,
                instance_id="aws-serverless-api",
                module_id="aws-serverless-api",
                state="NOT_DISPATCHED",
                operation="destroy"
                if operation in {"destroy-plan", "destroy-saved-plan", "verify-cleanup"}
                else "apply",
                attempt=0,
                input_digest=content_digest,
                idempotency_key=f"{run.id}:aws-serverless-api",
                dependencies=[],
                outputs={},
                evidence={
                    "reason": "single typed certification phase persisted; dispatch awaits confirmation"
                },
                version=1,
            )
        )
        self.audit(
            principal,
            "cloud_execution.serverless_certification_requested",
            "cloud_execution_run",
            run.id,
            {
                "revision_id": revision.id,
                "digest": content_digest,
                "operation": operation_script,
                "prior_run_id": prior.id if prior else None,
            },
        )
        self.db.commit()
        return self._cloud_execution_run_payload(run)

    def create_cloud_execution_run_for_revision(
        self,
        principal: Principal,
        revision_id: str,
        *,
        content_digest: str,
        terraform_render_id: str | None,
        preflight_id: str | None,
        terraform_plan_review_id: str | None,
        expected_account_id: str | None,
        expected_region: str | None,
        mode: str,
        confirmation: str | None,
        serverless_operation: str | None = None,
        prior_run_id: str | None = None,
        source_commit: str | None = None,
    ) -> dict[str, Any]:
        """Record a guarded App Runner execution run request.

        Default/local mode cannot mutate AWS. Authenticated execution remains
        gated by explicit process environment and request confirmation.
        """
        if not self._is_workspace_administrator(principal):
            raise PermissionError("only a workspace administrator can request cloud execution")
        if mode == "AUTHENTICATED_SERVERLESS_CERTIFICATION":
            return self._create_serverless_certification_run(
                principal,
                revision_id,
                content_digest=content_digest,
                operation=serverless_operation,
                prior_run_id=prior_run_id,
                source_commit=source_commit,
                expected_account_id=expected_account_id,
                expected_region=expected_region,
                confirmation=confirmation,
            )
        if serverless_operation or prior_run_id or source_commit:
            raise ValueError("serverless lifecycle fields require certification mode")
        if mode == "AUTHENTICATED_APP_RUNNER_IMAGE_BUILD":
            raise ValueError("use the governed customer-image-build endpoint for image delivery")
        revision, infrastructure_plan, _ = self._approved_customer_revision(principal, revision_id)
        if (
            revision.content_digest != content_digest
            or plan_hash(revision.content) != content_digest
        ):
            raise ValueError("stale cloud execution request: approved digest changed")
        module_payload = revision.content.get("architecture", {}).get("modules", [])
        try:
            universal_plan = compile_universal_execution_plan(
                [ArchitectureModule.model_validate(module) for module in module_payload],
                workspace_id=principal.organization_id,
                project_id=infrastructure_plan.project_id,
                plan_digest=revision.content_digest,
            )
        except (TypeError, ValueError) as error:
            raise ValueError(
                "approved revision has an invalid universal execution graph"
            ) from error
        profile_name = revision.content.get("summary", {}).get("selected_profile")
        if profile_name != "aws-app-runner":
            raise ValueError(
                "cloud execution run currently supports approved aws-app-runner plans only"
            )

        render = self._latest_execution_dependency(
            TerraformPlanRender,
            principal.organization_id,
            revision.id,
            revision.content_digest,
            terraform_render_id,
        )
        preflight = self._latest_execution_dependency(
            CloudReadinessPreflight,
            principal.organization_id,
            revision.id,
            revision.content_digest,
            preflight_id,
        )
        plan_review = self._latest_execution_dependency(
            TerraformPlanReview,
            principal.organization_id,
            revision.id,
            revision.content_digest,
            terraform_plan_review_id,
        )

        blockers: list[str] = []
        state = "BLOCKED_CLOUD_EXECUTION_NOT_ENABLED"
        render_inputs = render.render.get("module_inputs", {}) if render else {}
        account_id = render_inputs.get("aws_account_id")
        region = render_inputs.get("aws_region")
        if render is None:
            blockers.append("Generate an App Runner Terraform contract first.")
            state = "BLOCKED_TERRAFORM_CONTRACT_REQUIRED"
        if preflight is None:
            blockers.append("Run cloud-readiness preflight first.")
            state = "BLOCKED_PREFLIGHT_REQUIRED"
        elif preflight.state != "READY_FOR_AUTHORIZED_CLOUD_PLAN":
            blockers.append(f"Cloud-readiness preflight is {preflight.state}.")
            state = "BLOCKED_PREFLIGHT"
        destroy_mode = mode == "AUTHENTICATED_APP_RUNNER_DESTROY"
        expected_review_state = (
            "AUTHENTICATED_DESTROY_PLAN_REVIEWED" if destroy_mode else "AUTHENTICATED_PLAN_REVIEWED"
        )
        if plan_review is None:
            blockers.append("Record Terraform plan-only review first.")
            state = "BLOCKED_TERRAFORM_PLAN_REVIEW_REQUIRED"
        elif plan_review.state not in (
            {expected_review_state}
            if destroy_mode
            else {"LOCAL_CONTRACT_PLAN_REVIEWED", "AUTHENTICATED_PLAN_REVIEWED"}
        ):
            blockers.append(f"Terraform plan review is {plan_review.state}.")
            state = "BLOCKED_TERRAFORM_PLAN_REVIEW"
        if expected_account_id and account_id not in {
            expected_account_id,
            "customer-account-selected-at-apply-time",
        }:
            blockers.append(
                f"Expected AWS account {expected_account_id}; render targets {account_id}."
            )
            state = "BLOCKED_ACCOUNT_GUARD"
        if expected_region and region != expected_region:
            blockers.append(f"Expected AWS region {expected_region}; render targets {region}.")
            state = "BLOCKED_REGION_GUARD"

        cloud_apply_env = os.getenv("ALLOW_CLOUD_APPLY", "").lower() == "true"
        runtime_enabled = os.getenv("DAVDEPLOY_ENABLE_APP_RUNNER_EXECUTION", "").lower() == "true"
        confirmation_ok = confirmation == (
            "DESTROY_APP_RUNNER_WORKLOAD" if destroy_mode else "EXECUTE_APP_RUNNER_WORKLOAD"
        )
        connection_id = str((revision.content.get("target") or {}).get("connection_id") or "")
        connection: CloudConnection | None = None
        if mode in {"AUTHENTICATED_APP_RUNNER_APPLY", "AUTHENTICATED_APP_RUNNER_DESTROY"}:
            if not connection_id:
                blockers.append(
                    "Authenticated execution requires a verified customer cloud connection."
                )
                state = "BLOCKED_CLOUD_CONNECTION_REQUIRED"
            else:
                connection = self._cloud_connection(principal, connection_id)
                if connection.setup_state != "VERIFIED":
                    blockers.append("Selected customer cloud connection is not verified.")
                    state = "BLOCKED_CLOUD_CONNECTION_NOT_VERIFIED"
                if not connection.execution_role_arn:
                    blockers.append(
                        "Selected customer cloud connection has no bounded execution role."
                    )
                    state = "BLOCKED_CLOUD_EXECUTION_ROLE_REQUIRED"
                if account_id in {None, "customer-account-selected-at-apply-time"}:
                    account_id = connection.account_id
                if connection.account_id and account_id != connection.account_id:
                    blockers.append(
                        "Terraform contract account does not match the verified customer connection."
                    )
                    state = "BLOCKED_ACCOUNT_GUARD"
                real_plan_artifact = (
                    (plan_review.evidence or {}).get("real_plan_artifact") if plan_review else {}
                ) or {}
                if not real_plan_artifact.get("saved_plan_s3_uri") or not real_plan_artifact.get(
                    "saved_plan_sha256"
                ):
                    blockers.append(
                        "Authenticated execution requires a reviewed saved Terraform plan artifact."
                    )
                    state = "BLOCKED_TERRAFORM_PLAN_ARTIFACT_REQUIRED"
        execution_environment: dict[str, str] = {}
        if connection and connection.execution_role_arn and connection.external_id_secret_ref:
            image_build: CloudExecutionRun | None = None
            if mode == "AUTHENTICATED_APP_RUNNER_APPLY":
                image_build = self.db.scalar(
                    select(CloudExecutionRun)
                    .where(
                        CloudExecutionRun.organization_id == principal.organization_id,
                        CloudExecutionRun.revision_id == revision.id,
                        CloudExecutionRun.content_digest == revision.content_digest,
                        CloudExecutionRun.mode == "AUTHENTICATED_APP_RUNNER_IMAGE_BUILD",
                        CloudExecutionRun.state == "IMAGE_BUILT_AWAITING_SERVICE_PLAN",
                    )
                    .order_by(CloudExecutionRun.created_at.desc())
                    .limit(1)
                )
            image_identifier = ""
            if image_build:
                image_identifier = str(
                    ((image_build.outputs or {}).get("image_build") or {}).get("image_identifier")
                    or ""
                )
            execution_environment = {
                "AWS_REGION": str(region or ""),
                "EXPECTED_AWS_ACCOUNT_ID": str(account_id or ""),
                "TF_STATE_BUCKET": os.getenv("DAVDEPLOY_CUSTOMER_EXECUTION_STATE_BUCKET", ""),
                "TF_LOCK_TABLE": os.getenv("DAVDEPLOY_CUSTOMER_EXECUTION_LOCK_TABLE", ""),
                "DAVDEPLOY_CUSTOMER_CONNECTION_ID": connection.id,
                "DAVDEPLOY_CUSTOMER_EXECUTION_ROLE_ARN": connection.execution_role_arn,
                "DAVDEPLOY_EXTERNAL_ID_SECRET_ARN": connection.external_id_secret_ref,
                "DAVDEPLOY_CUSTOMER_APP_RUNNER_ECR_ROLE_ARN": (
                    f"arn:aws:iam::{account_id}:role/davdeployAppRunnerEcr-{connection.id}"
                ),
                "DAVDEPLOY_CUSTOMER_APP_RUNNER_RUNTIME_ROLE_ARN": (
                    f"arn:aws:iam::{account_id}:role/davdeployAppRunnerRuntime-{connection.id}"
                ),
                "DAVDEPLOY_EXECUTION_ARTIFACT_S3_URI": os.getenv(
                    "DAVDEPLOY_CUSTOMER_EXECUTION_ARTIFACT_S3_URI", ""
                ),
                "DAVDEPLOY_EXECUTION_OPERATION": "destroy-saved-plan"
                if destroy_mode
                else "apply-saved-plan",
                "DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI": str(
                    real_plan_artifact.get("saved_plan_s3_uri")
                    if mode
                    in {"AUTHENTICATED_APP_RUNNER_APPLY", "AUTHENTICATED_APP_RUNNER_DESTROY"}
                    else ""
                ),
                "DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256": str(
                    real_plan_artifact.get("saved_plan_sha256")
                    if mode
                    in {"AUTHENTICATED_APP_RUNNER_APPLY", "AUTHENTICATED_APP_RUNNER_DESTROY"}
                    else ""
                ),
                "DAVDEPLOY_CUSTOMER_PLAN_DIGEST": revision.content_digest,
                "DAVDEPLOY_CUSTOMER_APP_RUNNER_SERVICE_NAME": f"davdeploy-{connection.id[:8]}-workload",
            }
            if image_identifier:
                execution_environment.update(
                    {
                        "DAVDEPLOY_CUSTOMER_IMAGE_IDENTIFIER": image_identifier,
                        "DAVDEPLOY_ENABLE_CUSTOMER_SERVICE": "true",
                    }
                )
            required_runner_values = (
                "AWS_REGION",
                "EXPECTED_AWS_ACCOUNT_ID",
                "TF_STATE_BUCKET",
                "TF_LOCK_TABLE",
                "DAVDEPLOY_EXECUTION_ARTIFACT_S3_URI",
            )
            if not all(execution_environment[key] for key in required_runner_values):
                blockers.append("Customer execution runner configuration is incomplete.")
                state = "BLOCKED_CLOUD_EXECUTION_RUNTIME_NOT_CONFIGURED"
        if mode in {"AUTHENTICATED_APP_RUNNER_APPLY", "AUTHENTICATED_APP_RUNNER_DESTROY"}:
            if not cloud_apply_env or not runtime_enabled or not confirmation_ok:
                blockers.append(
                    "Authenticated App Runner execution requires ALLOW_CLOUD_APPLY=true, "
                    "DAVDEPLOY_ENABLE_APP_RUNNER_EXECUTION=true and the exact operation confirmation."
                )
                state = "BLOCKED_CLOUD_EXECUTION_NOT_ENABLED"
            elif not blockers:
                state = "READY_FOR_OPERATOR_APP_RUNNER_EXECUTION"
        elif not blockers:
            blockers.append(
                "Local/default mode records execution history only; cloud apply is disabled."
            )
            state = "BLOCKED_CLOUD_EXECUTION_NOT_ENABLED"

        previous = self.db.scalar(
            select(CloudExecutionRun)
            .where(
                CloudExecutionRun.organization_id == principal.organization_id,
                CloudExecutionRun.revision_id == revision.id,
            )
            .order_by(CloudExecutionRun.attempt.desc())
            .limit(1)
        )
        attempt_number = 1 if not previous else previous.attempt + 1
        lifecycle_operation = "destroy" if destroy_mode else "apply"
        command = {
            "profile": "aws-app-runner",
            "terraform_root": "infrastructure/terraform/customer-workload-app-runner-pilot",
            "script": "scripts/customer-workload-app-runner-pilot.sh",
            "steps": [
                "plan",
                "apply-foundation",
                "build-push-image",
                "apply-service",
                "wait-ready",
                "smoke",
                "destroy",
                "verify-absent",
            ],
            "apply_command_available": state == "READY_FOR_OPERATOR_APP_RUNNER_EXECUTION"
            and not destroy_mode,
            "destroy_command_available": state == "READY_FOR_OPERATOR_APP_RUNNER_EXECUTION"
            and destroy_mode,
            "destroy_required": True,
            "universal_lifecycle_work": list(lifecycle_work(universal_plan, lifecycle_operation)),
        }
        evidence = {
            "revision_id": revision.id,
            "digest": revision.content_digest,
            "profile": "aws-app-runner",
            "terraform_render_id": render.id if render else None,
            "preflight_id": preflight.id if preflight else None,
            "terraform_plan_review_id": plan_review.id if plan_review else None,
            "aws_account_id": account_id,
            "aws_region": region,
            "mode": mode,
            "runtime_enabled": runtime_enabled,
            "allow_cloud_apply_env": cloud_apply_env,
            "confirmation_ok": confirmation_ok,
            "operation": "destroy" if destroy_mode else "apply",
            "cloud_connection_id": connection_id or None,
            "execution_role_configured": bool(connection and connection.execution_role_arn),
            "execution_environment": execution_environment,
            "universal_execution": {
                "plan_digest": universal_plan.plan_digest,
                "operation": lifecycle_operation,
                "work": list(lifecycle_work(universal_plan, lifecycle_operation)),
                "modules": [
                    {
                        "id": module.instance_id,
                        "instance_id": module.instance_id,
                        "module_id": module.module_id,
                        "dependencies": list(module.dependencies),
                        "input_bindings": [
                            {
                                "input_name": input_name,
                                "source_instance_id": source_instance_id,
                                "source_output": source_output,
                            }
                            for input_name, source_instance_id, source_output in module.input_bindings
                        ],
                        "operations": list(module.operations),
                        "resource_tags": dict(module.resource_tags),
                    }
                    for module in universal_plan.modules
                ],
            },
            "blockers": blockers,
            "boundary": (
                "This run records a guarded execution request. It does not deploy unless the "
                "explicit cloud-apply gates are enabled and an operator proceeds with the "
                "App Runner execution profile."
            ),
        }
        run = CloudExecutionRun(
            organization_id=principal.organization_id,
            revision_id=revision.id,
            project_id=infrastructure_plan.project_id,
            terraform_render_id=render.id if render else None,
            preflight_id=preflight.id if preflight else None,
            terraform_plan_review_id=plan_review.id if plan_review else None,
            profile="aws-app-runner",
            state=state,
            mode=mode,
            attempt=attempt_number,
            command=command,
            evidence=evidence,
            outputs={"status": "not_executed", "resources_created": []},
            content_digest=revision.content_digest,
            requested_by_subject=principal.subject,
        )
        self.db.add(run)
        self.db.flush()
        if execution_environment:
            # Do not mutate the JSON value already assigned to the ORM row in
            # place. SQLAlchemy may not mark a nested JSON mutation dirty, and
            # the worker must receive these generated values after a restart.
            execution_environment = {
                **execution_environment,
                "DAVDEPLOY_EXECUTION_RUN_ID": run.id,
                "DAVDEPLOY_EXECUTION_RESULT_S3_URI": (
                    f"s3://{execution_environment['TF_STATE_BUCKET']}/davdeploy/customer/"
                    f"{execution_environment['DAVDEPLOY_CUSTOMER_CONNECTION_ID']}/runs/{run.id}/result.json"
                ),
            }
            run.evidence = {
                **run.evidence,
                "execution_environment": execution_environment,
                # Reconciliation deliberately reads this durable, top-level
                # immutable artifact location rather than trusting a later
                # worker environment reconstruction.
                "result_s3_uri": execution_environment["DAVDEPLOY_EXECUTION_RESULT_S3_URI"],
            }
        # Persist the approved typed graph as owner-scoped module-instance rows
        # at run creation. A queued or blocked run is not evidence that any node
        # was dispatched or applied.
        lifecycle_operation = "destroy" if destroy_mode else "apply"
        for module in universal_plan.modules:
            self.db.add(
                CloudExecutionModuleInstance(
                    organization_id=principal.organization_id,
                    project_id=infrastructure_plan.project_id,
                    execution_run_id=run.id,
                    instance_id=module.instance_id,
                    module_id=module.module_id,
                    state="NOT_DISPATCHED",
                    operation=lifecycle_operation,
                    attempt=0,
                    input_digest=universal_plan.plan_digest,
                    idempotency_key=f"{run.id}:{module.instance_id}",
                    dependencies=list(module.dependencies),
                    outputs={},
                    evidence={"reason": "run graph persisted; module dispatch is not enabled"},
                    version=1,
                )
            )
        self.audit(
            principal,
            "cloud_execution.run_requested",
            "cloud_execution_run",
            run.id,
            {
                "revision_id": revision.id,
                "digest": revision.content_digest,
                "state": state,
                "attempt": attempt_number,
                "profile": "aws-app-runner",
            },
        )
        self.db.commit()
        self._wake_worker("cloud_execution", run.id)
        return self._cloud_execution_run_payload(run)

    @staticmethod
    def _terraform_output_value(outputs: object, name: str) -> str:
        """Extract one non-secret Terraform output from a runner result artifact."""
        if not isinstance(outputs, dict):
            return ""
        value = outputs.get(name)
        if isinstance(value, dict):
            value = value.get("value")
        return value if isinstance(value, str) else ""

    def create_customer_image_build_for_revision(
        self,
        principal: Principal,
        revision_id: str,
        *,
        content_digest: str,
        expected_account_id: str | None,
        expected_region: str | None,
        confirmation: str | None,
    ) -> dict[str, Any]:
        """Queue a bounded, commit-pinned public repository image build.

        This deliberately does not create or update an App Runner service. The
        resulting image digest is evidence for a separate Terraform service plan.
        """
        if not self._is_workspace_administrator(principal):
            raise PermissionError("only a workspace administrator can build customer images")
        revision, infrastructure_plan, _ = self._approved_customer_revision(principal, revision_id)
        if (
            revision.content_digest != content_digest
            or plan_hash(revision.content) != content_digest
        ):
            raise ValueError("stale customer image build request: approved digest changed")
        content = revision.content
        application = content.get("application_analysis") or {}
        target = content.get("target") or {}
        repository_url = str(application.get("repository") or "")
        branch = str(application.get("branch") or "")
        connection_id = str(target.get("connection_id") or "")
        if not repository_url or not branch:
            raise ValueError("approved plan has no selected repository and branch")
        if not connection_id:
            raise ValueError(
                "authenticated image build requires a verified customer cloud connection"
            )
        connection = self._cloud_connection(principal, connection_id)
        if connection.setup_state != "VERIFIED" or not connection.execution_role_arn:
            raise ValueError(
                "selected customer cloud connection is not verified for bounded execution"
            )
        if expected_account_id and connection.account_id != expected_account_id:
            raise ValueError("expected AWS account does not match the verified customer connection")
        region = str(target.get("region") or connection.region or "")
        if expected_region and region != expected_region:
            raise ValueError("expected AWS region does not match the approved plan")
        if not region:
            raise ValueError("approved plan has no target region")
        if confirmation != "BUILD_CUSTOMER_IMAGE":
            raise ValueError("explicit BUILD_CUSTOMER_IMAGE confirmation is required")
        if (
            os.getenv("ALLOW_CLOUD_APPLY", "").lower() != "true"
            or os.getenv("DAVDEPLOY_ENABLE_APP_RUNNER_EXECUTION", "").lower() != "true"
        ):
            raise ValueError("customer image build runtime is disabled")

        repository_connection = self.db.scalar(
            select(RepositoryConnection).where(
                RepositoryConnection.organization_id == principal.organization_id,
                RepositoryConnection.project_id == infrastructure_plan.project_id,
                RepositoryConnection.repository_url == repository_url,
            )
        )
        if repository_connection is None or (
            repository_connection.selected_branch
            and repository_connection.selected_branch != branch
        ):
            raise ValueError("selected repository is no longer connected to the approved project")
        try:
            repository_name = self.public_github.repository_name(repository_url)
            response = httpx.get(
                f"https://api.github.com/repos/{repository_name}/commits/{branch}",
                headers=self.public_github._headers(),
                timeout=10,
            )
            response.raise_for_status()
            source_commit = str(response.json().get("sha") or "")
        except (HTTPError, ValueError) as error:
            raise ValueError(
                "the current bounded image builder supports a readable public GitHub repository; "
                "private GitHub archive delivery must be configured before use"
            ) from error
        if len(source_commit) != 40 or any(
            character not in "0123456789abcdef" for character in source_commit.lower()
        ):
            raise ValueError("GitHub did not return a valid immutable source commit")

        foundation = self.db.scalar(
            select(CloudExecutionRun)
            .where(
                CloudExecutionRun.organization_id == principal.organization_id,
                CloudExecutionRun.revision_id == revision.id,
                CloudExecutionRun.mode == "AUTHENTICATED_APP_RUNNER_APPLY",
                CloudExecutionRun.state == "SUCCEEDED_AWAITING_OBSERVATION",
            )
            .order_by(CloudExecutionRun.created_at.desc())
            .limit(1)
        )
        ecr_repository_url = self._terraform_output_value(
            (foundation.outputs or {}).get("terraform_outputs") if foundation else None,
            "ecr_repository_url",
        )
        if not ecr_repository_url:
            raise ValueError("a successful customer foundation with an ECR output is required")
        bucket = os.getenv("DAVDEPLOY_CUSTOMER_EXECUTION_STATE_BUCKET", "")
        lock_table = os.getenv("DAVDEPLOY_CUSTOMER_EXECUTION_LOCK_TABLE", "")
        artifact_uri = os.getenv("DAVDEPLOY_CUSTOMER_EXECUTION_ARTIFACT_S3_URI", "")
        if (
            not bucket
            or not lock_table
            or not artifact_uri
            or not connection.external_id_secret_ref
        ):
            raise ValueError("customer image build runner configuration is incomplete")
        previous = self.db.scalar(
            select(CloudExecutionRun)
            .where(
                CloudExecutionRun.organization_id == principal.organization_id,
                CloudExecutionRun.revision_id == revision.id,
            )
            .order_by(CloudExecutionRun.attempt.desc())
            .limit(1)
        )
        run = CloudExecutionRun(
            organization_id=principal.organization_id,
            revision_id=revision.id,
            project_id=infrastructure_plan.project_id,
            profile="aws-app-runner",
            state="READY_FOR_OPERATOR_APP_RUNNER_EXECUTION",
            mode="AUTHENTICATED_APP_RUNNER_IMAGE_BUILD",
            attempt=1 if not previous else previous.attempt + 1,
            command={"operation": "build-push-image", "source": "approved-repository-commit"},
            evidence={},
            outputs={"status": "submitting", "resources_created": []},
            content_digest=revision.content_digest,
            requested_by_subject=principal.subject,
        )
        self.db.add(run)
        self.db.flush()
        environment = {
            "AWS_REGION": region,
            "EXPECTED_AWS_ACCOUNT_ID": str(connection.account_id),
            "TF_STATE_BUCKET": bucket,
            "TF_LOCK_TABLE": lock_table,
            "DAVDEPLOY_CUSTOMER_CONNECTION_ID": connection.id,
            "DAVDEPLOY_CUSTOMER_EXECUTION_ROLE_ARN": connection.execution_role_arn,
            "DAVDEPLOY_EXTERNAL_ID_SECRET_ARN": connection.external_id_secret_ref,
            "DAVDEPLOY_CUSTOMER_APP_RUNNER_ECR_ROLE_ARN": f"arn:aws:iam::{connection.account_id}:role/davdeployAppRunnerEcr-{connection.id}",
            "DAVDEPLOY_CUSTOMER_APP_RUNNER_RUNTIME_ROLE_ARN": f"arn:aws:iam::{connection.account_id}:role/davdeployAppRunnerRuntime-{connection.id}",
            "DAVDEPLOY_EXECUTION_ARTIFACT_S3_URI": artifact_uri,
            "DAVDEPLOY_EXECUTION_OPERATION": "build-push-image",
            "DAVDEPLOY_EXECUTION_RUN_ID": run.id,
            "DAVDEPLOY_EXECUTION_RESULT_S3_URI": f"s3://{bucket}/davdeploy/customer/{connection.id}/runs/{run.id}/result.json",
            "DAVDEPLOY_CUSTOMER_PLAN_DIGEST": revision.content_digest,
            "DAVDEPLOY_CUSTOMER_SOURCE_REPOSITORY": repository_url,
            "DAVDEPLOY_CUSTOMER_SOURCE_COMMIT": source_commit,
            "DAVDEPLOY_CUSTOMER_ECR_REPOSITORY_URL": ecr_repository_url,
            "DAVDEPLOY_CUSTOMER_IMAGE_TAG": f"sha-{source_commit}",
        }
        run.evidence = {
            "result_s3_uri": environment["DAVDEPLOY_EXECUTION_RESULT_S3_URI"],
            "execution_environment": environment,
            "source": {"repository": repository_url, "branch": branch, "commit": source_commit},
            "foundation_run_id": foundation.id,
            "boundary": "The runner may build and push one pinned repository commit to the connection-scoped ECR repository. It cannot create an App Runner service.",
        }
        self.audit(
            principal,
            "cloud_execution.image_build_requested",
            "cloud_execution_run",
            run.id,
            {
                "revision_id": revision.id,
                "digest": revision.content_digest,
                "source_commit": source_commit,
            },
        )
        self.db.commit()
        return self._cloud_execution_run_payload(run)

    def queue_cloud_execution_run(
        self,
        principal: Principal,
        run_id: str,
        content_digest: str,
        confirmation: str,
    ) -> dict[str, Any]:
        """Queue an already-ready run; the trusted worker performs execution."""
        if not self._is_workspace_administrator(principal):
            raise PermissionError("only a workspace administrator can execute cloud runs")
        run = self.db.get(CloudExecutionRun, run_id)
        if not run or run.organization_id != principal.organization_id:
            raise PermissionError("cloud execution run not found in this organization")
        if run.content_digest != content_digest:
            raise ValueError("stale cloud execution run digest")
        if run.state not in {
            "READY_FOR_OPERATOR_APP_RUNNER_EXECUTION",
            "READY_FOR_OPERATOR_SERVERLESS_CERTIFICATION",
        }:
            raise ValueError(f"cloud execution run is not ready: {run.state}")
        if (
            run.mode == "AUTHENTICATED_SERVERLESS_CERTIFICATION"
            and run.profile != "aws-serverless-api"
        ):
            raise ValueError("serverless certification mode requires its matching renderer")
        expected_confirmation = (
            "RUN_SERVERLESS_CERTIFICATION_PHASE"
            if run.mode == "AUTHENTICATED_SERVERLESS_CERTIFICATION"
            else {
                "AUTHENTICATED_APP_RUNNER_DESTROY": "DESTROY_APP_RUNNER_WORKLOAD",
                "AUTHENTICATED_APP_RUNNER_IMAGE_BUILD": "BUILD_CUSTOMER_IMAGE",
            }.get(run.mode, "EXECUTE_APP_RUNNER_WORKLOAD")
        )
        if confirmation != expected_confirmation:
            raise ValueError("explicit confirmation for this cloud execution run is required")
        run.state = "QUEUED"
        work = (run.command or {}).get("universal_lifecycle_work")
        if run.module_instances and isinstance(work, list):
            next_item = next_dispatchable_work_item(
                work, {item.instance_id: item.state for item in run.module_instances}
            )
            if next_item is None:
                raise ValueError("cloud execution graph has no dependency-ready module")
            self._advance_cloud_execution_module_instances(
                run,
                module_outcomes={
                    str(next_item["instance_id"]): ModuleLifecycleOutcome(state="QUEUED")
                },
            )
        else:
            self._advance_cloud_execution_module_instances(run, "QUEUED")
        run.evidence = {
            **(run.evidence or {}),
            "queued_by_subject": principal.subject,
            "queue_confirmation": expected_confirmation,
            "boundary": (
                "Queued for the fixed renderer selected by the persisted run profile and mode; "
                "no user-supplied command is accepted."
            ),
        }
        self.audit(
            principal,
            "cloud_execution.queued",
            "cloud_execution_run",
            run.id,
            {"digest": run.content_digest, "profile": run.profile},
        )
        self.db.commit()
        # A run is created before an administrator gives the final execution
        # confirmation. Wake again only after that durable state transition so
        # the bounded worker can claim the newly queued run without polling.
        self._wake_worker("cloud_execution", run.id)
        return self._cloud_execution_run_payload(run)

    def run_next_cloud_execution(self) -> bool:
        """Claim and process one queued run without permitting duplicate owners."""
        self._scan_expired_cloud_execution_leases()
        claim = self._claim_next_cloud_execution_run()
        if claim is None:
            return False
        run, lease_token = claim
        work = (run.command or {}).get("universal_lifecycle_work")
        selected_instance_id: str | None = None
        resolved_module_inputs: dict[str, str] = {}
        if run.module_instances and isinstance(work, list):
            selected = next_dispatchable_work_item(
                work, {item.instance_id: item.state for item in run.module_instances}
            )
            if selected is None:
                self._mark_cloud_execution_reconciliation_required(
                    run.id, lease_token, "no dependency-ready module remained for a queued run"
                )
                return True
            selected_instance_id = str(selected["instance_id"])
            try:
                resolved_module_inputs = validate_module_inputs(
                    str(selected["module_id"]),
                    resolve_lifecycle_work_inputs(
                        work,
                        selected_instance_id,
                        {item.instance_id: item.outputs or {} for item in run.module_instances},
                        {item.instance_id: item.state for item in run.module_instances},
                        plan_digest=run.content_digest,
                    ),
                )
            except (TypeError, ValueError):
                run.state = "BLOCKED_MODULE_INPUTS_UNSUPPORTED"
                run.worker_lease_token = None
                run.worker_lease_expires_at = None
                run.evidence = {
                    **(run.evidence or {}),
                    "blocked_module_instance_id": selected_instance_id,
                    "failure_reason": "typed dependency inputs failed validation",
                }
                self.audit(
                    Principal("system-cloud-worker", run.organization_id, "operator"),
                    "cloud_execution.module_inputs_blocked",
                    "cloud_execution_run",
                    run.id,
                    {
                        "module_instance_id": selected_instance_id,
                        "input_names": sorted(
                            str(binding["input_name"]) for binding in selected["input_bindings"]
                        ),
                    },
                )
                self.db.commit()
                return True
            self._advance_cloud_execution_module_instances(
                run,
                module_outcomes={selected_instance_id: ModuleLifecycleOutcome(state="RUNNING")},
            )
            run.evidence = {
                **(run.evidence or {}),
                "active_module_instance_id": selected_instance_id,
            }
        else:
            self._advance_cloud_execution_module_instances(run, "RUNNING")
        self.db.commit()
        context = {
            "run_id": run.id,
            "profile": run.profile,
            "mode": run.mode,
            "digest": run.content_digest,
            "environment": (run.evidence or {}).get("execution_environment", {}),
            "lifecycle_work": (run.command or {}).get("universal_lifecycle_work"),
            "dispatch_instance_id": selected_instance_id,
            "resolved_module_inputs": resolved_module_inputs,
        }
        heartbeat_stop = threading.Event()
        heartbeat = threading.Thread(
            target=self._renew_cloud_execution_lease,
            args=(run.id, lease_token, heartbeat_stop),
            daemon=True,
            name=f"davdeploy-cloud-run-lease-{run.id[:8]}",
        )
        heartbeat.start()
        try:
            result = self.cloud_execution.execute(context)
        except Exception as error:  # noqa: BLE001 - adapter may already have side effects
            self._mark_cloud_execution_reconciliation_required(
                run.id, lease_token, f"adapter raised {type(error).__name__}"
            )
            return True
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=CLOUD_EXECUTION_WORKER_HEARTBEAT_SECONDS + 1)
        self._complete_cloud_execution_claim(run.id, lease_token, result)
        return True

    def _claim_next_cloud_execution_run(
        self,
    ) -> tuple[CloudExecutionRun, str] | None:
        """Atomically move one queued run to RUNNING and assign an unguessable lease."""
        candidate = self.db.scalar(
            select(CloudExecutionRun)
            .where(CloudExecutionRun.state == "QUEUED")
            .order_by(CloudExecutionRun.created_at, CloudExecutionRun.id)
            .limit(1)
        )
        if candidate is None:
            return None
        now = datetime.now(UTC)
        lease_token = secrets.token_hex(32)
        claimed = self.db.execute(
            update(CloudExecutionRun)
            .where(
                CloudExecutionRun.id == candidate.id,
                CloudExecutionRun.organization_id == candidate.organization_id,
                CloudExecutionRun.project_id == candidate.project_id,
                CloudExecutionRun.content_digest == candidate.content_digest,
                CloudExecutionRun.state == "QUEUED",
                CloudExecutionRun.worker_claim_version == candidate.worker_claim_version,
            )
            .values(
                state="RUNNING",
                worker_claim_version=CloudExecutionRun.worker_claim_version + 1,
                worker_lease_token=lease_token,
                worker_lease_expires_at=now
                + timedelta(seconds=CLOUD_EXECUTION_WORKER_LEASE_SECONDS),
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            self.db.rollback()
            return None
        self.db.commit()
        run = self.db.scalar(
            select(CloudExecutionRun)
            .where(CloudExecutionRun.id == candidate.id)
            .execution_options(populate_existing=True)
        )
        return (run, lease_token) if run is not None else None

    def _renew_cloud_execution_lease(
        self, run_id: str, lease_token: str, stop: threading.Event
    ) -> None:
        """Extend a live claim using an independent database session."""
        interval = CLOUD_EXECUTION_WORKER_HEARTBEAT_SECONDS
        bind = self.db.get_bind()
        while not stop.wait(interval):
            now = datetime.now(UTC)
            with Session(bind=bind) as heartbeat_db:
                renewed = heartbeat_db.execute(
                    update(CloudExecutionRun)
                    .where(
                        CloudExecutionRun.id == run_id,
                        CloudExecutionRun.state == "RUNNING",
                        CloudExecutionRun.worker_lease_token == lease_token,
                        CloudExecutionRun.worker_lease_expires_at > now,
                    )
                    .values(
                        worker_lease_expires_at=now
                        + timedelta(seconds=CLOUD_EXECUTION_WORKER_LEASE_SECONDS),
                        updated_at=now,
                    )
                    .execution_options(synchronize_session=False)
                )
                heartbeat_db.commit()
            if renewed.rowcount != 1:
                return

    def _scan_expired_cloud_execution_leases(self) -> None:
        """Flag expired claims for reconciliation without replaying external work."""
        global _last_cloud_execution_lease_scan
        scan_now = time.monotonic()
        with _cloud_execution_lease_scan_lock:
            if scan_now - _last_cloud_execution_lease_scan < CLOUD_EXECUTION_LEASE_SCAN_SECONDS:
                return
            _last_cloud_execution_lease_scan = scan_now

        now = datetime.now(UTC)
        # Do not infer abandonment for pre-lease RUNNING records. They may still
        # be owned by an older worker during a rolling deploy.
        expired = list(
            self.db.scalars(
                select(CloudExecutionRun).where(
                    CloudExecutionRun.state == "RUNNING",
                    CloudExecutionRun.worker_lease_token.is_not(None),
                    CloudExecutionRun.worker_lease_expires_at <= now,
                )
            )
        )
        for run in expired:
            old_token = run.worker_lease_token
            changed = self.db.execute(
                update(CloudExecutionRun)
                .where(
                    CloudExecutionRun.id == run.id,
                    CloudExecutionRun.state == "RUNNING",
                    CloudExecutionRun.worker_lease_token == old_token,
                    CloudExecutionRun.worker_lease_expires_at <= now,
                )
                .values(
                    state="RECONCILIATION_REQUIRED",
                    worker_lease_token=None,
                    worker_lease_expires_at=None,
                    updated_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            if changed.rowcount != 1:
                continue
            run.state = "RECONCILIATION_REQUIRED"
            run.worker_lease_token = None
            run.worker_lease_expires_at = None
            run.evidence = {
                **(run.evidence or {}),
                "worker_reconciliation": {
                    "reason": "worker lease expired before a durable outcome was recorded",
                    "detected_at": now.isoformat(),
                    "previous_lease_token_sha256": hashlib.sha256(
                        str(old_token).encode()
                    ).hexdigest(),
                    "automatic_replay": False,
                },
            }
            active_instance_id = (run.evidence or {}).get("active_module_instance_id")
            if active_instance_id and any(
                item.instance_id == active_instance_id for item in run.module_instances
            ):
                self._advance_cloud_execution_module_instances(
                    run,
                    module_outcomes={
                        str(active_instance_id): ModuleLifecycleOutcome(
                            state="RECONCILIATION_REQUIRED"
                        )
                    },
                )
            else:
                self._advance_cloud_execution_module_instances(run, "RECONCILIATION_REQUIRED")
            self.audit(
                Principal("system-cloud-worker", run.organization_id, "operator"),
                "cloud_execution.lease_expired_reconciliation_required",
                "cloud_execution_run",
                run.id,
                {"automatic_replay": False, "digest": run.content_digest},
            )
        if expired:
            self.db.commit()

    def _mark_cloud_execution_reconciliation_required(
        self, run_id: str, lease_token: str, reason: str
    ) -> None:
        run = self.db.scalar(
            select(CloudExecutionRun)
            .where(
                CloudExecutionRun.id == run_id,
                CloudExecutionRun.state == "RUNNING",
                CloudExecutionRun.worker_lease_token == lease_token,
            )
            .execution_options(populate_existing=True)
        )
        if run is None:
            self.db.rollback()
            return
        run.state = "RECONCILIATION_REQUIRED"
        run.worker_lease_token = None
        run.worker_lease_expires_at = None
        run.evidence = {
            **(run.evidence or {}),
            "worker_reconciliation": {
                "reason": reason,
                "detected_at": datetime.now(UTC).isoformat(),
                "automatic_replay": False,
            },
        }
        active_instance_id = (run.evidence or {}).get("active_module_instance_id")
        if active_instance_id and any(
            item.instance_id == active_instance_id for item in run.module_instances
        ):
            self._advance_cloud_execution_module_instances(
                run,
                module_outcomes={
                    str(active_instance_id): ModuleLifecycleOutcome(state="RECONCILIATION_REQUIRED")
                },
            )
        else:
            self._advance_cloud_execution_module_instances(run, "RECONCILIATION_REQUIRED")
        self.audit(
            Principal("system-cloud-worker", run.organization_id, "operator"),
            "cloud_execution.adapter_outcome_uncertain",
            "cloud_execution_run",
            run.id,
            {"automatic_replay": False},
        )
        self.db.commit()

    def _complete_cloud_execution_claim(self, run_id: str, lease_token: str, result) -> bool:
        now = datetime.now(UTC)
        updated = self.db.execute(
            update(CloudExecutionRun)
            .where(
                CloudExecutionRun.id == run_id,
                CloudExecutionRun.state == "RUNNING",
                CloudExecutionRun.worker_lease_token == lease_token,
                CloudExecutionRun.worker_lease_expires_at > now,
            )
            .values(
                state=result.state,
                worker_lease_token=None,
                worker_lease_expires_at=None,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        if updated.rowcount != 1:
            self.db.rollback()
            return False
        run = self.db.scalar(
            select(CloudExecutionRun)
            .where(CloudExecutionRun.id == run_id)
            .execution_options(populate_existing=True)
        )
        if run is None:
            self.db.rollback()
            return False
        raw_build_id = (result.outputs or {}).get("codebuild_build_id")
        raw_build_arn = (result.outputs or {}).get("codebuild_build_arn")
        active_instance_id = (run.evidence or {}).get("active_module_instance_id")
        target_instance = next(
            (item for item in run.module_instances if item.instance_id == active_instance_id),
            None,
        )
        if target_instance is None and len(run.module_instances) == 1:
            target_instance = run.module_instances[0]
        if raw_build_id is not None:
            build_id = str(raw_build_id).rsplit("/", 1)[-1]
            if (
                not build_id
                or len(build_id) > 255
                or re.fullmatch(r"[A-Za-z0-9._:-]+", build_id) is None
            ):
                self.db.rollback()
                return False
            if raw_build_arn is not None and str(raw_build_arn).rsplit("/", 1)[-1] != build_id:
                self.db.rollback()
                return False
            if len(run.module_instances) > 1 and target_instance is None:
                self.db.rollback()
                return False
            if target_instance is not None:
                if target_instance.runner_build_id not in {None, build_id}:
                    self.db.rollback()
                    return False
                target_instance.runner_build_id = build_id
                target_instance.evidence = {
                    **(target_instance.evidence or {}),
                    "runner_build_id": build_id,
                }
        run.state = result.state
        run.worker_lease_token = None
        run.worker_lease_expires_at = None
        if target_instance is not None:
            self._advance_cloud_execution_module_instances(
                run,
                module_outcomes={
                    target_instance.instance_id: ModuleLifecycleOutcome(state=result.state)
                },
            )
        elif run.module_instances:
            # Older single-renderer rows may not have stored an active instance
            # identity. Preserve compatibility only when the target is unique.
            if len(run.module_instances) != 1:
                self.db.rollback()
                return False
            self._advance_cloud_execution_module_instances(run, result.state)
        run.outputs = {
            **(run.outputs or {}),
            **result.outputs,
            "operations": list(result.operations),
            "failure_reason": result.failure_reason,
        }
        run.evidence = {
            **(run.evidence or {}),
            "observed_by": "trusted-cloud-execution-worker",
            "observed_state": result.state,
        }
        self.audit(
            Principal("system-cloud-worker", run.organization_id, "operator"),
            "cloud_execution.observed",
            "cloud_execution_run",
            run.id,
            {"state": result.state, "failure_reason": result.failure_reason},
        )
        self.db.commit()
        return True

    def _advance_cloud_execution_module_instances(
        self,
        run: CloudExecutionRun,
        state: str | None = None,
        *,
        module_outcomes: Mapping[str, ModuleLifecycleOutcome] | None = None,
    ) -> None:
        """Persist scoped run or per-module outcomes with optimistic locking."""
        allowed_targets = {
            "QUEUED",
            "SUBMITTED",
            "RUNNING",
            "FAILED",
            "BLOCKED_CLOUD_EXECUTION_NOT_ENABLED",
            "SUCCEEDED_AWAITING_OBSERVATION",
            "PLAN_READY_FOR_REVIEW",
            "DESTROY_PLAN_READY_FOR_REVIEW",
            "HEALTHY",
            "DESTROYED_VERIFIED",
            "CLEANUP_VERIFIED",
            "ARTIFACT_READY",
            "IMAGE_BUILT_AWAITING_SERVICE_PLAN",
            "RECONCILIATION_REQUIRED",
        }
        if (state is None) == (module_outcomes is None):
            raise ValueError("provide either one run state or per-module outcomes")
        if state is not None:
            if state not in allowed_targets:
                raise ValueError("cloud worker returned an unsupported module-instance state")
            outcomes = {
                item.instance_id: ModuleLifecycleOutcome(state=state)
                for item in run.module_instances
            }
        else:
            if not module_outcomes:
                raise ValueError("per-module outcomes are required")
            instance_ids = {item.instance_id for item in run.module_instances}
            if not set(module_outcomes).issubset(instance_ids):
                raise ValueError("module outcome is outside its execution run graph")
            outcomes = dict(module_outcomes)
            module_ids = {item.instance_id: item.module_id for item in run.module_instances}
            for instance_id, outcome in outcomes.items():
                if not isinstance(instance_id, str) or not isinstance(
                    outcome, ModuleLifecycleOutcome
                ):
                    raise TypeError("module outcome has an invalid shape")
                if outcome.state not in allowed_targets:
                    raise ValueError("module outcome has an unsupported state")
                if outcome.outputs is not None:
                    validate_module_outputs(module_ids[instance_id], dict(outcome.outputs))
                try:
                    if outcome.outputs is not None:
                        json.dumps(dict(outcome.outputs), sort_keys=True)
                    if outcome.evidence is not None:
                        json.dumps(dict(outcome.evidence), sort_keys=True)
                except (TypeError, ValueError) as error:
                    raise ValueError("module outcome must contain JSON-safe data") from error
        allowed_sources = {
            "NOT_DISPATCHED": {
                "QUEUED",
                "SUBMITTED",
                "RUNNING",
                "FAILED",
                "BLOCKED_CLOUD_EXECUTION_NOT_ENABLED",
                "RECONCILIATION_REQUIRED",
            },
            "QUEUED": {
                "SUBMITTED",
                "RUNNING",
                "FAILED",
                "BLOCKED_CLOUD_EXECUTION_NOT_ENABLED",
                "RECONCILIATION_REQUIRED",
            },
            "SUBMITTED": {"RUNNING", *allowed_targets - {"QUEUED", "SUBMITTED", "RUNNING"}},
            "RUNNING": allowed_targets - {"QUEUED", "RUNNING"},
        }
        now = datetime.now(UTC).isoformat()
        for item in run.module_instances:
            if (
                item.execution_run_id != run.id
                or item.organization_id != run.organization_id
                or item.project_id != run.project_id
                or item.input_digest != run.content_digest
            ):
                raise ValueError("module instance is outside its execution run scope")
            outcome = outcomes.get(item.instance_id)
            if outcome is None:
                continue
            if item.state == outcome.state:
                same_outputs = outcome.outputs is None or dict(outcome.outputs) == (
                    item.outputs or {}
                )
                same_evidence = outcome.evidence is None or dict(outcome.evidence) == (
                    (item.evidence or {}).get("module_outcome", {})
                )
                if same_outputs and same_evidence:
                    continue
                raise ValueError("module outcome cannot overwrite an existing result")
            if (
                item.state not in allowed_sources
                or outcome.state not in allowed_sources[item.state]
            ):
                raise ValueError("module instance state cannot be replayed or overwritten")
            event = {
                "from": item.state,
                "to": outcome.state,
                "run_id": run.id,
                "recorded_at": now,
            }
            evidence = {**(item.evidence or {})}
            if outcome.evidence is not None:
                evidence["module_outcome"] = dict(outcome.evidence)
            evidence["transitions"] = [*evidence.get("transitions", []), event]
            values = {
                "state": outcome.state,
                "attempt": item.attempt + (1 if outcome.state == "RUNNING" else 0),
                "version": item.version + 1,
                "evidence": evidence,
                "updated_at": datetime.now(UTC),
            }
            if outcome.outputs is not None:
                values["outputs"] = dict(outcome.outputs)
            result = self.db.execute(
                update(CloudExecutionModuleInstance)
                .where(
                    CloudExecutionModuleInstance.id == item.id,
                    CloudExecutionModuleInstance.execution_run_id == run.id,
                    CloudExecutionModuleInstance.organization_id == run.organization_id,
                    CloudExecutionModuleInstance.project_id == run.project_id,
                    CloudExecutionModuleInstance.input_digest == run.content_digest,
                    CloudExecutionModuleInstance.state == item.state,
                    CloudExecutionModuleInstance.version == item.version,
                )
                .values(**values)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                raise ValueError("module instance changed concurrently; refusing stale outcome")
            item.state = outcome.state
            item.attempt += 1 if outcome.state == "RUNNING" else 0
            item.version += 1
            item.evidence = evidence
            if outcome.outputs is not None:
                item.outputs = dict(outcome.outputs)

    def _schedule_next_cloud_execution_module(self, run: CloudExecutionRun) -> str | None:
        """Queue one dependency-ready instance, or fail closed on unresolved inputs."""
        work = (run.command or {}).get("universal_lifecycle_work")
        if not isinstance(work, list) or len(run.module_instances) <= 1:
            return None
        next_item = next_dispatchable_work_item(
            work, {item.instance_id: item.state for item in run.module_instances}
        )
        if next_item is None:
            return None
        instance_id = str(next_item["instance_id"])
        self._advance_cloud_execution_module_instances(
            run,
            module_outcomes={instance_id: ModuleLifecycleOutcome(state="QUEUED")},
        )
        run.state = "QUEUED"
        run.evidence = {
            **(run.evidence or {}),
            "next_module_instance_id": instance_id,
        }
        return "queued"

    def reconcile_cloud_execution_build(self, build_id: str) -> bool:
        """Persist one CodeBuild completion received through the SQS event bridge."""
        normalized_build_id = build_id.rsplit("/", 1)[-1]
        linked_instances = list(
            self.db.scalars(
                select(CloudExecutionModuleInstance).where(
                    CloudExecutionModuleInstance.runner_build_id == normalized_build_id
                )
            )
        )
        if len(linked_instances) > 1:
            return False
        linked_instance = linked_instances[0] if linked_instances else None
        run = (
            self.db.get(CloudExecutionRun, linked_instance.execution_run_id)
            if linked_instance is not None
            else next(
                (
                    item
                    for item in self.db.scalars(
                        select(CloudExecutionRun).where(
                            CloudExecutionRun.state.in_(("SUBMITTED", "FAILED"))
                        )
                    )
                    # A failed execution is replayable only when the exact bounded
                    # CodeBuild job succeeded but artifact decryption/reading failed.
                    # Other failures must remain immutable and require a new run.
                    if item.state == "SUBMITTED"
                    or (item.outputs or {}).get("failure_reason")
                    == "runner result artifact URI is missing"
                    if normalized_build_id == (item.outputs or {}).get("codebuild_build_id")
                    or build_id == (item.outputs or {}).get("codebuild_build_arn")
                ),
                None,
            )
        )
        if not run:
            return False
        if linked_instance is not None and (
            linked_instance.execution_run_id != run.id
            or linked_instance.organization_id != run.organization_id
            or linked_instance.project_id != run.project_id
            or linked_instance.input_digest != run.content_digest
            or linked_instance.runner_build_id != normalized_build_id
        ):
            return False
        if run.state not in {"SUBMITTED", "FAILED"}:
            return False
        if run.state == "FAILED" and (run.outputs or {}).get("failure_reason") != (
            "runner result artifact URI is missing"
        ):
            return False
        if linked_instance is not None and linked_instance.state != "SUBMITTED":
            return False
        if linked_instance is not None and (
            (run.outputs or {}).get("codebuild_build_id")
            and (run.outputs or {}).get("codebuild_build_id") != normalized_build_id
        ):
            return False
        response = boto3.client("codebuild").batch_get_builds(ids=[normalized_build_id])
        builds = response.get("builds") or []
        if not builds:
            return False
        build = builds[0]
        status = str(build.get("buildStatus") or "IN_PROGRESS")
        if status in {"IN_PROGRESS", "QUEUED"}:
            return False
        artifact: dict[str, Any] = {}
        typed_module_outputs: dict[str, str] | None = None
        artifact_error: str | None = None
        evidence = run.evidence or {}
        # Runs created before ticket147 stored the generated URI only inside
        # the durable execution context. Accept that generated legacy value,
        # while preferring the current explicit reconciliation field.
        result_uri = str(
            evidence.get("result_s3_uri")
            or (evidence.get("execution_environment") or {}).get(
                "DAVDEPLOY_EXECUTION_RESULT_S3_URI"
            )
            or ""
        )
        if status == "SUCCEEDED":
            try:
                if not result_uri.startswith("s3://"):
                    raise ValueError("runner result artifact URI is missing")
                bucket, key = result_uri[5:].split("/", 1)
                payload = boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
                artifact = json.loads(payload.decode("utf-8"))
                if (
                    not isinstance(artifact, dict)
                    or artifact.get("run_id") != run.id
                    or artifact.get("status") != "SUCCEEDED"
                ):
                    raise ValueError("runner result artifact does not match the execution run")
                if run.profile == "aws-serverless-api":
                    environment = evidence.get("execution_environment")
                    command = run.command or {}
                    if not isinstance(environment, dict) or not isinstance(command, dict):
                        raise ValueError("serverless run context is malformed")
                    expected_connection = str(
                        environment.get("DAVDEPLOY_CUSTOMER_CONNECTION_ID") or ""
                    )
                    expected_project = str(environment.get("DAVDEPLOY_CUSTOMER_PROJECT_ID") or "")
                    expected_phase = {
                        "build-artifact": "artifact-build",
                        "plan": "plan",
                        "destroy-plan": "destroy-plan",
                        "apply-saved-plan": "apply",
                        "health": "health",
                        "destroy-saved-plan": "destroy",
                        "verify-cleanup": "verify-cleanup",
                    }.get(str(environment.get("DAVDEPLOY_EXECUTION_OPERATION") or ""))
                    if (
                        artifact.get("schema_version") != "davdeploy.customer_execution_result.v1"
                        or not re.fullmatch(r"[a-f0-9]{64}", run.content_digest)
                        or artifact.get("plan_digest") != run.content_digest
                        or not expected_connection
                        or artifact.get("connection_id") != expected_connection
                        or not expected_project
                        or artifact.get("project_id") != expected_project
                        or not expected_phase
                        or artifact.get("phase") != expected_phase
                        or command.get("operation")
                        != environment.get("DAVDEPLOY_EXECUTION_OPERATION")
                        or not isinstance(artifact.get("detail"), dict)
                    ):
                        raise ValueError(
                            "serverless result does not match the approved run, connection, digest, and operation"
                        )
                    detail = artifact["detail"]
                    artifact_digest = str(detail.get("artifact_sha256") or "")
                    expected_artifact_uri = str(
                        environment.get("DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI") or ""
                    )
                    expected_source_commit = str(
                        environment.get("DAVDEPLOY_CUSTOMER_SOURCE_COMMIT") or ""
                    )
                    if expected_phase == "artifact-build" and (
                        detail.get("artifact_s3_uri") != expected_artifact_uri
                        or not re.fullmatch(r"[a-f0-9]{64}", artifact_digest)
                        or not re.fullmatch(r"[a-f0-9]{40}", expected_source_commit)
                        or detail.get("source_commit") != expected_source_commit
                    ):
                        raise ValueError("serverless artifact result is incomplete or mismatched")
                    if expected_phase in {"plan", "destroy-plan"} and (
                        detail.get("saved_plan_s3_uri")
                        != environment.get("DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI")
                        or not re.fullmatch(
                            r"[a-f0-9]{64}", str(detail.get("saved_plan_sha256") or "")
                        )
                        or not isinstance(detail.get("plan_summary"), dict)
                        or not re.fullmatch(r"[a-f0-9]{64}", artifact_digest)
                        or artifact_digest
                        != environment.get("DAVDEPLOY_SERVERLESS_ARTIFACT_SHA256")
                    ):
                        raise ValueError("serverless saved-plan result is incomplete or mismatched")
                    if expected_phase == "apply" and (
                        not re.fullmatch(
                            r"[a-f0-9]{64}", str(detail.get("saved_plan_sha256") or "")
                        )
                        or detail.get("saved_plan_sha256")
                        != environment.get("DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256")
                        or not re.fullmatch(r"[a-f0-9]{64}", artifact_digest)
                        or artifact_digest
                        != environment.get("DAVDEPLOY_SERVERLESS_ARTIFACT_SHA256")
                        or not isinstance(detail.get("outputs"), dict)
                    ):
                        raise ValueError("serverless apply result is incomplete")
                    if expected_phase == "apply":
                        typed_module_outputs = normalize_renderer_outputs(
                            "aws-serverless-api", detail["outputs"]
                        )
                    if expected_phase == "health" and (
                        not isinstance(detail.get("endpoint"), str)
                        or not detail["endpoint"].startswith("https://")
                        or not isinstance(detail.get("response"), str)
                    ):
                        raise ValueError("serverless health result is incomplete")
                    if expected_phase == "health":
                        prior_apply = self.db.scalar(
                            select(CloudExecutionRun)
                            .where(
                                CloudExecutionRun.organization_id == run.organization_id,
                                CloudExecutionRun.revision_id == run.revision_id,
                                CloudExecutionRun.profile == "aws-serverless-api",
                                CloudExecutionRun.state == "SUCCEEDED_AWAITING_OBSERVATION",
                                CloudExecutionRun.content_digest == run.content_digest,
                                CloudExecutionRun.id != run.id,
                            )
                            .order_by(CloudExecutionRun.created_at.desc())
                            .limit(1)
                        )
                        prior_outputs = (
                            ((prior_apply.outputs or {}).get("runner_artifact") or {})
                            .get("detail", {})
                            .get("outputs", {})
                            if prior_apply
                            else {}
                        )
                        applied_endpoint = prior_outputs.get("api_endpoint", {})
                        if isinstance(applied_endpoint, dict):
                            applied_endpoint = applied_endpoint.get("value")
                        if detail["endpoint"] != applied_endpoint:
                            raise ValueError(
                                "serverless health endpoint does not match the approved apply output"
                            )
                    if (
                        expected_phase in {"destroy", "verify-cleanup"}
                        and detail.get("cleanup") != "confirmed_absent"
                    ):
                        raise ValueError("serverless cleanup result did not confirm absence")
                    if expected_phase == "destroy" and detail.get(
                        "saved_plan_sha256"
                    ) != environment.get("DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256"):
                        raise ValueError(
                            "serverless destroy result does not match the approved plan"
                        )
            except (
                BotoCoreError,
                ClientError,
                UnicodeDecodeError,
                ValueError,
                json.JSONDecodeError,
            ) as error:
                # Artifact integrity failure must never become deployment success.
                artifact_error = str(error)
        if status != "SUCCEEDED" or artifact_error:
            run.state = "FAILED"
        elif run.mode in {
            "AUTHENTICATED_TERRAFORM_PLAN",
            "AUTHENTICATED_TERRAFORM_DESTROY_PLAN",
        }:
            review = self.db.get(TerraformPlanReview, run.terraform_plan_review_id)
            detail = artifact.get("detail") or {}
            if (
                not review
                or not detail.get("saved_plan_s3_uri")
                or not detail.get("saved_plan_sha256")
            ):
                run.state = "FAILED"
                artifact_error = (
                    "authenticated plan completion did not contain a saved plan artifact"
                )
            else:
                review.state = (
                    "AUTHENTICATED_DESTROY_PLAN_REVIEWED"
                    if run.mode == "AUTHENTICATED_TERRAFORM_DESTROY_PLAN"
                    else "AUTHENTICATED_PLAN_REVIEWED"
                )
                review.evidence = {
                    **(review.evidence or {}),
                    "real_plan_artifact": detail,
                    "runner_result_s3_uri": result_uri,
                    "reviewed_at": datetime.now(UTC).isoformat(),
                }
                run.state = review.state
        elif run.profile == "aws-serverless-api":
            phase = str(artifact.get("phase") or "")
            run.state = {
                "artifact-build": "ARTIFACT_READY",
                "plan": "PLAN_READY_FOR_REVIEW",
                "destroy-plan": "DESTROY_PLAN_READY_FOR_REVIEW",
                "apply": "SUCCEEDED_AWAITING_OBSERVATION",
                "health": "HEALTHY",
                "destroy": "DESTROYED_VERIFIED",
                "verify-cleanup": "CLEANUP_VERIFIED",
            }[phase]
        else:
            detail = artifact.get("detail") or {}
            if run.mode == "AUTHENTICATED_APP_RUNNER_DESTROY":
                run.state = (
                    "DESTROYED_VERIFIED"
                    if detail.get("destroy_proof") == "confirmed_absent"
                    else "FAILED"
                )
            elif run.mode == "AUTHENTICATED_APP_RUNNER_IMAGE_BUILD":
                run.state = (
                    "IMAGE_BUILT_AWAITING_SERVICE_PLAN"
                    if detail.get("image_identifier") and detail.get("source_commit")
                    else "FAILED"
                )
                if run.state == "FAILED":
                    artifact_error = (
                        "image build completion did not contain immutable image evidence"
                    )
            else:
                run.state = "SUCCEEDED_AWAITING_OBSERVATION"
        run.outputs = {
            **(run.outputs or {}),
            "codebuild_status": status,
            "codebuild_completed_at": str(build.get("buildComplete") or ""),
            "runner_artifact": (artifact or None) if artifact_error is None else None,
            "terraform_outputs": (artifact.get("detail") or {})
            if run.mode == "AUTHENTICATED_APP_RUNNER_APPLY"
            else (artifact.get("detail") or {}).get("outputs")
            if run.profile == "aws-serverless-api"
            and artifact.get("phase") == "apply"
            and artifact_error is None
            else None,
            "image_build": (artifact.get("detail") or {})
            if run.mode == "AUTHENTICATED_APP_RUNNER_IMAGE_BUILD"
            else None,
            "destroy_proof": (artifact.get("detail") or {}).get("destroy_proof")
            or (artifact.get("detail") or {}).get("cleanup"),
            "failure_reason": artifact_error
            or (None if status == "SUCCEEDED" else "Bounded CodeBuild runner failed."),
        }
        # A missing result object is the one replayable CodeBuild case. Keep
        # the graph node submitted until the exact same completed build can be
        # reconciled; do not make the provisional read failure terminal.
        should_wake_worker = False
        if artifact_error != "runner result artifact URI is missing":
            target_instance = linked_instance
            if (
                target_instance is None
                and len(run.module_instances) == 1
                and (run.outputs or {}).get("codebuild_build_id") == normalized_build_id
            ):
                # Legacy single-module runs can still bind the callback using
                # their unique run-level CodeBuild identity.
                target_instance = run.module_instances[0]
            if target_instance is None:
                # Compatibility for pre-migration single-renderer runs that
                # have only the old run-level build identity.
                self._advance_cloud_execution_module_instances(run, run.state)
            else:
                module_state = run.state
                if status == "SUCCEEDED" and artifact_error is None:
                    if run.mode == "AUTHENTICATED_TERRAFORM_PLAN":
                        module_state = "PLAN_READY_FOR_REVIEW"
                    elif run.mode == "AUTHENTICATED_TERRAFORM_DESTROY_PLAN":
                        module_state = "DESTROY_PLAN_READY_FOR_REVIEW"
                outcome = ModuleLifecycleOutcome(
                    state=module_state,
                    evidence={
                        "runner_build_id": normalized_build_id,
                        "runner_build_status": status,
                    },
                    outputs=typed_module_outputs,
                )
                self._advance_cloud_execution_module_instances(
                    run,
                    module_outcomes={target_instance.instance_id: outcome},
                )
                if status == "SUCCEEDED" and artifact_error is None:
                    should_wake_worker = self._schedule_next_cloud_execution_module(run) == "queued"
        self.audit(
            Principal("system-cloud-worker", run.organization_id, "operator"),
            "cloud_execution.codebuild_completed",
            "cloud_execution_run",
            run.id,
            {"build_id": build_id, "status": status},
        )
        self.db.commit()
        if should_wake_worker:
            self._wake_worker("cloud_execution", run.id)
        return True

    def reconcile_cloud_execution_run_result(
        self, principal: Principal, run_id: str
    ) -> dict[str, Any]:
        """Replay only a safely retryable completed CodeBuild result read."""
        if not self._is_workspace_administrator(principal):
            raise PermissionError("only a workspace administrator can reconcile cloud runs")
        run = self.db.get(CloudExecutionRun, run_id)
        if not run or run.organization_id != principal.organization_id:
            raise PermissionError("cloud execution run not found in this organization")
        if (run.outputs or {}).get("failure_reason") != "runner result artifact URI is missing":
            raise ValueError("cloud execution run is not eligible for result reconciliation")
        build_id = str((run.outputs or {}).get("codebuild_build_id") or "")
        if not build_id:
            raise ValueError("cloud execution run has no CodeBuild build identifier")
        if not self.reconcile_cloud_execution_build(build_id):
            raise ValueError("cloud execution result is not ready for reconciliation")
        refreshed = self.db.get(CloudExecutionRun, run_id)
        assert refreshed is not None
        self.audit(
            principal,
            "cloud_execution.result_reconciled",
            "cloud_execution_run",
            run_id,
            {"build_id": build_id, "state": refreshed.state},
        )
        self.db.commit()
        return self._cloud_execution_run_payload(refreshed)

    def _latest_execution_dependency(
        self,
        model: Any,
        organization_id: str,
        revision_id: str,
        content_digest: str,
        item_id: str | None,
    ) -> Any | None:
        query = select(model).where(
            model.organization_id == organization_id,
            model.revision_id == revision_id,
            model.content_digest == content_digest,
        )
        if item_id:
            query = query.where(model.id == item_id)
        return self.db.scalar(query.order_by(model.created_at.desc()).limit(1))

    @staticmethod
    def _cloud_execution_run_payload(run: CloudExecutionRun) -> dict[str, Any]:
        return {
            "id": run.id,
            "revision_id": run.revision_id,
            "project_id": run.project_id,
            "profile": run.profile,
            "state": run.state,
            "mode": run.mode,
            "attempt": run.attempt,
            "terraform_render_id": run.terraform_render_id,
            "preflight_id": run.preflight_id,
            "terraform_plan_review_id": run.terraform_plan_review_id,
            "command": run.command,
            "evidence": run.evidence,
            "outputs": run.outputs,
            "module_instances": [
                {
                    "project_id": item.project_id,
                    "instance_id": item.instance_id,
                    "module_id": item.module_id,
                    "state": item.state,
                    "operation": item.operation,
                    "attempt": item.attempt,
                    "input_digest": item.input_digest,
                    "dependencies": item.dependencies,
                    "outputs": item.outputs,
                    "evidence": item.evidence,
                    "version": item.version,
                }
                for item in run.module_instances
            ],
            "content_digest": run.content_digest,
            "requested_by_subject": run.requested_by_subject,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "execution": "CLOUD_EXECUTION_REQUEST_RECORD",
            "boundary": (
                "This is execution-history/governance evidence. It is not proof of AWS "
                "deployment unless a later run records observed AWS outputs/resources."
            ),
        }

    def cloud_execution_runs(self, principal: Principal) -> list[dict[str, Any]]:
        return [
            self._cloud_execution_run_payload(run)
            for run in self.db.scalars(
                select(CloudExecutionRun)
                .where(CloudExecutionRun.organization_id == principal.organization_id)
                .order_by(CloudExecutionRun.created_at.desc())
            )
        ]

    def cloud_execution_run_evidence(self, principal: Principal, run_id: str) -> dict[str, Any]:
        run = self.db.get(CloudExecutionRun, run_id)
        if not run or run.organization_id != principal.organization_id:
            raise PermissionError("cloud execution run not found in this organization")
        revision = self.db.get(InfrastructurePlanRevision, run.revision_id)
        if not revision or revision.organization_id != principal.organization_id:
            raise PermissionError("cloud execution revision not found in this organization")
        plan = self.db.get(InfrastructurePlan, revision.infrastructure_plan_id)
        if not plan or plan.organization_id != principal.organization_id:
            raise PermissionError("cloud execution plan not found in this organization")
        content = revision.content
        application = content.get("application_analysis", {})
        target = content.get("target", {})
        outputs = run.outputs or {}
        blockers = list((run.evidence or {}).get("blockers") or [])
        return {
            "kind": "davdeploy.cloud_execution_evidence.v1",
            "run": self._cloud_execution_run_payload(run),
            "project": {
                "id": plan.project_id,
                "title": plan.title,
                "creator_subject": plan.creator_subject,
            },
            "approved_plan": {
                "revision_id": revision.id,
                "revision": revision.revision_number,
                "digest": revision.content_digest,
                "state": revision.state,
                "submitted_by_subject": revision.submitted_by_subject,
                "submitted_at": revision.submitted_at.isoformat()
                if revision.submitted_at
                else None,
            },
            "source": {
                "repository": application.get("repository"),
                "branch": application.get("branch"),
                "commit": application.get("commit_sha") or "unresolved-local-fixture",
            },
            "target": {
                "provider": "aws",
                "account_id": target.get("account_id"),
                "region": target.get("region"),
                "profile": run.profile,
            },
            "terraform": {
                "render_id": run.terraform_render_id,
                "preflight_id": run.preflight_id,
                "plan_review_id": run.terraform_plan_review_id,
                "command": run.command,
                "state": run.state,
            },
            "observed": {
                "outputs": outputs,
                "resources": outputs.get("resources_created", []),
                "destroy_proof": outputs.get("destroy_proof") or "not_executed_no_destroy_proof",
                "failure_reason": "; ".join(blockers) if blockers else None,
            },
            "boundary": (
                "This evidence reflects davdeploy product records. It is not cloud execution "
                "proof unless the run contains observed AWS outputs/resources from an enabled apply path."
            ),
        }

    def cloud_role_contract(self, principal: Principal, connection_id: str) -> dict[str, str | int]:
        connection = self.db.get(CloudConnection, connection_id)
        if not connection or connection.organization_id != principal.organization_id:
            raise PermissionError("cloud connection not found in this organization")
        return self.cloud_discovery.role_contract(connection.id).__dict__ | {
            "execution": "SIMULATED"
        }

    def _project(self, principal: Principal, project_id: str) -> Project:
        project = self.db.get(Project, project_id)
        if not project or project.organization_id != principal.organization_id:
            raise PermissionError("project not found in this organization")
        return project

    @staticmethod
    def _generated_plan_ownership_scope(
        principal: Principal,
        project_id: str,
        plan_id: str,
        revision_id: str,
        environment_id: str | None,
    ) -> PlanOwnershipScope:
        """Bind plan tags to the currently authenticated tenant and revision."""
        # The current tenant model maps one workspace to the organization ID.
        return PlanOwnershipScope(
            organization_id=principal.organization_id,
            workspace_id=principal.organization_id,
            project_id=project_id,
            plan_id=plan_id,
            revision_id=revision_id,
            environment_id=environment_id,
        )

    def create_intent(
        self,
        principal: Principal,
        project_id: str,
        prompt: str,
        source_repository: str | None,
        cloud_connection_id: str | None,
        idempotency_key: str,
    ) -> WorkloadIntent:
        with self._trace("davdeploy.intent.interpret") as span:
            span.set_attribute("davdeploy.organization_id", principal.organization_id)
            return self._create_intent(
                principal,
                project_id,
                prompt,
                source_repository,
                cloud_connection_id,
                idempotency_key,
            )

    def _create_intent(
        self,
        principal: Principal,
        project_id: str,
        prompt: str,
        source_repository: str | None,
        cloud_connection_id: str | None,
        idempotency_key: str,
    ) -> WorkloadIntent:
        project = self._project(principal, project_id)
        if cloud_connection_id:
            connection = self.db.get(CloudConnection, cloud_connection_id)
            if not connection or connection.organization_id != principal.organization_id:
                raise PermissionError("cloud connection not found in this organization")
        existing = self.db.scalar(
            select(WorkloadIntent).where(
                WorkloadIntent.organization_id == principal.organization_id,
                WorkloadIntent.idempotency_key == idempotency_key,
            )
        )
        if existing:
            if existing.prompt != prompt or existing.project_id != project_id:
                raise ValueError("idempotency key conflicts with a different request")
            return existing
        selected_repository = source_repository or project.repository_url
        tenant = TenantScope(
            organization_id=principal.organization_id,
            workspace_id=principal.organization_id,
            project_id=project.id,
            actor_id=principal.subject,
        )
        interpretation = self.intent_provider.interpret(prompt, selected_repository, tenant)
        self._record_model_usage(principal, interpretation.model_metadata)
        spec = interpretation.spec
        repository_analysis = self.latest_repository_analysis(principal, project.id)
        spec_payload = spec.model_dump(mode="json")
        if repository_analysis:
            repository_runtime = self._runtime_from_repository(repository_analysis.analysis)
            spec_payload["repository_analysis"] = repository_analysis.analysis
            if repository_runtime and spec_payload.get("runtime") in {None, "containerized"}:
                spec_payload["runtime"] = repository_runtime
            spec_payload["containerized"] = bool(
                spec_payload.get("containerized")
                or "containerized" in repository_analysis.analysis.get("runtime_hints", [])
                or "Dockerfile" in repository_analysis.analysis.get("manifests", [])
            )
            if repository_analysis.analysis.get("database_hints"):
                spec_payload["stateful"] = True
                spec_payload["capability_requirements"] = sorted(
                    set(spec_payload.get("capability_requirements", [])) | {"relational_data"}
                )
            repository_capabilities = self._capabilities_from_repository_analysis(
                repository_analysis.analysis
            )
            if repository_capabilities:
                spec_payload["capability_requirements"] = sorted(
                    set(spec_payload.get("capability_requirements", [])) | repository_capabilities
                )
        state = LifecycleState.NEEDS_INPUT if spec.unknowns else LifecycleState.PLANNED
        intent = WorkloadIntent(
            organization_id=principal.organization_id,
            project_id=project.id,
            requester_subject=principal.subject,
            prompt=prompt,
            idempotency_key=idempotency_key,
            state=state,
            spec={
                **spec_payload,
                "cloud_connection_id": cloud_connection_id,
                "questions": [question.model_dump() for question in interpretation.questions],
                "model_metadata": interpretation.model_metadata,
            },
        )
        self.db.add(intent)
        self.db.flush()
        self.audit(
            principal,
            "intent.interpreted",
            "workload_intent",
            intent.id,
            {
                "state": state,
                "unknowns": spec.unknowns,
                "model_call": interpretation.model_metadata,
            },
        )
        self.db.commit()
        return intent

    def _record_model_usage(self, principal: Principal, metadata: dict[str, Any] | None) -> None:
        if not metadata:
            return
        usage = metadata.get("usage") or {}
        detail = {
            "request_id": metadata.get("request_id"),
            "provider": metadata.get("provider"),
            "model": metadata.get("model"),
            "prompt_version": metadata.get("prompt_version"),
        }
        for field in (
            "attempt_count",
            "retry_count",
            "latency_ms",
            "measured_at",
            "estimated_cost_usd",
            "failure",
            "evidence",
        ):
            if field in metadata:
                detail[field] = metadata[field]
        for metric, quantity in (
            ("model_calls", 1),
            ("model_input_tokens", int(usage.get("input_tokens") or 0)),
            ("model_output_tokens", int(usage.get("output_tokens") or 0)),
        ):
            self.db.add(
                UsageRecord(
                    organization_id=principal.organization_id,
                    metric=metric,
                    quantity=quantity,
                    source="model_gateway",
                    detail=detail,
                )
            )

    @staticmethod
    def _runtime_from_repository(analysis: dict[str, Any]) -> str | None:
        hints = analysis.get("framework_hints", []) + analysis.get("runtime_hints", [])
        if "fastapi" in hints:
            return "python-fastapi"
        if "django" in hints:
            return "python-django"
        if "next" in hints:
            return "node-nextjs"
        if "node" in hints:
            return "node"
        if "python" in hints:
            return "python"
        return None

    @staticmethod
    def _capabilities_from_repository_analysis(analysis: dict[str, Any]) -> set[str]:
        """Map safe repository hints to customer needs, never cloud-service choices."""

        hints = " ".join(
            str(item).lower()
            for field in ("framework_hints", "runtime_hints", "data_hints", "deployment_hints")
            for item in analysis.get(field, [])
        )
        capabilities: set[str] = set()
        if any(token in hints for token in ("postgres", "mysql", "prisma", "sqlalchemy")):
            capabilities.add("relational_data")
        if any(token in hints for token in ("redis", "dynamodb", "mongodb")):
            capabilities.add("nosql_data")
        if any(token in hints for token in ("websocket", "socket.io", "graphql")):
            capabilities.add("realtime")
        if any(token in hints for token in ("celery", "bull", "rq", "worker")):
            capabilities.add("jobs")
        return capabilities

    def _intent(self, principal: Principal, intent_id: str) -> WorkloadIntent:
        intent = self.db.get(WorkloadIntent, intent_id)
        if not intent or intent.organization_id != principal.organization_id:
            raise PermissionError("intent not found in this organization")
        return intent

    def plan_intent(self, principal: Principal, intent_id: str) -> DeploymentPlan:
        with self._trace("davdeploy.architecture.plan"):
            return self._plan_intent(principal, intent_id)

    def _plan_intent(self, principal: Principal, intent_id: str) -> DeploymentPlan:
        intent = self._intent(principal, intent_id)
        spec = WorkloadSpec.model_validate(intent.spec)
        if spec.unknowns:
            raise ValueError(f"missing material requirements: {', '.join(spec.unknowns)}")
        connection_id = str(intent.spec.get("cloud_connection_id") or "local-aws-fixture")
        requested_region = spec.region_constraints[0] if spec.region_constraints else "us-east-1"
        inventory = self._planning_inventory(principal, connection_id, requested_region)
        architecture = self.planner.plan(spec, inventory)
        stored = self.db.scalar(
            select(StoredArchitecturePlan).where(StoredArchitecturePlan.intent_id == intent.id)
        )
        if not stored:
            stored = StoredArchitecturePlan(
                organization_id=principal.organization_id,
                intent_id=intent.id,
                plan=architecture.model_dump(mode="json"),
            )
            self.db.add(stored)
        with self._trace("davdeploy.policy.evaluate"):
            decision = self.policy.evaluate(principal, spec, PlanAction.DEPLOY)
        payload = {
            "action": PlanAction.DEPLOY,
            "intent_id": intent.id,
            "cloud_connection_id": intent.spec.get("cloud_connection_id"),
            "spec": spec.model_dump(mode="json"),
            "architecture": architecture.model_dump(mode="json"),
            "inventory": inventory.model_dump(mode="json"),
            "policy": {"result": decision.result, "reason": decision.reason},
        }
        digest = plan_hash(payload)
        existing = self.db.scalar(select(DeploymentPlan).where(DeploymentPlan.plan_hash == digest))
        if existing:
            return existing
        state = {
            PolicyResult.ALLOW: LifecycleState.PLANNED,
            PolicyResult.DENY: LifecycleState.POLICY_DENIED,
            PolicyResult.APPROVAL_REQUIRED: LifecycleState.APPROVAL_REQUIRED,
        }[decision.result]
        plan = DeploymentPlan(
            organization_id=principal.organization_id,
            intent_id=intent.id,
            requester_subject=principal.subject,
            action=PlanAction.DEPLOY,
            state=state,
            plan_hash=digest,
            policy_result=decision.result,
            payload=payload,
        )
        self.db.add(plan)
        intent.state = state
        self.db.flush()
        self.audit(
            principal,
            "deployment_plan.created",
            "deployment_plan",
            plan.id,
            {"hash": digest, "policy": decision.result, "reason": decision.reason},
        )
        self.db.commit()
        return plan

    def _planning_inventory(
        self, principal: Principal, connection_id: str, requested_region: str
    ) -> CloudInventorySnapshot:
        """Use the freshest verified customer discovery evidence when a connection is selected.

        The planner does not call AWS from a browser request. It consumes a durable,
        tenant-scoped snapshot produced by the trusted discovery worker. Fixture
        discovery remains the explicit fallback for local planning without a connection.
        """
        if connection_id == "local-aws-fixture":
            return self.cloud_discovery.inventory(connection_id, requested_region)
        connection = self._cloud_connection(principal, connection_id)
        if connection.setup_state != "VERIFIED":
            raise ValueError("selected cloud connection must be verified before planning")
        snapshot = self.db.scalar(
            select(StoredCloudInventorySnapshot)
            .where(
                StoredCloudInventorySnapshot.organization_id == principal.organization_id,
                StoredCloudInventorySnapshot.cloud_connection_id == connection.id,
                StoredCloudInventorySnapshot.region == requested_region,
            )
            .order_by(StoredCloudInventorySnapshot.captured_at.desc())
            .limit(1)
        )
        if not snapshot:
            raise ValueError("selected cloud connection has no verified inventory for this region")
        return CloudInventorySnapshot.model_validate(snapshot.snapshot)

    def _plan(self, principal: Principal, plan_id: str) -> DeploymentPlan:
        plan = self.db.get(DeploymentPlan, plan_id)
        if not plan or plan.organization_id != principal.organization_id:
            raise PermissionError("deployment plan not found in this organization")
        return plan

    def get_plan(self, principal: Principal, plan_id: str) -> DeploymentPlan:
        return self._plan(principal, plan_id)

    def create_customer_plan_review(
        self, principal: Principal, deployment_plan_id: str
    ) -> InfrastructurePlanRevision:
        """Create the customer-facing DRAFT review from one validated AWS recommendation.

        The source deployment plan remains an execution contract. This separate business
        plan is intentionally DRAFT and cannot cause any cloud mutation.
        """
        deployment = self._plan(principal, deployment_plan_id)
        if deployment.action != PlanAction.DEPLOY:
            raise ValueError("only an AWS deployment recommendation can create a customer review")
        intent = self._intent(principal, str(deployment.intent_id))
        project = self._project(principal, intent.project_id)
        architecture = deployment.payload["architecture"]
        repository = self.db.scalar(
            select(RepositoryConnection).where(
                RepositoryConnection.organization_id == principal.organization_id,
                RepositoryConnection.project_id == project.id,
            )
        )
        repository_analysis = self.latest_repository_analysis(principal, project.id)
        connection_id = deployment.payload.get("cloud_connection_id")
        target: dict[str, Any] = {
            "provider": "aws",
            "region": architecture["region"],
            "connection_id": connection_id,
            "account_id": None,
            "connection_status": "local planning fixture" if not connection_id else "selected",
        }
        inventory_snapshot: dict[str, Any] | None = None
        if connection_id:
            connection = self._cloud_connection(principal, str(connection_id))
            target.update(
                {
                    "account_id": connection.account_id,
                    "connection_status": connection.setup_state,
                    "discovery_role": connection.discovery_role_arn,
                }
            )
            snapshot = self.db.scalar(
                select(StoredCloudInventorySnapshot)
                .where(
                    StoredCloudInventorySnapshot.organization_id == principal.organization_id,
                    StoredCloudInventorySnapshot.cloud_connection_id == connection.id,
                )
                .order_by(StoredCloudInventorySnapshot.captured_at.desc())
                .limit(1)
            )
            if snapshot:
                inventory_snapshot = {
                    "id": snapshot.id,
                    "captured_at": snapshot.captured_at.isoformat(),
                    "provenance": snapshot.provenance,
                    "resources": snapshot.snapshot.get("approved_resources", []),
                    "pricing_evidence": snapshot.snapshot.get("pricing_evidence"),
                }
        content = {
            "kind": "davdeploy.aws.infrastructure-plan.review.v1",
            "source_deployment_plan_id": deployment.id,
            "summary": {
                "selected_profile": architecture["profile"],
                "why": architecture["recommendation_reason"],
                "status": "DRAFT: review only; not submitted, approved, or deployed",
            },
            "application_analysis": {
                "project": project.name,
                "repository": project.repository_url,
                "branch": repository.selected_branch if repository else None,
                "request": intent.prompt,
                "repository_analysis": repository_analysis.analysis
                if repository_analysis
                else deployment.payload["spec"].get("repository_analysis", {}),
                "workload_spec": deployment.payload["spec"],
            },
            "target": target,
            "inventory_snapshot": inventory_snapshot,
            "architecture": {
                "components": architecture["components"],
                # This is an internal dependency graph, not a cloud-service
                # picker. It is preserved in the immutable customer revision
                # so an execution request can compile the exact approved
                # module set against that revision's digest.
                "modules": architecture.get("modules", []),
                "dependencies": architecture["dependencies"],
                "capacity": architecture["estimated_capacity"],
                "operational_characteristics": architecture["operational_characteristics"],
                "existing_resources_reused": architecture["existing_resources_reused"],
                "new_resources_required": architecture["new_resources_required"],
            },
            "resource_breakdown": architecture["components"],
            "security": deployment.payload["architecture"]["security_controls"],
            "observability": architecture["observability"],
            "cost_estimate": {
                "range": architecture["cost_estimate"],
                "components": architecture["cost_components"],
                "label": "Estimated monthly AWS cost; not an actual AWS bill.",
            },
            "deployment_strategy": {
                "steps": architecture["execution_steps"],
                "rollback": architecture["rollback_strategy"],
                "boundary": "Submission and approval make this review eligible for a later explicit execution action. This review does not deploy AWS infrastructure.",
            },
            "risks_and_limitations": architecture["risks"],
            "policy_findings": deployment.payload["policy"],
            "evidence": {
                "planner": "deterministic estimate; not an AWS bill",
                "cloud": "read-only discovery snapshot when one is selected; no deployment permission",
                "pricing": (
                    inventory_snapshot.get("pricing_evidence")
                    if inventory_snapshot
                    else {"state": "NOT_AVAILABLE_NO_CLOUD_CONNECTION"}
                ),
                "execution": "unexecuted customer plan review",
            },
        }
        drafts = self.db.scalars(
            select(InfrastructurePlanRevision)
            .where(
                InfrastructurePlanRevision.organization_id == principal.organization_id,
                InfrastructurePlanRevision.state == InfrastructurePlanState.DRAFT,
            )
            .order_by(InfrastructurePlanRevision.created_at.desc())
        ).all()
        existing = next(
            (
                draft
                for draft in drafts
                if draft.content.get("source_deployment_plan_id") == deployment.id
            ),
            None,
        )
        if existing is not None:
            return existing
        return self.create_infrastructure_plan(
            principal, project.id, f"AWS plan for {project.name}", content
        )

    def approve(self, principal: Principal, plan_id: str, provided_hash: str) -> DeploymentPlan:
        with self._trace("davdeploy.plan.approve"):
            return self._approve(principal, plan_id, provided_hash)

    def _approve(self, principal: Principal, plan_id: str, provided_hash: str) -> DeploymentPlan:
        plan = self._plan(principal, plan_id)
        if not self._is_workspace_administrator(principal):
            raise PermissionError("workspace administrator role required for approval")
        if plan.requester_subject == principal.subject:
            raise PermissionError("requester cannot approve their own protected plan")
        if plan.plan_hash != provided_hash:
            raise ValueError("stale approval: plan hash changed")
        if plan.state not in {
            LifecycleState.APPROVAL_REQUIRED,
            LifecycleState.DESTROY_APPROVAL_REQUIRED,
        }:
            raise ValueError("plan does not need approval")
        plan.state = LifecycleState.APPROVED
        self.db.add(
            Approval(
                deployment_plan_id=plan.id,
                plan_hash=plan.plan_hash,
                approver_subject=principal.subject,
            )
        )
        self.audit(
            principal,
            "deployment_plan.approved",
            "deployment_plan",
            plan.id,
            {"hash": plan.plan_hash},
        )
        self.db.commit()
        return plan

    def execute(self, principal: Principal, plan_id: str) -> list[Environment]:
        """Queue bounded work. A separate worker observes the fixture result."""
        plan = self._plan(principal, plan_id)
        if plan.action == PlanAction.DESTROY:
            return [self._queue_destroy(principal, plan)]
        if plan.action == PlanAction.CHANGE:
            return [self._queue_change(principal, plan)]
        if plan.state not in {LifecycleState.PLANNED, LifecycleState.APPROVED}:
            raise ValueError("plan is not executable")
        if plan.state == LifecycleState.APPROVED and not self.db.scalar(
            select(Approval).where(
                Approval.deployment_plan_id == plan.id, Approval.plan_hash == plan.plan_hash
            )
        ):
            raise ValueError("approved plan has no matching durable approval")
        spec = WorkloadSpec.model_validate(plan.payload["spec"])
        environments: list[Environment] = []
        plan.state = LifecycleState.QUEUED
        intent = self._intent(principal, plan.intent_id)
        for environment_type in spec.environments:
            environment = Environment(
                organization_id=principal.organization_id,
                project_id=intent.project_id,
                name=f"{intent.id[:8]}-{environment_type}",
                environment_type=environment_type,
                state=LifecycleState.QUEUED,
                desired_state={
                    "profile": plan.payload["architecture"]["profile"],
                    "execution_profile": execution_profile(
                        plan.payload["architecture"]["profile"]
                    ).__dict__,
                    "plan_hash": plan.plan_hash,
                    "execution_mode": plan.payload.get("execution_mode", "LOCAL_FIXTURE"),
                    "customer_plan_revision_id": plan.payload.get("customer_plan_revision_id"),
                    "customer_plan_digest": plan.payload.get("customer_plan_digest"),
                    "cost_estimate": plan.payload["architecture"].get("cost_estimate"),
                    "should_fail": "force failure" in intent.prompt.lower(),
                    "should_degrade": "force degraded" in intent.prompt.lower(),
                    "spec": plan.payload["spec"],
                    "min_replicas": 1,
                },
                observed_state={},
            )
            self.db.add(environment)
            self.db.flush()
            self.db.add(
                ExecutionJob(
                    deployment_plan_id=plan.id,
                    environment_id=environment.id,
                    state="QUEUED",
                    result={"operation": "DEPLOY"},
                )
            )
            self.audit(
                principal,
                "execution.queued",
                "environment",
                environment.id,
                {"plan_hash": plan.plan_hash},
            )
            environments.append(environment)
        self.db.commit()
        return environments

    def run_next_job(self) -> bool:
        """Run one durable fixture job. This is called only by the trusted local worker."""
        job = self.db.scalar(
            select(ExecutionJob)
            .where(ExecutionJob.state == "QUEUED")
            .order_by(ExecutionJob.created_at)
            .limit(1)
        )
        if not job:
            return False
        environment = self.db.get(Environment, job.environment_id)
        plan = self.db.get(DeploymentPlan, job.deployment_plan_id)
        if not environment or not plan:
            job.state = "FAILED"
            job.result = {"reason": "missing durable plan or environment"}
            self.db.commit()
            return True
        with self._trace("davdeploy.execution.run"):
            job.state = "RUNNING"
            if plan.action == PlanAction.DESTROY:
                environment.state = LifecycleState.DESTROYING
                observation = self.executor.destroy(environment.id)
                environment.state = (
                    LifecycleState.DESTROYED
                    if observation.state == "DESTROYED"
                    else LifecycleState.FAILED
                )
                action = (
                    "environment.destroyed"
                    if environment.state == LifecycleState.DESTROYED
                    else "environment.destroy_failed"
                )
            elif plan.action == PlanAction.CHANGE:
                for state in (
                    LifecycleState.PROVISIONING,
                    LifecycleState.DEPLOYING,
                    LifecycleState.VERIFYING,
                ):
                    require_transition(LifecycleState(environment.state), state)
                    environment.state = state
                change = plan.payload["recommendation"]["proposed_change"]
                observation = self.executor.change(environment.id, int(change["to"]))
                environment.desired_state = {
                    **environment.desired_state,
                    "min_replicas": int(change["to"]),
                    "last_change_plan_hash": plan.plan_hash,
                }
                environment.state = (
                    LifecycleState.READY if observation.state == "READY" else LifecycleState.FAILED
                )
                action = "environment.change_observed"
                self._resolve_day2_records(plan, environment)
            else:
                for state in (
                    LifecycleState.PROVISIONING,
                    LifecycleState.DEPLOYING,
                    LifecycleState.VERIFYING,
                ):
                    require_transition(LifecycleState(environment.state), state)
                    environment.state = state
                observation = self.executor.deploy(
                    environment.id,
                    profile=environment.desired_state["profile"],
                    should_fail=bool(environment.desired_state.get("should_fail")),
                    should_degrade=bool(environment.desired_state.get("should_degrade")),
                )
                environment.state = {
                    "READY": LifecycleState.READY,
                    "DEGRADED": LifecycleState.DEGRADED,
                }.get(observation.state, LifecycleState.FAILED)
                action = (
                    "environment.degraded"
                    if environment.state == LifecycleState.DEGRADED
                    else "environment.observed"
                )
                if environment.state == LifecycleState.DEGRADED:
                    self._open_incident(
                        environment,
                        "Fixture observation detected degraded application health.",
                        observation.detail,
                    )
            observation_detail = {**observation.detail, "state": observation.state}
            environment.observed_state = observation_detail
            self._record_environment_observation_assets(environment, observation_detail)
            job.state = (
                "SUCCEEDED" if observation.state in {"READY", "DEGRADED", "DESTROYED"} else "FAILED"
            )
            job.result = {"observation": observation_detail, "state": environment.state}
            principal = Principal(
                subject="system-worker",
                organization_id=environment.organization_id,
                role="operator",
            )
            self.audit(
                principal,
                action,
                "environment",
                environment.id,
                {"state": environment.state, "observation": observation_detail},
            )
            self.db.commit()
        return True

    def destroy_plan(self, principal: Principal, environment_id: str) -> DeploymentPlan:
        with self._trace("davdeploy.destroy.plan"):
            return self._destroy_plan(principal, environment_id)

    def _destroy_plan(self, principal: Principal, environment_id: str) -> DeploymentPlan:
        environment = self._environment(principal, environment_id)
        if LifecycleState(environment.state) not in {
            LifecycleState.READY,
            LifecycleState.FAILED,
            LifecycleState.DEGRADED,
        }:
            raise ValueError("environment cannot be destroyed in its current state")
        environment.state = LifecycleState.DESTROY_REQUESTED
        requires_approval = environment.environment_type == EnvironmentName.PRODUCTION
        payload = {
            "action": PlanAction.DESTROY,
            "environment_id": environment.id,
            "observed_state": environment.observed_state,
        }
        digest = plan_hash(payload)
        plan = DeploymentPlan(
            organization_id=principal.organization_id,
            environment_id=environment.id,
            requester_subject=principal.subject,
            action=PlanAction.DESTROY,
            state=LifecycleState.DESTROY_APPROVAL_REQUIRED
            if requires_approval
            else LifecycleState.PLANNED,
            plan_hash=digest,
            policy_result=PolicyResult.APPROVAL_REQUIRED
            if requires_approval
            else PolicyResult.ALLOW,
            payload=payload,
        )
        self.db.add(plan)
        self.db.flush()
        self.audit(
            principal,
            "destroy_plan.created",
            "deployment_plan",
            plan.id,
            {"hash": digest, "approval_required": requires_approval},
        )
        self.db.commit()
        return plan

    def recommendation(self, principal: Principal, environment_id: str) -> dict[str, Any]:
        """Explain a bounded local Day-2 change; this does not mutate the environment."""
        with self._trace("davdeploy.day2.diagnose"):
            environment = self._environment(principal, environment_id)
            if LifecycleState(environment.state) not in {
                LifecycleState.READY,
                LifecycleState.DEGRADED,
            }:
                raise ValueError("environment must be ready or degraded before it can be diagnosed")
            record = self._recommendation_record(principal, environment)
            return self._recommendation_response(record)

    def change_plan(self, principal: Principal, environment_id: str) -> DeploymentPlan:
        with self._trace("davdeploy.day2.change_plan"):
            environment = self._environment(principal, environment_id)
            if LifecycleState(environment.state) == LifecycleState.CHANGE_PROPOSED:
                existing = self.db.scalar(
                    select(DeploymentPlan)
                    .where(
                        DeploymentPlan.environment_id == environment.id,
                        DeploymentPlan.action == PlanAction.CHANGE,
                        DeploymentPlan.state.in_(
                            [LifecycleState.PLANNED, LifecycleState.APPROVAL_REQUIRED]
                        ),
                    )
                    .order_by(DeploymentPlan.created_at.desc())
                )
                if existing:
                    return existing
            if LifecycleState(environment.state) not in {
                LifecycleState.READY,
                LifecycleState.DEGRADED,
            }:
                raise ValueError("environment cannot receive a change plan in its current state")
            record = self._recommendation_record(principal, environment)
            recommendation = record.recommendation
            spec = WorkloadSpec.model_validate(environment.desired_state["spec"])
            with self._trace("davdeploy.policy.evaluate"):
                decision = self.policy.evaluate(
                    principal,
                    spec,
                    PlanAction.CHANGE,
                    target_environment_type=environment.environment_type,
                )
            payload = {
                "action": PlanAction.CHANGE,
                "environment_id": environment.id,
                "spec": spec.model_dump(mode="json"),
                "recommendation": recommendation,
                "recommendation_record_id": record.id,
                "policy": {"result": decision.result, "reason": decision.reason},
            }
            digest = plan_hash(payload)
            existing = self.db.scalar(
                select(DeploymentPlan).where(DeploymentPlan.plan_hash == digest)
            )
            if existing:
                return existing
            state = {
                PolicyResult.ALLOW: LifecycleState.PLANNED,
                PolicyResult.DENY: LifecycleState.POLICY_DENIED,
                PolicyResult.APPROVAL_REQUIRED: LifecycleState.APPROVAL_REQUIRED,
            }[decision.result]
            plan = DeploymentPlan(
                organization_id=principal.organization_id,
                environment_id=environment.id,
                requester_subject=principal.subject,
                action=PlanAction.CHANGE,
                state=state,
                plan_hash=digest,
                policy_result=decision.result,
                payload=payload,
            )
            self.db.add(plan)
            self.db.flush()
            record.deployment_plan_id = plan.id
            if decision.result == PolicyResult.DENY:
                record.state = "DENIED"
            else:
                record.state = "PLANNED"
                require_transition(
                    LifecycleState(environment.state), LifecycleState.CHANGE_PROPOSED
                )
                environment.state = LifecycleState.CHANGE_PROPOSED
            self.audit(
                principal,
                "change_plan.created",
                "deployment_plan",
                plan.id,
                {
                    "hash": digest,
                    "policy": decision.result,
                    "recommendation": recommendation["diagnosis"],
                    "recommendation_id": record.id,
                },
            )
            self.db.commit()
            return plan

    def _queue_destroy(self, principal: Principal, plan: DeploymentPlan) -> Environment:
        if plan.state not in {LifecycleState.PLANNED, LifecycleState.APPROVED}:
            raise ValueError("destroy plan is not executable")
        environment = self._environment(principal, plan.environment_id)
        self.db.add(
            ExecutionJob(
                deployment_plan_id=plan.id,
                environment_id=environment.id,
                state="QUEUED",
                result={"operation": "DESTROY"},
            )
        )
        self.audit(
            principal,
            "execution.queued",
            "environment",
            environment.id,
            {"plan_hash": plan.plan_hash},
        )
        self.db.commit()
        return environment

    def _queue_change(self, principal: Principal, plan: DeploymentPlan) -> Environment:
        if plan.state not in {LifecycleState.PLANNED, LifecycleState.APPROVED}:
            raise ValueError("change plan is not executable")
        environment = self._environment(principal, plan.environment_id)
        if LifecycleState(environment.state) not in {LifecycleState.CHANGE_PROPOSED}:
            raise ValueError("environment cannot receive a change in its current state")
        if plan.state == LifecycleState.APPROVED and not self.db.scalar(
            select(Approval).where(
                Approval.deployment_plan_id == plan.id, Approval.plan_hash == plan.plan_hash
            )
        ):
            raise ValueError("approved plan has no matching durable approval")
        require_transition(LifecycleState(environment.state), LifecycleState.QUEUED)
        environment.state = LifecycleState.QUEUED
        self.db.add(
            ExecutionJob(
                deployment_plan_id=plan.id,
                environment_id=environment.id,
                state="QUEUED",
                result={"operation": "CHANGE"},
            )
        )
        self.audit(
            principal,
            "change.execution_queued",
            "environment",
            environment.id,
            {"plan_hash": plan.plan_hash},
        )
        self.db.commit()
        return environment

    def incidents(self, principal: Principal, environment_id: str) -> list[Incident]:
        environment = self._environment(principal, environment_id)
        return list(
            self.db.scalars(
                select(Incident)
                .where(Incident.environment_id == environment.id)
                .order_by(Incident.created_at.desc())
            )
        )

    def _open_incident(self, environment: Environment, summary: str, evidence: dict) -> Incident:
        incident = self.db.scalar(
            select(Incident).where(
                Incident.environment_id == environment.id, Incident.state == "OPEN"
            )
        )
        if incident:
            return incident
        incident = Incident(
            organization_id=environment.organization_id,
            environment_id=environment.id,
            summary=summary,
            evidence=evidence,
        )
        self.db.add(incident)
        return incident

    def _recommendation_record(
        self, principal: Principal, environment: Environment
    ) -> Recommendation:
        incident = self.db.scalar(
            select(Incident)
            .where(Incident.environment_id == environment.id, Incident.state == "OPEN")
            .order_by(Incident.created_at.desc())
        )
        if not incident:
            incident = self._open_incident(
                environment,
                "Latency and saturation need a bounded diagnostic recommendation.",
                self.day2_advisor.recommend(environment).evidence.model_dump(mode="json"),
            )
            self.db.flush()
        record = self.db.scalar(
            select(Recommendation)
            .where(
                Recommendation.environment_id == environment.id,
                Recommendation.incident_id == incident.id,
                Recommendation.state.in_(["PROPOSED", "PLANNED"]),
            )
            .order_by(Recommendation.created_at.desc())
        )
        if record:
            return record
        recommendation = self.day2_advisor.recommend(environment)
        record = Recommendation(
            organization_id=principal.organization_id,
            environment_id=environment.id,
            incident_id=incident.id,
            recommendation=recommendation.model_dump(mode="json"),
        )
        self.db.add(record)
        self.db.flush()
        self.audit(
            principal,
            "recommendation.created",
            "recommendation",
            record.id,
            {"environment_id": environment.id, "incident_id": incident.id},
        )
        self.db.commit()
        return record

    @staticmethod
    def _recommendation_response(record: Recommendation) -> dict[str, Any]:
        return {
            **record.recommendation,
            "record_id": record.id,
            "incident_id": record.incident_id,
            "record_state": record.state,
        }

    def _resolve_day2_records(self, plan: DeploymentPlan, environment: Environment) -> None:
        record_id = plan.payload.get("recommendation_record_id")
        if not record_id:
            return
        record = self.db.get(Recommendation, record_id)
        if record and record.organization_id == environment.organization_id:
            record.state = "APPLIED"
            if record.incident_id:
                incident = self.db.get(Incident, record.incident_id)
                if incident:
                    incident.state = "RESOLVED"

    def _environment(self, principal: Principal, environment_id: str) -> Environment:
        environment = self.db.get(Environment, environment_id)
        if not environment or environment.organization_id != principal.organization_id:
            raise PermissionError("environment not found in this organization")
        return environment

    def get_environment(self, principal: Principal, environment_id: str) -> Environment:
        return self._environment(principal, environment_id)

    def environment_payload(self, principal: Principal, environment_id: str) -> dict[str, Any]:
        environment = self._environment(principal, environment_id)
        return self._environment_payload(environment)

    def environment_payloads(self, principal: Principal) -> list[dict[str, Any]]:
        return [
            self._environment_payload(environment)
            for environment in self.db.scalars(
                select(Environment)
                .where(Environment.organization_id == principal.organization_id)
                .order_by(Environment.created_at)
            )
        ]

    def _environment_payload(self, environment: Environment) -> dict[str, Any]:
        return {
            "id": environment.id,
            "name": environment.name,
            "type": environment.environment_type,
            "state": environment.state,
            "execution_mode": environment.desired_state.get("execution_mode"),
            "customer_plan_revision_id": environment.desired_state.get("customer_plan_revision_id"),
            "cost_estimate": environment.desired_state.get("cost_estimate"),
            "desired_state": environment.desired_state,
            "observed_state": environment.observed_state,
            "outputs": self._environment_outputs(environment.id),
            "resources": self._observed_resources(environment.id),
        }

    def audits(self, principal: Principal, environment_id: str | None = None) -> list[AuditEvent]:
        statement = select(AuditEvent).where(
            AuditEvent.organization_id == principal.organization_id
        )
        if environment_id:
            self._environment(principal, environment_id)
            statement = statement.where(
                AuditEvent.entity_type == "environment", AuditEvent.entity_id == environment_id
            )
        return list(self.db.scalars(statement.order_by(AuditEvent.created_at)))

    def audit_evidence(
        self, principal: Principal, entity_id: str | None = None
    ) -> list[dict[str, Any]]:
        statement = select(AuditEvent).where(
            AuditEvent.organization_id == principal.organization_id
        )
        if entity_id:
            statement = statement.where(AuditEvent.entity_id == entity_id)
        events = self.db.scalars(statement.order_by(AuditEvent.created_at)).all()
        users = {
            user.subject: user.role
            for user in self.db.scalars(
                select(ProductUser).where(ProductUser.organization_id == principal.organization_id)
            )
        }
        return [self._audit_evidence_item(event, users) for event in events]

    @staticmethod
    def _audit_evidence_item(event: AuditEvent, roles: dict[str, str]) -> dict[str, Any]:
        detail = event.detail or {}
        labels = {
            "project.created": "Project created",
            "repository.analyzed": "Repository analyzed",
            "cloud_connection.created": "AWS connection metadata created",
            "intent.interpreted": "Intent interpreted",
            "deployment_plan.created": "Deployment plan created",
            "infrastructure_plan.draft_created": "Customer plan draft created",
            "infrastructure_plan.constraints_updated": "Draft constraints updated",
            "infrastructure_plan.submitted": "Plan submitted for approval",
            "infrastructure_plan.approved": "Plan approved",
            "infrastructure_plan.rejected": "Plan rejected",
            "infrastructure_plan.revised": "Plan revised",
            "customer_plan.local_dry_run_plan_created": "Local dry-run plan created",
            "customer_plan.local_dry_run_queued": "Local dry-run queued",
            "customer_plan.local_destroy_requested": "Local destroy requested",
            "environment.observed": "Environment observed",
            "environment.degraded": "Environment degraded",
            "environment.destroyed": "Environment destroyed",
        }
        return {
            "id": event.id,
            "label": labels.get(event.action, event.action.replace("_", " ").replace(".", " / ")),
            "action": event.action,
            "actor_subject": event.actor_subject,
            "actor_role": roles.get(event.actor_subject, "system"),
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "plan_digest": detail.get("digest") or detail.get("hash") or detail.get("plan_hash"),
            "revision": detail.get("revision"),
            "decision_reason": detail.get("reason"),
            "integration": detail.get("provider") or detail.get("execution"),
            "detail": detail,
            "at": event.created_at.isoformat() if event.created_at else None,
            "export_ready": True,
        }
