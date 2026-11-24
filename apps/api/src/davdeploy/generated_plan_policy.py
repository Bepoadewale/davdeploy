"""Deterministic security and ownership review for generated Terraform plans."""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from fnmatch import fnmatchcase
from typing import Any

from davdeploy.generated_deployment_contract import GeneratedDeploymentProposal
from davdeploy.generated_plan_inspection import (
    TerraformPlanInspectionError,
    inspect_terraform_plan,
)
from davdeploy.generated_plan_ownership import (
    UNTAGGABLE_RESOURCE_TYPES_WITH_STATE_OWNERSHIP,
    PlanOwnershipScope,
    UntaggedResourceOwnershipRecord,
)


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


POLICY_VERSION = "nova-generated-plan-2026-11-24.4"
TRUSTED_GUARD_ADDRESS = "terraform_data.account_guard"
SECRET_VALUE_READ_ACTIONS = (
    "secretsmanager:GetSecretValue",
    "secretsmanager:BatchGetSecretValue",
)
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
S3_SUPPORTED_DEFAULT_ENCRYPTION_ALGORITHMS = frozenset(
    {"AES256", "aws:kms", "aws:kms:dsse"}
)
POLICY_CRITICAL_UNKNOWN_PATHS: dict[str, tuple[tuple[str, ...], ...]] = {
    "aws_s3_bucket": (("bucket",),),
    "aws_s3_bucket_acl": (("acl",),),
    "aws_s3_bucket_policy": (("policy",),),
    "aws_s3_bucket_public_access_block": tuple((flag,) for flag in S3_PUBLIC_BLOCK_FLAGS),
    "aws_s3_bucket_server_side_encryption_configuration": (
        ("rule",),
        ("rule", "apply_server_side_encryption_by_default", "sse_algorithm"),
    ),
    "aws_s3_bucket_ownership_controls": (
        ("rule",),
        ("rule", "object_ownership"),
    ),
    "aws_iam_policy": (("policy",),),
    "aws_iam_role": (("assume_role_policy",),),
    "aws_iam_role_policy": (("policy",),),
    "aws_ecr_repository": (
        ("image_tag_mutability",),
        ("image_scanning_configuration", "scan_on_push"),
        ("encryption_configuration", "encryption_type"),
        ("force_delete",),
    ),
    "aws_sqs_queue_policy": (("policy",),),
    "aws_sqs_queue": (
        ("sqs_managed_sse_enabled",),
        ("visibility_timeout_seconds",),
        ("message_retention_seconds",),
        ("redrive_policy",),
        ("redrive_allow_policy",),
    ),
    "aws_lambda_function": (("timeout",),),
    "aws_lambda_permission": (
        ("action",),
        ("function_name",),
        ("function_url_auth_type",),
        ("principal",),
        ("principal_org_id",),
        ("source_account",),
        ("source_arn",),
    ),
    "aws_sfn_state_machine": (("definition",), ("role_arn",), ("type",)),
    "aws_apigatewayv2_route": (("authorization_type",),),
    "aws_db_instance": (
        ("publicly_accessible",),
        ("storage_encrypted",),
        ("deletion_protection",),
        ("skip_final_snapshot",),
        ("backup_retention_period",),
    ),
    "aws_rds_cluster": (
        ("publicly_accessible",),
        ("storage_encrypted",),
        ("deletion_protection",),
        ("skip_final_snapshot",),
        ("backup_retention_period",),
    ),
    "aws_rds_cluster_instance": (("publicly_accessible",),),
    "aws_redshift_cluster": (("publicly_accessible",), ("encrypted",)),
    "aws_ebs_volume": (("encrypted",),),
    "aws_instance": (
        ("metadata_options", "http_endpoint"),
        ("metadata_options", "http_tokens"),
    ),
    "aws_launch_template": (
        ("metadata_options", "http_endpoint"),
        ("metadata_options", "http_tokens"),
    ),
    "aws_launch_configuration": (
        ("metadata_options", "http_endpoint"),
        ("metadata_options", "http_tokens"),
    ),
    "aws_ec2_instance_metadata_defaults": (("http_tokens",),),
    "aws_kms_key": (
        ("customer_master_key_spec",),
        ("key_usage",),
        ("enable_key_rotation",),
        ("deletion_window_in_days",),
        ("multi_region",),
    ),
    "aws_ssm_parameter": (("type",), ("tier",), ("key_id",)),
    "aws_acm_certificate": (
        ("domain_name",),
        ("validation_method",),
        ("key_algorithm",),
        ("options", "export"),
    ),
    "aws_route53_zone": (("name",), ("vpc",), ("force_destroy",)),
    "aws_appconfig_application": (("name",),),
    "aws_appconfig_environment": (("name",),),
    "aws_opensearch_domain": (
        ("engine_version",),
        ("cluster_config", "instance_type"),
        ("cluster_config", "instance_count"),
        ("cluster_config", "zone_awareness_enabled"),
        ("ebs_options", "ebs_enabled"),
        ("ebs_options", "volume_type"),
        ("ebs_options", "volume_size"),
        ("encrypt_at_rest", "enabled"),
        ("node_to_node_encryption", "enabled"),
        ("domain_endpoint_options", "enforce_https"),
        ("domain_endpoint_options", "tls_security_policy"),
    ),
    "aws_dynamodb_table": (
        ("name",),
        ("hash_key",),
        ("billing_mode",),
        ("server_side_encryption", "enabled"),
        ("deletion_protection_enabled",),
        ("point_in_time_recovery", "enabled"),
        ("point_in_time_recovery", "recovery_period_in_days"),
    ),
    "aws_kinesis_stream": (
        ("name",),
        ("shard_count",),
        ("retention_period",),
        ("encryption_type",),
        ("kms_key_id",),
        ("stream_mode_details", "stream_mode"),
    ),
    "aws_efs_file_system": (
        ("encrypted",),
        ("performance_mode",),
        ("throughput_mode",),
    ),
    "aws_elasticache_replication_group": (
        ("replication_group_id",),
        ("engine",),
        ("engine_version",),
        ("node_type",),
        ("num_cache_clusters",),
        ("port",),
        ("auth_token",),
        ("auth_token_update_strategy",),
        ("subnet_group_name",),
        ("at_rest_encryption_enabled",),
        ("transit_encryption_enabled",),
        ("transit_encryption_mode",),
        ("automatic_failover_enabled",),
        ("multi_az_enabled",),
    ),
    "aws_security_group": (("ingress",),),
    "aws_security_group_rule": (
        ("type",),
        ("protocol",),
        ("from_port",),
        ("to_port",),
        ("cidr_blocks",),
        ("ipv6_cidr_blocks",),
        ("prefix_list_ids",),
        ("source_security_group_id",),
        ("self",),
    ),
    "aws_vpc_security_group_ingress_rule": (
        ("ip_protocol",),
        ("from_port",),
        ("to_port",),
        ("cidr_ipv4",),
        ("cidr_ipv6",),
        ("prefix_list_id",),
        ("referenced_security_group_id",),
    ),
    "aws_cloudfront_distribution": (
        ("default_cache_behavior", "viewer_protocol_policy"),
        ("ordered_cache_behavior", "viewer_protocol_policy"),
        ("origin", "custom_origin_config", "origin_protocol_policy"),
        ("origin", "custom_origin_config", "origin_ssl_protocols"),
    ),
    "aws_network_acl": (("ingress",),),
    "aws_default_network_acl": (("ingress",),),
    "aws_network_acl_rule": (
        ("egress",),
        ("protocol",),
        ("rule_action",),
        ("cidr_block",),
        ("ipv6_cidr_block",),
        ("from_port",),
        ("to_port",),
        ("icmp_type",),
        ("icmp_code",),
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
    untagged_resource_ownership: tuple[UntaggedResourceOwnershipRecord, ...] = (),
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
            untagged_resource_ownership,
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
    untagged_resource_ownership: tuple[UntaggedResourceOwnershipRecord, ...],
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
    _validate_untagged_resource_ownership(
        untagged_resource_ownership, resources, proposal, findings
    )
    _check_resource_ownership(
        document, resources, ownership_scope, findings, untagged_resource_ownership
    )
    _check_policy_critical_unknowns(document, findings)
    _check_s3(document, resources, expected_region, findings, expected_account_id)
    _check_cloudfront_viewer_tls(resources, findings)
    _check_cloudfront_origin_tls(resources, findings)
    _check_ecr_repositories(resources, findings)
    _check_kms_keys(resources, findings)
    _check_ssm_parameters(resources, findings)
    _check_opensearch_domains(resources, findings)
    _check_acm_certificates(resources, findings)
    _check_route53_zones(resources, findings)
    _check_appconfig_bindings(document, resources, findings)
    _check_sqs_queue_encryption(resources, findings)
    _check_sqs_queue_policies(resources, findings, expected_account_id)
    _check_sns_sqs_subscription_bindings(
        resources, findings, expected_account_id, expected_region
    )
    _check_eventbridge_sqs_bindings(
        resources, findings, expected_account_id, expected_region
    )
    _check_sqs_delivery_contract(
        document, resources, findings, expected_account_id, expected_region
    )
    _check_step_functions_role_scope(
        document, resources, findings, expected_account_id, expected_region
    )
    _check_lambda_permissions(resources, findings)
    _check_api_gateway_routes(document, resources, proposal, findings)
    _check_iam(resources, findings, expected_account_id)
    _check_network(resources, findings)
    _check_databases(resources, findings)
    _check_dynamodb_table_safety(resources, findings)
    _check_dynamodb_recovery(resources, findings)
    _check_kinesis_streams(resources, findings)
    _check_efs_file_systems(resources, findings)
    _check_efs_nfs_ingress(resources, findings)
    _check_efs_mount_target_binding(document, resources, findings)
    _check_elasticache_replication_groups(document, resources, findings)
    _check_redis_ingress(document, resources, findings)
    _check_rds_final_snapshot_changes(document, findings)
    _check_ebs_volumes(resources, findings)
    _check_instance_metadata(document, resources, findings)
    _check_autoscaling_groups(document, resources, findings)

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
    untagged_resource_ownership: tuple[UntaggedResourceOwnershipRecord, ...],
) -> None:
    """Require exact scope tags or exact state ownership for untaggable resources."""
    expected_tags = ownership_scope.tags()
    state_owned = {item.address: item for item in untagged_resource_ownership}
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

        ownership_record = state_owned.get(address)
        if ownership_record is not None:
            if ownership_record.resource_type != kind:
                _deny(
                    findings,
                    "resource_ownership_record_mismatch",
                    address,
                    "DavDeploy could not match this untaggable resource to its trusted ownership record.",
                )
            elif any(
                isinstance(change.get(key), dict) and "tags" in change[key]
                for key in ("before", "after")
            ):
                _deny(
                    findings,
                    "resource_ownership_record_conflict",
                    address,
                    "DavDeploy found conflicting ownership data for this infrastructure resource.",
                )
            continue

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
        ownership_record = state_owned.get(address)
        if ownership_record is not None:
            if ownership_record.resource_type != kind:
                _deny(
                    findings,
                    "resource_ownership_record_mismatch",
                    address,
                    "DavDeploy could not match this untaggable resource to its trusted ownership record.",
                )
            elif isinstance(values, dict) and "tags" in values:
                _deny(
                    findings,
                    "resource_ownership_record_conflict",
                    address,
                    "DavDeploy found conflicting ownership data for this infrastructure resource.",
                )
            continue
        _check_resource_tag_values(address, values, expected_tags, findings)


def _validate_untagged_resource_ownership(
    records: tuple[UntaggedResourceOwnershipRecord, ...],
    resources: tuple[dict[str, Any], ...],
    proposal: GeneratedDeploymentProposal,
    findings: list[PlanPolicyFinding],
) -> None:
    if not isinstance(records, tuple) or len(records) > 2_000:
        raise GeneratedPlanPolicyError("untaggable resource ownership records are invalid")
    proposal_addresses = {
        f"{item.resource_type}.{item.name}": item.resource_type for item in proposal.resources
    }
    planned_addresses = {
        item.get("address"): item.get("type")
        for item in resources
        if isinstance(item.get("address"), str)
    }
    seen: set[str] = set()
    for record in records:
        resource_name = (
            record.address.removeprefix(record.resource_type + ".")
            if isinstance(record, UntaggedResourceOwnershipRecord)
            and isinstance(record.address, str)
            and isinstance(record.resource_type, str)
            else ""
        )
        if (
            not isinstance(record, UntaggedResourceOwnershipRecord)
            or record.resource_type not in UNTAGGABLE_RESOURCE_TYPES_WITH_STATE_OWNERSHIP
            or not resource_name
            or record.address != record.resource_type + "." + resource_name
            or proposal_addresses.get(record.address) != record.resource_type
            or planned_addresses.get(record.address) != record.resource_type
            or record.address in seen
        ):
            _deny(
                findings,
                "resource_ownership_record_invalid",
                record.address if isinstance(record, UntaggedResourceOwnershipRecord) else None,
                "DavDeploy could not verify the exact address of an untaggable AWS resource.",
            )
            continue
        seen.add(record.address)


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
    expected_region: str,
    findings: list[PlanPolicyFinding],
    expected_account_id: str,
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
            if policy is not None:
                if _has_public_allow(policy):
                    _deny(
                        findings,
                        "s3_public_policy_denied",
                        address,
                        "The plan grants direct public access to storage. Serve public files through a private origin instead.",
                    )
                elif _has_unverified_resource_policy_principal(
                    policy, expected_account_id
                ):
                    _deny(
                        findings,
                        "s3_unverified_policy_principal_denied",
                        address,
                        "The storage policy names an external or unverified principal.",
                    )
                elif _has_not_action_allow(policy):
                    _deny(
                        findings,
                        "s3_not_action_policy_denied",
                        address,
                        "The storage policy uses an inverse action scope that cannot be safely bounded.",
                    )
                elif _has_unbounded_resource_allow(policy):
                    _deny(
                        findings,
                        "s3_not_resource_policy_denied",
                        address,
                        "The storage policy uses an inverse resource scope that cannot be safely bounded.",
                    )
                elif _has_unbounded_resource_arn_allow(policy, "s3"):
                    _deny(
                        findings,
                        "s3_resource_arn_unbounded",
                        address,
                        "The storage policy resource must use a complete, bounded S3 ARN.",
                    )

    _check_s3_secure_transport(document, resources, expected_region, findings)
    _check_s3_default_encryption(document, resources, findings)
    _check_s3_ownership_controls(document, resources, findings)


def _check_s3_default_encryption(
    document: dict[str, Any],
    resources: tuple[dict[str, Any], ...],
    findings: list[PlanPolicyFinding],
) -> None:
    buckets = [item for item in resources if item.get("type") == "aws_s3_bucket"]
    configurations = [
        item
        for item in resources
        if item.get("type") == "aws_s3_bucket_server_side_encryption_configuration"
    ]
    configured_references = _configured_resource_references(document)
    checked_addresses: set[str] = set()

    for bucket in buckets:
        address = bucket.get("address")
        values = bucket.get("values")
        bucket_name = values.get("bucket") if isinstance(values, dict) else None
        if not isinstance(bucket_name, str) or not bucket_name:
            _deny(
                findings,
                "s3_default_encryption_bucket_unknown",
                address,
                "DavDeploy could not verify the bucket identity for its encryption configuration.",
            )
            continue

        matches = []
        for configuration in configurations:
            configuration_values = configuration.get("values")
            configured_bucket = (
                configuration_values.get("bucket")
                if isinstance(configuration_values, dict)
                else None
            )
            references_bucket = _references_resource(
                configured_references.get(configuration.get("address"), ()), address
            )
            if configured_bucket == bucket_name or (
                configured_bucket is None and references_bucket
            ):
                matches.append(configuration)

        if not matches:
            _deny(
                findings,
                "s3_default_encryption_configuration_missing",
                address,
                "Every planned S3 bucket must have a same-plan default-encryption configuration.",
            )
            continue
        if len(matches) != 1:
            checked_addresses.update(
                configuration.get("address")
                for configuration in matches
                if isinstance(configuration.get("address"), str)
            )
            _deny(
                findings,
                "s3_default_encryption_configuration_ambiguous",
                address,
                "DavDeploy could not identify exactly one default-encryption configuration for this S3 bucket.",
            )
            continue

        configuration = matches[0]
        configuration_address = configuration.get("address")
        if isinstance(configuration_address, str):
            checked_addresses.add(configuration_address)
        _check_s3_default_encryption_configuration(
            configuration, configuration_address, findings
        )

    for configuration in configurations:
        address = configuration.get("address")
        if isinstance(address, str) and address in checked_addresses:
            continue
        _deny(
            findings,
            "s3_default_encryption_bucket_unknown",
            address,
            "A planned S3 encryption configuration is not bound to exactly one planned bucket.",
        )


def _check_s3_default_encryption_configuration(
    configuration: dict[str, Any],
    address: Any,
    findings: list[PlanPolicyFinding],
) -> None:
    values = configuration.get("values")
    rules = values.get("rule") if isinstance(values, dict) else None
    if not isinstance(rules, list) or len(rules) != 1 or not isinstance(rules[0], dict):
        _deny(
            findings,
            "s3_default_encryption_configuration_incomplete",
            address,
            "S3 default encryption must have exactly one complete rule.",
        )
        return

    default_settings = rules[0].get("apply_server_side_encryption_by_default")
    if (
        not isinstance(default_settings, list)
        or len(default_settings) != 1
        or not isinstance(default_settings[0], dict)
    ):
        _deny(
            findings,
            "s3_default_encryption_configuration_incomplete",
            address,
            "S3 default encryption must declare exactly one default encryption mode.",
        )
        return

    algorithm = default_settings[0].get("sse_algorithm")
    if not isinstance(algorithm, str) or not algorithm:
        _deny(
            findings,
            "s3_default_encryption_algorithm_unknown",
            address,
            "The S3 default encryption algorithm is missing or unknown.",
        )
        return
    if algorithm not in S3_SUPPORTED_DEFAULT_ENCRYPTION_ALGORITHMS:
        _deny(
            findings,
            "s3_default_encryption_algorithm_unsupported",
            address,
            "The S3 default encryption algorithm is not supported by this policy.",
        )


def _check_s3_ownership_controls(
    document: dict[str, Any],
    resources: tuple[dict[str, Any], ...],
    findings: list[PlanPolicyFinding],
) -> None:
    buckets = [item for item in resources if item.get("type") == "aws_s3_bucket"]
    controls = [
        item
        for item in resources
        if item.get("type") == "aws_s3_bucket_ownership_controls"
    ]
    configured_references = _configured_resource_references(document)
    checked_addresses: set[str] = set()

    for bucket in buckets:
        address = bucket.get("address")
        values = bucket.get("values")
        bucket_name = values.get("bucket") if isinstance(values, dict) else None
        if not isinstance(bucket_name, str) or not bucket_name:
            _deny(
                findings,
                "s3_ownership_bucket_unknown",
                address,
                "DavDeploy could not verify the bucket identity for its ownership controls.",
            )
            continue

        matches = []
        for control in controls:
            control_values = control.get("values")
            control_bucket = (
                control_values.get("bucket") if isinstance(control_values, dict) else None
            )
            references_bucket = _references_resource(
                configured_references.get(control.get("address"), ()), address
            )
            if control_bucket == bucket_name or (
                control_bucket is None and references_bucket
            ):
                matches.append(control)

        if not matches:
            _deny(
                findings,
                "s3_ownership_controls_missing",
                address,
                "Every planned S3 bucket must explicitly enforce bucket-owner-enforced object ownership.",
            )
            continue
        if len(matches) != 1:
            checked_addresses.update(
                control.get("address")
                for control in matches
                if isinstance(control.get("address"), str)
            )
            _deny(
                findings,
                "s3_ownership_controls_ambiguous",
                address,
                "DavDeploy could not identify exactly one ownership-controls resource for this S3 bucket.",
            )
            continue

        control = matches[0]
        control_address = control.get("address")
        if isinstance(control_address, str):
            checked_addresses.add(control_address)
        _check_s3_ownership_control_configuration(control, control_address, findings)

    for control in controls:
        address = control.get("address")
        if isinstance(address, str) and address in checked_addresses:
            continue
        _deny(
            findings,
            "s3_ownership_bucket_unknown",
            address,
            "A planned S3 ownership-controls resource is not bound to exactly one planned bucket.",
        )


def _check_s3_ownership_control_configuration(
    control: dict[str, Any],
    address: Any,
    findings: list[PlanPolicyFinding],
) -> None:
    values = control.get("values")
    rules = values.get("rule") if isinstance(values, dict) else None
    if not isinstance(rules, list) or len(rules) != 1 or not isinstance(rules[0], dict):
        _deny(
            findings,
            "s3_ownership_controls_incomplete",
            address,
            "S3 ownership controls must have exactly one complete rule.",
        )
        return

    object_ownership = rules[0].get("object_ownership")
    if not isinstance(object_ownership, str) or not object_ownership:
        _deny(
            findings,
            "s3_object_ownership_unknown",
            address,
            "The S3 object ownership setting is missing or unknown.",
        )
        return
    if object_ownership != "BucketOwnerEnforced":
        _deny(
            findings,
            "s3_object_ownership_unsupported",
            address,
            "S3 buckets must disable ACLs and enforce bucket ownership of all objects.",
        )


def _check_s3_secure_transport(
    document: dict[str, Any],
    resources: tuple[dict[str, Any], ...],
    expected_region: str,
    findings: list[PlanPolicyFinding],
) -> None:
    buckets = [item for item in resources if item.get("type") == "aws_s3_bucket"]
    policies = [
        item for item in resources if item.get("type") == "aws_s3_bucket_policy"
    ]
    configured_references = _configured_resource_references(document)
    checked_policy_addresses: set[str] = set()

    for bucket in buckets:
        address = bucket.get("address")
        values = bucket.get("values")
        bucket_name = values.get("bucket") if isinstance(values, dict) else None
        bucket_arn = _s3_bucket_arn(
            values.get("arn") if isinstance(values, dict) else None,
            bucket_name,
            expected_region,
        )
        if bucket_arn is None:
            _deny(
                findings,
                "s3_secure_transport_bucket_unknown",
                address,
                "DavDeploy could not verify the identity of an S3 bucket requiring a transport policy.",
            )
            continue

        matches = []
        for policy in policies:
            policy_values = policy.get("values")
            policy_bucket = (
                policy_values.get("bucket") if isinstance(policy_values, dict) else None
            )
            policy_bucket_arn = _s3_bucket_arn(
                policy_bucket, policy_bucket, expected_region
            )
            policy_references_bucket = _references_resource(
                configured_references.get(policy.get("address"), ()), address
            )
            if policy_bucket_arn == bucket_arn or (
                policy_bucket is None and policy_references_bucket
            ):
                matches.append(policy)

        if not matches:
            _deny(
                findings,
                "s3_secure_transport_policy_missing",
                address,
                "Every planned S3 bucket must have a same-plan policy that requires secure transport.",
            )
            continue
        if len(matches) != 1:
            for policy in matches:
                policy_address = policy.get("address")
                if isinstance(policy_address, str):
                    checked_policy_addresses.add(policy_address)
            _deny(
                findings,
                "s3_secure_transport_policy_ambiguous",
                address,
                "DavDeploy could not identify exactly one transport policy for this S3 bucket.",
            )
            continue

        policy = matches[0]
        policy_address = policy.get("address")
        if isinstance(policy_address, str):
            checked_policy_addresses.add(policy_address)
        policy_values = policy.get("values")
        policy_document = (
            _json_document(policy_values.get("policy"), findings, policy_address)
            if isinstance(policy_values, dict)
            else None
        )
        if policy_document is not None and not _s3_policy_requires_secure_transport(
            policy_document, bucket_arn
        ):
            _deny(
                findings,
                "s3_secure_transport_policy_incomplete",
                policy_address,
                "The S3 bucket policy must deny non-TLS S3 requests to the bucket and its objects while allowing AWS service principals.",
            )

    for policy in policies:
        address = policy.get("address")
        if isinstance(address, str) and address in checked_policy_addresses:
            continue
        values = policy.get("values")
        bucket_identity = values.get("bucket") if isinstance(values, dict) else None
        bucket_arn = _s3_bucket_arn(
            bucket_identity, bucket_identity, expected_region
        )
        if bucket_arn is None:
            _deny(
                findings,
                "s3_secure_transport_bucket_unknown",
                address,
                "DavDeploy could not verify the bucket targeted by an S3 transport policy.",
            )
            continue
        policy_document = (
            _json_document(values.get("policy"), findings, address)
            if isinstance(values, dict)
            else None
        )
        if policy_document is not None and not _s3_policy_requires_secure_transport(
            policy_document, bucket_arn
        ):
            _deny(
                findings,
                "s3_secure_transport_policy_incomplete",
                address,
                "The S3 bucket policy must deny non-TLS S3 requests to the bucket and its objects while allowing AWS service principals.",
            )


def _s3_bucket_arn(identity: Any, bucket_name: Any, region: str) -> str | None:
    partition = _aws_partition_for_region(region)
    if partition is None:
        return None
    if isinstance(identity, str):
        match = re.fullmatch(r"arn:([a-z0-9-]+):s3:::([a-z0-9.-]{3,63})", identity)
        if match:
            if match.group(1) != partition:
                return None
            if (
                isinstance(bucket_name, str)
                and re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket_name)
                and match.group(2) != bucket_name
            ):
                return None
            return identity
    if not isinstance(bucket_name, str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket_name
    ):
        return None
    return f"arn:{partition}:s3:::{bucket_name}"


def _aws_partition_for_region(region: str) -> str | None:
    if region.startswith("cn-"):
        return "aws-cn"
    if region.startswith("us-gov-"):
        return "aws-us-gov"
    if region.startswith("us-iso-"):
        return "aws-iso"
    if region.startswith("us-isob-"):
        return "aws-iso-b"
    if region.startswith("eu-isoe-"):
        return "aws-iso-e"
    if region.startswith("us-isof-"):
        return "aws-iso-f"
    if region.startswith(("us-", "af-", "ap-", "ca-", "eu-", "me-", "sa-", "il-", "mx-", "eusc-")):
        return "aws"
    return None


def _s3_policy_requires_secure_transport(
    policy: dict[str, Any], bucket_arn: str
) -> bool:
    required_resources = {bucket_arn, f"{bucket_arn}/*"}
    try:
        statements = _statements(policy, require_resource=True, require_principal=True)
    except GeneratedPlanPolicyError:
        return False
    covered_resources: set[str] = set()
    required_condition = {
        "aws:SecureTransport": "false",
        "aws:PrincipalIsAWSService": "false",
    }
    for statement in statements:
        if (
            statement.get("Effect") != "Deny"
            or statement.get("Principal") != "*"
            or _string_list(statement.get("Action")) != ("s3:*",)
            or statement.get("Condition") != {"Bool": required_condition}
        ):
            continue
        covered_resources.update(_string_list(statement.get("Resource")))
    return required_resources <= covered_resources


def _check_cloudfront_viewer_tls(
    resources: tuple[dict[str, Any], ...], findings: list[PlanPolicyFinding]
) -> None:
    secure_policies = {"https-only", "redirect-to-https"}
    behavior_fields = (
        ("default_cache_behavior", True),
        ("ordered_cache_behavior", False),
    )
    for item in resources:
        if item.get("type") != "aws_cloudfront_distribution":
            continue
        address = item.get("address")
        values = item.get("values")
        if not isinstance(values, dict):
            _deny(
                findings,
                "cloudfront_viewer_behavior_unknown",
                address,
                "The plan does not make CloudFront viewer protocol settings clear.",
            )
            continue
        for field, required in behavior_fields:
            behaviors = values.get(field)
            if not isinstance(behaviors, list) or (required and len(behaviors) != 1):
                _deny(
                    findings,
                    "cloudfront_viewer_behavior_unknown",
                    address,
                    "The plan does not make every CloudFront cache behavior clear.",
                )
                continue
            for behavior in behaviors:
                if not isinstance(behavior, dict):
                    _deny(
                        findings,
                        "cloudfront_viewer_behavior_unknown",
                        address,
                        "The plan does not make every CloudFront cache behavior clear.",
                    )
                    continue
                viewer_policy = behavior.get("viewer_protocol_policy")
                if isinstance(viewer_policy, str) and viewer_policy in secure_policies:
                    continue
                if viewer_policy == "allow-all":
                    _deny(
                        findings,
                        "cloudfront_cleartext_viewer_access",
                        address,
                        "A CloudFront cache behavior allows viewers to use cleartext HTTP.",
                    )
                else:
                    _deny(
                        findings,
                        "cloudfront_viewer_protocol_unknown",
                        address,
                        "The plan does not make a CloudFront viewer protocol policy clear.",
                    )


def _check_cloudfront_origin_tls(
    resources: tuple[dict[str, Any], ...], findings: list[PlanPolicyFinding]
) -> None:
    secure_origin_policies = {"https-only", "match-viewer"}
    for item in resources:
        if item.get("type") != "aws_cloudfront_distribution":
            continue
        address = item.get("address")
        values = item.get("values")
        origins = values.get("origin") if isinstance(values, dict) else None
        if not isinstance(origins, list) or not origins:
            _deny(
                findings,
                "cloudfront_origin_settings_unknown",
                address,
                "The plan does not make CloudFront origin protocol settings clear.",
            )
            continue

        for origin in origins:
            if not isinstance(origin, dict):
                _deny(
                    findings,
                    "cloudfront_origin_settings_unknown",
                    address,
                    "The plan does not make every CloudFront origin protocol setting clear.",
                )
                continue

            custom_configs = origin.get("custom_origin_config")
            s3_configs = origin.get("s3_origin_config")
            custom_absent = custom_configs is None or custom_configs == []
            s3_absent = s3_configs is None or s3_configs == []
            if (
                isinstance(custom_configs, list)
                and len(custom_configs) == 1
                and s3_absent
            ):
                custom = custom_configs[0]
                if not isinstance(custom, dict):
                    _deny(
                        findings,
                        "cloudfront_origin_settings_unknown",
                        address,
                        "The plan does not make a CloudFront custom origin protocol setting clear.",
                    )
                    continue
                protocol_policy = custom.get("origin_protocol_policy")
                ssl_protocols = custom.get("origin_ssl_protocols")
                if protocol_policy == "http-only":
                    _deny(
                        findings,
                        "cloudfront_cleartext_origin_access",
                        address,
                        "A CloudFront custom origin can receive requests over cleartext HTTP.",
                    )
                elif (
                    not isinstance(protocol_policy, str)
                    or protocol_policy not in secure_origin_policies
                ):
                    _deny(
                        findings,
                        "cloudfront_origin_protocol_unknown",
                        address,
                        "The plan does not make a CloudFront custom origin protocol policy clear.",
                    )
                if ssl_protocols != ["TLSv1.2"]:
                    _deny(
                        findings,
                        "cloudfront_origin_tls_protocol_weak_or_unknown",
                        address,
                        "A CloudFront custom origin must allow only TLS 1.2.",
                    )
                continue

            if (
                isinstance(s3_configs, list)
                and len(s3_configs) == 1
                and custom_absent
            ):
                if not isinstance(s3_configs[0], dict):
                    _deny(
                        findings,
                        "cloudfront_origin_settings_unknown",
                        address,
                        "The plan does not make a CloudFront S3 origin setting clear.",
                    )
                continue

            _deny(
                findings,
                "cloudfront_origin_settings_unknown",
                address,
                "The plan uses an unsupported or ambiguous CloudFront origin configuration.",
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

    _check_network_acls(resources, findings)


def _check_network_acls(
    resources: tuple[dict[str, Any], ...], findings: list[PlanPolicyFinding]
) -> None:
    for item in resources:
        kind = item.get("type")
        values = item.get("values")
        address = item.get("address")
        if not isinstance(values, dict):
            if kind in {"aws_network_acl", "aws_default_network_acl", "aws_network_acl_rule"}:
                _deny(
                    findings,
                    "network_acl_ingress_unknown",
                    address,
                    "The plan does not make network ACL inbound access clear.",
                )
            continue

        if kind in {"aws_network_acl", "aws_default_network_acl"}:
            rules = values.get("ingress", [])
            if not isinstance(rules, list):
                _deny(
                    findings,
                    "network_acl_ingress_unknown",
                    address,
                    "The plan does not make network ACL inbound access clear.",
                )
                continue
            for rule in rules:
                if not isinstance(rule, dict):
                    _deny(
                        findings,
                        "network_acl_ingress_unknown",
                        address,
                        "The plan does not make network ACL inbound access clear.",
                    )
                    continue
                _check_network_acl_ingress(rule, address, findings)
        elif kind == "aws_network_acl_rule":
            egress = values.get("egress")
            if not isinstance(egress, bool):
                _deny(
                    findings,
                    "network_acl_ingress_unknown",
                    address,
                    "The plan does not make network ACL direction clear.",
                )
            elif not egress:
                _check_network_acl_ingress(values, address, findings)


def _check_network_acl_ingress(
    rule: dict[str, Any], address: Any, findings: list[PlanPolicyFinding]
) -> None:
    action = rule.get("rule_action")
    if action == "deny":
        return
    if action != "allow":
        _deny(
            findings,
            "network_acl_ingress_unknown",
            address,
            "The plan does not make network ACL rule behavior clear.",
        )
        return
    if _network_acl_source_is_unknown(rule):
        _deny(
            findings,
            "network_acl_ingress_unknown",
            address,
            "The plan does not make network ACL inbound access clear.",
        )
        return
    source = {
        "cidr_blocks": [rule["cidr_block"]] if rule.get("cidr_block") else [],
        "ipv6_cidr_blocks": [rule["ipv6_cidr_block"]] if rule.get("ipv6_cidr_block") else [],
    }
    if not _is_public_source(source):
        return

    protocol = rule.get("protocol")
    if isinstance(protocol, int) and not isinstance(protocol, bool):
        protocol = str(protocol)
    if not isinstance(protocol, str) or not protocol:
        _deny(
            findings,
            "network_acl_ingress_unknown",
            address,
            "The plan does not make network ACL protocol exposure clear.",
        )
        return
    if protocol == "-1":
        _deny(
            findings,
            "network_acl_public_all_protocols_denied",
            address,
            "The plan allows all inbound network protocols from a public address range.",
        )
        return

    low, high = _network_acl_ports(rule)
    if protocol in {"6", "17", "tcp", "udp"}:
        if low is None or high is None or low > high:
            _deny(
                findings,
                "network_acl_ingress_unknown",
                address,
                "The plan does not make public TCP or UDP ports clear.",
            )
            return
        if any(low <= port <= high for port in RISKY_PUBLIC_PORTS):
            _deny(
                findings,
                "network_acl_public_sensitive_port_denied",
                address,
                "The plan exposes an administrative or data port through a public network ACL.",
            )
            return
        if low <= 80 <= high or low <= 443 <= high:
            _review(
                findings,
                "network_acl_public_web_ingress_review",
                address,
                "The plan allows public web traffic through a network ACL. Confirm that the service is intended to be public.",
            )
        else:
            _review(
                findings,
                "network_acl_public_ingress_review",
                address,
                "The plan allows public traffic through a network ACL. Confirm that the access is required.",
            )
        return

    _review(
        findings,
        "network_acl_public_ingress_review",
        address,
        "The plan allows a non-TCP/UDP protocol from a public address range. Confirm that the access is required.",
    )


def _network_acl_source_is_unknown(rule: dict[str, Any]) -> bool:
    keys = ("cidr_block", "ipv6_cidr_block")
    present = [key for key in keys if key in rule]
    if not present:
        return True
    found = False
    for key in present:
        value = rule[key]
        if value is None:
            continue
        if value == "":
            continue
        if not isinstance(value, str):
            return True
        try:
            ipaddress.ip_network(value, strict=False)
        except ValueError:
            return True
        found = True
    return not found


def _network_acl_ports(rule: dict[str, Any]) -> tuple[int | None, int | None]:
    port_range = rule.get("port_range")
    if port_range is not None:
        if not isinstance(port_range, dict):
            return None, None
        return _integer(port_range.get("from")), _integer(port_range.get("to"))
    return _integer(rule.get("from_port")), _integer(rule.get("to_port"))


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
        if kind == "aws_db_instance":
            retention = values.get("backup_retention_period")
            if not isinstance(retention, int) or isinstance(retention, bool) or not 0 <= retention <= 35:
                _deny(
                    findings,
                    "database_backup_retention_invalid",
                    address,
                    "The plan does not confirm a valid RDS backup retention period.",
                )
            elif retention == 0:
                _review(
                    findings,
                    "database_backup_retention_disabled",
                    address,
                    "Automated backups and point-in-time recovery are disabled for this database. Confirm that this data-retention choice is intended.",
                )
        if kind == "aws_rds_cluster":
            retention = values.get("backup_retention_period")
            if not isinstance(retention, int) or isinstance(retention, bool) or not 1 <= retention <= 35:
                _deny(
                    findings,
                    "database_backup_retention_invalid",
                    address,
                    "The plan does not confirm a valid RDS cluster backup retention period.",
                )
        if kind == "aws_redshift_cluster" and values.get("encrypted") is not True:
            _deny(findings, "database_encryption_required", address, "The plan does not confirm encryption at rest for this database.")


def _check_rds_final_snapshot_changes(
    document: dict[str, Any], findings: list[PlanPolicyFinding]
) -> None:
    changes = document.get("resource_changes")
    if not isinstance(changes, list):
        raise GeneratedPlanPolicyError("resource changes are malformed")
    for item in changes:
        if not isinstance(item, dict) or item.get("type") not in {"aws_db_instance", "aws_rds_cluster"}:
            continue
        change_value = item.get("change")
        if not isinstance(change_value, dict):
            raise GeneratedPlanPolicyError("resource change is malformed")
        actions = change_value.get("actions")
        if not isinstance(actions, list) or not all(isinstance(action, str) for action in actions):
            raise GeneratedPlanPolicyError("resource change actions are malformed")
        # Terraform represents replacement as delete + create.
        if "delete" not in actions:
            continue
        before = change_value.get("before")
        address = item.get("address")
        if not isinstance(before, dict) or not isinstance(before.get("skip_final_snapshot"), bool):
            _deny(
                findings,
                "rds_final_snapshot_setting_unknown",
                address,
                "DavDeploy could not verify whether this database change preserves a final snapshot.",
            )
            continue
        if before["skip_final_snapshot"]:
            _review(
                findings,
                "rds_final_snapshot_skipped",
                address,
                "This database will be removed or replaced without a final snapshot. Confirm that the data can be discarded.",
            )
        elif not isinstance(before.get("final_snapshot_identifier"), str) or not before["final_snapshot_identifier"].strip():
            _deny(
                findings,
                "rds_final_snapshot_identifier_missing",
                address,
                "A final snapshot is required for this database change, but its identifier is missing.",
            )


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


def _check_instance_metadata(
    document: dict[str, Any],
    resources: tuple[dict[str, Any], ...],
    findings: list[PlanPolicyFinding],
) -> None:
    planned_launch_templates = {
        item.get("address"): item
        for item in resources
        if item.get("type") == "aws_launch_template"
        and isinstance(item.get("address"), str)
    }
    configured_resources = _configured_resources(document)
    for item in resources:
        kind = item.get("type")
        if kind == "aws_ec2_instance_metadata_defaults":
            values = item.get("values")
            if not isinstance(values, dict) or values.get("http_tokens") != "required":
                _deny(
                    findings,
                    "instance_metadata_defaults_require_v2",
                    item.get("address"),
                    "Regional EC2 metadata defaults must require Instance Metadata Service Version 2 tokens.",
                )
            continue
        if kind == "aws_eks_node_group":
            address = item.get("address")
            values = item.get("values")
            launch_templates = (
                values.get("launch_template") if isinstance(values, dict) else None
            )
            configured = configured_resources.get(address)
            expressions = configured.get("expressions") if isinstance(configured, dict) else None
            launch_template_expression = (
                expressions.get("launch_template") if isinstance(expressions, dict) else None
            )
            references = (
                launch_template_expression.get("references")
                if isinstance(launch_template_expression, dict)
                else None
            )
            referenced_templates = {
                template_address
                for reference in references or ()
                if isinstance(reference, str)
                for template_address in planned_launch_templates
                if _reference_targets_resource(reference, template_address, "aws_launch_template")
            }
            references_are_bound = bool(references) and all(
                isinstance(reference, str)
                and any(
                    _reference_targets_resource(
                        reference, template_address, "aws_launch_template"
                    )
                    for template_address in planned_launch_templates
                )
                for reference in references
            )
            if (
                not isinstance(address, str)
                or not isinstance(launch_templates, list)
                or len(launch_templates) != 1
                or not isinstance(launch_templates[0], dict)
                or len(referenced_templates) != 1
                or not references_are_bound
            ):
                _deny(
                    findings,
                    "eks_node_metadata_unverifiable",
                    address,
                    "Managed EKS nodes require one verifiable same-plan launch template so their metadata settings can be checked.",
                )
            continue
        if kind not in {
            "aws_instance",
            "aws_launch_template",
            "aws_launch_configuration",
        }:
            continue
        address = item.get("address")
        values = item.get("values")
        options = values.get("metadata_options") if isinstance(values, dict) else None
        if isinstance(options, list):
            options = options[0] if len(options) == 1 else None
        if not isinstance(options, dict):
            _deny(
                findings,
                "instance_metadata_options_unknown",
                address,
                "The plan does not make instance metadata settings clear.",
            )
            continue

        endpoint = options.get("http_endpoint")
        tokens = options.get("http_tokens")
        if endpoint == "disabled":
            continue
        if endpoint != "enabled" or tokens != "required":
            _deny(
                findings,
                "instance_metadata_v2_required",
                address,
                "Instances with metadata access must require Instance Metadata Service Version 2 tokens.",
            )


def _check_autoscaling_groups(
    document: dict[str, Any],
    resources: tuple[dict[str, Any], ...],
    findings: list[PlanPolicyFinding],
) -> None:
    """Allow only a small, predictable ASG backed by a same-plan launch template."""
    templates = {
        item.get("address"): item
        for item in resources
        if item.get("type") == "aws_launch_template"
        and isinstance(item.get("address"), str)
    }
    configured = _configured_resources(document)
    for group in resources:
        if group.get("type") != "aws_autoscaling_group":
            continue
        address = group.get("address")
        values = group.get("values")
        if not isinstance(address, str) or not isinstance(values, dict):
            _deny(
                findings,
                "autoscaling_capacity_unknown",
                address,
                "Auto Scaling capacity must be known and within the supported limit.",
            )
            continue

        minimum = values.get("min_size")
        desired = values.get("desired_capacity")
        maximum = values.get("max_size")
        capacities = (minimum, desired, maximum)
        if (
            any(not isinstance(value, int) or isinstance(value, bool) for value in capacities)
            or minimum < 0
            or minimum > desired
            or desired > maximum
            or maximum > 3
        ):
            _deny(
                findings,
                "autoscaling_capacity_out_of_bounds",
                address,
                "Auto Scaling capacity must satisfy 0 <= minimum <= desired <= maximum <= 3.",
            )

        group_config = configured.get(address)
        expressions = group_config.get("expressions") if isinstance(group_config, dict) else None
        template_expression = (
            expressions.get("launch_template") if isinstance(expressions, dict) else None
        )
        references = (
            template_expression.get("references")
            if isinstance(template_expression, dict)
            else None
        )
        template_addresses = {
            template_address
            for reference in references or ()
            if isinstance(reference, str)
            for template_address in templates
            if _reference_targets_resource(
                reference, template_address, "aws_launch_template"
            )
        }
        template_references = [
            reference
            for reference in references or ()
            if isinstance(reference, str)
            and any(
                _reference_targets_resource(reference, template_address, "aws_launch_template")
                for template_address in templates
            )
        ]
        version_bound = any(
            ".latest_version" in reference for reference in template_references
        )
        references_are_bound = bool(references) and len(template_references) == len(references)
        launch_templates = values.get("launch_template")
        template_config = (
            launch_templates[0]
            if isinstance(launch_templates, list)
            and len(launch_templates) == 1
            and isinstance(launch_templates[0], dict)
            else None
        )
        template_version = template_config.get("version") if template_config else None
        version_is_fixed = (
            isinstance(template_version, int)
            and not isinstance(template_version, bool)
            and template_version > 0
        ) or (isinstance(template_version, str) and template_version.isdigit())
        if (
            len(template_addresses) != 1
            or not references_are_bound
            or not version_bound
            or not version_is_fixed
        ):
            _deny(
                findings,
                "autoscaling_launch_template_unverifiable",
                address,
                "Auto Scaling requires one same-plan launch template with a fixed version from that template.",
            )
            continue

        if values.get("launch_configuration") not in (None, "") or values.get(
            "mixed_instances_policy"
        ) not in (None, [], {}):
            _deny(
                findings,
                "autoscaling_profile_unsupported",
                address,
                "Launch configurations and mixed-instance Auto Scaling profiles are unsupported.",
            )

        template = templates[next(iter(template_addresses))]
        template_values = template.get("values")
        template_values = template_values if isinstance(template_values, dict) else {}
        image_id = template_values.get("image_id")
        if not isinstance(image_id, str) or not re.fullmatch(r"ami-[0-9a-fA-F]{8,17}", image_id):
            _deny(
                findings,
                "autoscaling_ami_unknown",
                template.get("address"),
                "The Auto Scaling launch template must use a known AMI ID.",
            )
        if template_values.get("instance_type") != "t3.micro":
            _deny(
                findings,
                "autoscaling_instance_type_unsupported",
                template.get("address"),
                "The supported Auto Scaling profile uses t3.micro instances.",
            )
        if template_values.get("instance_market_options") not in (None, [], {}):
            _deny(
                findings,
                "autoscaling_profile_unsupported",
                template.get("address"),
                "Spot market options are unsupported by the bounded Auto Scaling profile.",
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


def _configured_resources(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    configuration = document.get("configuration")
    root = configuration.get("root_module") if isinstance(configuration, dict) else None
    if not isinstance(root, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    modules = [root]
    while modules:
        module = modules.pop()
        resources = module.get("resources", [])
        module_calls = module.get("module_calls", {})
        if (
            not isinstance(resources, list)
            or any(not isinstance(resource, dict) for resource in resources)
            or not isinstance(module_calls, dict)
            or any(not isinstance(call, dict) for call in module_calls.values())
        ):
            return {}
        for resource in resources:
            address = resource.get("address")
            if not isinstance(address, str):
                continue
            if address in result:
                return {}
            result[address] = resource
        for call in module_calls.values():
            child_module = call.get("module")
            if not isinstance(child_module, dict):
                return {}
            modules.append(child_module)
        if len(result) > 2_000:
            return {}
    return result


def _reference_targets_resource(reference: str, address: str, resource_type: str) -> bool:
    if reference == address or reference.startswith(f"{address}."):
        return True
    resource_address = address[address.rfind(f"{resource_type}.") :]
    return bool(resource_address) and (
        reference == resource_address or reference.startswith(f"{resource_address}.")
    )


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


def _check_dynamodb_recovery(
    resources: tuple[dict[str, Any], ...],
    findings: list[PlanPolicyFinding],
) -> None:
    """Require known, enabled PITR for generated DynamoDB tables."""
    for item in resources:
        if item.get("type") != "aws_dynamodb_table":
            continue
        address = item.get("address")
        values = item.get("values")
        if not isinstance(values, dict):
            _deny(
                findings,
                "dynamodb_pitr_settings_invalid",
                address,
                "DavDeploy could not verify DynamoDB point-in-time recovery settings.",
            )
            continue

        raw_pitr = values.get("point_in_time_recovery")
        if raw_pitr is None or raw_pitr == []:
            pitr = None
        elif isinstance(raw_pitr, dict):
            pitr = raw_pitr
        elif (
            isinstance(raw_pitr, list)
            and len(raw_pitr) == 1
            and isinstance(raw_pitr[0], dict)
        ):
            pitr = raw_pitr[0]
        else:
            pitr = "invalid"

        if pitr is None:
            enabled = False
            recovery_period = None
        elif isinstance(pitr, dict):
            enabled = pitr.get("enabled")
            recovery_period = pitr.get("recovery_period_in_days")
        else:
            enabled = None
            recovery_period = None

        if enabled is not True:
            _deny(
                findings,
                "dynamodb_pitr_required",
                address,
                "Generated DynamoDB tables must have point-in-time recovery enabled.",
            )
            continue

        if (
            not isinstance(recovery_period, int)
            or isinstance(recovery_period, bool)
            or not 1 <= recovery_period <= 35
        ):
            _deny(
                findings,
                "dynamodb_pitr_recovery_period_invalid",
                address,
                "The plan does not confirm a valid DynamoDB point-in-time recovery period.",
            )


def _check_dynamodb_table_safety(
    resources: tuple[dict[str, Any], ...], findings: list[PlanPolicyFinding]
) -> None:
    """Require the bounded encrypted, protected, on-demand table shape."""
    for item in resources:
        if item.get("type") != "aws_dynamodb_table":
            continue
        address = item.get("address")
        values = item.get("values")
        if not isinstance(values, dict):
            _deny(
                findings,
                "dynamodb_table_settings_invalid",
                address,
                "DavDeploy could not verify the required DynamoDB table settings.",
            )
            continue

        for key in ("name", "hash_key"):
            value = values.get(key)
            if not isinstance(value, str) or not value.strip():
                _deny(
                    findings,
                    "dynamodb_table_identity_invalid",
                    address,
                    "The DynamoDB table name and partition key must be known and non-empty.",
                )
                break

        if values.get("billing_mode") != "PAY_PER_REQUEST":
            _deny(
                findings,
                "dynamodb_billing_mode_unsupported",
                address,
                "Generated DynamoDB tables must use the module's bounded on-demand billing mode.",
            )

        encryption = values.get("server_side_encryption")
        if isinstance(encryption, list) and len(encryption) == 1:
            encryption = encryption[0]
        if not isinstance(encryption, dict) or encryption.get("enabled") is not True:
            _deny(
                findings,
                "dynamodb_encryption_required",
                address,
                "Generated DynamoDB tables must have server-side encryption enabled.",
            )

        if values.get("deletion_protection_enabled") is not True:
            _deny(
                findings,
                "dynamodb_deletion_protection_required",
                address,
                "Generated DynamoDB tables must have deletion protection enabled.",
            )


def _check_kinesis_streams(
    resources: tuple[dict[str, Any], ...], findings: list[PlanPolicyFinding]
) -> None:
    """Require the module's single-shard, short-retention encrypted stream."""
    for item in resources:
        if item.get("type") != "aws_kinesis_stream":
            continue
        address = item.get("address")
        values = item.get("values")
        if not isinstance(values, dict):
            _deny(
                findings,
                "kinesis_stream_settings_invalid",
                address,
                "DavDeploy could not verify the required Kinesis stream settings.",
            )
            continue

        name = values.get("name")
        if not isinstance(name, str) or not name.strip():
            _deny(
                findings,
                "kinesis_stream_name_invalid",
                address,
                "The Kinesis stream name must be known and non-empty.",
            )

        shard_count = values.get("shard_count")
        if isinstance(shard_count, bool) or shard_count != 1:
            _deny(
                findings,
                "kinesis_shard_count_unsupported",
                address,
                "Generated Kinesis streams are limited to one provisioned shard.",
            )

        retention = values.get("retention_period")
        if isinstance(retention, bool) or retention != 24:
            _deny(
                findings,
                "kinesis_retention_period_unsupported",
                address,
                "Generated Kinesis streams must use 24-hour record retention.",
            )

        if values.get("encryption_type") != "KMS":
            _deny(
                findings,
                "kinesis_encryption_required",
                address,
                "Generated Kinesis streams must use KMS server-side encryption.",
            )

        if values.get("kms_key_id") != "alias/aws/kinesis":
            _deny(
                findings,
                "kinesis_key_unsupported",
                address,
                "Generated Kinesis streams must use the AWS-managed Kinesis key.",
            )

        raw_mode = values.get("stream_mode_details")
        if isinstance(raw_mode, list) and len(raw_mode) == 1:
            raw_mode = raw_mode[0]
        if not isinstance(raw_mode, dict) or raw_mode.get("stream_mode") != "PROVISIONED":
            _deny(
                findings,
                "kinesis_stream_mode_unsupported",
                address,
                "Generated Kinesis streams must use provisioned capacity mode.",
            )


def _check_efs_file_systems(
    resources: tuple[dict[str, Any], ...], findings: list[PlanPolicyFinding]
) -> None:
    """Require encryption and the module's bounded EFS performance profile."""
    for item in resources:
        if item.get("type") != "aws_efs_file_system":
            continue
        address = item.get("address")
        values = item.get("values")
        if not isinstance(values, dict):
            _deny(
                findings,
                "efs_settings_invalid",
                address,
                "DavDeploy could not verify the required EFS file-system settings.",
            )
            continue

        if values.get("encrypted") is not True:
            _deny(
                findings,
                "efs_encryption_required",
                address,
                "Generated EFS file systems must encrypt data at rest.",
            )
        if values.get("performance_mode") != "generalPurpose":
            _deny(
                findings,
                "efs_performance_mode_unsupported",
                address,
                "Generated EFS file systems must use the reviewed General Purpose mode.",
            )
        if values.get("throughput_mode") != "bursting":
            _deny(
                findings,
                "efs_throughput_mode_unsupported",
                address,
                "Generated EFS file systems must use the reviewed Bursting throughput mode.",
            )


def _check_efs_nfs_ingress(
    resources: tuple[dict[str, Any], ...], findings: list[PlanPolicyFinding]
) -> None:
    """Require any planned NFS ingress to be TCP/2049 from a security group."""
    _check_security_group_port_ingress(
        resources, port=2049, service_name="NFS", finding_prefix="efs_nfs", findings=findings
    )


def _check_efs_mount_target_binding(
    document: dict[str, Any],
    resources: tuple[dict[str, Any], ...],
    findings: list[PlanPolicyFinding],
) -> None:
    """Bind EFS mount targets and NFS rules to the same planned security groups."""
    efs_file_systems = {
        item.get("address")
        for item in resources
        if item.get("type") == "aws_efs_file_system"
        and isinstance(item.get("address"), str)
    }
    if not efs_file_systems:
        return

    configured = _configured_resource_references(document)
    security_groups = {
        item.get("address")
        for item in resources
        if item.get("type") == "aws_security_group"
        and isinstance(item.get("address"), str)
    }
    mount_target_groups: dict[str, set[str]] = {}
    mount_targets_by_file_system: dict[str, set[str]] = {
        address: set() for address in efs_file_systems
    }
    for item in resources:
        if item.get("type") != "aws_efs_mount_target":
            continue
        address = item.get("address")
        if not isinstance(address, str):
            continue
        references = configured.get(address, ())
        file_system_refs = {
            file_system
            for file_system in efs_file_systems
            if _references_resource(references, file_system)
        }
        if len(file_system_refs) != 1:
            _deny(
                findings,
                "efs_mount_target_file_system_binding_invalid",
                address,
                "Each EFS mount target must reference exactly one same-plan file system.",
            )
        else:
            mount_targets_by_file_system[next(iter(file_system_refs))].add(address)

        group_refs = {
            security_group
            for security_group in security_groups
            if _references_resource(references, security_group)
        }
        if not group_refs:
            _deny(
                findings,
                "efs_mount_target_security_group_binding_invalid",
                address,
                "Each EFS mount target must reference a same-plan security group.",
            )
        mount_target_groups[address] = group_refs

    for file_system, targets in mount_targets_by_file_system.items():
        if not targets:
            _deny(
                findings,
                "efs_mount_target_missing",
                file_system,
                "Each generated EFS file system must have a same-plan mount target.",
            )

    nfs_target_groups: dict[str, set[str]] = {}
    for item in resources:
        kind = item.get("type")
        if kind == "aws_security_group":
            values = item.get("values")
            rules = values.get("ingress", []) if isinstance(values, dict) else []
            if not isinstance(rules, list):
                continue
            for rule in rules:
                if not isinstance(rule, dict) or not _rule_includes_port(rule, 2049):
                    continue
                address = item.get("address")
                if isinstance(address, str):
                    nfs_target_groups.setdefault(address, set()).add(address)
            continue
        if kind not in {
            "aws_security_group_rule",
            "aws_vpc_security_group_ingress_rule",
        }:
            continue
        values = item.get("values")
        if not isinstance(values, dict):
            continue
        if kind == "aws_security_group_rule" and values.get("type") != "ingress":
            continue
        protocol = values.get(
            "protocol" if kind == "aws_security_group_rule" else "ip_protocol"
        )
        if not _rule_includes_port(values, 2049, protocol=protocol):
            continue
        address = item.get("address")
        references = configured.get(address, ())
        target_groups = {
            security_group
            for security_group in security_groups
            if _references_resource(references, security_group)
        }
        if not target_groups:
            _deny(
                findings,
                "efs_nfs_ingress_target_binding_invalid",
                address,
                "NFS ingress must target a same-plan security group attached to an EFS mount target.",
            )
        nfs_target_groups[address] = target_groups

    attached_groups = {
        group
        for groups in mount_target_groups.values()
        for group in groups
    }
    bound_nfs_groups = {
        group for groups in nfs_target_groups.values() for group in groups
    }
    for security_group in attached_groups.difference(bound_nfs_groups):
        _deny(
            findings,
            "efs_nfs_ingress_missing",
            security_group,
            "Each EFS mount-target security group must have a same-plan TCP/2049 ingress rule.",
        )
    for address, groups in nfs_target_groups.items():
        if not groups.intersection(attached_groups):
            _deny(
                findings,
                "efs_nfs_ingress_target_mismatch",
                address,
                "NFS ingress must target a security group attached to a same-plan EFS mount target.",
            )


def _rule_includes_port(
    rule: dict[str, Any], port: int, *, protocol: Any = None
) -> bool:
    protocol = rule.get("protocol") if protocol is None else protocol
    from_port = _integer(rule.get("from_port"))
    to_port = _integer(rule.get("to_port"))
    return protocol == "-1" or (
        protocol == "tcp"
        and from_port is not None
        and to_port is not None
        and from_port <= port <= to_port
    )


def _check_redis_ingress(
    document: dict[str, Any],
    resources: tuple[dict[str, Any], ...],
    findings: list[PlanPolicyFinding],
) -> None:
    """Require Redis ingress to be TCP/6379 from a security group."""
    _check_security_group_port_ingress(
        resources, port=6379, service_name="Redis", finding_prefix="redis", findings=findings
    )
    configured = _configured_resource_references(document)
    redis_groups = tuple(
        resource.get("address")
        for resource in resources
        if resource.get("type") == "aws_security_group"
        and isinstance(resource.get("address"), str)
        and any(
            resource_ref == resource["address"]
            or resource_ref.startswith(f"{resource['address']}.")
            for item in resources
            if item.get("type") == "aws_elasticache_replication_group"
            for resource_ref in configured.get(item.get("address"), ())
        )
    )
    if not redis_groups:
        return
    for item in resources:
        if item.get("type") == "aws_security_group":
            values = item.get("values")
            rules = values.get("ingress", []) if isinstance(values, dict) else []
            if not isinstance(rules, list):
                continue
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                protocol = rule.get("protocol")
                from_port = _integer(rule.get("from_port"))
                to_port = _integer(rule.get("to_port"))
                includes_redis = protocol == "-1" or (
                    protocol == "tcp"
                    and from_port is not None
                    and to_port is not None
                    and from_port <= 6379 <= to_port
                )
                if includes_redis and item.get("address") not in redis_groups:
                    _deny(
                        findings,
                        "redis_ingress_group_binding_invalid",
                        item.get("address"),
                        "Redis ingress must attach to the security group used by the replication group.",
                    )
            continue
        if item.get("type") not in {
            "aws_vpc_security_group_ingress_rule",
            "aws_security_group_rule",
        }:
            continue
        values = item.get("values")
        if not isinstance(values, dict):
            continue
        if item.get("type") == "aws_security_group_rule" and values.get("type") != "ingress":
            continue
        protocol = values.get(
            "protocol" if item.get("type") == "aws_security_group_rule" else "ip_protocol"
        )
        from_port = _integer(values.get("from_port"))
        to_port = _integer(values.get("to_port"))
        if not (
            protocol == "-1"
            or protocol == "tcp"
            and from_port is not None
            and to_port is not None
            and from_port <= 6379 <= to_port
        ):
            continue
        references = configured.get(item.get("address"), ())
        if not any(
            _references_resource(references, group_address)
            for group_address in redis_groups
        ):
            _deny(
                findings,
                "redis_ingress_group_binding_invalid",
                item.get("address"),
                "Redis ingress must attach to the security group used by the replication group.",
            )


def _check_security_group_port_ingress(
    resources: tuple[dict[str, Any], ...],
    *,
    port: int,
    service_name: str,
    finding_prefix: str,
    findings: list[PlanPolicyFinding],
) -> None:
    """Require scoped source groups for exact single-port TCP service ingress."""
    for item in resources:
        kind = item.get("type")
        if kind not in {
            "aws_security_group",
            "aws_security_group_rule",
            "aws_vpc_security_group_ingress_rule",
        }:
            continue
        address = item.get("address")
        values = item.get("values")
        if not isinstance(values, dict):
            continue

        if kind == "aws_security_group":
            rules = values.get("ingress", [])
            legacy = True
        elif kind == "aws_security_group_rule":
            if values.get("type") != "ingress":
                continue
            rules = [values]
            legacy = True
        else:
            rules = [values]
            legacy = False
        if not isinstance(rules, list):
            _deny(
                findings,
                f"{finding_prefix}_ingress_unknown",
                address,
                f"The plan does not make {service_name} inbound access clear.",
            )
            continue

        for rule in rules:
            if not isinstance(rule, dict):
                _deny(
                    findings,
                    f"{finding_prefix}_ingress_unknown",
                    address,
                    f"The plan does not make {service_name} inbound access clear.",
                )
                continue
            protocol = rule.get("protocol" if legacy else "ip_protocol")
            from_port = _integer(rule.get("from_port"))
            to_port = _integer(rule.get("to_port"))
            if protocol == "-1":
                is_service_port = True
            elif protocol == "tcp" and from_port is not None and to_port is not None:
                is_service_port = from_port <= port <= to_port
            elif protocol is None or from_port is None or to_port is None:
                _deny(
                    findings,
                    f"{finding_prefix}_ingress_unknown",
                    address,
                    f"The plan does not make {service_name} inbound access clear.",
                )
                continue
            else:
                is_service_port = False
            if not is_service_port:
                continue

            source_fields = (
                ("source_security_group_id", "security_groups")
                if legacy
                else ("referenced_security_group_id",)
            )
            group_source = any(
                isinstance(rule.get(key), str)
                and bool(rule[key].strip())
                or isinstance(rule.get(key), list)
                and bool(rule[key])
                and all(isinstance(value, str) and value.strip() for value in rule[key])
                for key in source_fields
            )
            has_ip_source = any(
                rule.get(key) not in (None, "", [])
                for key in (
                    "cidr_ipv4",
                    "cidr_ipv6",
                    "cidr_blocks",
                    "ipv6_cidr_blocks",
                    "prefix_list_id",
                    "prefix_list_ids",
                )
            )
            if (
                protocol != "tcp"
                or from_port != port
                or to_port != port
                or not group_source
                or has_ip_source
                or rule.get("self") is True
            ):
                _deny(
                    findings,
                    f"{finding_prefix}_ingress_unsupported",
                    address,
                    f"{service_name} access must use exactly TCP port {port} from a security group.",
                )


def _check_elasticache_replication_groups(
    document: dict[str, Any],
    resources: tuple[dict[str, Any], ...],
    findings: list[PlanPolicyFinding],
) -> None:
    """Require the bounded, encrypted, AUTH-protected Redis module profile."""
    changes = {
        item.get("address"): item.get("change")
        for item in document.get("resource_changes", [])
        if isinstance(item, dict)
    }
    configured = _configured_resource_references(document)
    for item in resources:
        if item.get("type") != "aws_elasticache_replication_group":
            continue
        address = item.get("address")
        values = item.get("values")
        if not isinstance(values, dict):
            _deny(
                findings,
                "redis_settings_invalid",
                address,
                "DavDeploy could not verify the required Redis replication-group settings.",
            )
            continue

        if not isinstance(values.get("replication_group_id"), str) or not values[
            "replication_group_id"
        ].strip():
            _deny(
                findings,
                "redis_identity_invalid",
                address,
                "The Redis replication-group identity must be known and non-empty.",
            )
        exact_values = {
            "engine": ("redis", "redis_engine_unsupported"),
            "engine_version": ("7.1", "redis_engine_version_unsupported"),
            "node_type": ("cache.t4g.micro", "redis_node_type_unsupported"),
            "num_cache_clusters": (1, "redis_cluster_size_unsupported"),
            "port": (6379, "redis_port_unsupported"),
            "auth_token_update_strategy": ("SET", "redis_auth_strategy_unsupported"),
            "transit_encryption_mode": ("required", "redis_tls_mode_unsupported"),
            "automatic_failover_enabled": (False, "redis_failover_shape_unsupported"),
            "multi_az_enabled": (False, "redis_multi_az_shape_unsupported"),
        }
        for key, (expected, code) in exact_values.items():
            actual = values.get(key)
            if isinstance(expected, int) and not isinstance(expected, bool):
                matches = isinstance(actual, int) and not isinstance(actual, bool) and actual == expected
            else:
                matches = actual is expected if isinstance(expected, bool) else actual == expected
            if not matches:
                _deny(
                    findings,
                    code,
                    address,
                    "Generated Redis replication groups must use the module's reviewed bounded profile.",
                )

        if values.get("at_rest_encryption_enabled") is not True:
            _deny(
                findings,
                "redis_at_rest_encryption_required",
                address,
                "Generated Redis replication groups must encrypt data at rest.",
            )
        if values.get("transit_encryption_enabled") is not True:
            _deny(
                findings,
                "redis_transit_encryption_required",
                address,
                "Generated Redis replication groups must require encrypted client connections.",
            )

        token = values.get("auth_token")
        if (
            not isinstance(token, str)
            or not 16 <= len(token) <= 128
            or re.fullmatch(r"[A-Za-z0-9!&#$^<>-]{16,128}", token) is None
        ):
            _deny(
                findings,
                "redis_auth_token_invalid",
                address,
                "Generated Redis replication groups must have a valid AUTH token.",
            )

        change = changes.get(address)
        after_sensitive = change.get("after_sensitive") if isinstance(change, dict) else None
        if (
            not isinstance(after_sensitive, dict)
            or not _path_contains_unknown(after_sensitive, ("auth_token",))
        ):
            _deny(
                findings,
                "redis_auth_token_not_sensitive",
                address,
                "Redis AUTH token values must remain marked sensitive in the Terraform plan.",
            )

        if not isinstance(values.get("subnet_group_name"), str) or not values[
            "subnet_group_name"
        ].strip():
            _deny(
                findings,
                "redis_network_binding_invalid",
                address,
                "Redis replication groups must identify a known subnet group.",
            )
        references = configured.get(address, ())
        security_group_bound = any(
            resource.get("type") == "aws_security_group"
            and isinstance(resource.get("address"), str)
            and _references_resource(references, resource["address"])
            for resource in resources
        )
        subnet_group_bound = any(
            resource.get("type") == "aws_elasticache_subnet_group"
            and isinstance(resource.get("address"), str)
            and _references_resource(references, resource["address"])
            for resource in resources
        )
        if not security_group_bound or not subnet_group_bound:
            _deny(
                findings,
                "redis_network_binding_invalid",
                address,
                "Redis replication groups must reference same-plan subnet and security groups.",
            )


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
        if "NotPrincipal" in statement:
            return True
        principal = statement.get("Principal")
        if principal == "*" or (
            isinstance(principal, dict)
            and any(value == "*" or isinstance(value, list) and "*" in value for value in principal.values())
        ):
            return True
    return False


def _has_unbounded_resource_allow(policy: dict[str, Any]) -> bool:
    return any(
        str(statement.get("Effect", "")).lower() == "allow"
        and "NotResource" in statement
        for statement in _statements(policy, require_resource=True)
    )


def _has_unbounded_resource_arn_allow(
    policy: dict[str, Any], service: str
) -> bool:
    return any(
        str(statement.get("Effect", "")).lower() == "allow"
        and any(
            _unbounded_data_resource(resource, service)
            for resource in _string_list(statement.get("Resource"))
        )
        for statement in _statements(policy, require_resource=True)
    )


def _has_not_action_allow(policy: dict[str, Any]) -> bool:
    return any(
        str(statement.get("Effect", "")).lower() == "allow"
        and "NotAction" in statement
        for statement in _statements(policy, require_resource=True)
    )


def _has_unverified_resource_policy_principal(
    policy: dict[str, Any], expected_account_id: str
) -> bool:
    service_pattern = r"[a-z0-9-]+(?:\.[a-z0-9-]+)*\.amazonaws\.com(?:\.cn)?"
    for statement in _statements(policy, require_resource=True, require_principal=True):
        if str(statement.get("Effect", "")).lower() != "allow" or "NotPrincipal" in statement:
            continue
        principal = statement.get("Principal")
        if principal == "*":
            continue
        principals = principal if isinstance(principal, dict) else {"AWS": principal}
        for principal_type, raw_values in principals.items():
            values = _string_list(raw_values)
            if not values or any("*" in value or "?" in value for value in values):
                return True
            if principal_type == "AWS":
                if any(
                    not _is_same_account_principal(value, expected_account_id)
                    for value in values
                ):
                    return True
            elif principal_type == "Service":
                if any(not re.fullmatch(service_pattern, value) for value in values):
                    return True
            else:
                return True
    return False


def _check_sqs_queue_policies(
    resources: tuple[dict[str, Any], ...],
    findings: list[PlanPolicyFinding],
    expected_account_id: str,
) -> None:
    for item in resources:
        if item.get("type") != "aws_sqs_queue_policy":
            continue
        values = item.get("values")
        if not isinstance(values, dict):
            _deny(
                findings,
                "sqs_policy_unknown",
                item.get("address"),
                "The queue access policy is missing or unknown.",
            )
            continue
        address = item.get("address")
        policy = _json_document(values.get("policy"), findings, address)
        if policy is not None:
            if _has_public_allow(policy):
                _deny(
                    findings,
                    "sqs_public_policy_denied",
                    address,
                    "The plan grants public or unbounded access to an SQS queue.",
                )
            elif _has_unverified_resource_policy_principal(
                policy, expected_account_id
            ):
                _deny(
                    findings,
                    "sqs_unverified_policy_principal_denied",
                    address,
                    "The queue policy names an external or unverified principal.",
                )
            elif _has_not_action_allow(policy):
                _deny(
                    findings,
                    "sqs_not_action_policy_denied",
                    address,
                    "The queue policy uses an inverse action scope that cannot be safely bounded.",
                )
            elif _has_unbounded_resource_allow(policy):
                _deny(
                    findings,
                    "sqs_not_resource_policy_denied",
                    address,
                    "The queue policy uses an inverse resource scope that cannot be safely bounded.",
                )
            elif _has_unbounded_resource_arn_allow(policy, "sqs"):
                _deny(
                    findings,
                    "sqs_resource_arn_unbounded",
                    address,
                    "The queue policy resource must use a complete, bounded SQS ARN.",
                )


def _sns_topic_arn(name: Any, account_id: str, region: str) -> str | None:
    if not isinstance(name, str) or not re.fullmatch(
        r"(?=.{1,256}\Z)[A-Za-z0-9_-]+(?:\.fifo)?", name
    ):
        return None
    return (
        f"arn:{_sqs_partition_for_region(region)}:sns:{region}:"
        f"{account_id}:{name}"
    )


def _sqs_queue_url(name: Any, account_id: str, region: str) -> str | None:
    if _sqs_queue_arn(name, account_id, region) is None:
        return None
    partition = _sqs_partition_for_region(region)
    if partition not in {"aws", "aws-us-gov", "aws-cn"}:
        return None
    domain = "amazonaws.com.cn" if partition == "aws-cn" else "amazonaws.com"
    return f"https://sqs.{region}.{domain}/{account_id}/{name}"


def _sqs_policy_queue_arn(queue_urls: dict[str, str], queue_url: Any) -> str | None:
    return queue_urls.get(queue_url) if isinstance(queue_url, str) else None


def _sqs_action_may_send(action: Any) -> bool:
    actions = _string_list(action)
    return any(
        fnmatchcase("sqs:sendmessage", item.lower())
        for item in actions
    )


def _valid_sns_sqs_send_statement(
    statement: dict[str, Any],
    *,
    queue_arn: str,
    topic_arn: str,
    account_id: str,
) -> bool:
    return (
        statement.get("Effect") == "Allow"
        and statement.get("Principal") == {"Service": "sns.amazonaws.com"}
        and statement.get("Action") == "sqs:SendMessage"
        and statement.get("Resource") == queue_arn
        and statement.get("Condition")
        == {
            "ArnEquals": {"aws:SourceArn": topic_arn},
            "StringEquals": {"aws:SourceAccount": account_id},
        }
    )


def _check_sns_sqs_subscription_bindings(
    resources: tuple[dict[str, Any], ...],
    findings: list[PlanPolicyFinding],
    expected_account_id: str,
    expected_region: str,
) -> None:
    """Bind planned SNS-to-SQS subscriptions to one exact, conditional send grant."""
    topics: set[str] = set()
    for item in resources:
        if item.get("type") != "aws_sns_topic":
            continue
        values = item.get("values")
        name = values.get("name") if isinstance(values, dict) else None
        address = item.get("address")
        derived_arn = _sns_topic_arn(name, expected_account_id, expected_region)
        arn = values.get("arn") if isinstance(values, dict) else None
        if derived_arn is not None and arn in (None, derived_arn):
            topics.add(derived_arn)
        elif derived_arn is not None:
            _deny(
                findings,
                "sns_topic_identity_invalid",
                address,
                "The planned SNS topic does not match the trusted account, region, and topic name.",
            )

    queues: set[str] = set()
    queue_urls: dict[str, str] = {}
    for item in resources:
        if item.get("type") != "aws_sqs_queue":
            continue
        values = item.get("values")
        name = values.get("name") if isinstance(values, dict) else None
        address = item.get("address")
        derived_arn = _sqs_queue_arn(name, expected_account_id, expected_region)
        arn = values.get("arn") if isinstance(values, dict) else None
        if derived_arn is not None and arn in (None, derived_arn):
            queues.add(derived_arn)
            derived_url = _sqs_queue_url(name, expected_account_id, expected_region)
            if derived_url is not None:
                queue_urls[derived_url] = derived_arn

    subscriptions = [
        item for item in resources if item.get("type") == "aws_sns_topic_subscription"
    ]
    subscription_pairs: set[tuple[str, str]] = set()
    for subscription in subscriptions:
        address = subscription.get("address")
        values = subscription.get("values")
        if not isinstance(values, dict) or values.get("protocol") != "sqs":
            _deny(
                findings,
                "sns_subscription_protocol_unsupported",
                address,
                "Only a known SNS-to-SQS subscription protocol is supported by this plan policy.",
            )
            continue

        topic_arn = values.get("topic_arn")
        queue_arn = values.get("endpoint")
        if not isinstance(topic_arn, str) or topic_arn not in topics:
            _deny(
                findings,
                "sns_subscription_topic_unplanned",
                address,
                "The SNS subscription must name one exact topic in the trusted plan account and region.",
            )
            continue
        if not isinstance(queue_arn, str) or queue_arn not in queues:
            _deny(
                findings,
                "sns_subscription_queue_unplanned",
                address,
                "The SNS subscription must target one exact SQS queue in the trusted plan account and region.",
            )
            continue

        pair = (topic_arn, queue_arn)
        if pair in subscription_pairs:
            _deny(
                findings,
                "sns_subscription_duplicate",
                address,
                "A topic and queue may have only one planned subscription pair.",
            )
            continue
        subscription_pairs.add(pair)

        matching_policies: list[dict[str, Any]] = []
        for policy_item in resources:
            if policy_item.get("type") != "aws_sqs_queue_policy":
                continue
            policy_values = policy_item.get("values")
            if not isinstance(policy_values, dict):
                continue
            policy_queue = _sqs_policy_queue_arn(
                queue_urls, policy_values.get("queue_url")
            )
            if policy_queue != queue_arn:
                continue
            policy = _json_document(
                policy_values.get("policy"), findings, policy_item.get("address")
            )
            if policy is None:
                continue
            for statement in _statements(policy, require_resource=True, require_principal=True):
                if str(statement.get("Effect", "")).lower() != "allow":
                    continue
                principal = statement.get("Principal")
                if not (
                    isinstance(principal, dict)
                    and "sns.amazonaws.com" in _string_list(principal.get("Service"))
                ):
                    continue
                resources_in_statement = _string_list(statement.get("Resource"))
                targets_queue = any(
                    fnmatchcase(queue_arn, resource_arn)
                    for resource_arn in resources_in_statement
                )
                if not targets_queue or not _sqs_action_may_send(statement.get("Action")):
                    continue
                matching_policies.append(
                    {
                        "statement": statement,
                        "queue_arn": queue_arn,
                        "address": policy_item.get("address"),
                    }
                )

        valid = [
            item
            for item in matching_policies
            if _valid_sns_sqs_send_statement(
                item["statement"],
                queue_arn=queue_arn,
                topic_arn=topic_arn,
                account_id=expected_account_id,
            )
        ]
        if len(matching_policies) != 1 or len(valid) != 1:
            _deny(
                findings,
                "sns_sqs_policy_binding_invalid",
                address,
                "The subscribed queue needs one exact SNS SendMessage grant with matching source ARN and account conditions.",
            )

    for policy_item in resources:
        if policy_item.get("type") != "aws_sqs_queue_policy":
            continue
        values = policy_item.get("values")
        if not isinstance(values, dict):
            continue
        policy_queue = _sqs_policy_queue_arn(queue_urls, values.get("queue_url"))
        policy = _json_document(values.get("policy"), findings, policy_item.get("address"))
        if policy is None:
            continue
        for statement in _statements(policy, require_resource=True, require_principal=True):
            principal = statement.get("Principal")
            sns_principal = (
                isinstance(principal, dict)
                and "sns.amazonaws.com" in _string_list(principal.get("Service"))
            )
            if (
                not sns_principal
                or str(statement.get("Effect", "")).lower() != "allow"
                or not _sqs_action_may_send(statement.get("Action"))
            ):
                continue
            resources_in_statement = _string_list(statement.get("Resource"))
            condition = statement.get("Condition")
            arn_equals = condition.get("ArnEquals") if isinstance(condition, dict) else None
            topic_arn = (
                arn_equals.get("aws:SourceArn")
                if isinstance(arn_equals, dict)
                else None
            )
            queue_arns = [
                resource_arn
                for resource_arn in resources_in_statement
                if resource_arn in queues and resource_arn == policy_queue
            ]
            if (
                len(queue_arns) != 1
                or not isinstance(topic_arn, str)
                or topic_arn not in topics
                or (topic_arn, queue_arns[0]) not in subscription_pairs
                or not _valid_sns_sqs_send_statement(
                    statement,
                    queue_arn=queue_arns[0] if len(queue_arns) == 1 else "",
                    topic_arn=topic_arn if isinstance(topic_arn, str) else "",
                    account_id=expected_account_id,
                )
            ):
                _deny(
                    findings,
                    "sns_sqs_policy_binding_invalid",
                    policy_item.get("address"),
                    "SNS may send to SQS only through one exact planned topic, queue, and subscription with source conditions.",
                )


def _event_bus_name(value: Any, account_id: str, region: str) -> str | None:
    if value is None:
        return "default"
    if not isinstance(value, str):
        return None
    name_pattern = r"(?=.{1,256}\Z)[A-Za-z0-9_.-]+"
    if re.fullmatch(name_pattern, value):
        return value
    expected_prefix = (
        f"arn:{_sqs_partition_for_region(region)}:events:{region}:"
        f"{account_id}:event-bus/"
    )
    if value.startswith(expected_prefix):
        name = value[len(expected_prefix) :]
        return name if re.fullmatch(name_pattern, name) else None
    return None


def _event_rule_arn(name: Any, event_bus: str, account_id: str, region: str) -> str | None:
    if not isinstance(name, str) or not re.fullmatch(
        r"(?=.{1,64}\Z)[A-Za-z0-9_.-]+", name
    ):
        return None
    suffix = name if event_bus == "default" else f"{event_bus}/{name}"
    return (
        f"arn:{_sqs_partition_for_region(region)}:events:{region}:"
        f"{account_id}:rule/{suffix}"
    )


def _valid_eventbridge_sqs_send_statement(
    statement: dict[str, Any],
    *,
    queue_arn: str,
    rule_arn: str,
    account_id: str,
) -> bool:
    condition = {"ArnEquals": {"aws:SourceArn": rule_arn}}
    condition_with_account = {
        **condition,
        "StringEquals": {"aws:SourceAccount": account_id},
    }
    return (
        statement.get("Effect") == "Allow"
        and statement.get("Principal") == {"Service": "events.amazonaws.com"}
        and statement.get("Action") == "sqs:SendMessage"
        and statement.get("Resource") == queue_arn
        and statement.get("Condition") in (condition, condition_with_account)
    )


def _single_nested_plan_block(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict):
        return value[0]
    return None


def _eventbridge_sqs_send_statements(
    resources: tuple[dict[str, Any], ...],
    findings: list[PlanPolicyFinding],
    queue_urls: dict[str, str],
    queue_arn: str,
) -> list[dict[str, Any]]:
    matching: list[dict[str, Any]] = []
    for policy_item in resources:
        if policy_item.get("type") != "aws_sqs_queue_policy":
            continue
        policy_values = policy_item.get("values")
        if not isinstance(policy_values, dict):
            continue
        if _sqs_policy_queue_arn(queue_urls, policy_values.get("queue_url")) != queue_arn:
            continue
        policy = _json_document(
            policy_values.get("policy"), findings, policy_item.get("address")
        )
        if policy is None:
            continue
        for statement in _statements(policy, require_resource=True, require_principal=True):
            principal = statement.get("Principal")
            is_eventbridge = (
                isinstance(principal, dict)
                and "events.amazonaws.com" in _string_list(principal.get("Service"))
            )
            resources_in_statement = _string_list(statement.get("Resource"))
            if (
                is_eventbridge
                and str(statement.get("Effect", "")).lower() == "allow"
                and _sqs_action_may_send(statement.get("Action"))
                and any(
                    fnmatchcase(queue_arn, resource_arn)
                    for resource_arn in resources_in_statement
                )
            ):
                matching.append(statement)
    return matching


def _check_eventbridge_sqs_bindings(
    resources: tuple[dict[str, Any], ...],
    findings: list[PlanPolicyFinding],
    expected_account_id: str,
    expected_region: str,
) -> None:
    """Bind EventBridge SQS targets to exact planned rules and queue grants."""
    bus_names = {"default"}
    for item in resources:
        if item.get("type") != "aws_cloudwatch_event_bus":
            continue
        values = item.get("values")
        name = values.get("name") if isinstance(values, dict) else None
        if not isinstance(name, str) or not re.fullmatch(
            r"(?=.{1,256}\Z)[A-Za-z0-9_.-]+", name
        ):
            continue
        expected_arn = (
            f"arn:{_sqs_partition_for_region(expected_region)}:events:"
            f"{expected_region}:{expected_account_id}:event-bus/{name}"
        )
        planned_arn = values.get("arn") if isinstance(values, dict) else None
        if planned_arn not in (None, expected_arn):
            _deny(
                findings,
                "eventbridge_bus_identity_invalid",
                item.get("address"),
                "The planned EventBridge bus does not match the trusted account, region, and bus name.",
            )
            continue
        bus_names.add(name)

    rules: dict[tuple[str, str], str] = {}
    for item in resources:
        if item.get("type") != "aws_cloudwatch_event_rule":
            continue
        values = item.get("values")
        if not isinstance(values, dict):
            continue
        event_bus = _event_bus_name(
            values.get("event_bus_name"), expected_account_id, expected_region
        )
        rule_arn = _event_rule_arn(
            values.get("name"), event_bus or "", expected_account_id, expected_region
        )
        if event_bus is None or event_bus not in bus_names or rule_arn is None:
            continue
        planned_arn = values.get("arn")
        if planned_arn not in (None, rule_arn):
            _deny(
                findings,
                "eventbridge_rule_identity_invalid",
                item.get("address"),
                "The planned EventBridge rule does not match the trusted account, region, bus, and rule name.",
            )
            continue
        key = (event_bus, values["name"])
        if key in rules:
            _deny(
                findings,
                "eventbridge_rule_duplicate",
                item.get("address"),
                "An EventBridge bus and rule name may appear only once in the plan.",
            )
            continue
        rules[key] = rule_arn

    queues: set[str] = set()
    queue_names: dict[str, str] = {}
    queue_urls: dict[str, str] = {}
    for item in resources:
        if item.get("type") != "aws_sqs_queue":
            continue
        values = item.get("values")
        if not isinstance(values, dict):
            continue
        queue_arn = _sqs_queue_arn(
            values.get("name"), expected_account_id, expected_region
        )
        if queue_arn is None or values.get("arn") not in (None, queue_arn):
            continue
        queue_url = _sqs_queue_url(
            values.get("name"), expected_account_id, expected_region
        )
        queues.add(queue_arn)
        if queue_url is not None:
            queue_urls[queue_url] = queue_arn
        queue_names[queue_arn] = values["name"]

    target_pairs: set[tuple[str, str]] = set()
    for target in resources:
        if target.get("type") != "aws_cloudwatch_event_target":
            continue
        values = target.get("values")
        if not isinstance(values, dict):
            _deny(
                findings,
                "eventbridge_target_unknown",
                target.get("address"),
                "The EventBridge target must have known rule, bus, and destination values.",
            )
            continue
        target_arn = values.get("arn")
        if target_arn is None:
            _deny(
                findings,
                "eventbridge_target_unknown",
                target.get("address"),
                "The EventBridge target destination must be known before policy review.",
            )
            continue
        if not isinstance(target_arn, str) or not target_arn.startswith("arn:"):
            _deny(
                findings,
                "eventbridge_target_identity_invalid",
                target.get("address"),
                "The EventBridge target destination must be a known ARN.",
            )
            continue
        if ":sqs:" not in target_arn:
            continue

        event_bus = _event_bus_name(
            values.get("event_bus_name"), expected_account_id, expected_region
        )
        rule_name = values.get("rule")
        rule_arn = (
            rules.get((event_bus, rule_name))
            if event_bus is not None and isinstance(rule_name, str)
            else None
        )
        if rule_arn is None:
            _deny(
                findings,
                "eventbridge_target_rule_unplanned",
                target.get("address"),
                "An SQS target must name one exact EventBridge rule and bus in the plan.",
            )
            continue
        if target_arn not in queues:
            _deny(
                findings,
                "eventbridge_sqs_queue_unplanned",
                target.get("address"),
                "An EventBridge SQS target must use one exact queue in the trusted plan account and region.",
            )
            continue
        if values.get("role_arn"):
            _deny(
                findings,
                "eventbridge_sqs_role_unsupported",
                target.get("address"),
                "This policy supports direct EventBridge-to-SQS resource grants, not target execution roles.",
            )
            continue

        pair = (rule_arn, target_arn)
        if pair in target_pairs:
            _deny(
                findings,
                "eventbridge_target_duplicate",
                target.get("address"),
                "An EventBridge rule may target a given SQS queue only once in this plan.",
            )
            continue
        target_pairs.add(pair)
        matching = _eventbridge_sqs_send_statements(
            resources, findings, queue_urls, target_arn
        )
        valid = [
            statement
            for statement in matching
            if _valid_eventbridge_sqs_send_statement(
                statement,
                queue_arn=target_arn,
                rule_arn=rule_arn,
                account_id=expected_account_id,
            )
        ]
        if len(matching) != 1 or len(valid) != 1:
            _deny(
                findings,
                "eventbridge_sqs_policy_binding_invalid",
                target.get("address"),
                "The target queue needs one exact EventBridge SendMessage grant with the matching rule source ARN.",
            )

        retry_policy = _single_nested_plan_block(values.get("retry_policy"))
        retry_attempts = (
            retry_policy.get("maximum_retry_attempts")
            if retry_policy is not None
            else None
        )
        maximum_age = (
            retry_policy.get("maximum_event_age_in_seconds")
            if retry_policy is not None
            else None
        )
        if (
            type(retry_attempts) is not int
            or not 0 <= retry_attempts <= 185
            or type(maximum_age) is not int
            or not 60 <= maximum_age <= 86400
        ):
            _deny(
                findings,
                "eventbridge_retry_policy_invalid",
                target.get("address"),
                "An SQS target needs known retry attempts from 0 to 185 and maximum event age from 60 to 86400 seconds.",
            )

        dead_letter_config = _single_nested_plan_block(
            values.get("dead_letter_config")
        )
        dead_letter_arn = (
            dead_letter_config.get("arn")
            if dead_letter_config is not None
            else None
        )
        if (
            not isinstance(dead_letter_arn, str)
            or dead_letter_arn not in queues
            or dead_letter_arn == target_arn
            or queue_names.get(dead_letter_arn, "").endswith(".fifo")
        ):
            _deny(
                findings,
                "eventbridge_dlq_invalid",
                target.get("address"),
                "An SQS target needs a distinct planned standard queue for its dead-letter destination.",
            )
        else:
            dead_letter_pair = (rule_arn, dead_letter_arn)
            if dead_letter_pair in target_pairs:
                _deny(
                    findings,
                    "eventbridge_target_duplicate",
                    target.get("address"),
                    "An EventBridge rule may target a given SQS queue only once in this plan.",
                )
            else:
                target_pairs.add(dead_letter_pair)
            dead_letter_grants = _eventbridge_sqs_send_statements(
                resources, findings, queue_urls, dead_letter_arn
            )
            valid_dead_letter_grants = [
                statement
                for statement in dead_letter_grants
                if _valid_eventbridge_sqs_send_statement(
                    statement,
                    queue_arn=dead_letter_arn,
                    rule_arn=rule_arn,
                    account_id=expected_account_id,
                )
            ]
            if len(dead_letter_grants) != 1 or len(valid_dead_letter_grants) != 1:
                _deny(
                    findings,
                    "eventbridge_dlq_policy_binding_invalid",
                    target.get("address"),
                    "The dead-letter queue needs one exact EventBridge SendMessage grant with the matching rule source ARN.",
                )

    for policy_item in resources:
        if policy_item.get("type") != "aws_sqs_queue_policy":
            continue
        values = policy_item.get("values")
        if not isinstance(values, dict):
            continue
        policy_queue = _sqs_policy_queue_arn(queue_urls, values.get("queue_url"))
        policy = _json_document(values.get("policy"), findings, policy_item.get("address"))
        if policy is None:
            continue
        for statement in _statements(policy, require_resource=True, require_principal=True):
            principal = statement.get("Principal")
            is_eventbridge = (
                isinstance(principal, dict)
                and "events.amazonaws.com" in _string_list(principal.get("Service"))
            )
            if (
                not is_eventbridge
                or str(statement.get("Effect", "")).lower() != "allow"
                or not _sqs_action_may_send(statement.get("Action"))
            ):
                continue
            source = statement.get("Condition")
            arn_equals = source.get("ArnEquals") if isinstance(source, dict) else None
            rule_arn = arn_equals.get("aws:SourceArn") if isinstance(arn_equals, dict) else None
            resource_arns = _string_list(statement.get("Resource"))
            matching_queues = [
                arn for arn in resource_arns if arn in queues and arn == policy_queue
            ]
            if (
                len(matching_queues) != 1
                or not isinstance(rule_arn, str)
                or (rule_arn, matching_queues[0]) not in target_pairs
                or not _valid_eventbridge_sqs_send_statement(
                    statement,
                    queue_arn=matching_queues[0] if len(matching_queues) == 1 else "",
                    rule_arn=rule_arn if isinstance(rule_arn, str) else "",
                    account_id=expected_account_id,
                )
            ):
                _deny(
                    findings,
                    "eventbridge_sqs_policy_binding_invalid",
                    policy_item.get("address"),
                    "EventBridge may send to SQS only through an exact planned rule, queue, and target.",
                )


def _check_sqs_queue_encryption(
    resources: tuple[dict[str, Any], ...], findings: list[PlanPolicyFinding]
) -> None:
    for item in resources:
        if item.get("type") != "aws_sqs_queue":
            continue
        values = item.get("values")
        address = item.get("address")
        if not isinstance(values, dict):
            _deny(
                findings,
                "sqs_queue_encryption_unknown",
                address,
                "The plan does not show whether the SQS queue uses server-side encryption.",
            )
        elif values.get("sqs_managed_sse_enabled") is not True:
            _deny(
                findings,
                "sqs_queue_encryption_required",
                address,
                "The SQS queue must enable SQS-managed server-side encryption.",
            )


def _check_ecr_repositories(
    resources: tuple[dict[str, Any], ...], findings: list[PlanPolicyFinding]
) -> None:
    for item in resources:
        if item.get("type") != "aws_ecr_repository":
            continue
        address = item.get("address")
        values = item.get("values")
        if not isinstance(values, dict):
            _deny(
                findings,
                "ecr_repository_configuration_unknown",
                address,
                "The plan does not show the ECR repository safety settings.",
            )
            continue

        if values.get("image_tag_mutability") != "IMMUTABLE":
            _deny(
                findings,
                "ecr_image_tags_must_be_immutable",
                address,
                "ECR image tags must be immutable so a published tag cannot be overwritten.",
            )

        scanning = values.get("image_scanning_configuration")
        if (
            not isinstance(scanning, list)
            or len(scanning) != 1
            or not isinstance(scanning[0], dict)
            or scanning[0].get("scan_on_push") is not True
        ):
            _deny(
                findings,
                "ecr_scan_on_push_required",
                address,
                "The ECR repository must declare scan-on-push enabled.",
            )

        encryption = values.get("encryption_configuration")
        if (
            not isinstance(encryption, list)
            or len(encryption) != 1
            or not isinstance(encryption[0], dict)
            or encryption[0].get("encryption_type") != "AES256"
        ):
            _deny(
                findings,
                "ecr_encryption_required",
                address,
                "Only ECR AES256 repository encryption is currently supported by this policy.",
            )

        if values.get("force_delete") is not False:
            _deny(
                findings,
                "ecr_force_delete_denied",
                address,
                "ECR repositories cannot use force_delete because it removes stored images with the repository.",
            )


def _check_kms_keys(
    resources: tuple[dict[str, Any], ...], findings: list[PlanPolicyFinding]
) -> None:
    for item in resources:
        if item.get("type") != "aws_kms_key":
            continue
        address = item.get("address")
        values = item.get("values")
        if not isinstance(values, dict):
            _deny(
                findings,
                "kms_key_configuration_unknown",
                address,
                "The plan does not show the KMS key safety settings.",
            )
            continue

        requirements = (
            (
                "customer_master_key_spec",
                "SYMMETRIC_DEFAULT",
                "kms_key_must_be_symmetric",
                "Only symmetric-default KMS keys are currently supported.",
            ),
            (
                "key_usage",
                "ENCRYPT_DECRYPT",
                "kms_key_usage_invalid",
                "KMS keys must use ENCRYPT_DECRYPT usage.",
            ),
            (
                "enable_key_rotation",
                True,
                "kms_key_rotation_required",
                "KMS key material rotation must be enabled.",
            ),
            (
                "deletion_window_in_days",
                30,
                "kms_key_deletion_window_too_short",
                "KMS keys must use the maximum 30-day deletion waiting period.",
            ),
            (
                "multi_region",
                False,
                "kms_multi_region_unsupported",
                "Multi-Region KMS keys are unsupported by the current policy.",
            ),
        )
        for attribute, expected, code, message in requirements:
            actual = values.get(attribute)
            if actual != expected or isinstance(actual, bool) != isinstance(expected, bool):
                _deny(findings, code, address, message)


def _check_ssm_parameters(
    resources: tuple[dict[str, Any], ...], findings: list[PlanPolicyFinding]
) -> None:
    for item in resources:
        if item.get("type") != "aws_ssm_parameter":
            continue
        address = item.get("address")
        values = item.get("values")
        if not isinstance(values, dict):
            _deny(
                findings,
                "ssm_parameter_configuration_unknown",
                address,
                "The plan does not show the parameter encryption and tier settings.",
            )
            continue

        if values.get("type") != "SecureString":
            _deny(
                findings,
                "ssm_parameter_secure_string_required",
                address,
                "Parameters from this module must use SecureString encryption.",
            )
        if values.get("tier") != "Standard":
            _deny(
                findings,
                "ssm_parameter_standard_tier_required",
                address,
                "Only Standard-tier parameters are currently supported by this policy.",
            )

        key_id = values.get("key_id")
        if key_id is not None and (not isinstance(key_id, str) or not key_id.strip()):
            _deny(
                findings,
                "ssm_parameter_kms_key_invalid",
                address,
                "A custom KMS key reference must be a known non-empty string.",
            )


def _check_opensearch_domains(
    resources: tuple[dict[str, Any], ...], findings: list[PlanPolicyFinding]
) -> None:
    for item in resources:
        if item.get("type") != "aws_opensearch_domain":
            continue
        address = item.get("address")
        values = item.get("values")
        if not isinstance(values, dict):
            _deny(
                findings,
                "opensearch_configuration_unknown",
                address,
                "The plan does not show the OpenSearch domain safety settings.",
            )
            continue

        if values.get("engine_version") != "OpenSearch_2.11":
            _deny(
                findings,
                "opensearch_engine_version_unsupported",
                address,
                "Only the module's reviewed OpenSearch_2.11 engine setting is supported.",
            )

        cluster = _single_plan_block(values, "cluster_config")
        if cluster is None:
            _deny(
                findings,
                "opensearch_cluster_configuration_invalid",
                address,
                "The OpenSearch cluster must have one known cluster configuration block.",
            )
        else:
            if cluster.get("instance_type") != "t3.small.search":
                _deny(
                    findings,
                    "opensearch_instance_type_unsupported",
                    address,
                    "Only the module's bounded t3.small.search instance shape is supported.",
                )
            if cluster.get("instance_count") != 1 or isinstance(
                cluster.get("instance_count"), bool
            ):
                _deny(
                    findings,
                    "opensearch_instance_count_unsupported",
                    address,
                    "Only a single OpenSearch data node is covered by this policy.",
                )
            if cluster.get("zone_awareness_enabled") is not False:
                _deny(
                    findings,
                    "opensearch_zone_awareness_unsupported",
                    address,
                    "Multi-AZ OpenSearch configurations require separate cost and recovery review.",
                )

        ebs = _single_plan_block(values, "ebs_options")
        if ebs is None:
            _deny(
                findings,
                "opensearch_ebs_configuration_invalid",
                address,
                "The OpenSearch domain must have one known EBS configuration block.",
            )
        else:
            if ebs.get("ebs_enabled") is not True:
                _deny(
                    findings,
                    "opensearch_ebs_required",
                    address,
                    "The reviewed OpenSearch module requires EBS-backed storage.",
                )
            if ebs.get("volume_type") != "gp3":
                _deny(
                    findings,
                    "opensearch_volume_type_unsupported",
                    address,
                    "Only gp3 OpenSearch storage is covered by this policy.",
                )
            if ebs.get("volume_size") != 10 or isinstance(ebs.get("volume_size"), bool):
                _deny(
                    findings,
                    "opensearch_volume_size_unsupported",
                    address,
                    "Only the module's 10 GiB OpenSearch volume is covered by this policy.",
                )

        vpc = _single_plan_block(values, "vpc_options")
        if (
            vpc is None
            or not isinstance(vpc.get("subnet_ids"), list)
            or not vpc.get("subnet_ids")
            or not isinstance(vpc.get("security_group_ids"), list)
            or not vpc.get("security_group_ids")
        ):
            _deny(
                findings,
                "opensearch_vpc_required",
                address,
                "OpenSearch domains must use the reviewed VPC networking mode.",
            )

        encryption = _single_plan_block(values, "encrypt_at_rest")
        if encryption is None or encryption.get("enabled") is not True:
            _deny(
                findings,
                "opensearch_at_rest_encryption_required",
                address,
                "OpenSearch encryption at rest must be enabled.",
            )

        node_encryption = _single_plan_block(values, "node_to_node_encryption")
        if node_encryption is None or node_encryption.get("enabled") is not True:
            _deny(
                findings,
                "opensearch_node_encryption_required",
                address,
                "OpenSearch node-to-node encryption must be enabled.",
            )

        endpoint = _single_plan_block(values, "domain_endpoint_options")
        if endpoint is None or endpoint.get("enforce_https") is not True:
            _deny(
                findings,
                "opensearch_https_required",
                address,
                "OpenSearch domain endpoints must require HTTPS.",
            )
        elif endpoint.get("tls_security_policy") != "Policy-Min-TLS-1-2-2019-07":
            _deny(
                findings,
                "opensearch_tls_policy_unsupported",
                address,
                "OpenSearch endpoints must use the reviewed TLS 1.2 policy.",
            )


def _single_plan_block(values: dict[str, Any], name: str) -> dict[str, Any] | None:
    blocks = values.get(name)
    if not isinstance(blocks, list) or len(blocks) != 1 or not isinstance(blocks[0], dict):
        return None
    return blocks[0]


def _check_acm_certificates(
    resources: tuple[dict[str, Any], ...], findings: list[PlanPolicyFinding]
) -> None:
    for item in resources:
        if item.get("type") != "aws_acm_certificate":
            continue
        address = item.get("address")
        values = item.get("values")
        if not isinstance(values, dict):
            _deny(
                findings,
                "acm_certificate_configuration_unknown",
                address,
                "The plan does not show the certificate request safety settings.",
            )
            continue

        domain_name = values.get("domain_name")
        if not isinstance(domain_name, str) or not domain_name.strip():
            _deny(
                findings,
                "acm_certificate_domain_unknown",
                address,
                "The ACM certificate domain must be a known non-empty name.",
            )
        if values.get("validation_method") != "DNS":
            _deny(
                findings,
                "acm_certificate_dns_validation_required",
                address,
                "The reviewed ACM module requires DNS domain validation.",
            )
        if values.get("key_algorithm") != "RSA_2048":
            _deny(
                findings,
                "acm_certificate_key_algorithm_unsupported",
                address,
                "Only the module's RSA_2048 certificate shape is currently supported.",
            )

        options = _single_plan_block(values, "options")
        if options is None or options.get("export") != "DISABLED":
            _deny(
                findings,
                "acm_certificate_export_denied",
                address,
                "Exportable ACM certificates are outside the supported cost and key-handling policy.",
            )


def _check_route53_zones(
    resources: tuple[dict[str, Any], ...], findings: list[PlanPolicyFinding]
) -> None:
    for item in resources:
        if item.get("type") != "aws_route53_zone":
            continue
        address = item.get("address")
        values = item.get("values")
        if not isinstance(values, dict):
            _deny(
                findings,
                "route53_zone_configuration_unknown",
                address,
                "The plan does not show the hosted zone identity and deletion settings.",
            )
            continue

        name = values.get("name")
        if not isinstance(name, str) or not name.strip():
            _deny(
                findings,
                "route53_zone_name_unknown",
                address,
                "The hosted zone name must be known and non-empty.",
            )
        if values.get("vpc") not in (None, [], {}):
            _deny(
                findings,
                "route53_private_zone_unsupported",
                address,
                "Only public Route 53 hosted zones without VPC associations are covered by this policy.",
            )
        if values.get("force_destroy") is not False:
            _deny(
                findings,
                "route53_zone_force_destroy_denied",
                address,
                "Hosted zones cannot delete their records implicitly during destruction.",
            )


def _check_appconfig_bindings(
    document: dict[str, Any],
    resources: tuple[dict[str, Any], ...],
    findings: list[PlanPolicyFinding],
) -> None:
    applications = [
        item for item in resources if item.get("type") == "aws_appconfig_application"
    ]
    configured_references = _configured_resource_references(document)

    for application in applications:
        values = application.get("values")
        name = values.get("name") if isinstance(values, dict) else None
        if not isinstance(name, str) or not name.strip():
            _deny(
                findings,
                "appconfig_application_name_unknown",
                application.get("address"),
                "The AppConfig application name must be known and non-empty.",
            )

    for environment in (
        item for item in resources if item.get("type") == "aws_appconfig_environment"
    ):
        address = environment.get("address")
        values = environment.get("values")
        if not isinstance(address, str) or not isinstance(values, dict):
            _deny(
                findings,
                "appconfig_environment_configuration_unknown",
                address,
                "The AppConfig environment is missing its name or application binding.",
            )
            continue

        name = values.get("name")
        if not isinstance(name, str) or not name.strip():
            _deny(
                findings,
                "appconfig_environment_name_unknown",
                address,
                "The AppConfig environment name must be known and non-empty.",
            )

        references = configured_references.get(address, ())
        environment_application_id = values.get("application_id")
        matches = []
        for application in applications:
            application_address = application.get("address")
            application_values = application.get("values")
            application_id = (
                application_values.get("id") if isinstance(application_values, dict) else None
            )
            if _references_resource(references, application_address) or (
                isinstance(application_id, str)
                and environment_application_id == application_id
            ):
                matches.append(application)

        if len(matches) != 1:
            _deny(
                findings,
                "appconfig_environment_application_binding_invalid",
                address,
                "Each AppConfig environment must bind to exactly one same-plan application.",
            )


def _sqs_partition_for_region(region: str) -> str:
    if region.startswith("cn-"):
        return "aws-cn"
    if region.startswith("us-gov-"):
        return "aws-us-gov"
    if region.startswith("us-isob-"):
        return "aws-iso-b"
    if region.startswith("eu-isoe-"):
        return "aws-iso-e"
    if region.startswith("us-isof-"):
        return "aws-iso-f"
    if region.startswith(("us-iso-", "eu-iso-")):
        return "aws-iso"
    return "aws"


def _sqs_queue_arn(name: Any, account_id: str, region: str) -> str | None:
    if not isinstance(name, str) or not re.fullmatch(
        r"(?=.{1,80}\Z)[A-Za-z0-9_-]+(?:\.fifo)?", name
    ):
        return None
    return (
        f"arn:{_sqs_partition_for_region(region)}:sqs:{region}:"
        f"{account_id}:{name}"
    )


def _check_sqs_delivery_contract(
    document: dict[str, Any],
    resources: tuple[dict[str, Any], ...],
    findings: list[PlanPolicyFinding],
    expected_account_id: str,
    expected_region: str,
) -> None:
    """Require bounded queue retry pairs and bind Lambda consumers to them."""
    queues = [item for item in resources if item.get("type") == "aws_sqs_queue"]
    if not queues:
        return

    queue_by_arn: dict[str, dict[str, Any]] = {}
    queue_details: dict[str, tuple[dict[str, Any], str, int | None]] = {}
    for item in queues:
        address = item.get("address")
        values = item.get("values")
        if not isinstance(values, dict):
            _deny(
                findings,
                "sqs_queue_delivery_unknown",
                address,
                "The plan does not show the SQS queue delivery settings.",
            )
            continue

        name = values.get("name")
        derived_arn = _sqs_queue_arn(name, expected_account_id, expected_region)
        arn = values.get("arn")
        if derived_arn is None or arn not in {None, derived_arn}:
            _deny(
                findings,
                "sqs_queue_identity_invalid",
                address,
                "The plan does not bind the SQS queue name to the trusted account and region.",
            )
            continue
        if derived_arn in queue_by_arn:
            _deny(
                findings,
                "sqs_queue_identity_duplicate",
                address,
                "The plan contains ambiguous SQS queue identities.",
            )
            continue
        queue_by_arn[derived_arn] = item

        visibility = _integer(values.get("visibility_timeout_seconds"))
        if visibility is None or not 0 <= visibility <= 43_200:
            _deny(
                findings,
                "sqs_visibility_timeout_invalid",
                address,
                "The queue visibility timeout must be known and between 0 and 43,200 seconds.",
            )
        retention = _integer(values.get("message_retention_seconds"))
        if retention is None or not 60 <= retention <= 1_209_600:
            _deny(
                findings,
                "sqs_message_retention_invalid",
                address,
                "The queue message retention must be known and between 60 seconds and 14 days.",
            )
        queue_details[derived_arn] = (item, address, retention)

    redrive_pairs: dict[str, str] = {}
    redrive_targets: dict[str, str] = {}
    redrive_edges: dict[str, str] = {}
    eventbridge_dlq_targets: set[str] = set()
    for target in resources:
        if target.get("type") != "aws_cloudwatch_event_target":
            continue
        values = target.get("values")
        if not isinstance(values, dict):
            continue
        dead_letter = _single_nested_plan_block(values.get("dead_letter_config"))
        dead_letter_arn = dead_letter.get("arn") if dead_letter is not None else None
        if isinstance(dead_letter_arn, str) and dead_letter_arn in queue_by_arn:
            eventbridge_dlq_targets.add(dead_letter_arn)

    for arn, (item, address, source_retention) in queue_details.items():
        values = item["values"]
        redrive_raw = values.get("redrive_policy")
        allow_raw = values.get("redrive_allow_policy")

        if redrive_raw not in (None, ""):
            redrive = _json_document(redrive_raw, findings, address)
            if redrive is None:
                continue
            target_arn = redrive.get("deadLetterTargetArn")
            receive_count = _integer(redrive.get("maxReceiveCount"))
            if (
                set(redrive) != {"deadLetterTargetArn", "maxReceiveCount"}
                or not isinstance(target_arn, str)
                or receive_count is None
                or not 5 <= receive_count <= 10
                or target_arn == arn
            ):
                _deny(
                    findings,
                    "sqs_redrive_policy_invalid",
                    address,
                    "The queue redrive policy must use one different planned DLQ and 5 to 10 receives.",
                )
                continue
            if target_arn not in queue_by_arn:
                _deny(
                    findings,
                    "sqs_redrive_target_unplanned",
                    address,
                    "The queue redrive target must be a queue in the same Terraform plan and account.",
                )
                continue
            redrive_edges[arn] = target_arn
            if target_arn in redrive_targets:
                _deny(
                    findings,
                    "sqs_redrive_target_ambiguous",
                    address,
                    "A planned dead-letter queue must have one bounded source queue.",
                )
                continue
            target_retention = queue_details[target_arn][2]
            if (
                source_retention is None
                or target_retention is None
                or target_retention <= source_retention
            ):
                _deny(
                    findings,
                    "sqs_dlq_retention_not_longer",
                    queue_details[target_arn][1],
                    "Dead-letter queue retention must exceed its source queue retention.",
                )
                continue
            redrive_pairs[arn] = target_arn
            redrive_targets[target_arn] = arn
        elif allow_raw not in (None, ""):
            allow = _json_document(allow_raw, findings, address)
            if allow is None:
                continue
            source_arns = allow.get("sourceQueueArns")
            if (
                set(allow) != {"redrivePermission", "sourceQueueArns"}
                or allow.get("redrivePermission") != "byQueue"
                or not isinstance(source_arns, list)
                or len(source_arns) != 1
                or not isinstance(source_arns[0], str)
            ):
                _deny(
                    findings,
                    "sqs_redrive_allow_policy_invalid",
                    address,
                    "A dead-letter queue must allow exactly its planned source queue.",
                )

    for start_arn in redrive_edges:
        visited: set[str] = set()
        current_arn = start_arn
        while current_arn in redrive_edges:
            if current_arn in visited:
                _deny(
                    findings,
                    "sqs_redrive_cycle_denied",
                    queue_details[start_arn][1],
                    "The planned SQS redrive policies contain a cycle.",
                )
                break
            visited.add(current_arn)
            current_arn = redrive_edges[current_arn]

    for source_arn, target_arn in redrive_pairs.items():
        source_address = queue_details[source_arn][1]
        target_item, target_address, _ = queue_details[target_arn]
        target_values = target_item["values"]
        allow = _json_document(
            target_values.get("redrive_allow_policy"), findings, target_address
        )
        if allow is None:
            continue
        if (
            set(allow) != {"redrivePermission", "sourceQueueArns"}
            or allow.get("redrivePermission") != "byQueue"
            or allow.get("sourceQueueArns") != [source_arn]
        ):
            _deny(
                findings,
                "sqs_redrive_allow_source_mismatch",
                target_address,
                "The dead-letter queue must allow only its exact planned source queue.",
            )
        if target_arn in redrive_pairs:
            _deny(
                findings,
                "sqs_redrive_cycle_denied",
                source_address,
                "A planned dead-letter queue cannot itself redrive messages to another queue.",
            )

    for arn, (item, address, _) in queue_details.items():
        values = item["values"]
        if (
            arn not in redrive_pairs
            and arn not in redrive_targets
            and arn not in eventbridge_dlq_targets
        ):
            _deny(
                findings,
                "sqs_redrive_contract_missing",
                address,
                "Every planned SQS queue must be a bounded source queue or its paired dead-letter queue.",
            )
        if arn in redrive_pairs and values.get("redrive_allow_policy") not in (None, ""):
            _deny(
                findings,
                "sqs_queue_source_and_dlq_denied",
                address,
                "A planned queue cannot be both a retry source and a dead-letter target.",
            )
        if arn in redrive_targets and values.get("redrive_policy") not in (None, ""):
            _deny(
                findings,
                "sqs_queue_source_and_dlq_denied",
                address,
                "A planned queue cannot be both a retry source and a dead-letter target.",
            )

    _check_sqs_lambda_consumers(
        document,
        resources,
        queue_by_arn,
        findings,
        expected_account_id,
        expected_region,
    )


def _check_step_functions_role_scope(
    document: dict[str, Any],
    resources: tuple[dict[str, Any], ...],
    findings: list[PlanPolicyFinding],
    expected_account_id: str,
    expected_region: str,
) -> None:
    """Bound Standard workflows to exact same-plan Lambda invokes and role grants."""
    configured = _configured_resource_references(document)
    by_type: dict[str, list[dict[str, Any]]] = {}
    for item in resources:
        kind = item.get("type")
        if isinstance(kind, str):
            by_type.setdefault(kind, []).append(item)

    for machine in by_type.get("aws_sfn_state_machine", []):
        address = machine.get("address")
        values = machine.get("values")
        if not isinstance(address, str) or not isinstance(values, dict):
            _deny(
                findings,
                "step_functions_configuration_unknown",
                address,
                "The state machine is missing required plan values.",
            )
            continue
        if values.get("type") != "STANDARD":
            _deny(
                findings,
                "step_functions_type_unsupported",
                address,
                "Only Standard state machines are covered by the current execution policy.",
            )
            continue
        if not _aws_arn_matches(
            values.get("arn"), "states", expected_region, expected_account_id, "stateMachine:"
        ):
            _deny(
                findings,
                "step_functions_scope_mismatch",
                address,
                "The state machine ARN must match the approved account and region.",
            )
            continue
        if values.get("logging_configuration") not in (None, [], {}):
            _deny(
                findings,
                "step_functions_logging_unsupported",
                address,
                "State machine logging requires a separately reviewed log policy.",
            )
            continue

        definition = values.get("definition")
        try:
            asl = json.loads(definition) if isinstance(definition, str) else None
        except (json.JSONDecodeError, RecursionError):
            asl = None
        task_arns = _step_functions_lambda_tasks(asl)
        if task_arns is None or not task_arns:
            _deny(
                findings,
                "step_functions_definition_unsupported",
                address,
                "The state machine must use a known definition with direct Lambda task ARNs only.",
            )
            continue
        if not all(
            _aws_arn_matches(arn, "lambda", expected_region, expected_account_id, "function:")
            for arn in task_arns
        ):
            _deny(
                findings,
                "step_functions_task_scope_mismatch",
                address,
                "Lambda task ARNs must match the approved account and region.",
            )
            continue

        state_refs = configured.get(address, ())
        role_candidates = [
            role
            for role in by_type.get("aws_iam_role", [])
            if any(
                _reference_targets_resource(reference, role.get("address", ""), "aws_iam_role")
                for reference in state_refs
            )
        ]
        if len(role_candidates) != 1:
            _deny(
                findings,
                "step_functions_role_unbound",
                address,
                "The state machine must reference exactly one planned IAM execution role.",
            )
            continue

        lambda_arns = {
            item.get("values", {}).get("arn")
            for item in by_type.get("aws_lambda_function", [])
            if isinstance(item.get("values"), dict)
        }
        if not task_arns <= lambda_arns:
            _deny(
                findings,
                "step_functions_task_unplanned",
                address,
                "Every direct Lambda task must target a function in this plan.",
            )
            continue

        role = role_candidates[0]
        role_address = role.get("address")
        role_values = role.get("values")
        role_arn = role_values.get("arn") if isinstance(role_values, dict) else None
        role_name = role_values.get("name") if isinstance(role_values, dict) else None
        if (
            not isinstance(role_address, str)
            or not isinstance(role_arn, str)
            or not _aws_arn_matches(role_arn, "iam", "", expected_account_id, "role/")
            or values.get("role_arn") != role_arn
        ):
            _deny(
                findings,
                "step_functions_role_unbound",
                address,
                "The execution role must have a known planned ARN.",
            )
            continue
        role_trust = _json_document(role_values.get("assume_role_policy"), findings, role_address)
        state_machine_arn = values.get("arn")
        if (
            role_trust is None
            or not isinstance(state_machine_arn, str)
            or not _step_functions_role_trust_is_exact(
                role_trust, state_machine_arn, expected_account_id
            )
        ):
            _deny(
                findings,
                "step_functions_role_trust_invalid",
                role_address,
                "The execution role must trust only the Step Functions service.",
            )
            continue

        granted: set[str] = set()
        unsupported = False
        for policy_resource in by_type.get("aws_iam_role_policy", []):
            policy_address = policy_resource.get("address")
            policy_values = policy_resource.get("values")
            if not isinstance(policy_address, str) or not isinstance(policy_values, dict):
                continue
            references = configured.get(policy_address, ())
            bound = (
                any(
                    _reference_targets_resource(reference, role_address, "aws_iam_role")
                    for reference in references
                )
                or policy_values.get("role") == role_name
            )
            if not bound:
                continue
            if policy_values.get("role") != role_name:
                unsupported = True
                _deny(
                    findings,
                    "step_functions_role_scope_invalid",
                    policy_address,
                    "The inline policy must attach to the referenced execution role.",
                )
                continue
            policy = _json_document(policy_values.get("policy"), findings, policy_address)
            if policy is None:
                unsupported = True
                continue
            for statement in _statements(policy, require_resource=True):
                effect = statement.get("Effect")
                if str(effect).lower() == "deny":
                    continue
                actions = {item.lower() for item in _string_list(statement.get("Action"))}
                statement_resources = set(_string_list(statement.get("Resource")))
                if (
                    str(effect).lower() != "allow"
                    or actions != {"lambda:invokefunction"}
                    or not statement_resources
                    or not statement_resources <= task_arns
                    or "Condition" in statement
                    or "NotAction" in statement
                    or "NotResource" in statement
                ):
                    unsupported = True
                    _deny(
                        findings,
                        "step_functions_role_scope_invalid",
                        policy_address,
                        "The state machine role may grant only direct Lambda invocation on its exact planned task functions.",
                    )
                    continue
                granted.update(statement_resources)

        for attachment in (
            *by_type.get("aws_iam_role_policy_attachment", []),
            *by_type.get("aws_iam_policy_attachment", []),
        ):
            attachment_address = attachment.get("address")
            references = (
                configured.get(attachment_address, ())
                if isinstance(attachment_address, str)
                else ()
            )
            attachment_values = attachment.get("values")
            attached_to_role = any(
                _reference_targets_resource(reference, role_address, "aws_iam_role")
                for reference in references
            ) or (
                isinstance(attachment_values, dict)
                and (
                    attachment_values.get("role_arn") == role_arn
                    or attachment_values.get("role") == role_name
                    or role_name in _string_list(attachment_values.get("roles"))
                )
            )
            if attached_to_role:
                unsupported = True
                _deny(
                    findings,
                    "step_functions_managed_policy_unverified",
                    attachment_address,
                    "Managed policies attached to a state machine role are not covered by this policy.",
                )

        definition_references = set(state_refs)
        task_resources_bound = all(
            any(
                _reference_targets_resource(
                    reference, item.get("address", ""), "aws_lambda_function"
                )
                for reference in definition_references
            )
            for item in by_type.get("aws_lambda_function", [])
            if isinstance(item.get("values"), dict) and item["values"].get("arn") in task_arns
        )
        if unsupported or not task_resources_bound or not task_arns <= granted:
            _deny(
                findings,
                "step_functions_invoke_permission_missing",
                address,
                "The execution role must grant exact Lambda invoke access for every task in the state machine.",
            )


def _step_functions_lambda_tasks(asl: Any) -> set[str] | None:
    """Return direct Lambda task ARNs; return None for unsupported ASL shapes."""
    if not isinstance(asl, dict) or not isinstance(asl.get("States"), dict):
        return None
    tasks: set[str] = set()
    pending = [asl["States"]]
    while pending:
        states = pending.pop()
        if not isinstance(states, dict):
            return None
        for state in states.values():
            if not isinstance(state, dict) or not isinstance(state.get("Type"), str):
                return None
            state_type = state["Type"]
            if state_type == "Task":
                if "Credentials" in state:
                    return None
                resource_arn = state.get("Resource")
                if not isinstance(resource_arn, str) or not resource_arn.startswith("arn:"):
                    return None
                tasks.add(resource_arn)
            elif state_type not in {
                "Pass",
                "Succeed",
                "Fail",
                "Wait",
                "Choice",
            }:
                return None
    return tasks


def _step_functions_role_trust_is_exact(
    policy: dict[str, Any], state_machine_arn: str, account_id: str
) -> bool:
    statements = _statements(policy, require_resource=False)
    allows = [
        statement for statement in statements if str(statement.get("Effect", "")).lower() == "allow"
    ]
    return bool(allows) and all(
        {item.lower() for item in _string_list(statement.get("Action"))} == {"sts:assumerole"}
        and isinstance(statement.get("Principal"), dict)
        and set(_string_list(statement["Principal"].get("Service"))) == {"states.amazonaws.com"}
        and statement.get("Condition")
        == {
            "ArnEquals": {"aws:SourceArn": state_machine_arn},
            "StringEquals": {"aws:SourceAccount": account_id},
        }
        for statement in allows
    )


def _aws_arn_matches(
    value: Any, service: str, region: str, account_id: str, resource_prefix: str
) -> bool:
    if not isinstance(value, str):
        return False
    parts = value.split(":", maxsplit=5)
    return (
        len(parts) == 6
        and parts[0] == "arn"
        and bool(parts[1])
        and parts[2] == service
        and parts[3] == region
        and parts[4] == account_id
        and parts[5].startswith(resource_prefix)
    )


def _check_sqs_lambda_consumers(
    document: dict[str, Any],
    resources: tuple[dict[str, Any], ...],
    queue_by_arn: dict[str, dict[str, Any]],
    findings: list[PlanPolicyFinding],
    expected_account_id: str,
    expected_region: str,
) -> None:
    configured = _configured_resource_references(document)
    by_type: dict[str, list[dict[str, Any]]] = {}
    for item in resources:
        kind = item.get("type")
        address = item.get("address")
        if isinstance(kind, str) and isinstance(address, str):
            by_type.setdefault(kind, []).append(item)

    mappings = by_type.get("aws_lambda_event_source_mapping", [])
    for mapping in mappings:
        address = mapping.get("address")
        values = mapping.get("values")
        if not isinstance(address, str) or not isinstance(values, dict):
            _deny(
                findings,
                "sqs_lambda_mapping_unknown",
                address,
                "The SQS Lambda event source mapping is missing required plan values.",
            )
            continue
        references = configured.get(address, ())
        queue_candidates = [
            item
            for item in by_type.get("aws_sqs_queue", [])
            if any(
                _reference_targets_resource(reference, item["address"], "aws_sqs_queue")
                for reference in references
            )
        ]
        function_candidates = [
            item
            for item in by_type.get("aws_lambda_function", [])
            if any(
                _reference_targets_resource(reference, item["address"], "aws_lambda_function")
                for reference in references
            )
        ]
        if len(queue_candidates) != 1 or len(function_candidates) != 1:
            _deny(
                findings,
                "sqs_lambda_mapping_unbound",
                address,
                "The SQS Lambda mapping must reference exactly one planned queue and one planned function.",
            )
            continue

        queue = queue_candidates[0]
        function = function_candidates[0]
        queue_values = queue.get("values")
        function_values = function.get("values")
        queue_address = queue.get("address")
        function_address = function.get("address")
        if (
            not isinstance(queue_values, dict)
            or not isinstance(function_values, dict)
            or not isinstance(queue_address, str)
            or not isinstance(function_address, str)
        ):
            _deny(
                findings,
                "sqs_lambda_mapping_unbound",
                address,
                "The SQS Lambda mapping target resources are incomplete.",
            )
            continue

        queue_arn = _sqs_queue_arn(
            queue_values.get("name"), expected_account_id, expected_region
        )
        if queue_arn is None or queue_arn not in queue_by_arn:
            _deny(
                findings,
                "sqs_lambda_queue_unplanned",
                address,
                "The SQS Lambda mapping source must be an exact queue in this plan.",
            )
            continue
        mapping_queue_arn = values.get("event_source_arn")
        if isinstance(mapping_queue_arn, str) and mapping_queue_arn != queue_arn:
            _deny(
                findings,
                "sqs_lambda_queue_reference_mismatch",
                address,
                "The SQS Lambda mapping does not target its referenced queue.",
            )
        mapping_function_name = values.get("function_name")
        planned_function_name = function_values.get("function_name")
        if (
            isinstance(mapping_function_name, str)
            and isinstance(planned_function_name, str)
            and mapping_function_name != planned_function_name
        ):
            _deny(
                findings,
                "sqs_lambda_function_reference_mismatch",
                address,
                "The SQS Lambda mapping does not target its referenced function.",
            )
        if values.get("enabled", True) is not True:
            _deny(
                findings,
                "sqs_lambda_mapping_disabled",
                address,
                "An SQS consumer mapping must be enabled in the proposed deployment.",
            )

        timeout = _integer(function_values.get("timeout"))
        visibility = _integer(queue_values.get("visibility_timeout_seconds"))
        window = _integer(values.get("maximum_batching_window_in_seconds", 0))
        if (
            timeout is None
            or not 1 <= timeout <= 900
            or visibility is None
            or window is None
            or not 0 <= window <= 300
            or visibility < 6 * timeout + window
        ):
            _deny(
                findings,
                "sqs_lambda_visibility_timeout_insufficient",
                address,
                "Queue visibility must be at least six times the known Lambda timeout plus its batch window.",
            )

        role_references = configured.get(function_address, ())
        role_candidates = [
            item
            for item in by_type.get("aws_iam_role", [])
            if any(
                _reference_targets_resource(reference, item["address"], "aws_iam_role")
                for reference in role_references
            )
        ]
        if len(role_candidates) != 1:
            _deny(
                findings,
                "sqs_lambda_role_unbound",
                function_address,
                "The Lambda function must reference exactly one planned execution role.",
            )
            continue
        role = role_candidates[0]
        role_address = role.get("address")
        role_values = role.get("values")
        if not isinstance(role_address, str) or not isinstance(role_values, dict):
            _deny(
                findings,
                "sqs_lambda_role_unbound",
                function_address,
                "The Lambda execution role is missing required plan values.",
            )
            continue

        if not _sqs_lambda_role_grants_queue(
            resources,
            configured,
            role_address,
            role_values.get("name"),
            queue_arn,
            findings,
            address,
        ):
            _deny(
                findings,
                "sqs_lambda_consumer_permission_missing",
                address,
                "The Lambda execution role must grant receive, delete, and queue-attribute access on this exact SQS queue.",
            )


def _sqs_lambda_role_grants_queue(
    resources: tuple[dict[str, Any], ...],
    configured_references: dict[str, tuple[str, ...]],
    role_address: str,
    role_name: Any,
    queue_arn: str,
    findings: list[PlanPolicyFinding],
    mapping_address: str,
) -> bool:
    required_actions = {
        "sqs:receivemessage",
        "sqs:deletemessage",
        "sqs:getqueueattributes",
    }
    allowed_actions = required_actions | {"sqs:changemessagevisibility"}
    granted: set[str] = set()
    for item in resources:
        if item.get("type") != "aws_iam_role_policy":
            continue
        address = item.get("address")
        values = item.get("values")
        if not isinstance(address, str) or not isinstance(values, dict):
            continue
        references = configured_references.get(address, ())
        references_role = any(
            _reference_targets_resource(reference, role_address, "aws_iam_role")
            for reference in references
        )
        if not references_role and values.get("role") != role_name:
            continue
        policy = _json_document(values.get("policy"), findings, address)
        if policy is None:
            continue
        for statement in _statements(policy, require_resource=True):
            actions = {action.lower() for action in _string_list(statement.get("Action"))}
            sqs_actions = {action for action in actions if action.startswith("sqs:")}
            if not sqs_actions:
                continue
            resources_scoped = _string_list(statement.get("Resource"))
            if (
                statement.get("Effect") == "Deny"
                and any(
                    fnmatchcase(required, pattern)
                    for pattern in actions
                    for required in required_actions
                )
                and (queue_arn in resources_scoped or "*" in resources_scoped)
            ):
                _deny(
                    findings,
                    "sqs_lambda_consumer_explicit_deny",
                    mapping_address,
                    "The Lambda execution role explicitly denies a required SQS consumer action.",
                )
                continue
            if statement.get("Effect") != "Allow":
                continue
            if (
                not sqs_actions <= allowed_actions
                or resources_scoped != (queue_arn,)
                or "Condition" in statement
            ):
                _deny(
                    findings,
                    "sqs_lambda_consumer_scope_invalid",
                    address,
                    "SQS consumer permissions must name only required actions and the exact queue ARN without conditions.",
                )
                continue
            granted.update(sqs_actions)
    return required_actions <= granted


def _check_lambda_permissions(
    resources: tuple[dict[str, Any], ...], findings: list[PlanPolicyFinding]
) -> None:
    for item in resources:
        if item.get("type") != "aws_lambda_permission":
            continue
        values = item.get("values")
        address = item.get("address")
        if not isinstance(values, dict):
            _deny(
                findings,
                "lambda_permission_unknown",
                address,
                "The function access permission is missing or unknown.",
            )
            continue
        principal = values.get("principal")
        if not isinstance(principal, str) or not principal:
            _deny(
                findings,
                "lambda_permission_principal_unknown",
                address,
                "The function access principal is missing or unknown.",
            )
            continue
        if principal.strip() != "*":
            continue
        source_arn = values.get("source_arn")
        if not isinstance(source_arn, str) or not source_arn.strip() or source_arn.strip() == "*":
            _deny(
                findings,
                "lambda_unscoped_public_invoke_denied",
                address,
                "The plan grants public function invocation without a scoped source.",
            )
        else:
            _review(
                findings,
                "lambda_public_invoke_review",
                address,
                "The plan permits wildcard-principal function invocation with a source restriction; confirm the source is intended.",
            )


def _check_api_gateway_routes(
    document: dict[str, Any],
    resources: tuple[dict[str, Any], ...],
    proposal: GeneratedDeploymentProposal,
    findings: list[PlanPolicyFinding],
) -> None:
    authenticated_types = {"JWT", "AWS_IAM", "CUSTOM"}
    planned_by_address = {item.get("address"): item for item in resources}
    proposal_by_id = {item.resource_id: item for item in proposal.resources}
    configured_references = _configured_resource_references(document)
    for item in resources:
        if item.get("type") != "aws_apigatewayv2_route":
            continue
        values = item.get("values")
        address = item.get("address")
        route_references = configured_references.get(address, ())
        route_proposal = next(
            (
                candidate
                for candidate in proposal.resources
                if candidate.resource_type == "aws_apigatewayv2_route"
                and f"{candidate.resource_type}.{candidate.name}" == address
            ),
            None,
        )
        api_reference = route_proposal.arguments.get("api_id") if route_proposal else None
        api_proposal = (
            proposal_by_id.get(api_reference.get("resource_id"))
            if isinstance(api_reference, dict)
            and api_reference.get("kind") == "resource_reference"
            and api_reference.get("output_name") == "id"
            else None
        )
        expected_api_address = (
            f"{api_proposal.resource_type}.{api_proposal.name}" if api_proposal else None
        )
        api_references = tuple(
            reference
            for reference in route_references
            if reference.startswith("aws_apigatewayv2_api.")
        )
        planned_api = planned_by_address.get(expected_api_address)
        if (
            api_proposal is None
            or api_proposal.resource_type != "aws_apigatewayv2_api"
            or not any(output.name == "id" for output in api_proposal.outputs)
            or api_references != (f"{expected_api_address}.id",)
            or not isinstance(planned_api, dict)
            or planned_api.get("type") != "aws_apigatewayv2_api"
            or not isinstance(values, dict)
            or not isinstance(values.get("api_id"), str)
            or not values.get("api_id")
        ):
            _deny(
                findings,
                "api_gateway_route_target_not_owned",
                address,
                "The API route must reference exactly one API included in this deployment.",
            )
        authorization_type = values.get("authorization_type") if isinstance(values, dict) else None
        if not isinstance(authorization_type, str) or authorization_type not in authenticated_types | {"NONE"}:
            _deny(
                findings,
                "api_gateway_route_authorization_unknown",
                address,
                "DavDeploy could not verify the authorization configured for this API route.",
            )
        elif authorization_type == "NONE":
            _review(
                findings,
                "api_gateway_open_route_review",
                address,
                "This API route allows open access. Confirm that public access is required before approval.",
            )


def _check_iam_permissions(
    policy: dict[str, Any],
    address: Any,
    expected_account_id: str,
    findings: list[PlanPolicyFinding],
) -> None:
    for statement in _statements(policy, require_resource=True):
        if str(statement.get("Effect", "")).lower() != "allow":
            continue
        if "NotResource" in statement:
            _deny(
                findings,
                "iam_not_resource_policy_denied",
                address,
                "An IAM allow policy uses NotResource, so its effective resource scope cannot be safely bounded.",
            )
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
        if any(
            fnmatchcase(secret_action.lower(), action.lower())
            for action in actions
            for secret_action in SECRET_VALUE_READ_ACTIONS
        ):
            _deny(
                findings,
                "iam_secret_value_read_unbound",
                address,
                "The plan grants secret value reads that are not bound to a verified secret reference.",
            )
        wildcard_resource = any("*" in item or "?" in item for item in resources)
        pass_role = "iam:passrole" in normalized_actions
        broad_assume_role = any(
            action == "sts:*"
            or action.startswith("sts:assume") and action != "sts:assumerole"
            for action in normalized_actions
        )
        if broad_assume_role:
            _deny(
                findings,
                "sts_assume_role_unbounded_denied",
                address,
                "The plan uses a wildcard role-assumption action that cannot be safely bounded.",
            )
            continue
        if any("*" in action or "?" in action for action in actions):
            _deny(
                findings,
                "iam_privileged_wildcard",
                address,
                "The plan grants wildcard IAM permissions. Name each required action explicitly.",
            )
            continue
        if any(
            action.startswith(("s3:", "sqs:", "dynamodb:"))
            for action in normalized_actions
        ) and any(_unbounded_data_resource(resource) for resource in resources):
            _deny(
                findings,
                "iam_data_resource_unbounded",
                address,
                "The plan grants data-service access outside an exact bucket, queue, table, or table index scope.",
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
        if assume_role:
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


def _unbounded_data_resource(resource: str, service: str | None = None) -> bool:
    """Allow complete data ARNs and only the exact S3/DynamoDB child scopes."""
    partition = r"aws(?:-[a-z0-9-]+)?"
    bucket = r"[a-z0-9](?:[a-z0-9.-]{1,61}[a-z0-9])"
    allowed_patterns = {
        "s3": (
            rf"arn:{partition}:s3:::{bucket}(?:/[^*?]+)?",
            rf"arn:{partition}:s3:::{bucket}/\*",
        ),
        "sqs": (
            rf"arn:{partition}:sqs:[a-z0-9-]+:\d{{12}}:(?:[A-Za-z0-9_-]{{1,80}}|[A-Za-z0-9_-]{{1,75}}\.fifo)",
        ),
        "dynamodb": (
            rf"arn:{partition}:dynamodb:[a-z0-9-]+:\d{{12}}:table/[A-Za-z0-9_.-]{{3,255}}",
            rf"arn:{partition}:dynamodb:[a-z0-9-]+:\d{{12}}:table/[A-Za-z0-9_.-]{{3,255}}/index/[A-Za-z0-9_.-]{{3,255}}",
            rf"arn:{partition}:dynamodb:[a-z0-9-]+:\d{{12}}:table/[A-Za-z0-9_.-]{{3,255}}/index/\*",
        ),
    }
    patterns = (
        allowed_patterns.get(service, ())
        if service is not None
        else tuple(pattern for group in allowed_patterns.values() for pattern in group)
    )
    return not any(re.fullmatch(pattern, resource) for pattern in patterns)


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
        if network.is_global:
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
            continue
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
