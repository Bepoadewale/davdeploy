from __future__ import annotations

from typing import Any

import pytest
from davdeploy.contracts import ModelResponse, ModelUsage, TenantScope
from davdeploy.domain import IntentScope
from davdeploy.intent import IntentOutOfScopeError, NovaIntentProvider
from davdeploy.main import translate
from davdeploy.model_gateway import NOVA_2_LITE_MODEL_ID, ModelGatewayUnavailable
from fastapi import HTTPException


def scope() -> TenantScope:
    return TenantScope(
        organization_id="org-demo",
        workspace_id="workspace-demo",
        project_id="project-demo",
        actor_id="user-founder",
    )


def proposal(**updates: Any) -> dict[str, Any]:
    base = {
        "request_scope": "INFRASTRUCTURE",
        "workload_type": "ai_api",
        "data_classification": "restricted",
        "average_rps": 20,
        "peak_rps": 100,
        "monthly_budget_usd": 1500,
        "environments": ["staging", "production"],
        "availability_target": "99.9%",
        "region_constraints": ["us-east-1"],
        "integration_requirements": ["slack"],
        "runtime": "containerized",
        "containerized": True,
        "event_driven": False,
        "stateful": True,
        "requires_private_connectivity": True,
        "requires_kubernetes": False,
        "requires_gpu": False,
        "multi_service": False,
        "execution_duration_minutes": None,
        "confidence": 0.91,
    }
    return base | updates


class RecordingGateway:
    def __init__(self, output: dict[str, Any] | list[dict[str, Any]]):
        self.output = output
        self.calls: list[tuple] = []

    def complete(self, request, document):
        raise AssertionError("unstructured completion must not be used")

    def generate_structured(self, request, document, output_schema=None):
        self.calls.append((request, document, output_schema))
        output = self.output
        if isinstance(output, list):
            output = output[min(len(self.calls) - 1, len(output) - 1)]
        return ModelResponse(
            request=request,
            output=output,
            usage=ModelUsage(input_tokens=200, output_tokens=80, latency_ms=25),
            finish_reason="end_turn",
            safety_result="bedrock-structured-output-validated",
        )

    def estimate_cost(self, request):
        return 0.0

    def validate_output(self, output):
        return isinstance(output, dict)


def provider(
    output: dict[str, Any] | list[dict[str, Any]],
) -> tuple[NovaIntentProvider, RecordingGateway]:
    gateway = RecordingGateway(output)
    return (
        NovaIntentProvider(
            gateway=gateway,
            model_id=NOVA_2_LITE_MODEL_ID,
            max_output_tokens=800,
            timeout_seconds=30,
            data_policy="bedrock-no-training",
        ),
        gateway,
    )


def test_nova_intent_is_typed_tenant_scoped_and_non_authoritative():
    intent_provider, gateway = provider(proposal())
    result = intent_provider.interpret(
        "Deploy this API with private customer data.", "example/support-rag-api", scope()
    )
    request, document, output_schema = gateway.calls[0]
    assert request.tenant.organization_id == "org-demo"
    assert request.provider == "bedrock"
    assert request.model == NOVA_2_LITE_MODEL_ID
    assert request.prompt_version == "intent-nova2-v2"
    assert document["selected_repository"] == "example/support-rag-api"
    assert "use false when the capability is not explicitly required" in document["task"]
    assert output_schema["additionalProperties"] is False
    assert result.spec.cloud == "aws"
    assert result.spec.unknowns == []
    assert result.spec.requires_kubernetes is False
    assert result.model_metadata["provider"] == "bedrock"
    assert "approval" not in result.spec.model_dump()


def test_nova_intent_rejects_unrelated_requests_before_creating_a_workload_spec():
    intent_provider, gateway = provider(proposal(request_scope="OUT_OF_SCOPE"))

    result = intent_provider.interpret("Should I buy a particular stock?", None, scope())

    assert len(gateway.calls) == 1
    assert result.request_scope == IntentScope.OUT_OF_SCOPE
    assert result.spec is None
    _, document, _ = gateway.calls[0]
    assert "investment picks and financial advice are OUT_OF_SCOPE" in document["task"]


def test_model_scope_classification_keeps_deploying_financial_software_in_scope():
    intent_provider, _ = provider(proposal(workload_type="stockbroker_application"))

    result = intent_provider.interpret(
        "Deploy my stockbroking application to AWS.", "example/broker", scope()
    )

    assert result.spec.workload_type == "stockbroker_application"


def test_nova_intent_keeps_only_allow_listed_customer_capabilities():
    intent_provider, _ = provider(
        proposal(capability_requirements=["ai", "payments", "made_up_aws_admin_access"])
    )

    result = intent_provider.interpret("Deploy my AI product.", "example/ai", scope())

    assert result.spec.capability_requirements == ["ai", "payments"]


def test_nova_intent_recalculates_material_unknowns_locally():
    intent_provider, _ = provider(
        proposal(
            average_rps=None,
            peak_rps=None,
            monthly_budget_usd=None,
            environments=[],
        )
    )
    result = intent_provider.interpret("Deploy my API.", "example/api", scope())
    assert result.spec.unknowns == [
        "average_rps",
        "peak_rps",
        "monthly_budget_usd",
        "environments",
    ]
    assert [question.field for question in result.questions] == result.spec.unknowns


def test_nova_intent_rejects_fields_outside_the_contract():
    intent_provider, _ = provider(proposal(execute_terraform=True))
    with pytest.raises(ModelGatewayUnavailable, match="after one repair"):
        intent_provider.interpret("Deploy my API.", "example/api", scope())


def test_nova_intent_repairs_one_schema_violation_and_records_usage():
    intent_provider, gateway = provider(
        [proposal(execute_terraform=True), proposal(workload_type="rag_application")]
    )
    result = intent_provider.interpret("Deploy my RAG API.", "example/rag", scope())
    assert len(gateway.calls) == 2
    assert result.spec.workload_type == "rag_application"
    assert result.model_metadata["usage"]["retry_count"] == 1


def test_nova_intent_repair_receives_bounded_validation_diagnostics():
    invalid = proposal(execute_terraform=True, average_rps="twenty")
    intent_provider, gateway = provider([invalid, proposal()])

    intent_provider.interpret("Deploy my API.", "example/api", scope())

    _, repair_document, _ = gateway.calls[1]
    assert repair_document["previous_response"] == invalid
    assert repair_document["validation_issues"] == [
        {"location": "average_rps", "type": "int_parsing"},
        {"location": "execute_terraform", "type": "extra_forbidden"},
    ]
    assert "input" not in repair_document["validation_issues"][0]


def test_model_gateway_failure_translates_to_bounded_service_unavailable():
    with pytest.raises(HTTPException) as raised:
        translate(ModelGatewayUnavailable("model response failed validation"))
    assert raised.value.status_code == 503


def test_out_of_scope_request_translates_to_actionable_client_error():
    with pytest.raises(HTTPException) as raised:
        translate(IntentOutOfScopeError())
    assert raised.value.status_code == 422
    assert "cannot answer general questions" in raised.value.detail
