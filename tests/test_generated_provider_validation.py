from __future__ import annotations

import pytest
from davdeploy.generated_deployment_contract import (
    GeneratedDeploymentProposal,
    GeneratedResource,
)
from davdeploy.generated_provider_validation import (
    GeneratedProviderSchemaError,
    validate_generated_proposal,
)

PROVIDER = "registry.terraform.io/hashicorp/aws"


def schema():
    return {
        "provider_schemas": {
            PROVIDER: {
                "provider": {"version": 0},
                "resource_schemas": {
                    "aws_test_resource": {
                        "block": {
                            "attributes": {
                                "name": {"type": "string", "required": True},
                                "enabled": {"type": "bool", "optional": True},
                                "secret": {
                                    "type": "string",
                                    "optional": True,
                                    "sensitive": True,
                                },
                                "id": {
                                    "type": "string",
                                    "computed": True,
                                    "sensitive": False,
                                },
                            },
                            "block_types": {},
                        }
                    },
                    "aws_db_instance": {
                        "block": {
                            "attributes": {
                                "manage_master_user_password": {
                                    "type": "bool",
                                    "optional": True,
                                },
                                "master_user_secret": {
                                    "type": [
                                        "list",
                                        ["object", {"secret_arn": "string", "secret_status": "string"}],
                                    ],
                                    "computed": True,
                                    "sensitive": False,
                                },
                            },
                            "block_types": {},
                        }
                    },
                    "aws_lambda_function": {
                        "block": {
                            "attributes": {
                                "function_name": {"type": "string", "required": True},
                            },
                            "block_types": {
                                "environment": {
                                    "nesting_mode": "list",
                                    "max_items": 1,
                                    "block": {
                                        "attributes": {
                                            "variables": {
                                                "type": ["map", "string"],
                                                "optional": True,
                                            }
                                        },
                                        "block_types": {},
                                    },
                                }
                            },
                        }
                    },
                },
            }
        }
    }


def proposal(arguments=None, outputs=None, resource_type="aws_test_resource"):
    return GeneratedDeploymentProposal.model_validate(
        {
            "contract_version": "1.0",
            "source_revision": "revision",
            "context_digest": "a" * 64,
            "requirements": {"region": "us-east-1"},
            "resources": [
                {
                    "resource_id": "primary",
                    "resource_type": resource_type,
                    "name": "primary",
                    "arguments": arguments if arguments is not None else {"name": "demo"},
                    "outputs": outputs
                    if outputs is not None
                    else [{"name": "id", "value_type": "string"}],
                    "rationale": "Test fixture.",
                }
            ],
        }
    )


def test_schema_validation_accepts_known_fields_and_pinned_provider():
    validate_generated_proposal(
        proposal({"name": "demo", "enabled": True}),
        schema(),
        expected_provider_schema_version=0,
    )


@pytest.mark.parametrize(
    "value, expected",
    [
        (proposal({"name": "demo", "made_up": True}), "unsupported arguments"),
        (proposal({"enabled": True}), "missing required argument"),
        (proposal(outputs=[{"name": "missing", "value_type": "string"}]), "not a provider output"),
        (proposal(resource_type="aws_unknown_resource"), "absent from the pinned AWS provider"),
    ],
)
def test_schema_validation_rejects_invalid_proposals(value, expected):
    with pytest.raises(GeneratedProviderSchemaError, match=expected):
        validate_generated_proposal(value, schema())


def test_schema_validation_rejects_wrong_provider_schema_format_version():
    with pytest.raises(GeneratedProviderSchemaError, match="format version"):
        validate_generated_proposal(
            proposal(), schema(), expected_provider_schema_version=1
        )


def test_provider_schema_still_rejects_sensitive_literal_after_contract_bypass():
    # Defense in depth: a corrupted or legacy proposal cannot bypass provider
    # sensitivity checks even if it did not pass current contract validation.
    generated = GeneratedDeploymentProposal.model_construct(
        resources=(
            GeneratedResource.model_construct(
                resource_id="primary",
                resource_type="aws_test_resource",
                name="primary",
                arguments={"name": "demo", "secret": "plaintext"},
                outputs=(),
            ),
        )
    )

    with pytest.raises(GeneratedProviderSchemaError, match="must use a declared reference"):
        validate_generated_proposal(generated, schema())


def test_schema_validation_accepts_typed_resource_output_reference():
    document = schema()
    attributes = document["provider_schemas"][PROVIDER]["resource_schemas"][
        "aws_test_resource"
    ]["block"]["attributes"]
    attributes["input"] = {"type": "string", "optional": True}
    generated = GeneratedDeploymentProposal.model_validate(
        {
            "contract_version": "1.0",
            "source_revision": "revision",
            "context_digest": "a" * 64,
            "requirements": {"region": "us-east-1"},
            "resources": [
                {
                    "resource_id": "source",
                    "resource_type": "aws_test_resource",
                    "name": "source",
                    "arguments": {"name": "source"},
                    "outputs": [{"name": "id", "value_type": "string"}],
                    "rationale": "Creates a source resource.",
                },
                {
                    "resource_id": "consumer",
                    "resource_type": "aws_test_resource",
                    "name": "consumer",
                    "arguments": {
                        "name": "consumer",
                        "input": {
                            "kind": "resource_reference",
                            "resource_id": "source",
                            "output_name": "id",
                            "value_type": "string",
                        },
                    },
                    "rationale": "Consumes the declared source output.",
                },
            ],
        }
    )

    validate_generated_proposal(generated, document)


def test_schema_validation_accepts_rds_managed_nested_secret_arn_reference():
    document = schema()
    document["provider_schemas"][PROVIDER]["resource_schemas"][
        "aws_test_resource"
    ]["block"]["attributes"]["input"] = {"type": "string", "optional": True}
    generated = GeneratedDeploymentProposal.model_validate(
        {
            "contract_version": "1.0",
            "source_revision": "revision",
            "context_digest": "a" * 64,
            "requirements": {"region": "us-east-1"},
            "resources": [
                {
                    "resource_id": "database",
                    "resource_type": "aws_db_instance",
                    "name": "database",
                    "arguments": {"manage_master_user_password": True},
                    "outputs": [
                        {
                            "name": "master_user_secret[0].secret_arn",
                            "value_type": "secret_reference",
                        }
                    ],
                    "rationale": "Uses an RDS-managed master password.",
                },
                {
                    "resource_id": "application",
                    "resource_type": "aws_lambda_function",
                    "name": "application",
                    "arguments": {
                        "function_name": "application",
                        "environment": [
                            {
                                "variables": {
                                    "DATABASE_SECRET_ARN": {
                                        "kind": "resource_reference",
                                        "resource_id": "database",
                                        "output_name": "master_user_secret[0].secret_arn",
                                        "value_type": "secret_reference",
                                    }
                                }
                            }
                        ],
                    },
                    "rationale": "Receives only the secret ARN reference.",
                },
            ],
        }
    )

    validate_generated_proposal(generated, document)


def test_schema_validation_rejects_nested_reference_path_missing_from_provider():
    document = schema()
    document["provider_schemas"][PROVIDER]["resource_schemas"]["aws_db_instance"][
        "block"
    ]["attributes"].pop("master_user_secret")
    generated = GeneratedDeploymentProposal.model_validate(
        {
            "contract_version": "1.0",
            "source_revision": "revision",
            "context_digest": "a" * 64,
            "requirements": {"region": "us-east-1"},
            "resources": [
                {
                    "resource_id": "database",
                    "resource_type": "aws_db_instance",
                    "name": "database",
                    "arguments": {"manage_master_user_password": True},
                    "outputs": [
                        {
                            "name": "master_user_secret[0].secret_arn",
                            "value_type": "secret_reference",
                        }
                    ],
                    "rationale": "Uses an RDS-managed master password.",
                }
            ],
        }
    )

    with pytest.raises(GeneratedProviderSchemaError, match="not a provider output"):
        validate_generated_proposal(generated, document)
