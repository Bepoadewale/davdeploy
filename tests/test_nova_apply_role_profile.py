from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

import pytest
from davdeploy.nova_apply_access import (
    APPLY_ROLE_ACCESS_TAG,
    APPLY_ROLE_POLICY_NAME,
    build_nova_apply_access_policy,
    build_nova_apply_role_policy,
)
from davdeploy.nova_apply_role_profile import (
    NovaApplyRoleProfileError,
    verify_nova_apply_role_profile,
)

ACCOUNT = "123456789012"
CONNECTION = "connection-123"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT}:role/davdeployNovaApply-{CONNECTION}"
BROKER_ARN = f"arn:aws:iam::{ACCOUNT}:role/davdeploy-api"
EXTERNAL_ID = "customer-external-id"


def plan_scope():
    return build_nova_apply_access_policy(
        {
            "resource_changes": [
                {
                    "mode": "managed",
                    "type": "aws_dynamodb_table",
                    "address": "aws_dynamodb_table.example",
                    "change": {
                        "actions": ["create"],
                        "before": None,
                        "after": {"name": "pilot-table"},
                    },
                }
            ]
        },
        account_id=ACCOUNT,
        region="us-east-1",
    ).document


class FakeIam:
    def __init__(self):
        self.role = {
            "Arn": ROLE_ARN,
            "RoleName": f"davdeployNovaApply-{CONNECTION}",
            "Path": "/",
            "MaxSessionDuration": 3600,
            "PermissionsBoundary": None,
            "Tags": [
                {"Key": "ManagedBy", "Value": "davdeploy"},
                {"Key": "ConnectionId", "Value": CONNECTION},
                {"Key": "Access", "Value": APPLY_ROLE_ACCESS_TAG},
            ],
            "AssumeRolePolicyDocument": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": BROKER_ARN},
                        "Action": "sts:AssumeRole",
                        "Condition": {"StringEquals": {"sts:ExternalId": EXTERNAL_ID}},
                    }
                ],
            },
        }
        self.policy = build_nova_apply_role_policy(ROLE_ARN)

    def get_role(self, *, RoleName):
        assert RoleName == f"davdeployNovaApply-{CONNECTION}"
        return {"Role": self.role}

    def list_attached_role_policies(self, *, RoleName, **_kwargs):
        assert RoleName == f"davdeployNovaApply-{CONNECTION}"
        return {"AttachedPolicies": [], "IsTruncated": False}

    def list_role_policies(self, *, RoleName, **_kwargs):
        assert RoleName == f"davdeployNovaApply-{CONNECTION}"
        return {"PolicyNames": [APPLY_ROLE_POLICY_NAME], "IsTruncated": False}

    def get_role_policy(self, *, RoleName, PolicyName):
        assert RoleName == f"davdeployNovaApply-{CONNECTION}"
        assert PolicyName == APPLY_ROLE_POLICY_NAME
        return {"PolicyDocument": self.policy}

    def simulate_principal_policy(self, **request):
        assert request["PolicySourceArn"] == ROLE_ARN
        assert request["PermissionsBoundaryPolicyInputList"] == [
            json.dumps(plan_scope(), sort_keys=True, separators=(",", ":"))
        ]
        resource = request["ResourceArns"][0]
        return {
            "EvaluationResults": [
                {
                    "EvalActionName": action,
                    "EvalResourceName": resource,
                    "EvalDecision": "allowed",
                }
                for action in request["ActionNames"]
            ],
            "IsTruncated": False,
        }


def verify(iam):
    return verify_nova_apply_role_profile(
        iam,
        account_id=ACCOUNT,
        connection_id=CONNECTION,
        broker_role_arn=BROKER_ARN,
        external_id=EXTERNAL_ID,
        session_policy=plan_scope(),
    )


def test_apply_role_profile_accepts_exact_trust_tags_and_fixed_permission_ceiling():
    profile = verify(FakeIam())

    assert profile.account_id == ACCOUNT
    assert profile.role_arn == ROLE_ARN
    assert profile.version == "nova-apply-role-profile.v2"
    assert len(profile.sha256) == 64
    assert profile.simulated_action_resource_pairs == 4
    assert EXTERNAL_ID not in profile.sha256


@pytest.mark.parametrize(
    "mutation",
    [
        lambda iam: iam.role.update(PermissionsBoundary={"PermissionsBoundaryArn": "arn:aws:iam::123456789012:policy/boundary"}),
        lambda iam: iam.role["Tags"].append({"Key": "Extra", "Value": "unexpected"}),
        lambda iam: iam.role["AssumeRolePolicyDocument"]["Statement"][0]["Principal"].update(AWS="arn:aws:iam::123456789012:role/other"),
        lambda iam: iam.policy["Statement"].append({"Effect": "Allow", "Action": "s3:*", "Resource": "*"}),
    ],
)
def test_apply_role_profile_rejects_role_drift(mutation):
    iam = FakeIam()
    iam.policy = deepcopy(iam.policy)
    mutation(iam)

    with pytest.raises(NovaApplyRoleProfileError):
        verify(iam)


def test_apply_role_profile_rejects_unexpected_managed_policies():
    iam = FakeIam()
    iam.list_attached_role_policies = lambda **_kwargs: {
        "AttachedPolicies": [{"PolicyName": "AdministratorAccess"}],
        "IsTruncated": False,
    }

    with pytest.raises(NovaApplyRoleProfileError, match="attached managed policies"):
        verify(iam)


def test_customer_role_template_matches_the_broker_policy_ceiling():
    template = (
        Path(__file__).resolve().parents[1]
        / "infrastructure/cloudformation/customer-nova-apply-role.yaml"
    ).read_text()
    not_action = template.split("NotAction:\n", 1)[1].split('Resource: "*"', 1)[0]
    template_actions = set(re.findall(r"^\s+- ([a-z][a-z0-9]*:[A-Za-z]+)$", not_action, re.MULTILINE))
    expected_actions = set(
        next(
            statement["NotAction"]
            for statement in build_nova_apply_role_policy(ROLE_ARN)["Statement"]
            if statement.get("Effect") == "Deny" and "NotAction" in statement
        )
    )

    assert template_actions == expected_actions


def test_apply_role_profile_fails_closed_when_plan_permission_is_denied():
    iam = FakeIam()
    iam.simulate_principal_policy = lambda **request: {
        "EvaluationResults": [
            {
                "EvalActionName": request["ActionNames"][0],
                "EvalResourceName": request["ResourceArns"][0],
                "EvalDecision": "implicitDeny",
            }
        ],
        "IsTruncated": False,
    }

    with pytest.raises(NovaApplyRoleProfileError, match="exact approved plan scope"):
        verify(iam)


def test_apply_role_profile_fails_closed_when_simulation_is_unavailable():
    iam = FakeIam()
    iam.simulate_principal_policy = None

    with pytest.raises(NovaApplyRoleProfileError, match="simulation is unavailable"):
        verify(iam)


def test_apply_role_profile_fails_closed_when_simulation_has_missing_context():
    iam = FakeIam()
    iam.simulate_principal_policy = lambda **request: {
        "EvaluationResults": [
            {
                "EvalActionName": action,
                "EvalResourceName": request["ResourceArns"][0],
                "EvalDecision": "allowed",
                "MissingContextValues": ["aws:ResourceAccount"],
            }
            for action in request["ActionNames"]
        ],
        "IsTruncated": False,
    }

    with pytest.raises(NovaApplyRoleProfileError, match="exact approved plan scope"):
        verify(iam)


def test_apply_role_profile_rejects_wildcard_plan_scope_before_simulation():
    iam = FakeIam()
    unsafe_policy = {
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Action": "dynamodb:*", "Resource": "*"}],
    }

    with pytest.raises(NovaApplyRoleProfileError, match="action scope is invalid"):
        verify_nova_apply_role_profile(
            iam,
            account_id=ACCOUNT,
            connection_id=CONNECTION,
            broker_role_arn=BROKER_ARN,
            external_id=EXTERNAL_ID,
            session_policy=unsafe_policy,
        )
