"""Deterministic composed deployment lifecycle for natural-language plans."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from davdeploy.universal_execution import (
    LIFECYCLE_OPERATIONS,
    REVERSE_OPERATIONS,
    LifecycleEvidence,
    ModuleLifecycle,
    UniversalExecutionPlan,
    lifecycle_evidence_complete,
    ordered_modules,
    verify_cleanup,
)

_MODULE_STATES = frozenset(
    {
        "NOT_DISPATCHED",
        "QUEUED",
        "SUBMITTED",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "BLOCKED_CLOUD_EXECUTION_NOT_ENABLED",
        "SUCCEEDED_AWAITING_OBSERVATION",
        "PLAN_READY_FOR_REVIEW",
        "DESTROY_PLAN_READY_FOR_REVIEW",
        "HEALTHY",
        "ROLLED_BACK",
        "DESTROYED_VERIFIED",
        "CLEANUP_VERIFIED",
        "ABSENT",
        "ARTIFACT_READY",
        "IMAGE_BUILT_AWAITING_SERVICE_PLAN",
        "RECONCILIATION_REQUIRED",
    }
)
_DEPENDENCY_TERMINAL_STATES = {
    "plan": frozenset({"PLAN_READY_FOR_REVIEW", "DESTROY_PLAN_READY_FOR_REVIEW"}),
    "apply": frozenset({"SUCCEEDED", "SUCCEEDED_AWAITING_OBSERVATION", "HEALTHY"}),
    "observe": frozenset({"HEALTHY"}),
    "rollback": frozenset({"ROLLED_BACK", "DESTROYED_VERIFIED"}),
    "destroy": frozenset({"SUCCEEDED", "DESTROYED_VERIFIED"}),
    "verify_cleanup": frozenset({"ABSENT", "CLEANUP_VERIFIED"}),
}


def dependency_dispatch_wave(
    plan: UniversalExecutionPlan,
    operation: str,
    module_states: Mapping[str, str],
) -> tuple[ModuleLifecycle, ...]:
    """Select undispatched modules whose prerequisites have terminal evidence.

    This is a pure scheduling decision over persisted state. It does not claim
    rows, submit jobs, or retry operations. Missing/extra state rows and
    unknown states are rejected; failed and uncertain prerequisites simply
    keep their dependents out of the returned wave. Cleanup works in reverse
    dependency order so consumers are removed before their dependencies.
    """
    if operation not in LIFECYCLE_OPERATIONS:
        raise ValueError(f"unsupported lifecycle operation: {operation}")
    ordered = ordered_modules(plan, operation)
    expected = {module.module_id for module in ordered}
    if set(module_states) != expected:
        raise ValueError("module state rows do not match the execution graph")
    if any(
        not isinstance(state, str) or state not in _MODULE_STATES
        for state in module_states.values()
    ):
        raise ValueError("module graph contains an unknown lifecycle state")

    dependents: dict[str, set[str]] = {module_id: set() for module_id in expected}
    for module in plan.modules:
        for dependency in module.dependencies:
            dependents[dependency].add(module.module_id)

    prerequisites = (
        dependents if operation in REVERSE_OPERATIONS else {
            module.module_id: set(module.dependencies) for module in plan.modules
        }
    )
    terminal = _DEPENDENCY_TERMINAL_STATES[operation]
    return tuple(
        module
        for module in ordered
        if module_states[module.module_id] == "NOT_DISPATCHED"
        and all(
            module_states[prerequisite] in terminal
            for prerequisite in prerequisites[module.module_id]
        )
    )


@dataclass(frozen=True)
class DeploymentObservation:
    plan_digest: str
    module_id: str
    health: str
    outputs: tuple[tuple[str, str], ...]
    cost_state: str


def collect_observations(plan: UniversalExecutionPlan, evidence: tuple[LifecycleEvidence, ...]) -> tuple[DeploymentObservation, ...]:
    """Convert bounded provider observations into customer-safe plan evidence."""
    by_module: dict[str, list[LifecycleEvidence]] = {}
    for item in evidence:
        if item.operation == "observe":
            by_module.setdefault(item.module_id, []).append(item)
    observations = []
    for module in plan.modules:
        module_evidence = by_module.get(module.module_id, [])
        observed = module_evidence[0] if len(module_evidence) == 1 else None
        observations.append(
            DeploymentObservation(
                plan_digest=plan.plan_digest,
                module_id=module.module_id,
                health=observed.state if observed else "UNKNOWN",
                outputs=observed.outputs if observed else (),
                cost_state=plan.estimated_monthly_cost_state,
            )
        )
    return tuple(observations)


def lifecycle_ready(plan: UniversalExecutionPlan, evidence: tuple[LifecycleEvidence, ...]) -> bool:
    """A composed plan is ready only when every module has healthy evidence."""
    return lifecycle_evidence_complete(plan, "observe", evidence)


def destroy_verified(plan: UniversalExecutionPlan, evidence: tuple[LifecycleEvidence, ...]) -> bool:
    return verify_cleanup(evidence, plan)
