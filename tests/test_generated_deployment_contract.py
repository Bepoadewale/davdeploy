from __future__ import annotations

import pytest
from davdeploy.generated_deployment_contract import GeneratedDeploymentProposal
from pydantic import ValidationError


def proposal(resources: list[dict[str, object]]) -> dict[str, object]:
    return {
        "contract_version": "1.0",
        "source_revision": "test-revision",
        "context_digest": "a" * 64,
        "resources": resources,
        "requirements": {"region": "us-east-1"},
    }


def resource(
    resource_id: str,
    name: str,
    *,
    arguments: dict[str, object] | None = None,
    depends_on: tuple[str, ...] = (),
    outputs: tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    return {
        "resource_id": resource_id,
        "resource_type": "aws_s3_bucket",
        "name": name,
        "arguments": arguments or {},
        "depends_on": depends_on,
        "outputs": outputs,
        "rationale": "Stores private application uploads.",
    }


def test_contract_accepts_a_typed_reference_and_infers_dependency() -> None:
    result = GeneratedDeploymentProposal.model_validate(
        proposal(
            [
                resource(
                    "uploads",
                    "uploads",
                    outputs=(
                        {"name": "bucket_name", "value_type": "resource_name"},
                    ),
                ),
                resource(
                    "api",
                    "api",
                    depends_on=("uploads",),
                    arguments={
                        "bucket": {
                            "kind": "resource_reference",
                            "resource_id": "uploads",
                            "output_name": "bucket_name",
                            "value_type": "resource_name",
                        }
                    },
                ),
            ]
        )
    )

    assert [item.resource_id for item in result.resources] == ["uploads", "api"]


@pytest.mark.parametrize(
    "resources",
    [
        [resource("same", "one"), resource("same", "two")],
        [resource("one", "same"), resource("two", "same")],
        [resource("one", "one", depends_on=("missing",))],
        [
            resource("one", "one", depends_on=("two",)),
            resource("two", "two", depends_on=("one",)),
        ],
        [
            resource(
                "api",
                "api",
                arguments={
                    "bucket": {
                        "kind": "resource_reference",
                        "resource_id": "missing",
                        "output_name": "bucket_name",
                        "value_type": "resource_name",
                    }
                },
            )
        ],
        [
            resource(
                "uploads",
                "uploads",
                outputs=({"name": "bucket_name", "value_type": "resource_name"},),
            ),
            resource(
                "api",
                "api",
                arguments={
                    "bucket": {
                        "kind": "resource_reference",
                        "resource_id": "uploads",
                        "output_name": "bucket_name",
                        "value_type": "aws_arn",
                    }
                },
            ),
        ],
        [resource("one", "one", arguments={"name": "file(unsafe)"})],
        [resource("one", "one", arguments={"user_data": "unsafe"})],
        [
            resource(
                "one",
                "one",
                arguments={"tags": {"davdeployworkspace": "spoofed-owner"}},
            )
        ],
    ],
)
def test_contract_rejects_unsafe_or_invalid_graphs(
    resources: list[dict[str, object]],
) -> None:
    with pytest.raises(ValidationError):
        GeneratedDeploymentProposal.model_validate(proposal(resources))


@pytest.mark.parametrize(
    "field,value",
    [
        ("api_key", "literal-api-key"),
        ("clientSecret", "literal-client-secret"),
        ("AUTH-TOKEN", "literal-auth-token"),
        ("nested", {"session_token": "literal-session-token"}),
        (
            "environment",
            [{"name": "API_TOKEN", "value": "literal-env-token"}],
        ),
    ],
)
def test_contract_rejects_literal_secret_fields(field: str, value: object) -> None:
    with pytest.raises(ValidationError, match="typed secret_reference|forbidden"):
        GeneratedDeploymentProposal.model_validate(
            proposal([resource("api", "api", arguments={field: value})])
        )


def test_contract_accepts_typed_secret_reference_without_secret_material() -> None:
    result = GeneratedDeploymentProposal.model_validate(
        proposal(
            [
                resource(
                    "credentials",
                    "credentials",
                    outputs=(
                        {"name": "secret_arn", "value_type": "secret_reference"},
                    ),
                ),
                resource(
                    "api",
                    "api",
                    arguments={
                        "environment": [
                            {
                                "name": "API_TOKEN",
                                "value": {
                                    "kind": "resource_reference",
                                    "resource_id": "credentials",
                                    "output_name": "secret_arn",
                                    "value_type": "secret_reference",
                                },
                            }
                        ]
                    },
                ),
            ]
        )
    )

    assert len(result.resources) == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("manage_master_user_password", True),
        ("generate_secret", False),
        ("enable_token_revocation", True),
    ],
)
def test_contract_accepts_boolean_secret_related_configuration(field: str, value: bool) -> None:
    result = GeneratedDeploymentProposal.model_validate(
        proposal([resource("api", "api", arguments={field: value})])
    )

    assert result.resources[0].arguments[field] is value


def test_contract_emits_a_json_schema_for_nova_structured_generation() -> None:
    schema = GeneratedDeploymentProposal.model_json_schema()

    assert schema["title"] == "GeneratedDeploymentProposal"
    assert "resources" in schema["properties"]
    assert "requirements" in schema["properties"]


def test_resource_blocks_compile_references_only_after_contract_validation() -> None:
    from davdeploy.generated_deployment_contract import terraform_resource_blocks

    generated = GeneratedDeploymentProposal.model_validate(
        proposal(
            [
                resource(
                    "uploads",
                    "uploads",
                    outputs=(
                        {"name": "bucket_name", "value_type": "resource_name"},
                    ),
                ),
                resource(
                    "api",
                    "api",
                    depends_on=("uploads",),
                    arguments={
                        "bucket": {
                            "kind": "resource_reference",
                            "resource_id": "uploads",
                            "output_name": "bucket_name",
                            "value_type": "resource_name",
                        }
                    },
                ),
            ]
        )
    )

    blocks = terraform_resource_blocks(generated)
    assert blocks["aws_s3_bucket"]["api"]["bucket"] == (
        chr(36) + "{aws_s3_bucket.uploads.bucket_name}"
    )
    assert blocks["aws_s3_bucket"]["api"]["depends_on"] == [
        "aws_s3_bucket.uploads"
    ]
