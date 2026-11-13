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
    resource_type: str = "aws_s3_bucket",
    arguments: dict[str, object] | None = None,
    depends_on: tuple[str, ...] = (),
    outputs: tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    return {
        "resource_id": resource_id,
        "resource_type": resource_type,
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


def test_proposal_health_recovery_and_cost_evidence_is_bounded() -> None:
    base = proposal([resource("uploads", "uploads")])
    base["health_assertions"] = [
        {
            "kind": "storage_roundtrip",
            "target_resource_id": "uploads",
            "description": "A synthetic object can be stored and read back.",
        }
    ]
    base["recovery"] = {
        "backup_required": True,
        "recovery_point_objective_minutes": 60,
        "recovery_time_objective_minutes": 240,
        "destructive_change_notes": "Keep the previous object version.",
    }
    base["cost_assumptions"] = [
        {
            "resource_id": "uploads",
            "description": "Low initial request volume.",
            "source": "customer input",
            "captured_at": "2026-11-13T00:00:00Z",
        }
    ]
    base["assumptions"] = ["Initial request volume is low."]
    base["limitations"] = ["Health checks have not run."]
    parsed = GeneratedDeploymentProposal.model_validate(base)
    assert parsed.health_assertions[0].target_resource_id == "uploads"
    assert parsed.recovery.backup_required is True
    assert parsed.cost_assumptions[0].resource_id == "uploads"

    too_many_health_checks = {**base, "health_assertions": base["health_assertions"] * 65}
    with pytest.raises(ValidationError):
        GeneratedDeploymentProposal.model_validate(too_many_health_checks)

    overlong_assumption = {**base, "assumptions": ["x" * 501]}
    with pytest.raises(ValidationError, match="bounded text"):
        GeneratedDeploymentProposal.model_validate(overlong_assumption)


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
                    resource_type="aws_db_instance",
                    arguments={"manage_master_user_password": True},
                    outputs=(
                        {
                            "name": "master_user_secret[0].secret_arn",
                            "value_type": "secret_reference",
                        },
                    ),
                ),
                resource(
                    "api",
                    "api",
                    resource_type="aws_lambda_function",
                    arguments={
                        "environment": [
                            {
                                "variables": {
                                    "API_TOKEN_SECRET_ARN": {
                                        "kind": "resource_reference",
                                        "resource_id": "credentials",
                                        "output_name": "master_user_secret[0].secret_arn",
                                        "value_type": "secret_reference",
                                    }
                                },
                            }
                        ]
                    },
                ),
            ]
        )
    )

    assert len(result.resources) == 2


def test_contract_rejects_secret_arn_reference_as_a_password_value() -> None:
    with pytest.raises(ValidationError, match="Lambda secret ARN environment variable"):
        GeneratedDeploymentProposal.model_validate(
            proposal(
                [
                    resource(
                        "credentials",
                        "credentials",
                        resource_type="aws_db_instance",
                        arguments={"manage_master_user_password": True},
                        outputs=(
                            {
                                "name": "master_user_secret[0].secret_arn",
                                "value_type": "secret_reference",
                            },
                        ),
                    ),
                    resource(
                        "application",
                        "application",
                        resource_type="aws_lambda_function",
                        arguments={
                            "environment": [
                                {
                                    "variables": {
                                        "DATABASE_PASSWORD": {
                                            "kind": "resource_reference",
                                            "resource_id": "credentials",
                                            "output_name": "master_user_secret[0].secret_arn",
                                            "value_type": "secret_reference",
                                        }
                                    }
                                }
                            ]
                        },
                    ),
                ]
            )
        )


@pytest.mark.parametrize(
    "resource_type,arguments,output_name",
    [
        ("aws_lambda_function", {}, "arn"),
        ("aws_db_instance", {"manage_master_user_password": False}, "master_user_secret[0].secret_arn"),
        ("aws_rds_cluster", {}, "master_user_secret[0].secret_status"),
    ],
)
def test_contract_rejects_forged_or_unmanaged_secret_reference_outputs(
    resource_type: str, arguments: dict[str, object], output_name: str
) -> None:
    with pytest.raises(ValidationError, match="RDS-managed master secret ARN"):
        GeneratedDeploymentProposal.model_validate(
            proposal(
                [
                    resource(
                        "credentials",
                        "credentials",
                        resource_type=resource_type,
                        arguments=arguments,
                        outputs=({"name": output_name, "value_type": "secret_reference"},),
                    )
                ]
            )
        )


def test_contract_rejects_non_literal_zero_output_indices() -> None:
    with pytest.raises(ValidationError):
        GeneratedDeploymentProposal.model_validate(
            proposal(
                [
                    resource(
                        "credentials",
                        "credentials",
                        resource_type="aws_db_instance",
                        arguments={"manage_master_user_password": True},
                        outputs=(
                            {
                                "name": "master_user_secret[1].secret_arn",
                                "value_type": "secret_reference",
                            },
                        ),
                    )
                ]
            )
        )


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


@pytest.mark.parametrize(
    "arguments",
    [
        {"access_token_validity": 15, "id_token_validity": 15},
        {
            "password_policy": {
                "minimum_length": 12,
                "require_numbers": True,
                "temporary_password_validity_days": 7,
            }
        },
        {"software_token_mfa_configuration": {"enabled": True}},
        {
            "token_validity_units": {
                "access_token": "minutes",
                "id_token": "minutes",
                "refresh_token": "days",
            }
        },
    ],
)
def test_contract_accepts_secret_related_policy_and_lifetime_configuration(
    arguments: dict[str, object],
) -> None:
    result = GeneratedDeploymentProposal.model_validate(
        proposal([resource("identity", "identity", arguments=arguments)])
    )

    assert result.resources[0].arguments == arguments


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


def test_resource_blocks_compile_nested_secret_arn_reference() -> None:
    from davdeploy.generated_deployment_contract import terraform_resource_blocks

    generated = GeneratedDeploymentProposal.model_validate(
        proposal(
            [
                resource(
                    "database",
                    "database",
                    resource_type="aws_db_instance",
                    arguments={"manage_master_user_password": True},
                    outputs=(
                        {
                            "name": "master_user_secret[0].secret_arn",
                            "value_type": "secret_reference",
                        },
                    ),
                ),
                resource(
                    "application",
                    "application",
                    resource_type="aws_lambda_function",
                    arguments={
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
                        ]
                    },
                ),
            ]
        )
    )

    blocks = terraform_resource_blocks(generated)
    assert blocks["aws_lambda_function"]["application"]["environment"][0]["variables"][
        "DATABASE_SECRET_ARN"
    ] == "${aws_db_instance.database.master_user_secret[0].secret_arn}"
