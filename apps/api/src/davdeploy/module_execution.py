"""Compile bounded execution lifecycle requirements from selected modules."""

from __future__ import annotations

from davdeploy.domain import ArchitectureModule, ModuleExecutionContract


def module_execution_contracts(modules: list[ArchitectureModule]) -> list[ModuleExecutionContract]:
    result = []
    for module in modules:
        executable = module.execution_supported
        result.append(
            ModuleExecutionContract(
                module_id=module.identifier,
                execution_state="PILOT_ELIGIBLE" if executable else "IMPLEMENTATION_REQUIRED",
                prerequisites=[
                    "exact approved plan digest",
                    "validated customer cloud connection",
                    "policy, budget, quota and region checks",
                    "least-privilege module role",
                ],
                health_evidence=["provider resource state", "application or module metric"],
                rollback_strategy="restore the prior approved desired state through a governed change",
                destroy_strategy=(
                    "run the exact-digest governed destroy and independently verify absence"
                    if executable
                    else "not available until a bounded destroy implementation exists"
                ),
            )
        )
    return result
