"""Trusted ownership metadata for generated, plan-only Terraform work."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID


class PlanOwnershipError(ValueError):
    """Ownership cannot be represented or verified safely for this plan."""


# The top-level Terraform resource is not the only AWS object these resource
# types can create. Until their nested or propagated tags are independently
# checked in plan output, a tag on the parent resource is insufficient proof.
RESOURCE_TYPES_WITH_UNPROVEN_CHILD_OWNERSHIP = frozenset(
    {
        "aws_autoscaling_group",
        "aws_batch_compute_environment",
        "aws_cloudformation_stack",
        "aws_ec2_fleet",
        "aws_ecs_service",
        "aws_eks_node_group",
        "aws_instance",
        "aws_lambda_function",
        "aws_launch_configuration",
        "aws_launch_template",
        "aws_spot_fleet_request",
    }
)
UNTAGGABLE_RESOURCE_TYPES_WITH_STATE_OWNERSHIP = frozenset({"aws_apigatewayv2_route"})


@dataclass(frozen=True)
class PlanOwnershipScope:
    """Server-owned identifiers bound to one exact plan request.

    These values must come from an authorized workspace/revision lookup. They
    must never be populated from Nova's proposal or customer-provided tags.
    Raw tenant identifiers are not written to customer AWS resource tags.
    Their SHA-256 values are stable correlators, not anonymization. ``plan_id``
    is a trusted immutable platform identifier, not the hash of the saved
    Terraform plan that this configuration produces.

    Tags are mutable metadata for ownership correlation and recovery. They are
    not an authorization boundary; hosted lifecycle must use tenant-scoped
    remote-state keys, tenant authorization and IAM isolation.
    """

    organization_id: str
    workspace_id: str
    project_id: str
    plan_id: str
    revision_id: str
    environment_id: str | None = None

    def __post_init__(self) -> None:
        for name in ("organization_id", "workspace_id", "project_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or value != value.strip() or len(value) > 160:
                raise PlanOwnershipError(f"trusted {name} is invalid")
        if self.environment_id is not None and (
            not isinstance(self.environment_id, str)
            or not self.environment_id
            or self.environment_id != self.environment_id.strip()
            or len(self.environment_id) > 160
        ):
            raise PlanOwnershipError("trusted environment_id is invalid")
        for name in ("plan_id", "revision_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value or value != value.strip() or len(value) > 160:
                raise PlanOwnershipError(f"trusted {name} is invalid")

    @staticmethod
    def _identifier_tag(value: str) -> str:
        return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()

    def tags(self) -> dict[str, str]:
        """Return the exact reserved ownership tags for this trusted scope."""
        result = {
            "DavDeployManagedBy": "davdeploy",
            "DavDeployOrganization": self._identifier_tag(self.organization_id),
            "DavDeployWorkspace": self._identifier_tag(self.workspace_id),
            "DavDeployProject": self._identifier_tag(self.project_id),
            "DavDeployPlanId": self._identifier_tag(self.plan_id),
            "DavDeploySourceRevision": self._identifier_tag(self.revision_id),
        }
        if self.environment_id is not None:
            result["DavDeployEnvironment"] = self._identifier_tag(self.environment_id)
        return result

    def plan_id_sha256(self) -> str:
        return hashlib.sha256(self.plan_id.encode("utf-8")).hexdigest()

    def scope_sha256(self) -> str:
        encoded = json.dumps(self.tags(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class UntaggedResourceOwnershipRecord:
    """Exact Terraform address recorded as owned by one trusted remote state."""

    address: str
    resource_type: str


def inject_trusted_ownership_tags(
    configuration: dict[str, Any],
    provider_schema_document: dict[str, Any],
    ownership_scope: PlanOwnershipScope,
    *,
    remote_state_id: str | None = None,
    remote_state_scope_sha256: str | None = None,
    expected_remote_state_scope_sha256: str | None = None,
) -> tuple[UntaggedResourceOwnershipRecord, ...]:
    """Tag supported AWS resources and record exact state-owned exceptions.

    A resource without a safely writable ``map(string)`` tags argument is
    accepted only when a trusted, tenant-scoped state identity has already
    been verified. Its exact Terraform address is then bound to that state in
    the saved-plan manifest. Child-expanding types remain rejected below.
    """
    provider_schemas = provider_schema_document.get("provider_schemas")
    provider = (
        provider_schemas.get("registry.terraform.io/hashicorp/aws")
        if isinstance(provider_schemas, dict)
        else None
    )
    schemas = provider.get("resource_schemas") if isinstance(provider, dict) else None
    resources = configuration.get("resource")
    if not isinstance(schemas, dict) or not isinstance(resources, dict):
        raise PlanOwnershipError("pinned AWS tagging schema is unavailable")

    reserved_tags = ownership_scope.tags()
    aws_resources = 0
    untaggable: list[UntaggedResourceOwnershipRecord] = []
    for resource_type, instances in resources.items():
        if not isinstance(resource_type, str) or not resource_type.startswith("aws_"):
            continue
        if resource_type in RESOURCE_TYPES_WITH_UNPROVEN_CHILD_OWNERSHIP:
            raise PlanOwnershipError(
                f"AWS resource type {resource_type} has child resources without verified ownership tags"
            )
        if not isinstance(instances, dict):
            raise PlanOwnershipError("generated AWS resource configuration is malformed")
        resource_schema = schemas.get(resource_type)
        block = resource_schema.get("block") if isinstance(resource_schema, dict) else None
        attributes = block.get("attributes") if isinstance(block, dict) else None
        tags_schema = attributes.get("tags") if isinstance(attributes, dict) else None
        tags_type = tags_schema.get("type") if isinstance(tags_schema, dict) else None
        writable = isinstance(tags_schema, dict) and (
            tags_schema.get("optional") is True or tags_schema.get("required") is True
        )
        if (
            tags_type != ["map", "string"]
            or not writable
            or tags_schema.get("sensitive") is True
        ):
            if resource_type not in UNTAGGABLE_RESOURCE_TYPES_WITH_STATE_OWNERSHIP:
                raise PlanOwnershipError(
                    f"AWS resource type {resource_type} has no supported ownership mechanism"
                )
            if (
                remote_state_id is None
                or remote_state_scope_sha256 is None
                or remote_state_scope_sha256 != expected_remote_state_scope_sha256
            ):
                raise PlanOwnershipError(
                    f"AWS resource type {resource_type} has no safely writable ownership tags or verified remote state"
                )
            try:
                if str(UUID(remote_state_id)) != remote_state_id.lower():
                    raise ValueError
            except (AttributeError, TypeError, ValueError):
                raise PlanOwnershipError("trusted remote-state identity is invalid") from None
            if not re.fullmatch(r"[a-f0-9]{64}", remote_state_scope_sha256):
                raise PlanOwnershipError("trusted remote-state scope is invalid")
            for instance_name, arguments in instances.items():
                if not isinstance(instance_name, str) or not isinstance(arguments, dict):
                    raise PlanOwnershipError("generated AWS resource configuration is malformed")
                if "tags" in arguments:
                    raise PlanOwnershipError("proposal supplied tags for an untaggable AWS resource")
                untaggable.append(
                    UntaggedResourceOwnershipRecord(
                        address=f"{resource_type}.{instance_name}",
                        resource_type=resource_type,
                    )
                )
                aws_resources += 1
            continue
        for instance_name, arguments in instances.items():
            if not isinstance(instance_name, str) or not isinstance(arguments, dict):
                raise PlanOwnershipError("generated AWS resource configuration is malformed")
            current = arguments.get("tags", {})
            if not isinstance(current, dict) or any(not isinstance(key, str) for key in current):
                raise PlanOwnershipError("generated AWS resource tags are malformed")
            if any(key.casefold().startswith("davdeploy") for key in current):
                raise PlanOwnershipError("proposal attempted to set reserved ownership tags")
            arguments["tags"] = {**current, **reserved_tags}
            aws_resources += 1

    if aws_resources == 0:
        raise PlanOwnershipError("generated plan contains no verifiable AWS resources")
    return tuple(sorted(untaggable, key=lambda item: item.address))
