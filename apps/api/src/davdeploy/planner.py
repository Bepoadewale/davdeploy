from __future__ import annotations

from datetime import UTC, datetime

from davdeploy.contracts import PlanningEvidence
from davdeploy.domain import (
    ArchitectureCandidate,
    ArchitectureComponent,
    ArchitecturePlan,
    CandidateClass,
    CloudInventorySnapshot,
    CostComponent,
    CostRange,
    MonitoringSpecification,
    WorkloadSpec,
)
from davdeploy.module_catalogue import compose_modules
from davdeploy.module_contracts import module_contracts
from davdeploy.module_execution import module_execution_contracts
from davdeploy.operational_readiness import operational_readiness


class AwsV1Planner:
    """A small, deterministic AWS decision catalogue.

    It starts with the simplest viable candidate, rejects hard-constraint
    violations, and chooses the lowest-complexity option inside the configured
    cheapest viable cost band. It is not a live pricing or cloud-discovery tool.
    """

    catalog_version = "aws-v1-fixture-2026-10-minimum-infrastructure"

    def __init__(self, cheapest_viable_band: float = 0.10):
        self.cheapest_viable_band = cheapest_viable_band

    def plan(
        self,
        spec: WorkloadSpec,
        inventory: CloudInventorySnapshot | None = None,
        evidence: PlanningEvidence | None = None,
    ) -> ArchitecturePlan:
        if spec.cloud != "aws":
            raise ValueError("V1 supports AWS only")
        if spec.peak_rps is None or spec.monthly_budget_usd is None:
            raise ValueError(
                "peak_rps and monthly_budget_usd are needed before architecture planning"
            )
        inventory = inventory or CloudInventorySnapshot(discovered_at=datetime.now(UTC))
        region = self._region(spec, inventory)
        candidates = [
            self._evaluate(candidate, spec, inventory) for candidate in self._generate(spec, region)
        ]
        viable = [candidate for candidate in candidates if candidate.valid]
        if not viable:
            reasons = sorted(
                {reason for candidate in candidates for reason in candidate.rejected_reasons}
            )
            raise ValueError(f"no viable architecture: {'; '.join(reasons)}")
        cheapest = min(candidate.cost_estimate.monthly_low for candidate in viable)
        band_limit = cheapest * (1 + self.cheapest_viable_band)
        in_band = [
            candidate for candidate in viable if candidate.cost_estimate.monthly_low <= band_limit
        ]
        selected = min(
            in_band,
            key=lambda candidate: (
                candidate.operational_complexity,
                candidate.cost_estimate.monthly_low,
                candidate.candidate_id,
            ),
        )
        alternatives = [
            candidate for candidate in viable if candidate.candidate_id != selected.candidate_id
        ]
        simpler_failed = [
            candidate
            for candidate in candidates
            if not candidate.valid
            and candidate.operational_complexity <= selected.operational_complexity
        ]
        explanation = self._explanation(selected, simpler_failed)
        evidence_refs = list(evidence.references) if evidence else []
        evidence_limitations = (
            list(evidence.limitations)
            if evidence
            else [
                "No typed live evidence bundle supplied; inventory and pricing are fixture assumptions."
            ]
        )
        if evidence and evidence.pricing:
            evidence_limitations.append(
                "Pricing is an estimate and actual_billing is false; customer billing must be queried separately."
            )
        monitoring_cost = CostComponent(
            category="monitoring",
            monthly_low=20,
            monthly_high=50,
            reason="Prometheus-compatible metrics storage and private Grafana access estimate.",
        )
        total_cost = CostRange(
            currency=selected.cost_estimate.currency,
            monthly_low=selected.cost_estimate.monthly_low + monitoring_cost.monthly_low,
            monthly_high=selected.cost_estimate.monthly_high + monitoring_cost.monthly_high,
            assumptions=[
                *selected.cost_estimate.assumptions,
                "Monitoring is estimated for Amazon Managed Service for Prometheus and Amazon Managed Grafana; actual usage and retention can change cost.",
            ],
            catalog_version=selected.cost_estimate.catalog_version,
            estimated_at=selected.cost_estimate.estimated_at,
        )
        monitoring = MonitoringSpecification(
            scrape_targets=[
                "application /metrics endpoint",
                "selected AWS workload health metrics",
            ],
            baseline_dashboard="davdeploy workload health: availability, request rate, latency, error rate, CPU and memory where exposed.",
            access_boundary="Grafana is private to the customer workspace; no public unauthenticated dashboard is planned.",
            coverage=["metrics", "deployment health", "baseline workload capacity"],
            limitations=[
                "Logs and distributed traces are not included in this V1 selected-plan monitoring scope."
            ],
            cost_assumption="Estimated as a range, not an AWS bill. Retention, active series and viewer count materially affect cost.",
        )
        modules = compose_modules(spec, selected.candidate_id)
        return ArchitecturePlan(
            profile=selected.candidate_id,
            region=region,
            components=[
                *selected.components,
                ArchitectureComponent(
                    name="Prometheus-compatible metrics",
                    purpose="Collect and retain required workload and deployment metrics.",
                    service="Amazon Managed Service for Prometheus",
                    private=True,
                ),
                ArchitectureComponent(
                    name="Grafana dashboard",
                    purpose="Show the baseline health and capacity dashboard to authorised users.",
                    service="Amazon Managed Grafana",
                    private=True,
                ),
            ],
            modules=modules,
            module_contracts=module_contracts(modules),
            module_execution=module_execution_contracts(modules),
            operational_readiness=operational_readiness(modules),
            dependencies=[
                "customer AWS account",
                "GitHub repository connection",
                "scoped AWS role",
            ],
            assumptions=selected.cost_estimate.assumptions,
            security_controls=self._security_controls(spec),
            cost_estimate=total_cost,
            cost_components=[*selected.cost_components, monitoring_cost],
            observability=monitoring,
            estimated_capacity=f"Designed for {spec.average_rps or 0} average RPS and {spec.peak_rps} peak RPS.",
            risks=selected.risks,
            alternatives=[self._alternative(candidate) for candidate in alternatives],
            operational_characteristics=[
                f"Operational complexity: {selected.operational_complexity}/5",
                *selected.complexity_reasons,
            ],
            rollback_strategy="Keep the prior approved desired state; restore it through a reviewed change and independently observe recovery.",
            execution_steps=[
                "validate approved cloud connection",
                "render only the selected approved profile",
                "await required approval",
                "run bounded executor",
                "observe actual health",
            ],
            selected_candidate_id=selected.candidate_id,
            candidates=candidates,
            complexity_score=selected.operational_complexity,
            recommendation_reason=explanation,
            simplest_viable_explanation=explanation,
            existing_resources_reused=selected.existing_resources_reused,
            new_resources_required=selected.new_resources_required,
            evidence_refs=evidence_refs,
            evidence_limitations=evidence_limitations,
        )

    def _generate(self, spec: WorkloadSpec, region: str) -> list[ArchitectureCandidate]:
        all_candidates = [
            self._candidate(
                "aws-s3-cloudfront-static",
                CandidateClass.STATIC,
                "Static hosting",
                region,
                15,
                35,
                1,
                ["S3", "CloudFront"],
                "Serve static content without an application runtime.",
            ),
            self._candidate(
                "aws-lambda-api",
                CandidateClass.SERVERLESS,
                "Serverless API",
                region,
                30,
                120,
                1,
                ["Lambda", "API Gateway"],
                "Run short stateless request handlers without servers.",
            ),
            self._candidate(
                "aws-app-runner",
                CandidateClass.MANAGED_APPLICATION,
                "Managed application",
                region,
                65,
                180,
                1,
                ["App Runner"],
                "Run one containerised web/API service with managed deployment and scaling.",
            ),
            self._candidate(
                "aws-ecs-fargate",
                CandidateClass.MANAGED_CONTAINERS,
                "Managed containers",
                region,
                120,
                310,
                2,
                ["ECS Fargate", "ALB"],
                "Run container services without Kubernetes control-plane operations.",
            ),
            self._candidate(
                "aws-ec2-managed",
                CandidateClass.VIRTUAL_MACHINE,
                "Managed virtual machines",
                region,
                140,
                360,
                3,
                ["EC2", "ALB"],
                "Run workloads needing host-level control or long-lived processes.",
            ),
            self._candidate(
                "aws-eks-governed",
                CandidateClass.KUBERNETES,
                "Managed Kubernetes",
                region,
                950,
                1450,
                4,
                ["EKS", "GPU node group", "ECR", "ALB", "Argo CD"],
                "Run Kubernetes-specific multi-service scheduling, policies and accelerator placement.",
            ),
            self._candidate(
                "aws-managed-ai",
                CandidateClass.MANAGED_AI,
                "Managed AI endpoint",
                region,
                90,
                360,
                1,
                ["Approved model API", "API Gateway"],
                "Use an approved managed model endpoint instead of hosting a model.",
            ),
            self._candidate(
                "aws-cpu-inference",
                CandidateClass.CPU_INFERENCE,
                "CPU self-hosted inference",
                region,
                180,
                480,
                2,
                ["ECS Fargate", "ECR"],
                "Run a modest self-hosted CPU model when a managed endpoint is unsuitable.",
            ),
            self._candidate(
                "aws-gpu-inference",
                CandidateClass.GPU_INFERENCE,
                "GPU inference",
                region,
                780,
                1650,
                4,
                ["GPU compute", "ECR", "ALB"],
                "Run an accelerator-backed model only when requirements justify it.",
            ),
        ]
        return all_candidates

    def _candidate(
        self,
        candidate_id: str,
        candidate_class: CandidateClass,
        name: str,
        region: str,
        low: int,
        high: int,
        complexity: int,
        services: list[str],
        purpose: str,
    ) -> ArchitectureCandidate:
        components = [
            ArchitectureComponent(
                name="application",
                purpose=purpose,
                service=service,
                private=service not in {"CloudFront", "API Gateway", "ALB"},
            )
            for service in services
        ]
        components.extend(
            [
                ArchitectureComponent(
                    name="secrets",
                    purpose="Hold references, never values in plans",
                    service="AWS Secrets Manager",
                )
            ]
        )
        return ArchitectureCandidate(
            candidate_id=candidate_id,
            candidate_class=candidate_class,
            display_name=name,
            region=region,
            components=components,
            cost_estimate=CostRange(
                monthly_low=low,
                monthly_high=high,
                assumptions=[
                    "AWS fixture catalogue",
                    "us-east-1-like list-price assumptions",
                    "estimate, not actual billing",
                ],
                catalog_version=self.catalog_version,
                estimated_at=datetime.now(UTC),
            ),
            cost_components=self._cost_components(candidate_class, low, high, purpose),
            operational_complexity=complexity,
            complexity_reasons=self._complexity_reasons(complexity),
            satisfies=[],
            new_resources_required=services + ["AWS Secrets Manager"],
            upgrade_triggers=[
                "Traffic, reliability, isolation, or runtime requirements exceed this profile."
            ],
        )

    def _evaluate(
        self,
        candidate: ArchitectureCandidate,
        spec: WorkloadSpec,
        inventory: CloudInventorySnapshot,
    ) -> ArchitectureCandidate:
        rejected: list[str] = []
        candidate.satisfies = ["AWS-only V1", f"region {candidate.region}"]
        klass = candidate.candidate_class
        if candidate.region not in inventory.approved_regions:
            rejected.append("region is not approved by discovered customer policy")
        if spec.requires_gpu and klass not in {
            CandidateClass.GPU_INFERENCE,
            CandidateClass.KUBERNETES,
        }:
            rejected.append("GPU requirement needs accelerator-backed compute")
        if not spec.requires_gpu and klass == CandidateClass.GPU_INFERENCE:
            rejected.append("no GPU requirement justifies accelerator cost")
        if spec.requires_kubernetes and klass != CandidateClass.KUBERNETES:
            rejected.append("workload requires Kubernetes-specific scheduling or policy")
        if klass == CandidateClass.KUBERNETES and not (
            spec.requires_kubernetes or (spec.requires_gpu and spec.multi_service)
        ):
            rejected.append("Kubernetes-specific capability is not required")
        if klass == CandidateClass.KUBERNETES and spec.requires_gpu:
            candidate.satisfies.append("GPU scheduling through an isolated accelerator node group")
        if klass == CandidateClass.STATIC and spec.workload_type not in {
            "static_site",
            "static_application",
        }:
            rejected.append("workload needs a runtime, not static hosting")
        if klass == CandidateClass.SERVERLESS and not (
            spec.event_driven or (not spec.containerized and spec.peak_rps <= 20)
        ):
            rejected.append("workload is not a short stateless event/API handler")
        if klass == CandidateClass.MANAGED_APPLICATION and (
            spec.event_driven or spec.requires_gpu or spec.multi_service or spec.peak_rps > 50
        ):
            rejected.append(
                "managed application profile cannot satisfy the requested workload shape"
            )
        if klass == CandidateClass.MANAGED_CONTAINERS and (
            spec.requires_gpu or spec.requires_kubernetes
        ):
            rejected.append(
                "managed container profile lacks the required accelerator or Kubernetes control"
            )
        if klass == CandidateClass.VIRTUAL_MACHINE and not (
            spec.execution_duration_minutes and spec.execution_duration_minutes > 60
        ):
            rejected.append("host-level or long-running execution control is not required")
        if klass == CandidateClass.MANAGED_AI and (
            spec.requires_gpu
            or spec.data_classification == "restricted"
            or not spec.model_requirements.get("allow_managed_model", True)
        ):
            rejected.append(
                "managed model endpoint conflicts with model, data, or control requirements"
            )
        if klass == CandidateClass.CPU_INFERENCE and (
            spec.requires_gpu or spec.model_requirements.get("allow_managed_model", False)
        ):
            rejected.append("CPU self-hosting is not the simplest permitted AI runtime")
        if spec.availability_target == "99.99%" and klass in {
            CandidateClass.STATIC,
            CandidateClass.SERVERLESS,
            CandidateClass.MANAGED_APPLICATION,
        }:
            rejected.append(
                "availability target needs a stronger multi-component resilience design"
            )
        if candidate.cost_estimate.monthly_high + 50 > spec.monthly_budget_usd:
            rejected.append(
                "estimated upper cost including required Prometheus/Grafana monitoring exceeds the hard monthly budget"
            )
        reusable = self._reusable(candidate, inventory, spec)
        if reusable:
            candidate.existing_resources_reused = reusable
            candidate.new_resources_required = [
                item for item in candidate.new_resources_required if item not in reusable
            ]
            candidate.cost_estimate.monthly_low = max(
                0, candidate.cost_estimate.monthly_low - 30 * len(reusable)
            )
            candidate.cost_estimate.monthly_high = max(
                candidate.cost_estimate.monthly_low,
                candidate.cost_estimate.monthly_high - 45 * len(reusable),
            )
            candidate.satisfies.append(f"reuses approved resources: {', '.join(reusable)}")
        if spec.requires_private_connectivity or spec.data_classification == "restricted":
            candidate.satisfies.append("private data/network boundary")
        candidate.valid = not rejected
        candidate.rejected_reasons = rejected
        if candidate.valid:
            candidate.risks = [
                "Estimate uses fixture pricing; verify current customer-specific pricing before execution."
            ]
        return candidate

    @staticmethod
    def _region(spec: WorkloadSpec, inventory: CloudInventorySnapshot) -> str:
        requested = spec.region_constraints[0] if spec.region_constraints else inventory.region
        if requested not in inventory.approved_regions:
            return requested
        return requested

    @staticmethod
    def _reusable(
        candidate: ArchitectureCandidate,
        inventory: CloudInventorySnapshot,
        spec: WorkloadSpec,
    ) -> list[str]:
        service_keys = {
            "EKS": "eks",
            "ECS Fargate": "ecs",
            "App Runner": "app_runner",
            "RDS PostgreSQL": "rds",
            "GPU compute": "gpu",
        }
        approved = set(inventory.approved_resources) | set(spec.existing_approved_resources)
        return [
            service
            for service, key in service_keys.items()
            if key in approved
            and any(component.service == service for component in candidate.components)
        ]

    @staticmethod
    def _cost_components(
        candidate_class: CandidateClass,
        low: int,
        high: int,
        purpose: str,
    ) -> list[CostComponent]:
        compute_category = (
            "accelerator" if candidate_class == CandidateClass.GPU_INFERENCE else "compute"
        )
        compute_low, compute_high = round(low * 0.7), round(high * 0.7)
        components = [
            CostComponent(
                category=compute_category,
                monthly_low=compute_low,
                monthly_high=compute_high,
                reason=purpose,
            ),
            CostComponent(
                category="operations",
                monthly_low=low - compute_low,
                monthly_high=high - compute_high,
                reason="logging, metrics, network, and managed-service overhead in this fixture estimate",
            ),
        ]
        if candidate_class in {
            CandidateClass.MANAGED_CONTAINERS,
            CandidateClass.KUBERNETES,
            CandidateClass.VIRTUAL_MACHINE,
            CandidateClass.GPU_INFERENCE,
        }:
            components.append(
                CostComponent(
                    category="networking",
                    monthly_low=0,
                    monthly_high=0,
                    reason="Included in this high-level range; confirm load-balancing and egress costs with live pricing.",
                )
            )
        return components

    @staticmethod
    def _complexity_reasons(score: int) -> list[str]:
        return {
            1: [
                "managed service",
                "no cluster administration",
                "minimal infrastructure primitives",
            ],
            2: [
                "container operations are managed",
                "bounded networking and scaling responsibility",
            ],
            3: ["host lifecycle and patching responsibility"],
            4: [
                "specialist runtime or cluster operations",
                "more recovery and scaling responsibility",
            ],
            5: ["cross-cloud or advanced distributed operations"],
        }[score]

    @staticmethod
    def _security_controls(spec: WorkloadSpec) -> list[str]:
        controls = [
            "least-privilege workload identity",
            "encrypted storage",
            "secret references only",
            "reviewed immutable plan",
        ]
        if spec.requires_private_connectivity or spec.data_classification == "restricted":
            controls.insert(0, "private networking")
        return controls

    @staticmethod
    def _alternative(candidate: ArchitectureCandidate) -> str:
        return f"{candidate.display_name}: ${candidate.cost_estimate.monthly_low}–${candidate.cost_estimate.monthly_high}/month, complexity {candidate.operational_complexity}/5."

    @staticmethod
    def _explanation(
        selected: ArchitectureCandidate, simpler_failed: list[ArchitectureCandidate]
    ) -> str:
        failed = "; ".join(
            f"{candidate.display_name}: {', '.join(candidate.rejected_reasons)}"
            for candidate in simpler_failed
        )
        suffix = (
            f" Simpler candidates failed because {failed}."
            if failed
            else " No lower-complexity viable candidate was within the configured cheapest cost band."
        )
        return (
            f"{selected.display_name} is the lowest-complexity option within the cheapest viable "
            f"cost band.{suffix}"
        )
