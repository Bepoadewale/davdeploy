"""Deterministic composed deployment lifecycle for natural-language plans."""

from __future__ import annotations

from dataclasses import dataclass

from davdeploy.universal_execution import LifecycleEvidence, UniversalExecutionPlan, verify_cleanup


@dataclass(frozen=True)
class DeploymentObservation:
    plan_digest: str
    module_id: str
    health: str
    outputs: tuple[tuple[str, str], ...]
    cost_state: str


def collect_observations(plan: UniversalExecutionPlan, evidence: tuple[LifecycleEvidence, ...]) -> tuple[DeploymentObservation, ...]:
    """Convert bounded provider observations into customer-safe plan evidence."""
    by_module = {item.module_id: item for item in evidence if item.operation == "observe"}
    return tuple(
        DeploymentObservation(plan.plan_digest, module.module_id, by_module.get(module.module_id, LifecycleEvidence(module.module_id, "observe", "UNKNOWN")).state, by_module.get(module.module_id, LifecycleEvidence(module.module_id, "observe", "UNKNOWN")).outputs, plan.estimated_monthly_cost_state)
        for module in plan.modules
    )


def lifecycle_ready(plan: UniversalExecutionPlan, evidence: tuple[LifecycleEvidence, ...]) -> bool:
    """A composed plan is ready only when every module has healthy evidence."""
    observed = {item.module_id: item.state for item in evidence if item.operation == "observe"}
    return all(observed.get(module.module_id) == "HEALTHY" for module in plan.modules)


def destroy_verified(plan: UniversalExecutionPlan, evidence: tuple[LifecycleEvidence, ...]) -> bool:
    return verify_cleanup(evidence, plan)
