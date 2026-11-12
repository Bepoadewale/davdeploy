"""Deterministic validation of generated AWS resources against provider schemas."""

from __future__ import annotations

import re
from typing import Any

from davdeploy.generated_deployment_contract import (
    GENERATED_OUTPUT_PATH_PATTERN,
    GeneratedDeploymentProposal,
    ResourceReference,
)


class GeneratedProviderSchemaError(ValueError):
    """The proposal does not match the pinned AWS provider schema."""


def _schema_value_type(value: Any) -> str:
    if value in ("string", "bool", "number"):
        return str(value)
    if isinstance(value, list) and len(value) == 2:
        if value[0] in ("list", "set", "tuple"):
            return "list"
        if value[0] == "map":
            return "map"
        if value[0] == "object":
            return "object"
    return "object"


_OUTPUT_PATH_PATTERN = re.compile(GENERATED_OUTPUT_PATH_PATTERN)


def _computed_output(block: dict[str, Any], path: str) -> tuple[Any, bool, bool] | None:
    """Resolve a direct or fixed-index nested computed attribute path."""
    if not isinstance(path, str) or not _OUTPUT_PATH_PATTERN.fullmatch(path):
        return None
    tokens = re.findall(r"[a-z][a-z0-9_]{0,62}|\[0\]", path)
    attributes = block.get("attributes", {})
    if not tokens or not isinstance(attributes, dict):
        return None
    attribute = attributes.get(tokens[0])
    if not isinstance(attribute, dict):
        return None
    computed = attribute.get("computed") is True
    sensitive = attribute.get("sensitive") is True
    current_type = attribute.get("type")
    for token in tokens[1:]:
        if token == "[0]":
            if (
                not isinstance(current_type, list)
                or len(current_type) != 2
                or current_type[0] not in {"list", "tuple"}
            ):
                return None
            current_type = current_type[1]
        else:
            if (
                not isinstance(current_type, list)
                or len(current_type) != 2
                or current_type[0] != "object"
                or not isinstance(current_type[1], dict)
            ):
                return None
            current_type = current_type[1].get(token)
            if current_type is None:
                return None
    return current_type, computed, sensitive


def _reference(value: Any) -> ResourceReference | None:
    if isinstance(value, dict) and value.get("kind") == "resource_reference":
        return ResourceReference.model_validate(value)
    return None


def _references(value: Any) -> list[ResourceReference]:
    reference = _reference(value)
    if reference is not None:
        return [reference]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _references(child)]
    if isinstance(value, list):
        return [item for child in value for item in _references(child)]
    return []


def _validate_block(
    arguments: dict[str, Any],
    block_schema: dict[str, Any],
    address: str,
) -> None:
    attributes = block_schema.get("attributes", {})
    block_types = block_schema.get("block_types", {})
    allowed = set(attributes) | set(block_types) | {"depends_on"}
    unknown = set(arguments) - allowed
    if unknown:
        raise GeneratedProviderSchemaError(
            f"{address} has unsupported arguments: {', '.join(sorted(unknown))}"
        )

    for name, attribute in attributes.items():
        if attribute.get("required") and name not in arguments:
            raise GeneratedProviderSchemaError(
                f"{address} is missing required argument {name}"
            )
        if name not in arguments:
            continue
        value = arguments[name]
        if attribute.get("computed") and not attribute.get("optional"):
            raise GeneratedProviderSchemaError(
                f"{address}.{name} is computed by AWS and cannot be proposed"
            )
        ref = _reference(value)
        if attribute.get("sensitive") and ref is None:
            raise GeneratedProviderSchemaError(
                f"{address}.{name} is sensitive and must use a declared reference"
            )
        expected = _schema_value_type(attribute.get("type"))
        if ref is not None:
            if expected != ref.value_type and not (
                expected == "string"
                and ref.value_type
                in {"resource_name", "aws_arn", "https_url", "aws_queue_url", "secret_reference"}
            ):
                raise GeneratedProviderSchemaError(
                    f"{address}.{name} reference type does not match the provider schema"
                )
        elif expected == "string" and not isinstance(value, str):
            raise GeneratedProviderSchemaError(f"{address}.{name} must be a string")
        elif expected == "bool" and not isinstance(value, bool):
            raise GeneratedProviderSchemaError(f"{address}.{name} must be a boolean")
        elif expected == "number" and (
            isinstance(value, bool) or not isinstance(value, (int, float))
        ):
            raise GeneratedProviderSchemaError(f"{address}.{name} must be a number")
        elif expected == "map" and not isinstance(value, dict):
            raise GeneratedProviderSchemaError(f"{address}.{name} must be a map")
        elif expected == "list" and not isinstance(value, list):
            raise GeneratedProviderSchemaError(f"{address}.{name} must be a list")
        elif expected == "object" and not isinstance(value, dict):
            raise GeneratedProviderSchemaError(f"{address}.{name} must be an object")

    for name, value in arguments.items():
        if name not in block_types:
            continue
        nested = block_types[name]
        child_schema = nested.get("block", {})
        mode = nested.get("nesting_mode")
        if mode == "single":
            if not isinstance(value, dict):
                raise GeneratedProviderSchemaError(f"{address}.{name} must be an object")
            _validate_block(value, child_schema, f"{address}.{name}")
        elif mode in ("list", "set"):
            if not isinstance(value, list):
                raise GeneratedProviderSchemaError(f"{address}.{name} must be a list")
            for index, child in enumerate(value):
                if not isinstance(child, dict):
                    raise GeneratedProviderSchemaError(
                        f"{address}.{name}[{index}] must be an object"
                    )
                _validate_block(child, child_schema, f"{address}.{name}[{index}]")
        elif mode == "group":
            if not isinstance(value, dict):
                raise GeneratedProviderSchemaError(f"{address}.{name} must be an object")
            _validate_block(value, child_schema, f"{address}.{name}")
        elif mode == "map":
            if not isinstance(value, dict):
                raise GeneratedProviderSchemaError(f"{address}.{name} must be a map")
            for key, child in value.items():
                if not isinstance(child, dict):
                    raise GeneratedProviderSchemaError(
                        f"{address}.{name}.{key} must be an object"
                    )
                _validate_block(child, child_schema, f"{address}.{name}.{key}")
        else:
            raise GeneratedProviderSchemaError(
                f"{address}.{name} uses unsupported provider nesting mode"
            )


def validate_generated_proposal(
    proposal: GeneratedDeploymentProposal,
    provider_schema_document: dict[str, Any],
    *,
    provider_address: str = "registry.terraform.io/hashicorp/aws",
    expected_provider_schema_version: int | None = None,
) -> None:
    """Check resource names, arguments and declared reference outputs.

    The caller must obtain this schema from the pinned provider lockfile. This
    validates Terraform configuration shape, not AWS permissions, quotas,
    service behavior, cost or successful execution.
    """
    schemas = provider_schema_document.get("provider_schemas", {})
    provider = schemas.get(provider_address)
    if not isinstance(provider, dict):
        raise GeneratedProviderSchemaError("pinned AWS provider schema is unavailable")
    if expected_provider_schema_version is not None:
        actual = provider.get("provider", {}).get("version")
        if actual != expected_provider_schema_version:
            raise GeneratedProviderSchemaError(
                "provider schema format version does not match the expected version"
            )
    resource_schemas = provider.get("resource_schemas", {})
    by_id = {item.resource_id: item for item in proposal.resources}
    for resource in proposal.resources:
        schema = resource_schemas.get(resource.resource_type)
        if not isinstance(schema, dict):
            raise GeneratedProviderSchemaError(
                f"resource type {resource.resource_type} is absent from the pinned AWS provider"
            )
        _validate_block(
            resource.arguments,
            schema.get("block", {}),
            f"{resource.resource_type}.{resource.name}",
        )
        block = schema.get("block", {})
        for output in resource.outputs:
            resolved = _computed_output(block, output.name)
            if resolved is None or not resolved[1]:
                raise GeneratedProviderSchemaError(
                    f"{resource.resource_type}.{resource.name}.{output.name} is not a provider output"
                )
            if resolved[2] != output.sensitive:
                raise GeneratedProviderSchemaError(
                    f"{resource.resource_type}.{resource.name}.{output.name} has incorrect sensitivity"
                )
            if (
                _schema_value_type(resolved[0]) != output.value_type
                and not (
                    _schema_value_type(resolved[0]) == "string"
                    and output.value_type
                    in {"resource_name", "aws_arn", "https_url", "aws_queue_url", "secret_reference"}
                )
            ):
                raise GeneratedProviderSchemaError(
                    f"{resource.resource_type}.{resource.name}.{output.name} has incorrect value type"
                )
    for resource in proposal.resources:
        for ref in _references(resource.arguments):
            target = by_id[ref.resource_id]
            target_schema = resource_schemas[target.resource_type]
            target_block = target_schema.get("block", {})
            target_output = _computed_output(target_block, ref.output_name)
            if target_output is None or not target_output[1]:
                raise GeneratedProviderSchemaError(
                    f"reference {ref.resource_id}.{ref.output_name} is not a provider output"
                )
            declared = {item.name: item for item in target.outputs}
            output = declared.get(ref.output_name)
            if output is None:
                raise GeneratedProviderSchemaError(
                    f"reference {ref.resource_id}.{ref.output_name} is undeclared"
                )
            if target_output[2] != output.sensitive:
                raise GeneratedProviderSchemaError(
                    f"reference {ref.resource_id}.{ref.output_name} has incorrect sensitivity"
                )
            if (
                _schema_value_type(target_output[0]) != ref.value_type
                and not (
                    _schema_value_type(target_output[0]) == "string"
                    and ref.value_type
                    in {"resource_name", "aws_arn", "https_url", "aws_queue_url", "secret_reference"}
                )
            ):
                raise GeneratedProviderSchemaError(
                    f"reference {ref.resource_id}.{ref.output_name} has incorrect value type"
                )
