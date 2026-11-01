from __future__ import annotations

from datetime import UTC, datetime

import pytest
from davdeploy.domain import CloudInventorySnapshot, EnvironmentName, WorkloadSpec
from davdeploy.planner import AwsV1Planner


def spec(**overrides) -> WorkloadSpec:
    baseline = {
        "workload_type": "ai_api",
        "source_repository": "https://github.com/example/workload",
        "data_classification": "internal",
        "average_rps": 2,
        "peak_rps": 10,
        "monthly_budget_usd": 1000,
        "environments": [EnvironmentName.STAGING],
        "confidence": 1,
        "containerized": True,
    }
    baseline.update(overrides)
    return WorkloadSpec(**baseline)


def plan(**overrides):
    return AwsV1Planner().plan(spec(**overrides))


def selected(**overrides):
    return plan(**overrides).selected_candidate_id


def test_tiny_stateless_api_is_not_eks():
    assert selected() == "aws-app-runner"


def test_small_container_api_prefers_managed_application():
    assert selected(peak_rps=20) == "aws-app-runner"


def test_event_driven_processor_prefers_serverless():
    assert (
        selected(workload_type="document_processor", event_driven=True, containerized=False)
        == "aws-lambda-api"
    )


def test_kubernetes_requirement_justifies_eks():
    assert (
        selected(
            requires_kubernetes=True,
            multi_service=True,
            peak_rps=500,
            monthly_budget_usd=1500,
        )
        == "aws-eks-governed"
    )


def test_gpu_requirement_selects_accelerator_profile():
    assert (
        selected(
            requires_gpu=True,
            model_requirements={"allow_managed_model": False},
            peak_rps=100,
            monthly_budget_usd=2000,
        )
        == "aws-gpu-inference"
    )


def test_complex_gpu_kubernetes_workload_justifies_specialised_eks_profile():
    result = plan(
        requires_gpu=True,
        requires_kubernetes=True,
        multi_service=True,
        peak_rps=100,
        monthly_budget_usd=1500,
        model_requirements={"allow_managed_model": False},
    )
    assert result.profile == "aws-eks-governed"
    assert "GPU node group" in {component.service for component in result.components}


def test_no_gpu_requirement_does_not_select_gpu_profile():
    assert selected(requires_gpu=False) != "aws-gpu-inference"


def test_existing_approved_resource_is_reused_before_duplicate_creation():
    inventory = CloudInventorySnapshot(
        approved_resources=["app_runner"], discovered_at=datetime.now(UTC)
    )
    result = AwsV1Planner().plan(spec(), inventory)
    assert result.profile == "aws-app-runner"
    assert result.existing_resources_reused == ["App Runner"]


def test_hard_budget_rejects_all_profiles_when_no_candidate_fits():
    with pytest.raises(ValueError, match="hard monthly budget"):
        plan(monthly_budget_usd=10)


def test_unapproved_region_is_rejected():
    with pytest.raises(ValueError, match="region is not approved"):
        plan(region_constraints=["ap-south-1"])


def test_cheapest_viable_band_prefers_simpler_candidate():
    result = plan(model_requirements={"allow_managed_model": True}, peak_rps=10)
    assert result.profile == "aws-app-runner"
    assert result.complexity_score == 1


def test_reliability_constraint_rejects_low_complexity_profiles():
    assert (
        selected(
            availability_target="99.99%",
            requires_kubernetes=True,
            multi_service=True,
            peak_rps=500,
            monthly_budget_usd=1500,
        )
        == "aws-eks-governed"
    )


def test_single_cloud_beats_unnecessary_multicloud_complexity():
    result = plan()
    assert result.cloud == "aws"
    assert all(candidate.provider == "aws" for candidate in result.candidates)


def test_kubernetes_requested_for_status_is_not_selected_without_need():
    result = plan()
    assert result.profile != "aws-eks-governed"
    eks = next(
        candidate for candidate in result.candidates if candidate.candidate_id == "aws-eks-governed"
    )
    assert "Kubernetes-specific capability is not required" in eks.rejected_reasons


def test_plan_explains_why_it_selected_the_simplest_viable_option():
    result = plan()
    assert "lowest-complexity" in (result.recommendation_reason or "")
    assert "band.$" not in (result.recommendation_reason or "")
    assert result.candidates


def test_composed_plan_selects_internal_modules_without_customer_service_choices():
    result = plan(
        stateful=True,
        event_driven=True,
        capability_requirements=["identity", "file_storage", "payments", "realtime"],
        environments=[EnvironmentName.PRODUCTION],
    )

    modules = {module.identifier: module for module in result.modules}
    assert {
        "aws-serverless-api",
        "aws-identity",
        "aws-file-storage",
        "aws-relational-data",
        "aws-jobs-events",
        "aws-payments-webhooks",
        "aws-realtime",
        "aws-observability",
        "aws-backup-recovery",
    } <= modules.keys()
    assert modules["aws-serverless-api"].execution_supported is False
    assert modules["aws-relational-data"].execution_supported is False
    assert "aws-identity" in modules["aws-realtime"].depends_on


def test_private_ai_plan_composes_private_and_ai_modules():
    result = plan(
        requires_private_connectivity=True,
        capability_requirements=["ai", "analytics"],
    )

    assert {"aws-ai-retrieval", "aws-data-analytics", "aws-private-connectivity"} <= {
        module.identifier for module in result.modules
    }


def test_universal_modules_have_typed_resource_and_policy_contracts():
    result = plan(capability_requirements=["identity", "file_storage"])
    contracts = {contract.module_id: contract for contract in result.module_contracts}

    assert "aws_cognito_user_pool" in contracts["aws-identity"].resources
    assert "mfa_policy" in contracts["aws-identity"].policy_controls
    assert "aws_s3_bucket" in contracts["aws-file-storage"].resources
    assert contracts["aws-managed-application"].destroy_supported is True


def test_data_and_asynchronous_modules_have_safe_contracts():
    result = plan(
        stateful=True,
        event_driven=True,
        capability_requirements=["nosql_data", "payments", "realtime"],
    )
    contracts = {contract.module_id: contract for contract in result.module_contracts}

    assert "aws_rds_cluster" in contracts["aws-relational-data"].resources
    assert "aws_dynamodb_table" in contracts["aws-nosql-data"].resources
    assert "dead_letter_queue" in contracts["aws-jobs-events"].policy_controls
    assert "signature_validation" in contracts["aws-payments-webhooks"].policy_controls


def test_execution_contracts_do_not_claim_unimplemented_module_execution():
    result = plan(capability_requirements=["identity"])
    execution = {entry.module_id: entry for entry in result.module_execution}

    assert execution["aws-managed-application"].execution_state == "PILOT_ELIGIBLE"
    assert execution["aws-identity"].execution_state == "IMPLEMENTATION_REQUIRED"
    assert "exact approved plan digest" in execution["aws-identity"].prerequisites


def test_advanced_modules_have_bounded_ai_data_media_and_streaming_contracts():
    result = plan(capability_requirements=["ai", "search", "analytics", "streaming", "media"])
    contracts = {contract.module_id: contract for contract in result.module_contracts}

    assert "guardrails" in contracts["aws-ai-retrieval"].policy_controls
    assert "aws_opensearch_domain" in contracts["aws-search"].resources
    assert "query_budget" in contracts["aws-data-analytics"].policy_controls
    assert "iterator_age" in contracts["aws-stream-processing"].observation
    assert "signed_delivery" in contracts["aws-media"].policy_controls


def test_specialised_scale_modules_require_explicit_controls():
    result = plan(
        requires_kubernetes=True,
        requires_gpu=True,
        multi_service=True,
        peak_rps=100,
        monthly_budget_usd=2_000,
        model_requirements={"allow_managed_model": False},
        capability_requirements=["private_connectivity"],
    )
    contracts = {contract.module_id: contract for contract in result.module_contracts}
    assert "gitops_review" in contracts["aws-kubernetes-platform"].policy_controls
    assert "private_routing" in contracts["aws-private-connectivity"].policy_controls

    gpu_result = plan(
        requires_gpu=True,
        peak_rps=100,
        monthly_budget_usd=2_000,
        model_requirements={"allow_managed_model": False},
    )
    gpu_contracts = {contract.module_id: contract for contract in gpu_result.module_contracts}
    assert "quota_check" in gpu_contracts["aws-gpu-inference"].policy_controls


def test_plan_exposes_operational_readiness_before_execution():
    result = plan(stateful=True)
    assert result.operational_readiness is not None
    assert result.operational_readiness.quota_evidence_state == "REQUIRED_BEFORE_EXECUTION"
    assert "database point-in-time recovery" in result.operational_readiness.recovery_controls
