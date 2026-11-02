"""Provider-neutral, deterministic lifecycle contracts for composed workloads.

This is intentionally a compiler boundary.  It turns a selected internal module
graph into immutable lifecycle work, but never accepts free-form commands or
credentials from a model or browser.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from davdeploy.domain import ArchitectureModule

LIFECYCLE_OPERATIONS = ("plan", "apply", "observe", "rollback", "destroy", "verify_cleanup")


@dataclass(frozen=True)
class ModuleLifecycle:
    module_id: str
    dependencies: tuple[str, ...]
    operations: tuple[str, ...] = LIFECYCLE_OPERATIONS
    resource_tags: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class UniversalExecutionPlan:
    plan_digest: str
    modules: tuple[ModuleLifecycle, ...]
    estimated_monthly_cost_state: str
    immutable: bool = True


@dataclass(frozen=True)
class LifecycleEvidence:
    module_id: str
    operation: str
    state: str
    outputs: tuple[tuple[str, str], ...] = ()


class LifecycleExecutor(Protocol):
    def run(self, plan: UniversalExecutionPlan, operation: str) -> tuple[LifecycleEvidence, ...]: ...


def compile_universal_execution_plan(
    modules: list[ArchitectureModule], *, workspace_id: str, project_id: str, plan_digest: str
) -> UniversalExecutionPlan:
    """Compile dependency-ordered internal modules into bounded lifecycle work."""
    known = {module.identifier for module in modules}
    if len(known) != len(modules):
        raise ValueError("module graph contains duplicate module identifiers")
    result: list[ModuleLifecycle] = []
    for module in modules:
        unknown = set(module.depends_on) - known
        if unknown:
            raise ValueError(f"module {module.identifier} depends on unknown modules: {sorted(unknown)}")
        result.append(
            ModuleLifecycle(
                module_id=module.identifier,
                dependencies=tuple(module.depends_on),
                resource_tags=(
                    ("ManagedBy", "davdeploy"),
                    ("DavDeployWorkspace", workspace_id),
                    ("DavDeployProject", project_id),
                    ("DavDeployPlan", plan_digest),
                ),
            )
        )
    canonical = "|".join(f"{item.module_id}:{','.join(item.dependencies)}" for item in result)
    expected = sha256(canonical.encode()).hexdigest()
    # The caller-provided digest remains the authoritative approved artifact.
    if len(plan_digest) != 64:
        raise ValueError("plan digest must be a SHA-256 hex digest")
    return UniversalExecutionPlan(
        plan_digest=plan_digest,
        modules=tuple(result),
        estimated_monthly_cost_state=f"evidence-required:{expected[:12]}",
    )


def verify_cleanup(evidence: tuple[LifecycleEvidence, ...], plan: UniversalExecutionPlan) -> bool:
    """Require an independent ABSENT observation for every composed module."""
    absent = {item.module_id for item in evidence if item.operation == "verify_cleanup" and item.state == "ABSENT"}
    return absent == {module.module_id for module in plan.modules}
