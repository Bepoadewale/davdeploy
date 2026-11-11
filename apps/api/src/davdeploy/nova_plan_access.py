"""Fixed read-only AWS permission profile for the Nova Terraform planner.

The AWS provider is pinned in ``generated_terraform_plan.py``. This profile is
deliberately smaller than AWS ReadOnlyAccess: it excludes customer object and
secret contents, workload invocation, and every mutation action. Unsupported
resource types fail before the customer role is assumed.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from davdeploy.generated_deployment_contract import GeneratedDeploymentProposal

PLAN_ROLE_ACCESS_POLICY_VERSION = "nova-plan-read-v1.1"

# Role-level action patterns bound the possible reads. The worker session gets
# an exact provider-version action list and exact resource ARNs. The patterns
# also support explicit denies against direct resource-policy grants.
PLAN_ROLE_READ_ACTIONS = (
    "apigateway:GET",
    "dynamodb:Describe*",
    "dynamodb:ListTagsOfResource",
    "iam:Get*",
    "iam:List*",
    "lambda:Get*",
    "lambda:List*",
    "s3:GetAccelerateConfiguration",
    "s3:GetBucket*",
    "s3:Get*Configuration",
    "s3:ListBucket",
    "sqs:Get*",
    "sqs:ListQueueTags",
    "sts:GetCallerIdentity",
)
PLAN_SCOPED_READ_ACTIONS: dict[str, tuple[str, ...]] = {
    "s3": (
        "s3:GetAccelerateConfiguration",
        "s3:GetBucketAcl",
        "s3:GetBucketCORS",
        "s3:GetBucketLocation",
        "s3:GetBucketLogging",
        "s3:GetBucketNotification",
        "s3:GetBucketObjectLockConfiguration",
        "s3:GetBucketOwnershipControls",
        "s3:GetBucketPolicy",
        "s3:GetBucketPublicAccessBlock",
        "s3:GetBucketRequestPayment",
        "s3:GetBucketTagging",
        "s3:GetBucketVersioning",
        "s3:GetBucketWebsite",
        "s3:GetEncryptionConfiguration",
        "s3:GetLifecycleConfiguration",
        "s3:GetReplicationConfiguration",
        "s3:ListBucket",
    ),
    "dynamodb": (
        "dynamodb:DescribeContinuousBackups",
        "dynamodb:DescribeTable",
        "dynamodb:DescribeTimeToLive",
        "dynamodb:ListTagsOfResource",
    ),
    "sqs": ("sqs:GetQueueAttributes", "sqs:ListQueueTags"),
    "lambda": (
        "lambda:GetEventSourceMapping",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration",
        "lambda:GetPolicy",
        "lambda:ListTags",
        "lambda:ListVersionsByFunction",
    ),
    "iam-role": (
        "iam:GetRole",
        "iam:GetRolePolicy",
        "iam:ListAttachedRolePolicies",
        "iam:ListRolePolicies",
        "iam:ListRoleTags",
    ),
    "iam-policy": ("iam:GetPolicy", "iam:GetPolicyVersion", "iam:ListPolicyVersions"),
}

SUPPORTED_PLAN_RESOURCE_TYPES = frozenset(
    {
        "aws_apigatewayv2_api",
        "aws_apigatewayv2_authorizer",
        "aws_apigatewayv2_deployment",
        "aws_apigatewayv2_integration",
        "aws_apigatewayv2_integration_response",
        "aws_apigatewayv2_route",
        "aws_apigatewayv2_route_response",
        "aws_apigatewayv2_stage",
        "aws_dynamodb_table",
        "aws_iam_policy",
        "aws_iam_role",
        "aws_iam_role_policy",
        "aws_iam_role_policy_attachment",
        "aws_lambda_event_source_mapping",
        "aws_lambda_function",
        "aws_lambda_permission",
        "aws_s3_bucket",
        "aws_s3_bucket_acl",
        "aws_s3_bucket_cors_configuration",
        "aws_s3_bucket_lifecycle_configuration",
        "aws_s3_bucket_ownership_controls",
        "aws_s3_bucket_policy",
        "aws_s3_bucket_public_access_block",
        "aws_s3_bucket_server_side_encryption_configuration",
        "aws_s3_bucket_versioning",
        "aws_sqs_queue",
        "aws_sqs_queue_policy",
    }
)


class NovaPlanAccessError(ValueError):
    """A proposal cannot run under the fixed customer plan permission profile."""


@dataclass(frozen=True)
class NovaPlanAccessPolicy:
    version: str
    document: dict[str, object]
    sha256: str


def _aws_partition(region: str) -> str:
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
    return "aws"


def build_nova_plan_access_policy(
    proposal: GeneratedDeploymentProposal,
    *,
    account_id: str,
    region: str,
) -> NovaPlanAccessPolicy:
    """Build the only proposal-scoped session policy accepted by the worker."""
    if not isinstance(account_id, str) or len(account_id) != 12 or not account_id.isdigit():
        raise NovaPlanAccessError("trusted target account is invalid")
    if not isinstance(region, str) or not re.fullmatch(
        r"[a-z]{2}(?:-[a-z0-9]+)+-\d", region
    ):
        raise NovaPlanAccessError("trusted target region is invalid")
    if proposal.requirements.region != region:
        raise NovaPlanAccessError("proposal region does not match trusted region")
    unsupported = sorted(
        {
            item.resource_type
            for item in proposal.resources
            if item.resource_type not in SUPPORTED_PLAN_RESOURCE_TYPES
        }
    )
    if unsupported:
        raise NovaPlanAccessError("proposal contains unsupported plan resource types")

    by_id = {resource.resource_id: resource for resource in proposal.resources}
    partition = _aws_partition(region)

    def known_name(
        resource,
        field: str,
        *,
        allowed_reference_targets: dict[str, frozenset[str]],
        target_field: str | None = None,
    ) -> str:
        def exact(value: object) -> str | None:
            if isinstance(value, str) and re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_.+=,@-]{0,255}", value
            ):
                return value
            return None

        value = resource.arguments.get(field)
        known = exact(value)
        if known is not None:
            return known
        if isinstance(value, dict) and value.get("kind") == "resource_reference":
            target = by_id.get(value.get("resource_id"))
            allowed_outputs = (
                allowed_reference_targets.get(target.resource_type, frozenset())
                if target
                else frozenset()
            )
            target_value = (
                exact(target.arguments.get(target_field or field)) if target is not None else None
            )
            if (
                target is not None
                and value.get("output_name") in allowed_outputs
                and target_value is not None
            ):
                return target_value
        raise NovaPlanAccessError("resource name cannot be safely scoped")

    resources_by_service: dict[str, set[str]] = {
        "s3": set(),
        "dynamodb": set(),
        "sqs": set(),
        "lambda": set(),
        "iam-role": set(),
        "iam-policy": set(),
    }
    resources_by_service["lambda-event-source-mapping"] = set()
    for resource in proposal.resources:
        kind = resource.resource_type
        if kind.startswith("aws_s3_bucket"):
            bucket = known_name(
                resource,
                "bucket",
                allowed_reference_targets={"aws_s3_bucket": frozenset({"bucket", "id"})},
            )
            resources_by_service["s3"].add(f"arn:{partition}:s3:::{bucket}")
        elif kind == "aws_dynamodb_table" or kind.startswith("aws_dynamodb_table_"):
            table = known_name(
                resource,
                "name",
                allowed_reference_targets={"aws_dynamodb_table": frozenset({"name", "id"})},
            )
            resources_by_service["dynamodb"].add(
                f"arn:{partition}:dynamodb:{region}:{account_id}:table/{table}"
            )
        elif kind == "aws_sqs_queue" or kind == "aws_sqs_queue_policy":
            queue = known_name(
                resource,
                "name" if kind == "aws_sqs_queue" else "queue_url",
                allowed_reference_targets={"aws_sqs_queue": frozenset({"name", "id", "url"})},
                target_field="name",
            )
            queue_resource = (
                resource
                if kind == "aws_sqs_queue"
                else by_id.get(resource.arguments.get("queue_url", {}).get("resource_id"))
                if isinstance(resource.arguments.get("queue_url"), dict)
                else None
            )
            if (
                queue_resource is not None
                and queue_resource.arguments.get("fifo_queue") is True
                and not queue.endswith(".fifo")
            ):
                queue += ".fifo"
            resources_by_service["sqs"].add(f"arn:{partition}:sqs:{region}:{account_id}:{queue}")
        elif kind.startswith("aws_lambda_"):
            function = known_name(
                resource,
                "function_name",
                allowed_reference_targets={
                    "aws_lambda_function": frozenset({"function_name", "arn"})
                },
            )
            resources_by_service["lambda"].add(
                f"arn:{partition}:lambda:{region}:{account_id}:function:{function}"
            )
            if kind == "aws_lambda_event_source_mapping":
                resources_by_service["lambda-event-source-mapping"].add(
                    f"arn:{partition}:lambda:{region}:{account_id}:event-source-mapping:*"
                )
        elif kind == "aws_iam_role":
            role = known_name(
                resource,
                "name",
                allowed_reference_targets={"aws_iam_role": frozenset({"name", "id"})},
            )
            path = resource.arguments.get("path", "/")
            if (
                not isinstance(path, str)
                or not path.startswith("/")
                or (path != "/" and not path.endswith("/"))
                or any(marker in path for marker in ("*", "?", "%{", "${"))
            ):
                raise NovaPlanAccessError("IAM role path cannot be safely scoped")
            resources_by_service["iam-role"].add(
                f"arn:{partition}:iam::{account_id}:role/{path.lstrip('/')}{role}"
            )
        elif kind in {"aws_iam_role_policy", "aws_iam_role_policy_attachment"}:
            if not isinstance(resource.arguments.get("role"), dict):
                raise NovaPlanAccessError("IAM role references must target a declared role")
            role = known_name(
                resource,
                "role",
                allowed_reference_targets={"aws_iam_role": frozenset({"name", "id"})},
                target_field="name",
            )
            role_value = resource.arguments.get("role")
            target = (
                by_id.get(role_value.get("resource_id")) if isinstance(role_value, dict) else None
            )
            path = target.arguments.get("path", "/") if target is not None else "/"
            if (
                not isinstance(path, str)
                or not path.startswith("/")
                or (path != "/" and not path.endswith("/"))
                or any(marker in path for marker in ("*", "?", "%{", "${"))
            ):
                raise NovaPlanAccessError("IAM role path cannot be safely scoped")
            resources_by_service["iam-role"].add(
                f"arn:{partition}:iam::{account_id}:role/{path.lstrip('/')}{role.lstrip('/')}"
            )
            if kind == "aws_iam_role_policy_attachment":
                policy_value = resource.arguments.get("policy_arn")
                policy_arn = None
                if (
                    isinstance(policy_value, dict)
                    and policy_value.get("kind") == "resource_reference"
                ):
                    policy_target = by_id.get(policy_value.get("resource_id"))
                    if (
                        policy_target is not None
                        and policy_target.resource_type == "aws_iam_policy"
                    ):
                        policy_name = known_name(
                            policy_target,
                            "name",
                            allowed_reference_targets={},
                        )
                        policy_path = policy_target.arguments.get("path", "/")
                        if (
                            isinstance(policy_path, str)
                            and policy_path.startswith("/")
                            and (policy_path == "/" or policy_path.endswith("/"))
                            and not any(marker in policy_path for marker in ("*", "?", "%{", "${"))
                        ):
                            policy_arn = (
                                f"arn:{partition}:iam::{account_id}:policy/"
                                f"{policy_path.lstrip('/')}{policy_name}"
                            )
                elif isinstance(policy_value, str) and re.fullmatch(
                    rf"arn:{re.escape(partition)}:iam::(?:{account_id}|aws):policy/[A-Za-z0-9/_.+=,@-]+",
                    policy_value,
                ):
                    policy_arn = policy_value
                if policy_arn is None:
                    raise NovaPlanAccessError("IAM attached policy cannot be safely scoped")
                resources_by_service["iam-policy"].add(policy_arn)
        elif kind == "aws_iam_policy":
            name = known_name(resource, "name", allowed_reference_targets={})
            path = resource.arguments.get("path", "/")
            if (
                not isinstance(path, str)
                or not path.startswith("/")
                or (path != "/" and not path.endswith("/"))
                or any(marker in path for marker in ("*", "?", "%{", "${"))
            ):
                raise NovaPlanAccessError("IAM policy path cannot be safely scoped")
            resources_by_service["iam-policy"].add(
                f"arn:{partition}:iam::{account_id}:policy/{path.lstrip('/')}{name}"
            )
    statements: list[dict[str, object]] = []
    scoped_resources = sorted(
        {resource for values in resources_by_service.values() for resource in values}
        | (
            {f"arn:{partition}:apigateway:{region}::/apis/*"}
            if any(
                resource.resource_type.startswith("aws_apigatewayv2_")
                for resource in proposal.resources
            )
            else set()
        )
    )
    if not scoped_resources:
        raise NovaPlanAccessError("proposal has no supported customer plan resources")
    statements.append(
        {
            "Effect": "Allow",
            # Exact resource ARNs constrain the fixed role-level read patterns;
            # the explicit deny below also blocks direct grants outside them.
            "Action": sorted(PLAN_ROLE_READ_ACTIONS),
            "Resource": scoped_resources,
        }
    )
    # This explicit deny keeps the session read-only even if a customer edits
    # the role's identity policy or adds a resource-based grant.
    statements.append(
        {
            "Effect": "Deny",
            "NotAction": sorted(set(PLAN_ROLE_READ_ACTIONS) | {"sts:GetCallerIdentity"}),
            "Resource": "*",
        }
    )
    # The action deny above prevents writes and out-of-profile APIs. This
    # resource deny also blocks direct resource-policy grants to the assumed
    # role session from escaping the proposal's resource scope.
    statements.append(
        {
            "Effect": "Deny",
            "NotAction": ["sts:GetCallerIdentity"],
            "NotResource": scoped_resources,
        }
    )
    if resources_by_service["s3"]:
        statements.append(
            {
                "Effect": "Deny",
                "Action": "s3:*",
                "Resource": "*",
                "Condition": {
                    "StringNotEquals": {"aws:ResourceAccount": account_id}
                },
            }
        )
    document: dict[str, object] = {
        "Version": "2012-10-17",
        "Statement": statements,
    }
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) > 2048:
        raise NovaPlanAccessError("fixed plan role session policy exceeds the AWS limit")
    return NovaPlanAccessPolicy(
        version=PLAN_ROLE_ACCESS_POLICY_VERSION,
        document=document,
        sha256=hashlib.sha256(encoded).hexdigest(),
    )
