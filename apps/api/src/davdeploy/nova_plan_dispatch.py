"""Narrow API-side handoff to the isolated Nova plan-only CodeBuild project."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


class NovaPlanDispatchError(RuntimeError):
    """A plan-only request could not be safely staged or dispatched."""

    def __init__(self, message: str, *, outcome_uncertain: bool = False):
        super().__init__(message)
        self.outcome_uncertain = outcome_uncertain


@dataclass(frozen=True)
class NovaPlanBuild:
    build_id: str
    project_name: str
    status: str


class NovaPlanOnlyDispatcher:
    """Upload one encrypted input and start only the preconfigured plan project.

    The application supplies a server-generated run ID as the sole permitted
    CodeBuild environment override. It cannot select buildspec, source, role,
    image, compute, artifacts, or commands.
    """

    def __init__(
        self,
        *,
        project_name: str,
        bucket: str,
        kms_key_arn: str,
        expected_bucket_owner: str,
        s3_client: Any | None = None,
        codebuild_client: Any | None = None,
        max_input_bytes: int = 1_000_000,
        max_result_bytes: int = 1_000_000,
    ):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,254}", project_name):
            raise ValueError("Nova plan project name is invalid")
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
            raise ValueError("Nova plan bucket name is invalid")
        if not re.fullmatch(r"arn:aws:kms:[a-z0-9-]+:\d{12}:key/[a-f0-9-]+", kms_key_arn):
            raise ValueError("Nova plan KMS key must be a concrete key ARN")
        if not re.fullmatch(r"\d{12}", expected_bucket_owner):
            raise ValueError("Nova plan bucket owner is invalid")
        if max_input_bytes < 1 or max_input_bytes > 1_000_000:
            raise ValueError("Nova plan input size limit is invalid")
        if max_result_bytes < 1 or max_result_bytes > 1_000_000:
            raise ValueError("Nova plan result size limit is invalid")
        self.project_name = project_name
        self.bucket = bucket
        self.kms_key_arn = kms_key_arn
        self.expected_bucket_owner = expected_bucket_owner
        self.s3 = s3_client or boto3.client("s3")
        self.codebuild = codebuild_client or boto3.client("codebuild")
        self.max_input_bytes = max_input_bytes
        self.max_result_bytes = max_result_bytes

    @classmethod
    def from_environment(cls) -> NovaPlanOnlyDispatcher | None:
        """Return no dispatcher unless a later reviewed release enables it."""
        if os.getenv("DAVDEPLOY_NOVA_PLAN_RUNNER_READY", "false").lower() != "true":
            return None
        values = {
            "project_name": os.getenv("DAVDEPLOY_NOVA_PLAN_PROJECT", "").strip(),
            "bucket": os.getenv("DAVDEPLOY_NOVA_PLAN_ARTIFACT_BUCKET", "").strip(),
            "kms_key_arn": os.getenv("DAVDEPLOY_NOVA_PLAN_KMS_KEY_ARN", "").strip(),
            "expected_bucket_owner": os.getenv("DAVDEPLOY_NOVA_PLAN_BUCKET_OWNER", "").strip(),
        }
        if any(not value for value in values.values()):
            raise NovaPlanDispatchError("Nova plan runner configuration is incomplete")
        try:
            return cls(**values)
        except ValueError:
            raise NovaPlanDispatchError("Nova plan runner configuration is invalid") from None

    @staticmethod
    def input_key(run_id: str) -> str:
        return f"plans/nova-generated/requests/{_validate_run_id(run_id)}/input.json"

    @staticmethod
    def result_key(run_id: str) -> str:
        return f"plans/nova-generated/requests/{_validate_run_id(run_id)}/result.json"

    def stage_input(self, run_id: str, document: dict[str, Any]) -> tuple[str, str, str]:
        run_id = _validate_run_id(run_id)
        key = self.input_key(run_id)
        payload = _canonical_json(document)
        if len(payload) > self.max_input_bytes:
            raise NovaPlanDispatchError("Nova plan input exceeds its configured size limit")
        digest = hashlib.sha256(payload).hexdigest()
        try:
            response = self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=payload,
                ContentLength=len(payload),
                ContentType="application/json",
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=self.kms_key_arn,
                BucketKeyEnabled=False,
                IfNoneMatch="*",
                ExpectedBucketOwner=self.expected_bucket_owner,
                Metadata={"davdeploy-run-id": run_id, "davdeploy-input-sha256": digest},
            )
        except (BotoCoreError, ClientError, OSError, ValueError, TypeError):
            raise NovaPlanDispatchError("Nova plan input could not be securely stored") from None
        version_id = response.get("VersionId")
        if not isinstance(version_id, str) or not version_id or version_id == "null":
            raise NovaPlanDispatchError("Nova plan input bucket versioning is unavailable")
        return key, digest, version_id

    def start_build(self, run_id: str) -> NovaPlanBuild:
        run_id = _validate_run_id(run_id)
        try:
            response = self.codebuild.start_build(
                projectName=self.project_name,
                environmentVariablesOverride=[
                    {
                        "name": "DAVDEPLOY_NOVA_PLAN_RUN_ID",
                        "value": run_id,
                        "type": "PLAINTEXT",
                    }
                ],
            )
        except ClientError:
            raise NovaPlanDispatchError("Nova plan build was rejected by the configured runner") from None
        except (BotoCoreError, OSError, TimeoutError):
            raise NovaPlanDispatchError(
                "Nova plan build start could not be confirmed", outcome_uncertain=True
            ) from None
        build = response.get("build") or {}
        build_id = build.get("id")
        returned_project = build.get("projectName")
        status = build.get("buildStatus")
        if (
            not isinstance(build_id, str)
            or not build_id.startswith(f"{self.project_name}:")
            or returned_project != self.project_name
            or status not in {"IN_PROGRESS", "QUEUED"}
        ):
            raise NovaPlanDispatchError(
                "Nova plan build identity could not be verified", outcome_uncertain=True
            )
        return NovaPlanBuild(build_id, returned_project, status)

    def describe_build(self, build_id: str) -> NovaPlanBuild:
        if not isinstance(build_id, str) or not build_id.startswith(f"{self.project_name}:"):
            raise NovaPlanDispatchError("Nova plan build identity is invalid")
        try:
            response = self.codebuild.batch_get_builds(ids=[build_id])
        except (BotoCoreError, ClientError):
            raise NovaPlanDispatchError("Nova plan build status could not be checked") from None
        builds = response.get("builds") or []
        if len(builds) != 1:
            raise NovaPlanDispatchError("Nova plan build status is unavailable", outcome_uncertain=True)
        build = builds[0]
        if build.get("id") != build_id or build.get("projectName") != self.project_name:
            raise NovaPlanDispatchError("Nova plan build belongs to a different project")
        status = build.get("buildStatus")
        if status not in {
            "IN_PROGRESS",
            "QUEUED",
            "SUCCEEDED",
            "FAILED",
            "FAULT",
            "STOPPED",
            "TIMED_OUT",
        }:
            raise NovaPlanDispatchError(
                "Nova plan build returned an unrecognized status", outcome_uncertain=True
            )
        return NovaPlanBuild(build_id, self.project_name, status)


def _validate_run_id(run_id: str) -> str:
    try:
        parsed = uuid.UUID(run_id)
    except (AttributeError, ValueError):
        raise NovaPlanDispatchError("Nova plan run identifier is invalid") from None
    if str(parsed) != run_id.lower():
        raise NovaPlanDispatchError("Nova plan run identifier is invalid")
    return str(parsed)


def _canonical_json(document: dict[str, Any]) -> bytes:
    try:
        return json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        raise NovaPlanDispatchError("Nova plan input is not valid JSON") from None
