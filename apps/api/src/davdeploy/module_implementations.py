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
    "aws-s3-private-storage": ModuleImplementation("aws-s3-private-storage", ("aws_s3_bucket", "aws_s3_bucket_public_access_block"), "modules/s3-private-storage"),
    "aws-cloudfront-delivery": ModuleImplementation("aws-cloudfront-delivery", ("aws_cloudfront_distribution", "aws_cloudfront_origin_access_control"), "modules/cloudfront-delivery"),
    "aws-api-gateway-http": ModuleImplementation("aws-api-gateway-http", ("aws_apigatewayv2_api", "aws_apigatewayv2_stage"), "modules/api-gateway-http"),
    "aws-lambda-service": ModuleImplementation("aws-lambda-service", ("aws_lambda_function", "aws_iam_role"), "modules/lambda-service"),
    "aws-ecr-image": ModuleImplementation("aws-ecr-image", ("aws_ecr_repository", "aws_ecr_lifecycle_policy"), "modules/ecr-image"),
    "aws-aurora-postgres": ModuleImplementation("aws-aurora-postgres", ("aws_rds_cluster", "aws_rds_cluster_instance"), "modules/aurora-postgres"),
    "aws-dynamodb-table": ModuleImplementation("aws-dynamodb-table", ("aws_dynamodb_table",), "modules/dynamodb-table"),
    "aws-elasticache-redis": ModuleImplementation("aws-elasticache-redis", ("aws_elasticache_replication_group",), "modules/elasticache-redis"),
    "aws-opensearch": ModuleImplementation("aws-opensearch", ("aws_opensearch_domain",), "modules/opensearch"),
    "aws-efs-shared-storage": ModuleImplementation("aws-efs-shared-storage", ("aws_efs_file_system", "aws_efs_mount_target"), "modules/efs-shared-storage"),
    "aws-sqs-queue": ModuleImplementation("aws-sqs-queue", ("aws_sqs_queue", "aws_sqs_queue_policy"), "modules/sqs-queue"),
    "aws-eventbridge-bus": ModuleImplementation("aws-eventbridge-bus", ("aws_cloudwatch_event_bus", "aws_cloudwatch_event_rule"), "modules/eventbridge-bus"),
    "aws-step-functions": ModuleImplementation("aws-step-functions", ("aws_sfn_state_machine", "aws_iam_role"), "modules/step-functions"),
    "aws-sns-notifications": ModuleImplementation("aws-sns-notifications", ("aws_sns_topic", "aws_sns_topic_subscription"), "modules/sns-notifications"),
    "aws-ses-email": ModuleImplementation("aws-ses-email", ("aws_ses_domain_identity", "aws_sesv2_configuration_set"), "modules/ses-email"),
}


def module_implementations() -> tuple[ModuleImplementation, ...]:
    return tuple(_IMPLEMENTATIONS.values())
