"""Typed boundary for untrusted Nova infrastructure proposals.

This contract does not authorize Terraform execution.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

GENERATED_OUTPUT_PATH_PATTERN = (
    r"^[a-z][a-z0-9_]{0,62}(?:\[0\])?(?:\.[a-z][a-z0-9_]{0,62}(?:\[0\])?)*$"
)


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ResourceReference(StrictContract):
    kind: str = Field(pattern=r"^resource_reference$")
    resource_id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,62}$")
    output_name: str = Field(pattern=GENERATED_OUTPUT_PATH_PATTERN)
    value_type: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")


class GeneratedOutput(StrictContract):
    name: str = Field(pattern=GENERATED_OUTPUT_PATH_PATTERN)
    value_type: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    sensitive: bool = False


class GeneratedResource(StrictContract):
    resource_id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,62}$")
    resource_type: str = Field(pattern=r"^aws_[a-z0-9_]{2,120}$")
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    arguments: dict[str, Any]
    depends_on: tuple[str, ...] = ()
    outputs: tuple[GeneratedOutput, ...] = ()
    rationale: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_arguments_and_outputs(self) -> GeneratedResource:
        names = [output.name for output in self.outputs]
        if len(names) != len(set(names)):
            raise ValueError("generated output names must be unique")
        for output in self.outputs:
            if output.value_type == "secret_reference" and not _is_supported_secret_output(
                self, output.name
            ):
                raise ValueError(
                    "secret_reference outputs must identify an RDS-managed master secret ARN"
                )
        forbidden = {
            "provider", "provisioner", "connection", "access_key",
            "secret_key", "session_token", "private_key", "password",
            "user_data", "backend", "required_providers",
        }

        def is_secret_value_field(
            key: str, value: Any, *, parent_key: str | None = None
        ) -> bool:
            """Recognize credential values without mistaking policy controls for them."""
            normalized = "".join(character for character in key.casefold() if character.isalnum())
            normalized_parent = (
                "".join(character for character in parent_key.casefold() if character.isalnum())
                if parent_key is not None
                else None
            )
            if type(value) is bool:
                return False
            if normalized in {
                "passwordpolicy",
                "softwaretokenmfaconfiguration",
                "tokenvalidityunits",
            }:
                return False
            if normalized_parent == "tokenvalidityunits" and normalized in {
                "accesstoken",
                "idtoken",
                "refreshtoken",
            }:
                return False
            if isinstance(value, (int, float)) and normalized.endswith(
                ("validity", "validitydays", "validityminutes", "validityseconds")
            ):
                return False
            return any(
                marker in normalized
                for marker in (
                    "password",
                    "passwd",
                    "secret",
                    "credential",
                    "apikey",
                    "token",
                    "accesstoken",
                    "refreshtoken",
                    "idtoken",
                    "authtoken",
                    "sessiontoken",
                    "privatekey",
                    "accesskey",
                    "bearertoken",
                )
            ) or normalized in {"authorization", "proxyauthorization", "httpauthorization"}

        def is_secret_reference(value: Any) -> bool:
            if not isinstance(value, dict) or value.get("kind") != "resource_reference":
                return False
            reference = ResourceReference.model_validate(value)
            return reference.value_type == "secret_reference"

        def visit(value: Any, *, parent_key: str | None = None) -> None:
            if isinstance(value, str) and any(
                marker in value.lower()
                for marker in (chr(36) + "{", "%{", "file(", "templatefile(")
            ):
                raise ValueError("model-authored Terraform expressions are forbidden")
            if isinstance(value, dict):
                for key, child in value.items():
                    if not isinstance(key, str) or key.casefold() in forbidden:
                        raise ValueError("generated arguments contain a forbidden field")
                    if is_secret_value_field(key, child, parent_key=parent_key) and not is_secret_reference(child):
                        raise ValueError(
                            "credential and secret fields must use a typed secret_reference"
                        )
                    if isinstance(child, dict) and child.get("kind") == "resource_reference":
                        ResourceReference.model_validate(child)
                    visit(child, parent_key=key)

                # Terraform commonly represents environment variables as
                # {name: "API_TOKEN", value: ...}. Their generic `value` key
                # otherwise hides the sensitive meaning from the key check.
                variable_name = value.get("name")
                if (
                    isinstance(variable_name, str)
                    and "value" in value
                    and is_secret_value_field(
                        variable_name, value["value"], parent_key=parent_key
                    )
                    and not is_secret_reference(value["value"])
                ):
                    raise ValueError(
                        "credential and secret fields must use a typed secret_reference"
                    )
            elif isinstance(value, (list, tuple)):
                for child in value:
                    visit(child, parent_key=parent_key)
        visit(self.arguments)
        proposed_tags = self.arguments.get("tags")
        if isinstance(proposed_tags, dict) and any(
            isinstance(key, str) and key.casefold().startswith("davdeploy")
            for key in proposed_tags
        ):
            raise ValueError("generated arguments cannot set reserved DavDeploy ownership tags")
        return self


class WorkloadRequirements(StrictContract):
    region: str = Field(min_length=1, max_length=64)
    monthly_budget_minor: int | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    data_residency: tuple[str, ...] = ()
    availability: str | None = Field(default=None, max_length=500)
    downtime_tolerance: str | None = Field(default=None, max_length=500)


class HealthAssertion(StrictContract):
    kind: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    target_resource_id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,62}$")
    description: str = Field(min_length=1, max_length=500)


class RecoveryRequirement(StrictContract):
    backup_required: bool = False
    recovery_point_objective_minutes: int | None = Field(default=None, ge=0)
    recovery_time_objective_minutes: int | None = Field(default=None, ge=0)
    destructive_change_notes: str | None = Field(default=None, max_length=1000)


class CostAssumption(StrictContract):
    resource_id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,62}$")
    description: str = Field(min_length=1, max_length=500)
    source: str = Field(min_length=1, max_length=300)
    captured_at: str = Field(min_length=1, max_length=80)


class GeneratedDeploymentProposal(StrictContract):
    contract_version: str = Field(pattern=r"^1\.[0-9]+$")
    source_revision: str = Field(min_length=1, max_length=160)
    context_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    resources: tuple[GeneratedResource, ...] = Field(min_length=1, max_length=200)
    requirements: WorkloadRequirements
    health_assertions: tuple[HealthAssertion, ...] = Field(default=(), max_length=64)
    recovery: RecoveryRequirement = Field(default_factory=RecoveryRequirement)
    cost_assumptions: tuple[CostAssumption, ...] = Field(default=(), max_length=200)
    assumptions: tuple[str, ...] = Field(default=(), max_length=64)
    limitations: tuple[str, ...] = Field(default=(), max_length=64)

    @model_validator(mode="after")
    def validate_graph(self) -> GeneratedDeploymentProposal:
        if any(
            not isinstance(item, str) or not item.strip() or len(item) > 500
            for item in (*self.assumptions, *self.limitations)
        ):
            raise ValueError("proposal assumptions and limitations must be bounded text")
        by_id: dict[str, GeneratedResource] = {}
        addresses: set[tuple[str, str]] = set()
        for resource in self.resources:
            if resource.resource_id in by_id:
                raise ValueError("resource IDs must be unique")
            address = (resource.resource_type, resource.name)
            if address in addresses:
                raise ValueError("Terraform resource addresses must be unique")
            by_id[resource.resource_id] = resource
            addresses.add(address)
        graph: dict[str, set[str]] = {}
        for resource in self.resources:
            dependencies = set(resource.depends_on)
            if resource.resource_id in dependencies or not dependencies.issubset(by_id):
                raise ValueError("dependencies must reference other declared resources")
            graph[resource.resource_id] = dependencies
            for path, _reference in _secret_reference_paths(resource.arguments):
                allowed_lambda_secret_arn = (
                    resource.resource_type == "aws_lambda_function"
                    and len(path) == 4
                    and path[0:3] == ("environment", 0, "variables")
                    and isinstance(path[3], str)
                    and path[3].endswith("_SECRET_ARN")
                )
                if not allowed_lambda_secret_arn:
                    raise ValueError(
                        "secret_reference values may only populate a Lambda secret ARN environment variable"
                    )
            for ref in _references(resource.arguments):
                target = by_id.get(ref.resource_id)
                if target is None:
                    raise ValueError("references must target a declared resource")
                declared = {item.name: item.value_type for item in target.outputs}
                if declared.get(ref.output_name) != ref.value_type:
                    raise ValueError("reference must match a declared output type")
                graph[resource.resource_id].add(ref.resource_id)
        visiting: set[str] = set()
        visited: set[str] = set()
        def visit(resource_id: str) -> None:
            if resource_id in visiting:
                raise ValueError("resource dependency graph must be acyclic")
            if resource_id in visited:
                return
            visiting.add(resource_id)
            for dependency in graph[resource_id]:
                visit(dependency)
            visiting.remove(resource_id)
            visited.add(resource_id)
        for resource_id in graph:
            visit(resource_id)
        ids = set(by_id)
        if any(item.target_resource_id not in ids for item in self.health_assertions):
            raise ValueError("health assertions must target declared resources")
        if any(item.resource_id not in ids for item in self.cost_assumptions):
            raise ValueError("cost assumptions must target declared resources")
        return self


def _references(value: Any) -> list[ResourceReference]:
    if isinstance(value, dict):
        if value.get("kind") == "resource_reference":
            return [ResourceReference.model_validate(value)]
        return [ref for child in value.values() for ref in _references(child)]
    if isinstance(value, (list, tuple)):
        return [ref for child in value for ref in _references(child)]
    return []


def _secret_reference_paths(
    value: Any, path: tuple[str | int, ...] = ()
) -> list[tuple[tuple[str | int, ...], ResourceReference]]:
    if isinstance(value, dict):
        if value.get("kind") == "resource_reference":
            reference = ResourceReference.model_validate(value)
            return [(path, reference)] if reference.value_type == "secret_reference" else []
        return [
            item
            for key, child in value.items()
            for item in _secret_reference_paths(child, (*path, key))
        ]
    if isinstance(value, (list, tuple)):
        return [
            item
            for index, child in enumerate(value)
            for item in _secret_reference_paths(child, (*path, index))
        ]
    return []


def _is_supported_secret_output(resource: GeneratedResource, path: str) -> bool:
    """Allow only known RDS-managed master secret ARN outputs, never values."""
    return (
        resource.resource_type in {"aws_db_instance", "aws_rds_cluster"}
        and path == "master_user_secret[0].secret_arn"
        and resource.arguments.get("manage_master_user_password") is True
    )


def terraform_resource_blocks(
    proposal: GeneratedDeploymentProposal,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Translate validated references into Terraform resource expressions."""
    by_id = {resource.resource_id: resource for resource in proposal.resources}

    def encode(value: Any) -> Any:
        if isinstance(value, dict) and value.get("kind") == "resource_reference":
            reference = ResourceReference.model_validate(value)
            target = by_id[reference.resource_id]
            return chr(36) + "{" + target.resource_type + "." + target.name + "." + reference.output_name + "}"
        if isinstance(value, dict):
            return {key: encode(child) for key, child in value.items()}
        if isinstance(value, list):
            return [encode(child) for child in value]
        return value

    result: dict[str, dict[str, dict[str, Any]]] = {}
    for resource in proposal.resources:
        block = encode(resource.arguments)
        if resource.depends_on:
            block["depends_on"] = [
                f"{by_id[dependency].resource_type}.{by_id[dependency].name}"
                for dependency in resource.depends_on
            ]
        result.setdefault(resource.resource_type, {})[resource.name] = block
    return result
