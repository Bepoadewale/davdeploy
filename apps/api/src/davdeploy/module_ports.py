"""Checked-in typed ports for the first composed AWS module families.

Port declarations describe references only. They are not resource values,
credentials, or permission to execute a module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from davdeploy.domain import ModulePort


@dataclass(frozen=True)
class ModulePorts:
    inputs: tuple[ModulePort, ...] = ()
    outputs: tuple[ModulePort, ...] = ()


def port(name: str, value_type: str, *, secret_reference_only: bool = False) -> ModulePort:
    return ModulePort(
        name=name,
        value_type=value_type,
        secret_reference_only=secret_reference_only,
    )


_PORTS: dict[str, ModulePorts] = {
    "aws-file-storage": ModulePorts(
        outputs=(
            port("bucket_name", "resource_name"),
            port("bucket_arn", "aws_arn"),
        )
    ),
    "aws-nosql-data": ModulePorts(
        outputs=(
            port("table_name", "resource_name"),
            port("table_arn", "aws_arn"),
        )
    ),
    "aws-jobs-events": ModulePorts(
        outputs=(
            port("queue_url", "aws_queue_url"),
            port("queue_arn", "aws_arn"),
        )
    ),
    "aws-secrets-config": ModulePorts(
        outputs=(port("secret_reference", "secret_reference", secret_reference_only=True),)
    ),
    "aws-serverless-api": ModulePorts(
        inputs=(
            port("uploads_bucket_name", "resource_name"),
            port("table_name", "resource_name"),
            port("work_queue_url", "aws_queue_url"),
            port("api_secret_reference", "secret_reference", secret_reference_only=True),
        ),
        outputs=(
            port("api_url", "https_url"),
            port("lambda_arn", "aws_arn"),
        ),
    ),
}

_RENDERER_OUTPUT_NAMES: dict[str, dict[str, str]] = {
    # Terraform's external names stay renderer-specific; persisted values use
    # the stable module contract exposed to dependent modules.
    "aws-serverless-api": {
        "api_endpoint": "api_url",
        "lambda_arn": "lambda_arn",
    },
    "aws-file-storage": {
        "bucket_name": "bucket_name",
        "bucket_arn": "bucket_arn",
    },
}

_RESOURCE_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}\Z")
_PARTITIONS = {"aws", "aws-us-gov", "aws-cn"}


def _valid_arn(value: str) -> bool:
    parts = value.split(":", maxsplit=5)
    if len(parts) != 6 or parts[0] != "arn" or parts[1] not in _PARTITIONS:
        return False
    service, region, account_id, resource = parts[2:]
    if not service or not resource or "*" in value or any(char.isspace() for char in value):
        return False
    if service == "s3":
        return not region and not account_id
    if not account_id.isdigit() or len(account_id) != 12:
        return False
    return bool(region) or service == "iam"


def _valid_port_value(port_contract: ModulePort, value: object) -> bool:
    if not isinstance(value, str) or not value or len(value) > 4096 or "\x00" in value:
        return False
    if port_contract.secret_reference_only:
        return value.startswith(("arn:aws:secretsmanager:", "arn:aws:ssm:")) and _valid_arn(value)
    if port_contract.value_type == "resource_name":
        return bool(_RESOURCE_NAME_PATTERN.fullmatch(value))
    if port_contract.value_type == "aws_arn":
        return _valid_arn(value)
    parsed = urlparse(value)
    if port_contract.value_type == "aws_queue_url":
        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.hostname.endswith((".amazonaws.com", ".amazonaws.com.cn"))
            and len([segment for segment in parsed.path.split("/") if segment]) >= 2
            and not parsed.username
            and not parsed.password
        )
    if port_contract.value_type == "https_url":
        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
        )
    return False


def module_ports(module_id: str) -> ModulePorts:
    """Return the static port schema; unknown modules expose no bindable ports."""
    return _PORTS.get(module_id, ModulePorts())


def validate_module_outputs(module_id: str, outputs: object) -> dict[str, str] | None:
    """Validate output values for typed modules; return None for legacy modules."""
    contracts = module_ports(module_id).outputs
    if not contracts:
        return None
    if not isinstance(outputs, dict):
        raise TypeError("typed module outputs must be an object")
    if any(not isinstance(name, str) for name in outputs):
        raise TypeError("typed module output names must be strings")
    allowed = {item.name: item for item in contracts}
    unknown = set(outputs) - set(allowed)
    if unknown:
        raise ValueError(f"typed module returned undeclared output ports: {sorted(unknown)}")
    normalized: dict[str, str] = {}
    for name, value in outputs.items():
        if not _valid_port_value(allowed[name], value):
            raise ValueError(
                f"typed module output {name} has an invalid {allowed[name].value_type} value"
            )
        normalized[name] = value
    return normalized


def validate_module_inputs(module_id: str, inputs: object) -> dict[str, str]:
    """Validate resolved reference values against a module's declared inputs."""
    if not isinstance(inputs, dict) or any(not isinstance(name, str) for name in inputs):
        raise TypeError("typed module inputs must be an object")
    contracts = {item.name: item for item in module_ports(module_id).inputs}
    unknown = set(inputs) - set(contracts)
    if unknown:
        raise ValueError(f"typed module has undeclared input ports: {sorted(unknown)}")
    normalized: dict[str, str] = {}
    for name, value in inputs.items():
        contract = contracts[name]
        if not _valid_port_value(contract, value):
            raise ValueError(
                f"typed module input {name} has an invalid {contract.value_type} value"
            )
        normalized[name] = value
    return normalized


def normalize_renderer_outputs(module_id: str, renderer_outputs: object) -> dict[str, str] | None:
    """Convert a checked-in renderer's Terraform JSON outputs to typed ports.

    Sensitive Terraform outputs are rejected even if the output name happens
    to match a reference port. Consumers receive only the non-secret string
    values declared by the module contract.
    """
    contracts = module_ports(module_id).outputs
    if not contracts:
        return None
    name_mapping = _RENDERER_OUTPUT_NAMES.get(module_id)
    if name_mapping is None:
        raise ValueError("typed module has no checked-in renderer output mapping")
    if not isinstance(renderer_outputs, dict) or any(
        not isinstance(name, str) for name in renderer_outputs
    ):
        raise TypeError("renderer outputs must be a JSON object")
    if set(renderer_outputs) != set(name_mapping):
        raise ValueError("renderer outputs do not match the checked-in output mapping")

    normalized: dict[str, str] = {}
    for renderer_name, port_name in name_mapping.items():
        record = renderer_outputs[renderer_name]
        if (
            not isinstance(record, dict)
            or set(record) - {"value", "type", "sensitive"}
            or "value" not in record
            or record.get("type", "string") != "string"
            or record.get("sensitive", False) is not False
            or not isinstance(record["value"], str)
        ):
            raise ValueError("renderer output is malformed or marked sensitive")
        normalized[port_name] = record["value"]
    return validate_module_outputs(module_id, normalized)
