"""Strict, read-only verification for the customer Nova apply-role profile."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote

from davdeploy.nova_apply_access import (
    APPLY_ROLE_ACCESS_TAG,
    APPLY_ROLE_POLICY_NAME,
    NOVA_APPLY_ROLE_PROFILE_VERSION,
    NovaApplyAccessPolicyError,
    build_nova_apply_role_policy,
)


class NovaApplyRoleProfileError(ValueError):
    """The assumed customer role does not match the reviewed apply profile."""


@dataclass(frozen=True)
class NovaApplyRoleProfile:
    account_id: str
    role_arn: str
    version: str
    sha256: str


def _document(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(unquote(value))
        except json.JSONDecodeError as error:
            raise NovaApplyRoleProfileError("role policy document is not valid JSON") from error
        if isinstance(parsed, dict):
            return parsed
    raise NovaApplyRoleProfileError("role policy document is not an object")


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        values = [_canonical(item) for item in value]
        return sorted(values, key=lambda item: json.dumps(item, sort_keys=True))
    return value


def _policy_names(iam: Any, operation: str, role_name: str) -> list[str]:
    method = getattr(iam, operation, None)
    if not callable(method):
        raise NovaApplyRoleProfileError("role policy listing is unavailable")
    marker = None
    names: list[str] = []
    for _ in range(100):
        kwargs = {"RoleName": role_name}
        if marker:
            kwargs["Marker"] = marker
        response = method(**kwargs)
        if not isinstance(response, dict):
            raise NovaApplyRoleProfileError("role policy listing response is invalid")
        key = "PolicyNames" if operation == "list_role_policies" else "AttachedPolicies"
        items = response.get(key)
        if not isinstance(items, list):
            raise NovaApplyRoleProfileError("role policy listing response is invalid")
        for item in items:
            name = item if isinstance(item, str) else item.get("PolicyName") if isinstance(item, dict) else None
            if not isinstance(name, str) or not name:
                raise NovaApplyRoleProfileError("role policy listing item is invalid")
            names.append(name)
        if response.get("IsTruncated") is not True:
            return sorted(names)
        marker = response.get("Marker")
        if not isinstance(marker, str) or not marker:
            raise NovaApplyRoleProfileError("role policy pagination is invalid")
    raise NovaApplyRoleProfileError("role policy listing exceeded its page limit")


def verify_nova_apply_role_profile(
    iam: Any,
    *,
    account_id: str,
    connection_id: str,
    broker_role_arn: str,
    external_id: str,
) -> NovaApplyRoleProfile:
    """Verify the exact trust, ownership tags, and fixed maximum role policy."""
    if (
        not isinstance(account_id, str)
        or re.fullmatch(r"\d{12}", account_id) is None
        or not isinstance(connection_id, str)
        or re.fullmatch(r"[A-Za-z0-9-]{8,40}", connection_id) is None
        or not isinstance(broker_role_arn, str)
        or re.fullmatch(r"arn:aws:iam::\d{12}:role/.+", broker_role_arn) is None
        or not isinstance(external_id, str)
        or not external_id
    ):
        raise NovaApplyRoleProfileError("trusted apply role verification input is invalid")
    expected_arn = f"arn:aws:iam::{account_id}:role/davdeployNovaApply-{connection_id}"
    expected_name = f"davdeployNovaApply-{connection_id}"
    try:
        role_response = iam.get_role(RoleName=expected_name)
    except Exception as error:
        raise NovaApplyRoleProfileError("dedicated customer apply role is unavailable") from error
    role = role_response.get("Role") if isinstance(role_response, dict) else None
    if not isinstance(role, dict):
        raise NovaApplyRoleProfileError("dedicated customer apply role response is invalid")
    if (
        role.get("Arn") != expected_arn
        or role.get("RoleName") != expected_name
        or role.get("Path") != "/"
        or role.get("MaxSessionDuration") != 3600
        or role.get("PermissionsBoundary") is not None
    ):
        raise NovaApplyRoleProfileError("dedicated customer apply role identity differs from profile")
    tags = role.get("Tags")
    if not isinstance(tags, list):
        raise NovaApplyRoleProfileError("dedicated customer apply role tags are invalid")
    tag_map = {
        item.get("Key"): item.get("Value")
        for item in tags
        if isinstance(item, dict)
    }
    expected_tags = {
        "ManagedBy": "davdeploy",
        "ConnectionId": connection_id,
        "Access": APPLY_ROLE_ACCESS_TAG,
    }
    if len(tags) != len(expected_tags) or tag_map != expected_tags:
        raise NovaApplyRoleProfileError("dedicated customer apply role ownership tags differ")

    trust = _document(role.get("AssumeRolePolicyDocument"))
    trust_statements = trust.get("Statement")
    if isinstance(trust_statements, dict):
        trust_statements = [trust_statements]
    expected_trust = {
        "Effect": "Allow",
        "Principal": {"AWS": broker_role_arn},
        "Action": "sts:AssumeRole",
        "Condition": {"StringEquals": {"sts:ExternalId": external_id}},
    }
    if (
        trust.get("Version") != "2012-10-17"
        or set(trust) != {"Version", "Statement"}
        or trust_statements != [expected_trust]
    ):
        raise NovaApplyRoleProfileError("dedicated customer apply role trust differs from profile")

    if _policy_names(iam, "list_attached_role_policies", expected_name):
        raise NovaApplyRoleProfileError("dedicated customer apply role has attached managed policies")
    if _policy_names(iam, "list_role_policies", expected_name) != [APPLY_ROLE_POLICY_NAME]:
        raise NovaApplyRoleProfileError("dedicated customer apply role inline policy set differs")
    policy_response = iam.get_role_policy(
        RoleName=expected_name, PolicyName=APPLY_ROLE_POLICY_NAME
    )
    policy_document = _document(
        policy_response.get("PolicyDocument") if isinstance(policy_response, dict) else None
    )
    try:
        expected_policy = build_nova_apply_role_policy(expected_arn)
    except NovaApplyAccessPolicyError as error:
        raise NovaApplyRoleProfileError("dedicated apply policy profile is invalid") from error
    if _canonical(policy_document) != _canonical(expected_policy):
        raise NovaApplyRoleProfileError("dedicated customer apply role policy differs from profile")

    redacted_trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": broker_role_arn},
                "Action": "sts:AssumeRole",
                "Condition": {"StringEquals": {"sts:ExternalId": "<connection-external-id>"}},
            }
        ],
    }
    profile_digest = hashlib.sha256(
        json.dumps(
            {
                "version": NOVA_APPLY_ROLE_PROFILE_VERSION,
                "role_arn": expected_arn,
                "tags": expected_tags,
                "max_session_duration": 3600,
                "permissions_boundary": None,
                "managed_policy_arns": [],
                "trust": _canonical(redacted_trust),
                "inline_policy_name": APPLY_ROLE_POLICY_NAME,
                "inline_policy": _canonical(policy_document),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return NovaApplyRoleProfile(
        account_id=account_id,
        role_arn=expected_arn,
        version=NOVA_APPLY_ROLE_PROFILE_VERSION,
        sha256=profile_digest,
    )
