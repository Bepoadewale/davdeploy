"""Deterministic operational readiness requirements for composed plans."""

from __future__ import annotations

from davdeploy.domain import ArchitectureModule, OperationalReadiness


def operational_readiness(modules: list[ArchitectureModule]) -> OperationalReadiness:
    selected = {module.identifier for module in modules}
    recovery = ["backup policy", "tested restore procedure", "governed rollback"]
    if "aws-relational-data" in selected:
        recovery.append("database point-in-time recovery")
    return OperationalReadiness(
        cost_evidence_state="ESTIMATE_REQUIRES_LIVE_PRICING_AND_QUOTA_CHECK_BEFORE_EXECUTION",
        quota_evidence_state="REQUIRED_BEFORE_EXECUTION",
        health_checks=["provider resource state", "application endpoint or module metric"],
        incident_controls=["alarm routing", "audit trail", "workspace support handoff"],
        recovery_controls=recovery,
    )
