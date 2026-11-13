"""Fetch and restore the exact approved Nova Terraform plan workspace.

This boundary verifies encrypted, version-pinned objects and restores no
customer-controlled archive entries outside the existing strict Terraform
workspace extractor. It does not request AWS credentials or run Terraform.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from davdeploy.generated_plan_artifacts import GeneratedPlanArtifactError
from davdeploy.generated_terraform_plan import (
    PINNED_AWS_PROVIDER_VERSION,
    PINNED_TERRAFORM_VERSION,
    TerraformPlanExecutionError,
    extract_execution_workspace_bundle,
)
from davdeploy.nova_apply_contract import NovaApplyRequest


class NovaApplyWorkspaceError(RuntimeError):
    """The exact approved plan/workspace could not be restored safely."""


@dataclass(frozen=True)
class PreparedNovaApplyWorkspace:
    root: Path
    saved_plan_path: Path
    terraform_version: str
    aws_provider_version: str
    provider_lockfile_sha256: str


def prepare_nova_apply_workspace(
    request: NovaApplyRequest,
    *,
    s3_client: Any,
    expected_bucket_owner: str,
    expected_kms_key_arn: str,
    workspace_root: str | Path,
    expected_terraform_version: str = PINNED_TERRAFORM_VERSION,
    expected_aws_provider_version: str = PINNED_AWS_PROVIDER_VERSION,
) -> PreparedNovaApplyWorkspace:
    """Download and verify exact artifact versions into a private directory."""
    if not isinstance(request, NovaApplyRequest):
        raise NovaApplyWorkspaceError("Nova apply request was not validated")
    if not re.fullmatch(r"\d{12}", expected_bucket_owner):
        raise NovaApplyWorkspaceError("Nova apply artifact owner is invalid")
    if not re.fullmatch(
        r"arn:aws:kms:[a-z0-9-]+:\d{12}:key/[a-f0-9-]+", expected_kms_key_arn
    ):
        raise NovaApplyWorkspaceError("Nova apply artifact encryption key is invalid")
    if (
        request.saved_plan.bucket != request.execution_workspace.bucket
        or request.saved_plan.bucket != request.manifest["artifact"]["bucket"]
    ):
        raise NovaApplyWorkspaceError("Nova apply artifacts do not share the approved bucket")

    root = Path(workspace_root)
    if root.is_symlink() or root.exists():
        raise NovaApplyWorkspaceError("Nova apply workspace path must be new and private")
    try:
        root.mkdir(parents=True, mode=0o700)
        if root.is_symlink() or not root.is_dir() or stat.S_IMODE(root.stat().st_mode) & 0o077:
            raise NovaApplyWorkspaceError("Nova apply workspace directory is not private")
        plan_path = root / "saved.tfplan"
        archive_path = root / "execution-workspace.tar.gz"
        _download_exact_artifact(
            s3_client,
            bucket=request.saved_plan.bucket,
            key=request.saved_plan.key,
            version_id=request.saved_plan.version_id,
            size_bytes=request.saved_plan.size_bytes,
            expected_sha256=request.saved_plan.sha256,
            expected_run_id=request.tenant.source_plan_run_id,
            expected_bucket_owner=expected_bucket_owner,
            expected_kms_key_arn=expected_kms_key_arn,
            digest_metadata_key="davdeploy-plan-sha256",
            destination=plan_path,
            maximum_bytes=128 * 1024 * 1024,
        )
        _download_exact_artifact(
            s3_client,
            bucket=request.execution_workspace.bucket,
            key=request.execution_workspace.key,
            version_id=request.execution_workspace.version_id,
            size_bytes=request.execution_workspace.size_bytes,
            expected_sha256=request.execution_workspace.sha256,
            expected_run_id=request.tenant.source_plan_run_id,
            expected_bucket_owner=expected_bucket_owner,
            expected_kms_key_arn=expected_kms_key_arn,
            digest_metadata_key="davdeploy-workspace-sha256",
            destination=archive_path,
            maximum_bytes=request.execution_workspace.size_bytes,
        )
        terraform_root = extract_execution_workspace_bundle(
            archive_path,
            root / "terraform",
            expected_sha256=request.execution_workspace.sha256,
        )
        restored_plan = terraform_root / "saved.tfplan"
        if restored_plan.exists() or restored_plan.is_symlink():
            raise NovaApplyWorkspaceError("restored workspace contains an unexpected saved plan")
        # Both paths are created inside the new 0700 worker directory. Moving
        # the already verified 0600 file avoids loading a saved plan (up to
        # 128 MiB) into memory and preserves its restrictive permissions.
        plan_path.replace(restored_plan)
        archive_path.unlink()

        toolchain = request.manifest.get("toolchain")
        if not isinstance(toolchain, dict):
            raise NovaApplyWorkspaceError("approved toolchain binding is unavailable")
        provider_lockfile = terraform_root / ".terraform.lock.hcl"
        lockfile_sha256 = _sha256_file(provider_lockfile)
        if (
            toolchain.get("terraform_version") != expected_terraform_version
            or toolchain.get("aws_provider_version") != expected_aws_provider_version
            or toolchain.get("provider_lockfile_sha256") != lockfile_sha256
        ):
            raise NovaApplyWorkspaceError("restored Terraform toolchain does not match approval")
        return PreparedNovaApplyWorkspace(
            root=terraform_root,
            saved_plan_path=restored_plan,
            terraform_version=expected_terraform_version,
            aws_provider_version=expected_aws_provider_version,
            provider_lockfile_sha256=lockfile_sha256,
        )
    except NovaApplyWorkspaceError:
        raise
    except (GeneratedPlanArtifactError, TerraformPlanExecutionError, OSError, ValueError):
        raise NovaApplyWorkspaceError("approved Terraform artifacts could not be restored safely") from None


def _download_exact_artifact(
    s3_client: Any,
    *,
    bucket: str,
    key: str,
    version_id: str,
    size_bytes: int,
    expected_sha256: str,
    expected_run_id: str,
    expected_bucket_owner: str,
    expected_kms_key_arn: str,
    digest_metadata_key: str,
    destination: Path,
    maximum_bytes: int,
) -> None:
    if (
        not version_id
        or version_id == "null"
        or not re.fullmatch(r"[a-f0-9]{64}", expected_sha256)
        or type(size_bytes) is not int
        or not 0 < size_bytes <= maximum_bytes
        or destination.is_symlink()
        or destination.exists()
    ):
        raise NovaApplyWorkspaceError("approved Terraform artifact reference is invalid")
    try:
        head = s3_client.head_object(
            Bucket=bucket,
            Key=key,
            VersionId=version_id,
            ChecksumMode="ENABLED",
            ExpectedBucketOwner=expected_bucket_owner,
        )
        metadata = head.get("Metadata") if isinstance(head, dict) else None
        if (
            not isinstance(metadata, dict)
            or head.get("VersionId") != version_id
            or head.get("ContentLength") != size_bytes
            or head.get("ServerSideEncryption") != "aws:kms"
            or head.get("SSEKMSKeyId") != expected_kms_key_arn
            or head.get("BucketKeyEnabled") is not True
            or metadata.get(digest_metadata_key) != expected_sha256
            or metadata.get("davdeploy-run-id") != expected_run_id
            or head.get("ChecksumSHA256")
            != base64.b64encode(bytes.fromhex(expected_sha256)).decode("ascii")
        ):
            raise NovaApplyWorkspaceError("approved Terraform artifact metadata did not match")
        response = s3_client.get_object(
            Bucket=bucket,
            Key=key,
            VersionId=version_id,
            ChecksumMode="ENABLED",
            ExpectedBucketOwner=expected_bucket_owner,
        )
        body = response.get("Body") if isinstance(response, dict) else None
        response_metadata = response.get("Metadata") if isinstance(response, dict) else None
        if (
            body is None
            or not isinstance(response_metadata, dict)
            or response.get("VersionId") != version_id
            or response.get("ContentLength") != size_bytes
            or response.get("ServerSideEncryption") != "aws:kms"
            or response.get("SSEKMSKeyId") != expected_kms_key_arn
            or response.get("BucketKeyEnabled") is not True
            or response_metadata.get(digest_metadata_key) != expected_sha256
            or response_metadata.get("davdeploy-run-id") != expected_run_id
        ):
            if body is not None:
                body.close()
            raise NovaApplyWorkspaceError("approved Terraform artifact version did not match")
        digest = hashlib.sha256()
        written = 0
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(destination, flags, 0o600)
        try:
            with body, os.fdopen(descriptor, "wb") as output:
                while chunk := body.read(1024 * 1024):
                    if not isinstance(chunk, bytes):
                        raise NovaApplyWorkspaceError("Terraform artifact stream is invalid")
                    written += len(chunk)
                    if written > maximum_bytes or written > size_bytes:
                        raise NovaApplyWorkspaceError("Terraform artifact exceeds its size limit")
                    digest.update(chunk)
                    output.write(chunk)
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        if written != size_bytes or digest.hexdigest() != expected_sha256:
            destination.unlink(missing_ok=True)
            raise NovaApplyWorkspaceError("Terraform artifact failed its exact digest check")
    except NovaApplyWorkspaceError:
        raise
    except (BotoCoreError, ClientError, OSError, TypeError, ValueError):
        raise NovaApplyWorkspaceError("approved Terraform artifact could not be read safely") from None


def _sha256_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise NovaApplyWorkspaceError("provider lockfile is unavailable")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
