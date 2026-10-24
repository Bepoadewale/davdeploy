from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import boto3
import httpx
from botocore.exceptions import BotoCoreError, ClientError
from httpx import HTTPError
from opentelemetry import trace
from sqlalchemy import select
from sqlalchemy.orm import Session

from davdeploy.cloud_execution import (
    CloudExecutionAdapter,
    configured_cloud_execution_adapter,
)
from davdeploy.connection_secrets import (
    ConnectionSecretStore,
    configured_connection_secret_store,
)
from davdeploy.contracts import TenantScope
from davdeploy.day2 import FixtureDay2Advisor
from davdeploy.domain import (
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
from davdeploy.models import (
    ApiCredential,
    Approval,
    AuditEvent,
    CloudConnection,
    CloudDiscoveryJob,
    CloudExecutionRun,
    CloudReadinessPreflight,
    DataLifecycleRequest,
    DeploymentPlan,
    DesiredStatePublication,
    Environment,
    EnvironmentOutput,
    ExecutionJob,
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
    WorkloadIntent,
    WorkspaceInvitation,
    WorkspaceSubscription,
)
from davdeploy.planner import AwsV1Planner
from davdeploy.policy import PolicyClient
from davdeploy.security import IdentityClaims, Principal
from davdeploy.state import require_transition


def plan_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


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
            organization = Organization(name=f"{workspace_name.strip()} {identity.subject[-8:]}")
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
        self, principal: Principal, connection_id: str, account_id: str
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
        if not discovery_broker_role_arn or not execution_broker_role_arn or not template_url:
            raise RuntimeError(
                "AWS customer connection setup is not configured with broker roles and a hosted template"
            )
        external_id = secrets.token_urlsafe(32)
        stack_name = f"davdeploy-Discovery-{connection.id[:8]}"
        discovery_role_arn = f"arn:aws:iam::{account_id}:role/davdeployDiscovery-{connection.id}"
        execution_role_arn = f"arn:aws:iam::{account_id}:role/davdeployExecution-{connection.id}"
        parameters = {
            "davdeployDiscoveryBrokerRoleArn": discovery_broker_role_arn,
            "davdeployExecutionBrokerRoleArn": execution_broker_role_arn,
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
        connection.execution_role_arn = execution_role_arn
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
                "Review the separate read-only discovery and bounded execution IAM roles, then acknowledge IAM resource creation.",
                "Create the stack, then return to davdeploy to verify the connection.",
            ],
            "boundary": "This action only creates a setup link and does not create customer AWS resources. The execution role has no reusable credentials and is separate from discovery. davdeploy does not create a workload until an exact approved plan is applied.",
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
        snapshot = (discovery or StsAwsDiscovery()).verify(
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
        configured_fixture_repository = (
            getattr(self.github, "execution", None) == "SIMULATED"
            and repository_name.lower().startswith("example/")
        )
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
        """Generate a plan-only App Runner Terraform contract.

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
        if profile_name != "aws-app-runner":
            raise ValueError(
                "App Runner Terraform renderer only supports aws-app-runner approved plans"
            )
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
        render = self._app_runner_terraform_contract(
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
                ("AUTHENTICATED_DESTROY_PLAN_ALLOWED_NOT_EXECUTED" if destroy_review else "AUTHENTICATED_PLAN_ALLOWED_NOT_EXECUTED")
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
            if not connection or connection.setup_state != "VERIFIED" or not connection.execution_role_arn:
                stored.state = "BLOCKED_CLOUD_CONNECTION_NOT_VERIFIED"
                stored.evidence = {**stored.evidence, "blockers": ["Authenticated Terraform plan requires a verified customer connection with an execution role."]}
            elif not connection.external_id_secret_ref or not runner_bucket or not runner_artifact or not runtime_enabled:
                stored.state = "BLOCKED_CLOUD_EXECUTION_RUNTIME_NOT_CONFIGURED"
                stored.evidence = {**stored.evidence, "blockers": ["Authenticated Terraform plan runner configuration is incomplete or disabled."]}
            else:
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
                        ((image_build.outputs or {}).get("image_build") or {}).get("image_identifier")
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
                    stored.evidence = {**stored.evidence, "blockers": ["Customer execution lock table is not configured."]}
                    plan_run.state = "BLOCKED_CLOUD_EXECUTION_RUNTIME_NOT_CONFIGURED"
                else:
                    plan_run.evidence = {
                        "execution_environment": execution_environment,
                        "result_s3_uri": execution_environment["DAVDEPLOY_EXECUTION_RESULT_S3_URI"],
                        "boundary": "A bounded runner may generate a Terraform plan artifact only. It cannot apply this request.",
                    }
                    result = self.cloud_execution.execute({"run_id": plan_run.id, "environment": execution_environment})
                    plan_run.state = result.state
                    plan_run.outputs = {**plan_run.outputs, **result.outputs, "operations": list(result.operations), "failure_reason": result.failure_reason}
                    stored.state = (
                        "AUTHENTICATED_DESTROY_PLAN_SUBMITTED"
                        if destroy_review and result.state == "SUBMITTED"
                        else "AUTHENTICATED_PLAN_SUBMITTED"
                        if result.state == "SUBMITTED"
                        else "BLOCKED_CLOUD_EXECUTION_RUNTIME_NOT_CONFIGURED"
                    )
                    stored.evidence = {**stored.evidence, "execution_run_id": plan_run.id, "runner_state": result.state}
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
    ) -> dict[str, Any]:
        """Record a guarded App Runner execution run request.

        Default/local mode cannot mutate AWS. Authenticated execution remains
        gated by explicit process environment and request confirmation.
        """
        if not self._is_workspace_administrator(principal):
            raise PermissionError("only a workspace administrator can request cloud execution")
        if mode == "AUTHENTICATED_APP_RUNNER_IMAGE_BUILD":
            raise ValueError("use the governed customer-image-build endpoint for image delivery")
        revision, infrastructure_plan, _ = self._approved_customer_revision(principal, revision_id)
        if (
            revision.content_digest != content_digest
            or plan_hash(revision.content) != content_digest
        ):
            raise ValueError("stale cloud execution request: approved digest changed")
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
        elif plan_review.state not in ({expected_review_state} if destroy_mode else {"LOCAL_CONTRACT_PLAN_REVIEWED", "AUTHENTICATED_PLAN_REVIEWED"}):
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
                    blockers.append("Selected customer cloud connection has no bounded execution role.")
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
                if not real_plan_artifact.get("saved_plan_s3_uri") or not real_plan_artifact.get("saved_plan_sha256"):
                    blockers.append("Authenticated execution requires a reviewed saved Terraform plan artifact.")
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
                    ((image_build.outputs or {}).get("image_build") or {}).get("image_identifier") or ""
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
                "DAVDEPLOY_EXECUTION_OPERATION": "destroy-saved-plan" if destroy_mode else "apply-saved-plan",
                "DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI": str(real_plan_artifact.get("saved_plan_s3_uri") if mode in {"AUTHENTICATED_APP_RUNNER_APPLY", "AUTHENTICATED_APP_RUNNER_DESTROY"} else ""),
                "DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256": str(real_plan_artifact.get("saved_plan_sha256") if mode in {"AUTHENTICATED_APP_RUNNER_APPLY", "AUTHENTICATED_APP_RUNNER_DESTROY"} else ""),
                "DAVDEPLOY_CUSTOMER_PLAN_DIGEST": revision.content_digest,
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
            "apply_command_available": state == "READY_FOR_OPERATOR_APP_RUNNER_EXECUTION" and not destroy_mode,
            "destroy_command_available": state == "READY_FOR_OPERATOR_APP_RUNNER_EXECUTION" and destroy_mode,
            "destroy_required": True,
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
        if revision.content_digest != content_digest or plan_hash(revision.content) != content_digest:
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
            raise ValueError("authenticated image build requires a verified customer cloud connection")
        connection = self._cloud_connection(principal, connection_id)
        if connection.setup_state != "VERIFIED" or not connection.execution_role_arn:
            raise ValueError("selected customer cloud connection is not verified for bounded execution")
        if expected_account_id and connection.account_id != expected_account_id:
            raise ValueError("expected AWS account does not match the verified customer connection")
        region = str(target.get("region") or connection.region or "")
        if expected_region and region != expected_region:
            raise ValueError("expected AWS region does not match the approved plan")
        if not region:
            raise ValueError("approved plan has no target region")
        if confirmation != "BUILD_CUSTOMER_IMAGE":
            raise ValueError("explicit BUILD_CUSTOMER_IMAGE confirmation is required")
        if os.getenv("ALLOW_CLOUD_APPLY", "").lower() != "true" or os.getenv(
            "DAVDEPLOY_ENABLE_APP_RUNNER_EXECUTION", ""
        ).lower() != "true":
            raise ValueError("customer image build runtime is disabled")

        repository_connection = self.db.scalar(
            select(RepositoryConnection).where(
                RepositoryConnection.organization_id == principal.organization_id,
                RepositoryConnection.project_id == infrastructure_plan.project_id,
                RepositoryConnection.repository_url == repository_url,
            )
        )
        if repository_connection is None or (
            repository_connection.selected_branch and repository_connection.selected_branch != branch
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
        if len(source_commit) != 40 or any(character not in "0123456789abcdef" for character in source_commit.lower()):
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
        if not bucket or not lock_table or not artifact_uri or not connection.external_id_secret_ref:
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
        self.audit(principal, "cloud_execution.image_build_requested", "cloud_execution_run", run.id, {"revision_id": revision.id, "digest": revision.content_digest, "source_commit": source_commit})
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
        if run.state != "READY_FOR_OPERATOR_APP_RUNNER_EXECUTION":
            raise ValueError(f"cloud execution run is not ready: {run.state}")
        expected_confirmation = {
            "AUTHENTICATED_APP_RUNNER_DESTROY": "DESTROY_APP_RUNNER_WORKLOAD",
            "AUTHENTICATED_APP_RUNNER_IMAGE_BUILD": "BUILD_CUSTOMER_IMAGE",
        }.get(run.mode, "EXECUTE_APP_RUNNER_WORKLOAD")
        if confirmation != expected_confirmation:
            raise ValueError("explicit App Runner operation confirmation is required")
        run.state = "QUEUED"
        run.evidence = {
            **(run.evidence or {}),
            "queued_by_subject": principal.subject,
            "queue_confirmation": expected_confirmation,
            "boundary": "Queued for the trusted App Runner adapter; no user-supplied command is accepted.",
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
        """Run one durable cloud execution job through the configured adapter."""
        run = self.db.scalar(
            select(CloudExecutionRun)
            .where(CloudExecutionRun.state == "QUEUED")
            .order_by(CloudExecutionRun.created_at)
            .limit(1)
        )
        if not run:
            return False
        run.state = "RUNNING"
        self.db.commit()
        context = {
            "run_id": run.id,
            "profile": run.profile,
            "digest": run.content_digest,
            "environment": (run.evidence or {}).get("execution_environment", {}),
        }
        result = self.cloud_execution.execute(context)
        run.state = result.state
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

    def reconcile_cloud_execution_build(self, build_id: str) -> bool:
        """Persist one CodeBuild completion received through the SQS event bridge."""
        normalized_build_id = build_id.rsplit("/", 1)[-1]
        run = next(
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
        if not run:
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
                if artifact.get("run_id") != run.id or artifact.get("status") != "SUCCEEDED":
                    raise ValueError("runner result artifact does not match the execution run")
            except (BotoCoreError, ClientError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
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
            if not review or not detail.get("saved_plan_s3_uri") or not detail.get("saved_plan_sha256"):
                run.state = "FAILED"
                artifact_error = "authenticated plan completion did not contain a saved plan artifact"
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
        else:
            detail = artifact.get("detail") or {}
            if run.mode == "AUTHENTICATED_APP_RUNNER_DESTROY":
                run.state = "DESTROYED_VERIFIED" if detail.get("destroy_proof") == "confirmed_absent" else "FAILED"
            elif run.mode == "AUTHENTICATED_APP_RUNNER_IMAGE_BUILD":
                run.state = (
                    "IMAGE_BUILT_AWAITING_SERVICE_PLAN"
                    if detail.get("image_identifier") and detail.get("source_commit")
                    else "FAILED"
                )
                if run.state == "FAILED":
                    artifact_error = "image build completion did not contain immutable image evidence"
            else:
                run.state = "SUCCEEDED_AWAITING_OBSERVATION"
        run.outputs = {
            **(run.outputs or {}),
            "codebuild_status": status,
            "codebuild_completed_at": str(build.get("buildComplete") or ""),
            "runner_artifact": artifact or None,
            "terraform_outputs": (artifact.get("detail") or {}) if run.mode == "AUTHENTICATED_APP_RUNNER_APPLY" else None,
            "image_build": (artifact.get("detail") or {}) if run.mode == "AUTHENTICATED_APP_RUNNER_IMAGE_BUILD" else None,
            "destroy_proof": (artifact.get("detail") or {}).get("destroy_proof"),
            "failure_reason": artifact_error or (None if status == "SUCCEEDED" else "Bounded CodeBuild runner failed."),
        }
        self.audit(
            Principal("system-cloud-worker", run.organization_id, "operator"),
            "cloud_execution.codebuild_completed",
            "cloud_execution_run",
            run.id,
            {"build_id": build_id, "status": status},
        )
        self.db.commit()
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
