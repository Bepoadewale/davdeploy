"""Fixed CodeBuild dispatch boundary for exact-plan apply attempts."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
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

    def __init__(self, *, project_name: str, codebuild_client: Any | None = None):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,254}", project_name):
            raise ValueError("Nova apply project name is invalid")
        self.project_name = project_name
        self.codebuild = codebuild_client or boto3.client("codebuild")

    @classmethod
    def from_environment(cls) -> NovaExactPlanApplyDispatcher | None:
        if os.getenv("DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_RUNNER_READY", "false").lower() != "true":
            return None
        project_name = os.getenv("DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_PROJECT", "").strip()
        if not project_name:
            raise NovaApplyDispatchError("Nova exact-plan apply project is not configured")
        try:
            return cls(project_name=project_name)
        except ValueError:
            raise NovaApplyDispatchError("Nova exact-plan apply configuration is invalid") from None

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
        matches: list[NovaApplyBuild] = []
        next_token: str | None = None
        try:
            for _ in range(self._MAX_LOOKUP_PAGES):
                request: dict[str, Any] = {
                    "projectName": self.project_name,
                    "sortOrder": "DESCENDING",
                }
                if next_token:
                    request["nextToken"] = next_token
                page = self.codebuild.list_builds_for_project(**request)
                ids = page.get("ids", []) if isinstance(page, dict) else []
                if not isinstance(ids, list):
                    raise TypeError
                for offset in range(0, len(ids), 100):
                    batch = self.codebuild.batch_get_builds(ids=ids[offset : offset + 100])
                    builds = batch.get("builds", []) if isinstance(batch, dict) else []
                    if not isinstance(builds, list):
                        raise TypeError
                    for build in builds:
                        if not isinstance(build, dict):
                            raise TypeError
                        try:
                            parsed = self._parse_build(build)
                        except ValueError:
                            continue
                        if parsed.run_id == run_id:
                            matches.append(parsed)
                next_token = page.get("nextToken")
                if not next_token:
                    break
            else:
                if next_token:
                    raise NovaApplyDispatchError(
                        "Nova apply build lookup exceeded its bounded search",
                        outcome_uncertain=True,
                        phase="build_start",
                    )
        except NovaApplyDispatchError:
            raise
        except (BotoCoreError, ClientError, OSError, TimeoutError, TypeError, ValueError):
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

    def _parse_build(self, build: dict[str, Any], *, expected_run_id: str | None = None) -> NovaApplyBuild:
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
        variables = environment.get("environmentVariables", []) if isinstance(environment, dict) else []
        run_id = next(
            (
                item.get("value")
                for item in variables
                if isinstance(item, dict) and item.get("name") == self._RUN_ID_ENV
            ),
            None,
        )
        try:
            run_id = _canonical_run_id(run_id)
        except ValueError:
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
    if canonical != value.lower():
        raise ValueError("Nova apply run ID is not canonical")
    return canonical
