from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

import pytest
from davdeploy.nova_apply_access import (
    APPLY_ROLE_ACCESS_TAG,
    APPLY_ROLE_POLICY_NAME,
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


def verify(iam):
    return verify_nova_apply_role_profile(
        iam,
        account_id=ACCOUNT,
        connection_id=CONNECTION,
        broker_role_arn=BROKER_ARN,
        external_id=EXTERNAL_ID,
    )


def test_apply_role_profile_accepts_exact_trust_tags_and_fixed_permission_ceiling():
    profile = verify(FakeIam())

    assert profile.account_id == ACCOUNT
    assert profile.role_arn == ROLE_ARN
    assert profile.version == "nova-apply-role-profile.v1"
    assert len(profile.sha256) == 64
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
