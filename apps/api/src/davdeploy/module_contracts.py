"""Typed desired-state contracts for universal DavDeploy modules.

These are plan contracts, not free-form Terraform or live execution permission.
"""

from __future__ import annotations

from davdeploy.domain import ArchitectureModule, ModuleContract

_CONTRACTS: dict[str, tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], bool]] = {
    "aws-edge-https": (
        ("aws_cloudfront_distribution", "aws_route53_record", "aws_wafv2_web_acl"),
        ("https_only", "managed_waf_rules", "tag_scope"),
        ("edge_availability", "waf_block_count"),
        False,
    ),
    "aws-static-web": (
        ("aws_s3_bucket", "aws_cloudfront_distribution"),
        ("block_public_s3", "origin_access_control", "tag_scope"),
        ("http_health", "cdn_error_rate"),
        False,
    ),
    "aws-serverless-api": (
        ("aws_lambda_function", "aws_apigatewayv2_api", "aws_iam_role"),
        ("least_privilege_role", "api_throttle", "secret_references"),
        ("lambda_errors", "api_latency"),
        False,
    ),
    "aws-managed-application": (
        ("aws_apprunner_service", "aws_ecr_repository", "aws_iam_role"),
        ("immutable_image", "least_privilege_role", "secret_references"),
        ("service_health", "http_health"),
        True,
    ),
    "aws-container-service": (
        ("aws_ecs_service", "aws_ecs_task_definition", "aws_lb", "aws_iam_role"),
        ("immutable_image", "private_subnets", "least_privilege_role"),
        ("task_health", "target_health"),
        False,
    ),
    "aws-identity": (
        ("aws_cognito_user_pool", "aws_cognito_user_pool_client"),
        ("mfa_policy", "token_rotation", "least_privilege_roles"),
        ("sign_in_failures", "mfa_challenges"),
        False,
    ),
    "aws-file-storage": (
        ("aws_s3_bucket", "aws_s3_bucket_public_access_block"),
        ("encryption", "private_objects", "signed_uploads"),
        ("storage_bytes", "upload_failures"),
        False,
    ),
    "aws-observability": (
        ("aws_cloudwatch_log_group", "aws_cloudwatch_metric_alarm"),
        ("log_retention", "alarm_actions", "tag_scope"),
        ("availability", "latency", "errors"),
        False,
    ),
    "aws-secrets-config": (
        ("aws_secretsmanager_secret", "aws_ssm_parameter"),
        ("encryption", "reference_only", "least_privilege_read"),
        ("secret_access_denied", "rotation_status"),
        False,
    ),
}


def module_contracts(modules: list[ArchitectureModule]) -> list[ModuleContract]:
    """Build safe contracts for selected modules; unimplemented modules stay explicit."""

    result: list[ModuleContract] = []
    for module in modules:
        resources, controls, observation, destroy_supported = _CONTRACTS.get(
            module.identifier,
            (
                ("profile_specific_contract_pending",),
                ("policy_required",),
                ("observation_required",),
                False,
            ),
        )
        result.append(
            ModuleContract(
                module_id=module.identifier,
                version="2026-11-1",
                resources=list(resources),
                policy_controls=list(controls),
                observation=list(observation),
                destroy_supported=destroy_supported,
            )
        )
    return result
