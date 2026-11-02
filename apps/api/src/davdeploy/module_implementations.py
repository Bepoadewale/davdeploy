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
    "aws-dns-zone": ModuleImplementation("aws-dns-zone", ("aws_route53_zone",), "modules/dns-zone"),
    "aws-acm-certificate": ModuleImplementation("aws-acm-certificate", ("aws_acm_certificate",), "modules/acm-certificate"),
    "aws-kms-key": ModuleImplementation("aws-kms-key", ("aws_kms_key", "aws_kms_alias"), "modules/kms-key"),
    "aws-parameter-config": ModuleImplementation("aws-parameter-config", ("aws_ssm_parameter",), "modules/parameter-config"),
    "aws-feature-flags": ModuleImplementation("aws-feature-flags", ("aws_appconfig_application", "aws_appconfig_environment"), "modules/feature-flags"),
    "aws-s3-private-storage": ModuleImplementation("aws-s3-private-storage", ("aws_s3_bucket", "aws_s3_bucket_public_access_block"), "modules/artifacts"),
    "aws-cloudfront-delivery": ModuleImplementation("aws-cloudfront-delivery", ("aws_cloudfront_distribution",), "modules/cloudfront-delivery"),
    "aws-api-gateway-http": ModuleImplementation("aws-api-gateway-http", ("aws_apigatewayv2_api", "aws_apigatewayv2_stage"), "modules/api-gateway-http"),
    "aws-lambda-service": ModuleImplementation("aws-lambda-service", ("aws_lambda_function",), "modules/lambda-service"),
    "aws-ecr-image": ModuleImplementation("aws-ecr-image", ("aws_ecr_repository",), "modules/ecr"),
    "aws-aurora-postgres": ModuleImplementation("aws-aurora-postgres", ("aws_rds_cluster", "aws_rds_cluster_instance"), "modules/aurora-postgres"),
    "aws-dynamodb-table": ModuleImplementation("aws-dynamodb-table", ("aws_dynamodb_table",), "modules/dynamodb-table"),
    "aws-elasticache-redis": ModuleImplementation("aws-elasticache-redis", ("aws_elasticache_replication_group",), "modules/elasticache-redis"),
    "aws-opensearch": ModuleImplementation("aws-opensearch", ("aws_opensearch_domain",), "modules/opensearch"),
    "aws-efs-shared-storage": ModuleImplementation("aws-efs-shared-storage", ("aws_efs_file_system", "aws_efs_mount_target"), "modules/efs-shared-storage"),
    "aws-sqs-queue": ModuleImplementation("aws-sqs-queue", ("aws_sqs_queue",), "modules/sqs-queue"),
    "aws-eventbridge-bus": ModuleImplementation("aws-eventbridge-bus", ("aws_cloudwatch_event_bus",), "modules/eventbridge-bus"),
    "aws-step-functions": ModuleImplementation("aws-step-functions", ("aws_sfn_state_machine", "aws_iam_role"), "modules/step-functions"),
    "aws-sns-notifications": ModuleImplementation("aws-sns-notifications", ("aws_sns_topic", "aws_sns_topic_subscription"), "modules/sns-notifications"),
    "aws-ses-email": ModuleImplementation("aws-ses-email", ("aws_ses_domain_identity", "aws_ses_domain_dkim", "aws_ses_domain_mail_from"), "modules/ses-email"),
    "aws-bedrock-runtime": ModuleImplementation("aws-bedrock-runtime", ("aws_bedrock_guardrail",), "modules/bedrock-runtime"),
    "aws-bedrock-knowledge-base": ModuleImplementation("aws-bedrock-knowledge-base", ("aws_bedrockagent_knowledge_base",), "modules/bedrock-knowledge-base"),
    "aws-sagemaker-endpoint": ModuleImplementation("aws-sagemaker-endpoint", ("aws_sagemaker_endpoint", "aws_sagemaker_model"), "modules/sagemaker-endpoint"),
    "aws-kinesis-stream": ModuleImplementation("aws-kinesis-stream", ("aws_kinesis_stream",), "modules/kinesis-stream"),
    "aws-batch-compute": ModuleImplementation("aws-batch-compute", ("aws_batch_compute_environment", "aws_batch_job_queue", "aws_batch_job_definition"), "modules/batch-compute"),
    "aws-eks-cluster": ModuleImplementation("aws-eks-cluster", ("aws_eks_cluster", "aws_eks_node_group"), "modules/eks"),
    "aws-ec2-autoscaling": ModuleImplementation("aws-ec2-autoscaling", ("aws_launch_template", "aws_autoscaling_group"), "modules/ec2-autoscaling"),
    "aws-vpc-private-network": ModuleImplementation("aws-vpc-private-network", ("aws_vpc", "aws_subnet", "aws_nat_gateway"), "modules/vpc"),
    "aws-site-to-site-vpn": ModuleImplementation("aws-site-to-site-vpn", ("aws_vpn_gateway_attachment", "aws_vpn_connection"), "modules/site-to-site-vpn"),
    "aws-multi-region-dns": ModuleImplementation("aws-multi-region-dns", ("aws_route53_health_check", "aws_route53_record"), "modules/multi-region-dns"),
}


def module_implementations() -> tuple[ModuleImplementation, ...]:
    return tuple(_IMPLEMENTATIONS.values())
