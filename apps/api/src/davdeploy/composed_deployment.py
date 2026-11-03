"""Deterministic composed deployment lifecycle for natural-language plans."""

from __future__ import annotations

from dataclasses import dataclass

from davdeploy.universal_execution import (
    LifecycleEvidence,
    UniversalExecutionPlan,
    lifecycle_evidence_complete,
    verify_cleanup,
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
