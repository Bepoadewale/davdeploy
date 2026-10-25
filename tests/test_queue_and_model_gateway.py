import json
from datetime import UTC, datetime, timedelta

import pytest
from davdeploy.contracts import JobEnvelope, JobKind, ModelPurpose, ModelRequest, TenantScope
from davdeploy.db import run_migrations
from davdeploy.model_gateway import (
    NOVA_2_LITE_MODEL_ID,
    BedrockNovaGateway,
    DeterministicModelGateway,
    DisabledModelGateway,
    FallbackModelGateway,
    ModelCallPolicy,
    ModelGatewayUnavailable,
    NovaGatewayConfig,
    decode_structured_json,
    guarded_complete,
    configured_model_gateway,
    guarded_generate_structured,
    model_input_digest,
)
from davdeploy.models import Base
from davdeploy.queue import InMemoryJobQueue, PostgresJobQueue
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def tenant(org="org-demo"):
    return TenantScope(
        organization_id=org,
        workspace_id="workspace-demo",
        project_id="project-demo",
        actor_id="user-demo",
    )


def job(key="planning-123", org="org-demo"):
    return JobEnvelope(tenant=tenant(org), kind=JobKind.PLANNING, idempotency_key=key)


def test_in_memory_queue_is_idempotent_and_retries_then_dead_letters():
    queue = InMemoryJobQueue()
    first = queue.enqueue(job())
    duplicate = queue.enqueue(job())
    assert duplicate.job_id == first.job_id
    claimed = queue.claim("org-demo")
    assert claimed is not None and claimed.attempt == 1
    queue.claimed_at[claimed.job_id] = datetime.now(UTC) - timedelta(hours=1)
    assert queue.requeue_stale(60) == 1
    claimed = queue.claim("org-demo")
    assert claimed is not None
    assert queue.fail(claimed.job_id, "temporary") == "QUEUED"
    claimed_again = queue.claim("org-demo")
    assert claimed_again is not None and claimed_again.attempt == 3
    queue.heartbeat(claimed_again.job_id)
    queue.cancel(claimed_again.job_id, "operator requested cancellation")
    assert queue.fail(claimed_again.job_id, "permanent", retry=False) == "DEAD_LETTER"


def test_in_memory_queue_does_not_cross_tenants():
    queue = InMemoryJobQueue()
    queue.enqueue(job(org="org-a"))
    assert queue.claim("org-b") is None


def test_postgres_queue_persists_and_deduplicates_jobs():
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    run_migrations(engine)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as db:
        queue = PostgresJobQueue(db)
        first = queue.enqueue(job())
        duplicate = queue.enqueue(job())
        assert duplicate.job_id == first.job_id
        claimed = queue.claim("org-demo", [JobKind.PLANNING])
        assert claimed is not None and claimed.attempt == 1
        assert queue.fail(claimed.job_id, "retryable") == "QUEUED"
        assert queue.claim("org-demo") is not None
        queue.heartbeat(claimed.job_id)
        queue.acknowledge(claimed.job_id)


def test_fixture_model_gateway_returns_typed_non_authoritative_response():
    request = ModelRequest(
        tenant=tenant(),
        purpose=ModelPurpose.INTENT_EXTRACTION,
        provider="fixture",
        model="deterministic-fixture",
        prompt_version="intent-v1",
        input_digest="a" * 64,
    )
    response = DeterministicModelGateway().complete(request, {"prompt": "deploy api"})
    assert response.output["mode"] == "SIMULATED"
    assert response.evidence[0].kind.value == "fixture"
    assert response.usage is not None


def test_disabled_model_gateway_fails_closed():
    try:
        DisabledModelGateway().complete(None, {})  # type: ignore[arg-type]
    except ModelGatewayUnavailable as error:
        assert "configured" in str(error)
    else:
        raise AssertionError("disabled model gateway returned a response")


def test_model_call_policy_enforces_provider_and_budget():
    request = ModelRequest(
        tenant=tenant(),
        purpose=ModelPurpose.INTENT_EXTRACTION,
        provider="fixture",
        model="deterministic-fixture",
        prompt_version="intent-v1",
        input_digest="a" * 64,
        max_output_tokens=100,
    )
    response = guarded_complete(
        DeterministicModelGateway(),
        request,
        {"prompt": "ok"},
        ModelCallPolicy(max_output_tokens=100),
    )
    assert response.request.request_id == request.request_id
    assert DeterministicModelGateway().validate_output(response.output) is True
    assert DeterministicModelGateway().estimate_cost(request) > 0
    with pytest.raises(ModelGatewayUnavailable):
        guarded_complete(
            DeterministicModelGateway(),
            request.model_copy(update={"provider": "unknown"}),
            {"prompt": "no"},
        )


class FakeBedrockRuntime:
    def __init__(self, output=None, stop_reason="end_turn"):
        self.output = output or {"workload_type": "ai_api"}
        self.stop_reason = stop_reason
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "output": {
                "message": {"content": [{"text": json.dumps(self.output)}]},
            },
            "stopReason": self.stop_reason,
            "usage": {"inputTokens": 100, "outputTokens": 20},
            "metrics": {"latencyMs": 42},
            "ResponseMetadata": {"RequestId": "bedrock-request-1"},
        }


def nova_request(document, **updates):
    base = ModelRequest(
        tenant=tenant(),
        purpose=ModelPurpose.INTENT_EXTRACTION,
        provider="bedrock",
        model=NOVA_2_LITE_MODEL_ID,
        prompt_version="intent-nova2-v1",
        input_digest=model_input_digest(document),
        max_output_tokens=500,
        timeout_seconds=30,
        data_policy="bedrock-no-training",
    )
    return base.model_copy(update=updates)


def nova_config(**updates):
    base = NovaGatewayConfig(
        model_id=NOVA_2_LITE_MODEL_ID,
        input_price_per_million_usd=0.10,
        output_price_per_million_usd=0.40,
        pricing_catalog_version="test-2026-10-15",
    )
    return NovaGatewayConfig(**(base.__dict__ | updates))


def test_nova_gateway_requests_json_schema_and_records_safe_usage():
    document = {"customer_request": "deploy an api", "selected_repository": "org/repo"}
    client = FakeBedrockRuntime()
    gateway = BedrockNovaGateway(nova_config(), client)
    response = guarded_generate_structured(
        gateway,
        nova_request(document),
        document,
        {
            "type": "object",
            "properties": {
                "workload_type": {"type": "string", "minLength": 1},
            },
            "required": ["workload_type"],
        },
        ModelCallPolicy(
            max_output_tokens=500,
            max_timeout_seconds=30,
            allowed_providers=frozenset({"bedrock"}),
            allowed_data_policies=frozenset({"bedrock-no-training"}),
        ),
    )
    call = client.calls[0]
    prompt = json.loads(call["messages"][0]["content"][0]["text"])
    schema = prompt["required_output_schema"]
    assert call["modelId"] == NOVA_2_LITE_MODEL_ID
    assert call["inferenceConfig"]["temperature"] == 0.0
    assert schema["additionalProperties"] is False
    assert "minLength" not in schema["properties"]["workload_type"]
    assert "outputConfig" not in call
    assert call["requestMetadata"]["tenant_digest"] != "org-demo"
    assert response.output == {"workload_type": "ai_api"}
    assert response.usage is not None
    assert response.usage.estimated_cost_usd == 0.000018
    assert response.evidence[0].kind.value == "model_inference"
    assert response.safety_result == "bedrock-json-locally-schema-validated"


def test_nova_gateway_accepts_only_plain_or_exact_fenced_json_objects():
    assert decode_structured_json('{"ok":true}') == {"ok": True}
    assert decode_structured_json('```json\n{"ok":true}\n```') == {"ok": True}
    with pytest.raises(json.JSONDecodeError):
        decode_structured_json('Here is the result:\n```json\n{"ok":true}\n```')
    with pytest.raises(TypeError, match="JSON object"):
        decode_structured_json('["not-an-object"]')


def test_nova_gateway_rejects_digest_mismatch_and_incomplete_output():
    document = {"customer_request": "deploy"}
    gateway = BedrockNovaGateway(nova_config(), FakeBedrockRuntime(stop_reason="max_tokens"))
    with pytest.raises(ModelGatewayUnavailable, match="digest"):
        gateway.generate_structured(
            nova_request(document, input_digest="b" * 64),
            document,
            {"type": "object", "properties": {}, "additionalProperties": False},
        )
    with pytest.raises(ModelGatewayUnavailable, match="incomplete"):
        gateway.generate_structured(
            nova_request(document),
            document,
            {"type": "object", "properties": {}, "additionalProperties": False},
        )


def test_model_policy_rejects_unapproved_tenant_data_policy():
    document = {"customer_request": "deploy"}
    request = nova_request(document, data_policy="provider-training-allowed")
    with pytest.raises(ModelGatewayUnavailable, match="data policy"):
        ModelCallPolicy(
            allowed_providers=frozenset({"bedrock"}),
            allowed_data_policies=frozenset({"bedrock-no-training"}),
        ).validate(request)


def test_explicit_fallback_preserves_fixture_identity():
    document = {"customer_request": "deploy"}
    primary = BedrockNovaGateway(nova_config(), FakeBedrockRuntime(stop_reason="max_tokens"))
    gateway = FallbackModelGateway(primary, DeterministicModelGateway())
    response = gateway.generate_structured(
        nova_request(document),
        document,
        {"type": "object", "properties": {}, "additionalProperties": False},
    )
    assert response.request.provider == "fixture"
    assert response.request.model == "deterministic-fixture"
    assert response.evidence[0].kind.value == "fixture"


def test_configured_gateway_accepts_legacy_bedrock_nova_provider(monkeypatch):
    monkeypatch.setenv("DAVDEPLOY_MODEL_PROVIDER", "bedrock-nova")
    configured_model_gateway.cache_clear()
    try:
        assert isinstance(configured_model_gateway(), BedrockNovaGateway)
    finally:
        configured_model_gateway.cache_clear()
