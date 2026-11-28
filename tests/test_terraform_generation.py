from __future__ import annotations

import json

import pytest
from davdeploy.contracts import EvidenceKind, EvidenceRef, ModelResponse, ModelUsage, TenantScope
from davdeploy.generated_deployment_contract import GeneratedDeploymentProposal
from davdeploy.model_gateway import (
    BedrockNovaGateway,
    FallbackModelGateway,
    ModelGatewayUnavailable,
    NovaGatewayConfig,
    model_input_digest,
)
from davdeploy.nova_plan_access import SUPPORTED_PLAN_RESOURCE_TYPES
from davdeploy.terraform_generation import (
    _GRAPH_VALIDATION_FEEDBACK,
    _HEALTH_PAYLOAD_SIZE_GUIDANCE,
    _HEALTH_TARGET_COMPATIBILITY_GUIDANCE,
    _ID_PATTERN_GUIDANCE,
    _LAMBDA_CONTAINER_READINESS_GUIDANCE,
    _LAMBDA_EVENT_BINDING_GUIDANCE,
    _LAMBDA_HEALTH_ASSERTION_EXAMPLES,
    _LAMBDA_HTTP_RESPONSE_GUIDANCE,
    _PLAN_ACCESS_GUIDANCE,
    _RESOURCE_CREDENTIAL_GUIDANCE,
    _RESOURCE_GRAPH_GUIDANCE,
    _RESOURCE_NAME_GUIDANCE,
    _RESOURCE_OBJECT_SHAPE_GUIDANCE,
    _SECRET_REFERENCE_LOCATION_GUIDANCE,
    _UNKNOWN_ARGUMENTS_FIELD_GUIDANCE,
    NOVA_TERRAFORM_PROMPT_VERSION,
    NovaTerraformGenerationFailed,
    NovaTerraformGenerator,
    _canonical_field_path,
    _is_canonical_feedback_path,
    _sanitize_pydantic_feedback,
    _validation_guidance,
    _validation_issue,
    generation_context_digest,
)
from pydantic import ValidationError


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
        "contract_version": "1.1",
        "source_revision": source_revision,
        "context_digest": document["trusted_generation_context"]["context_digest"],
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


def queue_lambda_event_proposal(_request, document, *, include_binding):
    output = proposal(None, document)
    resources = [
        {
            "resource_id": "work-queue",
            "resource_type": "aws_sqs_queue",
            "name": "work_queue",
            "arguments": {},
            "outputs": [{"name": "arn", "value_type": "aws_arn"}],
            "rationale": "Receives asynchronous application work.",
        },
        {
            "resource_id": "work-handler",
            "resource_type": "aws_lambda_function",
            "name": "work_processor",
            "arguments": {},
            "outputs": [{"name": "arn", "value_type": "aws_arn"}],
            "rationale": "Processes asynchronous application work.",
        },
    ]
    if include_binding:
        resources.append(
            {
                "resource_id": "queue-binding",
                "resource_type": "aws_lambda_event_source_mapping",
                "name": "queue_binding",
                "arguments": {
                    "event_source_arn": {
                        "kind": "resource_reference",
                        "resource_id": "work-queue",
                        "output_name": "arn",
                        "value_type": "aws_arn",
                    },
                    "function_name": {
                        "kind": "resource_reference",
                        "resource_id": "work-handler",
                        "output_name": "arn",
                        "value_type": "aws_arn",
                    },
                    "enabled": True,
                    "batch_size": 1,
                },
                "rationale": "Connects the declared work queue to its Lambda processor.",
            }
        )
    output["resources"] = resources
    output["health_assertions"] = [
        {
            "kind": "event_processing",
            "target_resource_id": "work-handler",
            "source_resource_id": "work-queue",
            "description": "A queued message is processed by the worker.",
        }
    ]
    return output


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
    assert request.prompt_version == NOVA_TERRAFORM_PROMPT_VERSION
    assert "^[a-z][a-z0-9_]{0,62}$" in document["task"]
    assert "Do not use hyphens, uppercase letters, spaces, or punctuation" in document["task"]
    assert "^[a-z][a-z0-9-]{0,23}$" in document["task"]
    assert "resource_id=db-primary with name=primary_database" in document["task"]
    assert "Never copy a hyphenated resource_id" in document["task"]
    assert "source_resource_id only for event_processing" in document["task"]
    assert "copy every reference exactly from its declared resource_id" in document["task"]
    assert "Never use underscores, uppercase, spaces, dots, slashes" in document["task"]
    assert "environment[0].variables.<NAME>_SECRET_ARN" in document["task"]
    assert "value_type=secret_reference" in document["task"]
    assert '"manage_master_user_password":true' in document["task"]
    assert '"output_name":"master_user_secret[0].secret_arn"' in document["task"]
    assert '"kind":"resource_reference"' in document["task"]
    assert "payload_size_bytes only for storage_roundtrip or queue_roundtrip" in document["task"]
    assert "integer from 1 to 4096 inclusive" in document["task"]
    assert "http_response use max_response_bytes" in document["task"]
    assert "inference_response use minimum_response_bytes" in document["task"]
    assert "Treat resource IDs and references as short machine keys" in document["task"]
    assert "fixed vocabulary: api, web, app, db, files, bucket, table, queue" in document["task"]
    assert "append a numeric suffix such as -2 or -3" in document["task"]
    assert "stay within 24 characters" in document["task"]
    assert "without weakening customer requirements or inventing resource IDs" in document["task"]
    assert NOVA_TERRAFORM_PROMPT_VERSION == "terraform-nova2-contract-v29"
    assert "master_user_secret[0].secret_arn" in document["task"]
    assert _HEALTH_TARGET_COMPATIBILITY_GUIDANCE in document["task"]
    assert _LAMBDA_HEALTH_ASSERTION_EXAMPLES in document["task"]
    assert "arguments.event_source_arn" in document["task"]
    assert "arguments.function_name" in document["task"]
    assert '"value_type":"aws_arn"' in document["task"]
    assert "every `http_response` target is an `aws_apigatewayv2_stage`" in document["task"]
    assert "database_roundtrip: aws_db_instance, aws_dynamodb_table, aws_rds_cluster" in document["task"]
    assert "target the declared aws_db_instance or aws_rds_cluster resource itself" in document["task"]
    assert _LAMBDA_CONTAINER_READINESS_GUIDANCE in document["task"]
    assert "secret_reference_location" in document["task"]
    assert "report the limitation instead of inventing a resource" in document["task"]
    assert document["trusted_generation_context"]["context_digest"] == generation_context_digest(
        {
            "summary": {"selected_profile": "aws-ecs-fargate"},
            "target": {"region": "us-east-1"},
        },
        "revision-123",
    )
    assert request.input_digest == model_input_digest(document)
    assert "provider, provisioner, connection, backend" in document["task"]
    assert "contract_version to 1.1" in document["task"]
    assert "not evidence that a check ran" in document["task"]
    assert schema["additionalProperties"] is False
    assert result.proposal.source_revision == "revision-123"
    assert result.proposal.resources[0].resource_type == "aws_ecs_cluster"
    rendered = instance.terraform_json(result.proposal)
    assert rendered["resource"]["aws_ecs_cluster"]["application"]["name"] == "customer-application"


def test_nova_generation_normalizes_a_bounded_resource_id_before_strict_validation():
    def malformed_id(request, document):
        output = proposal(request, document)
        output["resources"][0]["resource_id"] = "API Gateway"
        return output

    instance = generator(malformed_id)
    result = instance.generate(
        approved_plan={"target": {"region": "us-east-1"}},
        tenant=scope(),
        source_revision="revision-123",
    )

    assert result.proposal.resources[0].resource_id == "api-gateway"
    assert len(instance.gateway.calls) == 1


def test_malformed_resource_type_reaches_bounded_validation_repair():
    def malformed_then_valid(request, document):
        if len(gateway.calls) == 1:
            output = proposal(request, document)
            output["resources"][0]["resource_type"] = ["aws_db_instance"]
            return output
        return proposal(request, document)

    gateway = RecordingGateway(malformed_then_valid)
    instance = NovaTerraformGenerator(
        gateway=gateway, max_output_tokens=800, timeout_seconds=30
    )
    result = instance.generate(
        approved_plan={"target": {"region": "us-east-1"}},
        tenant=scope(),
        source_revision="revision-123",
    )

    assert result.proposal.resources[0].resource_type == "aws_ecs_cluster"
    assert len(gateway.calls) == 2


def test_nova_generation_binds_lambda_secret_arn_to_unique_managed_database_secret():
    def literal_secret_arn(request, document):
        output = proposal(request, document)
        output["resources"] = [
            {
                "resource_id": "db",
                "resource_type": "aws_db_instance",
                "name": "database",
                "arguments": {"manage_master_user_password": False},
                "outputs": [],
                "rationale": "Stores application records.",
            },
            {
                "resource_id": "api",
                "resource_type": "aws_lambda_function",
                "name": "api",
                "arguments": {
                    "environment": [
                        {"variables": {"DATABASE_SECRET_ARN": "literal-must-not-survive"}}
                    ]
                },
                "rationale": "Processes application requests.",
            },
        ]
        return output

    instance = generator(literal_secret_arn)
    result = instance.generate(
        approved_plan={"target": {"region": "us-east-1"}},
        tenant=scope(),
        source_revision="revision-123",
    )

    database, lambda_resource = result.proposal.resources
    reference = lambda_resource.arguments["environment"][0]["variables"]["DATABASE_SECRET_ARN"]
    assert database.arguments["manage_master_user_password"] is True
    assert database.outputs[0].name == "master_user_secret[0].secret_arn"
    assert database.outputs[0].sensitive is True
    assert reference == {
        "kind": "resource_reference",
        "resource_id": "db",
        "output_name": "master_user_secret[0].secret_arn",
        "value_type": "secret_reference",
    }
    assert len(instance.gateway.calls) == 1


def test_incompatible_health_target_gets_exact_feedback_and_bounded_rds_repair():
    gateway = RecordingGateway(None)

    def incompatible_then_correct(request, document):
        output = proposal(request, document)
        output["resources"] = [
            {
                "resource_id": "db",
                "resource_type": "aws_rds_cluster",
                "name": "database",
                "arguments": {"manage_master_user_password": True},
                "rationale": "Stores relational application records.",
            },
            {
                "resource_id": "api-secret-key",
                "resource_type": "aws_ecs_service",
                "name": "api",
                "arguments": {},
                "rationale": "Serves application requests.",
            },
        ]
        output["health_assertions"] = [
            {
                "kind": "database_roundtrip",
                "target_resource_id": "api-secret-key" if len(gateway.calls) == 1 else "db",
                "description": "Write, read, and delete a synthetic relational record.",
            }
        ]
        return output

    gateway.output = incompatible_then_correct
    instance = NovaTerraformGenerator(
        gateway=gateway, max_output_tokens=800, timeout_seconds=30
    )
    result = instance.generate(
        approved_plan={"target": {"region": "us-east-1"}},
        tenant=scope(),
        source_revision="revision-123",
    )

    repair_feedback = gateway.calls[1][1]["validation_feedback"]
    assert repair_feedback == [
        {
            "code": "value_error",
            "field": "health_assertions[*].target_resource_id",
            "issue": "incompatible_health_target",
            "guidance": _HEALTH_TARGET_COMPATIBILITY_GUIDANCE,
            "assertion_kind": "database_roundtrip",
            "observed_resource_type": "aws_ecs_service",
        }
    ]
    assert "api-secret-key" not in str(repair_feedback)
    assert result.proposal.health_assertions[0].target_resource_id == "db"
    assert len(gateway.calls) == 2


def test_lambda_container_readiness_feedback_preserves_http_health_requirement():
    gateway = RecordingGateway(None)

    def incompatible_then_correct(request, document):
        output = proposal(request, document)
        output["resources"] = [
            {
                "resource_id": "health-handler-7a1",
                "resource_type": "aws_lambda_function",
                "name": "function",
                "arguments": {},
                "outputs": [{"name": "function_arn", "value_type": "aws_arn"}],
                "rationale": "Handles application requests.",
            },
            {
                "resource_id": "http-api-4c2",
                "resource_type": "aws_apigatewayv2_api",
                "name": "http_api",
                "arguments": {},
                "outputs": [{"name": "api_id", "value_type": "resource_name"}],
                "rationale": "Exposes the declared application HTTP API.",
            },
            {
                "resource_id": "integration-x90",
                "resource_type": "aws_apigatewayv2_integration",
                "name": "http_integration",
                "arguments": {
                    "api_id": {
                        "kind": "resource_reference",
                        "resource_id": "http-api-4c2",
                        "output_name": "api_id",
                        "value_type": "resource_name",
                    },
                    "integration_uri": {
                        "kind": "resource_reference",
                        "resource_id": "health-handler-7a1",
                        "output_name": "function_arn",
                        "value_type": "aws_arn",
                    },
                },
                "outputs": [{"name": "integration_id", "value_type": "resource_name"}],
                "rationale": "Connects the API to the declared Lambda function.",
            },
            {
                "resource_id": "route-y90",
                "resource_type": "aws_apigatewayv2_route",
                "name": "http_route",
                "arguments": {
                    "api_id": {
                        "kind": "resource_reference",
                        "resource_id": "http-api-4c2",
                        "output_name": "api_id",
                        "value_type": "resource_name",
                    },
                    "target": {
                        "kind": "resource_reference",
                        "resource_id": "integration-x90",
                        "output_name": "integration_id",
                        "value_type": "resource_name",
                    },
                },
                "rationale": "Routes HTTP requests through the Lambda integration.",
            },
            {
                "resource_id": "gateway-stage-22",
                "resource_type": "aws_apigatewayv2_stage",
                "name": "gateway_stage",
                "arguments": {
                    "api_id": {
                        "kind": "resource_reference",
                        "resource_id": "http-api-4c2",
                        "output_name": "api_id",
                        "value_type": "resource_name",
                    }
                },
                "rationale": "Provides the API endpoint for HTTP health checks.",
            },
        ]
        output["health_assertions"] = [
            {
                "kind": "container_readiness",
                "target_resource_id": "health-handler-7a1" if len(gateway.calls) == 1 else "gateway-stage-22",
                "description": "The HTTP application responds successfully.",
            }
        ]
        if len(gateway.calls) > 1:
            output["health_assertions"][0] = {
                "kind": "http_response",
                "target_resource_id": "gateway-stage-22",
                "path": "/health",
                "method": "GET",
                "expected_status_code": 200,
                "description": "The HTTP application health endpoint responds successfully.",
            }
        return output

    gateway.output = incompatible_then_correct
    instance = NovaTerraformGenerator(
        gateway=gateway, max_output_tokens=800, timeout_seconds=30
    )
    result = instance.generate(
        approved_plan={"target": {"region": "us-east-1"}},
        tenant=scope(),
        source_revision="revision-123",
    )

    repair_feedback = gateway.calls[1][1]["validation_feedback"]
    assert repair_feedback == [
        {
            "code": "value_error",
            "field": "health_assertions[*].target_resource_id",
            "issue": "incompatible_health_target",
            "guidance": _LAMBDA_CONTAINER_READINESS_GUIDANCE,
            "assertion_kind": "container_readiness",
            "observed_resource_type": "aws_lambda_function",
        }
    ]
    assert not any(
        resource_id in str(repair_feedback)
        for resource_id in (
            "health-handler-7a1",
            "http-api-4c2",
            "integration-x90",
            "route-y90",
            "gateway-stage-22",
        )
    )
    assert result.proposal.health_assertions[0].kind == "http_response"
    assert result.proposal.health_assertions[0].target_resource_id == "gateway-stage-22"
    assert "health endpoint responds successfully" in result.proposal.health_assertions[0].description
    assert len(gateway.calls) == 2


def test_lambda_http_response_feedback_targets_the_declared_api_gateway_stage():
    gateway = RecordingGateway(None)

    def incompatible_then_correct(request, document):
        output = proposal(request, document)
        output["resources"] = [
            {
                "resource_id": "health-handler-7a1",
                "resource_type": "aws_lambda_function",
                "name": "function",
                "arguments": {},
                "outputs": [{"name": "function_arn", "value_type": "aws_arn"}],
                "rationale": "Handles application requests.",
            },
            {
                "resource_id": "http-api-4c2",
                "resource_type": "aws_apigatewayv2_api",
                "name": "http_api",
                "arguments": {},
                "outputs": [{"name": "api_id", "value_type": "resource_name"}],
                "rationale": "Exposes the selected application HTTP API.",
            },
            {
                "resource_id": "integration-x90",
                "resource_type": "aws_apigatewayv2_integration",
                "name": "http_integration",
                "arguments": {
                    "api_id": {
                        "kind": "resource_reference",
                        "resource_id": "http-api-4c2",
                        "output_name": "api_id",
                        "value_type": "resource_name",
                    },
                    "integration_uri": {
                        "kind": "resource_reference",
                        "resource_id": "health-handler-7a1",
                        "output_name": "function_arn",
                        "value_type": "aws_arn",
                    },
                },
                "outputs": [{"name": "integration_id", "value_type": "resource_name"}],
                "rationale": "Connects the selected API to the Lambda function.",
            },
            {
                "resource_id": "route-y90",
                "resource_type": "aws_apigatewayv2_route",
                "name": "http_route",
                "arguments": {
                    "api_id": {
                        "kind": "resource_reference",
                        "resource_id": "http-api-4c2",
                        "output_name": "api_id",
                        "value_type": "resource_name",
                    },
                    "target": {
                        "kind": "resource_reference",
                        "resource_id": "integration-x90",
                        "output_name": "integration_id",
                        "value_type": "resource_name",
                    },
                },
                "rationale": "Routes HTTP requests through the Lambda integration.",
            },
            {
                "resource_id": "gateway-stage-22",
                "resource_type": "aws_apigatewayv2_stage",
                "name": "gateway_stage",
                "arguments": {
                    "api_id": {
                        "kind": "resource_reference",
                        "resource_id": "http-api-4c2",
                        "output_name": "api_id",
                        "value_type": "resource_name",
                    }
                },
                "rationale": "Exposes the HTTP API for the health check.",
            },
        ]
        output["health_assertions"] = [
            {
                "kind": "http_response",
                "target_resource_id": (
                    "health-handler-7a1" if len(gateway.calls) == 1 else "gateway-stage-22"
                ),
                "path": "/health",
                "method": "GET",
                "expected_status_code": 200,
                "description": "The HTTP application health endpoint responds successfully.",
            }
        ]
        return output

    gateway.output = incompatible_then_correct
    instance = NovaTerraformGenerator(
        gateway=gateway, max_output_tokens=800, timeout_seconds=30
    )
    approved_plan = {"summary": {"selected_profile": "aws-lambda-api"}, "target": {"region": "us-east-1"}}
    result = instance.generate(
        approved_plan=approved_plan,
        tenant=scope(),
        source_revision="revision-123",
    )

    repair_feedback = gateway.calls[1][1]["validation_feedback"]
    assert repair_feedback == [
        {
            "code": "value_error",
            "field": "health_assertions[*].target_resource_id",
            "issue": "incompatible_health_target",
            "guidance": _LAMBDA_HTTP_RESPONSE_GUIDANCE,
            "assertion_kind": "http_response",
            "observed_resource_type": "aws_lambda_function",
        }
    ]
    assert not any(
        resource_id in str(repair_feedback)
        for resource_id in ("health-handler-7a1", "http-api-4c2", "gateway-stage-22")
    )
    assert gateway.calls[0][1]["trusted_generation_context"] == gateway.calls[1][1][
        "trusted_generation_context"
    ]
    assert result.proposal.health_assertions[0].kind == "http_response"
    assert result.proposal.health_assertions[0].target_resource_id == "gateway-stage-22"
    assert len(gateway.calls) == 2


def test_lambda_http_response_without_declared_api_stage_fails_with_actionable_feedback():
    def unsupported_health_target(request, document):
        output = proposal(request, document)
        output["resources"] = [
            {
                "resource_id": "health-handler-7a1",
                "resource_type": "aws_lambda_function",
                "name": "health_handler",
                "arguments": {},
                "rationale": "Handles application requests.",
            }
        ]
        output["health_assertions"] = [
            {
                "kind": "http_response",
                "target_resource_id": "health-handler-7a1",
                "path": "/health",
                "method": "GET",
                "expected_status_code": 200,
                "description": "The HTTP application health endpoint responds successfully.",
            }
        ]
        return output

    gateway = RecordingGateway(unsupported_health_target)
    instance = NovaTerraformGenerator(
        gateway=gateway, max_output_tokens=800, timeout_seconds=30
    )
    with pytest.raises(NovaTerraformGenerationFailed) as failure:
        instance.generate(
            approved_plan={"summary": {"selected_profile": "aws-lambda-api"}, "target": {"region": "us-east-1"}},
            tenant=scope(),
            source_revision="revision-123",
        )

    assert failure.value.validation_feedback == (
        {
            "code": "value_error",
            "field": "health_assertions[*].target_resource_id",
            "issue": "incompatible_health_target",
            "guidance": _LAMBDA_HTTP_RESPONSE_GUIDANCE,
            "assertion_kind": "http_response",
            "observed_resource_type": "aws_lambda_function",
        },
    )
    assert len(gateway.calls) == 2


def test_missing_event_binding_feedback_repairs_with_typed_queue_and_lambda_references():
    gateway = RecordingGateway(None)

    def missing_then_correct(request, document):
        return queue_lambda_event_proposal(
            request, document, include_binding=len(gateway.calls) > 1
        )

    gateway.output = missing_then_correct
    instance = NovaTerraformGenerator(
        gateway=gateway, max_output_tokens=800, timeout_seconds=30
    )
    approved_plan = {
        "summary": {"selected_profile": "aws-lambda-api"},
        "target": {"region": "us-east-1"},
    }
    result = instance.generate(
        approved_plan=approved_plan,
        tenant=scope(),
        source_revision="revision-123",
    )

    repair_feedback = gateway.calls[1][1]["validation_feedback"]
    assert repair_feedback == [
        {
            "code": "value_error",
            "field": "proposal",
            "issue": "missing_event_binding",
            "guidance": _LAMBDA_EVENT_BINDING_GUIDANCE,
        }
    ]
    assert not any(
        value in str(repair_feedback)
        for value in ("work-queue", "work-handler", "queue-binding")
    )
    assert gateway.calls[0][1]["trusted_generation_context"] == gateway.calls[1][1][
        "trusted_generation_context"
    ]
    assertion = result.proposal.health_assertions[0]
    assert assertion.kind == "event_processing"
    assert assertion.target_resource_id == "work-handler"
    assert assertion.source_resource_id == "work-queue"
    mapping = next(
        item
        for item in result.proposal.resources
        if item.resource_type == "aws_lambda_event_source_mapping"
    )
    assert mapping.arguments["event_source_arn"] == {
        "kind": "resource_reference",
        "resource_id": "work-queue",
        "output_name": "arn",
        "value_type": "aws_arn",
    }
    assert mapping.arguments["function_name"] == {
        "kind": "resource_reference",
        "resource_id": "work-handler",
        "output_name": "arn",
        "value_type": "aws_arn",
    }
    assert len(gateway.calls) == 2


def test_missing_event_binding_without_valid_declared_resources_fails_closed():
    gateway = RecordingGateway(
        lambda request, document: queue_lambda_event_proposal(
            request, document, include_binding=False
        )
    )
    instance = NovaTerraformGenerator(
        gateway=gateway, max_output_tokens=800, timeout_seconds=30
    )

    with pytest.raises(NovaTerraformGenerationFailed) as failure:
        instance.generate(
            approved_plan={
                "summary": {"selected_profile": "aws-lambda-api"},
                "target": {"region": "us-east-1"},
            },
            tenant=scope(),
            source_revision="revision-123",
        )

    assert failure.value.attempt_count == 2
    assert failure.value.validation_feedback == (
        {
            "code": "value_error",
            "field": "proposal",
            "issue": "missing_event_binding",
            "guidance": _LAMBDA_EVENT_BINDING_GUIDANCE,
        },
    )
    assert len(gateway.calls) == 2


def test_lambda_container_readiness_without_declared_alternative_fails_closed():
    def unsupported_health_target(request, document):
        output = proposal(request, document)
        output["resources"] = [
            {
                "resource_id": "health-handler-7a1",
                "resource_type": "aws_lambda_function",
                "name": "health_handler",
                "arguments": {},
                "rationale": "Handles application requests.",
            }
        ]
        output["health_assertions"] = [
            {
                "kind": "container_readiness",
                "target_resource_id": "health-handler-7a1",
                "description": "The application must be ready to serve requests.",
            }
        ]
        return output

    instance = NovaTerraformGenerator(
        gateway=RecordingGateway(unsupported_health_target),
        max_output_tokens=800,
        timeout_seconds=30,
    )
    with pytest.raises(NovaTerraformGenerationFailed) as failure:
        instance.generate(
            approved_plan={"target": {"region": "us-east-1"}},
            tenant=scope(),
            source_revision="revision-123",
        )

    assert failure.value.attempt_count == 2
    assert failure.value.validation_feedback == (
        {
            "code": "value_error",
            "field": "health_assertions[*].target_resource_id",
            "issue": "incompatible_health_target",
            "guidance": _LAMBDA_CONTAINER_READINESS_GUIDANCE,
            "assertion_kind": "container_readiness",
            "observed_resource_type": "aws_lambda_function",
        },
    )
    assert "report that limitation" in failure.value.validation_feedback[0]["guidance"]
    assert "health-handler-7a1" not in str(failure.value.validation_feedback)
    assert len(instance.gateway.calls) == 2


def test_health_assertion_pattern_feedback_keeps_the_canonical_nested_field():
    invalid = {
        "contract_version": "1.1",
        "source_revision": "revision-123",
        "context_digest": "0" * 64,
        "resources": [
            {
                "resource_id": "api",
                "resource_type": "aws_s3_bucket",
                "name": "files",
                "arguments": {},
                "rationale": "Synthetic test resource.",
            }
        ],
        "requirements": {"region": "us-east-1"},
        "health_assertions": [
            {
                "kind": "storage_roundtrip",
                "target_resource_id": "bad_id",
                "description": "Synthetic storage check.",
            }
        ],
    }
    with pytest.raises(ValidationError) as error:
        GeneratedDeploymentProposal.model_validate(invalid)

    feedback = _sanitize_pydantic_feedback(error.value)
    assert feedback == [
        {
            "code": "string_pattern_mismatch",
            "field": "health_assertions[*].target_resource_id",
            "guidance": _ID_PATTERN_GUIDANCE,
        }
    ]


@pytest.mark.parametrize(("payload_size", "code"), [(0, "greater_than_equal"), (4097, "less_than_equal")])
def test_health_payload_bounds_return_fixed_safe_guidance(payload_size, code):
    invalid = {
        "contract_version": "1.1",
        "source_revision": "revision-123",
        "context_digest": "0" * 64,
        "resources": [
            {
                "resource_id": "files",
                "resource_type": "aws_s3_bucket",
                "name": "files",
                "arguments": {},
                "rationale": "Synthetic test resource.",
            }
        ],
        "requirements": {"region": "us-east-1"},
        "health_assertions": [
            {
                "kind": "storage_roundtrip",
                "target_resource_id": "files",
                "description": "Synthetic storage check.",
                "payload_size_bytes": payload_size,
            }
        ],
    }
    with pytest.raises(ValidationError) as error:
        GeneratedDeploymentProposal.model_validate(invalid)

    feedback = _sanitize_pydantic_feedback(error.value)
    item = next(entry for entry in feedback if entry["field"] == "health_assertions[*].payload_size_bytes")
    assert item == {
        "code": code,
        "field": "health_assertions[*].payload_size_bytes",
        "guidance": _HEALTH_PAYLOAD_SIZE_GUIDANCE,
    }
    assert set(item) == {"code", "field", "guidance"}


def test_health_payload_size_on_wrong_assertion_kind_is_rejected_with_guidance():
    invalid = {
        "contract_version": "1.1",
        "source_revision": "revision-123",
        "context_digest": "0" * 64,
        "resources": [
            {
                "resource_id": "api",
                "resource_type": "aws_s3_bucket",
                "name": "files",
                "arguments": {},
                "rationale": "Synthetic test resource.",
            }
        ],
        "requirements": {"region": "us-east-1"},
        "health_assertions": [
            {
                "kind": "http_response",
                "target_resource_id": "api",
                "description": "Synthetic HTTP check.",
                "payload_size_bytes": 128,
            }
        ],
    }
    with pytest.raises(ValidationError) as error:
        GeneratedDeploymentProposal.model_validate(invalid)

    feedback = _sanitize_pydantic_feedback(error.value)
    item = next(
        entry
        for entry in feedback
        if entry["field"] == "health_assertions[*].payload_size_bytes"
        and entry["code"] == "extra_forbidden"
    )
    assert item["guidance"] == _HEALTH_PAYLOAD_SIZE_GUIDANCE
    assert "128" not in repr(feedback)


def test_unknown_health_payload_error_uses_fixed_guidance_and_redacts_details():
    from pydantic_core import PydanticCustomError

    error = ValidationError.from_exception_data(
        "GeneratedDeploymentProposal",
        [
            {
                "type": PydanticCustomError(
                    "private_payload_validator",
                    "private value {secret}",
                    {"secret": "must-not-escape"},
                ),
                "loc": ("health_assertions", 0, "payload_size_bytes"),
                "input": 987654,
            }
        ],
    )

    feedback = _sanitize_pydantic_feedback(error)
    assert feedback == [
        {
            "code": "invalid",
            "field": "health_assertions[*].payload_size_bytes",
            "guidance": _HEALTH_PAYLOAD_SIZE_GUIDANCE,
        }
    ]
    rendered = repr(feedback)
    assert "private_payload_validator" not in rendered
    assert "must-not-escape" not in rendered
    assert "987654" not in rendered


def test_resource_name_pattern_feedback_distinguishes_name_from_resource_id():
    invalid = {
        "contract_version": "1.1",
        "source_revision": "revision-123",
        "context_digest": "0" * 64,
        "resources": [
            {
                "resource_id": "api-service",
                "resource_type": "aws_s3_bucket",
                "name": "api-service",
                "arguments": {},
                "rationale": "Synthetic test resource.",
            }
        ],
        "requirements": {"region": "us-east-1"},
    }
    with pytest.raises(ValidationError) as error:
        GeneratedDeploymentProposal.model_validate(invalid)

    feedback = _sanitize_pydantic_feedback(error.value)
    assert feedback[0] == {
        "code": "string_pattern_mismatch",
        "field": "resources[*].name",
        "guidance": _RESOURCE_NAME_GUIDANCE,
    }
    assert all(item["field"] != "resources[*].resource_id" for item in feedback)


def test_resource_id_pattern_feedback_is_actionable_and_redacts_invalid_value():
    invalid_id = "AWS_Resource_Identifier_Too_Long"
    invalid = {
        "contract_version": "1.1",
        "source_revision": "revision-123",
        "context_digest": "0" * 64,
        "resources": [
            {
                "resource_id": invalid_id,
                "resource_type": "aws_s3_bucket",
                "name": "files",
                "arguments": {},
                "rationale": "Synthetic test resource.",
            }
        ],
        "requirements": {"region": "us-east-1"},
    }
    with pytest.raises(ValidationError) as error:
        GeneratedDeploymentProposal.model_validate(invalid)

    feedback = _sanitize_pydantic_feedback(error.value)
    item = next(entry for entry in feedback if entry["field"] == "resources[*].resource_id")
    assert item == {
        "code": "string_pattern_mismatch",
        "field": "resources[*].resource_id",
        "guidance": _ID_PATTERN_GUIDANCE,
    }
    rendered = repr(feedback)
    assert invalid_id not in rendered
    assert "AWS_Resource" not in rendered


def test_unknown_validator_error_keeps_safe_path_and_uses_fixed_field_guidance():
    from pydantic_core import PydanticCustomError

    error = ValidationError.from_exception_data(
        "GeneratedDeploymentProposal",
        [
            {
                "type": PydanticCustomError(
                    "private_validator_code",
                    "private validator detail: {secret}",
                    {"secret": "must-not-escape"},
                ),
                "loc": ("resources", 0, "name"),
                "input": "private-invalid-value",
            }
        ],
    )

    feedback = _sanitize_pydantic_feedback(error)
    assert feedback == [
        {
            "code": "invalid",
            "field": "resources[*].name",
            "guidance": _RESOURCE_NAME_GUIDANCE,
        }
    ]
    failure = NovaTerraformGenerationFailed(
        "bounded failure",
        attempt_count=2,
        usage=ModelUsage(),
        evidence=(),
        validation_feedback=tuple(feedback),
    )
    assert failure.validation_feedback == tuple(feedback)
    assert "private_validator_code" not in repr(failure.validation_feedback)
    assert "must-not-escape" not in repr(failure.validation_feedback)
    assert "private-invalid-value" not in repr(failure.validation_feedback)


def test_unknown_nested_path_is_truncated_before_unrecognized_argument_name():
    from pydantic_core import PydanticCustomError

    error = ValidationError.from_exception_data(
        "GeneratedDeploymentProposal",
        [
            {
                "type": PydanticCustomError(
                    "private_nested_validator_code",
                    "private detail: {secret}",
                    {"secret": "do-not-expose"},
                ),
                "loc": ("resources", 0, "arguments", "untrusted_private_attribute"),
                "input": "private-input-value",
            }
        ],
    )

    feedback = _sanitize_pydantic_feedback(error)
    assert feedback == [
        {
            "code": "invalid",
            "field": "resources[*].arguments",
            "guidance": _UNKNOWN_ARGUMENTS_FIELD_GUIDANCE,
        }
    ]
    assert _is_canonical_feedback_path(feedback[0]["field"])
    rendered = repr(feedback)
    assert "private_nested_validator_code" not in rendered
    assert "untrusted_private_attribute" not in rendered
    assert "do-not-expose" not in rendered
    assert "private-input-value" not in rendered


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        (("resources", 0, "name"), "resources[*].name"),
        (("resources", 0, "arguments", object()), "resources[*].arguments"),
        (("requirements", "region", object()), "requirements.region"),
        (("untrusted_top_level", "field"), "proposal"),
        (("resources", "not-an-index", "name"), "resources"),
        (123, "proposal"),
    ],
)
def test_unknown_error_paths_fail_closed_to_canonical_schema_prefix(location, expected):
    field = _canonical_field_path(location)
    assert field == expected
    assert _is_canonical_feedback_path(field)
    assert not _is_canonical_feedback_path("resources[*].untrusted_private_attribute")


def test_resource_graph_feedback_uses_fixed_guidance_for_unknown_dependency():
    invalid = {
        "contract_version": "1.1",
        "source_revision": "revision-123",
        "context_digest": "0" * 64,
        "resources": [
            {
                "resource_id": "api",
                "resource_type": "aws_s3_bucket",
                "name": "files",
                "arguments": {},
                "depends_on": ["missing"],
                "rationale": "Synthetic test resource.",
            }
        ],
        "requirements": {"region": "us-east-1"},
    }
    with pytest.raises(ValidationError) as error:
        GeneratedDeploymentProposal.model_validate(invalid)

    assert _sanitize_pydantic_feedback(error.value) == [
        {
            "code": "value_error",
            "field": "proposal",
            "issue": "unknown_dependency",
            "guidance": _GRAPH_VALIDATION_FEEDBACK[
                "dependencies must reference other declared resources"
            ][1],
        }
    ]


@pytest.mark.parametrize(
    ("cause", "issue"),
    [
        ("dependencies must reference other declared resources", "unknown_dependency"),
        ("resource dependency graph must be acyclic", "dependency_cycle"),
        ("resource IDs must be unique", "duplicate_resource_id"),
        ("Terraform resource addresses must be unique", "duplicate_terraform_address"),
        ("references must target a declared resource", "unknown_resource_reference"),
        ("reference must match a declared output type", "reference_type_mismatch"),
        ("health assertions must target declared resources", "unknown_health_target"),
        ("proposal assumptions and limitations must be bounded text", "invalid_assumption_text"),
        (
            "secret_reference values may only populate a Lambda secret ARN environment variable",
            "invalid_secret_reference_location",
        ),
        ("health assertion target resource type is incompatible", "incompatible_health_target"),
        ("event probes must reference a declared source queue", "unknown_event_source"),
        ("event probe source must be an SQS queue", "unsupported_event_source"),
        ("event probes require a declared SQS-to-Lambda event binding", "missing_event_binding"),
        ("cost assumptions must target declared resources", "unknown_cost_resource"),
    ],
)
def test_known_graph_validator_causes_map_to_distinct_fixed_feedback(cause, issue):
    error = ValueError(cause)

    assert _validation_issue("value_error", "proposal", error) == issue
    guidance = _validation_guidance("value_error", "proposal", error)
    assert guidance == _GRAPH_VALIDATION_FEEDBACK[cause][1]
    assert cause not in guidance
    failure = NovaTerraformGenerationFailed(
        "safe failure",
        attempt_count=1,
        usage=ModelUsage(),
        evidence=(),
        validation_feedback=(
            {"code": "value_error", "field": "proposal", "issue": issue, "guidance": guidance},
        ),
    )
    assert failure.validation_feedback == (
        {"code": "value_error", "field": "proposal", "issue": issue, "guidance": guidance},
    )


@pytest.mark.parametrize(
    ("target_type", "target_arguments", "location"),
    [
        (
            "aws_ecs_task_definition",
            {"container_definitions": [{"secrets": [{"valueFrom": "placeholder"}]}]},
            "non_lambda_resource",
        ),
        (
            "aws_lambda_function",
            {"environment": [{"variables": {"DATABASE_PASSWORD": "placeholder"}}]},
            "lambda_environment_variable_name",
        ),
        (
            "aws_lambda_function",
            {"kms_key_arn": "placeholder"},
            "lambda_other_argument",
        ),
    ],
)
def test_secret_reference_location_feedback_is_safe_and_persisted(
    target_type, target_arguments, location
):
    reference = {
        "kind": "resource_reference",
        "resource_id": "database-secret",
        "output_name": "master_user_secret[0].secret_arn",
        "value_type": "secret_reference",
    }
    if target_type == "aws_ecs_task_definition":
        target_arguments["container_definitions"][0]["secrets"][0]["valueFrom"] = reference
    else:
        if "environment" in target_arguments:
            target_arguments["environment"][0]["variables"]["DATABASE_PASSWORD"] = reference
        else:
            target_arguments["kms_key_arn"] = reference
    raw = {
        "contract_version": "1.1",
        "source_revision": "revision-123",
        "context_digest": "a" * 64,
        "resources": [
            {
                "resource_id": "database-secret",
                "resource_type": "aws_rds_cluster",
                "name": "database",
                "arguments": {"manage_master_user_password": True},
                "outputs": [
                    {
                        "name": "master_user_secret[0].secret_arn",
                        "value_type": "secret_reference",
                    }
                ],
                "rationale": "Uses the provider-managed database credential.",
            },
            {
                "resource_id": "worker-secret-target",
                "resource_type": target_type,
                "name": "application",
                "arguments": target_arguments,
                "rationale": "Receives the database credential.",
            },
        ],
        "requirements": {"region": "us-east-1"},
    }
    with pytest.raises(ValidationError) as error:
        GeneratedDeploymentProposal.model_validate(raw)

    feedback = _sanitize_pydantic_feedback(error.value)
    assert feedback == [
        {
            "code": "value_error",
            "field": "resources[*].arguments",
            "issue": "invalid_secret_reference_location",
            "guidance": _SECRET_REFERENCE_LOCATION_GUIDANCE[location],
            "observed_resource_type": target_type,
            "secret_reference_location": location,
        }
    ]
    assert "database-secret" not in str(feedback)
    assert "worker-secret-target" not in str(feedback)
    assert "DATABASE_PASSWORD" not in str(feedback)
    assert "kms_key_arn" not in str(feedback)

    failure = NovaTerraformGenerationFailed(
        "safe failure",
        attempt_count=2,
        usage=ModelUsage(),
        evidence=(),
        validation_feedback=tuple(feedback),
    )
    assert failure.validation_feedback == tuple(feedback)
    hostile = NovaTerraformGenerationFailed(
        "safe failure",
        attempt_count=2,
        usage=ModelUsage(),
        evidence=(),
        validation_feedback=(
            {
                **feedback[0],
                "observed_resource_type": "untrusted-resource-id",
                "secret_reference_location": "untrusted-location",
                "resource_id": "must-not-escape",
            },
        ),
    )
    assert hostile.validation_feedback == (
        {key: feedback[0][key] for key in ("code", "field", "issue", "guidance")},
    )
    assert "must-not-escape" not in str(hostile.validation_feedback)


def test_nova_repairs_lambda_secret_variable_name_with_bounded_feedback():
    gateway = RecordingGateway(None)

    def output(request, document):
        variable_name = "DATABASE_PASSWORD" if len(gateway.calls) == 1 else "DATABASE_SECRET_ARN"
        return {
            "contract_version": "1.1",
            "source_revision": "revision-123",
            "context_digest": document["trusted_generation_context"]["context_digest"],
            "resources": [
                {
                    "resource_id": "database",
                    "resource_type": "aws_rds_cluster",
                    "name": "database",
                    "arguments": {"manage_master_user_password": True},
                    "outputs": [
                        {
                            "name": "master_user_secret[0].secret_arn",
                            "value_type": "secret_reference",
                        }
                    ],
                    "rationale": "Uses a managed database credential.",
                },
                {
                    "resource_id": "api",
                    "resource_type": "aws_lambda_function",
                    "name": "api",
                    "arguments": {
                        "environment": [
                            {
                                "variables": {
                                    variable_name: {
                                        "kind": "resource_reference",
                                        "resource_id": "database",
                                        "output_name": "master_user_secret[0].secret_arn",
                                        "value_type": "secret_reference",
                                    }
                                }
                            }
                        ]
                    },
                    "rationale": "Connects the API to its database.",
                },
            ],
            "requirements": {
                "region": document["trusted_generation_context"]["region"]
            },
        }

    gateway.output = output
    instance = NovaTerraformGenerator(
        gateway=gateway, max_output_tokens=800, timeout_seconds=30
    )
    result = instance.generate(
        approved_plan={"summary": {}, "target": {"region": "us-east-1"}},
        tenant=scope(),
        source_revision="revision-123",
    )

    assert len(gateway.calls) == 2
    feedback = gateway.calls[1][1]["validation_feedback"]
    assert feedback[0]["issue"] == "invalid_secret_reference_location"
    assert feedback[0]["observed_resource_type"] == "aws_lambda_function"
    assert feedback[0]["secret_reference_location"] == "lambda_environment_variable_name"
    assert "DATABASE_PASSWORD" not in str(feedback)
    assert "database" not in str(feedback)
    assert result.proposal.resources[1].arguments["environment"][0]["variables"].keys() == {
        "DATABASE_SECRET_ARN"
    }


def test_unrecognized_proposal_validator_message_is_never_returned():
    private_cause = ValueError("untrusted secret-like value must-not-escape")

    assert _validation_issue("value_error", "proposal", private_cause) is None
    guidance = _validation_guidance("value_error", "proposal", private_cause)
    assert guidance == _RESOURCE_GRAPH_GUIDANCE
    assert "must-not-escape" not in guidance
    assert "untrusted secret-like value" not in guidance


@pytest.mark.parametrize(
    ("resource_update", "issue", "guidance"),
    [
        (
            {"arguments": {"provider": "aws"}},
            "forbidden_argument_key",
            (
                "Use only literal JSON values for AWS resource attributes. Remove provider, "
                "provisioner, connection, backend, required_providers, access_key, secret_key, "
                "session_token, private_key, password, and user_data fields."
            ),
        ),
        (
            {"arguments": {"bucket": "${var.bucket_name}"}},
            "terraform_expression",
            (
                "Use literal JSON values only; remove Terraform interpolation, directives, file reads, "
                "template functions, and other expressions. Use typed resource_reference objects for links."
            ),
        ),
        (
            {"arguments": {"db_secret": "private-value"}},
            "credential_value",
            _RESOURCE_CREDENTIAL_GUIDANCE,
        ),
        (
            {"arguments": {"tags": {"DavDeployOwner": "model-value"}}},
            "reserved_ownership_tag",
            (
                "Remove every tag whose key starts with DavDeploy. Trusted execution code adds the "
                "required ownership tags."
            ),
        ),
        (
            {
                "outputs": [
                    {"name": "endpoint", "value_type": "url"},
                    {"name": "endpoint", "value_type": "url"},
                ]
            },
            "duplicate_output_name",
            (
                "Give every output a unique name. Use secret_reference outputs only on "
                "aws_db_instance or aws_rds_cluster with "
                "manage_master_user_password=true, and use the exact output name "
                "master_user_secret[0].secret_arn. Remove every other secret_reference output. "
                "A Lambda secret ARN environment reference must point to that declared output. "
                "Do not add resources or change the selected architecture to repair this output."
            ),
        ),
        (
            {"outputs": [{"name": "secret", "value_type": "secret_reference"}]},
            "unsupported_secret_output",
            (
                "Give every output a unique name. Use secret_reference outputs only on "
                "aws_db_instance or aws_rds_cluster with "
                "manage_master_user_password=true, and use the exact output name "
                "master_user_secret[0].secret_arn. Remove every other secret_reference output. "
                "A Lambda secret ARN environment reference must point to that declared output. "
                "Do not add resources or change the selected architecture to repair this output."
            ),
        ),
    ],
)
def test_resource_level_value_errors_receive_fixed_safe_guidance(resource_update, issue, guidance):
    resource = {
        "resource_id": "api",
        "resource_type": "aws_s3_bucket",
        "name": "files",
        "arguments": {},
        "rationale": "Synthetic test resource.",
    }
    resource.update(resource_update)
    invalid = {
        "contract_version": "1.1",
        "source_revision": "revision-123",
        "context_digest": "0" * 64,
        "resources": [resource],
        "requirements": {"region": "us-east-1"},
    }
    with pytest.raises(ValidationError) as error:
        GeneratedDeploymentProposal.model_validate(invalid)

    feedback = _sanitize_pydantic_feedback(error.value)
    assert feedback[0] == {
        "code": "value_error",
        "field": "resources[*]",
        "issue": issue,
        "guidance": guidance,
    }


@pytest.mark.parametrize(
    ("code", "location", "guidance"),
    [
        ("missing", ("resources", 0), _RESOURCE_OBJECT_SHAPE_GUIDANCE["missing"]),
        (
            "extra_forbidden",
            ("resources", 0, "private_input_marker"),
            _RESOURCE_OBJECT_SHAPE_GUIDANCE["extra_forbidden"],
        ),
    ],
)
def test_root_resource_shape_feedback_is_fixed_and_redacts_untrusted_keys(
    code, location, guidance
):
    error = ValidationError.from_exception_data(
        "GeneratedDeploymentProposal",
        [
            {
                "type": code,
                "loc": location,
                "input": {"private_input_marker": "do-not-echo-this-value"},
            }
        ],
    )

    feedback = _sanitize_pydantic_feedback(error)

    assert feedback == [
        {"code": code, "field": "resources[*]", "guidance": guidance}
    ]
    assert "private_input_marker" not in repr(feedback)
    assert "do-not-echo-this-value" not in repr(feedback)


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

    with pytest.raises(ModelGatewayUnavailable, match="bounded 2-attempt"):
        generator(invalid).generate(
            approved_plan={"target": {"region": "us-east-1"}}, tenant=scope()
        )


def test_nova_generation_rejects_untrusted_revision_or_region():
    def invalid_revision(request, document):
        return proposal(request, document, source_revision="different-revision")

    with pytest.raises(ModelGatewayUnavailable, match="bounded 2-attempt"):
        generator(invalid_revision).generate(
            approved_plan={"target": {"region": "us-east-1"}},
            tenant=scope(),
            source_revision="trusted-revision",
        )

    with pytest.raises(ModelGatewayUnavailable, match="trusted AWS region"):
        generator(proposal).generate(approved_plan={}, tenant=scope())


class SequenceGateway(RecordingGateway):
    def __init__(self, outputs, usage=None):
        self.outputs = list(outputs)
        self.calls = []
        self.usages = list(usage or [])

    def generate_structured(self, request, document, output_schema=None):
        self.calls.append((request, document, output_schema))
        output = self.outputs.pop(0)
        if callable(output):
            output = output(request, document)
        usage = self.usages.pop(0) if self.usages else ModelUsage(
            input_tokens=100, output_tokens=60, latency_ms=10
        )
        return ModelResponse(
            request=request,
            output=output,
            usage=usage,
            evidence=(
                EvidenceRef(
                    tenant=request.tenant,
                    kind=EvidenceKind.MODEL_INFERENCE,
                    source=f"fixture-call-{len(self.calls)}",
                    content_digest=f"{len(self.calls):064x}",
                ),
            ),
        )


def _valid_proposal(request, document):
    trusted = document["trusted_generation_context"]
    return proposal(
        request,
        document,
        source_revision=trusted["source_revision"],
    )


def _invalid_with_untrusted_extra(request, document):
    result = _valid_proposal(request, document)
    result["private_api_key_leak_me"] = "do-not-echo-this-value"
    return result


def _invalid_with_resource_wrapper(request, document):
    result = _valid_proposal(request, document)
    result["resources"][0]["private_resource_wrapper"] = {
        "value": "do-not-echo-resource-wrapper"
    }
    return result


def _typed_reference_proposal(request, document, value_type):
    result = _valid_proposal(request, document)
    result["resources"] = [
        {
            "resource_id": "jobs-queue",
            "resource_type": "aws_sqs_queue",
            "name": "jobs_queue",
            "arguments": {},
            "outputs": [{"name": "queue_url", "value_type": "aws_queue_url", "sensitive": False}],
            "rationale": "Provides asynchronous work.",
        },
        {
            "resource_id": "jobs-worker",
            "resource_type": "aws_lambda_function",
            "name": "jobs_worker",
            "arguments": {
                "environment": [
                    {
                        "variables": {
                            "QUEUE_URL": {
                                "kind": "resource_reference",
                                "resource_id": "jobs-queue",
                                "output_name": "queue_url",
                                "value_type": value_type,
                            }
                        }
                    }
                ]
            },
            "rationale": "Processes queued work.",
        },
    ]
    return result


def test_reference_type_mismatch_stays_strict_and_gets_actionable_bounded_repair():
    invalid = lambda request, document: _typed_reference_proposal(
        request, document, "resource_name"
    )
    repaired = lambda request, document: _typed_reference_proposal(
        request, document, "aws_queue_url"
    )
    gateway = SequenceGateway([invalid, repaired])

    result = NovaTerraformGenerator(
        gateway=gateway,
        max_output_tokens=800,
        timeout_seconds=30,
        total_timeout_seconds=60,
    ).generate(
        approved_plan={"target": {"region": "us-east-1"}},
        tenant=scope(),
        source_revision="trusted-reference-type-1",
    )

    assert result.proposal.resources[1].arguments["environment"][0]["variables"]["QUEUE_URL"][
        "value_type"
    ] == "aws_queue_url"
    repair_document = gateway.calls[1][1]
    feedback = repair_document["validation_feedback"]
    assert feedback == [
        {
            "code": "value_error",
            "field": "proposal",
            "issue": "reference_type_mismatch",
            "guidance": _GRAPH_VALIDATION_FEEDBACK[
                "reference must match a declared output type"
            ][1],
        }
    ]
    assert "jobs-queue" not in str(feedback)
    assert "resource_name" not in str(feedback)
    task = repair_document["task"]
    assert "value_type must exactly equal that output's value_type" in task
    assert "outputs=[{name: queue_url, value_type: aws_queue_url}]" in task
    assert NOVA_TERRAFORM_PROMPT_VERSION == "terraform-nova2-contract-v29"


def test_semantic_repair_uses_only_sanitized_feedback_and_preserves_trusted_inputs():
    gateway = SequenceGateway(
        [_invalid_with_untrusted_extra, _valid_proposal],
        usage=[
            ModelUsage(
                input_tokens=11,
                output_tokens=4,
                estimated_cost_usd=0.001,
                latency_ms=7,
                retry_count=2,
            ),
            ModelUsage(
                input_tokens=13,
                output_tokens=5,
                estimated_cost_usd=0.002,
                latency_ms=9,
                retry_count=1,
            ),
        ],
    )
    approved_plan = {"target": {"region": "eu-west-1"}, "note": "synthetic fixture"}
    result = NovaTerraformGenerator(
        gateway=gateway,
        max_output_tokens=800,
        timeout_seconds=30,
        total_timeout_seconds=60,
    ).generate(
        approved_plan=approved_plan,
        tenant=scope(),
        source_revision="trusted-revision-44",
    )

    first_request, first_document, _ = gateway.calls[0]
    second_request, second_document, _ = gateway.calls[1]
    assert first_request.input_digest == model_input_digest(first_document)
    assert second_request.input_digest == model_input_digest(second_document)
    assert first_document["approved_plan"] == second_document["approved_plan"] == approved_plan
    assert (
        first_document["trusted_generation_context"]
        == second_document["trusted_generation_context"]
    )
    assert result.proposal.source_revision == "trusted-revision-44"
    assert result.proposal.context_digest == generation_context_digest(
        approved_plan, "trusted-revision-44"
    )
    feedback = second_document["validation_feedback"]
    assert feedback == [{"code": "extra_forbidden", "field": "proposal"}]
    assert "do-not-echo-this-value" not in repr(second_document)
    assert "private_api_key_leak_me" not in repr(second_document)
    assert set(feedback[0]) == {"code", "field"}
    assert result.response.usage.input_tokens == 24
    assert result.response.usage.output_tokens == 9
    assert result.response.usage.estimated_cost_usd == 0.003
    assert result.response.usage.latency_ms == 16
    # One semantic correction plus both calls' provider-level JSON repairs.
    assert result.response.usage.retry_count == 4
    assert first_request.request_id != second_request.request_id
    assert [item.source for item in result.response.evidence] == [
        "fixture-call-1",
        "fixture-call-2",
    ]


def test_fixed_plan_access_profile_feedback_repairs_without_changing_trusted_inputs():
    gateway = SequenceGateway([_valid_proposal, _valid_proposal])
    approved_plan = {
        "target": {"account_id": "123456789012", "region": "us-east-1"},
        "required_behavior": "write records and process queued work",
    }
    validations = iter(["unsafe_resource_scope", None])

    result = NovaTerraformGenerator(
        gateway=gateway,
        max_output_tokens=800,
        timeout_seconds=30,
        total_timeout_seconds=60,
    ).generate(
        approved_plan=approved_plan,
        tenant=scope(),
        source_revision="trusted-access-profile-revision",
        proposal_validator=lambda _proposal: next(validations),
    )

    first_request, first_document, _ = gateway.calls[0]
    second_request, second_document, _ = gateway.calls[1]
    assert first_request.input_digest == model_input_digest(first_document)
    assert second_request.input_digest == model_input_digest(second_document)
    assert first_document["approved_plan"] == second_document["approved_plan"] == approved_plan
    assert (
        first_document["trusted_generation_context"]
        == second_document["trusted_generation_context"]
    )
    assert second_document["validation_feedback"] == [
        {
            "code": "invalid",
            "field": "resources",
            "issue": "plan_access_profile_mismatch",
            "guidance": _PLAN_ACCESS_GUIDANCE["unsafe_resource_scope"],
        }
    ]
    assert "Runs the proposed application workload" not in str(second_document["validation_feedback"])
    assert result.proposal.source_revision == "trusted-access-profile-revision"


def test_plan_access_profile_repair_exhaustion_returns_only_fixed_feedback():
    gateway = SequenceGateway([_valid_proposal, _valid_proposal])

    with pytest.raises(NovaTerraformGenerationFailed) as failure:
        NovaTerraformGenerator(
            gateway=gateway,
            max_output_tokens=800,
            timeout_seconds=30,
            max_semantic_attempts=2,
            total_timeout_seconds=60,
        ).generate(
            approved_plan={"target": {"account_id": "123456789012", "region": "us-east-1"}},
            tenant=scope(),
            source_revision="trusted-access-profile-exhausted",
            proposal_validator=lambda _proposal: "unsupported_resource_type",
        )

    assert failure.value.failure_code == "plan_access_profile_mismatch"
    assert failure.value.attempt_count == 2
    assert len(gateway.calls) == 2
    assert failure.value.validation_feedback == (
        {
            "code": "invalid",
            "field": "resources",
            "issue": "plan_access_profile_mismatch",
            "guidance": _PLAN_ACCESS_GUIDANCE["unsupported_resource_type"],
        },
    )
    assert "customer-application" not in str(failure.value.validation_feedback)
    assert "trusted-access-profile-exhausted" not in str(failure.value.validation_feedback)
    assert all(
        resource_type in _PLAN_ACCESS_GUIDANCE["unsupported_resource_type"]
        for resource_type in SUPPORTED_PLAN_RESOURCE_TYPES
    )


def test_semantic_repair_gets_fixed_guidance_for_root_resource_wrapper():
    gateway = SequenceGateway([_invalid_with_resource_wrapper, _valid_proposal])
    approved_plan = {"target": {"region": "us-east-1"}, "note": "synthetic fixture"}

    result = NovaTerraformGenerator(
        gateway=gateway,
        max_output_tokens=800,
        timeout_seconds=30,
        total_timeout_seconds=60,
    ).generate(
        approved_plan=approved_plan,
        tenant=scope(),
        source_revision="trusted-revision-shape-1",
    )

    feedback = gateway.calls[1][1]["validation_feedback"]
    assert feedback[0] == {
        "code": "extra_forbidden",
        "field": "resources[*]",
        "guidance": _RESOURCE_OBJECT_SHAPE_GUIDANCE["extra_forbidden"],
    }
    assert all(set(item) <= {"code", "field", "guidance", "issue"} for item in feedback)
    assert "private_resource_wrapper" not in repr(gateway.calls[1][1])
    assert "do-not-echo-resource-wrapper" not in repr(gateway.calls[1][1])
    assert result.proposal.source_revision == "trusted-revision-shape-1"


def test_unknown_cost_stays_unknown_after_a_semantic_repair():
    gateway = SequenceGateway(
        [_invalid_with_untrusted_extra, _valid_proposal],
        usage=[
            ModelUsage(input_tokens=5, output_tokens=2, estimated_cost_usd=0.01),
            ModelUsage(input_tokens=7, output_tokens=3, estimated_cost_usd=None),
        ],
    )
    result = NovaTerraformGenerator(gateway=gateway).generate(
        approved_plan={"target": {"region": "us-east-1"}},
        tenant=scope(),
        source_revision="trusted-revision",
    )
    assert result.response.usage.input_tokens == 12
    assert result.response.usage.output_tokens == 5
    assert result.response.usage.estimated_cost_usd is None


def test_semantic_repair_stops_after_attempt_cap_with_safe_error():
    gateway = SequenceGateway(
        [_invalid_with_untrusted_extra, _invalid_with_untrusted_extra, _valid_proposal]
    )
    instance = NovaTerraformGenerator(
        gateway=gateway,
        max_semantic_attempts=2,
        total_timeout_seconds=60,
    )

    with pytest.raises(
        ModelGatewayUnavailable,
        match="bounded 2-attempt, 60-second limit",
    ) as error:
        instance.generate(
            approved_plan={"target": {"region": "us-east-1"}},
            tenant=scope(),
            source_revision="trusted-revision",
        )
    assert len(gateway.calls) == 2
    assert "do-not-echo-this-value" not in str(error.value)
    assert "private_api_key_leak_me" not in str(error.value)
    assert "ValidationError" not in str(error.value)
    assert error.value.usage.input_tokens == 200
    assert error.value.usage.output_tokens == 120
    assert error.value.usage.retry_count == 1
    assert error.value.attempt_count == 2
    assert error.value.failure_code == "proposal_invalid"
    assert error.value.validation_feedback == (
        {"code": "extra_forbidden", "field": "proposal"},
    )


def test_gateway_failure_preserves_known_usage_without_exposing_provider_error():
    class PartialGatewayFailure(SequenceGateway):
        def generate_structured(self, request, document, output_schema=None):
            if self.calls:
                raise ModelGatewayUnavailable(
                    "provider error included sensitive details",
                    usage=ModelUsage(
                        input_tokens=7,
                        output_tokens=3,
                        estimated_cost_usd=None,
                        latency_ms=4,
                    ),
                    evidence=(
                        EvidenceRef(
                            tenant=request.tenant,
                            kind=EvidenceKind.MODEL_INFERENCE,
                            source="amazon-bedrock:test-model",
                            content_digest="f" * 64,
                            location="bedrock-request:partial-failure",
                        ),
                    ),
                    attempt_count=1,
                )
            return super().generate_structured(request, document, output_schema)

    gateway = PartialGatewayFailure(
        [_invalid_with_untrusted_extra],
        usage=[
            ModelUsage(
                input_tokens=5,
                output_tokens=2,
                estimated_cost_usd=0.01,
                latency_ms=3,
                retry_count=1,
            )
        ],
    )
    with pytest.raises(NovaTerraformGenerationFailed) as error:
        NovaTerraformGenerator(gateway=gateway).generate(
            approved_plan={"target": {"region": "us-east-1"}},
            tenant=scope(),
            source_revision="trusted-revision",
        )
    assert error.value.attempt_count == 2
    assert error.value.usage.input_tokens == 12
    assert error.value.usage.output_tokens == 5
    assert error.value.usage.estimated_cost_usd is None
    assert error.value.usage.retry_count == 2
    assert len(error.value.evidence) == 2
    assert error.value.failure_code == "provider_unavailable"
    assert error.value.validation_feedback == (
        {"code": "extra_forbidden", "field": "proposal"},
    )
    assert "sensitive details" not in str(error.value)


def test_semantic_repair_can_correct_context_mismatch_without_changing_context():
    def wrong_context(request, document):
        return proposal(
            request,
            document,
            source_revision="attacker-selected-revision",
        )

    gateway = SequenceGateway([wrong_context, _valid_proposal])
    plan = {"target": {"region": "us-east-1"}}
    result = NovaTerraformGenerator(gateway=gateway).generate(
        approved_plan=plan,
        tenant=scope(),
        source_revision="trusted-revision",
    )

    assert gateway.calls[1][1]["trusted_generation_context"] == gateway.calls[0][1][
        "trusted_generation_context"
    ]
    assert gateway.calls[1][1]["validation_feedback"] == [
        {"code": "trusted_context_mismatch", "field": "source_revision"}
    ]
    assert result.proposal.source_revision == "trusted-revision"
    assert result.proposal.context_digest == generation_context_digest(
        plan, "trusted-revision"
    )


def test_fixture_fallback_is_rejected_without_semantic_retry():
    class FixtureFallbackGateway(SequenceGateway):
        def generate_structured(self, request, document, output_schema=None):
            response = super().generate_structured(request, document, output_schema)
            return response.model_copy(
                update={
                    "request": request.model_copy(
                        update={"provider": "fixture", "model": "deterministic-fixture"}
                    )
                }
            )

    gateway = FixtureFallbackGateway([_valid_proposal, _valid_proposal])
    with pytest.raises(ModelGatewayUnavailable, match="requires enabled Nova 2 Lite"):
        NovaTerraformGenerator(gateway=gateway).generate(
            approved_plan={"target": {"region": "us-east-1"}}, tenant=scope()
        )
    assert len(gateway.calls) == 1


def test_configured_fixture_fallback_is_not_invoked_for_terraform_generation():
    class FailingPrimary:
        provider = "bedrock"

        def __init__(self):
            self.calls = 0

        def complete(self, request, document):
            raise AssertionError("complete must not be used")

        def generate_structured(self, request, document, output_schema=None):
            self.calls += 1
            raise ModelGatewayUnavailable("primary response was lost", outcome_uncertain=True)

        def estimate_cost(self, request):
            return 0.0

        def validate_output(self, output):
            return False

    primary = FailingPrimary()
    fallback = RecordingGateway(lambda request, document: _valid_proposal(request, document))
    gateway = FallbackModelGateway(primary, fallback)
    with pytest.raises(ModelGatewayUnavailable, match="stopped before a valid response") as error:
        NovaTerraformGenerator(gateway=gateway).generate(
            approved_plan={"target": {"region": "us-east-1"}}, tenant=scope()
        )
    assert primary.calls == 1
    assert fallback.calls == []
    assert error.value.outcome_uncertain


def test_semantic_repair_stops_when_time_budget_expires(monkeypatch):
    gateway = SequenceGateway([_invalid_with_untrusted_extra, _valid_proposal])
    clock = {"now": 10.0}

    def fake_monotonic():
        return clock["now"]

    def expire_after_first_call(request, document):
        clock["now"] = 12.0
        return _invalid_with_untrusted_extra(request, document)

    gateway.outputs[0] = expire_after_first_call
    monkeypatch.setattr("davdeploy.terraform_generation.time.monotonic", fake_monotonic)
    with pytest.raises(ModelGatewayUnavailable, match="bounded 2-attempt, 1-second limit"):
        NovaTerraformGenerator(
            gateway=gateway,
            max_semantic_attempts=2,
            timeout_seconds=30,
            total_timeout_seconds=1,
        ).generate(
            approved_plan={"target": {"region": "us-east-1"}}, tenant=scope()
        )
    assert len(gateway.calls) == 1
    assert gateway.calls[0][0].timeout_seconds == 1


class FakeBedrockClient:
    def __init__(self, response_texts):
        self.response_texts = list(response_texts)
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        response_text = self.response_texts.pop(0)
        return {
            "stopReason": "end_turn",
            "output": {"message": {"content": [{"text": response_text}]}},
            "usage": {"inputTokens": 10 + len(self.calls), "outputTokens": 5},
            "metrics": {"latencyMs": 8},
            "ResponseMetadata": {"RequestId": f"request-{len(self.calls)}"},
        }


def test_bedrock_gateway_accepts_generator_full_document_digest_and_rejects_tampering():
    approved_plan = {"target": {"region": "us-east-1"}}
    trusted_digest = generation_context_digest(approved_plan, "revision-123")
    valid_output = {
        "contract_version": "1.1",
        "source_revision": "revision-123",
        "context_digest": trusted_digest,
        "resources": [
            {
                "resource_id": "application",
                "resource_type": "aws_ecs_cluster",
                "name": "application",
                "arguments": {"name": "customer-application"},
                "rationale": "Runs the proposed workload.",
            }
        ],
        "requirements": {"region": "us-east-1"},
        "assumptions": [],
        "limitations": [],
    }
    fake_client = FakeBedrockClient(["not-json", json.dumps(valid_output)])

    class CapturingGateway(BedrockNovaGateway):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.inputs = []

        def generate_structured(self, request, document, output_schema=None):
            self.inputs.append((request, document, output_schema))
            return super().generate_structured(request, document, output_schema)

    gateway = CapturingGateway(
        config=NovaGatewayConfig(
            input_price_per_million_usd=1.0,
            output_price_per_million_usd=2.0,
            pricing_catalog_version="test-catalog-1",
        ),
        client=fake_client,
    )
    result = NovaTerraformGenerator(gateway=gateway).generate(
        approved_plan=approved_plan,
        tenant=scope(),
        source_revision="revision-123",
    )
    request, document, schema = gateway.inputs[0]
    assert request.input_digest == model_input_digest(document)
    assert result.proposal.context_digest == trusted_digest
    assert result.response.usage.input_tokens == 23
    assert result.response.usage.output_tokens == 10
    assert result.response.usage.retry_count == 1
    assert result.response.usage.estimated_cost_usd == pytest.approx(0.000043)
    assert len(fake_client.calls) == 2
    assert [item.location for item in result.response.evidence] == [
        "bedrock-request:request-1",
        "bedrock-request:request-2",
    ]

    tampered = {**document, "approved_plan": {"target": {"region": "eu-west-1"}}}
    with pytest.raises(ModelGatewayUnavailable, match="input digest does not match"):
        gateway.generate_structured(request, tampered, schema)
    assert len(fake_client.calls) == 2
