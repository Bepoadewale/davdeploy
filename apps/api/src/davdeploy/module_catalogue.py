"""Deterministic internal module composition for customer architecture plans.

The catalogue gives the planner a broad vocabulary without exposing cloud
service choices to customers or granting a model execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass

from davdeploy.domain import ArchitectureModule, WorkloadSpec


@dataclass(frozen=True)
class ModuleDefinition:
    identifier: str
    display_name: str
    purpose: str
    stage: str
    services: tuple[str, ...]
    depends_on: tuple[str, ...] = ()
    execution_supported: bool = False

    def selected(self) -> ArchitectureModule:
        return ArchitectureModule(
            identifier=self.identifier,
            display_name=self.display_name,
            purpose=self.purpose,
            stage=self.stage,
            services=list(self.services),
            depends_on=list(self.depends_on),
            execution_supported=self.execution_supported,
        )


_MODULES: tuple[ModuleDefinition, ...] = (
    ModuleDefinition(
        "aws-observability",
        "Operations",
        "Health, logs, metrics, alerts and audit evidence",
        "catalogued",
        ("CloudWatch", "OpenTelemetry"),
    ),
    ModuleDefinition(
        "aws-secrets-config",
        "Secure configuration",
        "Secret references and protected application configuration",
        "catalogued",
        ("Secrets Manager", "SSM Parameter Store"),
    ),
    ModuleDefinition(
        "aws-edge-https",
        "Secure public edge",
        "TLS, domain routing, CDN and edge protection",
        "planning",
        ("CloudFront", "Route 53", "AWS WAF"),
    ),
    ModuleDefinition(
        "aws-static-web",
        "Web experience",
        "Static frontend delivery",
        "planning",
        ("S3", "CloudFront"),
        ("aws-edge-https",),
    ),
    ModuleDefinition(
        "aws-serverless-api",
        "Application API",
        "Short-running API and event handlers",
        "planning",
        ("Lambda", "API Gateway"),
        ("aws-edge-https", "aws-secrets-config"),
    ),
    ModuleDefinition(
        "aws-managed-application",
        "Application service",
        "Single managed container service",
        "pilot",
        ("App Runner", "ECR"),
        ("aws-edge-https", "aws-secrets-config"),
        True,
    ),
    ModuleDefinition(
        "aws-container-service",
        "Container services",
        "Multi-service APIs and workers",
        "planning",
        ("ECS Fargate", "ECR", "ALB"),
        ("aws-edge-https", "aws-secrets-config"),
    ),
    ModuleDefinition(
        "aws-virtual-machine-service",
        "Managed compute",
        "Long-running or host-controlled service",
        "planning",
        ("EC2", "Auto Scaling"),
        ("aws-edge-https", "aws-secrets-config"),
    ),
    ModuleDefinition(
        "aws-kubernetes-platform",
        "Kubernetes platform",
        "Kubernetes-specific services and scheduling",
        "planning",
        ("EKS", "ECR", "Argo CD"),
        ("aws-secrets-config",),
    ),
    ModuleDefinition(
        "aws-identity",
        "Customer identity",
        "User authentication, sessions and access control",
        "catalogued",
        ("Cognito",),
        ("aws-secrets-config",),
    ),
    ModuleDefinition(
        "aws-relational-data",
        "Relational data",
        "Transactional application data",
        "catalogued",
        ("Aurora", "RDS"),
        ("aws-secrets-config",),
    ),
    ModuleDefinition(
        "aws-nosql-data",
        "NoSQL data",
        "High-scale key-value application state",
        "catalogued",
        ("DynamoDB",),
    ),
    ModuleDefinition(
        "aws-file-storage",
        "File storage",
        "Private uploads, assets and object storage",
        "catalogued",
        ("S3",),
        ("aws-secrets-config",),
    ),
    ModuleDefinition(
        "aws-jobs-events",
        "Jobs and events",
        "Reliable background work, schedules and notifications",
        "catalogued",
        ("SQS", "EventBridge", "SNS", "Step Functions"),
    ),
    ModuleDefinition(
        "aws-realtime",
        "Real-time updates",
        "WebSocket, GraphQL subscriptions and live application events",
        "catalogued",
        ("API Gateway WebSocket", "AppSync", "DynamoDB"),
        ("aws-identity",),
    ),
    ModuleDefinition(
        "aws-search",
        "Search",
        "Application search and indexing",
        "catalogued",
        ("OpenSearch", "Lambda"),
        ("aws-jobs-events",),
    ),
    ModuleDefinition(
        "aws-payments-webhooks",
        "Payments and webhooks",
        "Protected third-party payment and webhook processing",
        "catalogued",
        ("API Gateway", "Lambda", "SQS", "Secrets Manager"),
        ("aws-jobs-events", "aws-secrets-config"),
    ),
    ModuleDefinition(
        "aws-ai-retrieval",
        "AI application",
        "Managed model access and retrieval-augmented generation",
        "planning",
        ("Bedrock", "S3", "Lambda"),
        ("aws-secrets-config", "aws-file-storage"),
    ),
    ModuleDefinition(
        "aws-managed-ml",
        "Machine learning",
        "Managed training, model registry and endpoint lifecycle",
        "catalogued",
        ("SageMaker", "S3"),
        ("aws-file-storage", "aws-secrets-config"),
    ),
    ModuleDefinition(
        "aws-cpu-inference",
        "Custom model inference",
        "CPU-based hosted inference",
        "planning",
        ("ECS Fargate", "SageMaker"),
        ("aws-container-service",),
    ),
    ModuleDefinition(
        "aws-gpu-inference",
        "Accelerated inference",
        "GPU-backed inference or training",
        "planning",
        ("SageMaker", "EKS", "EC2"),
        ("aws-secrets-config",),
    ),
    ModuleDefinition(
        "aws-data-analytics",
        "Data analytics",
        "Data lake, transformation and query workloads",
        "catalogued",
        ("S3", "Glue", "Athena"),
        ("aws-file-storage",),
    ),
    ModuleDefinition(
        "aws-stream-processing",
        "Stream processing",
        "Ordered, high-throughput event processing",
        "catalogued",
        ("Kinesis", "MSK"),
        ("aws-jobs-events",),
    ),
    ModuleDefinition(
        "aws-media",
        "Media delivery",
        "Video ingestion, transcoding and delivery",
        "catalogued",
        ("S3", "MediaConvert", "CloudFront"),
        ("aws-file-storage", "aws-edge-https"),
    ),
    ModuleDefinition(
        "aws-private-connectivity",
        "Private connectivity",
        "Private service access and controlled network paths",
        "catalogued",
        ("VPC", "PrivateLink", "Transit Gateway"),
    ),
    ModuleDefinition(
        "aws-backup-recovery",
        "Backup and recovery",
        "Backups, restoration evidence and recovery controls",
        "catalogued",
        ("AWS Backup", "S3"),
        ("aws-observability",),
    ),
)

_BY_ID = {module.identifier: module for module in _MODULES}

_PROFILE_MODULE = {
    "aws-s3-cloudfront-static": "aws-static-web",
    "aws-lambda-api": "aws-serverless-api",
    "aws-app-runner": "aws-managed-application",
    "aws-ecs-fargate": "aws-container-service",
    "aws-ec2-managed": "aws-virtual-machine-service",
    "aws-eks-governed": "aws-kubernetes-platform",
    "aws-managed-ai": "aws-ai-retrieval",
    "aws-cpu-inference": "aws-cpu-inference",
    "aws-gpu-inference": "aws-gpu-inference",
}

_CAPABILITY_MODULE = {
    "identity": "aws-identity",
    "relational_data": "aws-relational-data",
    "nosql_data": "aws-nosql-data",
    "file_storage": "aws-file-storage",
    "jobs": "aws-jobs-events",
    "events": "aws-jobs-events",
    "realtime": "aws-realtime",
    "search": "aws-search",
    "payments": "aws-payments-webhooks",
    "ai": "aws-ai-retrieval",
    "machine_learning": "aws-managed-ml",
    "analytics": "aws-data-analytics",
    "streaming": "aws-stream-processing",
    "media": "aws-media",
    "private_connectivity": "aws-private-connectivity",
    "backup_recovery": "aws-backup-recovery",
}


def known_capabilities() -> frozenset[str]:
    """Return capability names accepted from model or repository evidence."""

    return frozenset(_CAPABILITY_MODULE)


def compose_modules(spec: WorkloadSpec, selected_profile: str) -> list[ArchitectureModule]:
    """Return a dependency-ordered internal module graph for one plan."""

    identifiers = {"aws-observability", "aws-secrets-config", _PROFILE_MODULE[selected_profile]}
    identifiers.update(
        _CAPABILITY_MODULE[capability]
        for capability in spec.capability_requirements
        if capability in _CAPABILITY_MODULE
    )
    if spec.stateful:
        identifiers.add("aws-relational-data")
    if spec.event_driven:
        identifiers.add("aws-jobs-events")
    if spec.requires_private_connectivity:
        identifiers.add("aws-private-connectivity")
    if spec.environments and any(
        environment.value == "production" for environment in spec.environments
    ):
        identifiers.add("aws-backup-recovery")

    ordered: list[ModuleDefinition] = []

    def visit(identifier: str) -> None:
        module = _BY_ID[identifier]
        for dependency in module.depends_on:
            if dependency not in {entry.identifier for entry in ordered}:
                visit(dependency)
        if identifier not in {entry.identifier for entry in ordered}:
            ordered.append(module)

    for identifier in sorted(identifiers):
        visit(identifier)
    return [module.selected() for module in ordered]
