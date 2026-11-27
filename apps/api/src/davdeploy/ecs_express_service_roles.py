"""Fail-closed verification for the customer-side ECS Express role pair."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote

TASK_EXECUTION_POLICY_ARN = (
    "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
)
EXPRESS_INFRASTRUCTURE_POLICY_ARN = (
    "arn:aws:iam::aws:policy/service-role/"
    "AmazonECSInfrastructureRoleforExpressGatewayServices"
)
CONNECTION_ID_PATTERN = re.compile(r"^[a-z0-9-]{8,30}$")


class EcsExpressServiceRoleProfileError(ValueError):
    """A connection's ECS Express service roles do not match the contract."""


@dataclass(frozen=True)
class EcsExpressServiceRoleProfile:
    account_id: str
    connection_id: str
    task_execution_role_arn: str
    infrastructure_role_arn: str
    sha256: str


def _policy_document(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(unquote(value))
        except json.JSONDecodeError as error:
            raise EcsExpressServiceRoleProfileError(
                "ECS Express service-role trust policy is invalid"
            ) from error
        if isinstance(parsed, dict):
            return parsed
    raise EcsExpressServiceRoleProfileError(
        "ECS Express service-role trust policy is invalid"
    )


def _list_role_policy_arns(iam: Any, role_name: str) -> list[str]:
    marker: str | None = None
    arns: list[str] = []
    for _ in range(20):
        request: dict[str, Any] = {"RoleName": role_name}
        if marker:
            request["Marker"] = marker
        response = iam.list_attached_role_policies(**request)
        items = response.get("AttachedPolicies") if isinstance(response, dict) else None
        if not isinstance(items, list):
            raise EcsExpressServiceRoleProfileError(
                "ECS Express service-role policy listing is invalid"
            )
        for item in items:
            arn = item.get("PolicyArn") if isinstance(item, dict) else None
            if not isinstance(arn, str) or not arn:
                raise EcsExpressServiceRoleProfileError(
                    "ECS Express service-role policy listing is invalid"
                )
            arns.append(arn)
        if response.get("IsTruncated") is not True:
            return sorted(arns)
        marker = response.get("Marker")
        if not isinstance(marker, str) or not marker:
            raise EcsExpressServiceRoleProfileError(
                "ECS Express service-role policy pagination is invalid"
            )
    raise EcsExpressServiceRoleProfileError(
        "ECS Express service-role policy listing exceeded its page limit"
    )


def _verify_role(
    iam: Any,
    *,
    account_id: str,
    connection_id: str,
    role_name: str,
    service_principal: str,
    policy_arn: str,
) -> str:
    try:
        response = iam.get_role(RoleName=role_name)
    except Exception as error:
        raise EcsExpressServiceRoleProfileError(
            f"required ECS Express service role is unavailable: {role_name}"
        ) from error
    role = response.get("Role") if isinstance(response, dict) else None
    if not isinstance(role, dict):
        raise EcsExpressServiceRoleProfileError(
            f"required ECS Express service role is unavailable: {role_name}"
        )

    expected_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
    if role.get("RoleName") != role_name or role.get("Arn") != expected_arn:
        raise EcsExpressServiceRoleProfileError(
            f"ECS Express service role has an unexpected identity: {role_name}"
        )
    if role.get("Path", "/") != "/" or role.get("PermissionsBoundary") is not None:
        raise EcsExpressServiceRoleProfileError(
            f"ECS Express service role has an unexpected path or boundary: {role_name}"
        )

    trust = _policy_document(role.get("AssumeRolePolicyDocument"))
    expected_trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": service_principal},
                "Action": "sts:AssumeRole",
            }
        ],
    }
    if trust != expected_trust:
        raise EcsExpressServiceRoleProfileError(
            f"ECS Express service role trust is not exact: {role_name}"
        )

    role_tags = role.get("Tags")
    if not isinstance(role_tags, list):
        raise EcsExpressServiceRoleProfileError(
            f"ECS Express service role tags are unavailable: {role_name}"
        )
    tags = {
        item.get("Key"): item.get("Value")
        for item in role_tags
        if isinstance(item, dict)
    }
    if tags.get("ManagedBy") != "davdeploy" or tags.get("ConnectionId") != connection_id:
        raise EcsExpressServiceRoleProfileError(
            f"ECS Express service role connection tags do not match: {role_name}"
        )

    if _list_role_policy_arns(iam, role_name) != [policy_arn]:
        raise EcsExpressServiceRoleProfileError(
            f"ECS Express service role managed policies do not match: {role_name}"
        )

    try:
        inline = iam.list_role_policies(RoleName=role_name)
    except Exception as error:
        raise EcsExpressServiceRoleProfileError(
            f"ECS Express service role inline policies could not be verified: {role_name}"
        ) from error
    if not isinstance(inline, dict) or inline.get("PolicyNames") != []:
        raise EcsExpressServiceRoleProfileError(
            f"ECS Express service role has inline policies: {role_name}"
        )
    return expected_arn


def verify_ecs_express_service_roles(
    iam: Any, *, account_id: str, connection_id: str
) -> EcsExpressServiceRoleProfile:
    """Verify exact role names, service trust, tags, and managed policies."""
    if not re.fullmatch(r"[0-9]{12}", account_id):
        raise EcsExpressServiceRoleProfileError("expected AWS account ID is invalid")
    if not CONNECTION_ID_PATTERN.fullmatch(connection_id):
        raise EcsExpressServiceRoleProfileError("DavDeploy connection ID is invalid")

    task_name = f"davdeployEcsExpressTask-{connection_id}"
    infrastructure_name = f"davdeployEcsExpressInfra-{connection_id}"
    task_arn = _verify_role(
        iam,
        account_id=account_id,
        connection_id=connection_id,
        role_name=task_name,
        service_principal="ecs-tasks.amazonaws.com",
        policy_arn=TASK_EXECUTION_POLICY_ARN,
    )
    infrastructure_arn = _verify_role(
        iam,
        account_id=account_id,
        connection_id=connection_id,
        role_name=infrastructure_name,
        service_principal="ecs.amazonaws.com",
        policy_arn=EXPRESS_INFRASTRUCTURE_POLICY_ARN,
    )
    profile = {
        "schema_version": "ecs-express-service-role-profile.v1",
        "account_id": account_id,
        "connection_id": connection_id,
        "task_execution_role_arn": task_arn,
        "task_execution_policy_arn": TASK_EXECUTION_POLICY_ARN,
        "infrastructure_role_arn": infrastructure_arn,
        "infrastructure_policy_arn": EXPRESS_INFRASTRUCTURE_POLICY_ARN,
    }
    digest = hashlib.sha256(
        json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return EcsExpressServiceRoleProfile(
        account_id=account_id,
        connection_id=connection_id,
        task_execution_role_arn=task_arn,
        infrastructure_role_arn=infrastructure_arn,
        sha256=digest,
    )


def profile_evidence(profile: EcsExpressServiceRoleProfile) -> dict[str, str]:
    """Return non-secret, plan-bindable profile evidence for run records."""
    return {
        "schema_version": "ecs-express-service-role-profile.v1",
        "account_id": profile.account_id,
        "connection_id": profile.connection_id,
        "task_execution_role_arn": profile.task_execution_role_arn,
        "infrastructure_role_arn": profile.infrastructure_role_arn,
        "sha256": profile.sha256,
    }
