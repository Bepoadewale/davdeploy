"""Versioned internal deployment-module registry.

Entries are disabled until their module-specific validation is recorded.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleImplementation:
    identifier: str
    resources: tuple[str, ...]
    terraform_root: str
    enabled: bool = False


_IMPLEMENTATIONS: dict[str, ModuleImplementation] = {
    "aws-dns-zone": ModuleImplementation("aws-dns-zone", ("aws_route53_zone", "aws_route53_record"), "modules/dns-zone"),
    "aws-acm-certificate": ModuleImplementation("aws-acm-certificate", ("aws_acm_certificate", "aws_route53_record"), "modules/acm-certificate"),
    "aws-kms-key": ModuleImplementation("aws-kms-key", ("aws_kms_key", "aws_kms_alias"), "modules/kms-key"),
    "aws-parameter-config": ModuleImplementation("aws-parameter-config", ("aws_ssm_parameter",), "modules/parameter-config"),
    "aws-feature-flags": ModuleImplementation("aws-feature-flags", ("aws_appconfig_application", "aws_appconfig_environment"), "modules/feature-flags"),
}


def module_implementations() -> tuple[ModuleImplementation, ...]:
    return tuple(_IMPLEMENTATIONS.values())
