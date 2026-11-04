from hashlib import sha256

import pytest
from davdeploy.domain import ArchitectureModule, ModuleInputBinding
from davdeploy.module_ports import (
    normalize_renderer_outputs,
    validate_module_inputs,
    validate_module_outputs,
)
from davdeploy.universal_execution import (
    compile_universal_execution_plan,
    resolve_lifecycle_work_inputs,
    resolve_module_inputs,
)


def module(identifier: str, *, instance_id: str, depends_on=None, bindings=None):
    return ArchitectureModule(
        identifier=identifier,
        instance_id=instance_id,
        display_name=identifier,
        purpose="test",
        stage="test",
        services=["AWS"],
        depends_on=depends_on or [],
        input_bindings=bindings or [],
    )


@pytest.mark.parametrize(
    ("module_id", "outputs"),
    [
        (
            "aws-file-storage",
            {
                "bucket_name": "davdeploy-uploads-123",
                "bucket_arn": "arn:aws:s3:::davdeploy-uploads-123",
            },
        ),
        (
            "aws-nosql-data",
            {
                "table_name": "davdeploy-records",
                "table_arn": "arn:aws:dynamodb:us-east-1:123456789012:table/davdeploy-records",
            },
        ),
        (
            "aws-jobs-events",
            {
                "queue_url": "https://sqs.us-east-1.amazonaws.com/123456789012/davdeploy-work",
                "queue_arn": "arn:aws:sqs:us-east-1:123456789012:davdeploy-work",
            },
        ),
        (
            "aws-secrets-config",
            {
                "secret_reference": "arn:aws:secretsmanager:us-east-1:123456789012:secret:api-key-AbCdEf"
            },
        ),
        (
            "aws-serverless-api",
            {
                "api_url": "https://api.example.test/v1",
                "lambda_arn": "arn:aws:lambda:us-east-1:123456789012:function:davdeploy-api",
            },
        ),
    ],
)
def test_typed_module_outputs_accept_values_matching_the_declared_ports(module_id, outputs):
    assert validate_module_outputs(module_id, outputs) == outputs


@pytest.mark.parametrize(
    ("module_id", "outputs", "message"),
    [
        ("aws-file-storage", {"unknown": "value"}, "undeclared output ports"),
        ("aws-serverless-api", {"api_url": "http://api.example.test"}, "invalid https_url value"),
        ("aws-serverless-api", {"lambda_arn": "not-an-arn"}, "invalid aws_arn value"),
        ("aws-jobs-events", {"queue_url": "https://example.test/q"}, "invalid aws_queue_url value"),
        (
            "aws-secrets-config",
            {"secret_reference": "do-not-store-secret-material"},
            "invalid secret_reference value",
        ),
    ],
)
def test_typed_module_outputs_reject_unknown_or_malformed_values(module_id, outputs, message):
    with pytest.raises(ValueError, match=message):
        validate_module_outputs(module_id, outputs)


def test_typed_module_inputs_accept_only_declared_valid_references():
    assert validate_module_inputs(
        "aws-serverless-api",
        {"uploads_bucket_name": "davdeploy-123456789012-us-east-1-0123456789abcdef0123"},
    ) == {"uploads_bucket_name": "davdeploy-123456789012-us-east-1-0123456789abcdef0123"}
    with pytest.raises(ValueError, match="undeclared input ports"):
        validate_module_inputs("aws-serverless-api", {"arbitrary": "value"})
    with pytest.raises(ValueError, match="invalid resource_name value"):
        validate_module_inputs("aws-serverless-api", {"uploads_bucket_name": "../bucket"})


def test_untyped_legacy_module_outputs_remain_unchanged():
    legacy = {"codebuild_build_id": "executor:build-123"}
    assert validate_module_outputs("aws-managed-application", legacy) is None


def test_serverless_renderer_outputs_normalize_to_typed_module_ports():
    raw_outputs = {
        "api_endpoint": {
            "sensitive": False,
            "type": "string",
            "value": "https://api.example.test",
        },
        "lambda_arn": {
            "sensitive": False,
            "type": "string",
            "value": "arn:aws:lambda:us-east-1:123456789012:function:davdeploy-api",
        },
    }
    assert normalize_renderer_outputs("aws-serverless-api", raw_outputs) == {
        "api_url": "https://api.example.test",
        "lambda_arn": "arn:aws:lambda:us-east-1:123456789012:function:davdeploy-api",
    }


def test_private_s3_renderer_outputs_normalize_to_typed_storage_ports():
    raw_outputs = {
        "bucket_name": {
            "sensitive": False,
            "type": "string",
            "value": "davdeploy-123456789012-us-east-1-0123456789abcdef0123",
        },
        "bucket_arn": {
            "sensitive": False,
            "type": "string",
            "value": "arn:aws:s3:::davdeploy-123456789012-us-east-1-0123456789abcdef0123",
        },
    }
    assert normalize_renderer_outputs("aws-file-storage", raw_outputs) == {
        "bucket_name": raw_outputs["bucket_name"]["value"],
        "bucket_arn": raw_outputs["bucket_arn"]["value"],
    }


def test_dynamodb_renderer_outputs_normalize_to_typed_nosql_ports():
    raw_outputs = {
        "table_name": {
            "sensitive": False,
            "type": "string",
            "value": "davdeploy-123456789012-us-east-1-0123456789abcdef0123",
        },
        "table_arn": {
            "sensitive": False,
            "type": "string",
            "value": "arn:aws:dynamodb:us-east-1:123456789012:table/davdeploy-table",
        },
    }
    assert normalize_renderer_outputs("aws-nosql-data", raw_outputs) == {
        "table_name": raw_outputs["table_name"]["value"],
        "table_arn": raw_outputs["table_arn"]["value"],
    }


def test_private_s3_renderer_output_mapping_rejects_sensitive_or_malformed_values():
    raw_outputs = {
        "bucket_name": {"sensitive": True, "type": "string", "value": "not-stored"},
        "bucket_arn": {
            "sensitive": False,
            "type": "string",
            "value": "arn:aws:s3:::davdeploy-bucket",
        },
    }
    with pytest.raises(ValueError, match="marked sensitive"):
        normalize_renderer_outputs("aws-file-storage", raw_outputs)

    raw_outputs["bucket_name"]["sensitive"] = False
    raw_outputs["bucket_arn"]["value"] = "not-an-s3-arn"
    with pytest.raises(ValueError, match="invalid aws_arn value"):
        normalize_renderer_outputs("aws-file-storage", raw_outputs)


@pytest.mark.parametrize(
    "raw_outputs",
    [
        {"api_endpoint": {"value": "https://api.example.test"}},
        {
            "api_endpoint": {
                "sensitive": True,
                "type": "string",
                "value": "https://api.example.test",
            },
            "lambda_arn": {
                "sensitive": False,
                "type": "string",
                "value": "arn:aws:lambda:us-east-1:123456789012:function:api",
            },
        },
        {
            "api_endpoint": {
                "sensitive": False,
                "type": "string",
                "value": "http://api.example.test",
            },
            "lambda_arn": {
                "sensitive": False,
                "type": "string",
                "value": "arn:aws:lambda:us-east-1:123456789012:function:api",
            },
        },
        {
            "api_endpoint": {
                "sensitive": False,
                "type": "string",
                "value": "https://api.example.test",
            },
            "lambda_arn": {
                "sensitive": False,
                "type": "string",
                "value": "not-an-arn",
            },
        },
        {
            "api_endpoint": {
                "sensitive": False,
                "type": "string",
                "value": "https://api.example.test",
            },
            "lambda_arn": {
                "sensitive": False,
                "type": "string",
                "value": "arn:aws:lambda:us-east-1:123456789012:function:api",
            },
            "unexpected": {"sensitive": False, "type": "string", "value": "extra"},
        },
    ],
)
def test_serverless_renderer_output_mapping_rejects_untrusted_shapes(raw_outputs):
    with pytest.raises((TypeError, ValueError)):
        normalize_renderer_outputs("aws-serverless-api", raw_outputs)


def test_resolver_uses_only_successful_dependency_outputs_and_secret_references():
    digest = sha256(b"approved").hexdigest()
    plan = compile_universal_execution_plan(
        [
            module("aws-file-storage", instance_id="uploads"),
            module("aws-secrets-config", instance_id="credentials"),
            module(
                "aws-serverless-api",
                instance_id="api",
                depends_on=["uploads", "credentials"],
                bindings=[
                    ModuleInputBinding(
                        input_name="uploads_bucket_name",
                        source_instance_id="uploads",
                        source_output="bucket_name",
                    ),
                    ModuleInputBinding(
                        input_name="api_secret_reference",
                        source_instance_id="credentials",
                        source_output="secret_reference",
                    ),
                ],
            ),
        ],
        workspace_id="w",
        project_id="p",
        plan_digest=digest,
    )
    secret_reference = "arn:aws:secretsmanager:us-east-1:123456789012:secret:api-key-AbCdEf"
    outputs = {
        "uploads": {"bucket_name": "davdeploy-uploads-123"},
        "credentials": {"secret_reference": secret_reference},
    }

    with pytest.raises(ValueError, match="has not completed successfully"):
        resolve_module_inputs(
            plan,
            "api",
            outputs,
            {"uploads": "SUCCEEDED_AWAITING_OBSERVATION", "credentials": "RUNNING"},
        )

    assert resolve_module_inputs(
        plan,
        "api",
        outputs,
        {"uploads": "HEALTHY", "credentials": "SUCCEEDED_AWAITING_OBSERVATION"},
    ) == {
        "uploads_bucket_name": "davdeploy-uploads-123",
        "api_secret_reference": secret_reference,
    }

    with pytest.raises(ValueError, match="invalid secret_reference value"):
        resolve_module_inputs(
            plan,
            "api",
            {**outputs, "credentials": {"secret_reference": "plaintext-secret"}},
            {"uploads": "HEALTHY", "credentials": "HEALTHY"},
        )


def test_worker_resolver_reads_only_successful_typed_outputs_from_durable_graph():
    work = [
        {
            "module_id": "aws-file-storage",
            "instance_id": "uploads",
            "operation": "apply",
            "dependencies": [],
            "input_bindings": [],
            "resource_tags": {"ManagedBy": "davdeploy"},
        },
        {
            "module_id": "aws-serverless-api",
            "instance_id": "api",
            "operation": "apply",
            "dependencies": ["uploads"],
            "input_bindings": [
                {
                    "input_name": "uploads_bucket_name",
                    "source_instance_id": "uploads",
                    "source_output": "bucket_name",
                }
            ],
            "resource_tags": {"ManagedBy": "davdeploy"},
        },
    ]
    bucket_name = "davdeploy-123456789012-us-east-1-0123456789abcdef0123"
    digest = sha256(b"approved").hexdigest()

    assert resolve_lifecycle_work_inputs(
        work,
        "api",
        {"uploads": {"bucket_name": bucket_name}},
        {"uploads": "SUCCEEDED_AWAITING_OBSERVATION", "api": "QUEUED"},
        plan_digest=digest,
    ) == {"uploads_bucket_name": bucket_name}

    with pytest.raises(ValueError, match="has not completed successfully"):
        resolve_lifecycle_work_inputs(
            work,
            "api",
            {"uploads": {"bucket_name": bucket_name}},
            {"uploads": "FAILED", "api": "QUEUED"},
            plan_digest=digest,
        )
