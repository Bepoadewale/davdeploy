"""Deterministic bindings from internal modules to checked-in renderers.

This registry is intentionally small. A planning module is not executable until
it has a binding here and its own bounded Terraform, observation and cleanup
implementation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleRenderer:
    module_id: str
    terraform_root: str
    runner_script: str
    supported_operations: tuple[str, ...]
    certification: str
    execution_enabled: bool = True
    operation_commands: tuple[tuple[str, str], ...] = ()


_RENDERERS: dict[str, ModuleRenderer] = {
    "aws-managed-application": ModuleRenderer(
        module_id="aws-managed-application",
        terraform_root="infrastructure/terraform/customer-workload-app-runner-pilot",
        runner_script="scripts/customer-workload-app-runner-pilot.sh",
        supported_operations=("plan", "apply", "destroy", "build-push-image"),
        certification="real-customer-run evidence required per workload",
        operation_commands=(
            ("plan", "plan"),
            ("apply", "apply-saved-plan"),
            ("destroy", "destroy-saved-plan"),
            ("build-push-image", "build-push-image"),
        ),
    ),
    "aws-serverless-api": ModuleRenderer(
        module_id="aws-serverless-api",
        terraform_root="infrastructure/terraform/customer-workload-serverless-api",
        runner_script="scripts/customer-workload-serverless-api.sh",
        supported_operations=("plan", "destroy_plan", "apply", "observe", "destroy", "verify_cleanup"),
        certification="isolated AWS renderer certified; hosted dispatch not certified",
        execution_enabled=False,
        operation_commands=(
            ("plan", "plan"),
            ("destroy_plan", "destroy-plan"),
            ("apply", "apply-saved-plan"),
            ("observe", "health"),
            ("destroy", "destroy-saved-plan"),
            ("verify_cleanup", "verify-cleanup"),
        ),
    ),
}


def renderer_for_profile(profile: str, operation: str) -> ModuleRenderer:
    """Resolve a selected planning profile to a bounded lifecycle renderer.

    This deliberately does not bypass ``execution_enabled``. A profile may be
    understood by the execution layer while remaining unavailable to customer
    execution until its hosted AWS certification is complete.
    """
    module_id = {
        "aws-app-runner": "aws-managed-application",
        "aws-lambda-api": "aws-serverless-api",
    }.get(profile)
    if module_id is None:
        raise ValueError(f"profile {profile} has no registered execution renderer")
    return renderer_for(module_id, operation)


def renderer_command(renderer: ModuleRenderer, operation: str) -> str:
    """Return the fixed checked-in script operation for typed lifecycle work."""
    if operation not in renderer.supported_operations:
        raise ValueError(f"module {renderer.module_id} does not support {operation}")
    command = dict(renderer.operation_commands).get(operation)
    if not command:
        raise ValueError(f"module {renderer.module_id} has no command mapping for {operation}")
    return command


def renderer_for(module_id: str, operation: str) -> ModuleRenderer:
    """Resolve a checked-in renderer or reject an unbound lifecycle module.

    The serverless opt-in is only for controlled hosted certification. Customer
    run creation has a separate profile gate and must not use this flag as a
    rollout switch.
    """
    renderer = _RENDERERS.get(module_id)
    if renderer is None:
        raise ValueError(f"module {module_id} has no executable renderer")
    serverless_certification_enabled = (
        module_id == "aws-serverless-api"
        and os.getenv("DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION", "false").lower()
        == "true"
    )
    if not renderer.execution_enabled and not serverless_certification_enabled:
        raise ValueError(f"module {module_id} renderer is not enabled for customer execution")
    if operation not in renderer.supported_operations:
        raise ValueError(f"module {module_id} does not support {operation}")
    return renderer


def renderer_manifest() -> tuple[ModuleRenderer, ...]:
    """Return stable registry metadata for API and audit evidence."""
    return tuple(_RENDERERS[module_id] for module_id in sorted(_RENDERERS))
