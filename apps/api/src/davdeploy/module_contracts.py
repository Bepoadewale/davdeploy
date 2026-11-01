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
    "aws-relational-data": (
        ("aws_rds_cluster", "aws_db_subnet_group", "aws_secretsmanager_secret"),
        ("private_subnets", "encryption", "backup_retention", "deletion_protection"),
        ("database_connections", "replication_lag", "backup_status"),
        False,
    ),
    "aws-nosql-data": (
        ("aws_dynamodb_table",),
        ("encryption", "point_in_time_recovery", "tag_scope"),
        ("read_throttle", "write_throttle", "table_size"),
        False,
    ),
    "aws-jobs-events": (
        ("aws_sqs_queue", "aws_cloudwatch_event_rule", "aws_sfn_state_machine"),
        ("dead_letter_queue", "retry_policy", "least_privilege_role"),
        ("queue_depth", "failed_executions", "dead_letters"),
        False,
    ),
    "aws-payments-webhooks": (
        (
            "aws_apigatewayv2_api",
            "aws_lambda_function",
            "aws_sqs_queue",
            "aws_secretsmanager_secret",
        ),
        ("signature_validation", "idempotency", "secret_references", "dead_letter_queue"),
        ("webhook_failures", "queue_depth"),
        False,
    ),
    "aws-realtime": (
        ("aws_apigatewayv2_api", "aws_dynamodb_table"),
        ("authenticated_connections", "connection_limits", "least_privilege_role"),
        ("active_connections", "message_errors"),
        False,
    ),
    "aws-ai-retrieval": (
        ("aws_bedrock_guardrail", "aws_s3_bucket", "aws_lambda_function"),
        ("model_allow_list", "guardrails", "data_boundary", "evaluation_required"),
        ("model_errors", "retrieval_latency", "guardrail_interventions"),
        False,
    ),
    "aws-managed-ml": (
        ("aws_sagemaker_endpoint", "aws_sagemaker_model", "aws_s3_bucket"),
        ("model_registry", "network_isolation", "model_monitoring"),
        ("endpoint_latency", "invocation_errors", "model_drift"),
        False,
    ),
    "aws-search": (
        ("aws_opensearch_domain", "aws_lambda_function"),
        ("private_access", "encryption", "index_access_policy"),
        ("cluster_health", "search_latency"),
        False,
    ),
    "aws-data-analytics": (
        ("aws_s3_bucket", "aws_glue_catalog_database", "aws_athena_workgroup"),
        ("encryption", "query_budget", "data_governance"),
        ("query_failures", "processed_bytes"),
        False,
    ),
    "aws-stream-processing": (
        ("aws_kinesis_stream", "aws_lambda_function"),
        ("retention_policy", "consumer_least_privilege", "backpressure_alarm"),
        ("iterator_age", "consumer_errors"),
        False,
    ),
    "aws-media": (
        ("aws_s3_bucket", "aws_mediaconvert_queue", "aws_cloudfront_distribution"),
        ("private_origin", "signed_delivery", "transcode_limits"),
        ("transcode_failures", "delivery_errors"),
        False,
    ),
    "aws-kubernetes-platform": (
        ("aws_eks_cluster", "aws_eks_node_group", "aws_iam_role", "argocd_application"),
        ("private_endpoint", "irsa", "gitops_review", "cluster_version_policy"),
        ("node_readiness", "workload_availability", "control_plane_health"),
        False,
    ),
    "aws-gpu-inference": (
        ("aws_sagemaker_endpoint", "aws_eks_node_group", "aws_iam_role"),
        ("quota_check", "accelerator_allow_list", "cost_ceiling", "image_provenance"),
        ("gpu_utilization", "inference_latency", "capacity_errors"),
        False,
    ),
    "aws-cpu-inference": (
        ("aws_ecs_service", "aws_sagemaker_endpoint", "aws_iam_role"),
        ("model_provenance", "cost_ceiling", "autoscaling_policy"),
        ("inference_latency", "invocation_errors"),
        False,
    ),
    "aws-private-connectivity": (
        ("aws_vpc", "aws_vpc_endpoint", "aws_vpn_connection"),
        ("private_routing", "restricted_egress", "network_audit"),
        ("connection_state", "egress_denials"),
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
