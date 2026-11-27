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
from davdeploy.terraform_generation import (
    _GENERIC_VALIDATION_GUIDANCE,
    _GRAPH_VALIDATION_FEEDBACK,
    _RESOURCE_CREDENTIAL_GUIDANCE,
    _RESOURCE_NAME_GUIDANCE,
    NOVA_TERRAFORM_PROMPT_VERSION,
    NovaTerraformGenerationFailed,
    NovaTerraformGenerator,
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
    assert "no underscores or uppercase" in document["task"]
    assert "environment[0].variables.<NAME>_SECRET_ARN" in document["task"]
    assert "value_type=secret_reference" in document["task"]
    assert '"manage_master_user_password":true' in document["task"]
    assert '"output_name":"master_user_secret[0].secret_arn"' in document["task"]
    assert '"kind":"resource_reference"' in document["task"]
    assert NOVA_TERRAFORM_PROMPT_VERSION == "terraform-nova2-contract-v14"
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
            "guidance": (
                "Use a unique resource_id of 1-24 characters matching ^[a-z][a-z0-9-]{0,23}$: "
                "lowercase letters, digits, and hyphens only; no underscores or uppercase. Prefer short "
                "IDs such as api, db, files, queue, worker, db-primary, or db-replica; copy every "
                "reference exactly from its declared resource_id."
            ),
        }
    ]


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


def test_unknown_validator_error_becomes_generic_safe_repair_feedback():
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
            "field": "proposal",
            "guidance": _GENERIC_VALIDATION_GUIDANCE,
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
    ],
)
def test_known_graph_validator_causes_map_to_distinct_fixed_feedback(cause, issue):
    error = ValueError(cause)

    assert _validation_issue("value_error", "proposal", error) == issue
    guidance = _validation_guidance("value_error", "proposal", error)
    assert guidance == _GRAPH_VALIDATION_FEEDBACK[cause][1]
    assert cause not in guidance


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
                "Give each output a unique name and expose only supported values; a secret "
                "reference output is allowed only for an RDS-managed master secret ARN."
            ),
        ),
        (
            {"outputs": [{"name": "secret", "value_type": "secret_reference"}]},
            "unsupported_secret_output",
            (
                "Give each output a unique name and expose only supported values; a secret "
                "reference output is allowed only for an RDS-managed master secret ARN."
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
