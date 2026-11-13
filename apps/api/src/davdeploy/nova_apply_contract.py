"""Strict contract for a future exact-plan Nova apply CodeBuild request.

This module validates authorization and artifact bindings only. It does not
start CodeBuild, request credentials, or execute Terraform. The apply project
must repeat live authorization immediately before invoking this boundary.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from davdeploy.generated_plan_artifacts import (
    GeneratedPlanArtifactError,
    S3GeneratedPlanArtifactStore,
    canonical_json_digest,
    has_complete_pricing_evidence,
)
from davdeploy.generated_terraform_plan import MAX_EXECUTION_WORKSPACE_BYTES

MAX_AUTHORIZATION_AGE = timedelta(minutes=5)


class StrictApplyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ApplyArtifactObject(StrictApplyModel):
    bucket: str = Field(min_length=3, max_length=255)
    key: str = Field(min_length=1, max_length=2048)
    version_id: str = Field(min_length=1, max_length=1024)
    size_bytes: int = Field(gt=0, le=128 * 1024 * 1024)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ApplyWorkspaceObject(ApplyArtifactObject):
    size_bytes: int = Field(gt=0, le=MAX_EXECUTION_WORKSPACE_BYTES)


class ApplyTenantBinding(StrictApplyModel):
    organization_id: str = Field(min_length=1, max_length=160)
    project_id: str = Field(min_length=1, max_length=160)
    revision_id: str = Field(min_length=1, max_length=160)
    artifact_id: str = Field(min_length=1, max_length=160)
    source_plan_run_id: str


class ApplyApprovalBinding(StrictApplyModel):
    approval_id: str = Field(min_length=1, max_length=160)
    state: Literal["APPROVED"]
    organization_id: str = Field(min_length=1, max_length=160)
    project_id: str = Field(min_length=1, max_length=160)
    revision_id: str = Field(min_length=1, max_length=160)
    artifact_id: str = Field(min_length=1, max_length=160)
    approved_manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    approver_subject: str = Field(min_length=1, max_length=160)


class ApplyAuthorization(StrictApplyModel):
    subject: str = Field(min_length=1, max_length=160)
    policy_version: str = Field(min_length=1, max_length=100)
    checked_at: datetime
    expires_at: datetime


class NovaApplyRequest(StrictApplyModel):
    contract: Literal["davdeploy.nova-apply-request.v1"]
    run_id: str
    codebuild_project: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{1,254}$")
    codebuild_build_arn: str = Field(min_length=1, max_length=512)
    tenant: ApplyTenantBinding
    target_account_id: str = Field(pattern=r"^\d{12}$")
    region: str = Field(pattern=r"^[a-z]{2}(?:-[a-z0-9]+)+-\d$")
    manifest: dict[str, Any]
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    approval: ApplyApprovalBinding
    saved_plan: ApplyArtifactObject
    execution_workspace: ApplyWorkspaceObject
    authorization: ApplyAuthorization


class NovaApplyContractError(ValueError):
    """An apply request is stale, incomplete, or not bound to exact artifacts."""


def validate_nova_apply_request(
    document: object,
    *,
    expected_run_id: str,
    expected_codebuild_project: str,
    expected_codebuild_build_arn: str,
    expected_artifact_bucket: str,
    now: datetime | None = None,
) -> NovaApplyRequest:
    """Validate the only request shape an exact-plan apply worker may accept.

    The caller must obtain this document from the fixed, encrypted control-plane
    input path and revalidate live approval/authorization before running it.
    """
    try:
        request_json = json.dumps(
            document, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        request = NovaApplyRequest.model_validate_json(request_json, strict=True)
    except (ValidationError, TypeError, ValueError):
        raise NovaApplyContractError("Nova apply request contract is invalid") from None

    try:
        if str(UUID(request.run_id)) != request.run_id.lower():
            raise ValueError
        if str(UUID(expected_run_id)) != expected_run_id.lower():
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        raise NovaApplyContractError("Nova apply run identity is invalid") from None
    if request.run_id != expected_run_id:
        raise NovaApplyContractError("Nova apply run ID does not match its fixed build")
    try:
        if str(UUID(request.tenant.source_plan_run_id)) != request.tenant.source_plan_run_id.lower():
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        raise NovaApplyContractError("source plan run identity is invalid") from None
    if (
        request.codebuild_project != expected_codebuild_project
        or request.codebuild_build_arn != expected_codebuild_build_arn
    ):
        raise NovaApplyContractError("Nova apply build identity does not match its fixed project")
    project_match = re.fullmatch(
        r"arn:aws(?:-us-gov|-cn)?:codebuild:[a-z0-9-]+:\d{12}:build/([A-Za-z0-9_-]+):[A-Za-z0-9-]+",
        request.codebuild_build_arn,
    )
    if project_match is None or project_match.group(1) != expected_codebuild_project:
        raise NovaApplyContractError("Nova apply build ARN is invalid")
    if (
        not isinstance(expected_artifact_bucket, str)
        or not expected_artifact_bucket
        or request.saved_plan.bucket != expected_artifact_bucket
        or request.execution_workspace.bucket != expected_artifact_bucket
        or request.saved_plan.version_id == "null"
        or request.execution_workspace.version_id == "null"
        or not _safe_artifact_key(request.saved_plan.key)
        or not _safe_artifact_key(request.execution_workspace.key)
    ):
        raise NovaApplyContractError("Nova apply artifacts are outside the fixed versioned bucket")

    manifest = request.manifest
    if canonical_json_digest(manifest) != request.manifest_sha256:
        raise NovaApplyContractError("Nova apply manifest digest does not match")
    tenant = manifest.get("tenant")
    target = manifest.get("target")
    digests = manifest.get("digests")
    policy = manifest.get("policy")
    boundary = manifest.get("planning_boundary")
    if (
        not isinstance(tenant, dict)
        or not isinstance(target, dict)
        or not isinstance(digests, dict)
        or not isinstance(policy, dict)
        or not isinstance(boundary, dict)
    ):
        raise NovaApplyContractError("Nova apply manifest is incomplete")
    if (
        tenant.get("organization_id") != request.tenant.organization_id
        or tenant.get("project_id") != request.tenant.project_id
        or tenant.get("revision_id") != request.tenant.revision_id
        or target.get("account_id") != request.target_account_id
        or target.get("region") != request.region
    ):
        raise NovaApplyContractError("Nova apply target or tenant does not match its manifest")
    if not has_complete_pricing_evidence(manifest):
        raise NovaApplyContractError("complete regional pricing evidence is unavailable")
    if boundary.get("approval_allowed") is not True or boundary.get("execution_allowed") is not True:
        raise NovaApplyContractError("Nova apply manifest does not permit execution")
    if (
        policy.get("human_approval_required") is not True
        or policy.get("verdict") not in {"REVIEW_REQUIRED", "ELIGIBLE_FOR_HUMAN_REVIEW"}
    ):
        raise NovaApplyContractError("Nova apply manifest policy is not eligible for approval")

    approval = request.approval
    if (
        approval.organization_id != request.tenant.organization_id
        or approval.project_id != request.tenant.project_id
        or approval.revision_id != request.tenant.revision_id
        or approval.artifact_id != request.tenant.artifact_id
        or approval.approved_manifest_sha256 != request.manifest_sha256
    ):
        raise NovaApplyContractError("Nova apply approval does not bind this exact manifest")

    plan_doc = manifest.get("artifact")
    workspace_doc = manifest.get("execution_workspace")
    if not isinstance(plan_doc, dict) or not isinstance(workspace_doc, dict):
        raise NovaApplyContractError("Nova apply manifest artifact references are incomplete")
    if not _artifact_matches(
        plan_doc, request.saved_plan, expected_sha256=digests.get("saved_plan_sha256")
    ):
        raise NovaApplyContractError("Nova apply saved plan differs from its approved manifest")
    if not _artifact_matches(
        workspace_doc,
        request.execution_workspace,
        expected_sha256=digests.get("workspace_sha256"),
    ):
        raise NovaApplyContractError("Nova apply workspace differs from its approved manifest")
    if (
        digests.get("saved_plan_sha256") != request.saved_plan.sha256
        or digests.get("workspace_sha256") != request.execution_workspace.sha256
    ):
        raise NovaApplyContractError("Nova apply artifact digest differs from its approved manifest")
    try:
        plan_build_arn = S3GeneratedPlanArtifactStore._build_arn_from_key(
            request.saved_plan.key
        )
        workspace_build_arn = S3GeneratedPlanArtifactStore._build_arn_from_key(
            request.execution_workspace.key
        )
        expected_plan_key = S3GeneratedPlanArtifactStore._key(
            request.tenant.organization_id,
            request.tenant.project_id,
            request.tenant.revision_id,
            request.tenant.source_plan_run_id,
            request.saved_plan.sha256,
            build_arn=plan_build_arn,
        )
        expected_workspace_key = S3GeneratedPlanArtifactStore._key(
            request.tenant.organization_id,
            request.tenant.project_id,
            request.tenant.revision_id,
            request.tenant.source_plan_run_id,
            request.execution_workspace.sha256,
            build_arn=workspace_build_arn,
            artifact_kind="workspace",
        )
    except (GeneratedPlanArtifactError, TypeError, ValueError):
        raise NovaApplyContractError("Nova apply artifact ownership path is invalid") from None
    if (
        request.saved_plan.key != expected_plan_key
        or request.execution_workspace.key != expected_workspace_key
        or plan_build_arn != workspace_build_arn
    ):
        raise NovaApplyContractError("Nova apply artifacts do not belong to this source plan")

    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        raise NovaApplyContractError("Nova apply validation time must include a timezone")
    checked_at = request.authorization.checked_at
    expires_at = request.authorization.expires_at
    if checked_at.tzinfo is None or expires_at.tzinfo is None:
        raise NovaApplyContractError("Nova apply authorization timestamps must include a timezone")
    checked_at = checked_at.astimezone(UTC)
    expires_at = expires_at.astimezone(UTC)
    current = current.astimezone(UTC)
    if (
        checked_at > current
        or current - checked_at > MAX_AUTHORIZATION_AGE
        or expires_at <= current
        or expires_at - checked_at > MAX_AUTHORIZATION_AGE
    ):
        raise NovaApplyContractError("Nova apply authorization is stale or expired")
    return request


def _artifact_matches(
    document: dict[str, Any], artifact: ApplyArtifactObject, *, expected_sha256: object
) -> bool:
    return (
        document.get("bucket") == artifact.bucket
        and document.get("key") == artifact.key
        and document.get("version_id") == artifact.version_id
        and document.get("size_bytes") == artifact.size_bytes
        and document.get("sha256", expected_sha256) == artifact.sha256
    )


def _safe_artifact_key(key: str) -> bool:
    return (
        key.startswith("plans/nova-generated/")
        and "\\" not in key
        and all(part not in {"", ".", ".."} for part in key.split("/"))
    )
