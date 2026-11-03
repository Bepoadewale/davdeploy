"""Narrow, explicitly gated cloud execution boundary.

The product never accepts arbitrary commands. The App Runner adapter invokes one
checked-in script with a fixed operation allowlist and bounded timeouts.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import boto3

from davdeploy.module_renderers import renderer_for


@dataclass(frozen=True)
class CloudExecutionResult:
    state: str
    operations: tuple[dict[str, object], ...]
    outputs: dict[str, object]
    failure_reason: str | None = None


class CloudExecutionAdapter(Protocol):
    def execute(self, context: dict[str, object]) -> CloudExecutionResult: ...


def validate_lifecycle_work(value: object) -> tuple[dict[str, object], ...]:
    """Accept only durable, typed module work, never a command payload."""
    if not isinstance(value, list) or not value:
        raise ValueError("universal lifecycle work is required")
    accepted: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise TypeError("universal lifecycle work item must be an object")
        module_id = item.get("module_id")
        operation = item.get("operation")
        dependencies = item.get("dependencies")
        resource_tags = item.get("resource_tags")
        if not isinstance(module_id, str) or not module_id:
            raise ValueError("universal lifecycle work item has no module identifier")
        if operation not in {"plan", "destroy_plan", "apply", "observe", "destroy", "verify_cleanup", "build-push-image"}:
            raise ValueError("universal lifecycle work has an unsupported operation")
        if not isinstance(dependencies, list) or not all(isinstance(value, str) for value in dependencies):
            raise ValueError("universal lifecycle work has invalid dependencies")
        if not isinstance(resource_tags, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in resource_tags.items()
        ):
            raise ValueError("universal lifecycle work has invalid resource tags")
        renderer = renderer_for(module_id, operation)
        accepted.append(
            {
                "module_id": module_id,
                "operation": operation,
                "dependencies": dependencies,
                "resource_tags": resource_tags,
                "renderer": {
                    "terraform_root": renderer.terraform_root,
                    "runner_script": renderer.runner_script,
                },
            }
        )
    return tuple(accepted)


def trusted_execution_work(context: dict[str, object]) -> tuple[dict[str, object], ...]:
    """Resolve lifecycle work or one fixed App Runner image-build task."""
    value = context.get("lifecycle_work")
    environment = context.get("environment") or {}
    if value is None and isinstance(environment, dict) and environment.get("DAVDEPLOY_EXECUTION_OPERATION") == "build-push-image":
        value = [
            {
                "module_id": "aws-managed-application",
                "operation": "build-push-image",
                "dependencies": [],
                "resource_tags": {"ManagedBy": "davdeploy"},
            }
        ]
    return validate_lifecycle_work(value)


class DisabledCloudExecutionAdapter:
    def execute(self, context: dict[str, object]) -> CloudExecutionResult:
        del context
        return CloudExecutionResult(
            state="BLOCKED_CLOUD_EXECUTION_NOT_ENABLED",
            operations=(),
            outputs={},
            failure_reason="Cloud execution adapter is disabled for this process.",
        )


class AppRunnerCloudExecutionAdapter:
    """Run only the checked-in App Runner pilot script when explicitly enabled."""

    operations = ("plan", "apply-foundation", "build-push-image", "apply-service", "wait-ready", "smoke")

    def __init__(self, *, root: str | Path = ".", timeout_seconds: int = 1_800):
        self.root = Path(root)
        self.timeout_seconds = timeout_seconds

    def execute(self, context: dict[str, object]) -> CloudExecutionResult:
        try:
            trusted_execution_work(context)
        except (TypeError, ValueError) as error:
            return CloudExecutionResult("FAILED", (), {}, str(error))
        if os.getenv("DAVDEPLOY_CLOUD_EXECUTION_COMMAND_ENABLED", "false").lower() != "true":
            return DisabledCloudExecutionAdapter().execute(context)
        script = self.root / "scripts" / "customer-workload-app-runner-pilot.sh"
        if not script.is_file():
            return CloudExecutionResult(
                state="FAILED",
                operations=(),
                outputs={},
                failure_reason="App Runner execution script is unavailable.",
            )
        environment = os.environ.copy()
        for key, value in (context.get("environment") or {}).items():
            if not isinstance(key, str) or not isinstance(value, str):
                continue
            environment[key] = value
        results: list[dict[str, object]] = []
        for operation in self.operations:
            try:
                completed = subprocess.run(
                    [str(script), operation],
                    cwd=self.root,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                results.append({"operation": operation, "returncode": None, "state": "TIMEOUT"})
                return CloudExecutionResult(
                    state="FAILED",
                    operations=tuple(results),
                    outputs={},
                    failure_reason=f"App Runner operation {operation} exceeded its timeout.",
                )
            results.append(
                {
                    "operation": operation,
                    "returncode": completed.returncode,
                    "state": "SUCCEEDED" if completed.returncode == 0 else "FAILED",
                    "stdout": completed.stdout[-2000:],
                    "stderr": completed.stderr[-2000:],
                }
            )
            if completed.returncode != 0:
                return CloudExecutionResult(
                    state="FAILED",
                    operations=tuple(results),
                    outputs={},
                    failure_reason=f"App Runner operation {operation} failed.",
                )
        return CloudExecutionResult(
            state="READY",
            operations=tuple(results),
            outputs={"source": "app-runner-pilot-script", "observed": True},
        )


class CodeBuildCloudExecutionAdapter:
    """Submit one bounded execution archive to the isolated CodeBuild runner."""

    required_environment = frozenset(
        {
            "AWS_REGION",
            "EXPECTED_AWS_ACCOUNT_ID",
            "TF_STATE_BUCKET",
            "TF_LOCK_TABLE",
            "DAVDEPLOY_CUSTOMER_CONNECTION_ID",
            "DAVDEPLOY_CUSTOMER_EXECUTION_ROLE_ARN",
            "DAVDEPLOY_EXTERNAL_ID_SECRET_ARN",
            "DAVDEPLOY_EXECUTION_ARTIFACT_S3_URI",
            "DAVDEPLOY_EXECUTION_OPERATION",
            "DAVDEPLOY_EXECUTION_RUN_ID",
            "DAVDEPLOY_EXECUTION_RESULT_S3_URI",
        }
    )

    def __init__(self, project_name: str | None = None, client=None):
        self.project_name = project_name or os.getenv("DAVDEPLOY_CUSTOMER_EXECUTOR_PROJECT")
        self.client = client or boto3.client("codebuild")

    def execute(self, context: dict[str, object]) -> CloudExecutionResult:
        environment = context.get("environment") or {}
        try:
            lifecycle_work = trusted_execution_work(context)
        except (TypeError, ValueError) as error:
            return CloudExecutionResult("FAILED", (), {}, str(error))
        if len(lifecycle_work) != 1:
            return CloudExecutionResult(
                "FAILED", (), {}, "CodeBuild currently accepts one certified module per execution run."
            )
        if not self.project_name:
            return DisabledCloudExecutionAdapter().execute(context)
        if not isinstance(environment, dict) or not self.required_environment.issubset(environment):
            return CloudExecutionResult(
                state="FAILED",
                operations=(),
                outputs={},
                failure_reason="Cloud execution environment is incomplete.",
            )
        overrides = [
            {"name": key, "value": str(value), "type": "PLAINTEXT"}
            for key, value in sorted(environment.items())
            if isinstance(key, str) and isinstance(value, str)
        ]
        overrides.append(
            {
                "name": "DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON",
                "value": json.dumps(lifecycle_work, sort_keys=True, separators=(",", ":")),
                "type": "PLAINTEXT",
            }
        )
        response = self.client.start_build(
            projectName=self.project_name,
            environmentVariablesOverride=overrides,
        )
        build = response["build"]
        build_id = str(build["id"])
        return CloudExecutionResult(
            state="SUBMITTED",
            operations=(
                {
                    "operation": str(environment["DAVDEPLOY_EXECUTION_OPERATION"]),
                    "state": "SUBMITTED",
                    "executor": "codebuild",
                    "build_id": build_id,
                },
            ),
            outputs={"codebuild_build_id": build_id, "codebuild_build_arn": build.get("arn")},
        )


def configured_cloud_execution_adapter() -> CloudExecutionAdapter:
    if (
        os.getenv("DAVDEPLOY_CLOUD_EXECUTION_COMMAND_ENABLED", "false").lower() == "true"
        and os.getenv("DAVDEPLOY_CLOUD_EXECUTION_BACKEND", "") == "codebuild"
    ):
        return CodeBuildCloudExecutionAdapter()
    if os.getenv("DAVDEPLOY_CLOUD_EXECUTION_COMMAND_ENABLED", "false").lower() == "true":
        return AppRunnerCloudExecutionAdapter()
    return DisabledCloudExecutionAdapter()
