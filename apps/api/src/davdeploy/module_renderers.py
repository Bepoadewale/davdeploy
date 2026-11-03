"""Deterministic bindings from internal modules to checked-in renderers.

This registry is intentionally small. A planning module is not executable until
it has a binding here and its own bounded Terraform, observation and cleanup
implementation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleRenderer:
    module_id: str
    terraform_root: str
    runner_script: str
    supported_operations: tuple[str, ...]
    certification: str


_RENDERERS: dict[str, ModuleRenderer] = {
    "aws-managed-application": ModuleRenderer(
        module_id="aws-managed-application",
        terraform_root="infrastructure/terraform/customer-workload-app-runner-pilot",
        runner_script="scripts/customer-workload-app-runner-pilot.sh",
        supported_operations=("apply", "destroy"),
        certification="real-customer-run evidence required per workload",
    ),
}


def renderer_for(module_id: str, operation: str) -> ModuleRenderer:
    """Resolve a checked-in renderer or reject an unbound lifecycle module."""
    renderer = _RENDERERS.get(module_id)
    if renderer is None:
        raise ValueError(f"module {module_id} has no executable renderer")
    if operation not in renderer.supported_operations:
        raise ValueError(f"module {module_id} does not support {operation}")
    return renderer


def renderer_manifest() -> tuple[ModuleRenderer, ...]:
    """Return stable registry metadata for API and audit evidence."""
    return tuple(_RENDERERS[module_id] for module_id in sorted(_RENDERERS))
