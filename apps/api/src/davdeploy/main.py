from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import Counter, generate_latest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from davdeploy.connection_secrets import configured_connection_secret_store
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
    AwsExistingRoleRequest,
    AwsQuickCreateRequest,
    BlogCommentRequest,
    BlogPostRequest,
    CloudConnectionRequest,
    CloudExecutionExecuteRequest,
    CloudExecutionRunRequest,
    CloudInventorySnapshotRequest,
    CloudReadinessPreflightRequest,
    DataLifecycleRequestBody,
    DesiredStatePublicationRequest,
    DesiredStatePublicationStateRequest,
    GeneratedPlanArtifactApprovalRequest,
    GeneratedPlanGenerationReconciliationRequest,
    GeneratedPlanInputReconciliationRequest,
    GeneratedPlanRunRequest,
    InfrastructurePlanConstraintUpdateRequest,
    InfrastructurePlanDecisionRequest,
    InfrastructurePlanRevisionRequest,
    IntentRequest,
    InvitationRequest,
    LocalLoginRequest,
    MembershipRoleRequest,
    NovaPlanCredentialRequest,
    OnboardingRequest,
    PlanCommentRequest,
    ProjectRequest,
    SubscriptionRequest,
    SupportTicketRequest,
    SupportTicketStateRequest,
    TerraformPlanRenderRequest,
    TerraformPlanReviewRequest,
    TerraformStateCredentialRequest,
)
from davdeploy.edge_origin import edge_origin_is_authorized
from davdeploy.generated_plan_artifacts import canonical_json_digest
from davdeploy.invitation_email import InvitationDeliveryUnavailable
from davdeploy.model_gateway import ModelGatewayUnavailable
from davdeploy.models import (
    AuditEvent,
    CloudConnection,
    Environment,
    GeneratedPlanRun,
    InfrastructurePlan,
    InfrastructurePlanDecisionRecord,
    InfrastructurePlanRevision,
    TerraformRemoteState,
    TerraformStateCredential,
    TerraformStateLock,
)
from davdeploy.nova_plan_access import NovaPlanAccessError, build_nova_plan_access_policy
from davdeploy.nova_plan_codebuild import NovaPlanBuildError, _validate_input_document
from davdeploy.nova_plan_dispatch import NovaPlanDispatchError, NovaPlanOnlyDispatcher
from davdeploy.product_readiness import security_headers
from davdeploy.rate_limit import SlidingWindowRateLimiter
from davdeploy.security import (
    IdentityClaims,
    Principal,
    issue_local_token,
    verify_identity_token,
    verify_token,
)
from davdeploy.service import ProductService, plan_hash
from davdeploy.telemetry import configure_tracing
from davdeploy.terraform_state import (
    MAX_TERRAFORM_STATE_BYTES,
    TerraformStateError,
    TerraformStateLocked,
    TerraformStateStorage,
    credential_matches,
    issue_terraform_state_credential,
    terraform_state_scope_digest,
    trusted_codebuild_build_id,
    trusted_codebuild_role_matches,
    validate_terraform_state_lock_id,
)

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
GITHUB_WEBHOOK_MAX_BODY_BYTES = 1_000_000
TERRAFORM_HTTP_MAX_BODY_BYTES = 8 * 1024 * 1024
TERRAFORM_BASIC = HTTPBasic(auto_error=False)


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
    is_terraform_state_bootstrap = (
        request.method == "POST"
        and request.url.path == "/api/v1/terraform-state/credentials"
        and trusted_codebuild_role_matches(
            request.headers.get("x-davdeploy-bootstrap-principal"),
            os.getenv("DAVDEPLOY_NOVA_PLAN_ONLY_ROLE_ARN"),
        )
    )
    is_nova_plan_credential_bootstrap = (
        request.method == "POST"
        and request.url.path == "/api/v1/nova-plan/credentials"
        and trusted_codebuild_role_matches(
            request.headers.get("x-davdeploy-bootstrap-principal"),
            os.getenv("DAVDEPLOY_NOVA_PLAN_ONLY_ROLE_ARN"),
        )
    )
    if not (is_terraform_state_bootstrap or is_nova_plan_credential_bootstrap) and not edge_origin_is_authorized(
        request.headers.get("x-davdeploy-edge")
    ):
        return JSONResponse(
            status_code=403,
            content={"detail": "This API is available through the DavDeploy edge endpoint."},
        )
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


def _require_state_environment(
    db: Session, environment_id: str, organization_id: str, project_id: str
) -> None:
    environment = db.get(Environment, environment_id)
    if (
        environment is None
        or environment.organization_id != organization_id
        or environment.project_id != project_id
    ):
        raise HTTPException(403, "Terraform state environment is outside the durable plan tenant")


def _build_matches_generated_plan_run(build: dict, run: GeneratedPlanRun, project: str) -> bool:
    environment = build.get("environment")
    environment_values = (
        environment.get("environmentVariables", []) if isinstance(environment, dict) else []
    )
    run_id = next(
        (
            item.get("value")
            for item in environment_values
            if isinstance(item, dict) and item.get("name") == "DAVDEPLOY_NOVA_PLAN_RUN_ID"
        ),
        None,
    )
    result_metadata = run.result_metadata if isinstance(run.result_metadata, dict) else {}
    return bool(
        run.state == "BUILD_STARTED"
        and run.codebuild_project == project
        and run.codebuild_build_id == build.get("id")
        and run.runner_run_id
        and build.get("projectName") == project
        and build.get("buildStatus") == "IN_PROGRESS"
        and run_id == run.runner_run_id
        and isinstance(build.get("arn"), str)
        and build.get("arn") == result_metadata.get("codebuild_build_arn")
    )


@app.post("/api/v1/terraform-state/credentials", include_in_schema=False)
def issue_terraform_state_credentials(
    body: TerraformStateCredentialRequest,
    request: Request,
    db: Session = Depends(session),
):
    """Issue an ephemeral state credential to the exact active fixed CodeBuild run."""
    if os.getenv("DAVDEPLOY_TERRAFORM_STATE_ENABLED", "false").lower() != "true":
        raise HTTPException(404, "Terraform remote state is not enabled")
    principal_arn = request.headers.get("x-davdeploy-bootstrap-principal")
    expected_role = os.getenv("DAVDEPLOY_NOVA_PLAN_ONLY_ROLE_ARN")
    if not trusted_codebuild_role_matches(principal_arn, expected_role):
        raise HTTPException(403, "Terraform state bootstrap requires the trusted plan-only role")
    expected_project = os.getenv("DAVDEPLOY_NOVA_PLAN_PROJECT", "")
    build_id = trusted_codebuild_build_id(principal_arn, expected_role, expected_project)
    if not expected_project or build_id is None:
        raise HTTPException(403, "CodeBuild identity is invalid")

    run = db.get(GeneratedPlanRun, body.run_id)
    if (
        run is None
        or run.codebuild_build_id != build_id
        or run.codebuild_project != expected_project
        or run.state != "BUILD_STARTED"
        or not run.runner_run_id
    ):
        raise HTTPException(403, "CodeBuild run is not bound to a durable DavDeploy plan request")
    try:
        response = boto3.client("codebuild").batch_get_builds(ids=[build_id])
    except (BotoCoreError, ClientError, TypeError, ValueError):
        raise HTTPException(503, "Could not verify the active plan build") from None
    builds = response.get("builds", []) if isinstance(response, dict) else []
    if len(builds) != 1 or not isinstance(builds[0], dict):
        raise HTTPException(403, "CodeBuild build identity could not be verified")
    if not _build_matches_generated_plan_run(builds[0], run, expected_project):
        raise HTTPException(403, "CodeBuild build is not the active trusted DavDeploy attempt")

    revision = db.get(InfrastructurePlanRevision, run.revision_id)
    content = revision.content if revision and isinstance(revision.content, dict) else {}
    target = content.get("target") if isinstance(content, dict) else None
    request_document = run.request_document if isinstance(run.request_document, dict) else {}
    if not isinstance(target, dict):
        raise HTTPException(409, "Customer revision has no trusted target environment")
    environment_id = target.get("environment_id")
    account_id = target.get("account_id")
    region = target.get("region")
    if (
        account_id != request_document.get("target_account_id")
        or region != request_document.get("region")
        or not isinstance(environment_id, str)
    ):
        raise HTTPException(409, "Customer revision has no stable state environment binding")
    _require_state_environment(db, environment_id, run.organization_id, run.project_id)
    try:
        scope_sha256 = terraform_state_scope_digest(
            organization_id=run.organization_id,
            project_id=run.project_id,
            environment_id=environment_id,
            target_account_id=account_id,
            region=region,
        )
    except ValueError as error:
        raise HTTPException(409, str(error)) from error

    state_base_url = os.getenv("DAVDEPLOY_TERRAFORM_STATE_API_URL", "").rstrip("/")
    if not state_base_url.startswith("https://"):
        raise HTTPException(503, "Terraform state API URL is not configured")
    state = db.scalar(
        select(TerraformRemoteState).where(TerraformRemoteState.scope_sha256 == scope_sha256)
    )
    if state is None:
        state = TerraformRemoteState(
            scope_sha256=scope_sha256,
            organization_id=run.organization_id,
            project_id=run.project_id,
            environment_id=environment_id,
            target_account_id=account_id,
            region=region,
        )
        db.add(state)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            state = db.scalar(
                select(TerraformRemoteState).where(
                    TerraformRemoteState.scope_sha256 == scope_sha256
                )
            )
            if state is None:
                raise HTTPException(503, "Terraform state identity could not be reserved") from None

    issued, password_digest = issue_terraform_state_credential()
    expires_at = datetime.now(UTC) + timedelta(minutes=25)
    build_arn = builds[0].get("arn")
    if not isinstance(principal_arn, str) or len(principal_arn) > 160:
        raise HTTPException(403, "Authenticated CodeBuild identity cannot be recorded safely")
    db.add(
        TerraformStateCredential(
            username=issued.username,
            password_sha256=password_digest,
            state_id=state.id,
            run_id=run.id,
            codebuild_build_id=build_id,
            expires_at=expires_at,
        )
    )
    db.add(
        AuditEvent(
            organization_id=run.organization_id,
            actor_subject=principal_arn,
            action="terraform_state_credentials.issued",
            entity_type="generated_plan_run",
            entity_id=run.id,
            detail={
                "codebuild_build_arn": build_arn,
                "project_id": run.project_id,
                "revision_id": run.revision_id,
                "revision_sha256": run.revision_sha256,
                "state_id": state.id,
                "state_scope_sha256": scope_sha256,
                "target_account_id": account_id,
                "region": region,
            },
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(503, "Terraform state credential could not be issued") from None

    address = f"{state_base_url}/api/v1/terraform-state/{state.id}"
    return {
        "state_id": state.id,
        "scope_sha256": scope_sha256,
        "address": address,
        "lock_address": f"{address}/lock",
        "unlock_address": f"{address}/unlock",
        "username": issued.username,
        "password": issued.password,
        "expires_at": expires_at.isoformat(),
    }


@app.post("/api/v1/nova-plan/credentials", include_in_schema=False)
def issue_nova_plan_role_credentials(
    body: NovaPlanCredentialRequest,
    request: Request,
    db: Session = Depends(session),
):
    """Issue exact proposal-scoped customer-role credentials to one live plan build."""
    if os.getenv("DAVDEPLOY_NOVA_PLAN_CREDENTIAL_BROKER_ENABLED", "false").lower() != "true":
        raise HTTPException(404, "Nova plan credential brokerage is not enabled")
    principal_arn = request.headers.get("x-davdeploy-bootstrap-principal")
    expected_role = os.getenv("DAVDEPLOY_NOVA_PLAN_ONLY_ROLE_ARN")
    project_name = os.getenv("DAVDEPLOY_NOVA_PLAN_PROJECT", "")
    build_id = trusted_codebuild_build_id(principal_arn, expected_role, project_name)
    if not project_name or build_id is None:
        raise HTTPException(403, "CodeBuild project is not the fixed plan-only project")

    run = db.get(GeneratedPlanRun, body.run_id)
    if (
        run is None
        or run.state != "BUILD_STARTED"
        or run.codebuild_project != project_name
        or run.codebuild_build_id != build_id
        or not run.runner_run_id
        or not run.input_key
        or not run.input_version_id
        or not run.input_sha256
        or not run.proposal_sha256
        or not isinstance(run.request_document, dict)
        or canonical_json_digest(run.request_document) != run.request_sha256
    ):
        raise HTTPException(403, "CodeBuild run is not bound to a durable Nova plan request")
    try:
        build_response = boto3.client("codebuild").batch_get_builds(ids=[build_id])
    except (BotoCoreError, ClientError, TypeError, ValueError):
        raise HTTPException(503, "Could not verify the active Nova plan build") from None
    builds = build_response.get("builds", []) if isinstance(build_response, dict) else []
    if (
        len(builds) != 1
        or not isinstance(builds[0], dict)
        or builds[0].get("id") != build_id
        or not _build_matches_generated_plan_run(builds[0], run, project_name)
    ):
        raise HTTPException(403, "CodeBuild build is not the active trusted plan attempt")

    try:
        dispatcher = NovaPlanOnlyDispatcher.from_environment()
        if dispatcher is None:
            raise NovaPlanDispatchError("Nova plan input reader is disabled")
        build_arn = builds[0]["arn"]
        if (
            run.input_key != dispatcher.build_input_key(build_arn)
            or run.result_key != dispatcher.build_result_key(build_arn)
            or (run.result_metadata or {}).get("codebuild_build_arn") != build_arn
        ):
            raise NovaPlanDispatchError("durable artifacts do not match the active build")
        staged_input = dispatcher.read_staged_input_document(
            run.runner_run_id,
            run.input_key,
            run.input_version_id,
            run.input_sha256,
        )
        binding = _validate_input_document(
            staged_input, run.runner_run_id, project_name, build_arn
        )
    except (NovaPlanBuildError, NovaPlanDispatchError, BotoCoreError, ClientError, TypeError, ValueError):
        raise HTTPException(409, "Exact Nova plan input could not be verified") from None
    request_document = run.request_document
    if (
        staged_input.get("control_plane_run_id") != run.id
        or staged_input.get("request_document") != request_document
        or staged_input.get("request_sha256") != run.request_sha256
        or binding["control_plane_run_id"] != run.id
        or binding["proposal_sha256"] != run.proposal_sha256
        or binding["organization_id"] != run.organization_id
        or binding["project_id"] != run.project_id
        or binding["revision_id"] != run.revision_id
        or binding["revision_sha256"] != run.revision_sha256
        or binding["account_id"] != request_document.get("target_account_id")
        or binding["region"] != request_document.get("region")
        or request_document.get("runner_project") != project_name
        or request_document.get("connection_id") != binding["connection_id"]
        or request_document.get("plan_role_arn") != binding["plan_role_arn"]
    ):
        raise HTTPException(409, "Nova plan request bindings do not match this durable run")

    revision = db.get(InfrastructurePlanRevision, run.revision_id)
    plan = db.get(InfrastructurePlan, revision.infrastructure_plan_id) if revision else None
    connection = db.get(CloudConnection, binding["connection_id"])
    latest = (
        db.scalar(
            select(InfrastructurePlanRevision)
            .where(
                InfrastructurePlanRevision.infrastructure_plan_id == plan.id,
                InfrastructurePlanRevision.organization_id == run.organization_id,
            )
            .order_by(InfrastructurePlanRevision.revision_number.desc())
            .limit(1)
        )
        if plan
        else None
    )
    target = (revision.content or {}).get("target", {}) if revision else {}
    if (
        revision is None
        or plan is None
        or binding["plan_id"] != plan.id
        or connection is None
        or revision.organization_id != run.organization_id
        or revision.id != run.revision_id
        or revision.content_digest != run.revision_sha256
        or revision.content_digest != plan_hash(revision.content or {})
        or revision.state not in {"SUBMITTED", "APPROVED"}
        or latest is None
        or latest.id != revision.id
        or plan.organization_id != run.organization_id
        or plan.project_id != run.project_id
        or connection.organization_id != run.organization_id
        or connection.provider != "aws"
        or connection.setup_state != "VERIFIED"
        or connection.plan_role_setup_state != "VERIFIED"
        or connection.account_id != binding["account_id"]
        or connection.plan_role_arn != binding["plan_role_arn"]
        or not connection.external_id_secret_ref
        or target.get("connection_id") != connection.id
        or target.get("account_id") != binding["account_id"]
        or target.get("region") != binding["region"]
    ):
        raise HTTPException(409, "Customer plan role or immutable revision is no longer current")
    if revision.state == "APPROVED":
        decision = db.scalar(
            select(InfrastructurePlanDecisionRecord).where(
                InfrastructurePlanDecisionRecord.revision_id == revision.id,
                InfrastructurePlanDecisionRecord.organization_id == run.organization_id,
            )
        )
        if (
            decision is None
            or decision.decision != "APPROVED"
            or decision.approved_digest != revision.content_digest
        ):
            raise HTTPException(409, "Customer revision approval is no longer current")

    try:
        access_policy = build_nova_plan_access_policy(
            binding["proposal"], account_id=binding["account_id"], region=binding["region"]
        )
        external_id = configured_connection_secret_store().get_external_id(
            connection.external_id_secret_ref
        )
        assumed = boto3.client("sts").assume_role(
            RoleArn=binding["plan_role_arn"],
            RoleSessionName=f"davdeploy-nova-plan-{run.runner_run_id}",
            ExternalId=external_id,
            DurationSeconds=900,
            Policy=json.dumps(
                access_policy.document, sort_keys=True, separators=(",", ":")
            ),
        )
        credentials = assumed.get("Credentials") if isinstance(assumed, dict) else None
        if not isinstance(credentials, dict):
            raise TypeError("temporary credentials are absent")
        session = boto3.Session(
            aws_access_key_id=credentials.get("AccessKeyId"),
            aws_secret_access_key=credentials.get("SecretAccessKey"),
            aws_session_token=credentials.get("SessionToken"),
        )
        identity = session.client("sts").get_caller_identity()
    except NovaPlanAccessError:
        raise HTTPException(403, "Nova proposal exceeds the fixed plan permission profile") from None
    except (BotoCoreError, ClientError, OSError, RuntimeError, TypeError, ValueError):
        raise HTTPException(403, "The exact customer plan role could not be verified") from None
    expected_identity = (
        f"arn:aws:sts::{binding['account_id']}:assumed-role/"
        f"davdeployPlan-{connection.id}/davdeploy-nova-plan-{run.runner_run_id}"
    )
    if (
        not isinstance(identity, dict)
        or identity.get("Account") != binding["account_id"]
        or identity.get("Arn") != expected_identity
        or not isinstance(credentials.get("Expiration"), datetime)
        or credentials["Expiration"].tzinfo is None
    ):
        raise HTTPException(403, "Customer plan role identity did not match the durable run")
    if len(principal_arn) > 160:
        raise HTTPException(403, "Authenticated CodeBuild identity cannot be recorded safely")
    db.add(
        AuditEvent(
            organization_id=run.organization_id,
            actor_subject=principal_arn,
            action="nova_plan_credentials.issued",
            entity_type="generated_plan_run",
            entity_id=run.id,
            detail={
                "codebuild_build_arn": build_arn,
                "project_id": run.project_id,
                "revision_id": run.revision_id,
                "revision_sha256": run.revision_sha256,
                "proposal_sha256": run.proposal_sha256,
                "plan_role_arn": binding["plan_role_arn"],
                "account_id": binding["account_id"],
                "region": binding["region"],
                "policy_version": access_policy.version,
                "policy_sha256": access_policy.sha256,
            },
        )
    )
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Credential issuance could not be recorded safely") from None
    response = {
        "contract": "davdeploy.nova-plan-credentials.v1",
        "role_arn": binding["plan_role_arn"],
        "account_id": binding["account_id"],
        "region": binding["region"],
        "policy_version": access_policy.version,
        "policy_sha256": access_policy.sha256,
        "credentials": {
            "access_key_id": credentials.get("AccessKeyId"),
            "secret_access_key": credentials.get("SecretAccessKey"),
            "session_token": credentials.get("SessionToken"),
            "expires_at": credentials["Expiration"].astimezone(UTC).isoformat(),
        },
    }
    return JSONResponse(response, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})


def _terraform_state_authorization(
    state_id: str,
    credentials: HTTPBasicCredentials | None,
    db: Session,
) -> tuple[TerraformStateCredential, GeneratedPlanRun]:
    if os.getenv("DAVDEPLOY_TERRAFORM_STATE_ENABLED", "false").lower() != "true":
        raise HTTPException(404, "Terraform remote state is not enabled")
    credential = (
        db.scalar(
            select(TerraformStateCredential).where(
                TerraformStateCredential.username == credentials.username
            )
        )
        if credentials
        else None
    )
    if (
        credential is None
        or credential.state_id != state_id
        or not credential_matches(
            credentials.password,
            credential.password_sha256,
            expires_at=credential.expires_at,
            revoked_at=credential.revoked_at,
        )
    ):
        raise HTTPException(
            401,
            "Valid short-lived Terraform state credentials are required",
            headers={"WWW-Authenticate": "Basic"},
        )
    run = db.get(GeneratedPlanRun, credential.run_id)
    if (
        run is None
        or run.state != "BUILD_STARTED"
        or run.codebuild_build_id != credential.codebuild_build_id
        or run.codebuild_project != os.getenv("DAVDEPLOY_NOVA_PLAN_PROJECT")
    ):
        raise HTTPException(401, "Terraform state credentials are no longer active")
    try:
        response = boto3.client("codebuild").batch_get_builds(ids=[credential.codebuild_build_id])
    except (BotoCoreError, ClientError, TypeError, ValueError):
        raise HTTPException(503, "Could not verify the active plan build") from None
    builds = response.get("builds", []) if isinstance(response, dict) else []
    if (
        len(builds) != 1
        or not isinstance(builds[0], dict)
        or builds[0].get("id") != credential.codebuild_build_id
        or builds[0].get("projectName") != run.codebuild_project
        or builds[0].get("buildStatus") != "IN_PROGRESS"
    ):
        raise HTTPException(401, "Terraform state credentials are no longer active")
    return credential, run


def _terraform_state_storage(db: Session) -> TerraformStateStorage:
    try:
        return TerraformStateStorage(
            db,
            s3_client=boto3.client("s3"),
            bucket=os.getenv("DAVDEPLOY_TERRAFORM_STATE_BUCKET", ""),
            kms_key_arn=os.getenv("DAVDEPLOY_TERRAFORM_STATE_KMS_KEY_ARN", ""),
            expected_bucket_owner=os.getenv("DAVDEPLOY_TERRAFORM_STATE_BUCKET_OWNER", ""),
        )
    except TerraformStateError as error:
        raise HTTPException(503, str(error)) from error


def _reclaim_expired_terraform_lock(
    state_id: str, db: Session, storage: TerraformStateStorage
) -> None:
    lock = db.get(TerraformStateLock, state_id)
    if lock is None:
        return
    expiry = lock.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    if expiry > datetime.now(UTC):
        return
    run = db.get(GeneratedPlanRun, lock.run_id)
    if (
        run is None
        or run.codebuild_project != os.getenv("DAVDEPLOY_NOVA_PLAN_PROJECT")
        or run.codebuild_build_id != lock.codebuild_build_id
    ):
        raise HTTPException(409, "Expired Terraform lock has no matching durable build record")
    try:
        response = boto3.client("codebuild").batch_get_builds(ids=[lock.codebuild_build_id])
    except (BotoCoreError, ClientError, TypeError, ValueError):
        raise HTTPException(503, "Could not verify the expired lock owner") from None
    builds = response.get("builds", []) if isinstance(response, dict) else []
    if len(builds) != 1 or not isinstance(builds[0], dict):
        raise HTTPException(409, "Expired Terraform lock owner could not be verified")
    build = builds[0]
    if (
        build.get("id") != lock.codebuild_build_id
        or build.get("projectName") != run.codebuild_project
    ):
        raise HTTPException(409, "Expired Terraform lock owner did not match the exact build")
    try:
        recovered = storage.reclaim_expired_lock(
            state_id=state_id,
            expected_lock_id=lock.lock_id,
            expected_run_id=lock.run_id,
            expected_build_id=lock.codebuild_build_id,
            observed_build_status=build.get("buildStatus", ""),
        )
    except TerraformStateError as error:
        raise HTTPException(409, str(error)) from error
    if not recovered:
        raise HTTPException(409, "Terraform lock expired while recovery was being checked")


async def _bounded_terraform_body(request: Request, maximum: int) -> bytes:
    content_length = request.headers.get("content-length")
    if content_length and (not content_length.isdecimal() or int(content_length) > maximum):
        raise HTTPException(413, "Terraform state request exceeds the size limit")
    body = await request.body()
    if not body or len(body) > maximum:
        raise HTTPException(413, "Terraform state request is empty or exceeds the size limit")
    return body


@app.get("/api/v1/terraform-state/{state_id}", include_in_schema=False)
def read_terraform_state(
    state_id: str,
    credentials: HTTPBasicCredentials | None = Depends(TERRAFORM_BASIC),
    db: Session = Depends(session),
):
    _terraform_state_authorization(state_id, credentials, db)
    try:
        raw = _terraform_state_storage(db).read(state_id)
    except TerraformStateError as error:
        raise HTTPException(503, str(error)) from error
    if raw is None:
        return Response(status_code=404)
    return Response(content=raw, media_type="application/json")


@app.post("/api/v1/terraform-state/{state_id}", include_in_schema=False)
async def write_terraform_state(
    state_id: str,
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(TERRAFORM_BASIC),
    db: Session = Depends(session),
):
    _, run = _terraform_state_authorization(state_id, credentials, db)
    try:
        raw = await _bounded_terraform_body(
            request, min(MAX_TERRAFORM_STATE_BYTES, TERRAFORM_HTTP_MAX_BODY_BYTES)
        )
        lock = db.get(TerraformStateLock, state_id)
        if lock is None:
            raise TerraformStateError("state write requires an active Terraform lock")
        validate_terraform_state_lock_id(request.query_params.get("ID"), lock.lock_id)
        metadata = _terraform_state_storage(db).write(
            state_id=state_id,
            run_id=run.id,
            build_id=run.codebuild_build_id or "",
            lock_id=lock.lock_id,
            raw=raw,
        )
    except TerraformStateLocked as error:
        raise HTTPException(423, error.lock_document) from error
    except TerraformStateError as error:
        raise HTTPException(409, str(error)) from error
    return {"serial": metadata.serial, "lineage": metadata.lineage}


@app.post("/api/v1/terraform-state/{state_id}/lock", include_in_schema=False)
async def lock_terraform_state(
    state_id: str,
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(TERRAFORM_BASIC),
    db: Session = Depends(session),
):
    _, run = _terraform_state_authorization(state_id, credentials, db)
    try:
        raw = await _bounded_terraform_body(request, 16 * 1024)
        storage = _terraform_state_storage(db)
        _reclaim_expired_terraform_lock(state_id, db, storage)
        document = storage.lock(
            state_id=state_id,
            run_id=run.id,
            build_id=run.codebuild_build_id or "",
            raw=raw,
            expires_at=datetime.now(UTC) + timedelta(minutes=20),
        )
    except TerraformStateLocked as error:
        return Response(
            content=json.dumps(error.lock_document),
            status_code=423,
            media_type="application/json",
        )
    except TerraformStateError as error:
        raise HTTPException(409, str(error)) from error
    return Response(content=json.dumps(document), media_type="application/json")


@app.delete("/api/v1/terraform-state/{state_id}/unlock", include_in_schema=False)
async def unlock_terraform_state(
    state_id: str,
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(TERRAFORM_BASIC),
    db: Session = Depends(session),
):
    _, run = _terraform_state_authorization(state_id, credentials, db)
    try:
        raw = await _bounded_terraform_body(request, 16 * 1024)
        _terraform_state_storage(db).unlock(
            state_id=state_id,
            run_id=run.id,
            build_id=run.codebuild_build_id or "",
            raw=raw,
        )
    except TerraformStateError as error:
        raise HTTPException(409, str(error)) from error
    return Response(content="OK", media_type="text/plain")


def translate(error: Exception) -> None:
    if isinstance(error, PermissionError):
        raise HTTPException(403, str(error)) from error
    if isinstance(error, (ValueError, KeyError)):
        raise HTTPException(409, str(error)) from error
    if isinstance(error, ModelGatewayUnavailable):
        raise HTTPException(503, str(error)) from error
    if isinstance(error, NovaPlanDispatchError):
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


@app.get("/api/v1/blog/posts")
def list_public_blog_posts(service: ProductService = Depends(product_service)):
    """Published editorial posts are readable without a workspace account."""
    return service.public_blog_posts()


@app.get("/api/v1/blog/posts/{slug}")
def get_public_blog_post(slug: str, service: ProductService = Depends(product_service)):
    try:
        return service.public_blog_post(slug)
    except KeyError as error:
        translate(error)


@app.get("/api/v1/blog/posts/{slug}/comments")
def list_public_blog_comments(slug: str, service: ProductService = Depends(product_service)):
    try:
        return service.blog_comments(slug)
    except KeyError as error:
        translate(error)


@app.post("/api/v1/blog/posts/{slug}/comments", status_code=201)
def create_public_blog_comment(
    slug: str,
    request: BlogCommentRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    try:
        return service.create_blog_comment(principal, slug, request.body)
    except (PermissionError, KeyError, ValueError) as error:
        translate(error)


@app.patch("/api/v1/blog/comments/{comment_id}")
def edit_public_blog_comment(
    comment_id: str,
    request: BlogCommentRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    try:
        return service.update_blog_comment(principal, comment_id, request.body)
    except (PermissionError, KeyError, ValueError) as error:
        translate(error)


@app.get("/api/v1/blog/author-access")
def blog_author_access(
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    return {"can_publish": service.can_author_blog(principal)}


@app.get("/api/v1/blog/team/posts")
def list_team_blog_posts(
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    try:
        return service.team_blog_posts(principal)
    except PermissionError as error:
        translate(error)


@app.post("/api/v1/blog/team/posts", status_code=201)
def create_team_blog_post(
    request: BlogPostRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    try:
        return service.create_blog_post(principal, request.model_dump())
    except (PermissionError, ValueError) as error:
        translate(error)


@app.patch("/api/v1/blog/team/posts/{post_id}")
def edit_team_blog_post(
    post_id: str,
    request: BlogPostRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    try:
        return service.update_blog_post(principal, post_id, request.model_dump())
    except (PermissionError, KeyError, ValueError) as error:
        translate(error)


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
    return service._support_ticket_response(ticket)


@app.get("/api/v1/support/tickets")
def list_support_tickets(
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    return service.support_tickets(principal)


@app.patch("/api/v1/support/tickets/{ticket_id}")
def update_support_ticket(
    ticket_id: str,
    request: SupportTicketStateRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    try:
        return service.update_support_ticket_state(principal, ticket_id, request.state)
    except (PermissionError, KeyError, ValueError) as error:
        translate(error)


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
    except (PermissionError, ValueError, KeyError, ModelGatewayUnavailable) as error:
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
        if len(body) > GITHUB_WEBHOOK_MAX_BODY_BYTES:
            raise ValueError("GitHub webhook payload is too large")
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
            "plan_role_arn": item.plan_role_arn,
            "plan_role_setup_state": item.plan_role_setup_state,
            "plan_role_policy_status": service.plan_role_policy_status(item),
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
        if (
            request.access_mode == "administrator-pilot"
            and not request.acknowledge_administrator_access
        ):
            raise ValueError(
                "acknowledge administrator access before enabling the deployment pilot"
            )
        return service.aws_quick_create_setup(
            principal, connection_id, request.account_id, request.access_mode
        )
    except (PermissionError, ValueError, KeyError, RuntimeError) as error:
        translate(error)


@app.post("/api/v1/cloud-connections/{connection_id}/aws-existing-role")
def attach_existing_aws_roles(
    connection_id: str,
    request: AwsExistingRoleRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    try:
        return service.aws_existing_role_setup(
            principal,
            connection_id,
            request.account_id,
            request.discovery_role_arn,
            request.execution_role_arn,
        )
    except (PermissionError, ValueError) as error:
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
    except (PermissionError, ValueError, KeyError, ModelGatewayUnavailable) as error:
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
            serverless_operation=request.serverless_operation,
            prior_run_id=request.prior_run_id,
            source_commit=request.source_commit,
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


@app.get("/api/v1/generated-plan-artifacts/{artifact_id}")
def get_generated_plan_artifact(
    artifact_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    """Return safe review evidence only; never return saved-plan bytes or object references."""
    REQUESTS.labels("generated_plan_artifacts.get").inc()
    try:
        return service.generated_plan_artifact_detail(principal, artifact_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.post(
    "/api/v1/customer-plan-revisions/{revision_id}/generated-plan-runs",
    status_code=202,
)
def request_generated_plan_run(
    revision_id: str,
    request: GeneratedPlanRunRequest,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=16, max_length=200),
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    """Queue one exact submitted revision through the separate plan-only project."""
    REQUESTS.labels("generated_plan_runs.create").inc()
    try:
        return service.request_generated_plan_run(
            principal,
            revision_id,
            request.content_digest,
            idempotency_key,
        )
    except (
        PermissionError,
        ValueError,
        KeyError,
        ModelGatewayUnavailable,
        NovaPlanDispatchError,
    ) as error:
        translate(error)


@app.get("/api/v1/generated-plan-runs/{run_id}")
def get_generated_plan_run(
    run_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    """Return safe status for one organization-owned Nova plan request."""
    REQUESTS.labels("generated_plan_runs.get").inc()
    try:
        return service.generated_plan_run_detail(principal, run_id)
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.get("/api/v1/projects/{project_id}/customer-plan-revisions")
def list_customer_plan_revisions(
    project_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None, min_length=1, max_length=36),
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    """List safe customer plan revision summaries for one authorized project."""
    REQUESTS.labels("customer_plans.history").inc()
    try:
        return service.customer_plan_revision_history(
            principal, project_id, limit=limit, cursor=cursor
        )
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.get("/api/v1/projects/{project_id}/generated-plan-runs")
def list_generated_plan_runs(
    project_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None, min_length=1, max_length=36),
    revision_id: str | None = Query(default=None, min_length=1, max_length=36),
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    """List safe Nova plan-run status for one organization-owned project."""
    REQUESTS.labels("generated_plan_runs.list").inc()
    try:
        return service.generated_plan_run_history(
            principal,
            project_id,
            limit=limit,
            cursor=cursor,
            revision_id=revision_id,
        )
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


@app.post("/api/v1/generated-plan-runs/{run_id}/retry", status_code=202)
def retry_generated_plan_run(
    run_id: str,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=16, max_length=200),
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    """Explicitly retry a confirmed failure with a new idempotency key."""
    REQUESTS.labels("generated_plan_runs.retry").inc()
    try:
        return service.retry_generated_plan_run(principal, run_id, idempotency_key)
    except (PermissionError, ValueError, KeyError, NovaPlanDispatchError) as error:
        translate(error)


@app.post("/api/v1/generated-plan-runs/{run_id}/reconcile-input", status_code=202)
def reconcile_generated_plan_input(
    run_id: str,
    request: GeneratedPlanInputReconciliationRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    """Verify a staged input or explicitly abandon that pre-build attempt."""
    REQUESTS.labels("generated_plan_runs.reconcile_input").inc()
    try:
        return service.reconcile_generated_plan_input(
            principal, run_id, abandon_attempt=request.abandon_attempt
        )
    except (PermissionError, ValueError, KeyError, NovaPlanDispatchError) as error:
        translate(error)


@app.post("/api/v1/generated-plan-runs/{run_id}/reconcile-generation", status_code=202)
def abandon_generated_plan_generation_attempt(
    run_id: str,
    request: GeneratedPlanGenerationReconciliationRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    """Explicitly abandon an uncertain or pre-call expired attempt for a fresh retry."""
    REQUESTS.labels("generated_plan_runs.reconcile_generation").inc()
    try:
        return service.abandon_generated_plan_generation_attempt(principal, run_id)
    except (PermissionError, ValueError, KeyError, NovaPlanDispatchError) as error:
        translate(error)


@app.post("/api/v1/generated-plan-runs/{run_id}/reconcile-build", status_code=202)
def reconcile_generated_plan_build_attempt(
    run_id: str,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    """Find one exact CodeBuild attempt after its start response was lost."""
    REQUESTS.labels("generated_plan_runs.reconcile_build").inc()
    try:
        return service.reconcile_generated_plan_build_attempt(principal, run_id)
    except (PermissionError, ValueError, KeyError, NovaPlanDispatchError) as error:
        translate(error)


@app.post("/api/v1/generated-plan-artifacts/{artifact_id}/approve")
def approve_generated_plan_artifact(
    artifact_id: str,
    request: GeneratedPlanArtifactApprovalRequest,
    principal: Principal = Depends(verify_token),
    service: ProductService = Depends(product_service),
):
    """Approve one immutable generated plan by its exact manifest digest."""
    REQUESTS.labels("generated_plan_artifacts.approve").inc()
    try:
        return service.approve_generated_plan_artifact(
            principal, artifact_id, request.manifest_sha256
        )
    except (PermissionError, ValueError, KeyError) as error:
        translate(error)


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
