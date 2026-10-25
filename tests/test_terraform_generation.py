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
        return ModelResponse(
            request=request,
            output=self.output,
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


def proposal(arguments=None):
    return {
        "resources": [
            {
                "resource_type": "aws_ecs_cluster",
                "name": "application",
                "arguments": arguments
                or {"name": "customer-application", "tags": {"ManagedBy": "davdeploy"}},
                "rationale": "Runs the approved managed-container workload.",
            }
        ],
        "assumptions": ["VPC identifiers are supplied during reviewed planning."],
        "limitations": ["Plan-only; provider schema validation is still required."],
    }


def generator(output):
    return NovaTerraformGenerator(
        gateway=RecordingGateway(output), max_output_tokens=800, timeout_seconds=30
    )


def test_nova_terraform_generation_is_typed_and_plan_only():
    instance = generator(proposal())
    result = instance.generate(approved_plan={"summary": {"selected_profile": "aws-ecs-fargate"}}, tenant=scope())

    request, document, schema = instance.gateway.calls[0]
    assert request.purpose.value == "terraform_generation"
    assert request.provider == "bedrock"
    assert "no provider blocks" in document["task"]
    assert schema["additionalProperties"] is False
    assert result.proposal.resources[0].resource_type == "aws_ecs_cluster"
    rendered = instance.terraform_json(result.proposal)
    assert rendered["resource"]["aws_ecs_cluster"]["application"]["name"] == "customer-application"


@pytest.mark.parametrize(
    "arguments,error",
    [
        ({"name": "x"}, "missing ManagedBy"),
        ({"tags": {"ManagedBy": "davdeploy"}, "provisioner": {}}, "forbidden field"),
        ({"tags": {"ManagedBy": "davdeploy"}, "value": "${file(\"secret\")}"}, "cannot read arbitrary"),
    ],
)
def test_nova_terraform_generation_rejects_unsafe_or_untagged_graphs(arguments, error):
    with pytest.raises(ModelGatewayUnavailable, match=error):
        generator(proposal(arguments)).generate(approved_plan={"kind": "approved"}, tenant=scope())
