"""Provider-neutral, deterministic lifecycle contracts for composed workloads.

This is intentionally a compiler boundary.  It turns a selected internal module
graph into immutable lifecycle work, but never accepts free-form commands or
credentials from a model or browser.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from davdeploy.domain import ArchitectureModule

LIFECYCLE_OPERATIONS = ("plan", "apply", "observe", "rollback", "destroy", "verify_cleanup")
FORWARD_OPERATIONS = ("plan", "apply", "observe")
REVERSE_OPERATIONS = ("rollback", "destroy", "verify_cleanup")
TERMINAL_EVIDENCE_STATES = {
    "plan": frozenset({"SUCCEEDED", "PLAN_READY_FOR_REVIEW", "DESTROY_PLAN_READY_FOR_REVIEW"}),
    "apply": frozenset({"SUCCEEDED", "SUCCEEDED_AWAITING_OBSERVATION"}),
    "observe": frozenset({"HEALTHY"}),
    "rollback": frozenset({"ROLLED_BACK", "DESTROYED_VERIFIED"}),
    "destroy": frozenset({"SUCCEEDED", "DESTROYED_VERIFIED"}),
    "verify_cleanup": frozenset({"ABSENT", "CLEANUP_VERIFIED"}),
}


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


def ordered_modules(plan: UniversalExecutionPlan, operation: str) -> tuple[ModuleLifecycle, ...]:
    """Return a stable dependency order for one bounded lifecycle operation.

    Apply-like work executes dependencies before their consumers. Cleanup-like
    work reverses that order. This contract deliberately contains no commands,
    credentials, or provider SDK calls.
    """
    if operation not in LIFECYCLE_OPERATIONS:
        raise ValueError(f"unsupported lifecycle operation: {operation}")
    by_id = {module.module_id: module for module in plan.modules}
    remaining = {module.module_id: set(module.dependencies) for module in plan.modules}
    ordered: list[ModuleLifecycle] = []
    while remaining:
        ready = sorted(identifier for identifier, dependencies in remaining.items() if not dependencies)
        if not ready:
            raise ValueError("module graph contains a dependency cycle")
        for identifier in ready:
            ordered.append(by_id[identifier])
            del remaining[identifier]
        completed = set(ready)
        for dependencies in remaining.values():
            dependencies.difference_update(completed)
    if operation in REVERSE_OPERATIONS:
        ordered.reverse()
    return tuple(ordered)


def lifecycle_work(plan: UniversalExecutionPlan, operation: str) -> tuple[dict[str, object], ...]:
    """Serialize only typed lifecycle work for a durable execution runner."""
    return tuple(
        {
            "module_id": module.module_id,
            "operation": operation,
            "dependencies": list(module.dependencies),
            "resource_tags": dict(module.resource_tags),
        }
        for module in ordered_modules(plan, operation)
    )


def lifecycle_evidence_complete(
    plan: UniversalExecutionPlan,
    operation: str,
    evidence: Iterable[LifecycleEvidence],
) -> bool:
    """Require one operation-appropriate terminal record for every graph node.

    A module's successful health check cannot stand in for its plan or apply,
    and a successful delete request is not cleanup proof until absence is
    independently observed. Duplicate records are ambiguous because this
    contract has no attempt ordering, so callers must pass the current
    per-module outcome set rather than an event history.
    """
    expected = {module.module_id for module in ordered_modules(plan, operation)}
    terminal_states = TERMINAL_EVIDENCE_STATES[operation]
    outcomes: dict[str, list[str]] = {module_id: [] for module_id in expected}
    for item in evidence:
        if item.operation == operation and item.module_id in outcomes:
            outcomes[item.module_id].append(item.state)
    return all(
        len(states) == 1 and states[0] in terminal_states for states in outcomes.values()
    )


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
