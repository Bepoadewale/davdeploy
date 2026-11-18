"""Fixed CodeBuild dispatch boundary for exact-plan apply attempts."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import boto3
from botocore.exceptions import BotoCoreError, ClientError


class NovaApplyDispatchError(RuntimeError):
    """An exact-plan apply build could not be safely started or reconciled."""

    def __init__(self, message: str, *, outcome_uncertain: bool = False, phase: str | None = None):
        super().__init__(message)
        self.outcome_uncertain = outcome_uncertain
        self.phase = phase


@dataclass(frozen=True)
class NovaApplyBuild:
    build_id: str
    project_name: str
    status: str
    run_id: str
    build_arn: str


class NovaExactPlanApplyDispatcher:
    """Start only the configured apply project with its durable run ID."""

    _RUN_ID_ENV = "DAVDEPLOY_NOVA_APPLY_RUN_ID"
    _MAX_LOOKUP_PAGES = 10
    _MAX_RESULT_BYTES = 64 * 1024

    def __init__(
        self,
        *,
        project_name: str,
        codebuild_client: Any | None = None,
        s3_client: Any | None = None,
        artifact_bucket: str | None = None,
        expected_bucket_owner: str | None = None,
        kms_key_arn: str | None = None,
    ):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,254}", project_name):
            raise ValueError("Nova apply project name is invalid")
        self.project_name = project_name
        self.codebuild = codebuild_client or boto3.client("codebuild")
        self.s3 = s3_client
        self.artifact_bucket = artifact_bucket
        self.expected_bucket_owner = expected_bucket_owner
        self.kms_key_arn = kms_key_arn

    @classmethod
    def from_environment(cls) -> NovaExactPlanApplyDispatcher | None:
        if os.getenv("DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_RUNNER_READY", "false").lower() != "true":
            return None
        project_name = os.getenv("DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_PROJECT", "").strip()
        if not project_name:
            raise NovaApplyDispatchError("Nova exact-plan apply project is not configured")
        artifact_bucket = os.getenv("DAVDEPLOY_NOVA_PLAN_ARTIFACT_BUCKET", "").strip()
        expected_bucket_owner = os.getenv("DAVDEPLOY_NOVA_APPLY_BUCKET_OWNER", "").strip()
        kms_key_arn = os.getenv("DAVDEPLOY_NOVA_APPLY_KMS_KEY_ARN", "").strip()
        if (
            not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", artifact_bucket)
            or not re.fullmatch(r"\d{12}", expected_bucket_owner)
            or not re.fullmatch(r"arn:aws:kms:[a-z0-9-]+:\d{12}:key/[a-f0-9-]+", kms_key_arn)
        ):
            raise NovaApplyDispatchError("Nova exact-plan apply artifact configuration is invalid")
        try:
            return cls(
                project_name=project_name,
                s3_client=boto3.client(
                    "s3", region_name=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
                ),
                artifact_bucket=artifact_bucket,
                expected_bucket_owner=expected_bucket_owner,
                kms_key_arn=kms_key_arn,
            )
        except ValueError:
            raise NovaApplyDispatchError("Nova exact-plan apply configuration is invalid") from None

    def read_result(
        self,
        run_id: str,
        request_document: dict[str, Any],
        expected_build_id: str,
        expected_build_arn: str,
        *,
        expected_state_id: str,
        expected_state_scope_sha256: str,
        expected_account_id: str,
        expected_region: str,
    ) -> tuple[dict[str, Any], str, str]:
        """Read and verify the immutable result for one exact successful build."""
        run_id = _canonical_run_id(run_id)
        expected_build_arn = _validate_build_arn(expected_build_arn, expected_build_id)
        if (
            not isinstance(expected_build_id, str)
            or not expected_build_id.startswith(f"{self.project_name}:")
            or not isinstance(request_document, dict)
            or request_document.get("manifest_sha256") is None
            or self.s3 is None
            or not self.artifact_bucket
            or not self.expected_bucket_owner
            or not self.kms_key_arn
            or expected_build_arn.split(":")[4] != self.expected_bucket_owner
        ):
            raise NovaApplyDispatchError("Nova apply result verification configuration is invalid")
        key = f"plans/nova-generated/apply-builds/{expected_build_arn}/result.json"
        try:
            response = self.s3.get_object(
                Bucket=self.artifact_bucket,
                Key=key,
                ExpectedBucketOwner=self.expected_bucket_owner,
                ChecksumMode="ENABLED",
            )
            body = response.get("Body")
            if body is None:
                raise NovaApplyDispatchError("Nova apply result body is unavailable")
            try:
                raw = body.read(self._MAX_RESULT_BYTES + 1)
            finally:
                body.close()
        except NovaApplyDispatchError:
            raise
        except (BotoCoreError, ClientError, OSError, ValueError, TypeError, AttributeError):
            raise NovaApplyDispatchError(
                "Nova apply result could not be read", outcome_uncertain=True, phase="result_read"
            ) from None
        if not isinstance(response, dict) or not isinstance(raw, bytes):
            raise NovaApplyDispatchError("Nova apply result response has an invalid shape")
        digest_bytes = hashlib.sha256(raw).digest()
        digest = digest_bytes.hex()
        version_id = response.get("VersionId")
        metadata = response.get("Metadata")
        expected_checksum = base64.b64encode(digest_bytes).decode("ascii")
        if (
            not isinstance(version_id, str)
            or not version_id
            or version_id == "null"
            or len(raw) > self._MAX_RESULT_BYTES
            or response.get("ContentLength") != len(raw)
            or response.get("ChecksumSHA256") != expected_checksum
            or response.get("ServerSideEncryption") != "aws:kms"
            or response.get("SSEKMSKeyId") != self.kms_key_arn
            or response.get("BucketKeyEnabled") is not True
            or not isinstance(metadata, dict)
            or metadata.get("davdeploy-run-id") != run_id
            or metadata.get("davdeploy-build-id") != expected_build_id
            or metadata.get("davdeploy-result-sha256") != digest
        ):
            raise NovaApplyDispatchError(
                "Nova apply result metadata did not match this exact build",
                outcome_uncertain=True,
                phase="result_read",
            )
        try:
            result = json.loads(raw)
            if not isinstance(result, dict) or _canonical_json(result) != raw:
                raise ValueError("non-canonical result")
        except (json.JSONDecodeError, TypeError, ValueError):
            raise NovaApplyDispatchError(
                "Nova apply result is not canonical JSON",
                outcome_uncertain=True,
                phase="result_read",
            ) from None
        saved_plan = request_document.get("saved_plan")
        execution_workspace = request_document.get("execution_workspace")
        expected_fields = {
            "contract": "davdeploy.nova-apply-result.v1",
            "run_id": run_id,
            "codebuild_project": self.project_name,
            "codebuild_build_id": expected_build_id,
            "codebuild_build_arn": expected_build_arn,
            "source_plan_run_id": request_document.get("source_plan_run_id"),
            "manifest_sha256": request_document.get("manifest_sha256"),
            "saved_plan_sha256": saved_plan.get("sha256") if isinstance(saved_plan, dict) else None,
            "execution_workspace_sha256": (
                execution_workspace.get("sha256")
                if isinstance(execution_workspace, dict)
                else None
            ),
            "state_id": expected_state_id,
            "state_scope_sha256": expected_state_scope_sha256,
            "account_id": expected_account_id,
            "region": expected_region,
            "execution_status": "APPLIED_UNVERIFIED",
        }
        if any(result.get(name) != expected for name, expected in expected_fields.items()):
            raise NovaApplyDispatchError(
                "Nova apply result did not match its approved run and saved plan",
                outcome_uncertain=True,
                phase="result_read",
            )
        if set(result) != set(expected_fields) | {
            "started_at",
            "finished_at",
            "terraform_version",
            "aws_provider_version",
        }:
            raise NovaApplyDispatchError("Nova apply result contract has unexpected fields")
        try:
            started_at = datetime.fromisoformat(result["started_at"])
            finished_at = datetime.fromisoformat(result["finished_at"])
            if (
                started_at.tzinfo is None
                or finished_at.tzinfo is None
                or finished_at < started_at
                or not isinstance(result["terraform_version"], str)
                or not result["terraform_version"]
                or not isinstance(result["aws_provider_version"], str)
                or not result["aws_provider_version"]
            ):
                raise ValueError
        except (AttributeError, TypeError, ValueError):
            raise NovaApplyDispatchError(
                "Nova apply result execution metadata is invalid",
                outcome_uncertain=True,
                phase="result_read",
            ) from None
        return result, version_id, digest

    @staticmethod
    def result_key(build_arn: str) -> str:
        validated = _validate_build_arn(build_arn, build_arn.rsplit("/", 1)[-1])
        return f"plans/nova-generated/apply-builds/{validated}/result.json"

    def start_build(self, run_id: str, idempotency_token: str) -> NovaApplyBuild:
        run_id = _canonical_run_id(run_id)
        if not re.fullmatch(r"[a-f0-9]{64}", idempotency_token):
            raise ValueError("Nova apply idempotency token is invalid")
        try:
            response = self.codebuild.start_build(
                projectName=self.project_name,
                idempotencyToken=idempotency_token,
                environmentVariablesOverride=[
                    {"name": self._RUN_ID_ENV, "value": run_id, "type": "PLAINTEXT"}
                ],
            )
        except (BotoCoreError, ClientError, OSError, TimeoutError, TypeError, ValueError):
            raise NovaApplyDispatchError(
                "Nova apply build start outcome is unconfirmed; reconcile the durable run",
                outcome_uncertain=True,
                phase="build_start",
            ) from None
        build = response.get("build") if isinstance(response, dict) else None
        if not isinstance(build, dict):
            raise NovaApplyDispatchError(
                "Nova apply build response is incomplete; reconcile the durable run",
                outcome_uncertain=True,
                phase="build_start",
            )
        return self._parse_build(build, expected_run_id=run_id)

    def describe_build(self, build_id: str) -> NovaApplyBuild:
        project_prefix = f"{self.project_name}:"
        if not isinstance(build_id, str) or not build_id.startswith(project_prefix):
            raise ValueError("Nova apply build ID does not match its fixed project")
        try:
            response = self.codebuild.batch_get_builds(ids=[build_id])
        except (BotoCoreError, ClientError, OSError, TimeoutError, TypeError, ValueError):
            raise NovaApplyDispatchError(
                "Nova apply build status is unavailable; reconcile the durable run",
                outcome_uncertain=True,
                phase="build_status",
            ) from None
        builds = response.get("builds", []) if isinstance(response, dict) else []
        if not isinstance(builds, list) or len(builds) != 1 or not isinstance(builds[0], dict):
            raise NovaApplyDispatchError(
                "Nova apply build identity could not be confirmed",
                outcome_uncertain=True,
                phase="build_status",
            )
        return self._parse_build(builds[0])

    def find_build_by_run_id(self, run_id: str) -> NovaApplyBuild | None:
        run_id = _canonical_run_id(run_id)
        build_ids: list[str] = []
        seen_build_ids: set[str] = set()
        seen_tokens: set[str] = set()
        next_token: str | None = None
        complete = False
        matches: list[NovaApplyBuild] = []
        try:
            for _ in range(self._MAX_LOOKUP_PAGES):
                request: dict[str, Any] = {
                    "projectName": self.project_name,
                    "sortOrder": "DESCENDING",
                }
                if next_token:
                    request["nextToken"] = next_token
                page = self.codebuild.list_builds_for_project(**request)
                ids = page.get("ids") if isinstance(page, dict) else None
                if not isinstance(ids, list) or any(
                    not isinstance(build_id, str)
                    or not build_id.startswith(f"{self.project_name}:")
                    for build_id in ids
                ):
                    raise TypeError
                if len(set(ids)) != len(ids) or seen_build_ids.intersection(ids):
                    raise ValueError
                build_ids.extend(ids)
                seen_build_ids.update(ids)
                next_token = page.get("nextToken")
                if next_token is None:
                    complete = True
                    break
                if not isinstance(next_token, str) or not next_token or next_token in seen_tokens:
                    raise ValueError
                seen_tokens.add(next_token)
            if not complete:
                raise NovaApplyDispatchError(
                    "Nova apply build lookup exceeded its bounded search",
                    outcome_uncertain=True,
                    phase="build_start",
                )

            for offset in range(0, len(build_ids), 100):
                batch_ids = build_ids[offset : offset + 100]
                response = self.codebuild.batch_get_builds(ids=batch_ids)
                builds = response.get("builds") if isinstance(response, dict) else None
                builds_not_found = (
                    response.get("buildsNotFound") if isinstance(response, dict) else None
                )
                if (
                    not isinstance(builds, list)
                    or len(builds) != len(batch_ids)
                    or builds_not_found not in (None, [])
                ):
                    raise TypeError
                expected_ids = set(batch_ids)
                returned_ids: set[str] = set()
                for build in builds:
                    if not isinstance(build, dict):
                        raise TypeError
                    build_id = build.get("id")
                    if (
                        not isinstance(build_id, str)
                        or build_id not in expected_ids
                        or build_id in returned_ids
                        or build.get("projectName") != self.project_name
                    ):
                        raise ValueError
                    parsed = self._parse_build(build)
                    returned_ids.add(build_id)
                    if parsed.run_id == run_id:
                        matches.append(parsed)
                if returned_ids != expected_ids:
                    raise ValueError
        except NovaApplyDispatchError:
            raise
        except (
            BotoCoreError,
            ClientError,
            OSError,
            TimeoutError,
            TypeError,
            ValueError,
            AttributeError,
        ):
            raise NovaApplyDispatchError(
                "Nova apply build lookup is inconclusive; reconcile the durable run",
                outcome_uncertain=True,
                phase="build_start",
            ) from None
        if len(matches) > 1:
            raise NovaApplyDispatchError(
                "multiple Nova apply builds matched one durable run",
                outcome_uncertain=True,
                phase="build_start",
            )
        return matches[0] if matches else None

    def _parse_build(
        self, build: dict[str, Any], *, expected_run_id: str | None = None
    ) -> NovaApplyBuild:
        build_id = build.get("id")
        build_arn = build.get("arn")
        if build.get("projectName") != self.project_name:
            raise ValueError("Nova apply build project did not match")
        if not isinstance(build_id, str):
            raise TypeError("Nova apply build ID is invalid")
        if not build_id.startswith(f"{self.project_name}:"):
            raise ValueError("Nova apply build ID did not match")
        if not isinstance(build_arn, str):
            raise TypeError("Nova apply build ARN is invalid")
        match = re.fullmatch(
            r"arn:aws(?:-us-gov|-cn)?:codebuild:[a-z0-9-]+:\d{12}:build/([A-Za-z0-9_-]+):([A-Za-z0-9-]+)",
            build_arn,
        )
        if match is None or match.group(1) != self.project_name:
            raise ValueError("Nova apply build ARN did not match its fixed project")
        if build_id != f"{self.project_name}:{match.group(2)}":
            raise ValueError("Nova apply build ID and ARN did not match")
        environment = build.get("environment")
        variables = (
            environment.get("environmentVariables") if isinstance(environment, dict) else None
        )
        if not isinstance(variables, list) or any(not isinstance(item, dict) for item in variables):
            raise ValueError("Nova apply build environment is invalid")
        run_id_values = [
            item.get("value") for item in variables if item.get("name") == self._RUN_ID_ENV
        ]
        if len(run_id_values) != 1:
            raise ValueError("Nova apply build durable identity is ambiguous")
        run_id = run_id_values[0]
        try:
            run_id = _canonical_run_id(run_id)
        except (TypeError, ValueError):
            raise ValueError("Nova apply build has no durable run identity") from None
        if expected_run_id is not None and run_id != expected_run_id:
            raise NovaApplyDispatchError(
                "Nova apply build did not preserve its durable run identity",
                outcome_uncertain=True,
                phase="build_start",
            )
        status = build.get("buildStatus")
        if not isinstance(status, str) or not status:
            raise ValueError("Nova apply build status is missing")
        return NovaApplyBuild(build_id, self.project_name, status, run_id, build_arn)


def _canonical_run_id(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("Nova apply run ID is invalid")
    try:
        canonical = str(UUID(value))
    except (AttributeError, TypeError, ValueError):
        raise ValueError("Nova apply run ID is invalid") from None
    if canonical != value:
        raise ValueError("Nova apply run ID is not canonical")
    return canonical


def _validate_build_arn(value: object, expected_build_id: str) -> str:
    if (
        not isinstance(value, str)
        or not re.fullmatch(
            r"arn:aws(?:-us-gov|-cn)?:codebuild:[a-z0-9-]+:\d{12}:build/[A-Za-z0-9_-]+:[A-Za-z0-9-]+",
            value,
        )
        or not isinstance(expected_build_id, str)
        or not value.endswith(f":build/{expected_build_id}")
    ):
        raise NovaApplyDispatchError("Nova apply CodeBuild ARN is invalid")
    return value


def _canonical_json(document: dict[str, Any]) -> bytes:
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
