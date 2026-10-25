from __future__ import annotations

import os
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import Counter, generate_latest
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from davdeploy.db import (
    AuroraDatabaseUnavailable,
    SessionLocal,
    ensure_aurora_ready,
    run_migrations,
    session,
)
from davdeploy.domain import (
    ApiCredentialRequest,
    ApprovalRequest,
    AwsConnectionVerificationRequest,
    AwsQuickCreateRequest,
    CloudConnectionRequest,
    CloudExecutionExecuteRequest,
    CloudExecutionRunRequest,
    CloudInventorySnapshotRequest,
    CloudReadinessPreflightRequest,
    DataLifecycleRequestBody,
    DesiredStatePublicationRequest,
    DesiredStatePublicationStateRequest,
    InfrastructurePlanConstraintUpdateRequest,
    InfrastructurePlanDecisionRequest,
    InfrastructurePlanRevisionRequest,
    IntentRequest,
    InvitationRequest,
    LocalLoginRequest,
    MembershipRoleRequest,
    OnboardingRequest,
    PlanCommentRequest,
    ProjectRequest,
    SubscriptionRequest,
    SupportTicketRequest,
    TerraformPlanRenderRequest,
    TerraformPlanReviewRequest,
)
from davdeploy.invitation_email import InvitationDeliveryUnavailable
from davdeploy.model_gateway import ModelGatewayUnavailable
from davdeploy.product_readiness import security_headers
from davdeploy.rate_limit import SlidingWindowRateLimiter
from davdeploy.security import (
    IdentityClaims,
    Principal,
    issue_local_token,
    verify_identity_token,
    verify_token,
)
from davdeploy.service import ProductService
from davdeploy.telemetry import configure_tracing

REQUESTS = Counter("davdeploy_api_requests_total", "API requests by route", ["route"])
PLAN_RESULTS = Counter("davdeploy_plan_results_total", "Plans by policy outcome", ["outcome"])
EXECUTION_RESULTS = Counter(
    "davdeploy_execution_results_total", "Observed execution results", ["state"]
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    hosted = os.getenv("DAVDEPLOY_HOSTED_MODE", "false").lower() == "true"
    auto_migrate = os.getenv("DAVDEPLOY_AUTO_MIGRATE", "false").lower() == "true"
    if not hosted or auto_migrate:
        run_migrations()
    if not hosted:
        db = SessionLocal()
        try:
            ProductService(db).seed_local_identity()
        finally:
            db.close()
    yield


app = FastAPI(title="davdeploy", version="0.1.0", lifespan=lifespan)
configure_tracing()
FastAPIInstrumentor.instrument_app(app)
API_CONTRACT_VERSION = "v1"
RATE_LIMIT = SlidingWindowRateLimiter(int(os.getenv("DAVDEPLOY_RATE_LIMIT_PER_MINUTE", "0")))


def parse_frontend_origins(value: str | None) -> list[str]:
    """Return distinct, exact browser origins or fail closed."""
    origins: list[str] = []
    for candidate in (item.strip().rstrip("/") for item in (value or "").split(",")):
        if not candidate:
            continue
        if candidate == "*":
            raise RuntimeError("wildcard frontend origins are not permitted")
        parsed = urlsplit(candidate)
        localhost = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
            or (parsed.scheme != "https" and not localhost)
        ):
            raise RuntimeError(f"invalid frontend origin: {candidate}")
        if candidate not in origins:
            origins.append(candidate)
    return origins


def configure_frontend_cors(application: FastAPI, origins: list[str]) -> None:
    if not origins:
        return
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        expose_headers=[
            "X-davdeploy-API-Version",
            "X-Request-ID",
            "X-Correlation-ID",
        ],
        max_age=600,
    )


configure_frontend_cors(
    app,
    parse_frontend_origins(os.getenv("DAVDEPLOY_ALLOWED_FRONTEND_ORIGINS")),
)


@app.middleware("http")
async def apply_api_guardrails(request: Request, call_next):
    """Apply bounded abuse protection, contract metadata and security headers."""
    client = request.client.host if request.client else "unknown"
    if (
        RATE_LIMIT.limit
        and not request.url.path.startswith("/healthz")
        and not RATE_LIMIT.allow(client)
    ):
        return Response(
            status_code=429,
            content='{"detail":"rate limit exceeded"}',
            media_type="application/json",
            headers={"Retry-After": "60"},
        )
    public_paths = {"/", "/healthz", "/status", "/metrics", "/openapi.json"}
    if request.method != "OPTIONS" and request.url.path not in public_paths:
        try:
            await run_in_threadpool(ensure_aurora_ready)
        except AuroraDatabaseUnavailable as error:
            response = JSONResponse(
                status_code=503,
                content={"detail": str(error)},
                headers={"Retry-After": "10"},
            )
        else:
            response = await call_next(request)
    else:
        response = await call_next(request)
    response.headers["X-davdeploy-API-Version"] = API_CONTRACT_VERSION
    for name, value in security_headers().items():
        response.headers[name] = value
    return response


def product_service(db: Session = Depends(session)) -> ProductService:
    return ProductService(db)


def translate(error: Exception) -> None:
    if isinstance(error, PermissionError):
        raise HTTPException(403, str(error)) from error
    if isinstance(error, (ValueError, KeyError)):
        raise HTTPException(409, str(error)) from error
    if isinstance(error, ModelGatewayUnavailable):
        raise HTTPException(503, str(error)) from error
    if isinstance(error, InvitationDeliveryUnavailable):
        raise HTTPException(503, str(error)) from error
    raise error


@app.get("/")
def api_root():
    return {
        "product": "davdeploy",
        "surface": "control-plane-api",
        "api_version": API_CONTRACT_VERSION,
        "openapi": "/openapi.json",
    }


@app.get("/healthz")
def healthz():
    return {"status": "ok", "product": "davdeploy"}


@app.get("/status")
def public_status():
    """Unauthenticated, provider-neutral status surface for demos/self-hosting."""
    return {
        "status": "operational",
        "product": "davdeploy",
        "cloud_execution": "not enabled by default",
    }


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain; version=0.0.4")


@app.post("/api/v1/auth/local-login")
def local_login(request: LocalLoginRequest):
    """Local fixture only. Production uses a trusted external OIDC issuer."""
    if os.getenv("DAVDEPLOY_HOSTED_MODE", "false").lower() == "true":
        raise HTTPException(404, "local fixture login is disabled in hosted mode")
    return {
        "access_token": issue_local_token(request.username),
        "token_type": "bearer",
        "expires_in": 1800,
    }


@app.get("/api/v1/me")
def current_user(
    principal: Principal = Depends(verify_token), service: ProductService = Depends(product_service)
):
    REQUESTS.labels("identity.current").inc()
    try:
        return service.workspace_profile(principal)
    except PermissionError as error:
        translate(error)


@app.post("/api/v1/onboarding")
def onboard_current_identity(
    request: OnboardingRequest,
    identity: IdentityClaims = Depends(verify_identity_token),
    service: ProductService = Depends(product_service),
):
    """Create a personal workspace or accept a tenant-scoped invitation."""
    try:
        return service.onboard_identity(
            identity,
            request.workspace_name,
            request.invitation_token,
        )
    except (PermissionError, ValueError, InvitationDeliveryUnavailable) as error:
        translate(error)


@app.get("/api/v1/workspace/invitations")
def workspace_invitations(
    principal: Principal = Depends(verify_token), service: ProductService = Depends(product_service)
):
    try:
        return service.list_workspace_invitations(principal)
    except PermissionError as error:
        translate(error)


@app.post("/api/v1/workspace/invitations/{invitation_id}/resend")
def resend_workspace_invitation(
    invitation_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    try:
        return service.resend_workspace_invitation(principal, invitation_id)
    except (PermissionError, KeyError, ValueError, InvitationDeliveryUnavailable) as error:
        translate(error)


@app.post("/api/v1/workspace/invitations/{invitation_id}/cancel")
def cancel_workspace_invitation(
    invitation_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    try:
        return service.cancel_workspace_invitation(principal, invitation_id)
    except (PermissionError, KeyError, ValueError) as error:
        translate(error)


@app.get("/api/v1/workspace/members")
def workspace_members(
    principal: Principal = Depends(verify_token), service: ProductService = Depends(product_service)
):
    return service.list_workspace_members(principal)


@app.patch("/api/v1/workspace/members/{subject}")
def change_workspace_member_role(
    subject: str,
    request: MembershipRoleRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    try:
        return service.change_workspace_member_role(principal, subject, request.role)
    except (PermissionError, KeyError, ValueError) as error:
        translate(error)


@app.post(
    "/api/v1/workspace/invitations",
    status_code=201,
    responses={503: {"description": "Invitation email delivery is unavailable"}},
)
def invite_workspace_member(
    request: InvitationRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    try:
        return service.invite_workspace_member(principal, request.email, request.role)
    except (PermissionError, ValueError, InvitationDeliveryUnavailable) as error:
        translate(error)


@app.get("/api/v1/usage")
def usage_summary(
    principal: Principal = Depends(verify_token), service: ProductService = Depends(product_service)
):
    return service.usage_summary(principal)


@app.get("/api/v1/billing/subscription")
def get_subscription(
    principal: Principal = Depends(verify_token), service: ProductService = Depends(product_service)
):
    return service.subscription(principal)


@app.put("/api/v1/billing/subscription")
def set_subscription(
    request: SubscriptionRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    try:
        return service.set_subscription(principal, request.plan_name, request.state, request.limits)
    except (PermissionError, ValueError) as error:
        translate(error)


@app.post("/api/v1/api-credentials", status_code=201)
def create_api_credential(
    request: ApiCredentialRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    try:
        return service.create_api_credential(principal, request.name, request.scopes)
    except (PermissionError, ValueError) as error:
        translate(error)


@app.delete("/api/v1/api-credentials/{credential_id}", status_code=204)
def revoke_api_credential(
    credential_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    try:
        service.revoke_api_credential(principal, credential_id)
    except (PermissionError, KeyError, ValueError) as error:
        translate(error)
    return Response(status_code=204)


@app.post("/api/v1/support/tickets", status_code=201)
def create_support_ticket(
    request: SupportTicketRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    ticket = service.create_support_ticket(principal, request.subject, request.body)
    return {
        "id": ticket.id,
        "subject": ticket.subject,
        "state": ticket.state,
        "created_at": ticket.created_at,
    }


@app.post("/api/v1/data-lifecycle", status_code=202)
def request_data_lifecycle(
    request: DataLifecycleRequestBody,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    try:
        return service.request_data_lifecycle(principal, request.request_type)
    except (PermissionError, ValueError) as error:
        translate(error)


@app.get("/api/v1/dashboard")
def workspace_dashboard(
    principal: Principal = Depends(verify_token), service: ProductService = Depends(product_service)
):
    REQUESTS.labels("workspace.dashboard").inc()
    try:
        return service.workspace_dashboard(principal)
    except PermissionError as error:
        translate(error)


@app.get("/api/v1/admin/pending-approvals")
def pending_approvals(
    principal: Principal = Depends(verify_token), service: ProductService = Depends(product_service)
):
    REQUESTS.labels("admin.pending_approvals").inc()
    try:
        return service.pending_infrastructure_plan_revisions(principal)
    except PermissionError as error:
        translate(error)


@app.get("/api/v1/admin/customer-plan-revisions")
def admin_customer_plan_revisions(
    state: str | None = None,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("admin.customer_plan_revisions").inc()
    try:
        return service.admin_infrastructure_plan_revisions(principal, state)
    except (PermissionError, ValueError) as error:
        translate(error)


@app.post("/api/v1/projects", status_code=201)
def create_project(
    request: ProjectRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("projects.create").inc()
    try:
        project = service.create_project(
            principal,
            request.name,
            str(request.repository_url) if request.repository_url else None,
            request.repository_branch,
        )
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)
    return {
        "id": project.id,
        "name": project.name,
        "repository_url": project.repository_url,
        "repository_branch": request.repository_branch,
    }


@app.get("/api/v1/github/connection")
def github_connection_status(
    principal: Principal = Depends(verify_token), service: ProductService = Depends(product_service)
):
    REQUESTS.labels("github.connection_status").inc()
    try:
        return service.github_connection_status(principal)
    except ValueError as error:
        translate(error)


@app.post("/api/v1/github/webhooks")
async def github_webhook(
    request: Request,
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("github.webhook").inc()
    event = request.headers.get("X-GitHub-Event", "")
    delivery_id = request.headers.get("X-GitHub-Delivery", "")
    signature = request.headers.get("X-Hub-Signature-256", "")
    body = await request.body()
    try:
        return service.receive_github_webhook(
            event=event,
            delivery_id=delivery_id,
            signature=signature,
            body=body,
        )
    except (PermissionError, ValueError) as error:
        translate(error)


@app.get("/api/v1/github/installations/{installation_id}/repositories")
def github_repositories(
    installation_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("github.repositories").inc()
    try:
        return service.github_repositories(principal, installation_id)
    except (PermissionError, ValueError) as error:
        translate(error)


@app.get("/api/v1/github/public-repository")
def public_github_repository(
    repository_url: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("github.public_repository").inc()
    try:
        return service.public_github_repository(principal, repository_url)
    except (PermissionError, ValueError) as error:
        translate(error)


@app.get("/api/v1/github/installations/{installation_id}/repositories/{repository:path}/branches")
def github_branches(
    installation_id: str,
    repository: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("github.branches").inc()
    try:
        return {"branches": service.github_branches(principal, installation_id, repository)}
    except (PermissionError, ValueError) as error:
        translate(error)


@app.post("/api/v1/cloud-connections", status_code=201)
def create_cloud_connection(
    request: CloudConnectionRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("cloud_connections.create").inc()
    connection = service.create_cloud_connection(
        principal, request.display_name, request.provider, request.connection_mode
    )
    return {
        "id": connection.id,
        "display_name": connection.display_name,
        "provider": connection.provider,
        "mode": connection.connection_mode,
        "executed": False,
        "setup_state": connection.setup_state,
    }


@app.get("/api/v1/cloud-connections")
def list_cloud_connections(
    principal: Principal = Depends(verify_token), service: ProductService = Depends(product_service)
):
    REQUESTS.labels("cloud_connections.list").inc()
    return [
        {
            "id": item.id,
            "display_name": item.display_name,
            "provider": item.provider,
            "mode": item.connection_mode,
            "executed": False,
            "account_id": item.account_id,
            "setup_state": item.setup_state,
        }
        for item in service.cloud_connections(principal)
    ]


@app.get("/api/v1/cloud-connections/{connection_id}")
def get_cloud_connection(
    connection_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("cloud_connections.get").inc()
    try:
        return service.cloud_connection_detail(principal, connection_id)
    except PermissionError as error:
        translate(error)


@app.delete("/api/v1/cloud-connections/{connection_id}", status_code=204)
def disconnect_cloud_connection(
    connection_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("cloud_connections.disconnect").inc()
    try:
        service.disconnect_cloud_connection(principal, connection_id)
    except PermissionError as error:
        translate(error)
    return Response(status_code=204)


@app.get("/api/v1/cloud-connections/{connection_id}/role-contract")
def get_cloud_role_contract(
    connection_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("cloud_connections.role_contract").inc()
    try:
        return service.cloud_role_contract(principal, connection_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.post("/api/v1/cloud-connections/{connection_id}/aws-quick-create")
def create_aws_quick_create_setup(
    connection_id: str,
    request: AwsQuickCreateRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("cloud_connections.aws_quick_create").inc()
    try:
        return service.aws_quick_create_setup(principal, connection_id, request.account_id)
    except (PermissionError, ValueError, KeyError, RuntimeError) as error:
        translate(error)


@app.post("/api/v1/cloud-connections/{connection_id}/aws-verify", status_code=202)
def verify_aws_connection(
    connection_id: str,
    request: AwsConnectionVerificationRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("cloud_connections.aws_verify").inc()
    try:
        job = service.queue_aws_connection_verification(principal, connection_id, request.region)
        if os.getenv("DAVDEPLOY_AWS_VERIFY_INLINE", "false").lower() == "true":
            service.run_next_discovery_job()
            job = service.cloud_discovery_job(principal, connection_id, job.id)
    except (PermissionError, ValueError, KeyError, RuntimeError) as error:
        translate(error)
    return {
        "id": job.id,
        "connection_id": job.cloud_connection_id,
        "region": job.region,
        "state": job.state,
        "credentials_stored": False,
    }


@app.get("/api/v1/cloud-connections/{connection_id}/aws-verification-jobs/{job_id}")
def get_aws_verification_job(
    connection_id: str,
    job_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("cloud_connections.aws_verify_status").inc()
    try:
        job = service.cloud_discovery_job(principal, connection_id, job_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)
    return {
        "id": job.id,
        "connection_id": job.cloud_connection_id,
        "region": job.region,
        "state": job.state,
        "attempts": job.attempts,
        "result": job.result,
        "error": job.error,
        "credentials_stored": False,
    }


@app.post("/api/v1/cloud-connections/{connection_id}/inventory-snapshots", status_code=201)
def record_cloud_inventory_snapshot(
    connection_id: str,
    request: CloudInventorySnapshotRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("cloud_inventory_snapshots.create").inc()
    try:
        stored = service.record_cloud_inventory_snapshot(
            principal,
            connection_id,
            request.region,
            request.provenance,
            request.captured_at,
            request.snapshot,
        )
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)
    return {
        "id": stored.id,
        "connection_id": stored.cloud_connection_id,
        "captured_at": stored.captured_at,
    }


@app.get("/api/v1/cloud-connections/{connection_id}/inventory-snapshots")
def list_cloud_inventory_snapshots(
    connection_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("cloud_inventory_snapshots.list").inc()
    try:
        snapshots = service.cloud_inventory_snapshots(principal, connection_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)
    return [
        {
            "id": snapshot.id,
            "connection_id": snapshot.cloud_connection_id,
            "region": snapshot.region,
            "provenance": snapshot.provenance,
            "captured_at": snapshot.captured_at,
            "snapshot": snapshot.snapshot,
        }
        for snapshot in snapshots
    ]


@app.get("/api/v1/projects/{project_id}/repository-discovery")
def get_repository_discovery(
    project_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("repositories.discovery").inc()
    try:
        return service.repository_discovery(principal, project_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.delete("/api/v1/projects/{project_id}/repository", status_code=204)
def disconnect_project_repository(
    project_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("repositories.disconnect").inc()
    try:
        service.disconnect_project_repository(principal, project_id)
    except PermissionError as error:
        translate(error)
    return Response(status_code=204)


@app.post("/api/v1/projects/{project_id}/desired-state-publications/{plan_id}")
def create_desired_state_publication(
    project_id: str,
    plan_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("gitops.desired_state_contract").inc()
    try:
        return service.desired_state_publication(principal, project_id, plan_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.post("/api/v1/customer-plan-revisions/{revision_id}/desired-state-publications")
def create_customer_plan_desired_state_publication(
    revision_id: str,
    request: DesiredStatePublicationRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("desired_state.customer_plan_fixture_pr").inc()
    try:
        return service.create_desired_state_publication_for_revision(
            principal, revision_id, request.content_digest
        )
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.post(
    "/api/v1/customer-plan-revisions/{revision_id}/desired-state-publications/{publication_id}/state"
)
def update_customer_plan_desired_state_publication_state(
    revision_id: str,
    publication_id: str,
    request: DesiredStatePublicationStateRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("desired_state.customer_plan_fixture_pr_state").inc()
    try:
        return service.update_desired_state_publication_state(
            principal,
            revision_id,
            publication_id,
            content_digest=request.content_digest,
            state=request.state,
        )
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.post("/api/v1/customer-plan-revisions/{revision_id}/terraform-plan-renders")
def create_customer_plan_terraform_render(
    revision_id: str,
    request: TerraformPlanRenderRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("terraform.customer_plan_render").inc()
    try:
        return service.create_terraform_plan_render_for_revision(
            principal, revision_id, request.content_digest
        )
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.post("/api/v1/customer-plan-revisions/{revision_id}/cloud-readiness-preflights")
def create_customer_plan_cloud_preflight(
    revision_id: str,
    request: CloudReadinessPreflightRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("cloud_readiness.preflight").inc()
    try:
        return service.create_cloud_readiness_preflight(
            principal,
            revision_id,
            content_digest=request.content_digest,
            expected_account_id=request.expected_account_id,
            allowed_regions=request.allowed_regions,
            required_tags=request.required_tags,
            budget_ceiling_usd=request.budget_ceiling_usd,
            execution_mode=request.execution_mode,
            require_reviewed_pr=request.require_reviewed_pr,
            runtime_identity_configured=request.runtime_identity_configured,
        )
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.post("/api/v1/customer-plan-revisions/{revision_id}/terraform-plan-reviews")
def create_customer_plan_terraform_plan_review(
    revision_id: str,
    request: TerraformPlanReviewRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("terraform.customer_plan_review").inc()
    try:
        return service.create_terraform_plan_review_for_revision(
            principal,
            revision_id,
            content_digest=request.content_digest,
            preflight_id=request.preflight_id,
            expected_account_id=request.expected_account_id,
            expected_region=request.expected_region,
            mode=request.mode,
            allow_cloud_plan=request.allow_cloud_plan,
        )
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.post("/api/v1/customer-plan-revisions/{revision_id}/cloud-execution-runs")
def create_customer_plan_cloud_execution_run(
    revision_id: str,
    request: CloudExecutionRunRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("cloud_execution.customer_plan_run").inc()
    try:
        return service.create_cloud_execution_run_for_revision(
            principal,
            revision_id,
            content_digest=request.content_digest,
            terraform_render_id=request.terraform_render_id,
            preflight_id=request.preflight_id,
            terraform_plan_review_id=request.terraform_plan_review_id,
            expected_account_id=request.expected_account_id,
            expected_region=request.expected_region,
            mode=request.mode,
            confirmation=request.confirmation,
        )
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.post("/api/v1/customer-plan-revisions/{revision_id}/customer-image-builds")
def create_customer_image_build(
    revision_id: str,
    request: CloudExecutionRunRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("cloud_execution.customer_image_build").inc()
    try:
        return service.create_customer_image_build_for_revision(
            principal,
            revision_id,
            content_digest=request.content_digest,
            expected_account_id=request.expected_account_id,
            expected_region=request.expected_region,
            confirmation=request.confirmation,
        )
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.get("/api/v1/cloud-execution-runs")
def list_cloud_execution_runs(
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("cloud_execution.runs_list").inc()
    try:
        return service.cloud_execution_runs(principal)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.post("/api/v1/cloud-execution-runs/{run_id}/execute")
def execute_cloud_execution_run(
    run_id: str,
    request: CloudExecutionExecuteRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("cloud_execution.queue").inc()
    try:
        return service.queue_cloud_execution_run(
            principal,
            run_id,
            content_digest=request.content_digest,
            confirmation=request.confirmation,
        )
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.post("/api/v1/cloud-execution-runs/{run_id}/reconcile-result")
def reconcile_cloud_execution_run_result(
    run_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    """Replay a decrypt/read failure for a completed immutable runner result."""
    REQUESTS.labels("cloud_execution.result_reconcile").inc()
    try:
        return service.reconcile_cloud_execution_run_result(principal, run_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.get("/api/v1/cloud-execution-runs/{run_id}/evidence")
def get_cloud_execution_run_evidence(
    run_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("cloud_execution.evidence").inc()
    try:
        return service.cloud_execution_run_evidence(principal, run_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.post("/api/v1/intents", status_code=201)
def create_intent(
    request: IntentRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("intents.create").inc()
    try:
        intent = service.create_intent(
            principal,
            request.project_id,
            request.prompt,
            request.source_repository,
            request.cloud_connection_id,
            request.idempotency_key,
        )
    except (PermissionError, ValueError, KeyError, ModelGatewayUnavailable) as error:
        translate(error)
    return {"id": intent.id, "state": intent.state, "spec": intent.spec}


@app.post("/api/v1/intents/{intent_id}/plans", status_code=201)
def create_plan(
    intent_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("plans.create").inc()
    try:
        plan = service.plan_intent(principal, intent_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)
    PLAN_RESULTS.labels(plan.policy_result).inc()
    return {
        "id": plan.id,
        "state": plan.state,
        "plan_hash": plan.plan_hash,
        "policy_result": plan.policy_result,
        "payload": plan.payload,
    }


@app.post("/api/v1/deployment-plans/{plan_id}/customer-review", status_code=201)
def create_customer_plan_review(
    plan_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("customer_plans.review_create").inc()
    try:
        revision = service.create_customer_plan_review(principal, plan_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)
    review = service.infrastructure_plan_revision_detail(principal, revision.id)
    review["execution"] = "UNEXECUTED_REVIEW_ONLY"
    return review


@app.get("/api/v1/customer-plan-revisions/{revision_id}")
def get_customer_plan_revision(
    revision_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("customer_plans.review_get").inc()
    try:
        return service.infrastructure_plan_revision_detail(principal, revision_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.post("/api/v1/customer-plan-revisions/{revision_id}/submit")
def submit_customer_plan_revision(
    revision_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("customer_plans.submit").inc()
    try:
        revision = service.submit_infrastructure_plan(principal, revision_id)
        return service.infrastructure_plan_revision_detail(principal, revision.id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.post("/api/v1/customer-plan-revisions/{revision_id}/decisions")
def decide_customer_plan_revision(
    revision_id: str,
    request: InfrastructurePlanDecisionRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("customer_plans.decision").inc()
    try:
        revision = service.decide_infrastructure_plan(
            principal, revision_id, request.decision, request.content_digest, request.reason
        )
        return service.infrastructure_plan_revision_detail(principal, revision.id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.post("/api/v1/customer-plan-revisions/{revision_id}/execute-dry-run")
def execute_customer_plan_dry_run(
    revision_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("customer_plans.dry_run_execute").inc()
    try:
        environments = service.execute_customer_plan_dry_run(principal, revision_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)
    for environment in environments:
        EXECUTION_RESULTS.labels(environment.state).inc()
    payloads = [
        service.environment_payload(principal, environment.id) for environment in environments
    ]
    return {
        "execution": "LOCAL_DRY_RUN",
        "boundary": "Queued only against the bounded local fixture executor. No AWS resources are created.",
        "environments": [
            {
                "id": item["id"],
                "name": item["name"],
                "type": item["type"],
                "state": item["state"],
                "execution_mode": item["execution_mode"],
                "cost_estimate": item["cost_estimate"],
                "observed_state": item["observed_state"],
                "outputs": item["outputs"],
                "resources": item["resources"],
            }
            for item in payloads
        ],
    }


@app.post(
    "/api/v1/customer-plan-revisions/{revision_id}/environments/{environment_id}/destroy-dry-run"
)
def destroy_customer_plan_dry_run(
    revision_id: str,
    environment_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("customer_plans.dry_run_destroy").inc()
    try:
        plan = service.customer_plan_destroy_plan(principal, revision_id, environment_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)
    return {
        "id": plan.id,
        "state": plan.state,
        "plan_hash": plan.plan_hash,
        "policy_result": plan.policy_result,
        "action": plan.action,
        "boundary": "Destroy is a separate governed local dry-run action; no AWS resources are deleted.",
    }


@app.post("/api/v1/customer-plans/{plan_id}/revisions", status_code=201)
def revise_customer_plan(
    plan_id: str,
    request: InfrastructurePlanRevisionRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("customer_plans.revise").inc()
    try:
        revision = service.revise_infrastructure_plan(principal, plan_id, request.content)
        return service.infrastructure_plan_revision_detail(principal, revision.id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.post("/api/v1/customer-plans/{plan_id}/constraint-revisions", status_code=201)
def revise_customer_plan_constraints(
    plan_id: str,
    request: InfrastructurePlanConstraintUpdateRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("customer_plans.constraint_revise").inc()
    try:
        revision = service.revise_infrastructure_plan_constraints(
            principal,
            plan_id,
            request.model_dump(mode="json"),
        )
        return service.infrastructure_plan_revision_detail(principal, revision.id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.post("/api/v1/deployment-plans/{plan_id}/approve")
def approve_plan(
    plan_id: str,
    request: ApprovalRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("plans.approve").inc()
    try:
        plan = service.approve(principal, plan_id, request.plan_hash)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)
    return {"id": plan.id, "state": plan.state, "plan_hash": plan.plan_hash}


@app.get("/api/v1/deployment-plans/{plan_id}")
def get_plan(
    plan_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("plans.get").inc()
    try:
        plan = service.get_plan(principal, plan_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)
    return {
        "id": plan.id,
        "state": plan.state,
        "plan_hash": plan.plan_hash,
        "policy_result": plan.policy_result,
        "action": plan.action,
        "payload": plan.payload,
    }


@app.post("/api/v1/deployment-plans/{plan_id}/execute")
def execute_plan(
    plan_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("plans.execute").inc()
    try:
        environments = service.execute(principal, plan_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)
    for environment in environments:
        EXECUTION_RESULTS.labels(environment.state).inc()
    return {
        "environments": [
            {
                "id": item.id,
                "state": item.state,
                "type": item.environment_type,
                "observed_state": item.observed_state,
            }
            for item in environments
        ]
    }


@app.get("/api/v1/environments")
def list_environments(
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("environments.list").inc()
    return service.environment_payloads(principal)


@app.get("/api/v1/environments/{environment_id}")
def get_environment(
    environment_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("environments.get").inc()
    try:
        return service.environment_payload(principal, environment_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.get("/api/v1/environments/{environment_id}/recommendation")
def get_recommendation(
    environment_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("day2.recommendation").inc()
    try:
        return service.recommendation(principal, environment_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.get("/api/v1/environments/{environment_id}/incidents")
def get_incidents(
    environment_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("incidents.list").inc()
    try:
        return [
            {
                "id": incident.id,
                "state": incident.state,
                "summary": incident.summary,
                "evidence": incident.evidence,
                "at": incident.created_at,
            }
            for incident in service.incidents(principal, environment_id)
        ]
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.post("/api/v1/environments/{environment_id}/change-plan", status_code=201)
def create_change_plan(
    environment_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("day2.change_plan").inc()
    try:
        plan = service.change_plan(principal, environment_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)
    PLAN_RESULTS.labels(plan.policy_result).inc()
    return {
        "id": plan.id,
        "state": plan.state,
        "plan_hash": plan.plan_hash,
        "policy_result": plan.policy_result,
        "action": plan.action,
        "payload": plan.payload,
    }


@app.post("/api/v1/environments/{environment_id}/destroy-plan", status_code=201)
def create_destroy_plan(
    environment_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("destroy.plan").inc()
    try:
        plan = service.destroy_plan(principal, environment_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)
    return {
        "id": plan.id,
        "state": plan.state,
        "plan_hash": plan.plan_hash,
        "policy_result": plan.policy_result,
    }


@app.get("/api/v1/audit-events")
def audit_events(
    environment_id: str | None = None,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("audit.list").inc()
    return [
        {
            "actor_subject": item.actor_subject,
            "action": item.action,
            "entity_type": item.entity_type,
            "entity_id": item.entity_id,
            "detail": item.detail,
            "at": item.created_at,
        }
        for item in service.audits(principal, environment_id)
    ]


@app.get("/api/v1/customer-plans/revisions/{revision_id}/comments")
def list_plan_comments(
    revision_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    try:
        comments = service.plan_comments(principal, revision_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)
    return [
        {
            "id": item.id,
            "body": item.body,
            "author_subject": item.author_subject,
            "state": item.state,
            "created_at": item.created_at,
        }
        for item in comments
    ]


@app.post("/api/v1/customer-plans/revisions/{revision_id}/comments", status_code=201)
def add_plan_comment(
    revision_id: str,
    request: PlanCommentRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    try:
        comment = service.add_plan_comment(principal, revision_id, request.body)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)
    return {
        "id": comment.id,
        "body": comment.body,
        "state": comment.state,
        "created_at": comment.created_at,
    }


@app.get("/api/v1/audit-evidence")
def audit_evidence(
    entity_id: str | None = None,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    REQUESTS.labels("audit.evidence").inc()
    return service.audit_evidence(principal, entity_id)
