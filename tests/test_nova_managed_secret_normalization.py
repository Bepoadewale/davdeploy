from __future__ import annotations

from copy import deepcopy

from davdeploy.generated_deployment_contract import GeneratedDeploymentProposal
from davdeploy.nova_contract_generation import normalize_managed_lambda_secret_reference


def proposal(*, databases: int = 1, variables: dict[str, object] | None = None):
    resources = [
        {
            "resource_id": "db" if index == 0 else f"db-{index + 1}",
            "resource_type": "aws_db_instance",
            "name": f"database_{index + 1}",
            "arguments": {"manage_master_user_password": False},
            "outputs": [],
            "rationale": "Stores application records.",
        }
        for index in range(databases)
    ]
    resources.append(
        {
            "resource_id": "api",
            "resource_type": "aws_lambda_function",
            "name": "api",
            "arguments": {
                "environment": [
                    {"variables": variables or {"DATABASE_SECRET_ARN": "literal-must-not-survive"}}
                ]
            },
            "rationale": "Processes application requests.",
        }
    )
    return {
        "contract_version": "1.1",
        "source_revision": "revision-123",
        "context_digest": "0" * 64,
        "resources": resources,
        "requirements": {"region": "us-east-1"},
    }


def test_single_lambda_secret_arn_uses_unique_managed_rds_secret_reference():
    original = proposal()
    normalized = normalize_managed_lambda_secret_reference(original)

    database = normalized["resources"][0]
    lambda_resource = normalized["resources"][1]
    reference = lambda_resource["arguments"]["environment"][0]["variables"]["DATABASE_SECRET_ARN"]

    assert database["arguments"]["manage_master_user_password"] is True
    assert database["outputs"] == [
        {
            "name": "master_user_secret[0].secret_arn",
            "value_type": "secret_reference",
            "sensitive": True,
        }
    ]
    assert reference == {
        "kind": "resource_reference",
        "resource_id": "db",
        "output_name": "master_user_secret[0].secret_arn",
        "value_type": "secret_reference",
    }
    GeneratedDeploymentProposal.model_validate(normalized)
    assert "literal-must-not-survive" not in repr(normalized)
    assert "literal-must-not-survive" in repr(original)


def test_existing_managed_secret_output_is_marked_sensitive_and_reused():
    original = proposal()
    database = original["resources"][0]
    database["arguments"]["manage_master_user_password"] = True
    database["outputs"] = [
        {"name": "master_user_secret[0].secret_arn", "value_type": "secret_reference"}
    ]

    normalized = normalize_managed_lambda_secret_reference(original)

    assert normalized["resources"][0]["outputs"] == [
        {
            "name": "master_user_secret[0].secret_arn",
            "value_type": "secret_reference",
            "sensitive": True,
        }
    ]
    GeneratedDeploymentProposal.model_validate(normalized)


def test_multiple_database_resources_are_not_guessed():
    original = proposal(databases=2)
    before = deepcopy(original)

    assert normalize_managed_lambda_secret_reference(original) is original
    assert original == before


def test_multiple_lambda_secret_arn_variables_are_not_guessed():
    original = proposal(
        variables={
            "DATABASE_SECRET_ARN": "first-literal",
            "CACHE_SECRET_ARN": "second-literal",
        }
    )
    before = deepcopy(original)

    assert normalize_managed_lambda_secret_reference(original) is original
    assert original == before


def test_other_secret_variable_names_are_not_repaired():
    other_name = proposal(variables={"DATABASE_URL": "literal-must-not-survive"})

    assert normalize_managed_lambda_secret_reference(other_name) is other_name


def test_supported_rds_master_password_literals_are_removed_when_bound_to_secret_arn():
    for resource_type, password_field in (
        ("aws_db_instance", "password"),
        ("aws_rds_cluster", "master_password"),
    ):
        original = proposal()
        database = original["resources"][0]
        database["resource_type"] = resource_type
        database["arguments"][password_field] = "literal-must-not-survive"

        normalized = normalize_managed_lambda_secret_reference(original)

        assert password_field not in normalized["resources"][0]["arguments"]
        assert normalized["resources"][0]["arguments"]["manage_master_user_password"] is True
        assert "literal-must-not-survive" not in repr(normalized)
        GeneratedDeploymentProposal.model_validate(normalized)


def test_rds_master_password_is_not_removed_without_a_secret_arn_consumer():
    original = proposal(variables={"DATABASE_URL": "url-literal"})
    original["resources"][0]["resource_type"] = "aws_rds_cluster"
    original["resources"][0]["arguments"]["master_password"] = "literal-must-not-survive"
    before = deepcopy(original)

    assert normalize_managed_lambda_secret_reference(original) is original
    assert original == before
