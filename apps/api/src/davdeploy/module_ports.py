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
            raise ValueError(f"typed module output {name} has an invalid {allowed[name].value_type} value")
        normalized[name] = value
    return normalized
