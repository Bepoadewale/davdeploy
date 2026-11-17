"""Stage exact source-plan artifacts under the active apply build's S3 prefix."""

from __future__ import annotations

import base64
import hashlib
import re
from typing import Any
from urllib.parse import quote

from botocore.exceptions import BotoCoreError, ClientError

from davdeploy.nova_apply_contract import (
    ApplyArtifactObject,
    ApplyWorkspaceObject,
    NovaApplyRequest,
)


class NovaApplyArtifactError(RuntimeError):
    """Exact approved artifacts could not be staged for one apply build."""


def stage_nova_apply_artifacts(
    request: NovaApplyRequest,
    *,
    s3_client: Any,
    expected_bucket_owner: str,
    expected_kms_key_arn: str,
) -> tuple[ApplyArtifactObject, ApplyWorkspaceObject]:
    """Copy the two approved versions to keys readable only by this build."""
    if not isinstance(request, NovaApplyRequest):
        raise NovaApplyArtifactError("Nova apply request was not validated")
    if not re.fullmatch(r"\d{12}", expected_bucket_owner):
        raise NovaApplyArtifactError("Nova apply artifact owner is invalid")
    if not re.fullmatch(r"arn:aws:kms:[a-z0-9-]+:\d{12}:key/[a-f0-9-]+", expected_kms_key_arn):
        raise NovaApplyArtifactError("Nova apply artifact key is invalid")

    objects: list[ApplyArtifactObject | ApplyWorkspaceObject] = []
    for kind, source in (
        ("saved-plan", request.saved_plan),
        ("workspace", request.execution_workspace),
    ):
        key = _staged_key(request.codebuild_build_arn, request.run_id, kind)
        metadata = {
            "davdeploy-run-id": request.run_id,
            "davdeploy-source-run-id": request.tenant.source_plan_run_id,
            "davdeploy-source-version-sha256": hashlib.sha256(
                source.version_id.encode("utf-8")
            ).hexdigest(),
            (
                "davdeploy-plan-sha256" if kind == "saved-plan" else "davdeploy-workspace-sha256"
            ): source.sha256,
        }
        version_id = _stage_one(
            s3_client,
            source=source,
            destination_bucket=source.bucket,
            destination_key=key,
            expected_bucket_owner=expected_bucket_owner,
            expected_kms_key_arn=expected_kms_key_arn,
            expected_source_run_id=request.tenant.source_plan_run_id,
            expected_source_digest_metadata_key=(
                "davdeploy-plan-sha256" if kind == "saved-plan" else "davdeploy-workspace-sha256"
            ),
            metadata=metadata,
        )
        artifact_model = ApplyArtifactObject if kind == "saved-plan" else ApplyWorkspaceObject
        objects.append(
            artifact_model(
                bucket=source.bucket,
                key=key,
                version_id=version_id,
                size_bytes=source.size_bytes,
                sha256=source.sha256,
            )
        )
    return objects[0], objects[1]


def _stage_one(
    s3_client: Any,
    *,
    source: ApplyArtifactObject,
    destination_bucket: str,
    destination_key: str,
    expected_bucket_owner: str,
    expected_kms_key_arn: str,
    expected_source_run_id: str,
    expected_source_digest_metadata_key: str,
    metadata: dict[str, str],
) -> str:
    try:
        source_head = s3_client.head_object(
            Bucket=source.bucket,
            Key=source.key,
            VersionId=source.version_id,
            ChecksumMode="ENABLED",
            ExpectedBucketOwner=expected_bucket_owner,
        )
        if not _matches_source(
            source_head,
            source,
            expected_kms_key_arn,
            expected_source_run_id=expected_source_run_id,
            expected_digest_metadata_key=expected_source_digest_metadata_key,
        ):
            raise NovaApplyArtifactError("approved source artifact metadata did not match")

        try:
            existing = s3_client.head_object(
                Bucket=destination_bucket,
                Key=destination_key,
                ChecksumMode="ENABLED",
                ExpectedBucketOwner=expected_bucket_owner,
            )
        except (BotoCoreError, ClientError):
            existing = None
        if isinstance(existing, dict) and _matches_staged(
            existing, source, metadata, expected_kms_key_arn
        ):
            version_id = existing.get("VersionId")
            if isinstance(version_id, str) and version_id and version_id != "null":
                return version_id

        response = s3_client.copy_object(
            Bucket=destination_bucket,
            Key=destination_key,
            CopySource={
                "Bucket": source.bucket,
                "Key": source.key,
                "VersionId": source.version_id,
            },
            CopySourceIfMatch=source_head.get("ETag"),
            ExpectedBucketOwner=expected_bucket_owner,
            ExpectedSourceBucketOwner=expected_bucket_owner,
            MetadataDirective="REPLACE",
            Metadata=metadata,
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=expected_kms_key_arn,
            BucketKeyEnabled=True,
            ChecksumAlgorithm="SHA256",
        )
        version_id = response.get("VersionId") if isinstance(response, dict) else None
        if not isinstance(version_id, str) or not version_id or version_id == "null":
            raise NovaApplyArtifactError("staged apply artifact has no immutable version")
        staged = s3_client.head_object(
            Bucket=destination_bucket,
            Key=destination_key,
            VersionId=version_id,
            ChecksumMode="ENABLED",
            ExpectedBucketOwner=expected_bucket_owner,
        )
        if not _matches_staged(staged, source, metadata, expected_kms_key_arn):
            raise NovaApplyArtifactError("staged apply artifact failed its exact version check")
        return version_id
    except NovaApplyArtifactError:
        raise
    except (BotoCoreError, ClientError, OSError, TypeError, ValueError):
        raise NovaApplyArtifactError("approved apply artifact could not be staged safely") from None


def _matches_source(
    head: object,
    source: ApplyArtifactObject,
    expected_kms_key_arn: str,
    *,
    expected_source_run_id: str,
    expected_digest_metadata_key: str,
) -> bool:
    return (
        isinstance(head, dict)
        and head.get("VersionId") == source.version_id
        and head.get("ContentLength") == source.size_bytes
        and head.get("ServerSideEncryption") == "aws:kms"
        and head.get("SSEKMSKeyId") == expected_kms_key_arn
        and head.get("BucketKeyEnabled") is True
        and head.get("ChecksumSHA256") == _checksum(source.sha256)
        and (head.get("Metadata") or {}).get(expected_digest_metadata_key) == source.sha256
        and (head.get("Metadata") or {}).get("davdeploy-run-id") == expected_source_run_id
    )


def _matches_staged(
    head: object,
    source: ApplyArtifactObject,
    metadata: dict[str, str],
    expected_kms_key_arn: str,
) -> bool:
    return (
        isinstance(head, dict)
        and head.get("VersionId") not in {None, "", "null"}
        and head.get("ContentLength") == source.size_bytes
        and head.get("ServerSideEncryption") == "aws:kms"
        and head.get("SSEKMSKeyId") == expected_kms_key_arn
        and head.get("BucketKeyEnabled") is True
        and head.get("ChecksumSHA256") == _checksum(source.sha256)
        and all((head.get("Metadata") or {}).get(key) == value for key, value in metadata.items())
    )


def _checksum(sha256: str) -> str:
    return base64.b64encode(bytes.fromhex(sha256)).decode("ascii")


def _staged_key(build_arn: str, run_id: str, kind: str) -> str:
    if kind not in {"saved-plan", "workspace"}:
        raise NovaApplyArtifactError("apply artifact kind is invalid")
    # The build ARN comes from the verified CodeBuild API response; quote all
    # non-path characters so this key cannot escape the exact-build prefix.
    encoded_build_arn = quote(build_arn, safe=":/-_")
    filename = "saved.tfplan" if kind == "saved-plan" else "execution-workspace.tar.gz"
    return (
        "plans/nova-generated/apply-builds/"
        f"{encoded_build_arn}/artifacts/{run_id}/{filename}"
    )
