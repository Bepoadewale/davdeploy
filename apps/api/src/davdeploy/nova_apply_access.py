"""Build a bounded STS session policy from an exact Terraform plan."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

NOVA_APPLY_ACCESS_POLICY_VERSION = "nova-apply-plan-scope.v1"
NOVA_APPLY_ROLE_PROFILE_VERSION = "nova-apply-role-profile.v2"
APPLY_ROLE_POLICY_NAME = "davdeployNovaApplyBoundedExecution"
APPLY_ROLE_ACCESS_TAG = "nova-apply-bounded-v1"
MAX_SESSION_POLICY_BYTES = 2048
APPLY_ROLE_INSPECTION_ACTIONS = (
    "iam:GetRole",
    "iam:GetRolePolicy",
    "iam:ListAttachedRolePolicies",
    "iam:ListRolePolicies",
    "iam:SimulatePrincipalPolicy",
)

_SQS_QUEUE_READ_ACTIONS = frozenset(
    {
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl",
        "sqs:ListQueueTags",
    }
)
_DYNAMODB_TABLE_READ_ACTIONS = frozenset(
    {
        "dynamodb:DescribeTable",
        "dynamodb:ListTagsOfResource",
    }
)
_S3_BUCKET_READ_ACTIONS = frozenset(
    {
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
    }
)

def _profile(
    service: str,
    field: str,
    read: set[str] | frozenset[str],
    create: set[str] | frozenset[str],
    update: set[str] | frozenset[str],
    delete: set[str] | frozenset[str],
) -> tuple[str, str, frozenset[str], frozenset[str], frozenset[str], frozenset[str]]:
    return service, field, frozenset(read), frozenset(create), frozenset(update), frozenset(delete)


_RESOURCE_PROFILES: dict[
    str, tuple[str, str, frozenset[str], frozenset[str], frozenset[str], frozenset[str]]
] = {
    "aws_s3_bucket": _profile(
        "s3", "bucket", _S3_BUCKET_READ_ACTIONS,
        {"s3:CreateBucket", "s3:PutBucketTagging"}, {"s3:PutBucketTagging"},
        {"s3:DeleteBucket"},
    ),
    "aws_s3_bucket_acl": _profile(
        "s3", "bucket", {"s3:GetBucketAcl"}, {"s3:PutBucketAcl"},
        {"s3:PutBucketAcl"}, {"s3:PutBucketAcl"},
    ),
    "aws_s3_bucket_cors_configuration": _profile(
        "s3", "bucket", {"s3:GetBucketCORS"}, {"s3:PutBucketCORS"},
        {"s3:PutBucketCORS"}, {"s3:PutBucketCORS"},
    ),
    "aws_s3_bucket_lifecycle_configuration": _profile(
        "s3", "bucket", {"s3:GetLifecycleConfiguration"},
        {"s3:PutLifecycleConfiguration"}, {"s3:PutLifecycleConfiguration"},
        {"s3:PutLifecycleConfiguration"},
    ),
    "aws_s3_bucket_ownership_controls": _profile(
        "s3", "bucket", {"s3:GetBucketOwnershipControls"},
        {"s3:PutBucketOwnershipControls"}, {"s3:PutBucketOwnershipControls"},
        {"s3:PutBucketOwnershipControls"},
    ),
    "aws_s3_bucket_policy": _profile(
        "s3", "bucket", {"s3:GetBucketPolicy"}, {"s3:PutBucketPolicy"},
        {"s3:PutBucketPolicy"}, {"s3:DeleteBucketPolicy"},
    ),
    "aws_s3_bucket_public_access_block": _profile(
        "s3", "bucket", {"s3:GetBucketPublicAccessBlock"},
        {"s3:PutBucketPublicAccessBlock"}, {"s3:PutBucketPublicAccessBlock"},
        {"s3:PutBucketPublicAccessBlock"},
    ),
    "aws_s3_bucket_server_side_encryption_configuration": _profile(
        "s3", "bucket", {"s3:GetEncryptionConfiguration"},
        {"s3:PutEncryptionConfiguration"}, {"s3:PutEncryptionConfiguration"},
        {"s3:PutEncryptionConfiguration"},
    ),
    "aws_s3_bucket_versioning": _profile(
        "s3", "bucket", {"s3:GetBucketVersioning"},
        {"s3:PutBucketVersioning"}, {"s3:PutBucketVersioning"},
        {"s3:PutBucketVersioning"},
    ),
    "aws_sqs_queue": _profile(
        "sqs", "name", _SQS_QUEUE_READ_ACTIONS,
        {"sqs:CreateQueue", "sqs:TagQueue"},
        {"sqs:SetQueueAttributes", "sqs:TagQueue", "sqs:UntagQueue"},
        {"sqs:DeleteQueue"},
    ),
    "aws_dynamodb_table": _profile(
        "dynamodb", "name", _DYNAMODB_TABLE_READ_ACTIONS,
        {"dynamodb:CreateTable", "dynamodb:TagResource"},
        {"dynamodb:UpdateTable", "dynamodb:TagResource", "dynamodb:UntagResource"},
        {"dynamodb:DeleteTable"},
    ),
}
_MUTATING_ACTIONS = frozenset({"create", "update", "delete"})
_UNSCOPED_S3_BUCKET_CONFIGURATION = frozenset(
    {
        "acl",
        "acceleration_status",
        "cors_rule",
        "grant",
        "lifecycle_rule",
        "logging",
        "object_lock_configuration",
        "policy",
        "replication_configuration",
        "request_payer",
        "server_side_encryption_configuration",
        "versioning",
        "website",
    }
)
_VALID_PLAN_ACTIONS = frozenset(
    {"no-op", "read", "create", "update", "delete"}
)
_ROLE_ACTIONS_BY_SERVICE: dict[str, set[str]] = {}
for _profile_value in _RESOURCE_PROFILES.values():
    _service, _, _read, _create, _update, _delete = _profile_value
    _ROLE_ACTIONS_BY_SERVICE.setdefault(_service, set()).update(
        _read | _create | _update | _delete
    )
_ROLE_ALLOWED_ACTIONS = frozenset(
    action
    for service_actions in _ROLE_ACTIONS_BY_SERVICE.values()
    for action in service_actions
) | frozenset(APPLY_ROLE_INSPECTION_ACTIONS) | {"sts:GetCallerIdentity"}


class NovaApplyAccessPolicyError(ValueError):
    """A saved Terraform plan cannot be scoped to the supported IAM profile."""


@dataclass(frozen=True)
class NovaApplyAccessPolicy:
    version: str
    document: dict[str, Any]
    sha256: str


def build_nova_apply_role_policy(role_arn: str) -> dict[str, Any]:
    """Build the fixed role ceiling; each apply session adds its plan scope."""
    if not isinstance(role_arn, str) or re.fullmatch(
        r"arn:aws:iam::\d{12}:role/davdeployNovaApply-[A-Za-z0-9-]{8,40}", role_arn
    ) is None:
        raise NovaApplyAccessPolicyError("dedicated Nova apply role ARN is invalid")
    statements: list[dict[str, Any]] = [
        {
            "Effect": "Allow",
            "Action": sorted(actions),
            "Resource": "*",
        }
        for _, actions in sorted(_ROLE_ACTIONS_BY_SERVICE.items())
    ]
    statements.extend(
        [
            {
                "Effect": "Allow",
                "Action": list(APPLY_ROLE_INSPECTION_ACTIONS),
                "Resource": role_arn,
            },
            {"Effect": "Allow", "Action": "sts:GetCallerIdentity", "Resource": "*"},
            {
                "Effect": "Deny",
                "NotAction": sorted(_ROLE_ALLOWED_ACTIONS),
                "Resource": "*",
            },
        ]
    )
    return {"Version": "2012-10-17", "Statement": statements}


def build_nova_apply_role_inspection_policy(role_arn: str) -> dict[str, Any]:
    """Limit role-profile inspection credentials to one customer role."""
    if not isinstance(role_arn, str) or re.fullmatch(
        r"arn:aws:iam::\d{12}:role/davdeployNovaApply-[A-Za-z0-9-]{8,40}", role_arn
    ) is None:
        raise NovaApplyAccessPolicyError("dedicated Nova apply role ARN is invalid")
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": list(APPLY_ROLE_INSPECTION_ACTIONS),
                "Resource": role_arn,
            },
            {"Effect": "Allow", "Action": "sts:GetCallerIdentity", "Resource": "*"},
        ],
    }


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


def _exact_name(value: Any) -> str | None:
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.+=,@-]{0,254}", value
    ):
        return None
    return value


def _has_configured_value(value: Any) -> bool:
    if value is None or value is False or value == "" or value == [] or value == {}:
        return False
    if isinstance(value, list):
        return any(_has_configured_value(item) for item in value)
    if isinstance(value, dict):
        return any(_has_configured_value(item) for item in value.values())
    return True


def _validate_s3_bucket_configuration(change: dict[str, Any], actions: list[str]) -> None:
    before = change.get("before")
    after = change.get("after")
    before = before if isinstance(before, dict) else {}
    after = after if isinstance(after, dict) else {}
    if "delete" in actions and before.get("force_destroy") is True:
        raise NovaApplyAccessPolicyError(
            "saved plan requires unsupported forced S3 bucket deletion"
        )
    if "create" in actions:
        configured = {
            field
            for field in _UNSCOPED_S3_BUCKET_CONFIGURATION
            if _has_configured_value(after.get(field))
        }
    elif "update" in actions:
        configured = {
            field
            for field in _UNSCOPED_S3_BUCKET_CONFIGURATION
            if before.get(field) != after.get(field)
            and (
                _has_configured_value(before.get(field))
                or _has_configured_value(after.get(field))
            )
        }
    else:
        configured = set()
    if configured:
        raise NovaApplyAccessPolicyError(
            "saved plan changes unsupported embedded S3 bucket settings"
        )


def _resource_arn(
    resource_type: str,
    values: dict[str, Any],
    *,
    account_id: str,
    region: str,
) -> tuple[str, str, str]:
    profile = _RESOURCE_PROFILES.get(resource_type)
    if profile is None:
        raise NovaApplyAccessPolicyError("saved plan contains an unsupported apply resource type")
    service, name_field = profile[:2]
    if service == "s3":
        bucket = _exact_name(values.get(name_field))
        if bucket is None:
            raise NovaApplyAccessPolicyError("saved plan has an unscopable S3 bucket name")
        return service, f"arn:{_aws_partition(region)}:s3:::{bucket}", name_field
    name = _exact_name(values.get(name_field))
    if name is None:
        raise NovaApplyAccessPolicyError("saved plan has an unscopable resource name")
    partition = _aws_partition(region)
    if service == "sqs":
        arn = f"arn:{partition}:sqs:{region}:{account_id}:{name}"
    else:
        arn = f"arn:{partition}:dynamodb:{region}:{account_id}:table/{name}"
    return service, arn, name_field


def build_nova_apply_access_policy(
    plan_document: dict[str, Any], *, account_id: str, region: str
) -> NovaApplyAccessPolicy:
    """Scope temporary credentials to exact changed resources in a saved plan.

    The policy deliberately rejects unknown resource/action mappings and plans
    that exceed AWS STS's inline session-policy size limit.
    """
    if not isinstance(account_id, str) or not re.fullmatch(r"\d{12}", account_id):
        raise NovaApplyAccessPolicyError("trusted target account is invalid")
    if not isinstance(region, str) or not re.fullmatch(
        r"[a-z]{2}(?:-[a-z0-9]+)+-\d", region
    ):
        raise NovaApplyAccessPolicyError("trusted target region is invalid")
    changes = plan_document.get("resource_changes")
    if not isinstance(changes, list):
        raise NovaApplyAccessPolicyError("saved plan resource changes are unavailable")

    scoped: dict[str, set[str]] = {}
    mutating_count = 0
    for item in changes:
        if not isinstance(item, dict):
            raise NovaApplyAccessPolicyError("saved plan resource change is malformed")
        if item.get("mode", "managed") == "data":
            continue
        if item.get("mode", "managed") != "managed":
            raise NovaApplyAccessPolicyError("saved plan resource mode is unsupported")
        resource_type = item.get("type")
        change = item.get("change")
        actions = change.get("actions") if isinstance(change, dict) else None
        if not isinstance(resource_type, str) or not isinstance(actions, list):
            raise NovaApplyAccessPolicyError("saved plan resource action is malformed")
        if any(action not in _VALID_PLAN_ACTIONS for action in actions):
            raise NovaApplyAccessPolicyError("saved plan contains an unknown Terraform action")
        if not _MUTATING_ACTIONS.intersection(actions):
            continue
        if (
            len(actions) > 2
            or len(set(actions)) != len(actions)
            or set(actions) - _MUTATING_ACTIONS
            or (len(actions) == 2 and set(actions) != {"create", "delete"})
        ):
            raise NovaApplyAccessPolicyError("saved plan has an unsupported replacement action")
        if resource_type not in _RESOURCE_PROFILES:
            raise NovaApplyAccessPolicyError("saved plan contains an unsupported apply resource type")
        if resource_type == "aws_s3_bucket":
            _validate_s3_bucket_configuration(change, actions)
        profile = _RESOURCE_PROFILES[resource_type]
        if len(actions) == 2:
            value_actions = {"before": {"delete"}, "after": {"create"}}
        else:
            value_field = "before" if "delete" in actions else "after"
            value_actions = {value_field: set(actions)}
        mapped_actions = {"create": profile[3], "update": profile[4], "delete": profile[5]}
        for value_field, terraform_actions in value_actions.items():
            values = change.get(value_field)
            if not isinstance(values, dict):
                raise NovaApplyAccessPolicyError("saved plan resource identity is unavailable")
            _, arn, _ = _resource_arn(
                resource_type, values, account_id=account_id, region=region
            )
            actions_for_arn = scoped.setdefault(arn, set())
            actions_for_arn.update(profile[2])
            for terraform_action in terraform_actions:
                actions_for_arn.update(mapped_actions[terraform_action])
        mutating_count += 1
    if mutating_count == 0 or not scoped:
        raise NovaApplyAccessPolicyError("saved plan has no supported resource changes to apply")

    statements: list[dict[str, Any]] = []
    all_actions: set[str] = {"sts:GetCallerIdentity"}
    all_resources: set[str] = set()
    for arn in sorted(scoped):
        actions = scoped[arn]
        all_actions.update(actions)
        all_resources.add(arn)
        statements.append(
            {"Effect": "Allow", "Action": sorted(actions), "Resource": arn}
        )
    statements.append(
        {"Effect": "Allow", "Action": "sts:GetCallerIdentity", "Resource": "*"}
    )
    statements.append(
        {"Effect": "Deny", "NotAction": sorted(all_actions), "Resource": "*"}
    )
    statements.append(
        {
            "Effect": "Deny",
            "NotAction": "sts:GetCallerIdentity",
            "NotResource": sorted(all_resources),
        }
    )
    if any(arn.startswith(f"arn:{_aws_partition(region)}:s3:::") for arn in scoped):
        statements.append(
            {
                "Effect": "Deny",
                "Action": "s3:*",
                "Resource": "*",
                "Condition": {"StringNotEquals": {"aws:ResourceAccount": account_id}},
            }
        )
    document = {"Version": "2012-10-17", "Statement": statements}
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) > MAX_SESSION_POLICY_BYTES:
        raise NovaApplyAccessPolicyError(
            f"apply session policy exceeds the AWS STS limit ({len(encoded)} bytes)"
        )
    return NovaApplyAccessPolicy(
        version=NOVA_APPLY_ACCESS_POLICY_VERSION,
        document=document,
        sha256=hashlib.sha256(encoded).hexdigest(),
    )
