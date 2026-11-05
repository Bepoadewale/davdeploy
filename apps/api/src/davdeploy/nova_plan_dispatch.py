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

    def __init__(
        self,
        message: str,
        *,
        outcome_uncertain: bool = False,
        phase: str | None = None,
    ):
        super().__init__(message)
        self.outcome_uncertain = outcome_uncertain
        self.phase = phase


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

    _RUN_ID_ENVIRONMENT_VARIABLE = "DAVDEPLOY_NOVA_PLAN_RUN_ID"
    _BUILD_LOOKUP_PAGE_LIMIT = 10

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
            response = self._put_input_object(run_id, key, payload, digest)
        except (BotoCoreError, ClientError, OSError, ValueError, TypeError):
            response = None

        version_id = self._version_id(response)
        if version_id:
            return key, digest, version_id

        # A lost PutObject response can still mean S3 stored the object. Inspect
        # the exact attempt key and accept only our matching run/digest metadata.
        version_id = self.inspect_staged_input(run_id, key, digest)
        if version_id:
            return key, digest, version_id

        # HeadObject confirmed absence, so retry the conditional write once. If
        # another writer wins the race, the next inspection verifies its object.
        try:
            response = self._put_input_object(run_id, key, payload, digest)
        except (BotoCoreError, ClientError, OSError, ValueError, TypeError):
            response = None
        version_id = self._version_id(response)
        if version_id:
            return key, digest, version_id
        version_id = self.inspect_staged_input(run_id, key, digest)
        if version_id:
            return key, digest, version_id
        raise NovaPlanDispatchError(
            "Nova plan input is confirmed absent after one conditional retry",
            phase="input_stage",
        )

    def inspect_staged_input(self, run_id: str, key: str, digest: str) -> str | None:
        """Return the exact stored version, None for confirmed absence, or fail closed."""
        run_id = _validate_run_id(run_id)
        if key != self.input_key(run_id) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise NovaPlanDispatchError(
                "Nova plan input inspection did not match the durable attempt key",
                outcome_uncertain=True,
                phase="input_stage",
            )
        try:
            response = self.s3.head_object(
                Bucket=self.bucket,
                Key=key,
                ExpectedBucketOwner=self.expected_bucket_owner,
            )
        except ClientError as error:
            error_detail = error.response.get("Error") or {}
            error_code = error_detail.get("Code")
            status = (error.response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
            if error_code == "NoSuchBucket":
                raise NovaPlanDispatchError(
                    "Nova plan input bucket could not be inspected; reconcile this attempt",
                    outcome_uncertain=True,
                    phase="input_stage",
                ) from None
            if error_code in {"404", "NoSuchKey", "NotFound"} or status == 404:
                return None
            raise NovaPlanDispatchError(
                "Nova plan input object could not be inspected; reconcile this attempt",
                outcome_uncertain=True,
                phase="input_stage",
            ) from None
        except (BotoCoreError, OSError, TimeoutError, ValueError, TypeError):
            raise NovaPlanDispatchError(
                "Nova plan input object could not be inspected; reconcile this attempt",
                outcome_uncertain=True,
                phase="input_stage",
            ) from None

        if not isinstance(response, dict):
            raise NovaPlanDispatchError(
                "Nova plan input object inspection returned invalid metadata; reconcile this attempt",
                outcome_uncertain=True,
                phase="input_stage",
            )
        metadata = response.get("Metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        if (
            metadata.get("davdeploy-run-id") != run_id
            or metadata.get("davdeploy-input-sha256") != digest
        ):
            raise NovaPlanDispatchError(
                "Nova plan input object metadata does not match this attempt; reconcile it",
                outcome_uncertain=True,
                phase="input_stage",
            )
        version_id = self._version_id(response)
        if not version_id:
            raise NovaPlanDispatchError(
                "Nova plan input object has no immutable version; reconcile this attempt",
                outcome_uncertain=True,
                phase="input_stage",
            )
        return version_id

    def _put_input_object(
        self, run_id: str, key: str, payload: bytes, digest: str
    ) -> dict[str, Any]:
        return self.s3.put_object(
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

    @staticmethod
    def _version_id(response: dict[str, Any] | None) -> str | None:
        version_id = response.get("VersionId") if isinstance(response, dict) else None
        if not isinstance(version_id, str) or not version_id or version_id == "null":
            return None
        return version_id

    def start_build(self, run_id: str, idempotency_token: str) -> NovaPlanBuild:
        run_id = _validate_run_id(run_id)
        if not isinstance(idempotency_token, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,64}", idempotency_token
        ):
            raise NovaPlanDispatchError("Nova plan build idempotency token is invalid")
        try:
            response = self.codebuild.start_build(
                projectName=self.project_name,
                idempotencyToken=idempotency_token,
                environmentVariablesOverride=[
                    {
                        "name": self._RUN_ID_ENVIRONMENT_VARIABLE,
                        "value": run_id,
                        "type": "PLAINTEXT",
                    }
                ],
            )
        except ClientError as error:
            response = error.response if isinstance(error.response, dict) else {}
            error_data = response.get("Error")
            code = (
                str(error_data.get("Code") or "unknown")
                if isinstance(error_data, dict)
                else "unknown"
            )
            metadata = response.get("ResponseMetadata")
            status = metadata.get("HTTPStatusCode") if isinstance(metadata, dict) else None
            if (
                "timeout" in code.casefold()
                or type(status) is not int
                or status == 408
                or not 400 <= status < 500
            ):
                raise NovaPlanDispatchError(
                    f"Nova plan build start outcome is uncertain ({code})",
                    outcome_uncertain=True,
                    phase="build_start",
                ) from None
            raise NovaPlanDispatchError(
                f"Nova plan build was rejected by the configured runner ({code})"
            ) from None
        except (BotoCoreError, OSError, TimeoutError):
            raise NovaPlanDispatchError(
                "Nova plan build start could not be confirmed",
                outcome_uncertain=True,
                phase="build_start",
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
                "Nova plan build identity could not be verified",
                outcome_uncertain=True,
                phase="build_start",
            )
        return NovaPlanBuild(build_id, returned_project, status)

    def find_build_by_run_id(self, run_id: str) -> NovaPlanBuild | None:
        """Find one build by its exact server-owned run-ID override, fail closed otherwise."""
        run_id = _validate_run_id(run_id)
        build_ids: list[str] = []
        next_token: str | None = None
        seen_tokens: set[str] = set()
        complete = False
        try:
            for _ in range(self._BUILD_LOOKUP_PAGE_LIMIT):
                request: dict[str, Any] = {"projectName": self.project_name}
                if next_token:
                    request["nextToken"] = next_token
                page = self.codebuild.list_builds_for_project(**request)
                ids = page.get("ids")
                if not isinstance(ids, list) or any(
                    not isinstance(build_id, str)
                    or not build_id.startswith(f"{self.project_name}:")
                    for build_id in ids
                ):
                    raise NovaPlanDispatchError(
                        "Nova plan build search returned an invalid project result",
                        outcome_uncertain=True,
                        phase="build_start",
                    )
                build_ids.extend(ids)
                next_token = page.get("nextToken")
                if not next_token:
                    complete = True
                    break
                if not isinstance(next_token, str) or next_token in seen_tokens:
                    raise NovaPlanDispatchError(
                        "Nova plan build search pagination could not be confirmed",
                        outcome_uncertain=True,
                        phase="build_start",
                    )
                seen_tokens.add(next_token)
        except NovaPlanDispatchError:
            raise
        except (BotoCoreError, ClientError, OSError, TimeoutError, ValueError, TypeError, AttributeError):
            raise NovaPlanDispatchError(
                "Nova plan build search could not be confirmed",
                outcome_uncertain=True,
                phase="build_start",
            ) from None
        if not complete:
            raise NovaPlanDispatchError(
                "Nova plan build search exceeded its safe pagination limit",
                outcome_uncertain=True,
                phase="build_start",
            )

        matches: list[NovaPlanBuild] = []
        for offset in range(0, len(build_ids), 100):
            batch_ids = build_ids[offset : offset + 100]
            try:
                response = self.codebuild.batch_get_builds(ids=batch_ids)
            except (BotoCoreError, ClientError, OSError, TimeoutError, ValueError, TypeError):
                raise NovaPlanDispatchError(
                    "Nova plan build details could not be confirmed",
                    outcome_uncertain=True,
                    phase="build_start",
                ) from None
            builds = response.get("builds")
            if (
                not isinstance(builds, list)
                or len(builds) != len(batch_ids)
                or response.get("buildsNotFound")
            ):
                raise NovaPlanDispatchError(
                    "Nova plan build search returned incomplete build details",
                    outcome_uncertain=True,
                    phase="build_start",
                )
            for build in builds:
                if not isinstance(build, dict):
                    raise NovaPlanDispatchError(
                        "Nova plan build details could not be checked",
                        outcome_uncertain=True,
                        phase="build_start",
                    )
                build_id = build.get("id")
                if (
                    build.get("projectName") != self.project_name
                    or not isinstance(build_id, str)
                    or not build_id.startswith(f"{self.project_name}:")
                ):
                    raise NovaPlanDispatchError(
                        "Nova plan build search returned another project identity",
                        outcome_uncertain=True,
                        phase="build_start",
                    )
                environment = build.get("environment")
                if not isinstance(environment, dict):
                    raise NovaPlanDispatchError(
                        "Nova plan build environment could not be checked",
                        outcome_uncertain=True,
                        phase="build_start",
                    )
                variables = environment.get("environmentVariables")
                if not isinstance(variables, list):
                    raise NovaPlanDispatchError(
                        "Nova plan build environment could not be checked",
                        outcome_uncertain=True,
                        phase="build_start",
                    )
                if any(not isinstance(variable, dict) for variable in variables):
                    raise NovaPlanDispatchError(
                        "Nova plan build environment could not be checked",
                        outcome_uncertain=True,
                        phase="build_start",
                    )
                run_id_variables = [
                    variable
                    for variable in variables
                    if variable.get("name") == self._RUN_ID_ENVIRONMENT_VARIABLE
                ]
                if len(run_id_variables) > 1:
                    raise NovaPlanDispatchError(
                        "Nova plan build has an ambiguous run-ID override",
                        outcome_uncertain=True,
                        phase="build_start",
                    )
                if run_id_variables and (
                    not isinstance(run_id_variables[0].get("value"), str)
                    or run_id_variables[0].get("type") != "PLAINTEXT"
                ):
                    raise NovaPlanDispatchError(
                        "Nova plan build run-ID override could not be confirmed",
                        outcome_uncertain=True,
                        phase="build_start",
                    )
                if (
                    len(run_id_variables) == 1
                    and run_id_variables[0].get("value") == run_id
                    and run_id_variables[0].get("type") == "PLAINTEXT"
                ):
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
                            "Nova plan build returned an unrecognized status",
                            outcome_uncertain=True,
                            phase="build_start",
                        )
                    matches.append(NovaPlanBuild(build_id, self.project_name, status))

        if len(matches) > 1:
            raise NovaPlanDispatchError(
                "Multiple Nova plan builds matched this exact run ID; reconcile manually",
                outcome_uncertain=True,
                phase="build_start",
            )
        return matches[0] if matches else None

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
