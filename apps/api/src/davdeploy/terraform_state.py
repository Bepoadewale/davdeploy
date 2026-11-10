"""Bounded primitives for the tenant-isolated Terraform HTTP state backend.

This module deliberately contains no caller-selected S3 key construction and no
Terraform command execution. HTTP handlers and persistence adapters build on
these validated values.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from davdeploy.models import TerraformRemoteState, TerraformStateLock, TerraformStateWrite

MAX_TERRAFORM_STATE_BYTES = 128 * 1024 * 1024
MAX_TERRAFORM_LOCK_BYTES = 16 * 1024
_ACCOUNT_ID = re.compile(r"^[0-9]{12}$")
_REGION = re.compile(r"^[a-z]{2}(?:-[a-z0-9]+)+-\d$")
_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.IGNORECASE
)
_IAM_ROLE_ARN = re.compile(
    r"^arn:(?P<partition>aws(?:-[a-z0-9-]+)?):iam::(?P<account>[0-9]{12}):role/(?P<role>.+)$"
)
_ASSUMED_ROLE_ARN = re.compile(
    r"^arn:(?P<partition>aws(?:-[a-z0-9-]+)?):sts::(?P<account>[0-9]{12}):"
    r"assumed-role/(?P<role>.+)/(?P<session>[^/]+)$"
)


class TerraformStateError(ValueError):
    """A state request is malformed, stale, or outside its trusted boundary."""


class TerraformStateLocked(TerraformStateError):
    """Another live build owns the Terraform state lock."""

    def __init__(self, lock_document: dict[str, Any]) -> None:
        self.lock_document = lock_document
        super().__init__("Terraform state is locked by another plan run")


@dataclass(frozen=True)
class TerraformStateMetadata:
    lineage: str
    serial: int
    sha256: str
    byte_length: int


@dataclass(frozen=True)
class TerraformStateCredentialValue:
    username: str
    password: str


def trusted_codebuild_role_matches(
    actual_principal_arn: str | None, expected_role_arn: str | None
) -> bool:
    """Match an API Gateway IAM caller to one exact configured CodeBuild role."""
    if not isinstance(actual_principal_arn, str) or not isinstance(expected_role_arn, str):
        return False
    expected = _IAM_ROLE_ARN.fullmatch(expected_role_arn)
    actual = _ASSUMED_ROLE_ARN.fullmatch(actual_principal_arn)
    if expected is None or actual is None:
        return False
    return (
        actual.group("partition") == expected.group("partition")
        and actual.group("account") == expected.group("account")
        and actual.group("role") == expected.group("role")
    )


def terraform_state_scope_digest(
    *,
    organization_id: str,
    project_id: str,
    environment_id: str | None,
    target_account_id: str,
    region: str,
) -> str:
    """Return a stable scope digest, refusing ambiguous project-only state."""
    for label, value in (
        ("organization", organization_id),
        ("project", project_id),
        ("environment", environment_id),
    ):
        if not isinstance(value, str) or not _UUID.fullmatch(value):
            raise TerraformStateError(f"trusted {label} identity is required for remote state")
    if not isinstance(target_account_id, str) or not _ACCOUNT_ID.fullmatch(target_account_id):
        raise TerraformStateError("trusted AWS account identity is invalid")
    if not isinstance(region, str) or not _REGION.fullmatch(region):
        raise TerraformStateError("trusted AWS region is invalid")
    document = {
        "contract": "davdeploy.terraform-state-scope.v1",
        "organization_id": organization_id,
        "project_id": project_id,
        "environment_id": environment_id,
        "target_account_id": target_account_id,
        "region": region,
    }
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def parse_terraform_state(raw: bytes) -> TerraformStateMetadata:
    """Validate bounded Terraform state JSON and return only safe metadata."""
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_TERRAFORM_STATE_BYTES:
        raise TerraformStateError("Terraform state is empty or exceeds the size limit")
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise TerraformStateError("Terraform state must be valid UTF-8 JSON") from None
    if not isinstance(document, dict):
        raise TerraformStateError("Terraform state must be a JSON object")
    lineage = document.get("lineage")
    serial = document.get("serial")
    state_version = document.get("version")
    if (
        not isinstance(lineage, str)
        or not _UUID.fullmatch(lineage)
        or isinstance(serial, bool)
        or not isinstance(serial, int)
        or serial < 0
        or isinstance(state_version, bool)
        or not isinstance(state_version, int)
        or state_version < 1
        or not isinstance(document.get("resources"), list)
    ):
        raise TerraformStateError("Terraform state metadata is malformed")
    return TerraformStateMetadata(
        lineage=lineage,
        serial=serial,
        sha256=hashlib.sha256(raw).hexdigest(),
        byte_length=len(raw),
    )


def parse_terraform_lock(raw: bytes) -> tuple[str, dict[str, Any]]:
    """Validate the Terraform HTTP backend lock request body."""
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_TERRAFORM_LOCK_BYTES:
        raise TerraformStateError("Terraform lock request is empty or exceeds the size limit")
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise TerraformStateError("Terraform lock request must be valid JSON") from None
    if not isinstance(document, dict):
        raise TerraformStateError("Terraform lock request must be a JSON object")
    lock_id = document.get("ID")
    if not isinstance(lock_id, str) or not 1 <= len(lock_id) <= 128:
        raise TerraformStateError("Terraform lock ID is missing or invalid")
    if any(
        not isinstance(document.get(key, ""), str)
        for key in ("Operation", "Info", "Who", "Version", "Path")
    ):
        raise TerraformStateError("Terraform lock metadata is malformed")
    created = document.get("Created")
    if not isinstance(created, str) or len(created) > 64:
        raise TerraformStateError("Terraform lock timestamp is malformed")
    return lock_id, document


def validate_terraform_state_lock_id(supplied_lock_id: str | None, active_lock_id: str) -> None:
    """Require the HTTP backend's state update lock ID to match its active lock."""
    if (
        not isinstance(supplied_lock_id, str)
        or not supplied_lock_id
        or not isinstance(active_lock_id, str)
        or not hmac.compare_digest(
            supplied_lock_id.encode("utf-8"), active_lock_id.encode("utf-8")
        )
    ):
        raise TerraformStateError("state update lock ID does not match the active Terraform lock")


def issue_terraform_state_credential() -> tuple[TerraformStateCredentialValue, str]:
    """Create high-entropy Basic Auth credentials and return only a digest for storage."""
    username = secrets.token_urlsafe(24)
    password = secrets.token_urlsafe(48)
    digest = hashlib.sha256(password.encode("ascii")).hexdigest()
    return TerraformStateCredentialValue(username=username, password=password), digest


def credential_matches(
    password: str, digest: str, *, expires_at: datetime, revoked_at: datetime | None
) -> bool:
    """Constant-time credential check with UTC-safe expiry and revocation handling."""
    now = datetime.now(UTC)
    expiry = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
    if revoked_at is not None or expiry <= now:
        return False
    if not isinstance(password, str) or len(password) > 256:
        return False
    candidate = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(candidate, digest)


class TerraformStateStorage:
    """Persist state through versioned KMS-encrypted S3 objects and DB pointers."""

    def __init__(
        self,
        db: Session,
        *,
        s3_client: Any,
        bucket: str,
        kms_key_arn: str,
        expected_bucket_owner: str,
    ) -> None:
        if not bucket or not kms_key_arn or not _ACCOUNT_ID.fullmatch(expected_bucket_owner):
            raise TerraformStateError("Terraform state storage is not configured")
        self.db = db
        self.s3 = s3_client
        self.bucket = bucket
        self.kms_key_arn = kms_key_arn
        self.expected_bucket_owner = expected_bucket_owner

    def read(self, state_id: str) -> bytes | None:
        state = self._state(state_id)
        if not state.latest_object_key or not state.latest_version_id or not state.state_sha256:
            return None
        try:
            response = self.s3.get_object(
                Bucket=self.bucket,
                Key=state.latest_object_key,
                VersionId=state.latest_version_id,
                ExpectedBucketOwner=self.expected_bucket_owner,
            )
            body = response.get("Body")
            if body is None:
                raise TerraformStateError("the exact recorded Terraform state body is unavailable")
            try:
                raw = body.read(MAX_TERRAFORM_STATE_BYTES + 1)
            finally:
                body.close()
        except (BotoCoreError, ClientError, OSError, TypeError, ValueError, AttributeError):
            raise TerraformStateError(
                "the exact recorded Terraform state version is unavailable"
            ) from None
        metadata = response.get("Metadata") if isinstance(response, dict) else None
        parsed = parse_terraform_state(raw)
        if (
            response.get("VersionId") != state.latest_version_id
            or response.get("ServerSideEncryption") != "aws:kms"
            or response.get("SSEKMSKeyId") != self.kms_key_arn
            or not isinstance(metadata, dict)
            or metadata.get("davdeploy-state-id") != state.id
            or metadata.get("davdeploy-state-sha256") != parsed.sha256
            or metadata.get("davdeploy-state-lineage") != parsed.lineage
            or metadata.get("davdeploy-state-serial") != str(parsed.serial)
            or parsed.sha256 != state.state_sha256
            or parsed.lineage != state.lineage
            or parsed.serial != state.serial
        ):
            raise TerraformStateError("the stored Terraform state failed version or digest checks")
        return raw

    def write(
        self,
        *,
        state_id: str,
        run_id: str,
        build_id: str,
        lock_id: str,
        raw: bytes,
    ) -> TerraformStateMetadata:
        state = self._state(state_id)
        metadata = parse_terraform_state(raw)
        lock = self.db.get(TerraformStateLock, state_id)
        lock_expiry = (
            lock.expires_at.replace(tzinfo=UTC)
            if lock and lock.expires_at.tzinfo is None
            else lock.expires_at
            if lock
            else None
        )
        if (
            lock is None
            or lock.lock_id != lock_id
            or lock.run_id != run_id
            or lock.codebuild_build_id != build_id
            or lock_expiry <= datetime.now(UTC)
        ):
            raise TerraformStateError("state write requires this active build's Terraform lock")
        if state.lineage is not None and state.lineage != metadata.lineage:
            raise TerraformStateError("Terraform state lineage changed unexpectedly")
        if state.serial is not None:
            if metadata.serial < state.serial:
                raise TerraformStateError("Terraform state serial would move backwards")
            if metadata.serial == state.serial:
                if metadata.sha256 == state.state_sha256:
                    return metadata
                raise TerraformStateError(
                    "Terraform state serial was reused with different contents"
                )
            if metadata.serial != state.serial + 1:
                raise TerraformStateError("Terraform state serial skipped an expected version")
        elif metadata.serial != 0:
            raise TerraformStateError("initial Terraform state serial must be zero")

        write = self.db.scalar(
            select(TerraformStateWrite).where(
                TerraformStateWrite.state_id == state_id,
                TerraformStateWrite.lineage == metadata.lineage,
                TerraformStateWrite.serial == metadata.serial,
            )
        )
        if write is not None and (
            write.state_sha256 != metadata.sha256
            or write.run_id != run_id
            or write.status not in {"PENDING", "COMMITTED"}
        ):
            raise TerraformStateError("a conflicting Terraform state write already exists")
        if write is None:
            write = TerraformStateWrite(
                state_id=state_id,
                run_id=run_id,
                object_key=f"terraform-state/{state_id}/{secrets.token_hex(24)}.tfstate",
                status="PENDING",
                lineage=metadata.lineage,
                serial=metadata.serial,
                state_sha256=metadata.sha256,
            )
            self.db.add(write)
            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
                write = self.db.scalar(
                    select(TerraformStateWrite).where(
                        TerraformStateWrite.state_id == state_id,
                        TerraformStateWrite.lineage == metadata.lineage,
                        TerraformStateWrite.serial == metadata.serial,
                    )
                )
                if (
                    write is None
                    or write.state_sha256 != metadata.sha256
                    or write.run_id != run_id
                    or write.status not in {"PENDING", "COMMITTED"}
                ):
                    raise TerraformStateError(
                        "a concurrent Terraform state write could not be reconciled"
                    ) from None
        if write.status == "COMMITTED":
            return metadata

        object_metadata = {
            "davdeploy-state-id": state.id,
            "davdeploy-state-sha256": metadata.sha256,
            "davdeploy-state-lineage": metadata.lineage,
            "davdeploy-state-serial": str(metadata.serial),
            "davdeploy-run-id": run_id,
            "davdeploy-build-id-sha256": hashlib.sha256(build_id.encode()).hexdigest(),
        }
        try:
            head = self.s3.head_object(
                Bucket=self.bucket,
                Key=write.object_key,
                ExpectedBucketOwner=self.expected_bucket_owner,
            )
        except ClientError as error:
            error_code = error.response.get("Error", {}).get("Code")
            if error_code not in {"403", "AccessDenied", "404", "NoSuchKey", "NotFound"}:
                raise TerraformStateError(
                    "Terraform state upload could not be reconciled"
                ) from None
            head = None
        except (BotoCoreError, OSError, TypeError, ValueError):
            raise TerraformStateError("Terraform state upload could not be reconciled") from None
        if head is None:
            version_id = None
            for attempt in range(2):
                try:
                    response = self.s3.put_object(
                        Bucket=self.bucket,
                        Key=write.object_key,
                        Body=raw,
                        ContentLength=len(raw),
                        ContentType="application/json",
                        ServerSideEncryption="aws:kms",
                        SSEKMSKeyId=self.kms_key_arn,
                        BucketKeyEnabled=True,
                        ExpectedBucketOwner=self.expected_bucket_owner,
                        Metadata=object_metadata,
                        IfNoneMatch="*",
                    )
                    version_id = response.get("VersionId") if isinstance(response, dict) else None
                    break
                except ClientError as error:
                    error_code = error.response.get("Error", {}).get("Code")
                    status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                    if status == 412 or error_code in {"412", "PreconditionFailed"}:
                        try:
                            head = self.s3.head_object(
                                Bucket=self.bucket,
                                Key=write.object_key,
                                ExpectedBucketOwner=self.expected_bucket_owner,
                            )
                        except (BotoCoreError, ClientError, OSError, TypeError, ValueError):
                            raise TerraformStateError(
                                "conditional Terraform state upload could not be reconciled"
                            ) from None
                        break
                    if (status == 409 or error_code == "ConditionalRequestConflict") and attempt == 0:
                        continue
                    raise TerraformStateError(
                        "Terraform state upload is uncertain; retry this write"
                    ) from None
                except (BotoCoreError, OSError, TypeError, ValueError):
                    raise TerraformStateError(
                        "Terraform state upload is uncertain; retry this write"
                    ) from None
            if head is not None:
                version_id = head.get("VersionId")
                if (
                    not isinstance(version_id, str)
                    or not version_id
                    or head.get("ServerSideEncryption") != "aws:kms"
                    or head.get("SSEKMSKeyId") != self.kms_key_arn
                    or head.get("Metadata") != object_metadata
                ):
                    raise TerraformStateError(
                        "pending Terraform state upload failed reconciliation checks"
                    )
            elif not isinstance(version_id, str) or not version_id:
                raise TerraformStateError("state bucket versioning is required")
        else:
            version_id = head.get("VersionId")
            if (
                not isinstance(version_id, str)
                or not version_id
                or head.get("ServerSideEncryption") != "aws:kms"
                or head.get("SSEKMSKeyId") != self.kms_key_arn
                or head.get("Metadata") != object_metadata
            ):
                raise TerraformStateError(
                    "pending Terraform state upload failed reconciliation checks"
                )

        current_lock = self.db.scalar(
            select(TerraformStateLock)
            .where(
                TerraformStateLock.state_id == state_id,
                TerraformStateLock.lock_id == lock_id,
                TerraformStateLock.run_id == run_id,
                TerraformStateLock.codebuild_build_id == build_id,
            )
            .with_for_update()
        )
        if current_lock is None:
            raise TerraformStateError("Terraform lock changed before state metadata was committed")
        current_expiry = current_lock.expires_at
        if current_expiry.tzinfo is None:
            current_expiry = current_expiry.replace(tzinfo=UTC)
        if current_expiry <= datetime.now(UTC):
            raise TerraformStateError("Terraform state lock expired before commit")

        write.object_version_id = version_id
        write.status = "COMMITTED"
        write.committed_at = datetime.now(UTC)
        state.latest_object_key = write.object_key
        state.latest_version_id = version_id
        state.lineage = metadata.lineage
        state.serial = metadata.serial
        state.state_sha256 = metadata.sha256
        self.db.commit()
        return metadata

    def lock(
        self,
        *,
        state_id: str,
        run_id: str,
        build_id: str,
        raw: bytes,
        expires_at: datetime,
    ) -> dict[str, Any]:
        lock_id, document = parse_terraform_lock(raw)
        if expires_at <= datetime.now(UTC):
            raise TerraformStateError("Terraform lock expiry must be in the future")
        self._state(state_id)
        current = self.db.get(TerraformStateLock, state_id)
        if current:
            if (
                current.lock_id == lock_id
                and current.run_id == run_id
                and current.codebuild_build_id == build_id
            ):
                return current.lock_document
            raise TerraformStateLocked(current.lock_document)
        self.db.add(
            TerraformStateLock(
                state_id=state_id,
                lock_id=lock_id,
                lock_document=document,
                run_id=run_id,
                codebuild_build_id=build_id,
                expires_at=expires_at,
            )
        )
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            current = self.db.get(TerraformStateLock, state_id)
            if current:
                raise TerraformStateLocked(current.lock_document) from None
            raise TerraformStateError("Terraform state lock could not be acquired") from None
        return document

    def unlock(self, *, state_id: str, run_id: str, build_id: str, raw: bytes) -> None:
        lock_id, _ = parse_terraform_lock(raw)
        current = self.db.get(TerraformStateLock, state_id)
        if current is None:
            raise TerraformStateError("Terraform state has no active lock")
        if (
            current.lock_id != lock_id
            or current.run_id != run_id
            or current.codebuild_build_id != build_id
        ):
            raise TerraformStateError("Terraform unlock does not match the active lock owner")
        removed = self.db.execute(
            delete(TerraformStateLock).where(
                TerraformStateLock.state_id == state_id,
                TerraformStateLock.lock_id == lock_id,
                TerraformStateLock.run_id == run_id,
                TerraformStateLock.codebuild_build_id == build_id,
            )
        )
        if removed.rowcount != 1:
            self.db.rollback()
            raise TerraformStateError("Terraform lock changed while it was being released")
        self.db.commit()

    def reclaim_expired_lock(
        self,
        *,
        state_id: str,
        expected_lock_id: str,
        expected_run_id: str,
        expected_build_id: str,
        observed_build_status: str,
    ) -> bool:
        """Release an expired lock only after its exact CodeBuild run is terminal."""
        terminal_statuses = {"SUCCEEDED", "FAILED", "FAULT", "STOPPED", "TIMED_OUT"}
        current = self.db.get(TerraformStateLock, state_id)
        expiry = (
            current.expires_at.replace(tzinfo=UTC)
            if current and current.expires_at.tzinfo is None
            else current.expires_at
            if current
            else None
        )
        if current is None or expiry is None or expiry > datetime.now(UTC):
            return False
        if (
            observed_build_status not in terminal_statuses
            or current.lock_id != expected_lock_id
            or current.run_id != expected_run_id
            or current.codebuild_build_id != expected_build_id
        ):
            raise TerraformStateError("expired lock recovery lacks exact terminal build evidence")
        removed = self.db.execute(
            delete(TerraformStateLock).where(
                TerraformStateLock.state_id == state_id,
                TerraformStateLock.lock_id == expected_lock_id,
                TerraformStateLock.run_id == expected_run_id,
                TerraformStateLock.codebuild_build_id == expected_build_id,
                TerraformStateLock.expires_at == current.expires_at,
            )
        )
        if removed.rowcount != 1:
            self.db.rollback()
            raise TerraformStateError("Terraform lock changed during stale-lock recovery")
        self.db.commit()
        return True

    def _state(self, state_id: str) -> TerraformRemoteState:
        state = self.db.get(TerraformRemoteState, state_id)
        if state is None:
            raise TerraformStateError("Terraform state identity was not found")
        return state
