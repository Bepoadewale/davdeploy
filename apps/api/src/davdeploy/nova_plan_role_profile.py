"""Strict, read-only verification for the customer Nova plan-role profile."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote

from davdeploy.nova_plan_access import PLAN_ROLE_READ_ACTIONS

NOVA_PLAN_ROLE_PROFILE_VERSION = "nova-plan-role-profile.v1"
PLAN_ROLE_POLICY_NAME = "davdeployNovaPlanReadOnlyProfile"
PLAN_ROLE_ACCESS_TAG = "nova-plan-only-read-v1"

INSPECTION_ACTIONS = (
    "iam:GetRole",
    "iam:GetRolePolicy",
    "iam:ListAttachedRolePolicies",
    "iam:ListRolePolicies",
)


class NovaPlanRoleProfileError(ValueError):
    """The assumed customer role does not match the reviewed plan-only profile."""


@dataclass(frozen=True)
class NovaPlanRoleProfile:
    account_id: str
    role_arn: str
    version: str
    sha256: str


def build_nova_plan_role_inspection_policy(role_arn: str) -> dict[str, Any]:
    """Limit profile inspection to IAM metadata for one role and caller identity."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": list(INSPECTION_ACTIONS),
                "Resource": role_arn,
            },
            {
                "Effect": "Allow",
                "Action": "sts:GetCallerIdentity",
                "Resource": "*",
            },
        ],
    }


def _document(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        decoded = unquote(value)
        try:
            parsed = json.loads(decoded)
        except json.JSONDecodeError as error:
            raise NovaPlanRoleProfileError("role policy document is not valid JSON") from error
        if isinstance(parsed, dict):
            return parsed
    raise NovaPlanRoleProfileError("role policy document is not an object")


def _items(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise NovaPlanRoleProfileError("role policy action shape is invalid")


def _canonical(value: Any) -> Any:
    """Canonicalize IAM documents whose JSON array ordering is immaterial."""
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        canonical = [_canonical(item) for item in value]
        return sorted(canonical, key=lambda item: json.dumps(item, sort_keys=True))
    return value


def _statements(document: dict[str, Any]) -> list[dict[str, Any]]:
    raw = document.get("Statement")
    if isinstance(raw, dict):
        result = [raw]
    elif isinstance(raw, list) and all(isinstance(item, dict) for item in raw):
        result = raw
    else:
        raise NovaPlanRoleProfileError("role policy statements are invalid")
    if document.get("Version") != "2012-10-17" or set(document) != {"Version", "Statement"}:
        raise NovaPlanRoleProfileError("role policy document has unexpected fields")
    return result


def _validate_inline_policy(document: dict[str, Any], account_id: str) -> dict[str, Any]:
    statements = _statements(document)
    if len(statements) != 3:
        raise NovaPlanRoleProfileError("role policy has unexpected statements")
    expected_actions = set(PLAN_ROLE_READ_ACTIONS)
    found_allow = found_account_deny = found_other_deny = False
    for statement in statements:
        effect = statement.get("Effect")
        resource = statement.get("Resource")
        if effect == "Allow":
            if (
                found_allow
                or set(statement) != {"Effect", "Action", "Resource"}
                or resource != "*"
                or len(_items(statement.get("Action"))) != len(expected_actions)
                or set(_items(statement.get("Action"))) != expected_actions
            ):
                raise NovaPlanRoleProfileError(
                    "role allow policy differs from the reviewed profile"
                )
            found_allow = True
        elif effect == "Deny" and "Action" in statement:
            if (
                found_account_deny
                or set(statement) != {"Effect", "Action", "Resource", "Condition"}
                or statement.get("Action") != "s3:*"
                or resource != "*"
                or statement.get("Condition")
                != {"StringNotEquals": {"aws:ResourceAccount": account_id}}
            ):
                raise NovaPlanRoleProfileError("role account-boundary deny differs from profile")
            found_account_deny = True
        elif effect == "Deny" and "NotAction" in statement:
            if (
                found_other_deny
                or set(statement) != {"Effect", "NotAction", "Resource"}
                or resource != "*"
                or len(_items(statement.get("NotAction"))) != len(expected_actions)
                or set(_items(statement.get("NotAction"))) != expected_actions
            ):
                raise NovaPlanRoleProfileError("role explicit-deny boundary differs from profile")
            found_other_deny = True
        else:
            raise NovaPlanRoleProfileError("role policy contains an unsupported statement")
    if not (found_allow and found_account_deny and found_other_deny):
        raise NovaPlanRoleProfileError("role policy is missing a required profile statement")
    return _canonical(document)


def _all_role_policy_names(iam: Any, operation: str, role_name: str) -> list[str]:
    names: list[str] = []
    marker: str | None = None
    while True:
        method = getattr(iam, operation)
        kwargs: dict[str, Any] = {"RoleName": role_name}
        if marker:
            kwargs["Marker"] = marker
        response = method(**kwargs)
        if not isinstance(response, dict):
            raise NovaPlanRoleProfileError("role policy listing response is invalid")
        collection = (
            "AttachedPolicies" if operation == "list_attached_role_policies" else "PolicyNames"
        )
        values = response.get(collection, [])
        if operation == "list_attached_role_policies":
            if not isinstance(values, list) or any(
                not isinstance(item, dict) or not isinstance(item.get("PolicyArn"), str)
                for item in values
            ):
                raise NovaPlanRoleProfileError("attached policy list is invalid")
            names.extend(item["PolicyArn"] for item in values)
        else:
            if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
                raise NovaPlanRoleProfileError("inline policy list is invalid")
            names.extend(values)
        if not response.get("IsTruncated"):
            return names
        marker = response.get("Marker")
        if not isinstance(marker, str) or not marker:
            raise NovaPlanRoleProfileError("truncated policy list has no continuation marker")


def verify_nova_plan_role_profile(
    iam: Any,
    *,
    role_arn: str,
    connection_id: str,
    account_id: str,
    broker_role_arn: str,
    external_id: str,
) -> NovaPlanRoleProfile:
    """Verify the exact customer template profile without claiming all effective policy layers."""
    expected_role_name = f"davdeployPlan-{connection_id}"
    expected_role_arn = f"arn:aws:iam::{account_id}:role/{expected_role_name}"
    if role_arn != expected_role_arn:
        raise NovaPlanRoleProfileError("plan role ARN does not match the connection")

    response = iam.get_role(RoleName=expected_role_name)
    role = response.get("Role") if isinstance(response, dict) else None
    if not isinstance(role, dict):
        raise NovaPlanRoleProfileError("plan role metadata is unavailable")
    if (
        role.get("Arn") != expected_role_arn
        or role.get("RoleName") != expected_role_name
        or role.get("Path") != "/"
        or role.get("MaxSessionDuration") != 3600
        or role.get("PermissionsBoundary") is not None
    ):
        raise NovaPlanRoleProfileError("plan role identity or boundary differs from profile")
    tags = role.get("Tags", [])
    if not isinstance(tags, list) or any(
        not isinstance(item, dict)
        or not isinstance(item.get("Key"), str)
        or not isinstance(item.get("Value"), str)
        for item in tags
    ):
        raise NovaPlanRoleProfileError("plan role ownership tags are invalid")
    tag_map = {item["Key"]: item["Value"] for item in tags}
    expected_tags = {
        "ManagedBy": "davdeploy",
        "ConnectionId": connection_id,
        "Access": PLAN_ROLE_ACCESS_TAG,
    }
    if len(tags) != len(expected_tags) or tag_map != expected_tags:
        raise NovaPlanRoleProfileError("plan role ownership tags differ from profile")

    trust = _document(role.get("AssumeRolePolicyDocument"))
    trust_statements = _statements(trust)
    expected_trust = {
        "Effect": "Allow",
        "Principal": {"AWS": broker_role_arn},
        "Action": "sts:AssumeRole",
        "Condition": {"StringEquals": {"sts:ExternalId": external_id}},
    }
    if len(trust_statements) != 1 or trust_statements[0] != expected_trust:
        raise NovaPlanRoleProfileError("plan role trust differs from the reviewed profile")
    redacted_trust = {
        "Version": trust["Version"],
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": broker_role_arn},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"sts:ExternalId": "<connection-external-id>"}
                },
            }
        ],
    }

    if _all_role_policy_names(iam, "list_attached_role_policies", expected_role_name):
        raise NovaPlanRoleProfileError("plan role has an unexpected attached policy")
    policy_names = _all_role_policy_names(iam, "list_role_policies", expected_role_name)
    if policy_names != [PLAN_ROLE_POLICY_NAME]:
        raise NovaPlanRoleProfileError("plan role inline policy set differs from profile")
    policy_response = iam.get_role_policy(
        RoleName=expected_role_name, PolicyName=PLAN_ROLE_POLICY_NAME
    )
    policy_document = _document(
        policy_response.get("PolicyDocument") if isinstance(policy_response, dict) else None
    )
    canonical_policy = _validate_inline_policy(policy_document, account_id)
    profile_sha256 = hashlib.sha256(
        json.dumps(
            {
                "version": NOVA_PLAN_ROLE_PROFILE_VERSION,
                "role_arn": expected_role_arn,
                "tags": expected_tags,
                "max_session_duration": 3600,
                "permissions_boundary": None,
                "managed_policy_arns": [],
                "trust": _canonical(redacted_trust),
                "inline_policy_name": PLAN_ROLE_POLICY_NAME,
                "inline_policy": canonical_policy,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return NovaPlanRoleProfile(
        account_id=account_id,
        role_arn=expected_role_arn,
        version=NOVA_PLAN_ROLE_PROFILE_VERSION,
        sha256=profile_sha256,
    )
