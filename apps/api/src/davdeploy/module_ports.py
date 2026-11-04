"""Checked-in typed ports for the first composed AWS module families.

Port declarations describe references only. They are not resource values,
credentials, or permission to execute a module.
"""

from __future__ import annotations

from dataclasses import dataclass

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


def module_ports(module_id: str) -> ModulePorts:
    """Return the static port schema; unknown modules expose no bindable ports."""
    return _PORTS.get(module_id, ModulePorts())
