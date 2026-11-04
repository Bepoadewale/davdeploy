from __future__ import annotations

import pytest
from davdeploy.generated_plan_ownership import (
    PlanOwnershipError,
    PlanOwnershipScope,
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

    with pytest.raises(PlanOwnershipError, match="no safely writable ownership tags"):
        inject_trusted_ownership_tags(
            generated,
            provider_schema(tags_attribute=False),
            scope(),
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
