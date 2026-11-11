from __future__ import annotations

import pytest
from davdeploy.generated_plan_ownership import (
    PlanOwnershipError,
    PlanOwnershipScope,
    UntaggedResourceOwnershipRecord,
    inject_trusted_ownership_tags,
)


def scope(**overrides):
    values = {
        "organization_id": "org-internal-id",
        "workspace_id": "workspace-internal-id",
        "project_id": "project-internal-id",
        "environment_id": "production",
        "plan_id": "plan-internal-id",
        "revision_id": "revision-internal-id",
    }
    values.update(overrides)
    return PlanOwnershipScope(**values)


def provider_schema(*, tags_attribute=True):
    attributes = {
        "bucket": {"type": "string", "required": True},
    }
    if tags_attribute:
        attributes["tags"] = {"type": ["map", "string"], "optional": True}
    return {
        "provider_schemas": {
            "registry.terraform.io/hashicorp/aws": {
                "resource_schemas": {
                    "aws_s3_bucket": {"block": {"attributes": attributes}}
                }
            }
        }
    }


def configuration(tags=None):
    return {
        "resource": {
            "aws_s3_bucket": {
                "uploads": {
                    "bucket": "example-uploads",
                    "tags": tags or {"Purpose": "customer-uploads"},
                }
            },
            "terraform_data": {"account_guard": {"input": "trusted"}},
        }
    }


def test_ownership_tags_are_server_derived_and_custom_tags_are_preserved():
    generated = configuration()
    trusted = scope()

    inject_trusted_ownership_tags(generated, provider_schema(), trusted)

    tags = generated["resource"]["aws_s3_bucket"]["uploads"]["tags"]
    assert tags["Purpose"] == "customer-uploads"
    assert {key: tags[key] for key in trusted.tags()} == trusted.tags()
    assert tags["DavDeployWorkspace"] != trusted.workspace_id


def test_reserved_ownership_tag_cannot_be_overridden():
    generated = configuration({"davdeployworkspace": "spoofed"})

    with pytest.raises(PlanOwnershipError, match="reserved ownership tags"):
        inject_trusted_ownership_tags(generated, provider_schema(), scope())


def test_resource_without_writable_tag_schema_is_rejected():
    generated = configuration()

    with pytest.raises(PlanOwnershipError, match="no supported ownership mechanism"):
        inject_trusted_ownership_tags(
            generated,
            provider_schema(tags_attribute=False),
            scope(),
        )


def untaggable_route_schema():
    return {
        "provider_schemas": {
            "registry.terraform.io/hashicorp/aws": {
                "resource_schemas": {
                    "aws_apigatewayv2_route": {
                        "block": {
                            "attributes": {
                                "api_id": {"type": "string", "required": True},
                                "route_key": {"type": "string", "required": True},
                            }
                        }
                    }
                }
            }
        }
    }


def untaggable_route_configuration():
    return {
        "resource": {
            "aws_apigatewayv2_route": {
                "application": {"api_id": "api-123", "route_key": "GET /items"}
            }
        }
    }


def test_untaggable_api_route_requires_remote_state_and_records_exact_address():
    generated = untaggable_route_configuration()
    state_id = "12345678-1234-4234-8234-123456789012"

    records = inject_trusted_ownership_tags(
        generated,
        untaggable_route_schema(),
        scope(),
        remote_state_id=state_id,
        remote_state_scope_sha256="c" * 64,
        expected_remote_state_scope_sha256="c" * 64,
    )

    assert records == (
        UntaggedResourceOwnershipRecord(
            address="aws_apigatewayv2_route.application",
            resource_type="aws_apigatewayv2_route",
        ),
    )
    assert "tags" not in generated["resource"]["aws_apigatewayv2_route"]["application"]


def test_untaggable_api_route_fails_without_remote_state_or_on_scope_mismatch():
    for state_args in (
        {},
        {
            "remote_state_id": "12345678-1234-4234-8234-123456789012",
            "remote_state_scope_sha256": "c" * 64,
            "expected_remote_state_scope_sha256": "d" * 64,
        },
    ):
        with pytest.raises(PlanOwnershipError, match="no safely writable ownership tags or verified remote state"):
            inject_trusted_ownership_tags(
                untaggable_route_configuration(),
                untaggable_route_schema(),
                scope(),
                **state_args,
            )


def test_unsupported_untaggable_resource_stays_denied_even_with_state():
    with pytest.raises(PlanOwnershipError, match="no supported ownership mechanism"):
        inject_trusted_ownership_tags(
            configuration(),
            provider_schema(tags_attribute=False),
            scope(),
            remote_state_id="12345678-1234-4234-8234-123456789012",
            remote_state_scope_sha256="c" * 64,
            expected_remote_state_scope_sha256="c" * 64,
        )


@pytest.mark.parametrize(
    "resource_type",
    ["aws_instance", "aws_autoscaling_group", "aws_ecs_service", "aws_lambda_function"],
)
def test_resources_with_unverified_child_tag_propagation_are_rejected(resource_type):
    generated = {
        "resource": {
            resource_type: {"primary": {"tags": {"Purpose": "application"}}}
        }
    }

    with pytest.raises(PlanOwnershipError, match="child resources without verified ownership tags"):
        inject_trusted_ownership_tags(generated, provider_schema(), scope())


@pytest.mark.parametrize(
    "field, value",
    [
        ("organization_id", " "),
        ("workspace_id", "workspace\n"),
        ("project_id", ""),
        ("plan_id", " " ),
    ],
)
def test_untrusted_or_malformed_scope_is_rejected(field, value):
    with pytest.raises(PlanOwnershipError):
        scope(**{field: value})
