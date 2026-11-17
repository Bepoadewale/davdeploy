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
    simulated_action_resource_pairs: int


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


def _simulate_plan_permissions(
    iam: Any, *, role_arn: str, account_id: str, session_policy: dict[str, Any]
) -> list[tuple[str, str]]:
    """Fail closed unless IAM simulates every plan-scoped allow as effective."""
    if not isinstance(session_policy, dict) or session_policy.get("Version") != "2012-10-17":
        raise NovaApplyRoleProfileError("approved apply permission scope is invalid")
    statements = session_policy.get("Statement")
    if not isinstance(statements, list) or not statements:
        raise NovaApplyRoleProfileError("approved apply permission scope is invalid")

    actions_by_resource: dict[str, set[str]] = {}
    for statement in statements:
        if not isinstance(statement, dict):
            raise NovaApplyRoleProfileError("approved apply permission scope is invalid")
        if statement.get("Effect") != "Allow":
            continue
        action_value = statement.get("Action")
        resource_value = statement.get("Resource")
        actions = [action_value] if isinstance(action_value, str) else action_value
        resources = [resource_value] if isinstance(resource_value, str) else resource_value
        if not isinstance(actions, list) or not actions or not all(
            isinstance(action, str) and action and "*" not in action for action in actions
        ):
            raise NovaApplyRoleProfileError("approved apply action scope is invalid")
        if actions == ["sts:GetCallerIdentity"] and resources == ["*"]:
            continue
        if not isinstance(resources, list) or not resources or not all(
            isinstance(resource, str)
            and resource.startswith("arn:")
            and "*" not in resource
            for resource in resources
        ):
            raise NovaApplyRoleProfileError("approved apply resource scope is invalid")
        for resource in resources:
            actions_by_resource.setdefault(resource, set()).update(actions)
    if not actions_by_resource:
        raise NovaApplyRoleProfileError("approved apply permission scope has no resources")

    simulate = getattr(iam, "simulate_principal_policy", None)
    if not callable(simulate):
        raise NovaApplyRoleProfileError("IAM permission simulation is unavailable")
    boundary = json.dumps(session_policy, sort_keys=True, separators=(",", ":"))
    verified: list[tuple[str, str]] = []
    for resource, actions in sorted(actions_by_resource.items()):
        marker: str | None = None
        seen_markers: set[str] = set()
        remaining = set(actions)
        for _ in range(100):
            request: dict[str, Any] = {
                "PolicySourceArn": role_arn,
                "ActionNames": sorted(actions),
                "ResourceArns": [resource],
                "PermissionsBoundaryPolicyInputList": [boundary],
                "MaxItems": 1000,
            }
            if resource.startswith("arn:aws:s3:::"):
                request["ContextEntries"] = [
                    {
                        "ContextKeyName": "aws:ResourceAccount",
                        "ContextKeyValues": [account_id],
                        "ContextKeyType": "string",
                    }
                ]
            if marker:
                request["Marker"] = marker
            try:
                response = simulate(**request)
            except Exception as error:
                raise NovaApplyRoleProfileError("IAM permission simulation failed") from error
            results = response.get("EvaluationResults") if isinstance(response, dict) else None
            if not isinstance(results, list):
                raise NovaApplyRoleProfileError("IAM permission simulation response is invalid")
            for result in results:
                if not isinstance(result, dict):
                    raise NovaApplyRoleProfileError("IAM permission simulation response is invalid")
                action = result.get("EvalActionName")
                if (
                    not isinstance(action, str)
                    or action not in remaining
                    or result.get("EvalResourceName") != resource
                    or result.get("EvalDecision") != "allowed"
                    or result.get("MissingContextValues") not in (None, [])
                ):
                    raise NovaApplyRoleProfileError(
                        "customer apply role does not allow the exact approved plan scope"
                    )
                remaining.remove(action)
                verified.append((resource, action))
            if response.get("IsTruncated") is not True:
                break
            marker = response.get("Marker")
            if not isinstance(marker, str) or not marker or marker in seen_markers:
                raise NovaApplyRoleProfileError("IAM permission simulation pagination is invalid")
            seen_markers.add(marker)
        else:
            raise NovaApplyRoleProfileError("IAM permission simulation exceeded its page limit")
        if remaining:
            raise NovaApplyRoleProfileError("IAM permission simulation omitted plan actions")
    return sorted(verified)


def verify_nova_apply_role_profile(
    iam: Any,
    *,
    account_id: str,
    connection_id: str,
    broker_role_arn: str,
    external_id: str,
    session_policy: dict[str, Any],
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

    simulated_pairs = _simulate_plan_permissions(
        iam,
        role_arn=expected_arn,
        account_id=account_id,
        session_policy=session_policy,
    )

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
                "simulated_action_resource_pairs": simulated_pairs,
                "session_policy_sha256": hashlib.sha256(
                    json.dumps(session_policy, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
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
        simulated_action_resource_pairs=len(simulated_pairs),
    )
