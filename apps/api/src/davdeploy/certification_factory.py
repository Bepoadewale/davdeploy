"""Composable AWS certification scenarios used before module activation.

Scenarios are test-only manifests. They do not grant execution privileges and
must run only through the isolated, disposable AWS validation runner.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CertificationScenario:
    identifier: str
    modules: tuple[str, ...]
    readiness: tuple[str, ...]
    rollback: str
    cleanup: tuple[str, ...]


_SCENARIOS = (
    CertificationScenario("web-application", ("aws-static-web", "aws-serverless-api", "aws-identity"), ("https 200", "api health 200"), "restore prior artifact", ("cloudfront absent", "bucket empty")),
    CertificationScenario("saas-backend", ("aws-managed-application", "aws-relational-data", "aws-nosql-data", "aws-jobs-events"), ("service health", "database query", "queue publish"), "restore prior desired state", ("service absent", "owned data resources absent")),
    CertificationScenario("async-data", ("aws-jobs-events", "aws-data-analytics", "aws-stream-processing"), ("event delivered", "job completed"), "replay idempotent fixture", ("queue absent", "stream absent")),
    CertificationScenario("ai-rag", ("aws-ai-retrieval", "aws-search", "aws-file-storage"), ("synthetic document retrieved", "guardrail response"), "remove indexed fixture", ("index absent", "fixture objects absent")),
    CertificationScenario("kubernetes", ("aws-kubernetes-platform", "aws-container-service"), ("load balancer health", "workload ready"), "roll back deployment revision", ("cluster workloads absent",)),
    CertificationScenario("hybrid-network", ("aws-private-connectivity",), ("vpn tunnel up", "routed probe succeeds"), "withdraw test route", ("vpn absent", "test peer absent")),
    CertificationScenario("multi-region", ("aws-edge-https", "aws-backup-recovery"), ("primary health", "failover DNS answer"), "restore primary", ("health checks absent", "validation records absent")),
    CertificationScenario("machine-learning", ("aws-managed-ml",), ("endpoint invocation", "model metrics"), "delete endpoint configuration", ("endpoint absent", "model absent")),
)


def certification_scenarios() -> tuple[CertificationScenario, ...]:
    return _SCENARIOS


def scenario_for_module(module_id: str) -> tuple[CertificationScenario, ...]:
    return tuple(scenario for scenario in _SCENARIOS if module_id in scenario.modules)
