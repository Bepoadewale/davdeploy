from __future__ import annotations

import json

import pytest
from davdeploy.generated_deployment_contract import GeneratedDeploymentProposal
from davdeploy.generated_plan_ownership import PlanOwnershipScope, UntaggedResourceOwnershipRecord
from davdeploy.generated_plan_policy import (
    PlanPolicyVerdict,
    _check_rds_final_snapshot_changes,
    _configured_resources,
    _path_contains_unknown,
    _reference_targets_resource,
    evaluate_generated_plan_policy,
)

ACCOUNT = "654654474502"
REGION = "us-east-1"
_OMIT = object()


def ownership_scope():
    return PlanOwnershipScope(
        organization_id="org-test",
        workspace_id="workspace-test",
        project_id="project-test",
        environment_id="production",
        plan_id="plan-internal-id",
        revision_id="revision-internal-id",
    )


def s3_secure_transport_policy(bucket_name):
    bucket_arn = f"arn:aws:s3:::{bucket_name}"
    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:*",
                    "Resource": [bucket_arn, f"{bucket_arn}/*"],
                    "Condition": {
                        "Bool": {
                            "aws:SecureTransport": "false",
                            "aws:PrincipalIsAWSService": "false",
                        }
                    },
                }
            ],
        }
    )


def s3_default_encryption(algorithm="AES256"):
    return [
        {
            "apply_server_side_encryption_by_default": [
                {"sse_algorithm": algorithm}
            ]
        }
    ]


def s3_ownership_control(object_ownership="BucketOwnerEnforced"):
    return [{"object_ownership": object_ownership}]


def proposal(resources=None, *, backup_required=False):
    resources = resources or [
        {
            "resource_id": "bucket",
            "resource_type": "aws_s3_bucket",
            "name": "bucket",
            "arguments": {"bucket": "private-plan-bucket"},
            "rationale": "Private application file storage.",
        },
        {
            "resource_id": "public-access",
            "resource_type": "aws_s3_bucket_public_access_block",
            "name": "public_access",
            "arguments": {
                "bucket": {
                    "kind": "resource_reference",
                    "resource_id": "bucket",
                    "output_name": "id",
                    "value_type": "string",
                },
                "block_public_acls": True,
                "block_public_policy": True,
                "ignore_public_acls": True,
                "restrict_public_buckets": True,
            },
            "rationale": "Keep customer files private.",
        },
        {
            "resource_id": "secure-transport-policy",
            "resource_type": "aws_s3_bucket_policy",
            "name": "transport_policy",
            "arguments": {
                "bucket": {
                    "kind": "resource_reference",
                    "resource_id": "bucket",
                    "output_name": "id",
                    "value_type": "string",
                },
                "policy": s3_secure_transport_policy("private-plan-bucket"),
            },
            "rationale": "Deny unencrypted requests while preserving AWS service access.",
        },
        {
            "resource_id": "bucket-encryption",
            "resource_type": "aws_s3_bucket_server_side_encryption_configuration",
            "name": "encryption",
            "arguments": {
                "bucket": {
                    "kind": "resource_reference",
                    "resource_id": "bucket",
                    "output_name": "id",
                    "value_type": "string",
                },
                "rule": s3_default_encryption(),
            },
            "rationale": "Declare the default server-side encryption mode for stored objects.",
        },
        {
            "resource_id": "bucket-ownership",
            "resource_type": "aws_s3_bucket_ownership_controls",
            "name": "ownership",
            "arguments": {
                "bucket": {
                    "kind": "resource_reference",
                    "resource_id": "bucket",
                    "output_name": "id",
                    "value_type": "string",
                },
                "rule": s3_ownership_control(),
            },
            "rationale": "Disable ACLs and make the bucket owner responsible for every stored object.",
        },
    ]
    if resources[0]["resource_type"] == "aws_s3_bucket":
        resources[0]["outputs"] = [{"name": "id", "value_type": "string"}]
    return GeneratedDeploymentProposal.model_validate(
        {
            "contract_version": "1.1",
            "source_revision": "test-revision",
            "context_digest": "a" * 64,
            "requirements": {"region": REGION},
            "recovery": {"backup_required": backup_required},
            "resources": resources,
        }
    )


def resource(address, kind, values):
    if kind.startswith("aws_"):
        values = {**values, "tags": {**ownership_scope().tags(), **values.get("tags", {})}}
    return {"address": address, "mode": "managed", "type": kind, "values": values}


def change(address, kind, actions=("create",), **metadata):
    before = {"tags": ownership_scope().tags()} if any(
        action in actions for action in ("delete", "update", "no-op")
    ) else None
    after = {"tags": ownership_scope().tags()} if any(
        action in actions for action in ("create", "update", "no-op")
    ) else None
    return {
        "address": address,
        "type": kind,
        "change": {
            "actions": list(actions),
            "before": before,
            "after": after,
            "before_sensitive": False,
            "after_sensitive": False,
            "after_unknown": {},
            **metadata,
        },
    }


def plan(resources=None, changes=None, **overrides):
    resources = resources or [
        resource(
            "aws_s3_bucket.bucket",
            "aws_s3_bucket",
            {"bucket": "private-plan-bucket", "arn": "arn:aws:s3:::private-plan-bucket"},
        ),
        resource(
            "aws_s3_bucket_public_access_block.public_access",
            "aws_s3_bucket_public_access_block",
            {
                "bucket": "private-plan-bucket",
                "block_public_acls": True,
                "block_public_policy": True,
                "ignore_public_acls": True,
                "restrict_public_buckets": True,
            },
        ),
        resource(
            "aws_s3_bucket_policy.transport_policy",
            "aws_s3_bucket_policy",
            {
                "bucket": "private-plan-bucket",
                "policy": s3_secure_transport_policy("private-plan-bucket"),
            },
        ),
        resource(
            "aws_s3_bucket_server_side_encryption_configuration.encryption",
            "aws_s3_bucket_server_side_encryption_configuration",
            {
                "bucket": "private-plan-bucket",
                "rule": s3_default_encryption(),
            },
        ),
        resource(
            "aws_s3_bucket_ownership_controls.ownership",
            "aws_s3_bucket_ownership_controls",
            {
                "bucket": "private-plan-bucket",
                "rule": s3_ownership_control(),
            },
        ),
        resource("terraform_data.account_guard", "terraform_data", {"input": None}),
    ]
    changes = changes or [
        change("aws_s3_bucket.bucket", "aws_s3_bucket"),
        change("aws_s3_bucket_public_access_block.public_access", "aws_s3_bucket_public_access_block"),
        change("aws_s3_bucket_policy.transport_policy", "aws_s3_bucket_policy"),
        change(
            "aws_s3_bucket_server_side_encryption_configuration.encryption",
            "aws_s3_bucket_server_side_encryption_configuration",
        ),
        change("aws_s3_bucket_ownership_controls.ownership", "aws_s3_bucket_ownership_controls"),
        change("terraform_data.account_guard", "terraform_data"),
    ]
    document = {
        "format_version": "1.2",
        "applyable": True,
        "errored": False,
        "complete": True,
        "configuration": {
            "provider_config": {"aws": {"expressions": {"region": {"constant_value": REGION}}}}
        },
        "planned_values": {"root_module": {"resources": resources}},
        "resource_changes": changes,
    }
    document.update(overrides)
    return document


def evaluate(document=None, proposal_value=None):
    return evaluate_generated_plan_policy(
        document or plan(),
        proposal_value or proposal(),
        expected_account_id=ACCOUNT,
        expected_region=REGION,
        ownership_scope=ownership_scope(),
        trusted_configuration={
            "data": {"aws_caller_identity": {"trusted": {}}},
            "resource": {
                "terraform_data": {
                    "account_guard": {
                        "lifecycle": {
                            "precondition": {
                                "condition": '${data.aws_caller_identity.trusted.account_id == "'
                                + ACCOUNT
                                + '"}'
                            }
                        }
                    }
                }
            },
        },
    )


def plan_with_s3_transport_policy(policy):
    document = plan()
    policy_resource = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item.get("address") == "aws_s3_bucket_policy.transport_policy"
    )
    policy_resource["values"]["policy"] = policy
    proposal_resources = [
        item.model_dump(mode="json") for item in proposal().resources
    ]
    proposal_policy = next(
        item for item in proposal_resources if item["resource_id"] == "secure-transport-policy"
    )
    proposal_policy["arguments"]["policy"] = policy
    return document, proposal(proposal_resources)


def plan_with_s3_default_encryption(rule, *, configured_bucket="private-plan-bucket"):
    document = plan()
    encryption_resource = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item.get("type") == "aws_s3_bucket_server_side_encryption_configuration"
    )
    encryption_resource["values"]["bucket"] = configured_bucket
    encryption_resource["values"]["rule"] = rule
    proposal_resources = [
        item.model_dump(mode="json") for item in proposal().resources
    ]
    proposal_encryption = next(
        item for item in proposal_resources if item["resource_id"] == "bucket-encryption"
    )
    proposal_encryption["arguments"]["bucket"] = configured_bucket
    proposal_encryption["arguments"]["rule"] = rule
    return document, proposal(proposal_resources)


def plan_with_s3_ownership_control(rule, *, configured_bucket="private-plan-bucket"):
    document = plan()
    control_resource = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item.get("type") == "aws_s3_bucket_ownership_controls"
    )
    control_resource["values"]["bucket"] = configured_bucket
    control_resource["values"]["rule"] = rule
    proposal_resources = [
        item.model_dump(mode="json") for item in proposal().resources
    ]
    proposal_control = next(
        item for item in proposal_resources if item["resource_id"] == "bucket-ownership"
    )
    proposal_control["arguments"]["bucket"] = configured_bucket
    proposal_control["arguments"]["rule"] = rule
    return document, proposal(proposal_resources)


def add_policy_resource(document, kind, name, arguments, *, after_unknown=None):
    address = f"{kind}.{name}"
    document["planned_values"]["root_module"]["resources"].append(
        resource(address, kind, arguments)
    )
    unknown = after_unknown if after_unknown is not None else {}
    document["resource_changes"].append(
        change(address, kind, after_unknown=unknown)
    )
    resources = [item.model_dump(mode="json") for item in proposal().resources]

    resources.append(
        {
            "resource_id": name.replace("_", "-"),
            "resource_type": kind,
            "name": name,
            "arguments": arguments,
            "rationale": "Apply the requested compute configuration with bounded metadata access.",
        }
    )
    return proposal(resources)


def add_network_resource(document, kind, name, arguments, *, after_unknown=None):
    address = f"{kind}.{name}"
    document["planned_values"]["root_module"]["resources"].append(
        resource(address, kind, arguments)
    )
    changes = {}
    if after_unknown is not None:
        changes["after_unknown"] = after_unknown
    document["resource_changes"].append(change(address, kind, **changes))
    proposal_resources = [item.model_dump(mode="json") for item in proposal().resources]
    proposal_resources.append(
        {
            "resource_id": name.replace("_", "-"),
            "resource_type": kind,
            "name": name,
            "arguments": arguments,
            "rationale": "Apply a bounded network access rule for the application.",
        }
    )
    return proposal(proposal_resources)


def dynamodb_case(point_in_time_recovery=_OMIT, *, backup_required=False, after_unknown=None):
    table_values = {
        "name": "app-records",
        "server_side_encryption": {"enabled": True},
        "deletion_protection_enabled": True,
    }
    if point_in_time_recovery is not _OMIT:
        table_values["point_in_time_recovery"] = point_in_time_recovery
    table_address = "aws_dynamodb_table.records"
    document = plan()
    document["planned_values"]["root_module"]["resources"] = [
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "terraform_data"
    ]
    document["resource_changes"] = [
        item for item in document["resource_changes"] if item["type"] == "terraform_data"
    ]
    document["planned_values"]["root_module"]["resources"].append(
        resource(table_address, "aws_dynamodb_table", table_values)
    )
    metadata = {"after_unknown": after_unknown or {}}
    document["resource_changes"].append(
        change(table_address, "aws_dynamodb_table", **metadata)
    )
    proposal_value = proposal(
        [
            {
                "resource_id": "records",
                "resource_type": "aws_dynamodb_table",
                "name": "records",
                "arguments": {"name": "app-records"},
                "rationale": "Store application records.",
            }
        ],
        backup_required=backup_required,
    )
    return document, proposal_value


def add_sqs_queue_policy(document, policy, **change_metadata):
    address = "aws_sqs_queue_policy.queue_access"
    document["planned_values"]["root_module"]["resources"].append(
        resource(address, "aws_sqs_queue_policy", {"policy": policy})
    )
    document["resource_changes"].append(
        change(address, "aws_sqs_queue_policy", **change_metadata)
    )
    return document


def sqs_queue_case(sqs_managed_sse_enabled, *, after_unknown=None):
    document = plan()
    address = "aws_sqs_queue.queue"
    queue_arn = f"arn:aws:sqs:{REGION}:{ACCOUNT}:async-work"
    dlq_arn = f"arn:aws:sqs:{REGION}:{ACCOUNT}:async-work-dlq"
    values = {
        "name": "async-work",
        "sqs_managed_sse_enabled": sqs_managed_sse_enabled,
        "visibility_timeout_seconds": 360,
        "message_retention_seconds": 345600,
        "redrive_policy": json.dumps(
            {"deadLetterTargetArn": dlq_arn, "maxReceiveCount": 5}
        ),
    }
    document["planned_values"]["root_module"]["resources"].append(
        resource(address, "aws_sqs_queue", values)
    )
    document["resource_changes"].append(
        change(address, "aws_sqs_queue", after_unknown=after_unknown or {})
    )
    dlq_address = "aws_sqs_queue.dead_letter"
    dlq_values = {
        "name": "async-work-dlq",
        "sqs_managed_sse_enabled": True,
        "visibility_timeout_seconds": 30,
        "message_retention_seconds": 1209600,
        "redrive_allow_policy": json.dumps(
            {"redrivePermission": "byQueue", "sourceQueueArns": [queue_arn]}
        ),
    }
    document["planned_values"]["root_module"]["resources"].append(
        resource(dlq_address, "aws_sqs_queue", dlq_values)
    )
    document["resource_changes"].append(change(dlq_address, "aws_sqs_queue"))
    resources = [item.model_dump(mode="json") for item in proposal().resources]
    resources.extend(
        [
            {
                "resource_id": "queue",
                "resource_type": "aws_sqs_queue",
                "name": "queue",
                "arguments": {
                    "name": "async-work",
                    "sqs_managed_sse_enabled": sqs_managed_sse_enabled,
                },
                "rationale": "Use an encrypted queue with bounded retries.",
            },
            {
                "resource_id": "dead-letter",
                "resource_type": "aws_sqs_queue",
                "name": "dead_letter",
                "arguments": {
                    "name": "async-work-dlq",
                    "sqs_managed_sse_enabled": True,
                },
                "rationale": "Keep failed queue messages in a scoped dead-letter queue.",
            },
        ]
    )
    return document, proposal(resources)


def ecr_repository_case(*, values=None, after_unknown=None):
    address = "aws_ecr_repository.repository"
    repository_values = {
        "name": "davdeploy-test-images",
        "image_tag_mutability": "IMMUTABLE",
        "image_scanning_configuration": [{"scan_on_push": True}],
        "encryption_configuration": [{"encryption_type": "AES256"}],
        "force_delete": False,
    }
    repository_values.update(values or {})
    document = plan(
        resources=[
            resource(address, "aws_ecr_repository", repository_values),
            resource("terraform_data.account_guard", "terraform_data", {"input": None}),
        ],
        changes=[
            change(address, "aws_ecr_repository", after_unknown=after_unknown or {}),
            change("terraform_data.account_guard", "terraform_data"),
        ],
    )
    proposal_value = proposal(
        [
            {
                "resource_id": "repository",
                "resource_type": "aws_ecr_repository",
                "name": "repository",
                "arguments": repository_values,
                "rationale": "Store versioned application images in an encrypted private registry.",
            }
        ]
    )
    return document, proposal_value


def kms_key_case(*, values=None, after_unknown=None):
    address = "aws_kms_key.this"
    key_values = {
        "description": "DavDeploy managed key: test",
        "customer_master_key_spec": "SYMMETRIC_DEFAULT",
        "key_usage": "ENCRYPT_DECRYPT",
        "deletion_window_in_days": 30,
        "enable_key_rotation": True,
        "multi_region": False,
        "tags": {"Product": "davdeploy"},
    }
    key_values.update(values or {})
    document = plan(
        resources=[
            resource(address, "aws_kms_key", key_values),
            resource("terraform_data.account_guard", "terraform_data", {"input": None}),
        ],
        changes=[
            change(address, "aws_kms_key", after_unknown=after_unknown or {}),
            change("terraform_data.account_guard", "terraform_data"),
        ],
    )
    proposal_value = proposal(
        [
            {
                "resource_id": "key",
                "resource_type": "aws_kms_key",
                "name": "this",
                "arguments": key_values,
                "rationale": "Use a rotating symmetric key with a bounded deletion wait.",
            }
        ]
    )
    return document, proposal_value


def ssm_parameter_case(*, values=None, after_unknown=None):
    address = "aws_ssm_parameter.this"
    parameter_values = {
        "name": "/davdeploy/test/setting",
        "type": "SecureString",
        "tier": "Standard",
        "key_id": None,
        "value": "synthetic-test-value",
        "tags": {"Product": "davdeploy"},
    }
    parameter_values.update(values or {})
    document = plan(
        resources=[
            resource(address, "aws_ssm_parameter", parameter_values),
            resource("terraform_data.account_guard", "terraform_data", {"input": None}),
        ],
        changes=[
            change(address, "aws_ssm_parameter", after_unknown=after_unknown or {}),
            change("terraform_data.account_guard", "terraform_data"),
        ],
    )
    proposal_value = proposal(
        [
            {
                "resource_id": "parameter",
                "resource_type": "aws_ssm_parameter",
                "name": "this",
                "arguments": parameter_values,
                "rationale": "Store an encrypted Standard-tier configuration value.",
            }
        ]
    )
    return document, proposal_value


def opensearch_domain_case(*, values=None, after_unknown=None):
    address = "aws_opensearch_domain.this"
    domain_values = {
        "domain_name": "davdeploy-search-test",
        "engine_version": "OpenSearch_2.11",
        "cluster_config": [
            {
                "instance_type": "t3.small.search",
                "instance_count": 1,
                "zone_awareness_enabled": False,
            }
        ],
        "ebs_options": [
            {"ebs_enabled": True, "volume_type": "gp3", "volume_size": 10}
        ],
        "vpc_options": [
            {"subnet_ids": ["subnet-private"], "security_group_ids": ["sg-search"]}
        ],
        "encrypt_at_rest": [{"enabled": True}],
        "node_to_node_encryption": [{"enabled": True}],
        "domain_endpoint_options": [
            {
                "enforce_https": True,
                "tls_security_policy": "Policy-Min-TLS-1-2-2019-07",
            }
        ],
        "tags": {"Product": "davdeploy"},
    }
    domain_values.update(values or {})
    document = plan(
        resources=[
            resource(address, "aws_opensearch_domain", domain_values),
            resource("terraform_data.account_guard", "terraform_data", {"input": None}),
        ],
        changes=[
            change(address, "aws_opensearch_domain", after_unknown=after_unknown or {}),
            change("terraform_data.account_guard", "terraform_data"),
        ],
    )
    proposal_value = proposal(
        [
            {
                "resource_id": "search",
                "resource_type": "aws_opensearch_domain",
                "name": "this",
                "arguments": domain_values,
                "rationale": "Use a bounded private encrypted search domain.",
            }
        ]
    )
    return document, proposal_value


def acm_certificate_case(*, values=None, after_unknown=None):
    address = "aws_acm_certificate.this"
    certificate_values = {
        "domain_name": "example.test",
        "validation_method": "DNS",
        "key_algorithm": "RSA_2048",
        "options": [{"export": "DISABLED"}],
        "tags": {"Product": "davdeploy"},
    }
    certificate_values.update(values or {})
    document = plan(
        resources=[
            resource(address, "aws_acm_certificate", certificate_values),
            resource("terraform_data.account_guard", "terraform_data", {"input": None}),
        ],
        changes=[
            change(address, "aws_acm_certificate", after_unknown=after_unknown or {}),
            change("terraform_data.account_guard", "terraform_data"),
        ],
    )
    proposal_value = proposal(
        [
            {
                "resource_id": "certificate",
                "resource_type": "aws_acm_certificate",
                "name": "this",
                "arguments": certificate_values,
                "rationale": "Request a non-exportable certificate with DNS validation.",
            }
        ]
    )
    return document, proposal_value


def sns_sqs_case():
    document, base_proposal = sqs_queue_case(True)
    topic_arn = f"arn:aws:sns:{REGION}:{ACCOUNT}:notifications"
    queue_arn = f"arn:aws:sqs:{REGION}:{ACCOUNT}:async-work"
    queue_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowExactSnsTopic",
                "Effect": "Allow",
                "Principal": {"Service": "sns.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "Resource": queue_arn,
                "Condition": {
                    "ArnEquals": {"aws:SourceArn": topic_arn},
                    "StringEquals": {"aws:SourceAccount": ACCOUNT},
                },
            }
        ],
    }
    planned = [
        (
            "aws_sns_topic.notifications",
            "aws_sns_topic",
            {"name": "notifications", "arn": topic_arn},
        ),
        (
            "aws_sqs_queue_policy.sns_publish",
            "aws_sqs_queue_policy",
            {
                "queue_url": f"https://sqs.{REGION}.amazonaws.com/{ACCOUNT}/async-work",
                "policy": json.dumps(queue_policy),
            },
        ),
        (
            "aws_sns_topic_subscription.to_queue",
            "aws_sns_topic_subscription",
            {
                "protocol": "sqs",
                "topic_arn": topic_arn,
                "endpoint": queue_arn,
                "raw_message_delivery": True,
            },
        ),
    ]
    proposal_resources = [item.model_dump(mode="json") for item in base_proposal.resources]
    for address, kind, values in planned:
        document["planned_values"]["root_module"]["resources"].append(
            resource(address, kind, values)
        )
        document["resource_changes"].append(change(address, kind))
        name = address.split(".", maxsplit=1)[1]
        proposal_resources.append(
            {
                "resource_id": name.replace("_", "-"),
                "resource_type": kind,
                "name": name,
                "arguments": values,
                "rationale": "Bind synthetic SNS notifications to the exact test queue.",
            }
        )
    return document, proposal(proposal_resources)


def eventbridge_sqs_case(*, include_source_account=False):
    document, base_proposal = sqs_queue_case(True)
    queue_arn = f"arn:aws:sqs:{REGION}:{ACCOUNT}:async-work"
    dead_letter_arn = f"arn:aws:sqs:{REGION}:{ACCOUNT}:eventbridge-delivery-dlq"
    rule_arn = f"arn:aws:events:{REGION}:{ACCOUNT}:rule/orders/route-orders"
    queue_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowExactEventBridgeRule",
                "Effect": "Allow",
                "Principal": {"Service": "events.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "Resource": queue_arn,
                "Condition": {
                    "ArnEquals": {"aws:SourceArn": rule_arn},
                    **(
                        {"StringEquals": {"aws:SourceAccount": ACCOUNT}}
                        if include_source_account
                        else {}
                    ),
                },
            }
        ],
    }
    dead_letter_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowExactEventBridgeRule",
                "Effect": "Allow",
                "Principal": {"Service": "events.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "Resource": dead_letter_arn,
                "Condition": {"ArnEquals": {"aws:SourceArn": rule_arn}},
            }
        ],
    }
    planned = [
        (
            "aws_cloudwatch_event_bus.orders",
            "aws_cloudwatch_event_bus",
            {"name": "orders"},
        ),
        (
            "aws_cloudwatch_event_rule.route_orders",
            "aws_cloudwatch_event_rule",
            {"name": "route-orders", "event_bus_name": "orders"},
        ),
        (
            "aws_cloudwatch_event_target.to_queue",
            "aws_cloudwatch_event_target",
            {
                "rule": "route-orders",
                "event_bus_name": "orders",
                "arn": queue_arn,
                "target_id": "orders-queue",
                "retry_policy": {
                    "maximum_retry_attempts": 0,
                    "maximum_event_age_in_seconds": 60,
                },
                "dead_letter_config": {"arn": dead_letter_arn},
            },
        ),
        (
            "aws_sqs_queue_policy.eventbridge_publish",
            "aws_sqs_queue_policy",
            {
                "queue_url": f"https://sqs.{REGION}.amazonaws.com/{ACCOUNT}/async-work",
                "policy": json.dumps(queue_policy),
            },
        ),
        (
            "aws_sqs_queue.eventbridge_dead_letter",
            "aws_sqs_queue",
            {
                "name": "eventbridge-delivery-dlq",
                "sqs_managed_sse_enabled": True,
                "visibility_timeout_seconds": 30,
                "message_retention_seconds": 1209600,
            },
        ),
        (
            "aws_sqs_queue_policy.eventbridge_dlq_publish",
            "aws_sqs_queue_policy",
            {
                "queue_url": f"https://sqs.{REGION}.amazonaws.com/{ACCOUNT}/eventbridge-delivery-dlq",
                "policy": json.dumps(dead_letter_policy),
            },
        ),
    ]
    proposal_resources = [item.model_dump(mode="json") for item in base_proposal.resources]
    for address, kind, values in planned:
        document["planned_values"]["root_module"]["resources"].append(
            resource(address, kind, values)
        )
        document["resource_changes"].append(change(address, kind))
        name = address.split(".", maxsplit=1)[1]
        proposal_resources.append(
            {
                "resource_id": name.replace("_", "-"),
                "resource_type": kind,
                "name": name,
                "arguments": values,
                "rationale": "Bind a planned EventBridge rule to its exact test queue.",
            }
        )
    return document, proposal(proposal_resources)


def test_ecr_repository_with_immutable_tags_encryption_and_scan_is_reviewable():
    document, proposal_value = ecr_repository_case()

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert not any(code.startswith("ecr_") for code in codes(result))


@pytest.mark.parametrize(
    ("values", "expected_code"),
    [
        ({"image_tag_mutability": "MUTABLE"}, "ecr_image_tags_must_be_immutable"),
        (
            {"image_scanning_configuration": [{"scan_on_push": False}]},
            "ecr_scan_on_push_required",
        ),
        (
            {"encryption_configuration": [{"encryption_type": "KMS"}]},
            "ecr_encryption_required",
        ),
        ({"force_delete": True}, "ecr_force_delete_denied"),
    ],
)
def test_ecr_repository_rejects_unsafe_configuration(values, expected_code):
    document, proposal_value = ecr_repository_case(values=values)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert expected_code in codes(result)


def test_ecr_repository_denies_unknown_safety_configuration():
    document, proposal_value = ecr_repository_case(
        values={"image_tag_mutability": None},
        after_unknown={"image_tag_mutability": True},
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)
    assert "ecr_image_tags_must_be_immutable" in codes(result)


@pytest.mark.parametrize(
    ("values", "after_unknown", "expected_code"),
    [
        (
            {"image_scanning_configuration": [{"scan_on_push": None}]},
            {"image_scanning_configuration": [{"scan_on_push": True}]},
            "ecr_scan_on_push_required",
        ),
        (
            {"encryption_configuration": [{"encryption_type": None}]},
            {"encryption_configuration": [{"encryption_type": True}]},
            "ecr_encryption_required",
        ),
        ({"force_delete": None}, {"force_delete": True}, "ecr_force_delete_denied"),
    ],
)
def test_ecr_repository_denies_unknown_scanning_encryption_or_force_delete(
    values, after_unknown, expected_code
):
    document, proposal_value = ecr_repository_case(
        values=values,
        after_unknown=after_unknown,
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)
    assert expected_code in codes(result)


def test_kms_key_with_supported_safety_settings_is_reviewable():
    document, proposal_value = kms_key_case()

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert not any(code.startswith("kms_") for code in codes(result))


@pytest.mark.parametrize(
    ("values", "expected_code"),
    [
        (
            {"customer_master_key_spec": "RSA_2048"},
            "kms_key_must_be_symmetric",
        ),
        ({"key_usage": "SIGN_VERIFY"}, "kms_key_usage_invalid"),
        ({"enable_key_rotation": False}, "kms_key_rotation_required"),
        ({"deletion_window_in_days": 7}, "kms_key_deletion_window_too_short"),
        ({"multi_region": True}, "kms_multi_region_unsupported"),
    ],
)
def test_kms_key_rejects_unsupported_or_weakened_settings(values, expected_code):
    document, proposal_value = kms_key_case(values=values)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert expected_code in codes(result)


@pytest.mark.parametrize(
    ("attribute", "expected_code", "unknown_value"),
    [
        ("customer_master_key_spec", "kms_key_must_be_symmetric", True),
        ("key_usage", "kms_key_usage_invalid", True),
        ("enable_key_rotation", "kms_key_rotation_required", True),
        ("deletion_window_in_days", "kms_key_deletion_window_too_short", True),
        ("multi_region", "kms_multi_region_unsupported", True),
    ],
)
def test_kms_key_denies_unknown_safety_settings(attribute, expected_code, unknown_value):
    document, proposal_value = kms_key_case(
        values={attribute: None},
        after_unknown={attribute: unknown_value},
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)
    assert expected_code in codes(result)


def test_ssm_parameter_with_secure_standard_configuration_is_reviewable():
    document, proposal_value = ssm_parameter_case()

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert not any(code.startswith("ssm_parameter_") for code in codes(result))


@pytest.mark.parametrize(
    ("values", "expected_code"),
    [
        ({"type": "String"}, "ssm_parameter_secure_string_required"),
        ({"tier": "Advanced"}, "ssm_parameter_standard_tier_required"),
        ({"tier": "Intelligent-Tiering"}, "ssm_parameter_standard_tier_required"),
        ({"key_id": "  "}, "ssm_parameter_kms_key_invalid"),
    ],
)
def test_ssm_parameter_rejects_unsupported_encryption_or_tier(values, expected_code):
    document, proposal_value = ssm_parameter_case(values=values)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert expected_code in codes(result)


@pytest.mark.parametrize("attribute", ["type", "tier", "key_id"])
def test_ssm_parameter_denies_unknown_encryption_or_tier_settings(attribute):
    document, proposal_value = ssm_parameter_case(
        values={attribute: None},
        after_unknown={attribute: True},
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


def test_opensearch_domain_with_supported_private_shape_is_reviewable():
    document, proposal_value = opensearch_domain_case()

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert not any(code.startswith("opensearch_") for code in codes(result))


@pytest.mark.parametrize(
    ("values", "expected_code"),
    [
        ({"engine_version": "OpenSearch_1.0"}, "opensearch_engine_version_unsupported"),
        (
            {"cluster_config": [{"instance_type": "m6g.large.search", "instance_count": 1, "zone_awareness_enabled": False}]},
            "opensearch_instance_type_unsupported",
        ),
        (
            {"cluster_config": [{"instance_type": "t3.small.search", "instance_count": 2, "zone_awareness_enabled": False}]},
            "opensearch_instance_count_unsupported",
        ),
        (
            {"ebs_options": [{"ebs_enabled": True, "volume_type": "gp2", "volume_size": 10}]},
            "opensearch_volume_type_unsupported",
        ),
        ({"encrypt_at_rest": [{"enabled": False}]}, "opensearch_at_rest_encryption_required"),
        ({"node_to_node_encryption": [{"enabled": False}]}, "opensearch_node_encryption_required"),
        (
            {"domain_endpoint_options": [{"enforce_https": False, "tls_security_policy": "Policy-Min-TLS-1-0-2019-07"}]},
            "opensearch_https_required",
        ),
    ],
)
def test_opensearch_domain_rejects_unsupported_or_unsafe_settings(values, expected_code):
    document, proposal_value = opensearch_domain_case(values=values)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert expected_code in codes(result)


@pytest.mark.parametrize(
    ("values", "after_unknown"),
    [
        ({"engine_version": None}, {"engine_version": True}),
        (
            {"cluster_config": [{"instance_type": None}]},
            {"cluster_config": [{"instance_type": True}]},
        ),
        ({"ebs_options": [{"volume_size": None}]}, {"ebs_options": [{"volume_size": True}]}),
        ({"encrypt_at_rest": [{"enabled": None}]}, {"encrypt_at_rest": [{"enabled": True}]}),
        (
            {"domain_endpoint_options": [{"tls_security_policy": None}]},
            {"domain_endpoint_options": [{"tls_security_policy": True}]},
        ),
    ],
)
def test_opensearch_domain_denies_unknown_safety_settings(values, after_unknown):
    document, proposal_value = opensearch_domain_case(
        values=values,
        after_unknown=after_unknown,
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


def test_acm_certificate_with_reviewed_request_settings_is_reviewable():
    document, proposal_value = acm_certificate_case()

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert not any(code.startswith("acm_certificate_") for code in codes(result))


@pytest.mark.parametrize(
    ("values", "expected_code"),
    [
        ({"domain_name": ""}, "acm_certificate_domain_unknown"),
        ({"validation_method": "EMAIL"}, "acm_certificate_dns_validation_required"),
        ({"key_algorithm": "EC_secp384r1"}, "acm_certificate_key_algorithm_unsupported"),
        ({"options": [{"export": "ENABLED"}]}, "acm_certificate_export_denied"),
    ],
)
def test_acm_certificate_rejects_unsupported_request_settings(values, expected_code):
    document, proposal_value = acm_certificate_case(values=values)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert expected_code in codes(result)


@pytest.mark.parametrize(
    ("values", "after_unknown"),
    [
        ({"domain_name": None}, {"domain_name": True}),
        ({"validation_method": None}, {"validation_method": True}),
        ({"key_algorithm": None}, {"key_algorithm": True}),
        ({"options": [{"export": None}]}, {"options": [{"export": True}]}),
    ],
)
def test_acm_certificate_denies_unknown_request_settings(values, after_unknown):
    document, proposal_value = acm_certificate_case(
        values=values,
        after_unknown=after_unknown,
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


def test_sqs_queue_requires_sqs_managed_encryption():
    document, proposal_value = sqs_queue_case(False)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "sqs_queue_encryption_required" in codes(result)


def test_sqs_queue_unknown_encryption_is_denied():
    document, proposal_value = sqs_queue_case(
        None,
        after_unknown={"sqs_managed_sse_enabled": True},
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)
    assert "sqs_queue_encryption_required" in codes(result)


def test_sqs_queue_with_sqs_managed_encryption_remains_reviewable():
    document, proposal_value = sqs_queue_case(True)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert "sqs_queue_encryption_required" not in codes(result)


def test_sns_sqs_subscription_with_exact_queue_policy_is_reviewable():
    document, proposal_value = sns_sqs_case()

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert "sns_sqs_policy_binding_invalid" not in codes(result)


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_principal",
        "broad_action",
        "wildcard_queue",
        "wrong_source",
        "wrong_account",
        "extra_send_grant",
        "queue_url_mismatch",
        "queue_url_malformed",
    ],
)
def test_sns_sqs_subscription_denies_unscoped_queue_send_policy(mutation):
    document, proposal_value = sns_sqs_case()
    policy_item = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "aws_sqs_queue_policy"
    )
    policy = json.loads(policy_item["values"]["policy"])
    statement = policy["Statement"][0]
    if mutation == "wrong_principal":
        statement["Principal"] = {"Service": "events.amazonaws.com"}
    elif mutation == "broad_action":
        statement["Action"] = "sqs:*"
    elif mutation == "wildcard_queue":
        statement["Resource"] = "arn:aws:sqs:us-east-1:654654474502:*"
    elif mutation == "wrong_source":
        statement["Condition"]["ArnEquals"]["aws:SourceArn"] = (
            "arn:aws:sns:us-east-1:654654474502:another-topic"
        )
    elif mutation == "wrong_account":
        statement["Condition"]["StringEquals"]["aws:SourceAccount"] = "111111111111"
    elif mutation == "queue_url_mismatch":
        policy_item["values"]["queue_url"] = (
            f"https://sqs.{REGION}.amazonaws.com/{ACCOUNT}/another-queue"
        )
    elif mutation == "queue_url_malformed":
        policy_item["values"]["queue_url"] = {"unexpected": "object"}
    else:
        policy["Statement"].append(
            {
                "Effect": "Allow",
                "Principal": {"Service": "sns.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "Resource": "arn:aws:sqs:us-east-1:654654474502:async-work",
            }
        )
    policy_item["values"]["policy"] = json.dumps(policy)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "sns_sqs_policy_binding_invalid" in codes(result)


@pytest.mark.parametrize(
    "field,value,expected_code",
    [
        ("protocol", "email", "sns_subscription_protocol_unsupported"),
        ("topic_arn", "arn:aws:sns:us-east-1:654654474502:other", "sns_subscription_topic_unplanned"),
        ("endpoint", "arn:aws:sqs:us-east-1:654654474502:other", "sns_subscription_queue_unplanned"),
    ],
)
def test_sns_sqs_subscription_requires_exact_planned_topic_and_queue(field, value, expected_code):
    document, proposal_value = sns_sqs_case()
    subscription = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "aws_sns_topic_subscription"
    )
    subscription["values"][field] = value

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert expected_code in codes(result)


def test_sns_sqs_subscription_rejects_duplicate_topic_queue_pair():
    document, proposal_value = sns_sqs_case()
    subscription = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "aws_sns_topic_subscription"
    )
    address = "aws_sns_topic_subscription.duplicate"
    document["planned_values"]["root_module"]["resources"].append(
        resource(address, "aws_sns_topic_subscription", subscription["values"])
    )
    document["resource_changes"].append(change(address, "aws_sns_topic_subscription"))
    resources = [item.model_dump(mode="json") for item in proposal_value.resources]
    resources.append(
        {
            "resource_id": "duplicate",
            "resource_type": "aws_sns_topic_subscription",
            "name": "duplicate",
            "arguments": {
                key: value
                for key, value in subscription["values"].items()
                if key != "tags"
            },
            "rationale": "Duplicate notification route regression.",
        }
    )

    result = evaluate(document, proposal(resources))

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "sns_subscription_duplicate" in codes(result)


def test_sns_sqs_send_policy_requires_a_same_plan_subscription():
    document, proposal_value = sns_sqs_case()
    address = "aws_sns_topic_subscription.to_queue"
    document["planned_values"]["root_module"]["resources"] = [
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["address"] != address
    ]
    document["resource_changes"] = [
        item for item in document["resource_changes"] if item["address"] != address
    ]
    proposal_resources = [
        item.model_dump(mode="json")
        for item in proposal_value.resources
        if item.name != "to_queue"
    ]

    result = evaluate(document, proposal(proposal_resources))

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "sns_sqs_policy_binding_invalid" in codes(result)


def test_sns_sqs_policy_finding_does_not_echo_policy_values():
    marker = "private-sns-source-arn-marker"
    document, proposal_value = sns_sqs_case()
    policy_item = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "aws_sqs_queue_policy"
    )
    policy = json.loads(policy_item["values"]["policy"])
    policy["Statement"][0]["Condition"]["ArnEquals"]["aws:SourceArn"] = marker
    policy_item["values"]["policy"] = json.dumps(policy)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "sns_sqs_policy_binding_invalid" in codes(result)
    assert marker not in repr(result)


@pytest.mark.parametrize("include_source_account", [False, True])
def test_eventbridge_sqs_target_requires_exact_planned_rule_and_queue_grant(
    include_source_account,
):
    document, proposal_value = eventbridge_sqs_case(
        include_source_account=include_source_account
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert "eventbridge_sqs_policy_binding_invalid" not in codes(result)


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_principal",
        "broad_action",
        "wildcard_queue",
        "wrong_source",
        "wrong_account",
        "extra_send_grant",
        "queue_url_mismatch",
        "queue_url_malformed",
    ],
)
def test_eventbridge_sqs_target_denies_unscoped_queue_send_policy(mutation):
    document, proposal_value = eventbridge_sqs_case()
    policy_item = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "aws_sqs_queue_policy"
    )
    policy = json.loads(policy_item["values"]["policy"])
    statement = policy["Statement"][0]
    if mutation == "wrong_principal":
        statement["Principal"] = {"Service": "sns.amazonaws.com"}
    elif mutation == "broad_action":
        statement["Action"] = "sqs:*"
    elif mutation == "wildcard_queue":
        statement["Resource"] = f"arn:aws:sqs:{REGION}:{ACCOUNT}:*"
    elif mutation == "wrong_source":
        statement["Condition"]["ArnEquals"]["aws:SourceArn"] = (
            f"arn:aws:events:{REGION}:{ACCOUNT}:rule/orders/other"
        )
    elif mutation == "wrong_account":
        statement["Condition"]["StringEquals"] = {"aws:SourceAccount": "111111111111"}
    elif mutation == "queue_url_mismatch":
        policy_item["values"]["queue_url"] = (
            f"https://sqs.{REGION}.amazonaws.com/{ACCOUNT}/another-queue"
        )
    elif mutation == "queue_url_malformed":
        policy_item["values"]["queue_url"] = {"unexpected": "object"}
    else:
        policy["Statement"].append(
            {
                "Effect": "Allow",
                "Principal": {"Service": "events.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "Resource": f"arn:aws:sqs:{REGION}:{ACCOUNT}:async-work",
                "Condition": {
                    "ArnEquals": {
                        "aws:SourceArn": f"arn:aws:events:{REGION}:{ACCOUNT}:rule/orders/other"
                    }
                },
            }
        )
    policy_item["values"]["policy"] = json.dumps(policy)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "eventbridge_sqs_policy_binding_invalid" in codes(result)


@pytest.mark.parametrize(
    "target_mutation,expected_code",
    [
        ("rule", "eventbridge_target_rule_unplanned"),
        ("bus", "eventbridge_target_rule_unplanned"),
        ("queue", "eventbridge_sqs_queue_unplanned"),
        ("role", "eventbridge_sqs_role_unsupported"),
    ],
)
def test_eventbridge_sqs_target_requires_supported_planned_identity(
    target_mutation, expected_code
):
    document, proposal_value = eventbridge_sqs_case()
    target = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "aws_cloudwatch_event_target"
    )
    if target_mutation == "rule":
        target["values"]["rule"] = "unplanned-rule"
    elif target_mutation == "bus":
        target["values"]["event_bus_name"] = "unplanned-bus"
    elif target_mutation == "queue":
        target["values"]["arn"] = f"arn:aws:sqs:{REGION}:111111111111:external"
    else:
        target["values"]["role_arn"] = f"arn:aws:iam::{ACCOUNT}:role/target-role"

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert expected_code in codes(result)


@pytest.mark.parametrize(
    "field,value",
    [
        ("maximum_retry_attempts", -1),
        ("maximum_retry_attempts", 186),
        ("maximum_event_age_in_seconds", 59),
        ("maximum_event_age_in_seconds", 86401),
    ],
)
def test_eventbridge_sqs_target_requires_bounded_retry_values(field, value):
    document, proposal_value = eventbridge_sqs_case()
    target = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "aws_cloudwatch_event_target"
    )
    target["values"]["retry_policy"][field] = value

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "eventbridge_retry_policy_invalid" in codes(result)


def test_eventbridge_sqs_target_denies_missing_retry_policy():
    document, proposal_value = eventbridge_sqs_case()
    target = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "aws_cloudwatch_event_target"
    )
    del target["values"]["retry_policy"]

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "eventbridge_retry_policy_invalid" in codes(result)


@pytest.mark.parametrize("dead_letter_mode", ["missing", "unplanned", "same_queue", "fifo"])
def test_eventbridge_sqs_target_requires_planned_standard_dead_letter_queue(
    dead_letter_mode,
):
    document, proposal_value = eventbridge_sqs_case()
    target = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "aws_cloudwatch_event_target"
    )
    if dead_letter_mode == "missing":
        del target["values"]["dead_letter_config"]
    elif dead_letter_mode == "unplanned":
        target["values"]["dead_letter_config"]["arn"] = (
            f"arn:aws:sqs:{REGION}:{ACCOUNT}:unplanned-dlq"
        )
    elif dead_letter_mode == "same_queue":
        target["values"]["dead_letter_config"]["arn"] = (
            f"arn:aws:sqs:{REGION}:{ACCOUNT}:async-work"
        )
    else:
        dead_letter_arn = f"arn:aws:sqs:{REGION}:{ACCOUNT}:eventbridge-fifo.fifo"
        target["values"]["dead_letter_config"]["arn"] = dead_letter_arn
        address = "aws_sqs_queue.eventbridge_fifo"
        values = {
            "name": "eventbridge-fifo.fifo",
            "sqs_managed_sse_enabled": True,
            "visibility_timeout_seconds": 30,
            "message_retention_seconds": 1209600,
        }
        document["planned_values"]["root_module"]["resources"].append(
            resource(address, "aws_sqs_queue", values)
        )
        document["resource_changes"].append(change(address, "aws_sqs_queue"))
        resources = [item.model_dump(mode="json") for item in proposal_value.resources]
        resources.append(
            {
                "resource_id": "eventbridge-fifo",
                "resource_type": "aws_sqs_queue",
                "name": "eventbridge_fifo",
                "arguments": {
                    "name": values["name"],
                    "sqs_managed_sse_enabled": True,
                },
                "rationale": "Regression case for unsupported EventBridge FIFO DLQ.",
            }
        )
        proposal_value = proposal(resources)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "eventbridge_dlq_invalid" in codes(result)


def test_eventbridge_sqs_target_requires_exact_dlq_queue_policy():
    document, proposal_value = eventbridge_sqs_case()
    policy_item = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["address"] == "aws_sqs_queue_policy.eventbridge_dlq_publish"
    )
    policy = json.loads(policy_item["values"]["policy"])
    policy["Statement"][0]["Condition"]["ArnEquals"]["aws:SourceArn"] = (
        f"arn:aws:events:{REGION}:{ACCOUNT}:rule/orders/another"
    )
    policy_item["values"]["policy"] = json.dumps(policy)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "eventbridge_dlq_policy_binding_invalid" in codes(result)


def test_eventbridge_sqs_policy_requires_same_plan_target():
    document, proposal_value = eventbridge_sqs_case()
    address = "aws_cloudwatch_event_target.to_queue"
    document["planned_values"]["root_module"]["resources"] = [
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["address"] != address
    ]
    document["resource_changes"] = [
        item for item in document["resource_changes"] if item["address"] != address
    ]
    proposal_resources = [
        item.model_dump(mode="json")
        for item in proposal_value.resources
        if item.name != "to_queue"
    ]

    result = evaluate(document, proposal(proposal_resources))

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "eventbridge_sqs_policy_binding_invalid" in codes(result)


def test_eventbridge_sqs_target_requires_its_custom_bus_in_the_plan():
    document, proposal_value = eventbridge_sqs_case()
    address = "aws_cloudwatch_event_bus.orders"
    document["planned_values"]["root_module"]["resources"] = [
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["address"] != address
    ]
    document["resource_changes"] = [
        item for item in document["resource_changes"] if item["address"] != address
    ]
    proposal_resources = [
        item.model_dump(mode="json")
        for item in proposal_value.resources
        if item.name != "orders"
    ]

    result = evaluate(document, proposal(proposal_resources))

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "eventbridge_target_rule_unplanned" in codes(result)


def test_eventbridge_and_sns_grants_can_share_an_exact_queue_policy():
    document, proposal_value = eventbridge_sqs_case()
    topic_arn = f"arn:aws:sns:{REGION}:{ACCOUNT}:notifications"
    queue_arn = f"arn:aws:sqs:{REGION}:{ACCOUNT}:async-work"
    policy_item = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "aws_sqs_queue_policy"
    )
    policy = json.loads(policy_item["values"]["policy"])
    policy["Statement"].append(
        {
            "Effect": "Allow",
            "Principal": {"Service": "sns.amazonaws.com"},
            "Action": "sqs:SendMessage",
            "Resource": queue_arn,
            "Condition": {
                "ArnEquals": {"aws:SourceArn": topic_arn},
                "StringEquals": {"aws:SourceAccount": ACCOUNT},
            },
        }
    )
    policy_item["values"]["policy"] = json.dumps(policy)
    address = "aws_sns_topic.notifications"
    subscription_address = "aws_sns_topic_subscription.to_queue"
    planned = [
        (
            address,
            "aws_sns_topic",
            {"name": "notifications", "arn": topic_arn},
        ),
        (
            subscription_address,
            "aws_sns_topic_subscription",
            {
                "protocol": "sqs",
                "topic_arn": topic_arn,
                "endpoint": queue_arn,
            },
        ),
    ]
    proposal_resources = [item.model_dump(mode="json") for item in proposal_value.resources]
    for proposal_resource in proposal_resources:
        if proposal_resource["name"] == "eventbridge_publish":
            proposal_resource["arguments"]["policy"] = policy_item["values"]["policy"]
    for resource_address, kind, values in planned:
        document["planned_values"]["root_module"]["resources"].append(
            resource(resource_address, kind, values)
        )
        document["resource_changes"].append(change(resource_address, kind))
        name = resource_address.split(".", maxsplit=1)[1]
        proposal_resources.append(
            {
                "resource_id": f"sns-{name.replace('_', '-')}",
                "resource_type": kind,
                "name": name,
                "arguments": values,
                "rationale": "Bind a separate notification topic to the same test queue.",
            }
        )

    result = evaluate(document, proposal(proposal_resources))

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW


def sqs_lambda_consumer_case(
    *, permissions=None, visibility=360, timeout=60, batch_window=0,
    unknown_timeout=False,
):
    document, proposal_value = sqs_queue_case(True)
    root_resources = document["planned_values"]["root_module"]["resources"]
    queue_arn = f"arn:aws:sqs:{REGION}:{ACCOUNT}:async-work"
    source_queue = next(item for item in root_resources if item["address"] == "aws_sqs_queue.queue")
    source_queue["values"]["visibility_timeout_seconds"] = visibility
    role_arn = f"arn:aws:iam::{ACCOUNT}:role/queue-consumer"
    role_trust = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    )
    consumer_policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": permissions
                    or [
                        "sqs:ReceiveMessage",
                        "sqs:DeleteMessage",
                        "sqs:GetQueueAttributes",
                    ],
                    "Resource": queue_arn,
                }
            ],
        }
    )
    role_address = "aws_iam_role.queue_consumer"
    policy_address = "aws_iam_role_policy.queue_consumer"
    function_address = "aws_lambda_function.queue_consumer"
    mapping_address = "aws_lambda_event_source_mapping.queue_consumer"
    values_by_resource = [
        resource(
            role_address,
            "aws_iam_role",
            {"name": "queue-consumer", "arn": role_arn, "assume_role_policy": role_trust},
        ),
        resource(
            policy_address,
            "aws_iam_role_policy",
            {"name": "queue-consumer-sqs", "role": "queue-consumer", "policy": consumer_policy},
        ),
        resource(
            function_address,
            "aws_lambda_function",
            {
                "function_name": "queue-consumer",
                "role": role_arn,
                "timeout": timeout,
            },
        ),
        resource(
            mapping_address,
            "aws_lambda_event_source_mapping",
            {
                "event_source_arn": queue_arn,
                "function_name": "queue-consumer",
                "enabled": True,
                "batch_size": 1,
                "maximum_batching_window_in_seconds": batch_window,
            },
        ),
    ]
    for item in values_by_resource:
        root_resources.append(item)
        metadata = (
            {"after_unknown": {"timeout": True}}
            if unknown_timeout and item["type"] == "aws_lambda_function"
            else {}
        )
        document["resource_changes"].append(
            change(item["address"], item["type"], **metadata)
        )

    document["configuration"]["root_module"] = {
        "resources": [
            {
                "address": function_address,
                "expressions": {"role": {"references": [f"{role_address}.arn"]}},
            },
            {
                "address": policy_address,
                "expressions": {"role": {"references": [f"{role_address}.name"]}},
            },
            {
                "address": mapping_address,
                "expressions": {
                    "event_source_arn": {"references": ["aws_sqs_queue.queue.arn"]},
                    "function_name": {"references": [f"{function_address}.arn"]},
                },
            },
        ]
    }
    proposal_resources = [item.model_dump(mode="json") for item in proposal_value.resources]
    proposal_resources.extend(
        [
            {
                "resource_id": "queue-consumer-role",
                "resource_type": "aws_iam_role",
                "name": "queue_consumer",
                "arguments": {"name": "queue-consumer"},
                "rationale": "Run the queue consumer with a dedicated execution role.",
            },
            {
                "resource_id": "queue-consumer-policy",
                "resource_type": "aws_iam_role_policy",
                "name": "queue_consumer",
                "arguments": {"role": "queue-consumer"},
                "rationale": "Limit the consumer to its planned SQS queue.",
            },
            {
                "resource_id": "queue-consumer-function",
                "resource_type": "aws_lambda_function",
                "name": "queue_consumer",
                "arguments": {"function_name": "queue-consumer", "timeout": timeout},
                "rationale": "Process messages from the planned SQS queue.",
            },
            {
                "resource_id": "queue-consumer-mapping",
                "resource_type": "aws_lambda_event_source_mapping",
                "name": "queue_consumer",
                "arguments": {"batch_size": 1},
                "rationale": "Connect the queue to its same-plan consumer.",
            },
        ]
    )
    dlq_resource = next(item for item in proposal_resources if item["resource_id"] == "dead-letter")
    dlq_resource["arguments"]["name"] = "async-work-dlq"
    source_resource = next(item for item in proposal_resources if item["resource_id"] == "queue")
    source_resource["arguments"]["name"] = "async-work"
    source_resource["arguments"]["visibility_timeout_seconds"] = visibility
    return document, proposal(proposal_resources)


def test_sqs_lambda_consumer_requires_bounded_queue_retry_and_exact_role_scope():
    document, proposal_value = sqs_lambda_consumer_case()

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert not any(item.code.startswith("sqs_lambda_") for item in result.findings)


def test_sqs_lambda_consumer_visibility_accounts_for_batch_window():
    document, proposal_value = sqs_lambda_consumer_case(
        visibility=360, timeout=60, batch_window=1
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "sqs_lambda_visibility_timeout_insufficient" in codes(result)


def test_sqs_lambda_consumer_unknown_function_timeout_fails_closed():
    document, proposal_value = sqs_lambda_consumer_case(unknown_timeout=True)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


@pytest.mark.parametrize("visibility,timeout", [(359, 60), (0, 1), (43201, 60)])
def test_sqs_lambda_consumer_denies_insufficient_or_invalid_visibility(visibility, timeout):
    document, proposal_value = sqs_lambda_consumer_case(
        visibility=visibility, timeout=timeout
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "sqs_visibility_timeout_invalid" in codes(result) or (
        "sqs_lambda_visibility_timeout_insufficient" in codes(result)
    )


def test_sqs_lambda_consumer_denies_missing_required_permission():
    document, proposal_value = sqs_lambda_consumer_case(
        permissions=["sqs:ReceiveMessage", "sqs:GetQueueAttributes"]
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "sqs_lambda_consumer_permission_missing" in codes(result)


def test_sqs_lambda_consumer_denies_wildcard_permission_resource():
    document, proposal_value = sqs_lambda_consumer_case()
    policy = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "aws_iam_role_policy"
    )
    policy_document = json.loads(policy["values"]["policy"])
    policy_document["Statement"][0]["Resource"] = "*"
    policy["values"]["policy"] = json.dumps(policy_document)
    change_item = next(
        item
        for item in document["resource_changes"]
        if item["type"] == "aws_iam_role_policy"
    )
    change_item["change"]["after"]["policy"] = policy["values"]["policy"]

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "sqs_lambda_consumer_scope_invalid" in codes(result)


def test_sqs_lambda_consumer_denies_unbound_mapping_references():
    document, proposal_value = sqs_lambda_consumer_case()
    mapping = document["configuration"]["root_module"]["resources"][-1]
    mapping["expressions"]["event_source_arn"]["references"] = []

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "sqs_lambda_mapping_unbound" in codes(result)


def test_sqs_redrive_policy_requires_bounded_retries_and_planned_dlq():
    document, proposal_value = sqs_queue_case(True)
    queue = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["address"] == "aws_sqs_queue.queue"
    )
    queue["values"]["redrive_policy"] = json.dumps(
        {
            "deadLetterTargetArn": f"arn:aws:sqs:{REGION}:{ACCOUNT}:outside-dlq",
            "maxReceiveCount": 3,
        }
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "sqs_redrive_policy_invalid" in codes(result)


def test_sqs_dlq_must_allow_only_its_exact_source_and_have_longer_retention():
    document, proposal_value = sqs_queue_case(True)
    dlq = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["address"] == "aws_sqs_queue.dead_letter"
    )
    dlq["values"]["redrive_allow_policy"] = json.dumps(
        {
            "redrivePermission": "byQueue",
            "sourceQueueArns": [f"arn:aws:sqs:{REGION}:{ACCOUNT}:another-source"],
        }
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "sqs_redrive_allow_source_mismatch" in codes(result)


def test_sqs_dlq_retention_must_exceed_source_retention():
    document, proposal_value = sqs_queue_case(True)
    dlq = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["address"] == "aws_sqs_queue.dead_letter"
    )
    dlq["values"]["message_retention_seconds"] = 345600

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "sqs_dlq_retention_not_longer" in codes(result)


def test_sqs_redrive_unknown_value_fails_closed():
    document, proposal_value = sqs_queue_case(
        True, after_unknown={"redrive_policy": True}
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


def test_sqs_queue_must_belong_to_a_bounded_redrive_pair():
    document, proposal_value = sqs_queue_case(True)
    queue = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["address"] == "aws_sqs_queue.queue"
    )
    queue["values"]["redrive_policy"] = None

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "sqs_redrive_contract_missing" in codes(result)


def test_sqs_redrive_cycle_is_denied():
    document, proposal_value = sqs_queue_case(True)
    dlq = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["address"] == "aws_sqs_queue.dead_letter"
    )
    dlq["values"]["redrive_policy"] = json.dumps(
        {
            "deadLetterTargetArn": f"arn:aws:sqs:{REGION}:{ACCOUNT}:async-work",
            "maxReceiveCount": 5,
        }
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "sqs_redrive_cycle_denied" in codes(result)


@pytest.mark.parametrize(
    "unknown",
    [
        {"visibility_timeout_seconds": True},
        {"message_retention_seconds": True},
    ],
)
def test_sqs_queue_unknown_delivery_values_fail_closed(unknown):
    document, proposal_value = sqs_queue_case(True, after_unknown=unknown)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


def cloudfront_case(
    default_behavior, ordered_behaviors=None, *, origins=None, after_unknown=None
):
    document = plan()
    arguments = {
        "default_cache_behavior": default_behavior,
        "ordered_cache_behavior": []
        if ordered_behaviors is None
        else ordered_behaviors,
        "origin": origins
        if origins is not None
        else [
            {
                "domain_name": "origin.example.com",
                "origin_id": "origin",
                "custom_origin_config": [
                    {
                        "origin_protocol_policy": "https-only",
                        "origin_ssl_protocols": ["TLSv1.2"],
                    }
                ],
            }
        ],
    }
    proposal_value = add_policy_resource(
        document,
        "aws_cloudfront_distribution",
        "cdn",
        arguments,
        after_unknown=after_unknown,
    )
    return document, proposal_value


def add_lambda_permission(document, values, **change_metadata):
    address = "aws_lambda_permission.function_access"
    document["planned_values"]["root_module"]["resources"].append(
        resource(address, "aws_lambda_permission", values)
    )
    document["resource_changes"].append(
        change(address, "aws_lambda_permission", **change_metadata)
    )
    return document


def add_api_gateway_route(document, authorization_type=_OMIT, *, after_unknown=None):
    address = "aws_apigatewayv2_route.application"
    api_address = "aws_apigatewayv2_api.application"
    document["planned_values"]["root_module"]["resources"].append(
        resource(api_address, "aws_apigatewayv2_api", {"name": "application-api", "protocol_type": "HTTP", "id": "api-123"})
    )
    document["resource_changes"].append(change(api_address, "aws_apigatewayv2_api"))
    values = {"api_id": "api-123", "route_key": "GET /items"}
    if authorization_type is not _OMIT:
        values["authorization_type"] = authorization_type
    document["planned_values"]["root_module"]["resources"].append(
        {"address": address, "mode": "managed", "type": "aws_apigatewayv2_route", "values": values}
    )
    planned_after = values.copy()
    document["resource_changes"].append(
        change(
            address,
            "aws_apigatewayv2_route",
            after=planned_after,
            after_unknown=after_unknown or {},
        )
    )
    document["configuration"]["root_module"] = {
        "resources": [
            {
                "address": address,
                "expressions": {
                    "api_id": {"references": [f"{api_address}.id"]},
                },
            }
        ]
    }
    proposal_resources = [item.model_dump(mode="json") for item in proposal().resources]
    proposal_resources.append(
        {
            "resource_id": "application-api",
            "resource_type": "aws_apigatewayv2_api",
            "name": "application",
            "arguments": {"name": "application-api", "protocol_type": "HTTP"},
            "outputs": [{"name": "id", "value_type": "string"}],
            "rationale": "Provide the API that owns the application route.",
        }
    )
    proposal_resources.append(
        {
            "resource_id": "application-route",
            "resource_type": "aws_apigatewayv2_route",
            "name": "application",
            "arguments": {
                **values,
                "api_id": {
                    "kind": "resource_reference",
                    "resource_id": "application-api",
                    "output_name": "id",
                    "value_type": "string",
                },
            },
            "rationale": "Route API requests to the application.",
        }
    )
    return document, proposal(proposal_resources)


def codes(result):
    return {finding.code for finding in result.findings}


def ebs_volume_policy_case(encryption_state):
    address = "aws_ebs_volume.data"
    tags = ownership_scope().tags()
    values = {"tags": tags}
    planned_after = {"tags": tags}
    after_unknown = {}
    if encryption_state == "false":
        values["encrypted"] = False
        planned_after["encrypted"] = False
    elif encryption_state == "true":
        values["encrypted"] = True
        planned_after["encrypted"] = True
    elif encryption_state == "unknown":
        values["encrypted"] = None
        planned_after["encrypted"] = None
        after_unknown = {"encrypted": True}

    resources = [
        resource(address, "aws_ebs_volume", values),
        resource("terraform_data.account_guard", "terraform_data", {"input": None}),
    ]
    changes = [
        change(
            address,
            "aws_ebs_volume",
            after=planned_after,
            after_unknown=after_unknown,
        ),
        change("terraform_data.account_guard", "terraform_data"),
    ]
    proposal_value = proposal(
        [
            {
                "resource_id": "data-volume",
                "resource_type": "aws_ebs_volume",
                "name": "data",
                "arguments": {"type": "gp3", "size": 8, "encrypted": encryption_state == "true"},
                "rationale": "Store application data on an encrypted EBS volume.",
            }
        ]
    )
    return evaluate(plan(resources, changes), proposal_value)


@pytest.mark.parametrize(
    "encryption_state,expected_finding",
    [
        ("false", "ebs_encryption_required"),
        ("missing", "ebs_encryption_required"),
        ("unknown", "policy_critical_value_unknown"),
        ("true", None),
    ],
)
def test_ebs_volume_requires_known_encryption_enabled(encryption_state, expected_finding):
    result = ebs_volume_policy_case(encryption_state)

    if expected_finding is None:
        assert "ebs_encryption_required" not in codes(result)
        assert result.verdict != PlanPolicyVerdict.DENY
    else:
        assert result.verdict == PlanPolicyVerdict.DENY
        assert expected_finding in codes(result)
        if expected_finding == "ebs_encryption_required":
            finding = next(item for item in result.findings if item.code == expected_finding)
            assert finding.message == "EBS volumes must have encryption enabled."


def test_resource_ownership_tags_are_required_for_every_aws_resource():
    document = plan()
    document["planned_values"]["root_module"]["resources"][0]["values"]["tags"].pop(
        "DavDeployWorkspace"
    )

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "resource_ownership_tags_missing" in codes(result)


def test_resource_ownership_mismatch_is_denied():
    document = plan()
    document["planned_values"]["root_module"]["resources"][0]["values"]["tags"][
        "DavDeployProject"
    ] = "another-project"

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "resource_ownership_tags_mismatch" in codes(result)


def test_unknown_resource_ownership_tag_is_denied():
    document = plan()
    document["resource_changes"][0]["change"]["after_unknown"] = {
        "tags": {"DavDeployWorkspace": True}
    }

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "resource_ownership_unknown" in codes(result)


def test_missing_trusted_ownership_scope_is_denied():
    result = evaluate_generated_plan_policy(
        plan(),
        proposal(),
        expected_account_id=ACCOUNT,
        expected_region=REGION,
        ownership_scope=None,
    )

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "plan_policy_input_invalid" in codes(result)


def test_secure_composed_s3_plan_is_eligible_only_for_human_review():
    result = evaluate()
    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert result.human_approval_required is True
    assert result.findings == ()


@pytest.mark.parametrize("algorithm", ["AES256", "aws:kms", "aws:kms:dsse"])
def test_s3_default_encryption_accepts_supported_algorithms(algorithm):
    document, proposal_value = plan_with_s3_default_encryption(
        s3_default_encryption(algorithm)
    )

    result = evaluate(document, proposal_value)

    assert "s3_default_encryption_algorithm_unsupported" not in codes(result)
    assert "s3_default_encryption_algorithm_unknown" not in codes(result)


def test_planned_s3_bucket_requires_one_same_plan_encryption_configuration():
    document = plan()
    document["planned_values"]["root_module"]["resources"] = [
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item.get("type") != "aws_s3_bucket_server_side_encryption_configuration"
    ]
    document["resource_changes"] = [
        item
        for item in document["resource_changes"]
        if item.get("type") != "aws_s3_bucket_server_side_encryption_configuration"
    ]
    proposal_resources = [
        item.model_dump(mode="json")
        for item in proposal().resources
        if item.resource_id != "bucket-encryption"
    ]

    result = evaluate(document, proposal(proposal_resources))

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_default_encryption_configuration_missing" in codes(result)


@pytest.mark.parametrize(
    "rule",
    [
        [],
        [{"apply_server_side_encryption_by_default": []}],
        [
            {"apply_server_side_encryption_by_default": [{"sse_algorithm": "AES256"}]},
            {"apply_server_side_encryption_by_default": [{"sse_algorithm": "aws:kms"}]},
        ],
        [{"apply_server_side_encryption_by_default": [{"sse_algorithm": None}]}],
    ],
)
def test_s3_default_encryption_requires_one_complete_known_rule(rule):
    document, proposal_value = plan_with_s3_default_encryption(rule)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert {
        "s3_default_encryption_configuration_incomplete",
        "s3_default_encryption_algorithm_unknown",
    } & codes(result)


def test_s3_default_encryption_rejects_unsupported_algorithm_without_echoing_value():
    marker = "private-unapproved-encryption-marker"
    document, proposal_value = plan_with_s3_default_encryption(
        s3_default_encryption(marker)
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_default_encryption_algorithm_unsupported" in codes(result)
    assert marker not in repr(result)


def test_s3_default_encryption_rejects_duplicate_configurations():
    document = plan()
    duplicate_address = (
        "aws_s3_bucket_server_side_encryption_configuration.duplicate"
    )
    document["planned_values"]["root_module"]["resources"].append(
        resource(
            duplicate_address,
            "aws_s3_bucket_server_side_encryption_configuration",
            {"bucket": "private-plan-bucket", "rule": s3_default_encryption()},
        )
    )
    document["resource_changes"].append(
        change(duplicate_address, "aws_s3_bucket_server_side_encryption_configuration")
    )
    proposal_resources = [
        item.model_dump(mode="json") for item in proposal().resources
    ]
    proposal_resources.append(
        {
            "resource_id": "duplicate-encryption",
            "resource_type": "aws_s3_bucket_server_side_encryption_configuration",
            "name": "duplicate",
            "arguments": {
                "bucket": "private-plan-bucket",
                "rule": s3_default_encryption(),
            },
            "rationale": "Duplicate encryption configuration regression.",
        }
    )

    result = evaluate(document, proposal(proposal_resources))

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_default_encryption_configuration_ambiguous" in codes(result)


def test_s3_default_encryption_reference_cannot_override_conflicting_bucket_identity():
    document, proposal_value = plan_with_s3_default_encryption(
        s3_default_encryption(), configured_bucket="another-plan-bucket"
    )
    document["configuration"]["root_module"] = {
        "resources": [
            {
                "address": "aws_s3_bucket_server_side_encryption_configuration.encryption",
                "expressions": {"bucket": {"references": ["aws_s3_bucket.bucket.id"]}},
            }
        ]
    }

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_default_encryption_configuration_missing" in codes(result)


def test_planned_s3_bucket_requires_bucket_owner_enforced_controls():
    result = evaluate()

    assert "s3_ownership_controls_missing" not in codes(result)
    assert "s3_object_ownership_unsupported" not in codes(result)


def test_s3_ownership_controls_require_one_same_plan_resource():
    document = plan()
    document["planned_values"]["root_module"]["resources"] = [
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item.get("type") != "aws_s3_bucket_ownership_controls"
    ]
    document["resource_changes"] = [
        item
        for item in document["resource_changes"]
        if item.get("type") != "aws_s3_bucket_ownership_controls"
    ]
    proposal_resources = [
        item.model_dump(mode="json")
        for item in proposal().resources
        if item.resource_id != "bucket-ownership"
    ]

    result = evaluate(document, proposal(proposal_resources))

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_ownership_controls_missing" in codes(result)


@pytest.mark.parametrize("ownership", ["BucketOwnerPreferred", "ObjectWriter"])
def test_s3_ownership_controls_reject_acl_enabled_modes(ownership):
    document, proposal_value = plan_with_s3_ownership_control(
        s3_ownership_control(ownership)
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_object_ownership_unsupported" in codes(result)


@pytest.mark.parametrize("rule", [[], [{"object_ownership": None}], [{"object_ownership": "BucketOwnerEnforced"}, {"object_ownership": "ObjectWriter"}]])
def test_s3_ownership_controls_reject_incomplete_or_unknown_rules(rule):
    document, proposal_value = plan_with_s3_ownership_control(rule)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert {
        "s3_ownership_controls_incomplete",
        "s3_object_ownership_unknown",
    } & codes(result)


def test_s3_ownership_controls_reject_duplicate_resources():
    document = plan()
    duplicate_address = "aws_s3_bucket_ownership_controls.duplicate"
    document["planned_values"]["root_module"]["resources"].append(
        resource(
            duplicate_address,
            "aws_s3_bucket_ownership_controls",
            {"bucket": "private-plan-bucket", "rule": s3_ownership_control()},
        )
    )
    document["resource_changes"].append(
        change(duplicate_address, "aws_s3_bucket_ownership_controls")
    )
    proposal_resources = [
        item.model_dump(mode="json") for item in proposal().resources
    ]
    proposal_resources.append(
        {
            "resource_id": "duplicate-ownership",
            "resource_type": "aws_s3_bucket_ownership_controls",
            "name": "duplicate",
            "arguments": {
                "bucket": "private-plan-bucket",
                "rule": s3_ownership_control(),
            },
            "rationale": "Duplicate ownership-controls regression.",
        }
    )

    result = evaluate(document, proposal(proposal_resources))

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_ownership_controls_ambiguous" in codes(result)


def test_s3_ownership_reference_cannot_override_conflicting_bucket_identity():
    document, proposal_value = plan_with_s3_ownership_control(
        s3_ownership_control(), configured_bucket="another-plan-bucket"
    )
    document["configuration"]["root_module"] = {
        "resources": [
            {
                "address": "aws_s3_bucket_ownership_controls.ownership",
                "expressions": {"bucket": {"references": ["aws_s3_bucket.bucket.id"]}},
            }
        ]
    }

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_ownership_controls_missing" in codes(result)


def test_unknown_s3_ownership_rule_is_denied():
    document = plan()
    ownership_change = next(
        item
        for item in document["resource_changes"]
        if item.get("type") == "aws_s3_bucket_ownership_controls"
    )
    ownership_change["change"]["after_unknown"] = {"rule": True}

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


@pytest.mark.parametrize(
    ("kind", "options"),
    [
        (
            "aws_instance",
            {"http_endpoint": "enabled", "http_tokens": "required"},
        ),
        (
            "aws_launch_template",
            [{"http_endpoint": "enabled", "http_tokens": "required"}],
        ),
        (
            "aws_launch_configuration",
            [{"http_endpoint": "enabled", "http_tokens": "required"}],
        ),
    ],
)
def test_ec2_metadata_access_requires_imdsv2_tokens(kind, options):
    document = plan()
    proposal_value = add_policy_resource(
        document, kind, "secure_compute", {"metadata_options": options}
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert not any(code.startswith("instance_metadata_") for code in codes(result))


@pytest.mark.parametrize("kind", ["aws_instance", "aws_launch_template"])
def test_ec2_metadata_endpoint_may_be_explicitly_disabled(kind):
    document = plan()
    proposal_value = add_policy_resource(
        document,
        kind,
        "metadata_disabled",
        {
            "metadata_options": {
                "http_endpoint": "disabled",
                "http_tokens": "optional",
            }
        },
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert not any(code.startswith("instance_metadata_") for code in codes(result))


@pytest.mark.parametrize("kind", ["aws_instance", "aws_launch_template"])
def test_ec2_metadata_endpoint_with_optional_tokens_is_denied(kind):
    document = plan()
    proposal_value = add_policy_resource(
        document,
        kind,
        "imdsv1_compatible",
        {
            "metadata_options": {
                "http_endpoint": "enabled",
                "http_tokens": "optional",
            }
        },
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "instance_metadata_v2_required" in codes(result)


def test_regional_ec2_metadata_defaults_must_require_imdsv2():
    document = plan()
    proposal_value = add_policy_resource(
        document,
        "aws_ec2_instance_metadata_defaults",
        "regional_defaults",
        {"region": REGION, "http_tokens": "required"},
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert "instance_metadata_defaults_require_v2" not in codes(result)


@pytest.mark.parametrize("tokens", ["optional", "no_preference"])
def test_regional_ec2_metadata_defaults_that_do_not_require_imdsv2_are_denied(tokens):
    document = plan()
    proposal_value = add_policy_resource(
        document,
        "aws_ec2_instance_metadata_defaults",
        "regional_defaults",
        {"region": REGION, "http_tokens": tokens},
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "instance_metadata_defaults_require_v2" in codes(result)


def eks_node_group_case(*, metadata_tokens="required", launch_template_references=None):
    document = plan()
    template_address = "aws_launch_template.eks_nodes"
    node_group_address = "aws_eks_node_group.app_nodes"
    template_values = {
        "name": "app-nodes",
        "metadata_options": [
            {"http_endpoint": "enabled", "http_tokens": metadata_tokens}
        ],
    }
    node_group_values = {
        "cluster_name": "app-cluster",
        "node_group_name": "app-nodes",
        "launch_template": [{"id": "lt-0123456789abcdef0", "version": "1"}],
    }
    document["planned_values"]["root_module"]["resources"].extend(
        [
            resource(template_address, "aws_launch_template", template_values),
            resource(node_group_address, "aws_eks_node_group", node_group_values),
        ]
    )
    document["resource_changes"].extend(
        [
            change(template_address, "aws_launch_template"),
            change(node_group_address, "aws_eks_node_group"),
        ]
    )
    references = (
        [f"{template_address}.id", template_address]
        if launch_template_references is None
        else launch_template_references
    )
    document["configuration"]["root_module"] = {
        "resources": [
            {"address": template_address, "expressions": {}},
            {
                "address": node_group_address,
                "expressions": {"launch_template": {"references": references}},
            },
        ]
    }
    resources = [item.model_dump(mode="json") for item in proposal().resources]
    resources.extend(
        [
            {
                "resource_id": "eks-nodes-template",
                "resource_type": "aws_launch_template",
                "name": "eks_nodes",
                "arguments": template_values,
                "rationale": "Use IMDSv2 for managed Kubernetes nodes.",
            },
            {
                "resource_id": "eks-node-group",
                "resource_type": "aws_eks_node_group",
                "name": "app_nodes",
                "arguments": node_group_values,
                "rationale": "Run the application on managed Kubernetes nodes.",
            },
        ]
    )
    return document, proposal(resources)


def test_eks_node_group_requires_same_plan_launch_template_with_imdsv2():
    document, proposal_value = eks_node_group_case()

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert "eks_node_metadata_unverifiable" not in codes(result)
    assert "instance_metadata_v2_required" not in codes(result)


@pytest.mark.parametrize(
    "references",
    [[], ["aws_launch_template.external.id"], ["aws_launch_template.eks_nodes.id", "aws_launch_template.other.id"]],
)
def test_eks_node_group_without_one_same_plan_template_reference_is_denied(references):
    document, proposal_value = eks_node_group_case(launch_template_references=references)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "eks_node_metadata_unverifiable" in codes(result)


def test_eks_node_group_with_launch_template_that_allows_imdsv1_is_denied():
    document, proposal_value = eks_node_group_case(metadata_tokens="optional")

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "instance_metadata_v2_required" in codes(result)


def test_configured_resource_lookup_includes_child_modules():
    document = plan(
        configuration={
            "root_module": {
                "resources": [],
                "module_calls": {
                    "eks": {
                        "module": {
                            "resources": [
                                {
                                    "address": "module.eks.aws_eks_node_group.nodes",
                                    "expressions": {},
                                }
                            ],
                            "module_calls": {},
                        }
                    }
                },
            }
        }
    )

    assert "module.eks.aws_eks_node_group.nodes" in _configured_resources(document)
    assert _reference_targets_resource(
        "aws_launch_template.nodes.id",
        "module.eks.aws_launch_template.nodes",
        "aws_launch_template",
    )
    assert _reference_targets_resource(
        "aws_launch_template.nodes",
        "module.eks.aws_launch_template.nodes",
        "aws_launch_template",
    )


@pytest.mark.parametrize(
    "options",
    [None, [], [{"http_endpoint": "enabled"}, {"http_endpoint": "disabled"}]],
)
def test_malformed_or_missing_ec2_metadata_options_are_denied(options):
    document = plan()
    proposal_value = add_policy_resource(
        document,
        "aws_instance",
        "unknown_metadata",
        {"metadata_options": options},
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "instance_metadata_options_unknown" in codes(result)


@pytest.mark.parametrize(
    "kind",
    [
        "aws_instance",
        "aws_launch_template",
        "aws_launch_configuration",
        "aws_ec2_instance_metadata_defaults",
    ],
)
def test_unknown_ec2_metadata_token_requirement_is_denied(kind):
    document = plan()
    options = (
        {"http_tokens": "required"}
        if kind == "aws_ec2_instance_metadata_defaults"
        else {
            "metadata_options": [
                {"http_endpoint": "enabled", "http_tokens": "required"}
            ]
        }
    )
    unknown = (
        {"http_tokens": True}
        if kind == "aws_ec2_instance_metadata_defaults"
        else {"metadata_options": [{"http_tokens": True}]}
    )
    proposal_value = add_policy_resource(
        document,
        kind,
        "unknown_tokens",
        options,
        after_unknown=unknown,
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


@pytest.mark.parametrize(
    "flag",
    ["block_public_acls", "block_public_policy", "ignore_public_acls", "restrict_public_buckets"],
)
def test_s3_public_access_must_be_blocked_in_all_four_settings(flag):
    document = plan()
    document["planned_values"]["root_module"]["resources"][1]["values"][flag] = False
    assert "s3_public_access_block_incomplete" in codes(evaluate(document))


def test_missing_s3_public_access_block_is_denied():
    document = plan()
    document["planned_values"]["root_module"]["resources"].pop(1)
    document["resource_changes"].pop(1)
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_public_access_block_missing" in codes(result)
    assert "plan_resource_inventory_mismatch" in codes(result)


@pytest.mark.parametrize("acl", ["public-read", "public-read-write", "authenticated-read"])
def test_public_s3_acl_is_denied(acl):
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(
        resource("aws_s3_bucket_acl.bucket_acl", "aws_s3_bucket_acl", {"acl": acl})
    )
    return_resource = change("aws_s3_bucket_acl.bucket_acl", "aws_s3_bucket_acl")
    document["resource_changes"].append(return_resource)
    result = evaluate(document)
    assert "s3_public_acl" in codes(result)


def test_public_s3_policy_is_denied():
    document = plan()
    policy = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": "*", "Action": "s3:GetObject", "Resource": "*"}]}
    document["planned_values"]["root_module"]["resources"].append(
        resource("aws_s3_bucket_policy.policy", "aws_s3_bucket_policy", {"policy": json.dumps(policy)})
    )
    document["resource_changes"].append(change("aws_s3_bucket_policy.policy", "aws_s3_bucket_policy"))
    proposal_value = proposal(
        [
            *(item.model_dump(mode="json") for item in proposal().resources),
            {
                "resource_id": "bucket-policy",
                "resource_type": "aws_s3_bucket_policy",
                "name": "policy",
                "arguments": {"bucket": "private-plan-bucket", "policy": json.dumps(policy)},
                "rationale": "Public delivery requires review.",
            },
        ]
    )
    result = evaluate(document, proposal_value)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_public_policy_denied" in codes(result)


def test_s3_policy_allow_with_not_resource_is_denied_for_specific_principal():
    document = plan()
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": "arn:aws:iam::654654474502:role/app"},
                "Action": "s3:GetObject",
                "NotResource": "arn:aws:s3:::private-plan-bucket/private.json",
            }
        ],
    }
    document["planned_values"]["root_module"]["resources"].append(
        resource("aws_s3_bucket_policy.policy", "aws_s3_bucket_policy", {"policy": json.dumps(policy)})
    )
    document["resource_changes"].append(change("aws_s3_bucket_policy.policy", "aws_s3_bucket_policy"))
    proposal_value = proposal(
        [
            *(item.model_dump(mode="json") for item in proposal().resources),
            {
                "resource_id": "bucket-policy",
                "resource_type": "aws_s3_bucket_policy",
                "name": "policy",
                "arguments": {"bucket": "private-plan-bucket", "policy": json.dumps(policy)},
                "rationale": "Scoped access for the application role.",
            },
        ]
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_not_resource_policy_denied" in codes(result)


def test_s3_policy_allow_with_not_action_is_denied_for_specific_principal():
    document = plan()
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": "arn:aws:iam::654654474502:role/app"},
                "NotAction": "s3:DeleteObject",
                "Resource": "arn:aws:s3:::private-plan-bucket/*",
            }
        ],
    }
    document["planned_values"]["root_module"]["resources"].append(
        resource("aws_s3_bucket_policy.policy", "aws_s3_bucket_policy", {"policy": json.dumps(policy)})
    )
    document["resource_changes"].append(change("aws_s3_bucket_policy.policy", "aws_s3_bucket_policy"))
    proposal_value = proposal(
        [
            *(item.model_dump(mode="json") for item in proposal().resources),
            {
                "resource_id": "bucket-policy",
                "resource_type": "aws_s3_bucket_policy",
                "name": "policy",
                "arguments": {"bucket": "private-plan-bucket", "policy": json.dumps(policy)},
                "rationale": "Scoped access for the application role.",
            },
        ]
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_not_action_policy_denied" in codes(result)


def test_s3_policy_external_aws_principal_is_denied():
    document = plan()
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": "arn:aws:iam::999999999999:root"},
                "Action": "s3:GetObject",
                "Resource": "arn:aws:s3:::private-plan-bucket/*",
            }
        ],
    }
    document["planned_values"]["root_module"]["resources"].append(
        resource("aws_s3_bucket_policy.policy", "aws_s3_bucket_policy", {"policy": json.dumps(policy)})
    )
    document["resource_changes"].append(change("aws_s3_bucket_policy.policy", "aws_s3_bucket_policy"))
    proposal_value = proposal(
        [
            *(item.model_dump(mode="json") for item in proposal().resources),
            {
                "resource_id": "bucket-policy",
                "resource_type": "aws_s3_bucket_policy",
                "name": "policy",
                "arguments": {"bucket": "private-plan-bucket", "policy": json.dumps(policy)},
                "rationale": "Share storage with a separate account.",
            },
        ]
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_unverified_policy_principal_denied" in codes(result)


def test_s3_policy_unbounded_resource_arn_is_denied():
    document = plan()
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": "arn:aws:iam::654654474502:role/app"},
                "Action": "s3:GetObject",
                "Resource": "*",
            }
        ],
    }
    document["planned_values"]["root_module"]["resources"].append(
        resource("aws_s3_bucket_policy.policy", "aws_s3_bucket_policy", {"policy": json.dumps(policy)})
    )
    document["resource_changes"].append(change("aws_s3_bucket_policy.policy", "aws_s3_bucket_policy"))
    proposal_value = proposal(
        [
            *(item.model_dump(mode="json") for item in proposal().resources),
            {
                "resource_id": "bucket-policy",
                "resource_type": "aws_s3_bucket_policy",
                "name": "policy",
                "arguments": {"bucket": "private-plan-bucket", "policy": json.dumps(policy)},
                "rationale": "Scope application access to one bucket.",
            },
        ]
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_resource_arn_unbounded" in codes(result)


def test_planned_s3_bucket_requires_one_same_plan_transport_policy():
    document = plan()
    document["planned_values"]["root_module"]["resources"] = [
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item.get("address") != "aws_s3_bucket_policy.transport_policy"
    ]
    document["resource_changes"] = [
        item
        for item in document["resource_changes"]
        if item.get("address") != "aws_s3_bucket_policy.transport_policy"
    ]
    proposal_resources = [
        item.model_dump(mode="json")
        for item in proposal().resources
        if item.resource_id != "secure-transport-policy"
    ]

    result = evaluate(document, proposal(proposal_resources))

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_secure_transport_policy_missing" in codes(result)


@pytest.mark.parametrize(
    "bucket_arn",
    [
        "arn:aws:s3:::different-plan-bucket",
        "arn:aws-cn:s3:::private-plan-bucket",
    ],
)
def test_s3_transport_policy_rejects_bucket_arn_identity_mismatch(bucket_arn):
    document = plan()
    document["planned_values"]["root_module"]["resources"][0]["values"]["arn"] = bucket_arn

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_secure_transport_bucket_unknown" in codes(result)


def test_s3_transport_policy_reference_cannot_override_conflicting_bucket_identity():
    document = plan()
    policy = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item.get("type") == "aws_s3_bucket_policy"
    )
    policy["values"]["bucket"] = "another-plan-bucket"
    document["configuration"]["root_module"] = {
        "resources": [
            {
                "address": "aws_s3_bucket_policy.transport_policy",
                "expressions": {"bucket": {"references": ["aws_s3_bucket.bucket.id"]}},
            }
        ]
    }

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_secure_transport_policy_missing" in codes(result)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_service_exclusion",
        "secure_transport_true",
        "narrow_action",
        "missing_bucket_resource",
        "missing_object_resource",
        "narrow_principal",
        "conditional_scope",
    ],
)
def test_s3_transport_policy_must_cover_tls_bucket_and_object_requests(mutation):
    policy = json.loads(s3_secure_transport_policy("private-plan-bucket"))
    statement = policy["Statement"][0]
    if mutation == "missing_service_exclusion":
        statement["Condition"]["Bool"].pop("aws:PrincipalIsAWSService")
    elif mutation == "secure_transport_true":
        statement["Condition"]["Bool"]["aws:SecureTransport"] = "true"
    elif mutation == "narrow_action":
        statement["Action"] = "s3:GetObject"
    elif mutation == "missing_bucket_resource":
        statement["Resource"] = ["arn:aws:s3:::private-plan-bucket/*"]
    elif mutation == "missing_object_resource":
        statement["Resource"] = ["arn:aws:s3:::private-plan-bucket"]
    elif mutation == "narrow_principal":
        statement["Principal"] = {"AWS": "arn:aws:iam::654654474502:root"}
    else:
        statement["Condition"]["IpAddress"] = {"aws:SourceIp": "192.0.2.0/24"}
    document, proposal_value = plan_with_s3_transport_policy(json.dumps(policy))

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_secure_transport_policy_incomplete" in codes(result)


def test_s3_transport_policy_can_split_bucket_and_object_arns_across_statements():
    policy = json.loads(s3_secure_transport_policy("private-plan-bucket"))
    statement = policy["Statement"][0]
    first = {**statement, "Resource": ["arn:aws:s3:::private-plan-bucket"]}
    second = {**statement, "Resource": ["arn:aws:s3:::private-plan-bucket/*"]}
    policy["Statement"] = [first, second]
    document, proposal_value = plan_with_s3_transport_policy(json.dumps(policy))

    result = evaluate(document, proposal_value)

    assert "s3_secure_transport_policy_incomplete" not in codes(result)


def test_s3_transport_policy_rejects_duplicate_bucket_policies():
    document = plan()
    duplicate_address = "aws_s3_bucket_policy.duplicate"
    policy = s3_secure_transport_policy("private-plan-bucket")
    document["planned_values"]["root_module"]["resources"].append(
        resource(
            duplicate_address,
            "aws_s3_bucket_policy",
            {"bucket": "private-plan-bucket", "policy": policy},
        )
    )
    document["resource_changes"].append(
        change(duplicate_address, "aws_s3_bucket_policy")
    )
    proposal_resources = [
        item.model_dump(mode="json") for item in proposal().resources
    ]
    proposal_resources.append(
        {
            "resource_id": "duplicate-policy",
            "resource_type": "aws_s3_bucket_policy",
            "name": "duplicate",
            "arguments": {"bucket": "private-plan-bucket", "policy": policy},
            "rationale": "Duplicate policy regression.",
        }
    )

    result = evaluate(document, proposal(proposal_resources))

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_secure_transport_policy_ambiguous" in codes(result)


def test_s3_transport_policy_findings_do_not_echo_policy_values():
    marker = "s3-policy-sensitive-transport-marker"
    policy = json.loads(s3_secure_transport_policy("private-plan-bucket"))
    policy["Statement"][0]["Condition"]["Bool"]["aws:SecureTransport"] = marker
    document, proposal_value = plan_with_s3_transport_policy(json.dumps(policy))

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert marker not in repr(result)

@pytest.mark.parametrize("principal", ["*", {"AWS": "*"}, {"AWS": ["*"]}])
def test_public_sqs_queue_policy_is_denied(principal):
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": principal,
                "Action": "sqs:ReceiveMessage",
                "Resource": "arn:aws:sqs:us-east-1:654654474502:async-work",
            }
        ],
    }
    document = add_sqs_queue_policy(plan(), json.dumps(policy))

    assert "sqs_public_policy_denied" in codes(evaluate(document))


def test_sqs_queue_policy_allow_with_not_resource_is_denied_for_specific_principal():
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "sns.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "NotResource": "arn:aws:sqs:us-east-1:654654474502:excluded-queue",
            }
        ],
    }
    document = add_sqs_queue_policy(plan(), json.dumps(policy))

    assert "sqs_not_resource_policy_denied" in codes(evaluate(document))


def test_sqs_queue_policy_allow_with_not_action_is_denied_for_specific_principal():
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "sns.amazonaws.com"},
                "NotAction": "sqs:DeleteMessage",
                "Resource": "arn:aws:sqs:us-east-1:654654474502:async-work",
            }
        ],
    }
    document = add_sqs_queue_policy(plan(), json.dumps(policy))

    assert "sqs_not_action_policy_denied" in codes(evaluate(document))


def test_sqs_queue_policy_external_aws_principal_is_denied():
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": "arn:aws:iam::999999999999:root"},
                "Action": "sqs:SendMessage",
                "Resource": "arn:aws:sqs:us-east-1:654654474502:async-work",
            }
        ],
    }
    document = add_sqs_queue_policy(plan(), json.dumps(policy))

    assert "sqs_unverified_policy_principal_denied" in codes(evaluate(document))


def test_sqs_queue_policy_unbounded_resource_arn_is_denied():
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "sns.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "Resource": "*",
            }
        ],
    }
    document = add_sqs_queue_policy(plan(), json.dumps(policy))

    assert "sqs_resource_arn_unbounded" in codes(evaluate(document))


def test_sqs_queue_policy_allow_with_not_principal_is_denied():
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "NotPrincipal": {"AWS": "arn:aws:iam::654654474502:root"},
                "Action": "sqs:ReceiveMessage",
                "Resource": "arn:aws:sqs:us-east-1:654654474502:async-work",
            }
        ],
    }
    document = add_sqs_queue_policy(plan(), json.dumps(policy))

    assert "sqs_public_policy_denied" in codes(evaluate(document))


def test_specific_sqs_queue_policy_principal_does_not_trigger_public_policy_denial():
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "sns.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "Resource": "arn:aws:sqs:us-east-1:654654474502:async-work",
            }
        ],
    }
    document = add_sqs_queue_policy(plan(), json.dumps(policy))

    assert "sqs_public_policy_denied" not in codes(evaluate(document))


def test_unknown_sqs_queue_policy_is_denied_even_if_after_value_looks_safe():
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "sns.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "Resource": "arn:aws:sqs:us-east-1:654654474502:async-work",
            }
        ],
    }
    document = add_sqs_queue_policy(plan(), json.dumps(policy), after_unknown={"policy": True})

    assert "policy_critical_value_unknown" in codes(evaluate(document))


def test_malformed_sqs_queue_policy_is_denied_without_echoing_policy_text():
    secret_text = "private-policy-secret"
    document = add_sqs_queue_policy(plan(), f"{{{secret_text}")

    result = evaluate(document)

    assert "policy_document_invalid" in codes(result)
    assert secret_text not in repr(result)


def test_public_sqs_queue_policy_finding_does_not_echo_policy_values():
    secret_action = "sqs:SendMessage-private-policy-secret"
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": "*",
                "Action": secret_action,
                "Resource": "arn:aws:sqs:us-east-1:654654474502:async-work",
            }
        ],
    }
    document = add_sqs_queue_policy(plan(), json.dumps(policy))

    result = evaluate(document)

    assert "sqs_public_policy_denied" in codes(result)
    assert secret_action not in repr(result)


@pytest.mark.parametrize("source_arn", [None, "", "*"])
def test_unscoped_lambda_wildcard_principal_is_denied(source_arn):
    values = {
        "action": "lambda:InvokeFunction",
        "function_name": "application-handler",
        "principal": "*",
    }
    if source_arn is not None:
        values["source_arn"] = source_arn
    document = add_lambda_permission(plan(), values)

    assert "lambda_unscoped_public_invoke_denied" in codes(evaluate(document))


def test_scoped_lambda_wildcard_principal_requires_human_review():
    document = add_lambda_permission(
        plan(),
        {
            "action": "lambda:InvokeFunction",
            "function_name": "application-handler",
            "principal": "*",
            "source_arn": "arn:aws:execute-api:us-east-1:654654474502:api-id/*/*/*",
        },
    )

    result = evaluate(document)

    assert "lambda_public_invoke_review" in codes(result)
    assert result.human_approval_required


def test_specific_lambda_service_principal_is_not_public_invoke():
    document = add_lambda_permission(
        plan(),
        {
            "action": "lambda:InvokeFunction",
            "function_name": "application-handler",
            "principal": "apigateway.amazonaws.com",
            "source_arn": "arn:aws:execute-api:us-east-1:654654474502:api-id/*/*/*",
        },
    )

    assert "lambda_unscoped_public_invoke_denied" not in codes(evaluate(document))
    assert "lambda_public_invoke_review" not in codes(evaluate(document))


def test_open_api_gateway_route_requires_human_review():
    document, proposal_value = add_api_gateway_route(plan(), "NONE")

    result = evaluate(document, proposal_value)

    # This provider resource has no tags argument, so ownership fails closed
    # until exact ownership records for untaggable resources are implemented.
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "api_gateway_open_route_review" in codes(result)
    finding = next(item for item in result.findings if item.code == "api_gateway_open_route_review")
    assert "GET /items" not in repr(finding)


@pytest.mark.parametrize("authorization_type", ["JWT", "AWS_IAM", "CUSTOM"])
def test_authenticated_api_gateway_routes_do_not_trigger_open_route_review(authorization_type):
    document, proposal_value = add_api_gateway_route(plan(), authorization_type)

    result = evaluate(document, proposal_value)

    assert "api_gateway_open_route_review" not in codes(result)
    # Route authorization is recognized, while untaggable ownership remains denied.
    assert result.verdict == PlanPolicyVerdict.DENY


def test_authenticated_route_with_exact_remote_state_record_passes_ownership_check():
    document, proposal_value = add_api_gateway_route(plan(), "AWS_IAM")

    result = evaluate_generated_plan_policy(
        document,
        proposal_value,
        expected_account_id=ACCOUNT,
        expected_region=REGION,
        ownership_scope=ownership_scope(),
        trusted_configuration={
            "data": {"aws_caller_identity": {"trusted": {}}},
            "resource": {
                "terraform_data": {
                    "account_guard": {
                        "lifecycle": {
                            "precondition": {
                                "condition": '${data.aws_caller_identity.trusted.account_id == "'
                                + ACCOUNT
                                + '"}'
                            }
                        }
                    }
                }
            },
        },
        untagged_resource_ownership=(
            UntaggedResourceOwnershipRecord(
                address="aws_apigatewayv2_route.application",
                resource_type="aws_apigatewayv2_route",
            ),
        ),
    )

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert "resource_ownership_tags_missing" not in codes(result)
    assert "api_gateway_open_route_review" not in codes(result)


def test_api_gateway_route_cannot_target_api_outside_deployment():
    document, proposal_value = add_api_gateway_route(plan(), "AWS_IAM")
    document["configuration"]["root_module"]["resources"][0]["expressions"]["api_id"][
        "references"
    ] = ["aws_apigatewayv2_api.external.id"]

    result = evaluate_generated_plan_policy(
        document,
        proposal_value,
        expected_account_id=ACCOUNT,
        expected_region=REGION,
        ownership_scope=ownership_scope(),
        trusted_configuration={
            "data": {"aws_caller_identity": {"trusted": {}}},
            "resource": {
                "terraform_data": {
                    "account_guard": {
                        "lifecycle": {
                            "precondition": {
                                "condition": '${data.aws_caller_identity.trusted.account_id == "'
                                + ACCOUNT
                                + '"}'
                            }
                        }
                    }
                }
            },
        },
        untagged_resource_ownership=(
            UntaggedResourceOwnershipRecord(
                address="aws_apigatewayv2_route.application",
                resource_type="aws_apigatewayv2_route",
            ),
        ),
    )

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "api_gateway_route_target_not_owned" in codes(result)


@pytest.mark.parametrize("authorization_type", [_OMIT, None, "", "INVALID", ["JWT"]])
def test_missing_or_invalid_api_gateway_route_authorization_is_denied(authorization_type):
    document, proposal_value = add_api_gateway_route(plan(), authorization_type)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "api_gateway_route_authorization_unknown" in codes(result)


def test_unknown_api_gateway_route_authorization_is_denied():
    document, proposal_value = add_api_gateway_route(
        plan(), "JWT", after_unknown={"authorization_type": True}
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


@pytest.mark.parametrize(
    "unknown_field",
    ["principal", "source_arn", "source_account", "principal_org_id", "function_url_auth_type"],
)
def test_unknown_lambda_permission_security_fields_are_denied(unknown_field):
    document = add_lambda_permission(
        plan(),
        {
            "action": "lambda:InvokeFunction",
            "function_name": "application-handler",
            "principal": "apigateway.amazonaws.com",
        },
        after_unknown={unknown_field: True},
    )

    assert "policy_critical_value_unknown" in codes(evaluate(document))


@pytest.mark.parametrize(
    "policy",
    [
        {"Statement": "malformed"},
        {"Statement": ["malformed"]},
        {"Statement": {"Effect": "Allow", "Action": 7, "Principal": "*", "Resource": "*"}},
        {"Statement": {"Effect": "Allow", "Action": "s3:GetObject", "Principal": [], "Resource": "*"}},
    ],
)
def test_malformed_public_bucket_policy_fails_closed(policy):
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(
        resource("aws_s3_bucket_policy.policy", "aws_s3_bucket_policy", {"policy": json.dumps(policy)})
    )
    document["resource_changes"].append(change("aws_s3_bucket_policy.policy", "aws_s3_bucket_policy"))
    proposal_value = proposal(
        [
            *(item.model_dump(mode="json") for item in proposal().resources),
            {"resource_id": "bucket-policy", "resource_type": "aws_s3_bucket_policy", "name": "policy",
             "arguments": {"bucket": "private-plan-bucket", "policy": json.dumps(policy)},
             "rationale": "Malformed policy regression."},
        ]
    )
    assert evaluate(document, proposal_value).verdict == PlanPolicyVerdict.DENY


@pytest.mark.parametrize("port", [22, 3306, 5432, 6379])
def test_public_admin_or_database_ingress_is_denied(port):
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(
        resource(
            "aws_security_group_rule.ingress",
            "aws_security_group_rule",
            {"protocol": "tcp", "from_port": port, "to_port": port, "cidr_blocks": ["0.0.0.0/0"]},
        )
    )
    document["resource_changes"].append(change("aws_security_group_rule.ingress", "aws_security_group_rule"))
    assert "public_sensitive_port" in codes(evaluate(document))


def test_public_web_ingress_is_flagged_for_review():
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(
        resource(
            "aws_security_group_rule.web",
            "aws_security_group_rule",
            {"protocol": "tcp", "from_port": 443, "to_port": 443, "cidr_blocks": ["0.0.0.0/0"]},
        )
    )
    document["resource_changes"].append(change("aws_security_group_rule.web", "aws_security_group_rule"))
    assert "public_web_ingress_review" in codes(evaluate(document))


def test_unknown_ingress_source_fails_closed():
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(
        resource("aws_security_group_rule.unknown", "aws_security_group_rule", {"from_port": 8080, "to_port": 8080})
    )
    document["resource_changes"].append(change("aws_security_group_rule.unknown", "aws_security_group_rule"))
    assert "security_group_ingress_unknown" in codes(evaluate(document))


def test_unknown_s3_public_access_setting_is_denied_from_plan_unknowns():
    document = plan()
    document["resource_changes"][1]["change"]["after_unknown"] = {"block_public_acls": True}
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


def test_unknown_iam_policy_document_is_denied_even_when_after_values_look_safe():
    policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {"Effect": "Allow", "Action": "s3:GetObject", "Resource": "arn:aws:s3:::private-plan-bucket/*"}
            ],
        }
    )
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(
        resource("aws_iam_policy.app", "aws_iam_policy", {"policy": policy})
    )
    document["resource_changes"].append(
        change(
            "aws_iam_policy.app",
            "aws_iam_policy",
            after_unknown={"policy": True},
        )
    )
    proposal_value = proposal(
        [
            *(item.model_dump(mode="json") for item in proposal().resources),
            {
                "resource_id": "app-policy",
                "resource_type": "aws_iam_policy",
                "name": "app",
                "arguments": {"policy": policy},
                "rationale": "Limit application access to its own files.",
            },
        ]
    )
    result = evaluate(document, proposal_value)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


def test_unknown_database_encryption_is_denied_even_when_after_values_look_safe():
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(
        resource(
            "aws_db_instance.database",
            "aws_db_instance",
            {"publicly_accessible": False, "storage_encrypted": True, "backup_retention_period": 7},
        )
    )
    document["resource_changes"].append(
        change(
            "aws_db_instance.database",
            "aws_db_instance",
            after_unknown={"storage_encrypted": True},
        )
    )
    proposal_value = proposal(
        [
            *(item.model_dump(mode="json") for item in proposal().resources),
            {
                "resource_id": "database",
                "resource_type": "aws_db_instance",
                "name": "database",
                "arguments": {"publicly_accessible": False, "storage_encrypted": True, "backup_retention_period": 7},
                "rationale": "Keep application data private and encrypted.",
            },
        ]
    )
    result = evaluate(document, proposal_value)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


def test_unknown_rds_backup_retention_is_denied_even_when_after_values_look_safe():
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(
        resource(
            "aws_db_instance.database",
            "aws_db_instance",
            {"publicly_accessible": False, "storage_encrypted": True, "backup_retention_period": 7},
        )
    )
    document["resource_changes"].append(
        change(
            "aws_db_instance.database",
            "aws_db_instance",
            after_unknown={"backup_retention_period": True},
        )
    )
    proposal_value = proposal(
        [
            *(item.model_dump(mode="json") for item in proposal().resources),
            {
                "resource_id": "database",
                "resource_type": "aws_db_instance",
                "name": "database",
                "arguments": {"publicly_accessible": False, "storage_encrypted": True, "backup_retention_period": 7},
                "rationale": "Keep application data private, encrypted, and recoverable.",
            },
        ]
    )
    result = evaluate(document, proposal_value)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


def test_unknown_computed_identifier_does_not_block_policy_review():
    document = plan()
    document["resource_changes"][1]["change"]["after_unknown"] = {"id": True}
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW


def test_unresolved_kms_key_reference_is_outside_encryption_algorithm_unknown_gate():
    unknowns = {
        "rule": [
            {"apply_server_side_encryption_by_default": {"kms_master_key_id": True}}
        ]
    }
    assert not _path_contains_unknown(
        unknowns,
        ("rule", "apply_server_side_encryption_by_default", "sse_algorithm"),
    )


def test_unknown_s3_default_encryption_rule_is_denied():
    document = plan()
    encryption_change = next(
        item
        for item in document["resource_changes"]
        if item.get("type")
        == "aws_s3_bucket_server_side_encryption_configuration"
    )
    encryption_change["change"]["after_unknown"] = {"rule": True}

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


def test_malformed_unknown_metadata_fails_closed():
    document = plan()
    document["resource_changes"][1]["change"]["after_unknown"] = ["invalid"]
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_unknown_structure_invalid" in codes(result)


def test_non_boolean_unknown_leaf_fails_closed():
    document = plan()
    document["resource_changes"][1]["change"]["after_unknown"] = {"block_public_acls": False}
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_unknown_structure_invalid" in codes(result)


@pytest.mark.parametrize("viewer_policy", ["https-only", "redirect-to-https"])
def test_cloudfront_all_cache_behaviors_require_https(viewer_policy):
    document, proposal_value = cloudfront_case(
        [{"viewer_protocol_policy": viewer_policy}],
        [{"viewer_protocol_policy": viewer_policy}],
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert not {
        "cloudfront_cleartext_viewer_access",
        "cloudfront_viewer_protocol_unknown",
        "cloudfront_viewer_behavior_unknown",
        "policy_critical_value_unknown",
    } & codes(result)


@pytest.mark.parametrize("field", ["default", "ordered"])
def test_cloudfront_allow_all_viewer_policy_is_denied(field):
    default_behaviors = [{"viewer_protocol_policy": "https-only"}]
    ordered_behaviors = [{"viewer_protocol_policy": "https-only"}]
    if field == "default":
        default_behaviors[0]["viewer_protocol_policy"] = "allow-all"
    else:
        ordered_behaviors[0]["viewer_protocol_policy"] = "allow-all"
    document, proposal_value = cloudfront_case(default_behaviors, ordered_behaviors)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "cloudfront_cleartext_viewer_access" in codes(result)


@pytest.mark.parametrize(
    ("default_behaviors", "ordered_behaviors"),
    [
        ([], []),
        ([{"viewer_protocol_policy": "future-value"}], []),
        ([{"viewer_protocol_policy": ["https-only"]}], []),
        ([{"viewer_protocol_policy": "https-only"}], [{"viewer_protocol_policy": None}]),
    ],
)
def test_cloudfront_missing_or_unrecognized_viewer_policy_is_denied(
    default_behaviors, ordered_behaviors
):
    document, proposal_value = cloudfront_case(default_behaviors, ordered_behaviors)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert {
        "cloudfront_viewer_protocol_unknown",
        "cloudfront_viewer_behavior_unknown",
    } & codes(result)


def test_cloudfront_unknown_viewer_policy_fails_closed_without_echoing_values():
    document, proposal_value = cloudfront_case(
        [{"viewer_protocol_policy": "https-only"}],
        after_unknown={
            "default_cache_behavior": [{"viewer_protocol_policy": True}],
        },
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)
    assert "viewer_protocol_policy" not in repr(result)


@pytest.mark.parametrize("origin_policy", ["https-only", "match-viewer"])
def test_cloudfront_custom_origin_requires_https(origin_policy):
    origins = [
        {
            "domain_name": "origin.example.com",
            "origin_id": "origin",
            "custom_origin_config": [
                {
                    "origin_protocol_policy": origin_policy,
                    "origin_ssl_protocols": ["TLSv1.2"],
                }
            ],
        }
    ]
    document, proposal_value = cloudfront_case(
        [{"viewer_protocol_policy": "redirect-to-https"}], origins=origins
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert not {
        "cloudfront_cleartext_origin_access",
        "cloudfront_origin_protocol_unknown",
        "cloudfront_origin_tls_protocol_weak_or_unknown",
        "cloudfront_origin_settings_unknown",
    } & codes(result)


@pytest.mark.parametrize(
    ("origin_policy", "expected_code"),
    [
        ("http-only", "cloudfront_cleartext_origin_access"),
        ("future-value", "cloudfront_origin_protocol_unknown"),
        (["https-only"], "cloudfront_origin_protocol_unknown"),
        (None, "cloudfront_origin_protocol_unknown"),
    ],
)
def test_cloudfront_custom_origin_cleartext_or_unknown_protocol_is_denied(
    origin_policy, expected_code
):
    origins = [
        {
            "domain_name": "origin.example.com",
            "origin_id": "origin",
            "custom_origin_config": [
                {
                    "origin_protocol_policy": origin_policy,
                    "origin_ssl_protocols": ["TLSv1.2"],
                }
            ],
        }
    ]
    document, proposal_value = cloudfront_case(
        [{"viewer_protocol_policy": "https-only"}], origins=origins
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert expected_code in codes(result)
    if isinstance(origin_policy, str):
        assert origin_policy not in repr(result)


@pytest.mark.parametrize(
    "ssl_protocols", [[], ["TLSv1.1"], ["TLSv1.1", "TLSv1.2"], None]
)
def test_cloudfront_custom_origin_rejects_weak_or_unknown_tls(ssl_protocols):
    origins = [
        {
            "domain_name": "origin.example.com",
            "origin_id": "origin",
            "custom_origin_config": [
                {
                    "origin_protocol_policy": "https-only",
                    "origin_ssl_protocols": ssl_protocols,
                }
            ],
        }
    ]
    document, proposal_value = cloudfront_case(
        [{"viewer_protocol_policy": "https-only"}], origins=origins
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "cloudfront_origin_tls_protocol_weak_or_unknown" in codes(result)


@pytest.mark.parametrize("origins", [[], [{}], [None]])
def test_cloudfront_origin_inventory_must_be_complete(origins):
    document, proposal_value = cloudfront_case(
        [{"viewer_protocol_policy": "https-only"}], origins=origins
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "cloudfront_origin_settings_unknown" in codes(result)


def test_cloudfront_standard_s3_origin_uses_enforced_viewer_https():
    origins = [
        {
            "domain_name": "private-bucket.s3.us-east-1.amazonaws.com",
            "origin_id": "private-bucket",
            "s3_origin_config": [{"origin_access_identity": ""}],
        }
    ]
    document, proposal_value = cloudfront_case(
        [{"viewer_protocol_policy": "https-only"}], origins=origins
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert "cloudfront_origin_settings_unknown" not in codes(result)


def test_cloudfront_match_viewer_origin_still_requires_secure_viewer_policy():
    origins = [
        {
            "domain_name": "origin.example.com",
            "origin_id": "origin",
            "custom_origin_config": [
                {
                    "origin_protocol_policy": "match-viewer",
                    "origin_ssl_protocols": ["TLSv1.2"],
                }
            ],
        }
    ]
    document, proposal_value = cloudfront_case(
        [{"viewer_protocol_policy": "allow-all"}], origins=origins
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "cloudfront_cleartext_viewer_access" in codes(result)


def test_cloudfront_unknown_origin_tls_settings_fail_closed_without_echoing_values():
    document, proposal_value = cloudfront_case(
        [{"viewer_protocol_policy": "https-only"}],
        after_unknown={
            "origin": [
                {
                    "custom_origin_config": [
                        {"origin_ssl_protocols": True},
                    ]
                }
            ]
        },
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)
    assert "origin_ssl_protocols" not in repr(result)


@pytest.mark.parametrize("metadata", [None, "missing"])
def test_missing_unknown_metadata_fails_closed_for_monitored_resource(metadata):
    document = plan()
    change_document = document["resource_changes"][1]["change"]
    if metadata == "missing":
        change_document.pop("after_unknown")
    else:
        change_document["after_unknown"] = metadata
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_unknown_structure_invalid" in codes(result)


def test_malformed_ingress_cidr_fails_closed():
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(
        resource(
            "aws_security_group_rule.bad_cidr", "aws_security_group_rule",
            {"from_port": 8080, "to_port": 8080, "cidr_blocks": ["not-a-cidr"]},
        )
    )
    document["resource_changes"].append(change("aws_security_group_rule.bad_cidr", "aws_security_group_rule"))
    assert "security_group_ingress_unknown" in codes(evaluate(document))


def test_scoped_security_group_source_is_not_treated_as_unknown_or_public():
    ingress = resource(
        "aws_security_group_rule.internal", "aws_security_group_rule",
        {"from_port": 8080, "to_port": 8080, "protocol": "tcp", "source_security_group_id": "sg-0123456789abcdef0"},
    )
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(ingress)
    document["resource_changes"].append(change("aws_security_group_rule.internal", "aws_security_group_rule"))
    proposal_value = proposal(
        [
            *(item.model_dump(mode="json") for item in proposal().resources),
            {"resource_id": "internal-ingress", "resource_type": "aws_security_group_rule", "name": "internal",
             "arguments": {"from_port": 8080, "to_port": 8080, "protocol": "tcp", "source_security_group_id": "sg-0123456789abcdef0"},
             "rationale": "Allow traffic from a scoped application security group."},
        ]
    )
    result = evaluate(document, proposal_value)
    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert result.findings == ()


@pytest.mark.parametrize(
    ("source_key", "source", "port"),
    [
        ("cidr_block", "8.0.0.0/8", 22),
        ("cidr_block", "1.1.1.1/32", 5432),
        ("ipv6_cidr_block", "2606:4700::/32", 3306),
    ],
)
def test_public_network_acl_admin_and_data_ports_are_denied(source_key, source, port):
    document = plan()
    other_source_key = "ipv6_cidr_block" if source_key == "cidr_block" else "cidr_block"
    arguments = {
        "egress": False,
        "protocol": "6",
        "rule_action": "allow",
        "rule_number": 100,
        "from_port": port,
        "to_port": port,
        source_key: source,
        other_source_key: None,
    }
    proposal_value = add_network_resource(document, "aws_network_acl_rule", "public", arguments)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "network_acl_public_sensitive_port_denied" in codes(result)


def test_public_network_acl_all_protocols_is_denied():
    document = plan()
    proposal_value = add_network_resource(
        document,
        "aws_network_acl_rule",
        "all_protocols",
        {
            "egress": False,
            "protocol": "-1",
            "rule_action": "allow",
            "rule_number": 100,
            "cidr_block": "1.1.1.0/24",
        },
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "network_acl_public_all_protocols_denied" in codes(result)


def test_public_network_acl_web_ingress_requires_review():
    document = plan()
    proposal_value = add_network_resource(
        document,
        "aws_network_acl_rule",
        "public_web",
        {
            "egress": False,
            "protocol": "6",
            "rule_action": "allow",
            "rule_number": 100,
            "from_port": 443,
            "to_port": 443,
            "cidr_block": "1.1.1.0/24",
        },
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.REVIEW_REQUIRED
    assert "network_acl_public_web_ingress_review" in codes(result)


def test_private_network_acl_ingress_and_public_egress_are_not_public_ingress():
    document = plan()
    proposal_resources = add_network_resource(
        document,
        "aws_network_acl_rule",
        "private_ingress",
        {
            "egress": False,
            "protocol": "6",
            "rule_action": "allow",
            "rule_number": 100,
            "from_port": 8080,
            "to_port": 8080,
            "cidr_block": "10.0.0.0/8",
        },
    )
    proposal_value = add_network_resource(
        document,
        "aws_network_acl_rule",
        "public_egress",
        {
            "egress": True,
            "protocol": "-1",
            "rule_action": "allow",
            "rule_number": 101,
            "cidr_block": "0.0.0.0/0",
        },
    )
    # Retain both proposed resources in the test contract.
    proposal_value = proposal(
        [item.model_dump(mode="json") for item in proposal_resources.resources]
        + [item.model_dump(mode="json") for item in proposal_value.resources if item.resource_id == "public-egress"]
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert not any(code.startswith("network_acl_public_") for code in codes(result))


def test_network_acl_malformed_and_unknown_values_fail_closed():
    document = plan()
    proposal_value = add_network_resource(
        document,
        "aws_network_acl_rule",
        "unknown_source",
        {
            "egress": False,
            "protocol": "6",
            "rule_action": "allow",
            "rule_number": 100,
            "from_port": 80,
            "to_port": 80,
            "cidr_block": "not-a-cidr",
        },
    )
    assert "network_acl_ingress_unknown" in codes(evaluate(document, proposal_value))

    document = plan()
    proposal_value = add_network_resource(
        document,
        "aws_network_acl_rule",
        "unknown_port",
        {
            "egress": False,
            "protocol": "6",
            "rule_action": "allow",
            "rule_number": 100,
            "from_port": 80,
            "to_port": 80,
            "cidr_block": "1.1.1.0/24",
        },
        after_unknown={"to_port": True},
    )
    result = evaluate(document, proposal_value)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


def test_inline_network_acl_public_sensitive_ingress_is_denied():
    document = plan()
    proposal_value = add_network_resource(
        document,
        "aws_network_acl",
        "application",
        {
            "vpc_id": "vpc-0123456789abcdef0",
            "ingress": [
                {
                    "protocol": "6",
                    "rule_action": "allow",
                    "rule_no": 100,
                    "from_port": 22,
                    "to_port": 22,
                    "cidr_block": "1.1.1.0/24",
                }
            ],
            "egress": [],
        },
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "network_acl_public_sensitive_port_denied" in codes(result)


def test_default_network_acl_public_data_ingress_is_denied():
    document = plan()
    proposal_value = add_network_resource(
        document,
        "aws_default_network_acl",
        "default",
        {
            "default_network_acl_id": "acl-0123456789abcdef0",
            "ingress": [
                {
                    "protocol": "6",
                    "rule_action": "allow",
                    "rule_no": 100,
                    "from_port": 27017,
                    "to_port": 27017,
                    "cidr_block": "8.8.8.0/24",
                }
            ],
            "egress": [],
        },
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "network_acl_public_sensitive_port_denied" in codes(result)


def test_publicly_routable_security_group_cidr_is_not_limited_to_world_open_cidr():
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(
        resource(
            "aws_security_group_rule.public_database",
            "aws_security_group_rule",
            {
                "protocol": "tcp",
                "from_port": 5432,
                "to_port": 5432,
                "cidr_blocks": ["1.1.1.0/24"],
            },
        )
    )
    document["resource_changes"].append(
        change("aws_security_group_rule.public_database", "aws_security_group_rule")
    )
    proposal_value = proposal(
        [
            *(item.model_dump(mode="json") for item in proposal().resources),
            {
                "resource_id": "public-database",
                "resource_type": "aws_security_group_rule",
                "name": "public_database",
                "arguments": {
                    "protocol": "tcp",
                    "from_port": 5432,
                    "to_port": 5432,
                    "cidr_blocks": ["1.1.1.0/24"],
                },
                "rationale": "This fixture verifies non-default public CIDRs are recognized.",
            },
        ]
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "public_sensitive_port" in codes(result)


@pytest.mark.parametrize(
    "policy,expected_code",
    [
        (
            {"Statement": {"Effect": "Allow", "Action": "*", "Resource": "*"}},
            "iam_privileged_wildcard",
        ),
        (
            {
                "Statement": {
                    "Effect": "Allow",
                    "Action": "s3:GetObject",
                    "NotResource": "arn:aws:s3:::excluded-bucket/*",
                }
            },
            "iam_not_resource_policy_denied",
        ),
        (
            {"Statement": {"Effect": "Allow", "Action": "iam:PassRole", "Resource": "*"}},
            "iam_passrole_unbounded_denied",
        ),
        (
            {"Statement": {"Effect": "Allow", "Action": "sts:AssumeRole", "Resource": "*"}},
            "sts_assume_role_unbounded_denied",
        ),
        (
            {
                "Statement": {
                    "Effect": "Allow",
                    "Action": "sts:Assume*",
                    "Resource": "arn:aws:iam::654654474502:role/app",
                }
            },
            "sts_assume_role_unbounded_denied",
        ),
        (
            {
                "Statement": {
                    "Effect": "Allow",
                    "Action": "iam:CreateRole",
                    "Resource": "arn:aws:iam::654654474502:role/*",
                }
            },
            "iam_permission_management_denied",
        ),
    ],
)
def test_privileged_iam_is_denied(policy, expected_code):
    result = evaluate(
        plan(
            resources=[
                resource(
                    "aws_iam_policy.application", "aws_iam_policy", {"policy": json.dumps(policy)}
                ),
                resource("terraform_data.account_guard", "terraform_data", {"input": None}),
            ],
            changes=[
                change("aws_iam_policy.application", "aws_iam_policy"),
                change("terraform_data.account_guard", "terraform_data"),
            ],
        ),
        proposal(
            [
                {
                    "resource_id": "application",
                    "resource_type": "aws_iam_policy",
                    "name": "application",
                    "arguments": {"name": "application", "policy": json.dumps(policy)},
                    "rationale": "Application permissions.",
                }
            ]
        ),
    )
    assert result.verdict == PlanPolicyVerdict.DENY
    assert expected_code in codes(result)


def evaluate_application_policy(policy_document):
    encoded = json.dumps(policy_document)
    resource_address = "aws_iam_policy.application"
    resources = [
        resource(resource_address, "aws_iam_policy", {"name": "application", "policy": encoded}),
        resource("terraform_data.account_guard", "terraform_data", {"input": None}),
    ]
    generated = proposal(
        [
            {
                "resource_id": "application",
                "resource_type": "aws_iam_policy",
                "name": "application",
                "arguments": {"name": "application", "policy": encoded},
                "rationale": "Application permissions.",
            }
        ]
    )
    return evaluate(
        plan(
            resources,
            [
                change(resource_address, "aws_iam_policy"),
                change("terraform_data.account_guard", "terraform_data"),
            ],
        ),
        generated,
    )


@pytest.mark.parametrize("action", ["s3:*", "dynamodb:Put*", "sqs:*"])
def test_application_data_policies_deny_service_action_wildcards(action):
    result = evaluate_application_policy(
        {
            "Statement": {
                "Effect": "Allow",
                "Action": action,
                "Resource": "arn:aws:s3:::pilot-uploads",
            }
        }
    )

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "iam_privileged_wildcard" in codes(result)


@pytest.mark.parametrize(
    ("action", "resource_arn"),
    [
        ("s3:GetObject", "*"),
        ("s3:GetObject", "arn:aws:s3:::*"),
        ("dynamodb:PutItem", "arn:aws:dynamodb:us-east-1:654654474502:table/*"),
        (
            "sqs:SendMessage",
            "arn:aws:sqs:us-east-1:654654474502:*",
        ),
    ],
)
def test_application_data_policies_deny_unbounded_resource_patterns(action, resource_arn):
    result = evaluate_application_policy(
        {
            "Statement": {
                "Effect": "Allow",
                "Action": action,
                "Resource": resource_arn,
            }
        }
    )

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "iam_data_resource_unbounded" in codes(result)


@pytest.mark.parametrize(
    ("action", "resource_arn"),
    [
        ("s3:GetObject", "arn:aws:s3"),
        ("sqs:SendMessage", "arn:aws:sqs"),
        ("dynamodb:PutItem", "arn:aws:dynamodb:us-east-1:654654474502"),
    ],
)
def test_application_data_policies_deny_incomplete_resource_arns(action, resource_arn):
    result = evaluate_application_policy(
        {
            "Statement": {
                "Effect": "Allow",
                "Action": action,
                "Resource": resource_arn,
            }
        }
    )

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "iam_data_resource_unbounded" in codes(result)


@pytest.mark.parametrize(
    ("action", "resource_arn"),
    [
        ("s3:GetObject", "arn:aws:s3:::pilot-uploads"),
        ("s3:GetObject", "arn:aws:s3:::pilot-uploads/*"),
        ("s3:GetObject", "arn:aws:s3:::pilot-uploads/inbox/item.json"),
        ("sqs:SendMessage", "arn:aws:sqs:us-east-1:654654474502:pilot-queue"),
        (
            "dynamodb:PutItem",
            "arn:aws:dynamodb:us-east-1:654654474502:table/pilot-table",
        ),
        (
            "dynamodb:Query",
            "arn:aws:dynamodb:us-east-1:654654474502:table/pilot-table/index/*",
        ),
    ],
)
def test_application_data_policies_allow_exact_child_resource_scopes(action, resource_arn):
    result = evaluate_application_policy(
        {
            "Statement": {
                "Effect": "Allow",
                "Action": action,
                "Resource": resource_arn,
            }
        }
    )

    assert "iam_data_resource_unbounded" not in codes(result)


def evaluate_role_trust(trust_document):
    encoded = json.dumps(trust_document)
    role_address = "aws_iam_role.application"
    resources = [
        resource(role_address, "aws_iam_role", {"name": "application", "assume_role_policy": encoded}),
        resource("terraform_data.account_guard", "terraform_data", {"input": None}),
    ]
    generated = proposal(
        [
            {
                "resource_id": "application",
                "resource_type": "aws_iam_role",
                "name": "application",
                "arguments": {"name": "application", "assume_role_policy": trust_document},
                "rationale": "Application runtime role.",
            }
        ]
    )
    return evaluate(
        plan(
            resources,
            [change(role_address, "aws_iam_role"), change("terraform_data.account_guard", "terraform_data")],
        ),
        generated,
    )


@pytest.mark.parametrize(
    "policy",
    [
        {
            "Statement": {
                "Effect": "Allow",
                "NotAction": "iam:DeleteRole",
                "Resource": "arn:aws:iam::654654474502:role/app",
            }
        },
        {
            "Statement": {
                "Effect": "Allow",
                "Action": "iam:CreatePolicyVersion",
                "Resource": "arn:aws:iam::654654474502:policy/app",
            }
        },
        {
            "Statement": {
                "Effect": "Allow",
                "Action": "iam:AttachRolePolicy",
                "Resource": "arn:aws:iam::654654474502:role/app",
            }
        },
    ],
)
def test_exact_resource_iam_management_and_not_action_are_denied(policy):
    result = evaluate_application_policy(policy)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert {"iam_not_action_policy_denied", "iam_permission_management_denied"} & codes(result)


@pytest.mark.parametrize(
    "resource_arn,condition",
    [
        ("*", {"StringEquals": {"iam:PassedToService": "lambda.amazonaws.com"}}),
        ("arn:aws:iam::654654474502:role/app", None),
        (
            "arn:aws:iam::654654474502:role/app",
            {"StringNotEquals": {"iam:PassedToService": "lambda.amazonaws.com"}},
        ),
        (
            "arn:aws:iam::654654474502:role/*",
            {"StringEquals": {"iam:PassedToService": "lambda.amazonaws.com"}},
        ),
        (
            "arn:aws:iam::654654474502:role/app",
            {"StringEquals": {"iam:PassedToService": "*.amazonaws.com"}},
        ),
    ],
)
def test_unbounded_or_malformed_passrole_is_denied(resource_arn, condition):
    statement = {"Effect": "Allow", "Action": "iam:PassRole", "Resource": resource_arn}
    if condition is not None:
        statement["Condition"] = condition
    result = evaluate_application_policy({"Statement": statement})
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "iam_passrole_unbounded_denied" in codes(result)


def test_exact_passrole_with_literal_service_condition_requires_human_review():
    result = evaluate_application_policy(
        {
            "Statement": {
                "Effect": "Allow",
                "Action": "iam:PassRole",
                "Resource": "arn:aws:iam::654654474502:role/app/runtime",
                "Condition": {"StringEquals": {"iam:PassedToService": ["lambda.amazonaws.com"]}},
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.REVIEW_REQUIRED
    assert "iam_passrole_requires_review" in codes(result)


def test_scoped_read_only_iam_policy_remains_eligible():
    result = evaluate_application_policy(
        {
            "Statement": {
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:GetObjectVersion"],
                "Resource": "arn:aws:s3:::application-files/*",
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert result.findings == ()


@pytest.mark.parametrize(
    "action,resource_arn",
    [
        (
            "secretsmanager:GetSecretValue",
            "arn:aws:secretsmanager:us-east-1:654654474502:secret:application-password-AbCdEf",
        ),
        ("secretsmanager:BatchGetSecretValue", "*"),
        ("secretsmanager:Get*", "arn:aws:secretsmanager:us-east-1:654654474502:secret:app-*"),
        ("secretsmanager:*", "*"),
        ("SecretsManager:GETSECRETVALUE", "arn:aws:secretsmanager:us-east-1:654654474502:secret:app-AbCdEf"),
    ],
)
def test_unbound_secrets_manager_value_reads_are_denied(action, resource_arn):
    result = evaluate_application_policy(
        {
            "Statement": {
                "Effect": "Allow",
                "Action": action,
                "Resource": resource_arn,
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.DENY
    finding = next(
        item for item in result.findings if item.code == "iam_secret_value_read_unbound"
    )
    assert resource_arn not in finding.message
    assert "SecretValue" not in finding.message


def test_secrets_manager_metadata_read_remains_eligible():
    result = evaluate_application_policy(
        {
            "Statement": {
                "Effect": "Allow",
                "Action": "secretsmanager:DescribeSecret",
                "Resource": "arn:aws:secretsmanager:us-east-1:654654474502:secret:app-AbCdEf",
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert result.findings == ()


def test_specific_same_account_assume_role_requires_human_review():
    result = evaluate_application_policy(
        {
            "Statement": {
                "Effect": "Allow",
                "Action": "sts:AssumeRole",
                "Resource": "arn:aws:iam::654654474502:role/app/reader",
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.REVIEW_REQUIRED
    assert "sts_assume_role_requires_review" in codes(result)


def test_external_assume_role_is_denied():
    result = evaluate_application_policy(
        {
            "Statement": {
                "Effect": "Allow",
                "Action": "sts:AssumeRole",
                "Resource": "arn:aws:iam::111122223333:role/external",
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "sts_assume_role_unbounded_denied" in codes(result)


def test_external_account_role_trust_is_denied():
    result = evaluate_role_trust(
        {
            "Statement": {
                "Effect": "Allow",
                "Principal": {"AWS": "arn:aws:iam::111122223333:root"},
                "Action": "sts:AssumeRole",
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "iam_external_trust_denied" in codes(result)


def test_same_account_role_trust_requires_human_review():
    result = evaluate_role_trust(
        {
            "Statement": {
                "Effect": "Allow",
                "Principal": {"AWS": f"arn:aws:iam::{ACCOUNT}:root"},
                "Action": "sts:AssumeRole",
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.REVIEW_REQUIRED
    assert "iam_same_account_trust_requires_review" in codes(result)


def test_allow_not_principal_trust_is_denied():
    result = evaluate_role_trust(
        {
            "Statement": {
                "Effect": "Allow",
                "NotPrincipal": {"AWS": f"arn:aws:iam::{ACCOUNT}:role/blocked"},
                "Action": "sts:AssumeRole",
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "iam_not_principal_trust_denied" in codes(result)


def test_exact_aws_service_trust_is_accepted_without_extra_review():
    result = evaluate_role_trust(
        {
            "Statement": {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert result.findings == ()


def test_non_admin_managed_policy_attachment_requires_human_review():
    resources = [
        resource(
            "aws_iam_role.application",
            "aws_iam_role",
            {
                "name": "application",
                "assume_role_policy": json.dumps(
                    {
                        "Statement": {
                            "Effect": "Allow",
                            "Principal": {"Service": "lambda.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }
                    }
                ),
            },
        ),
        resource(
            "aws_iam_role_policy_attachment.runtime",
            "aws_iam_role_policy_attachment",
            {"policy_arn": "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"},
        ),
        resource("terraform_data.account_guard", "terraform_data", {"input": None}),
    ]
    generated = proposal(
        [
            {
                "resource_id": "application",
                "resource_type": "aws_iam_role",
                "name": "application",
                "arguments": {
                    "name": "application",
                    "assume_role_policy": {
                        "Version": "2012-10-17",
                        "Statement": {
                            "Effect": "Allow",
                            "Principal": {"Service": "lambda.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        },
                    },
                },
                "outputs": [{"name": "name", "value_type": "string"}],
                "rationale": "Lambda runtime role.",
            },
            {
                "resource_id": "runtime",
                "resource_type": "aws_iam_role_policy_attachment",
                "name": "runtime",
                "arguments": {
                    "role": {
                        "kind": "resource_reference",
                        "resource_id": "application",
                        "output_name": "name",
                        "value_type": "string",
                    },
                    "policy_arn": "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                },
                "rationale": "Permit application logging.",
            },
        ]
    )
    document = plan(resources, [change(item["address"], item["type"]) for item in resources])
    result = evaluate(document, generated)
    assert result.verdict == PlanPolicyVerdict.REVIEW_REQUIRED
    assert "iam_managed_policy_contents_unverified" in codes(result)


def test_wildcard_role_trust_and_administrator_attachment_are_denied():
    resources = [
        resource("aws_iam_role.application", "aws_iam_role", {"assume_role_policy": json.dumps({"Statement": {"Effect": "Allow", "Principal": "*", "Action": "sts:AssumeRole"}})}),
        resource("aws_iam_role_policy_attachment.admin", "aws_iam_role_policy_attachment", {"policy_arn": "arn:aws:iam::aws:policy/AdministratorAccess"}),
        resource("terraform_data.account_guard", "terraform_data", {"input": None}),
    ]
    generated = [
        {"resource_id": "application", "resource_type": "aws_iam_role", "name": "application", "arguments": {"name": "application", "assume_role_policy": json.dumps({"Statement": {"Effect": "Allow", "Principal": "*", "Action": "sts:AssumeRole"}})}, "rationale": "Application role."},
        {"resource_id": "admin", "resource_type": "aws_iam_role_policy_attachment", "name": "admin", "arguments": {"role": "application", "policy_arn": "arn:aws:iam::aws:policy/AdministratorAccess"}, "rationale": "Test denied attachment."},
    ]
    document = plan(resources, [change(item["address"], item["type"]) for item in resources])
    result = evaluate(document, proposal(generated))
    assert {"iam_wildcard_trust", "iam_administrator_access_attached"}.issubset(codes(result))


@pytest.mark.parametrize(
    "kind,values,expected",
    [
        ("aws_db_instance", {"publicly_accessible": True, "storage_encrypted": True, "backup_retention_period": 7}, "database_publicly_accessible"),
        ("aws_db_instance", {"publicly_accessible": False, "storage_encrypted": False, "backup_retention_period": 7}, "database_encryption_required"),
        ("aws_db_instance", {"storage_encrypted": True, "backup_retention_period": 7}, "database_publicly_accessible"),
    ],
)
def test_database_publicness_and_encryption_fail_closed(kind, values, expected):
    address = f"{kind}.database"
    resources = [resource(address, kind, values), resource("terraform_data.account_guard", "terraform_data", {"input": None})]
    proposal_value = proposal([{"resource_id": "database", "resource_type": kind, "name": "database", "arguments": {"identifier": "database", **values}, "rationale": "Database."}])
    result = evaluate(plan(resources, [change(address, kind), change("terraform_data.account_guard", "terraform_data")]), proposal_value)
    assert expected in codes(result)


@pytest.mark.parametrize(
    "kind,retention",
    [
        ("aws_db_instance", _OMIT),
        ("aws_db_instance", "seven"),
        ("aws_rds_cluster", _OMIT),
        ("aws_rds_cluster", 1.5),
    ],
)
def test_rds_backup_retention_must_be_explicit_and_well_formed(kind, retention):
    values = {"publicly_accessible": False, "storage_encrypted": True}
    if retention is not _OMIT:
        values["backup_retention_period"] = retention
    address = f"{kind}.database"
    resources = [
        resource(address, kind, values),
        resource("terraform_data.account_guard", "terraform_data", {"input": None}),
    ]
    proposal_value = proposal(
        [
            {
                "resource_id": "database",
                "resource_type": kind,
                "name": "database",
                "arguments": {"identifier": "database", **values},
                "rationale": "Database with an explicit backup policy.",
            }
        ]
    )
    result = evaluate(
        plan(resources, [change(address, kind), change("terraform_data.account_guard", "terraform_data")]),
        proposal_value,
    )
    assert "database_backup_retention_invalid" in codes(result)


@pytest.mark.parametrize(
    "kind,retention,expected",
    [
        ("aws_db_instance", 0, "database_backup_retention_disabled"),
        ("aws_db_instance", -1, "database_backup_retention_invalid"),
        ("aws_db_instance", 36, "database_backup_retention_invalid"),
        ("aws_db_instance", True, "database_backup_retention_invalid"),
        ("aws_rds_cluster", 0, "database_backup_retention_invalid"),
        ("aws_rds_cluster", 7, None),
    ],
)
def test_rds_backup_retention_is_bounded_and_disabled_instance_backups_require_review(kind, retention, expected):
    values = {
        "publicly_accessible": False,
        "storage_encrypted": True,
        "backup_retention_period": retention,
    }
    address = f"{kind}.database"
    resources = [
        resource(address, kind, values),
        resource("terraform_data.account_guard", "terraform_data", {"input": None}),
    ]
    proposal_value = proposal(
        [
            {
                "resource_id": "database",
                "resource_type": kind,
                "name": "database",
                "arguments": {"identifier": "database", **values},
                "rationale": "Database with an explicit backup policy.",
            }
        ]
    )
    result = evaluate(
        plan(resources, [change(address, kind), change("terraform_data.account_guard", "terraform_data")]),
        proposal_value,
    )
    if expected is None:
        assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
        assert "database_backup_retention_invalid" not in codes(result)
    else:
        assert expected in codes(result)


@pytest.mark.parametrize(
    "skip_snapshot,identifier,expected",
    [
        (True, None, "rds_final_snapshot_skipped"),
        (False, "final-database-snapshot", None),
        (False, None, "rds_final_snapshot_identifier_missing"),
    ],
)
def test_rds_replacement_requires_valid_final_snapshot_or_explicit_review(skip_snapshot, identifier, expected):
    address = "aws_db_instance.database"
    before = {
        "tags": ownership_scope().tags(),
        "skip_final_snapshot": skip_snapshot,
        "final_snapshot_identifier": identifier,
    }
    values = {
        "publicly_accessible": False,
        "storage_encrypted": True,
        "backup_retention_period": 7,
    }
    document = plan(
        [
            resource(address, "aws_db_instance", values),
            resource("terraform_data.account_guard", "terraform_data", {"input": None}),
        ],
        [
            change(
                address,
                "aws_db_instance",
                ("delete", "create"),
                before=before,
                after={"tags": ownership_scope().tags()},
            ),
            change("terraform_data.account_guard", "terraform_data"),
        ],
    )
    proposal_value = proposal(
        [
            {
                "resource_id": "database",
                "resource_type": "aws_db_instance",
                "name": "database",
                "arguments": {"identifier": "database", **values},
                "rationale": "Database with explicit retention and encryption.",
            }
        ]
    )
    result = evaluate(document, proposal_value)
    if expected is None:
        assert result.verdict == PlanPolicyVerdict.REVIEW_REQUIRED
        assert "rds_final_snapshot_skipped" not in codes(result)
        assert "destructive_change_requires_review" in codes(result)
    else:
        assert expected in codes(result)


@pytest.mark.parametrize(
    "before,expected",
    [
        ({"skip_final_snapshot": True}, "rds_final_snapshot_skipped"),
        ({"skip_final_snapshot": False, "final_snapshot_identifier": "final-db"}, None),
        ({"skip_final_snapshot": False}, "rds_final_snapshot_identifier_missing"),
        ({"skip_final_snapshot": "unknown"}, "rds_final_snapshot_setting_unknown"),
    ],
)
def test_rds_delete_final_snapshot_policy(before, expected):
    findings = []
    _check_rds_final_snapshot_changes(
        {
            "resource_changes": [
                {
                    "address": "aws_db_instance.database",
                    "type": "aws_db_instance",
                    "change": {"actions": ["delete"], "before": before},
                }
            ]
        },
        findings,
    )
    codes_found = {finding.code for finding in findings}
    if expected is None:
        assert "rds_final_snapshot_skipped" not in codes_found
        assert "rds_final_snapshot_identifier_missing" not in codes_found
    else:
        assert expected in codes_found


def test_unexpected_region_or_resource_inventory_is_denied():
    wrong_region = plan()
    wrong_region["configuration"]["provider_config"]["aws"]["expressions"]["region"]["constant_value"] = "eu-west-1"
    assert evaluate(wrong_region).verdict == PlanPolicyVerdict.DENY
    extra = plan()
    extra["planned_values"]["root_module"]["resources"].append(resource("aws_s3_bucket.extra", "aws_s3_bucket", {"bucket": "unapproved"}))
    assert "plan_resource_inventory_mismatch" in codes(evaluate(extra))


@pytest.mark.parametrize("guard", [None, "${true}", '${data.aws_caller_identity.trusted.account_id == "111111111111"}'])
def test_missing_or_mismatched_trusted_account_guard_is_denied(guard):
    trusted = {
        "data": {"aws_caller_identity": {"trusted": {}}},
        "resource": {"terraform_data": {"account_guard": {"lifecycle": {"precondition": {"condition": guard}}}}},
    }
    result = evaluate_generated_plan_policy(
        plan(),
        proposal(),
        expected_account_id=ACCOUNT,
        expected_region=REGION,
        ownership_scope=ownership_scope(),
        trusted_configuration=trusted,
    )
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "plan_policy_input_invalid" in codes(result)


def test_nested_unproposed_resource_is_not_hidden_from_inventory():
    document = plan()
    document["planned_values"]["root_module"]["child_modules"] = [
        {"resources": [resource("module.hidden.aws_s3_bucket.extra", "aws_s3_bucket", {"bucket": "extra"})]}
    ]
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "plan_resource_inventory_mismatch" in codes(result)


def test_unexplained_unknown_plan_shape_fails_closed_without_echoing_values():
    secret = "super-secret-plan-value"
    document = plan()
    document["planned_values"]["root_module"]["resources"] = secret
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert secret not in repr(result)


def test_delete_replacement_and_sensitive_change_require_human_review():
    document = plan()
    document["resource_changes"] = [
        change("aws_s3_bucket.bucket", "aws_s3_bucket", ("delete",), before_sensitive={"secret": True}),
        change("aws_s3_bucket_public_access_block.public_access", "aws_s3_bucket_public_access_block"),
        change("aws_s3_bucket_policy.transport_policy", "aws_s3_bucket_policy", ("delete",)),
        change(
            "aws_s3_bucket_server_side_encryption_configuration.encryption",
            "aws_s3_bucket_server_side_encryption_configuration",
            ("delete",),
        ),
        change(
            "aws_s3_bucket_ownership_controls.ownership",
            "aws_s3_bucket_ownership_controls",
            ("delete",),
        ),
        change("terraform_data.account_guard", "terraform_data"),
    ]
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.REVIEW_REQUIRED
    assert {"destructive_change_requires_review", "sensitive_change_requires_review"}.issubset(codes(result))


def test_delete_requires_matching_ownership_on_the_existing_resource():
    document = plan()
    document["resource_changes"][0] = change(
        "aws_s3_bucket.bucket",
        "aws_s3_bucket",
        ("delete",),
        before={"tags": {**ownership_scope().tags(), "DavDeployPlanId": "another-plan"}},
    )

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "resource_ownership_tags_mismatch" in codes(result)


def test_replacement_with_matching_ownership_on_both_sides_requires_review():
    document = plan()
    document["resource_changes"][0] = change(
        "aws_s3_bucket.bucket",
        "aws_s3_bucket",
        ("delete", "create"),
    )

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.REVIEW_REQUIRED
    assert "destructive_change_requires_review" in codes(result)
    assert "resource_ownership_tags_mismatch" not in codes(result)


def test_replacement_requires_matching_ownership_before_and_after():
    document = plan()
    document["resource_changes"][0] = change(
        "aws_s3_bucket.bucket",
        "aws_s3_bucket",
        ("delete", "create"),
        before={"tags": {**ownership_scope().tags(), "DavDeployPlanId": "another-plan"}},
        after={"tags": ownership_scope().tags()},
    )

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "resource_ownership_tags_mismatch" in codes(result)


@pytest.mark.parametrize("actions", [("update",), ("delete",), ("delete", "create")])
def test_existing_resource_accepts_prior_source_revision_for_same_plan(actions):
    document = plan()
    existing = change("aws_s3_bucket.bucket", "aws_s3_bucket", actions)
    existing["change"]["before"]["tags"]["DavDeploySourceRevision"] = (
        "sha256:" + "a" * 64
    )
    document["resource_changes"][0] = existing
    if actions == ("delete",):
        # Deleted resources may not appear in planned_values. Their before
        # values still need to prove stable ownership and a valid prior revision.
        document["planned_values"]["root_module"]["resources"] = document[
            "planned_values"
        ]["root_module"]["resources"][1:]

    result = evaluate(document)

    assert "resource_ownership_tags_mismatch" not in codes(result)
    assert "resource_ownership_tags_missing" not in codes(result)
    if actions in (("delete",), ("delete", "create")):
        assert "destructive_change_requires_review" in codes(result)


def test_existing_resource_requires_well_formed_prior_source_revision():
    document = plan()
    existing = change("aws_s3_bucket.bucket", "aws_s3_bucket", ("update",))
    existing["change"]["before"]["tags"]["DavDeploySourceRevision"] = "old-revision"
    document["resource_changes"][0] = existing

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "resource_ownership_tags_mismatch" in codes(result)


def test_desired_resource_requires_exact_current_source_revision():
    document = plan()
    document["resource_changes"][0]["change"]["after"]["tags"][
        "DavDeploySourceRevision"
    ] = "sha256:" + "a" * 64

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "resource_ownership_tags_mismatch" in codes(result)


@pytest.mark.parametrize("actions", [("forget",), ("update", "forget")])
def test_unknown_managed_aws_actions_are_denied(actions):
    document = plan()
    document["resource_changes"][0] = change("aws_s3_bucket.bucket", "aws_s3_bucket", actions)

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "plan_policy_input_invalid" in codes(result)


def test_delete_of_resource_outside_proposal_is_denied():
    document = plan()
    document["resource_changes"].append(change("aws_s3_bucket.unowned", "aws_s3_bucket", ("delete",)))
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "unproposed_resource_change" in codes(result)


def test_dynamodb_pitr_enabled_with_valid_recovery_period_passes_recovery_policy():
    document, proposal_value = dynamodb_case(
        [{"enabled": True, "recovery_period_in_days": 35}], backup_required=True
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert not {"dynamodb_pitr_required", "dynamodb_pitr_disabled", "dynamodb_pitr_recovery_period_invalid"} & codes(result)


def test_dynamodb_pitr_disabled_is_reviewed_when_backups_are_not_required():
    document, proposal_value = dynamodb_case(
        [{"enabled": False, "recovery_period_in_days": 35}]
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.REVIEW_REQUIRED
    assert "dynamodb_pitr_disabled" in codes(result)


@pytest.mark.parametrize(
    "pitr",
    [None, [{"enabled": False, "recovery_period_in_days": 35}]],
)
def test_dynamodb_backup_requirement_denies_missing_or_disabled_pitr(pitr):
    document, proposal_value = dynamodb_case(pitr, backup_required=True)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "dynamodb_pitr_required" in codes(result)


@pytest.mark.parametrize("unknown_path", ["enabled", "recovery_period_in_days"])
def test_unknown_dynamodb_pitr_values_are_denied(unknown_path):
    document, proposal_value = dynamodb_case(
        [{"enabled": True, "recovery_period_in_days": 30}],
        after_unknown={"point_in_time_recovery": {unknown_path: True}},
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


@pytest.mark.parametrize("recovery_period", [None, 0, 36, True, "30"])
def test_dynamodb_pitr_enabled_requires_bounded_integer_recovery_period(recovery_period):
    document, proposal_value = dynamodb_case(
        [{"enabled": True, "recovery_period_in_days": recovery_period}],
        backup_required=True,
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "dynamodb_pitr_recovery_period_invalid" in codes(result)


def test_dynamodb_pitr_policy_findings_do_not_include_plan_values():
    document, proposal_value = dynamodb_case(
        [{"enabled": False, "recovery_period_in_days": 35}]
    )
    document["planned_values"]["root_module"]["resources"][-1]["values"][
        "sensitive_customer_value"
    ] = "private-data-marker"

    result = evaluate(document, proposal_value)

    assert "dynamodb_pitr_disabled" in codes(result)
    assert "private-data-marker" not in repr(result)


def step_functions_lambda_case():
    document = plan()
    root_resources = document["planned_values"]["root_module"]["resources"]
    worker_arn = f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:workflow-worker"
    role_arn = f"arn:aws:iam::{ACCOUNT}:role/workflow"
    role_trust = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "states.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "ArnEquals": {
                            "aws:SourceArn": f"arn:aws:states:{REGION}:{ACCOUNT}:stateMachine:workflow"
                        },
                        "StringEquals": {"aws:SourceAccount": ACCOUNT},
                    },
                }
            ],
        }
    )
    role_policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "lambda:InvokeFunction",
                    "Resource": worker_arn,
                }
            ],
        }
    )
    state_machine_arn = f"arn:aws:states:{REGION}:{ACCOUNT}:stateMachine:workflow"
    definition = json.dumps(
        {
            "StartAt": "Invoke",
            "States": {"Invoke": {"Type": "Task", "Resource": worker_arn, "End": True}},
        }
    )
    additions = [
        resource(
            "aws_iam_role.workflow",
            "aws_iam_role",
            {
                "name": "workflow",
                "arn": role_arn,
                "assume_role_policy": role_trust,
            },
        ),
        resource(
            "aws_iam_role_policy.workflow",
            "aws_iam_role_policy",
            {
                "name": "workflow-invoke",
                "role": "workflow",
                "policy": role_policy,
            },
        ),
        resource(
            "aws_lambda_function.workflow",
            "aws_lambda_function",
            {
                "function_name": "workflow-worker",
                "arn": worker_arn,
                "timeout": 10,
            },
        ),
        resource(
            "aws_sfn_state_machine.workflow",
            "aws_sfn_state_machine",
            {
                "name": "workflow",
                "arn": state_machine_arn,
                "role_arn": role_arn,
                "type": "STANDARD",
                "definition": definition,
            },
        ),
    ]
    for item in additions:
        root_resources.append(item)
        document["resource_changes"].append(change(item["address"], item["type"]))
    document["configuration"]["root_module"] = {
        "resources": [
            {
                "address": "aws_iam_role_policy.workflow",
                "expressions": {"role": {"references": ["aws_iam_role.workflow.name"]}},
            },
            {
                "address": "aws_sfn_state_machine.workflow",
                "expressions": {
                    "role_arn": {"references": ["aws_iam_role.workflow.arn"]},
                    "definition": {"references": ["aws_lambda_function.workflow.arn"]},
                },
            },
        ]
    }
    proposal_resources = [item.model_dump(mode="json") for item in proposal().resources]
    proposal_resources.extend(
        [
            {
                "resource_id": "workflow-role",
                "resource_type": "aws_iam_role",
                "name": "workflow",
                "arguments": {"name": "workflow"},
                "rationale": "Give the workflow a dedicated execution role.",
            },
            {
                "resource_id": "workflow-policy",
                "resource_type": "aws_iam_role_policy",
                "name": "workflow",
                "arguments": {"role": "workflow"},
                "rationale": "Limit workflow access to its planned Lambda task.",
            },
            {
                "resource_id": "workflow-worker",
                "resource_type": "aws_lambda_function",
                "name": "workflow",
                "arguments": {"function_name": "workflow-worker"},
                "rationale": "Run the workflow's bounded task.",
            },
            {
                "resource_id": "workflow-machine",
                "resource_type": "aws_sfn_state_machine",
                "name": "workflow",
                "arguments": {"name": "workflow", "type": "STANDARD"},
                "rationale": "Coordinate the planned Lambda task.",
            },
        ]
    )
    return document, proposal(proposal_resources)


def test_step_functions_requires_exact_same_plan_lambda_role_permissions():
    document, proposal_value = step_functions_lambda_case()

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert not any(item.code.startswith("step_functions_") for item in result.findings)


@pytest.mark.parametrize(
    "action,resource_arn",
    [
        ("lambda:*", f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:workflow-worker"),
        ("lambda:InvokeFunction", "*"),
        ("s3:GetObject", "arn:aws:s3:::unrelated/*"),
    ],
)
def test_step_functions_denies_broad_or_unrelated_role_permissions(action, resource_arn):
    document, proposal_value = step_functions_lambda_case()
    policy = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "aws_iam_role_policy"
    )
    policy_doc = json.loads(policy["values"]["policy"])
    policy_doc["Statement"][0]["Action"] = action
    policy_doc["Statement"][0]["Resource"] = resource_arn
    policy["values"]["policy"] = json.dumps(policy_doc)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "step_functions_role_scope_invalid" in codes(result)


def test_step_functions_denies_unplanned_lambda():
    document, proposal_value = step_functions_lambda_case()
    machine = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "aws_sfn_state_machine"
    )
    asl = json.loads(machine["values"]["definition"])
    asl["States"]["Invoke"]["Resource"] = f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:outside"
    machine["values"]["definition"] = json.dumps(asl)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "step_functions_task_unplanned" in codes(result)


def test_step_functions_requires_confused_deputy_trust_conditions():
    document, proposal_value = step_functions_lambda_case()
    role = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "aws_iam_role"
    )
    trust = json.loads(role["values"]["assume_role_policy"])
    trust["Statement"][0]["Condition"]["ArnEquals"]["aws:SourceArn"] = (
        f"arn:aws:states:{REGION}:{ACCOUNT}:stateMachine:*"
    )
    role["values"]["assume_role_policy"] = json.dumps(trust)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "step_functions_role_trust_invalid" in codes(result)


def test_step_functions_rejects_express_and_service_integrations():
    document, proposal_value = step_functions_lambda_case()
    machine = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "aws_sfn_state_machine"
    )
    machine["values"]["type"] = "EXPRESS"

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "step_functions_type_unsupported" in codes(result)


def test_step_functions_rejects_task_credentials_role_overrides():
    document, proposal_value = step_functions_lambda_case()
    machine = next(
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "aws_sfn_state_machine"
    )
    definition = json.loads(machine["values"]["definition"])
    definition["States"]["Invoke"]["Credentials"] = {
        "RoleArn": f"arn:aws:iam::{ACCOUNT}:role/other"
    }
    machine["values"]["definition"] = json.dumps(definition)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "step_functions_definition_unsupported" in codes(result)


def test_step_functions_denies_unverified_managed_policy_attachment():
    document, proposal_value = step_functions_lambda_case()
    attachment = resource(
        "aws_iam_role_policy_attachment.workflow_admin",
        "aws_iam_role_policy_attachment",
        {
            "role": "workflow",
            "policy_arn": "arn:aws:iam::aws:policy/ReadOnlyAccess",
        },
    )
    document["planned_values"]["root_module"]["resources"].append(attachment)
    document["resource_changes"].append(change(attachment["address"], attachment["type"]))
    proposal_resources = [item.model_dump(mode="json") for item in proposal_value.resources]
    proposal_resources.append(
        {
            "resource_id": "workflow-managed-policy",
            "resource_type": "aws_iam_role_policy_attachment",
            "name": "workflow_admin",
            "arguments": {"role": "workflow", "policy_arn": "ReadOnlyAccess"},
            "rationale": "Regression case for an unverified workflow managed policy.",
        }
    )

    result = evaluate(document, proposal(proposal_resources))

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "step_functions_managed_policy_unverified" in codes(result)
