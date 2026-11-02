"""Typed evidence status for controlled AWS certification scenarios."""

from __future__ import annotations

from dataclasses import dataclass

from davdeploy.certification_factory import certification_scenarios


@dataclass(frozen=True)
class CertificationEvidence:
    scenario: str
    apply_succeeded: bool
    destroy_succeeded: bool
    readiness_proven: bool = False
    rollback_proven: bool = False
    cleanup_proven: bool = False

    @property
    def complete(self) -> bool:
        return all((self.apply_succeeded, self.destroy_succeeded, self.readiness_proven, self.rollback_proven, self.cleanup_proven))


def scenario_status(evidence: tuple[CertificationEvidence, ...]) -> dict[str, str]:
    indexed = {item.scenario: item for item in evidence}
    return {scenario.identifier: "CERTIFIED" if indexed.get(scenario.identifier) and indexed[scenario.identifier].complete else "REQUIRES_WORKLOAD_EVIDENCE" for scenario in certification_scenarios()}
