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
from typing import ClassVar, Protocol

import boto3

from davdeploy.module_ports import validate_module_inputs
from davdeploy.module_renderers import renderer_for
from davdeploy.universal_execution import validate_lifecycle_work_graph


@dataclass(frozen=True)
class CloudExecutionResult:
    state: str
    operations: tuple[dict[str, object], ...]
    outputs: dict[str, object]
    failure_reason: str | None = None


class CloudExecutionAdapter(Protocol):
    def execute(self, context: dict[str, object]) -> CloudExecutionResult: ...


def validate_lifecycle_work(
    value: object, *, hosted_certification: bool = False
) -> tuple[dict[str, object], ...]:
    """Accept only durable, typed module work, never a command payload."""
    accepted: list[dict[str, object]] = []
    for item in validate_lifecycle_work_graph(value):
        module_id = str(item["module_id"])
        instance_id = str(item["instance_id"])
        operation = str(item["operation"])
        dependencies = item["dependencies"]
        input_bindings = item["input_bindings"]
        resource_tags = item["resource_tags"]
        assert isinstance(dependencies, list) and isinstance(input_bindings, list)
        assert isinstance(resource_tags, dict)
        renderer = renderer_for(module_id, operation, hosted_certification=hosted_certification)
        accepted.append(
            {
                "module_id": module_id,
                "instance_id": instance_id,
                "operation": operation,
                "dependencies": dependencies,
                "input_bindings": input_bindings,
                "resource_tags": resource_tags,
                "renderer": {
                    "terraform_root": renderer.terraform_root,
                    "runner_script": renderer.runner_script,
                },
            }
        )
    return tuple(accepted)


def trusted_execution_work(context: dict[str, object]) -> tuple[dict[str, object], ...]:
    """Resolve durable lifecycle work or one fixed App Runner image-build task.

    The hosted serverless certification exception is granted only by a run mode
    loaded from the durable execution row, never by a caller-provided environment
    flag.
    """
    value = context.get("lifecycle_work")
    environment = context.get("environment") or {}
    hosted_certification = (
        context.get("mode") == "AUTHENTICATED_SERVERLESS_CERTIFICATION"
        and context.get("profile") == "aws-serverless-api"
    )
    if (
        value is None
        and isinstance(environment, dict)
        and environment.get("DAVDEPLOY_EXECUTION_OPERATION") == "build-push-image"
    ):
        value = [
            {
                "module_id": "aws-managed-application",
                "operation": "build-push-image",
                "dependencies": [],
                "resource_tags": {"ManagedBy": "davdeploy"},
            }
        ]
    return validate_lifecycle_work(value, hosted_certification=hosted_certification)


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

    operations = (
        "plan",
        "apply-foundation",
        "build-push-image",
        "apply-service",
        "wait-ready",
        "smoke",
    )

    def __init__(self, *, root: str | Path = ".", timeout_seconds: int = 1_800):
        self.root = Path(root)
        self.timeout_seconds = timeout_seconds

    def execute(self, context: dict[str, object]) -> CloudExecutionResult:
        try:
            lifecycle_work = trusted_execution_work(context)
        except (TypeError, ValueError) as error:
            return CloudExecutionResult("FAILED", (), {}, str(error))
        if len(lifecycle_work) != 1:
            return CloudExecutionResult(
                "FAILED",
                (),
                {},
                "App Runner accepts one module instance per execution run.",
            )
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
    renderer_input_allowlist: ClassVar[dict[str, frozenset[str]]] = {
        "aws-serverless-api": frozenset({"uploads_bucket_name"}),
        "aws-file-storage": frozenset(),
    }

    def __init__(self, project_name: str | None = None, client=None):
        self.project_name = project_name or os.getenv("DAVDEPLOY_CUSTOMER_EXECUTOR_PROJECT")
        self.client = client or boto3.client("codebuild")

    def execute(self, context: dict[str, object]) -> CloudExecutionResult:
        environment = context.get("environment") or {}
        try:
            lifecycle_work = trusted_execution_work(context)
        except (TypeError, ValueError) as error:
            return CloudExecutionResult("FAILED", (), {}, str(error))
        module_types = [str(item["module_id"]) for item in lifecycle_work]
        if len(module_types) != len(set(module_types)):
            return CloudExecutionResult(
                "FAILED",
                (),
                {},
                "The registered renderer does not yet isolate repeated instances of one module type.",
            )
        renderer_roots = [str(item["renderer"]["terraform_root"]) for item in lifecycle_work]
        if len(renderer_roots) != len(set(renderer_roots)):
            return CloudExecutionResult(
                "FAILED",
                (),
                {},
                "The registered renderers do not yet isolate shared Terraform state roots.",
            )
        selected_instance_id = context.get("dispatch_instance_id")
        selected = next(
            (item for item in lifecycle_work if item["instance_id"] == selected_instance_id),
            None,
        )
        if selected is None and len(lifecycle_work) == 1 and selected_instance_id is None:
            selected = lifecycle_work[0]
        if selected is None:
            return CloudExecutionResult(
                "FAILED",
                (),
                {},
                "CodeBuild requires one selected module instance from the validated graph.",
            )
        raw_inputs = context.get("resolved_module_inputs", {})
        try:
            if not isinstance(raw_inputs, dict):
                raise TypeError("resolved renderer inputs must be an object")
            resolved_inputs = validate_module_inputs(str(selected["module_id"]), raw_inputs)
            allowed_inputs = self.renderer_input_allowlist.get(
                str(selected["module_id"]), frozenset()
            )
            if set(resolved_inputs) - allowed_inputs:
                raise ValueError("renderer input is not enabled")
            binding_names = {str(binding["input_name"]) for binding in selected["input_bindings"]}
            if set(resolved_inputs) != binding_names:
                raise ValueError("resolved inputs do not match the declared references")
        except (TypeError, ValueError, KeyError) as error:
            return CloudExecutionResult("FAILED", (), {}, str(error))
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
            if isinstance(key, str)
            and isinstance(value, str)
            and key != "DAVDEPLOY_RESOLVED_MODULE_INPUTS_JSON"
        ]
        overrides.append(
            {
                "name": "DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON",
                "value": json.dumps([selected], sort_keys=True, separators=(",", ":")),
                "type": "PLAINTEXT",
            }
        )
        if resolved_inputs:
            overrides.append(
                {
                    "name": "DAVDEPLOY_RESOLVED_MODULE_INPUTS_JSON",
                    "value": json.dumps(resolved_inputs, sort_keys=True, separators=(",", ":")),
                    "type": "PLAINTEXT",
                }
            )
        if context.get("mode") == "AUTHENTICATED_SERVERLESS_CERTIFICATION":
            certification_environment = {
                "aws-serverless-api": "DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION",
                "aws-file-storage": "DAVDEPLOY_ENABLE_PRIVATE_S3_HOSTED_CERTIFICATION",
            }.get(str(selected["module_id"]))
            if certification_environment:
                overrides.append(
                    {"name": certification_environment, "value": "true", "type": "PLAINTEXT"}
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
