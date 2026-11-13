from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from davdeploy.generated_plan_artifacts import (
    S3GeneratedPlanArtifactStore,
    canonical_json_digest,
)
from davdeploy.nova_apply_contract import (
    NovaApplyContractError,
    validate_nova_apply_request,
)


def _request_document(*, now: datetime | None = None) -> dict:
    current = now or datetime.now(UTC)
    run_id = str(uuid4())
    source_plan_run_id = str(uuid4())
    project = "davdeploy-nova-apply"
    build_arn = f"arn:aws:codebuild:us-east-1:654654474502:build/{project}:build-abc123"
    plan = {
        "bucket": "davdeploy-plans-654654474502",
        "key": S3GeneratedPlanArtifactStore._key(
            "org-1", "project-1", "revision-1", source_plan_run_id, "a" * 64
        ),
        "version_id": "plan-version-1",
        "size_bytes": 512,
        "sha256": "a" * 64,
    }
    workspace = {
        "bucket": "davdeploy-plans-654654474502",
        "key": S3GeneratedPlanArtifactStore._key(
            "org-1",
            "project-1",
            "revision-1",
            source_plan_run_id,
            "b" * 64,
            artifact_kind="workspace",
        ),
        "version_id": "workspace-version-1",
        "size_bytes": 1024,
        "sha256": "b" * 64,
    }
    manifest = {
        "tenant": {
            "organization_id": "org-1",
            "project_id": "project-1",
            "revision_id": "revision-1",
        },
        "target": {"account_id": "654654474502", "region": "us-east-1"},
        "digests": {
            "saved_plan_sha256": plan["sha256"],
            "workspace_sha256": workspace["sha256"],
        },
        "policy": {
            "verdict": "REVIEW_REQUIRED",
            "human_approval_required": True,
        },
        "planning_boundary": {"approval_allowed": True, "execution_allowed": True},
        "pricing": {
            "status": "COMPLETE",
            "region": "us-east-1",
            "evidence_sha256": "c" * 64,
        },
        "artifact": {key: value for key, value in plan.items() if key != "sha256"},
        "execution_workspace": workspace,
    }
    manifest_sha256 = canonical_json_digest(manifest)
    return {
        "contract": "davdeploy.nova-apply-request.v1",
        "run_id": run_id,
        "codebuild_project": project,
        "codebuild_build_arn": build_arn,
        "tenant": {
            "organization_id": "org-1",
            "project_id": "project-1",
            "revision_id": "revision-1",
            "artifact_id": "artifact-1",
            "source_plan_run_id": source_plan_run_id,
        },
        "target_account_id": "654654474502",
        "region": "us-east-1",
        "manifest": deepcopy(manifest),
        "manifest_sha256": manifest_sha256,
        "approval": {
            "approval_id": "approval-1",
            "state": "APPROVED",
            "organization_id": "org-1",
            "project_id": "project-1",
            "revision_id": "revision-1",
            "artifact_id": "artifact-1",
            "approved_manifest_sha256": manifest_sha256,
            "approver_subject": "admin-1",
        },
        "saved_plan": deepcopy(plan),
        "execution_workspace": deepcopy(workspace),
        "authorization": {
            "subject": "admin-1",
            "policy_version": "workspace-authorization-v1",
            "checked_at": current.isoformat(),
            "expires_at": (current + timedelta(minutes=4)).isoformat(),
        },
    }


def _validate(document: dict, *, now: datetime | None = None):
    return validate_nova_apply_request(
        document,
        expected_run_id=document["run_id"],
        expected_codebuild_project="davdeploy-nova-apply",
        expected_codebuild_build_arn=document["codebuild_build_arn"],
        expected_artifact_bucket="davdeploy-plans-654654474502",
        now=now,
    )


def test_accepts_exact_fresh_priced_approval_and_both_artifact_versions():
    document = _request_document()

    accepted = _validate(document)

    assert accepted.run_id == document["run_id"]
    assert accepted.saved_plan.version_id == "plan-version-1"
    assert accepted.execution_workspace.version_id == "workspace-version-1"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda document: document["manifest"]["pricing"].update(status="UNAVAILABLE"),
            "pricing evidence is unavailable",
        ),
        (
            lambda document: document["approval"].update(approved_manifest_sha256="d" * 64),
            "approval does not bind this exact manifest",
        ),
        (
            lambda document: document["execution_workspace"].update(version_id="other-version"),
            "workspace differs from its approved manifest",
        ),
        (
            lambda document: document["manifest"]["planning_boundary"].update(execution_allowed=False),
            "manifest does not permit execution",
        ),
        (
            lambda document: document["approval"].update(state="REVOKED"),
            "contract is invalid",
        ),
    ],
)
def test_rejects_missing_or_mismatched_apply_prerequisite(mutate, message):
    document = _request_document()
    mutate(document)
    if document["manifest"].get("pricing", {}).get("status") == "UNAVAILABLE":
        document["manifest_sha256"] = canonical_json_digest(document["manifest"])
        document["approval"]["approved_manifest_sha256"] = document["manifest_sha256"]
    if document["manifest"]["planning_boundary"].get("execution_allowed") is False:
        document["manifest_sha256"] = canonical_json_digest(document["manifest"])
        document["approval"]["approved_manifest_sha256"] = document["manifest_sha256"]

    with pytest.raises(NovaApplyContractError, match=message):
        _validate(document)


def test_rejects_stale_actor_authorization():
    document = _request_document()
    now = datetime.now(UTC)
    document["authorization"]["checked_at"] = (now - timedelta(minutes=6)).isoformat()
    document["authorization"]["expires_at"] = (now + timedelta(minutes=1)).isoformat()

    with pytest.raises(NovaApplyContractError, match="authorization is stale or expired"):
        _validate(document, now=now)


def test_rejects_wrong_codebuild_run_identity():
    document = _request_document()

    with pytest.raises(NovaApplyContractError, match="run ID does not match"):
        validate_nova_apply_request(
            document,
            expected_run_id=str(uuid4()),
            expected_codebuild_project=document["codebuild_project"],
            expected_codebuild_build_arn=document["codebuild_build_arn"],
            expected_artifact_bucket="davdeploy-plans-654654474502",
        )


def test_rejects_coerced_artifact_sizes_and_unsafe_object_keys():
    document = _request_document()
    document["saved_plan"]["size_bytes"] = "512"
    with pytest.raises(NovaApplyContractError, match="contract is invalid"):
        _validate(document)

    document = _request_document()
    document["execution_workspace"]["key"] = "plans/nova-generated/../other/workspace.tar.gz"
    manifest = document["manifest"]
    manifest["execution_workspace"]["key"] = document["execution_workspace"]["key"]
    document["manifest_sha256"] = canonical_json_digest(manifest)
    document["approval"]["approved_manifest_sha256"] = document["manifest_sha256"]
    with pytest.raises(NovaApplyContractError, match="outside the fixed versioned bucket"):
        _validate(document)
