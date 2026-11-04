from __future__ import annotations

import pytest
from davdeploy.contracts import ModelResponse, ModelUsage, TenantScope
from davdeploy.model_gateway import ModelGatewayUnavailable
from davdeploy.terraform_generation import NovaTerraformGenerator


class RecordingGateway:
    provider = "bedrock"

    def __init__(self, output):
        self.output = output
        self.calls = []

    def complete(self, request, document):
        raise AssertionError("Terraform generation must use structured output")

    def generate_structured(self, request, document, output_schema=None):
        self.calls.append((request, document, output_schema))
        output = self.output(request, document) if callable(self.output) else self.output
        return ModelResponse(
            request=request,
            output=output,
            usage=ModelUsage(input_tokens=100, output_tokens=60, latency_ms=10),
        )

    def estimate_cost(self, request):
        return 0.0

    def validate_output(self, output):
        return True


def scope():
    return TenantScope(
        organization_id="org-demo",
        workspace_id="org-demo",
        project_id="project-demo",
        actor_id="user-founder",
    )


def proposal(request, document, *, arguments=None, source_revision="revision-123"):
    return {
        "contract_version": "1.0",
        "source_revision": source_revision,
        "context_digest": request.input_digest,
        "resources": [
            {
                "resource_id": "application",
                "resource_type": "aws_ecs_cluster",
                "name": "application",
                "arguments": arguments
                or {"name": "customer-application", "tags": {"ManagedBy": "davdeploy"}},
                "rationale": "Runs the proposed application workload.",
            }
        ],
        "requirements": {"region": document["trusted_generation_context"]["region"]},
        "assumptions": ["Application traffic is synthetic in the current plan."],
        "limitations": ["Provider schema and live plan checks are not yet connected."],
    }


def generator(output):
    return NovaTerraformGenerator(
        gateway=RecordingGateway(output), max_output_tokens=800, timeout_seconds=30
    )


def test_nova_generation_uses_typed_contract_and_stays_plan_only():
    instance = generator(proposal)
    result = instance.generate(
        approved_plan={
            "summary": {"selected_profile": "aws-ecs-fargate"},
            "target": {"region": "us-east-1"},
        },
        tenant=scope(),
        source_revision="revision-123",
    )

    request, document, schema = instance.gateway.calls[0]
    assert request.purpose.value == "terraform_generation"
    assert request.provider == "bedrock"
    assert request.prompt_version == "terraform-nova2-contract-v2"
    assert document["trusted_generation_context"]["context_digest"] == request.input_digest
    assert "provider/backend configuration" in document["task"]
    assert schema["additionalProperties"] is False
    assert result.proposal.source_revision == "revision-123"
    assert result.proposal.resources[0].resource_type == "aws_ecs_cluster"
    rendered = instance.terraform_json(result.proposal)
    assert rendered["resource"]["aws_ecs_cluster"]["application"]["name"] == "customer-application"


@pytest.mark.parametrize(
    "arguments",
    [
        {"password": "plaintext"},
        {"provisioner": {}},
        {"value": "file(secret)"},
        {"user_data": "unsafe"},
    ],
)
def test_nova_generation_rejects_unsafe_contract_content(arguments):
    def invalid(request, document):
        return proposal(request, document, arguments=arguments)

    with pytest.raises(ModelGatewayUnavailable, match="violated the generation schema"):
        generator(invalid).generate(
            approved_plan={"target": {"region": "us-east-1"}}, tenant=scope()
        )


def test_nova_generation_rejects_untrusted_revision_or_region():
    def invalid_revision(request, document):
        return proposal(request, document, source_revision="different-revision")

    with pytest.raises(ModelGatewayUnavailable, match="source revision"):
        generator(invalid_revision).generate(
            approved_plan={"target": {"region": "us-east-1"}},
            tenant=scope(),
            source_revision="trusted-revision",
        )

    with pytest.raises(ModelGatewayUnavailable, match="trusted AWS region"):
        generator(proposal).generate(approved_plan={}, tenant=scope())
