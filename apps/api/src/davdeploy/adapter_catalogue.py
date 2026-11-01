"""The governed workload-pattern catalogue.

This registry is intentionally broader than ``execution_profiles``.  It lets
planning and product documentation name important customer workload families
without turning an unproven family into an executable cloud adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CapabilityStage = Literal["catalogued", "planning", "pilot", "general-availability"]


@dataclass(frozen=True)
class AdapterCatalogueEntry:
    """A bounded customer workload family, not an authority to deploy it."""

    identifier: str
    family: str
    stage: CapabilityStage
    primary_services: tuple[str, ...]
    purpose: str


_CATALOGUE: tuple[AdapterCatalogueEntry, ...] = (
    AdapterCatalogueEntry("aws-static-edge", "static-web", "planning", ("S3", "CloudFront"), "Static web and edge delivery"),
    AdapterCatalogueEntry("aws-serverless-api", "serverless-api", "planning", ("Lambda", "API Gateway"), "Variable-traffic HTTP APIs"),
    AdapterCatalogueEntry("aws-app-runner", "managed-application", "pilot", ("App Runner", "ECR"), "Single container web or API service"),
    AdapterCatalogueEntry("aws-ecs-fargate", "managed-containers", "planning", ("ECS Fargate", "ECR"), "Multi-container and API-worker services"),
    AdapterCatalogueEntry("aws-ec2-managed", "managed-vm", "planning", ("EC2", "Auto Scaling"), "OS-level or legacy workloads"),
    AdapterCatalogueEntry("aws-eks-governed", "kubernetes", "planning", ("EKS", "ECR"), "Kubernetes-specific workloads"),
    AdapterCatalogueEntry("aws-scheduled-batch", "jobs-and-batch", "catalogued", ("EventBridge Scheduler", "Step Functions", "AWS Batch"), "Scheduled and batch work"),
    AdapterCatalogueEntry("aws-event-backbone", "events-and-workflows", "catalogued", ("EventBridge", "SQS", "SNS", "Step Functions"), "Decoupled event workflows"),
    AdapterCatalogueEntry("aws-relational-data", "relational-data", "catalogued", ("RDS", "Aurora", "Secrets Manager"), "Transactional relational data"),
    AdapterCatalogueEntry("aws-nosql-cache", "nosql-and-cache", "catalogued", ("DynamoDB", "ElastiCache"), "Key-value state and justified cache"),
    AdapterCatalogueEntry("aws-object-analytics", "object-and-analytics", "catalogued", ("S3", "Glue", "Athena"), "Object storage and analytics"),
    AdapterCatalogueEntry("aws-stream-processing", "streaming", "catalogued", ("Kinesis", "MSK"), "Streaming ingestion and processing"),
    AdapterCatalogueEntry("aws-realtime-api", "realtime-api", "catalogued", ("API Gateway", "AppSync"), "WebSocket and GraphQL clients"),
    AdapterCatalogueEntry("aws-ai-retrieval", "ai-application", "planning", ("Bedrock", "S3", "Lambda"), "Bounded AI and retrieval applications"),
    AdapterCatalogueEntry("aws-managed-ml", "managed-machine-learning", "catalogued", ("SageMaker", "S3"), "Managed model training and inference"),
    AdapterCatalogueEntry("aws-cpu-inference", "cpu-inference", "planning", ("ECS Fargate", "EC2", "SageMaker"), "Custom CPU inference"),
    AdapterCatalogueEntry("aws-gpu-inference", "gpu-inference", "planning", ("SageMaker", "EKS", "EC2"), "Accelerated inference and training"),
    AdapterCatalogueEntry("aws-hybrid-connectivity", "hybrid-networking", "catalogued", ("VPC", "PrivateLink", "Transit Gateway"), "Private and hybrid connectivity"),
    AdapterCatalogueEntry("aws-observability-recovery", "operations", "catalogued", ("CloudWatch", "OpenTelemetry", "S3"), "Observability, backup and recovery"),
)


def adapter_catalogue() -> tuple[AdapterCatalogueEntry, ...]:
    """Return the full product catalogue in stable declaration order."""

    return _CATALOGUE


def adapter_catalogue_entry(identifier: str) -> AdapterCatalogueEntry:
    """Return a named catalogue entry or fail closed for unknown scope."""

    for entry in _CATALOGUE:
        if entry.identifier == identifier:
            return entry
    raise ValueError(f"no governed adapter catalogue entry exists for {identifier}")
