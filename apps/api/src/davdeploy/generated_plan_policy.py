"""Deterministic security and ownership review for generated Terraform plans."""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from davdeploy.generated_deployment_contract import GeneratedDeploymentProposal
from davdeploy.generated_plan_inspection import (
    TerraformPlanInspectionError,
    inspect_terraform_plan,
)
from davdeploy.generated_plan_ownership import PlanOwnershipScope


class PlanPolicyVerdict(StrEnum):
    DENY = "DENY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ELIGIBLE_FOR_HUMAN_REVIEW = "ELIGIBLE_FOR_HUMAN_REVIEW"


class GeneratedPlanPolicyError(ValueError):
    """Raised only for invalid policy inputs, never including raw plan values."""


@dataclass(frozen=True)
class PlanPolicyFinding:
    code: str
    severity: str
    address: str | None
    message: str


@dataclass(frozen=True)
class GeneratedPlanPolicyResult:
    verdict: PlanPolicyVerdict
    policy_version: str
    findings: tuple[PlanPolicyFinding, ...]
    human_approval_required: bool = True


POLICY_VERSION = "nova-generated-plan-2026-11-11.6"
TRUSTED_GUARD_ADDRESS = "terraform_data.account_guard"
RISKY_PUBLIC_PORTS = frozenset(
    {
        20, 21, 22, 23, 135, 389, 445, 1433, 1434, 2375, 2376, 3000,
        3306, 3389, 4333, 5432, 5500, 5672, 5800, 5900, 6379, 6443,
        9200, 9300, 10250, 11211, 27017, 27018, 28017,
    }
)
S3_PUBLIC_BLOCK_FLAGS = (
    "block_public_acls",
    "block_public_policy",
    "ignore_public_acls",
    "restrict_public_buckets",
)
POLICY_CRITICAL_UNKNOWN_PATHS: dict[str, tuple[tuple[str, ...], ...]] = {
    "aws_s3_bucket": (("bucket",),),
    "aws_s3_bucket_acl": (("acl",),),
    "aws_s3_bucket_policy": (("policy",),),
    "aws_s3_bucket_public_access_block": tuple((flag,) for flag in S3_PUBLIC_BLOCK_FLAGS),
    "aws_s3_bucket_server_side_encryption_configuration": (
        ("rule", "apply_server_side_encryption_by_default", "sse_algorithm"),
    ),
    "aws_iam_policy": (("policy",),),
    "aws_iam_role": (("assume_role_policy",),),
    "aws_iam_role_policy": (("policy",),),
    "aws_db_instance": (
        ("publicly_accessible",),
        ("storage_encrypted",),
        ("deletion_protection",),
        ("skip_final_snapshot",),
    ),
    "aws_rds_cluster": (
        ("publicly_accessible",),
        ("storage_encrypted",),
        ("deletion_protection",),
        ("skip_final_snapshot",),
    ),
    "aws_rds_cluster_instance": (("publicly_accessible",),),
    "aws_redshift_cluster": (("publicly_accessible",), ("encrypted",)),
    "aws_ebs_volume": (("encrypted",),),
    "aws_kms_key": (("key_usage",), ("deletion_window_in_days",)),
    "aws_dynamodb_table": (
        ("server_side_encryption", "enabled"),
        ("deletion_protection_enabled",),
    ),
}


def evaluate_generated_plan_policy(
    document: dict[str, Any],
    proposal: GeneratedDeploymentProposal,
    *,
    expected_account_id: str,
    expected_region: str,
    ownership_scope: PlanOwnershipScope,
    trusted_configuration: dict[str, Any] | None = None,
) -> GeneratedPlanPolicyResult:
    """Evaluate trusted context and common AWS security risks, without output values."""
    try:
        return _evaluate(
            document,
            proposal,
            expected_account_id,
            expected_region,
            ownership_scope,
            trusted_configuration,
        )
    except (
        GeneratedPlanPolicyError,
        TerraformPlanInspectionError,
        TypeError,
        ValueError,
        RecursionError,
    ):
        return GeneratedPlanPolicyResult(
            verdict=PlanPolicyVerdict.DENY,
            policy_version=POLICY_VERSION,
            findings=(
                PlanPolicyFinding(
                    "plan_policy_input_invalid",
                    "deny",
                    None,
                    "DavDeploy could not safely verify this infrastructure plan.",
                ),
            ),
        )


def _evaluate(
    document: dict[str, Any],
    proposal: GeneratedDeploymentProposal,
    expected_account_id: str,
    expected_region: str,
    ownership_scope: PlanOwnershipScope,
    trusted_configuration: dict[str, Any] | None,
) -> GeneratedPlanPolicyResult:
    if not isinstance(ownership_scope, PlanOwnershipScope):
        raise GeneratedPlanPolicyError("trusted ownership scope is missing")
    if not re.fullmatch(r"\d{12}", expected_account_id):
        raise GeneratedPlanPolicyError("trusted account scope is invalid")
    if proposal.requirements.region != expected_region:
        raise GeneratedPlanPolicyError("trusted region does not match the proposal")
    if not _trusted_account_guard_matches(trusted_configuration, expected_account_id):
        raise GeneratedPlanPolicyError("trusted Terraform account guard is missing or mismatched")
    summary = inspect_terraform_plan(document)
    if summary.errored:
        raise GeneratedPlanPolicyError("Terraform plan reported an error")
    changed = (
        summary.create_count + summary.update_count + summary.delete_count + summary.replacement_count
    )
    if not summary.applyable and changed:
        raise GeneratedPlanPolicyError("Terraform plan cannot be applied")
    if document.get("complete") is False:
        raise GeneratedPlanPolicyError("Terraform plan is incomplete")

    findings: list[PlanPolicyFinding] = []
    _check_region(document, expected_region)
    resources = _planned_resources(document)
    _check_proposal_inventory(resources, document, proposal, findings)
    _check_resource_ownership(document, resources, ownership_scope, findings)
    _check_policy_critical_unknowns(document, findings)
    _check_s3(document, resources, findings)
    _check_iam(resources, findings, expected_account_id)
    _check_network(resources, findings)
    _check_databases(resources, findings)
    _check_ebs_volumes(resources, findings)

    if summary.delete_count or summary.replacement_count:
        findings.append(
            PlanPolicyFinding(
                "destructive_change_requires_review",
                "review",
                None,
                "This plan removes or replaces infrastructure. Review data retention and downtime before approval.",
            )
        )
    if summary.contains_sensitive_changes:
        findings.append(
            PlanPolicyFinding(
                "sensitive_change_requires_review",
                "review",
                None,
                "This plan changes sensitive settings. Review the change without exposing secret values.",
            )
        )

    ordered = tuple(sorted(set(findings), key=lambda item: (item.severity, item.code, item.address or "")))
    verdict = (
        PlanPolicyVerdict.DENY
        if any(item.severity == "deny" for item in ordered)
        else PlanPolicyVerdict.REVIEW_REQUIRED
        if ordered
        else PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    )
    return GeneratedPlanPolicyResult(verdict, POLICY_VERSION, ordered)


def _check_resource_ownership(
    document: dict[str, Any],
    resources: tuple[dict[str, Any], ...],
    ownership_scope: PlanOwnershipScope,
    findings: list[PlanPolicyFinding],
) -> None:
    """Require exact known scope tags on existing and proposed AWS resources."""
    expected_tags = ownership_scope.tags()
    changes = document.get("resource_changes")
    if not isinstance(changes, list):
        raise GeneratedPlanPolicyError("resource changes are malformed")
    by_address: dict[str, dict[str, Any]] = {}
    for item in changes:
        if not isinstance(item, dict) or not isinstance(item.get("address"), str):
            raise GeneratedPlanPolicyError("resource change is malformed")
        if item["address"] in by_address:
            raise GeneratedPlanPolicyError("resource change addresses are duplicated")
        by_address[item["address"]] = item

        mode = item.get("mode", "managed")
        if mode == "data":
            continue
        kind = item.get("type")
        if not isinstance(kind, str) or not kind.startswith("aws_"):
            continue
        if mode != "managed":
            raise GeneratedPlanPolicyError("AWS resource mode is unsupported")
        address = item["address"]
        change = item.get("change")
        actions = change.get("actions") if isinstance(change, dict) else None
        if not isinstance(actions, list) or not all(isinstance(action, str) for action in actions):
            raise GeneratedPlanPolicyError("resource change actions are malformed")
        if tuple(actions) not in {
            ("no-op",),
            ("create",),
            ("update",),
            ("delete",),
            ("delete", "create"),
            ("create", "delete"),
        }:
            raise GeneratedPlanPolicyError("AWS resource change action is unsupported")

        if "delete" in actions or "update" in actions or actions == ["no-op"]:
            _check_resource_tag_values(
                address,
                change.get("before"),
                expected_tags,
                findings,
                allow_prior_source_revision=True,
            )
        if "create" in actions or "update" in actions or actions == ["no-op"]:
            after_unknown = change.get("after_unknown")
            if not isinstance(after_unknown, dict) or not _valid_unknown_tree(after_unknown) or any(
                _path_contains_unknown(after_unknown, ("tags", key))
                for key in expected_tags
            ):
                _deny(
                    findings,
                    "resource_ownership_unknown",
                    address,
                    "DavDeploy could not verify ownership tags in the planned AWS values.",
                )
            else:
                _check_resource_tag_values(address, change.get("after"), expected_tags, findings)

    for resource in resources:
        kind = resource.get("type")
        if not isinstance(kind, str) or not kind.startswith("aws_"):
            continue
        address = resource.get("address")
        values = resource.get("values")
        if not isinstance(address, str):
            _deny(
                findings,
                "resource_ownership_unknown",
                address,
                "DavDeploy could not verify ownership tags in the planned AWS values.",
            )
            continue
        if address not in by_address:
            _deny(
                findings,
                "resource_ownership_unknown",
                address,
                "DavDeploy could not connect this planned AWS resource to ownership evidence.",
            )
        _check_resource_tag_values(address, values, expected_tags, findings)


def _check_resource_tag_values(
    address: str,
    values: Any,
    expected_tags: dict[str, str],
    findings: list[PlanPolicyFinding],
    *,
    allow_prior_source_revision: bool = False,
) -> None:
    tags = values.get("tags") if isinstance(values, dict) else None
    required_tags = (
        {
            key: value
            for key, value in expected_tags.items()
            if key != "DavDeploySourceRevision"
        }
        if allow_prior_source_revision
        else expected_tags
    )
    if not isinstance(tags, dict) or any(key not in tags for key in required_tags):
        _deny(
            findings,
            "resource_ownership_tags_missing",
            address,
            "DavDeploy could not verify which workspace owns this AWS resource.",
        )
    elif any(tags.get(key) != value for key, value in required_tags.items()):
        _deny(
            findings,
            "resource_ownership_tags_mismatch",
            address,
            "This AWS resource is not tagged for the workspace, project, and plan being reviewed.",
        )
    elif allow_prior_source_revision and not re.fullmatch(
        r"sha256:[a-f0-9]{64}", str(tags.get("DavDeploySourceRevision", ""))
    ):
        _deny(
            findings,
            "resource_ownership_tags_mismatch",
            address,
            "DavDeploy could not verify the prior source revision for this AWS resource.",
        )


def _check_policy_critical_unknowns(
    document: dict[str, Any], findings: list[PlanPolicyFinding]
) -> None:
    changes = document.get("resource_changes", [])
    if not isinstance(changes, list):
        raise GeneratedPlanPolicyError("resource changes are malformed")
    for item in changes:
        if not isinstance(item, dict):
            raise GeneratedPlanPolicyError("resource change is malformed")
        kind = item.get("type")
        paths = POLICY_CRITICAL_UNKNOWN_PATHS.get(kind, ()) if isinstance(kind, str) else ()
        if not paths:
            continue
        address = item.get("address")
        change = item.get("change")
        if not isinstance(change, dict):
            raise GeneratedPlanPolicyError("resource change is malformed")
        after_unknown = change.get("after_unknown")
        if not isinstance(after_unknown, dict) or not _valid_unknown_tree(after_unknown):
            _deny(
                findings,
                "policy_critical_unknown_structure_invalid",
                address,
                "DavDeploy could not verify safety-critical values in this plan.",
            )
            continue
        if any(_path_contains_unknown(after_unknown, path) for path in paths):
            _deny(
                findings,
                "policy_critical_value_unknown",
                address,
                "A safety-critical infrastructure setting is unknown in this plan, so it cannot be approved yet.",
            )


def _valid_unknown_tree(tree: dict[str, Any]) -> bool:
    pending: list[Any] = [tree]
    visited = 0
    while pending:
        value = pending.pop()
        visited += 1
        if visited > 10_000:
            raise GeneratedPlanPolicyError("unknown-value metadata exceeds its limit")
        if value is True:
            continue
        if isinstance(value, dict):
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
        else:
            return False
    return True


def _path_contains_unknown(tree: dict[str, Any], path: tuple[str, ...]) -> bool:
    pending: list[tuple[Any, tuple[str, ...]]] = [(tree, path)]
    visited = 0
    while pending:
        value, remaining = pending.pop()
        visited += 1
        if visited > 10_000:
            raise GeneratedPlanPolicyError("unknown-value metadata exceeds its limit")
        if value is True:
            return True
        if not remaining:
            if isinstance(value, dict):
                pending.extend((child, ()) for child in value.values())
            elif isinstance(value, list):
                pending.extend((child, ()) for child in value)
        elif isinstance(value, dict):
            pending.append((value.get(remaining[0]), remaining[1:]))
        elif isinstance(value, list):
            pending.extend((child, remaining) for child in value)
    return False


def _check_region(document: dict[str, Any], expected_region: str) -> None:
    provider_config = (
        document.get("configuration", {}).get("provider_config", {})
        if isinstance(document.get("configuration"), dict)
        else {}
    )
    aws = provider_config.get("aws") if isinstance(provider_config, dict) else None
    expressions = aws.get("expressions", {}) if isinstance(aws, dict) else {}
    region_expression = expressions.get("region") if isinstance(expressions, dict) else None
    actual_region = (
        region_expression.get("constant_value") if isinstance(region_expression, dict) else None
    )
    if actual_region != expected_region:
        raise GeneratedPlanPolicyError("AWS plan region is unknown or does not match trusted scope")


def _planned_resources(document: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    planned_values = document.get("planned_values")
    root = planned_values.get("root_module") if isinstance(planned_values, dict) else None
    if not isinstance(root, dict):
        raise GeneratedPlanPolicyError("planned resource inventory is missing")
    resources: list[dict[str, Any]] = []
    modules = [root]
    while modules:
        module = modules.pop()
        module_resources = module.get("resources", [])
        children = module.get("child_modules", [])
        if (
            not isinstance(module_resources, list)
            or any(not isinstance(item, dict) for item in module_resources)
            or not isinstance(children, list)
            or any(not isinstance(item, dict) for item in children)
        ):
            raise GeneratedPlanPolicyError("planned resource inventory is malformed")
        for item in module_resources:
            if item.get("mode", "managed") == "managed" and (
                not isinstance(item.get("address"), str)
                or not isinstance(item.get("type"), str)
                or not isinstance(item.get("values"), dict)
            ):
                raise GeneratedPlanPolicyError("planned managed resource is malformed")
        resources.extend(module_resources)
        modules.extend(children)
        if len(resources) > 2_000:
            raise GeneratedPlanPolicyError("planned resource inventory exceeds its limit")
    if len(resources) > 2_000:
        raise GeneratedPlanPolicyError("planned resource inventory exceeds its limit")
    return tuple(
        resource
        for resource in resources
        if isinstance(resource, dict) and resource.get("mode", "managed") == "managed"
    )


def _check_proposal_inventory(
    resources: tuple[dict[str, Any], ...],
    document: dict[str, Any],
    proposal: GeneratedDeploymentProposal,
    findings: list[PlanPolicyFinding],
) -> None:
    expected = {f"{item.resource_type}.{item.name}" for item in proposal.resources}
    expected.add(TRUSTED_GUARD_ADDRESS)
    actual = {item.get("address") for item in resources}
    if actual != expected:
        findings.append(
            PlanPolicyFinding(
                "plan_resource_inventory_mismatch",
                "deny",
                None,
                "The resources in this plan do not match the approved architecture proposal.",
            )
        )

    changes = document.get("resource_changes", [])
    if not isinstance(changes, list):
        raise GeneratedPlanPolicyError("resource changes are malformed")
    for item in changes:
        if not isinstance(item, dict):
            raise GeneratedPlanPolicyError("resource change is malformed")
        actions = item.get("change", {}).get("actions", []) if isinstance(item.get("change"), dict) else []
        address = item.get("address")
        if not isinstance(address, str):
            raise GeneratedPlanPolicyError("resource address is malformed")
        if address not in expected and actions not in (["no-op"], ["read"]):
            findings.append(
                PlanPolicyFinding(
                    "unproposed_resource_change",
                    "deny",
                    address[:1_024],
                    "This plan changes a resource that is not in the approved architecture proposal.",
                )
            )


def _check_s3(
    document: dict[str, Any],
    resources: tuple[dict[str, Any], ...],
    findings: list[PlanPolicyFinding],
) -> None:
    buckets = {
        item.get("values", {}).get("bucket"): item
        for item in resources
        if item.get("type") == "aws_s3_bucket" and isinstance(item.get("values"), dict)
    }
    blocks = [
        item
        for item in resources
        if item.get("type") == "aws_s3_bucket_public_access_block"
    ]
    configured_references = _configured_resource_references(document)
    for bucket_name, bucket in buckets.items():
        address = bucket.get("address")
        if not isinstance(bucket_name, str):
            _deny(findings, "s3_bucket_name_unknown", address, "The planned storage bucket name is unknown.")
            continue
        block = next(
            (
                item
                for item in blocks
                if (
                    isinstance(item.get("values"), dict)
                    and item["values"].get("bucket") == bucket_name
                )
                or _references_resource(
                    configured_references.get(item.get("address"), ()), address
                )
            ),
            None,
        )
        if block is None:
            _deny(
                findings,
                "s3_public_access_block_missing",
                address,
                "Private file storage must block public access in all four S3 settings.",
            )
        else:
            values = block.get("values", {})
            for flag in S3_PUBLIC_BLOCK_FLAGS:
                if values.get(flag) is not True:
                    _deny(
                        findings,
                        "s3_public_access_block_incomplete",
                        block.get("address"),
                        "Private file storage must block public access in all four S3 settings.",
                    )
                    break

    for item in resources:
        kind = item.get("type")
        values = item.get("values", {})
        if not isinstance(values, dict):
            continue
        address = item.get("address")
        if kind == "aws_s3_bucket_acl" and str(values.get("acl", "")).lower() in {
            "public-read",
            "public-read-write",
            "authenticated-read",
        }:
            _deny(findings, "s3_public_acl", address, "The plan grants public access through an S3 access control list.")
        if kind == "aws_s3_bucket_policy":
            policy = _json_document(values.get("policy"), findings, address)
            if policy is not None and _has_public_allow(policy):
                _deny(
                    findings,
                    "s3_public_policy_denied",
                    address,
                    "The plan grants direct public access to storage. Serve public files through a private origin instead.",
                )


def _check_iam(
    resources: tuple[dict[str, Any], ...],
    findings: list[PlanPolicyFinding],
    expected_account_id: str,
) -> None:
    for item in resources:
        kind = item.get("type")
        values = item.get("values", {})
        if not isinstance(values, dict):
            continue
        address = item.get("address")
        if kind in {"aws_iam_policy", "aws_iam_role_policy"}:
            policy = _json_document(values.get("policy"), findings, address)
            if policy is not None:
                _check_iam_permissions(policy, address, expected_account_id, findings)
        if kind == "aws_iam_role":
            trust = _json_document(values.get("assume_role_policy"), findings, address)
            if trust is not None:
                _check_role_trust(trust, address, expected_account_id, findings)
        if kind in {"aws_iam_role_policy_attachment", "aws_iam_policy_attachment"}:
            policy_arn = values.get("policy_arn")
            if not isinstance(policy_arn, str) or not policy_arn:
                _deny(
                    findings,
                    "iam_attached_policy_unknown",
                    address,
                    "The permissions attached to this role could not be verified.",
                )
            elif policy_arn.endswith(":policy/AdministratorAccess"):
                _deny(
                    findings,
                    "iam_administrator_access_attached",
                    address,
                    "The plan attaches the AWS AdministratorAccess policy to an application role.",
                )
            else:
                _review(
                    findings,
                    "iam_managed_policy_contents_unverified",
                    address,
                    "The attached managed policy contents are not present in this plan and require explicit review.",
                )


def _check_network(resources: tuple[dict[str, Any], ...], findings: list[PlanPolicyFinding]) -> None:
    for item in resources:
        kind = item.get("type")
        values = item.get("values", {})
        if not isinstance(values, dict):
            continue
        address = item.get("address")
        rules = values.get("ingress", []) if kind == "aws_security_group" else [values]
        if kind not in {"aws_security_group", "aws_security_group_rule", "aws_vpc_security_group_ingress_rule"}:
            continue
        if not isinstance(rules, list):
            _deny(findings, "security_group_ingress_unknown", address, "The plan does not make inbound network access clear.")
            continue
        for rule in rules:
            if not isinstance(rule, dict):
                _deny(findings, "security_group_ingress_unknown", address, "The plan does not make inbound network access clear.")
                continue
            if _source_is_unknown(rule):
                _deny(findings, "security_group_ingress_unknown", address, "The plan does not make inbound network access clear.")
                continue
            if not _is_public_source(rule):
                continue
            protocol = str(rule.get("ip_protocol", rule.get("protocol", "")))
            low = _integer(rule.get("from_port"))
            high = _integer(rule.get("to_port"))
            if protocol == "-1" or low is None or high is None:
                _deny(findings, "public_all_ports", address, "The plan exposes all inbound ports to the internet.")
                continue
            if any(low <= port <= high for port in RISKY_PUBLIC_PORTS):
                _deny(
                    findings,
                    "public_sensitive_port",
                    address,
                    "The plan exposes an administrative or data port to the internet.",
                )
            elif low <= 80 <= high or low <= 443 <= high:
                _review(
                    findings,
                    "public_web_ingress_review",
                    address,
                    "The plan exposes web traffic to the internet. Confirm that the service is intended to be public.",
                )
            else:
                _review(
                    findings,
                    "public_ingress_review",
                    address,
                    "The plan exposes a network port to the internet. Confirm that the access is required.",
                )


def _check_databases(resources: tuple[dict[str, Any], ...], findings: list[PlanPolicyFinding]) -> None:
    public_database_types = {
        "aws_db_instance",
        "aws_rds_cluster",
        "aws_rds_cluster_instance",
        "aws_redshift_cluster",
        "aws_dms_replication_instance",
    }
    encrypted_database_types = {"aws_db_instance", "aws_rds_cluster"}
    for item in resources:
        kind = item.get("type")
        if kind not in public_database_types:
            continue
        values = item.get("values", {})
        if not isinstance(values, dict):
            _deny(findings, "database_settings_unknown", item.get("address"), "Database security settings are not known.")
            continue
        address = item.get("address")
        if values.get("publicly_accessible") is not False:
            _deny(findings, "database_publicly_accessible", address, "The plan makes a database reachable from the public internet.")
        if kind in encrypted_database_types and values.get("storage_encrypted") is not True:
            _deny(findings, "database_encryption_required", address, "The plan does not confirm encryption at rest for this database.")
        if kind == "aws_redshift_cluster" and values.get("encrypted") is not True:
            _deny(findings, "database_encryption_required", address, "The plan does not confirm encryption at rest for this database.")


def _check_ebs_volumes(
    resources: tuple[dict[str, Any], ...], findings: list[PlanPolicyFinding]
) -> None:
    for item in resources:
        if item.get("type") != "aws_ebs_volume":
            continue
        values = item.get("values")
        if not isinstance(values, dict) or values.get("encrypted") is not True:
            _deny(
                findings,
                "ebs_encryption_required",
                item.get("address"),
                "EBS volumes must have encryption enabled.",
            )


def _json_document(value: Any, findings: list[PlanPolicyFinding], address: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        _deny(findings, "policy_document_unknown", address, "A security policy document is missing or unknown.")
        return None
    try:
        document = json.loads(value)
    except (json.JSONDecodeError, RecursionError):
        _deny(findings, "policy_document_invalid", address, "A security policy document could not be validated.")
        return None
    if not isinstance(document, dict):
        _deny(findings, "policy_document_invalid", address, "A security policy document could not be validated.")
        return None
    return document


def _configured_resource_references(document: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    configuration = document.get("configuration")
    root = configuration.get("root_module") if isinstance(configuration, dict) else None
    resources = root.get("resources") if isinstance(root, dict) else None
    if not isinstance(resources, list):
        return {}
    result: dict[str, tuple[str, ...]] = {}
    for resource in resources:
        if not isinstance(resource, dict) or not isinstance(resource.get("address"), str):
            continue
        expressions = resource.get("expressions")
        if not isinstance(expressions, dict):
            continue
        references: list[str] = []
        for expression in expressions.values():
            if isinstance(expression, dict) and isinstance(expression.get("references"), list):
                references.extend(item for item in expression["references"] if isinstance(item, str))
        result[resource["address"]] = tuple(references)
    return result


def _trusted_account_guard_matches(configuration: Any, expected_account_id: str) -> bool:
    if not isinstance(configuration, dict):
        return False
    data = configuration.get("data")
    identity = data.get("aws_caller_identity") if isinstance(data, dict) else None
    if not isinstance(identity, dict) or not isinstance(identity.get("trusted"), dict):
        return False
    resources = configuration.get("resource")
    terraform_data = resources.get("terraform_data") if isinstance(resources, dict) else None
    guard = terraform_data.get("account_guard") if isinstance(terraform_data, dict) else None
    lifecycle = guard.get("lifecycle") if isinstance(guard, dict) else None
    precondition = lifecycle.get("precondition") if isinstance(lifecycle, dict) else None
    condition = precondition.get("condition") if isinstance(precondition, dict) else None
    expected = (
        "${data.aws_caller_identity.trusted.account_id == "
        + json.dumps(expected_account_id)
        + "}"
    )
    return condition == expected


def _references_resource(references: tuple[str, ...], resource_address: Any) -> bool:
    if not isinstance(resource_address, str):
        return False
    return any(
        reference == resource_address or reference.startswith(f"{resource_address}.")
        for reference in references
    )


def _has_public_allow(policy: dict[str, Any]) -> bool:
    for statement in _statements(policy, require_resource=True, require_principal=True):
        if str(statement.get("Effect", "")).lower() != "allow":
            continue
        principal = statement.get("Principal")
        if principal == "*" or (
            isinstance(principal, dict)
            and any(value == "*" or isinstance(value, list) and "*" in value for value in principal.values())
        ):
            return True
    return False


def _check_iam_permissions(
    policy: dict[str, Any],
    address: Any,
    expected_account_id: str,
    findings: list[PlanPolicyFinding],
) -> None:
    for statement in _statements(policy, require_resource=True):
        if str(statement.get("Effect", "")).lower() != "allow":
            continue
        if "NotAction" in statement:
            _deny(
                findings,
                "iam_not_action_policy_denied",
                address,
                "An IAM allow policy uses NotAction, so its effective permissions cannot be safely bounded.",
            )
            continue
        actions = _string_list(statement.get("Action"))
        resources = _string_list(statement.get("Resource"))
        normalized_actions = {item.lower() for item in actions}
        wildcard_resource = any("*" in item or "?" in item for item in resources)
        pass_role = "iam:passrole" in normalized_actions
        if "*" in actions or "iam:*" in normalized_actions:
            _deny(
                findings,
                "iam_privileged_wildcard",
                address,
                "The plan grants broad IAM administration. Narrow the permissions to required actions and resources.",
            )
            continue
        iam_mutations = {
            action
            for action in normalized_actions
            if action.startswith("iam:")
            and not action.startswith(("iam:get", "iam:list"))
            and action != "iam:passrole"
        }
        if iam_mutations:
            _deny(
                findings,
                "iam_permission_management_denied",
                address,
                "The plan grants IAM permission-management actions that could change or delegate account access.",
            )
        if pass_role:
            if not _pass_role_is_bounded(
                resources, statement.get("Condition"), expected_account_id
            ):
                _deny(
                    findings,
                    "iam_passrole_unbounded_denied",
                    address,
                    "The plan can pass a role without an exact same-account role ARN and a literal iam:PassedToService condition.",
                )
            else:
                _review(
                    findings,
                    "iam_passrole_requires_review",
                    address,
                    "The plan passes a specific role to a named AWS service; confirm the role permissions and service use before approval.",
                )
        assume_role = "sts:assumerole" in normalized_actions
        broad_assume_role = any(
            action == "sts:*" or action.startswith("sts:assume") and action != "sts:assumerole"
            for action in normalized_actions
        )
        if broad_assume_role:
            _deny(
                findings,
                "sts_assume_role_unbounded_denied",
                address,
                "The plan uses a wildcard role-assumption action that cannot be safely bounded.",
            )
        elif assume_role:
            if wildcard_resource or not _same_account_role_resources(
                resources, expected_account_id
            ):
                _deny(
                    findings,
                    "sts_assume_role_unbounded_denied",
                    address,
                    "The plan grants role assumption outside a fixed same-account role scope.",
                )
            else:
                _review(
                    findings,
                    "sts_assume_role_requires_review",
                    address,
                    "The plan grants role assumption for a specific same-account role; review the target trust and application need.",
                )


def _same_account_role_resources(resources: tuple[str, ...], account_id: str) -> bool:
    if not resources:
        return False
    return all(
        bool(
            re.fullmatch(
                rf"arn:[a-z0-9-]+:iam::{account_id}:role/"
                r"(?:[A-Za-z0-9+=,.@_-]+/)*[A-Za-z0-9+=,.@_-]+",
                resource,
            )
        )
        for resource in resources
    )


def _pass_role_is_bounded(resources: tuple[str, ...], condition: Any, account_id: str) -> bool:
    if not _same_account_role_resources(resources, account_id) or not isinstance(condition, dict):
        return False
    if set(condition) != {"StringEquals"}:
        return False
    equals = condition.get("StringEquals")
    if not isinstance(equals, dict) or set(equals) != {"iam:PassedToService"}:
        return False
    service = equals.get("iam:PassedToService") if isinstance(equals, dict) else None
    service_names = (
        (service,)
        if isinstance(service, str)
        else tuple(service)
        if isinstance(service, list)
        else ()
    )
    return bool(service_names) and all(
        isinstance(value, str) and bool(re.fullmatch(r"[a-z0-9-]+\.amazonaws\.com(?:\.cn)?", value))
        for value in service_names
    )


def _check_role_trust(
    policy: dict[str, Any],
    address: Any,
    expected_account_id: str,
    findings: list[PlanPolicyFinding],
) -> None:
    for statement in _statements(policy, require_principal=True):
        if str(statement.get("Effect", "")).lower() != "allow":
            continue
        if "NotPrincipal" in statement:
            _deny(
                findings,
                "iam_not_principal_trust_denied",
                address,
                "An IAM role trust allow uses NotPrincipal and cannot be safely bounded.",
            )
            continue
        principal = statement.get("Principal")
        if principal == "*":
            _deny(
                findings,
                "iam_wildcard_trust",
                address,
                "The role trust policy accepts an unrestricted principal.",
            )
            continue
        principals = principal if isinstance(principal, dict) else {"AWS": principal}
        same_account_aws_principal = False
        for principal_type, raw_values in principals.items():
            values = _string_list(raw_values)
            if not values or any("*" in value or "?" in value for value in values):
                _deny(
                    findings,
                    "iam_wildcard_trust",
                    address,
                    "The role trust policy contains a wildcard or malformed principal.",
                )
                continue
            if principal_type == "Service":
                if any(
                    not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)*\.amazonaws\.com(?:\.cn)?", value)
                    for value in values
                ):
                    _deny(
                        findings,
                        "iam_unverified_trust_principal_denied",
                        address,
                        "The role trust policy contains a service principal outside the verified AWS service-name format.",
                    )
            elif principal_type == "AWS":
                if all(_is_same_account_principal(value, expected_account_id) for value in values):
                    same_account_aws_principal = True
                else:
                    _deny(
                        findings,
                        "iam_external_trust_denied",
                        address,
                        "The role trust policy grants access to an external or unverified AWS principal.",
                    )
            else:
                _deny(
                    findings,
                    "iam_unverified_trust_principal_denied",
                    address,
                    "The role trust policy uses an unverified principal type.",
                )
        if same_account_aws_principal:
            _review(
                findings,
                "iam_same_account_trust_requires_review",
                address,
                "The role trust policy accepts an AWS principal in this account; confirm that principal should assume the role.",
            )


def _is_same_account_principal(value: str, account_id: str) -> bool:
    if value == account_id or re.fullmatch(
        rf"arn:[a-z0-9-]+:iam::{account_id}:root", value
    ):
        return True
    return bool(
        re.fullmatch(
            rf"arn:[a-z0-9-]+:iam::{account_id}:(?:role|user)/"
            r"(?:[A-Za-z0-9+=,.@_-]+/)*[A-Za-z0-9+=,.@_-]+",
            value,
        )
    )


def _statements(
    policy: dict[str, Any], *, require_resource: bool = False, require_principal: bool = False
) -> tuple[dict[str, Any], ...]:
    statements = policy.get("Statement")
    if isinstance(statements, dict):
        statements = [statements]
    if not isinstance(statements, list) or not statements or any(not isinstance(item, dict) for item in statements):
        raise GeneratedPlanPolicyError("security policy statements are malformed")
    for statement in statements:
        if statement.get("Effect") not in {"Allow", "Deny"}:
            raise GeneratedPlanPolicyError("security policy effect is malformed")
        action_fields = [key for key in ("Action", "NotAction") if key in statement]
        if len(action_fields) != 1 or not _string_list(statement[action_fields[0]]):
            raise GeneratedPlanPolicyError("security policy actions are malformed")
        resource_fields = [key for key in ("Resource", "NotResource") if key in statement]
        if len(resource_fields) > 1 or require_resource and len(resource_fields) != 1:
            raise GeneratedPlanPolicyError("security policy resources are malformed")
        if resource_fields and not _string_list(statement[resource_fields[0]]):
            raise GeneratedPlanPolicyError("security policy resources are malformed")
        principal_fields = [key for key in ("Principal", "NotPrincipal") if key in statement]
        if len(principal_fields) > 1 or require_principal and len(principal_fields) != 1:
            raise GeneratedPlanPolicyError("security policy principals are malformed")
        if principal_fields and not _valid_principal(statement[principal_fields[0]]):
            raise GeneratedPlanPolicyError("security policy principals are malformed")
    return tuple(statements)


def _valid_principal(value: Any) -> bool:
    if value == "*" or isinstance(value, str) and bool(value):
        return True
    if not isinstance(value, dict) or not value:
        return False
    return all(bool(_string_list(child)) for child in value.values())


def _string_list(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    return ()


def _is_public_source(rule: dict[str, Any]) -> bool:
    sources = []
    for key in ("cidr_ipv4", "cidr_ipv6"):
        if rule.get(key):
            sources.append(rule[key])
    for key in ("cidr_blocks", "ipv6_cidr_blocks"):
        value = rule.get(key, [])
        if isinstance(value, list):
            sources.extend(value)
    for source in sources:
        if not isinstance(source, str):
            continue
        try:
            network = ipaddress.ip_network(source, strict=False)
        except ValueError:
            continue
        if network.prefixlen == 0:
            return True
    return False


def _source_is_unknown(rule: dict[str, Any]) -> bool:
    """Fail closed when Terraform cannot prove an ingress source is scoped."""
    source_keys = (
        "cidr_ipv4", "cidr_ipv6", "cidr_blocks", "ipv6_cidr_blocks",
        "prefix_list_ids", "prefix_list_id", "source_security_group_id",
        "referenced_security_group_id", "security_groups", "self",
    )
    present = [key for key in source_keys if key in rule]
    if not present:
        return True
    has_source = False
    for key in present:
        value = rule[key]
        if value is None:
            return True
        if key == "self":
            if value is not True and value is not False:
                return True
            has_source = has_source or value is True
            continue
        if value == "" or value == []:
            continue
        values = value if isinstance(value, list) else [value]
        if any(not isinstance(item, str) or not item for item in values):
            return True
        if key in {"cidr_ipv4", "cidr_ipv6", "cidr_blocks", "ipv6_cidr_blocks"}:
            try:
                for item in values:
                    ipaddress.ip_network(item, strict=False)
            except ValueError:
                return True
        has_source = True
    return not has_source


def _integer(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _deny(findings: list[PlanPolicyFinding], code: str, address: Any, message: str) -> None:
    findings.append(PlanPolicyFinding(code, "deny", _safe_address(address), message))


def _review(findings: list[PlanPolicyFinding], code: str, address: Any, message: str) -> None:
    findings.append(PlanPolicyFinding(code, "review", _safe_address(address), message))


def _safe_address(address: Any) -> str | None:
    if not isinstance(address, str) or len(address) > 1_024:
        return None
    if re.fullmatch(r"(?:module\.[A-Za-z0-9_-]+\.)*[A-Za-z][A-Za-z0-9_]*\.[A-Za-z][A-Za-z0-9_]*", address):
        return address
    return None
