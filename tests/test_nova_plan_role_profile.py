from __future__ import annotations

from copy import deepcopy

import pytest
from davdeploy.nova_plan_access import PLAN_ROLE_READ_ACTIONS
from davdeploy.nova_plan_role_profile import (
    NovaPlanRoleProfileError,
    build_nova_plan_role_inspection_policy,
    verify_nova_plan_role_profile,
)

ACCOUNT = "123456789012"
CONNECTION = "connection-1234"
ROLE_ARN = f"arn:aws:iam::{ACCOUNT}:role/davdeployPlan-{CONNECTION}"
BROKER_ARN = f"arn:aws:iam::{ACCOUNT}:role/davdeploy-api"
EXTERNAL_ID = "test-external-id"


def valid_role_document() -> dict:
    return {
        "Role": {
            "Arn": ROLE_ARN,
            "RoleName": f"davdeployPlan-{CONNECTION}",
            "Path": "/",
            "MaxSessionDuration": 3600,
            "Tags": [
                {"Key": "ManagedBy", "Value": "davdeploy"},
                {"Key": "ConnectionId", "Value": CONNECTION},
                {"Key": "Access", "Value": "nova-plan-only-read-v1"},
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
        },
        "PolicyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": list(PLAN_ROLE_READ_ACTIONS),
                    "Resource": "*",
                },
                {
                    "Effect": "Deny",
                    "Action": "s3:*",
                    "Resource": "*",
                    "Condition": {"StringNotEquals": {"aws:ResourceAccount": ACCOUNT}},
                },
                {
                    "Effect": "Deny",
                    "NotAction": list(PLAN_ROLE_READ_ACTIONS),
                    "Resource": "*",
                },
            ],
        },
    }


class FakeIam:
    def __init__(self):
        self.document = valid_role_document()
        self.attached: list[dict] = []
        self.inline_names = ["davdeployNovaPlanReadOnlyProfile"]

    def get_role(self, *, RoleName):
        assert RoleName == f"davdeployPlan-{CONNECTION}"
        return {"Role": deepcopy(self.document["Role"])}

    def list_attached_role_policies(self, *, RoleName, **_kwargs):
        assert RoleName == f"davdeployPlan-{CONNECTION}"
        return {"AttachedPolicies": deepcopy(self.attached), "IsTruncated": False}

    def list_role_policies(self, *, RoleName, **_kwargs):
        assert RoleName == f"davdeployPlan-{CONNECTION}"
        return {"PolicyNames": list(self.inline_names), "IsTruncated": False}

    def get_role_policy(self, *, RoleName, PolicyName):
        assert RoleName == f"davdeployPlan-{CONNECTION}"
        assert PolicyName == "davdeployNovaPlanReadOnlyProfile"
        return {"PolicyDocument": deepcopy(self.document["PolicyDocument"])}


def verify(iam: FakeIam):
    return verify_nova_plan_role_profile(
        iam,
        role_arn=ROLE_ARN,
        connection_id=CONNECTION,
        account_id=ACCOUNT,
        broker_role_arn=BROKER_ARN,
        external_id=EXTERNAL_ID,
    )


def test_exact_plan_role_profile_verifies_and_returns_only_a_digest():
    result = verify(FakeIam())

    assert result.account_id == ACCOUNT
    assert result.role_arn == ROLE_ARN
    assert result.version == "nova-plan-role-profile.v1"
    assert len(result.sha256) == 64
    assert EXTERNAL_ID not in result.sha256


def test_inspection_policy_is_limited_to_one_role_and_read_actions():
    policy = build_nova_plan_role_inspection_policy(ROLE_ARN)

    assert policy["Statement"][0] == {
        "Effect": "Allow",
        "Action": [
            "iam:GetRole",
            "iam:GetRolePolicy",
            "iam:ListAttachedRolePolicies",
            "iam:ListRolePolicies",
        ],
        "Resource": ROLE_ARN,
    }
    assert policy["Statement"][1] == {
        "Effect": "Allow",
        "Action": "sts:GetCallerIdentity",
        "Resource": "*",
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_external_id",
        "wrong_broker",
        "permission_boundary",
        "wrong_connection_tag",
        "extra_tag",
        "duplicate_tag",
        "extra_trust_statement",
        "wrong_session_duration",
        "extra_allow",
        "wrong_allow_resource",
        "missing_deny",
        "wrong_account_deny",
        "attached_policy",
        "extra_inline_policy",
        "wrong_role_arn",
    ],
)
def test_changed_role_profile_fails_closed(mutation):
    iam = FakeIam()
    if mutation == "wrong_external_id":
        iam.document["Role"]["AssumeRolePolicyDocument"]["Statement"][0]["Condition"][
            "StringEquals"
        ]["sts:ExternalId"] = "different"
    elif mutation == "wrong_broker":
        iam.document["Role"]["AssumeRolePolicyDocument"]["Statement"][0]["Principal"]["AWS"] = (
            "arn:aws:iam::123456789012:role/unexpected"
        )
    elif mutation == "permission_boundary":
        iam.document["Role"]["PermissionsBoundary"] = "arn:aws:iam::aws:policy/ReadOnlyAccess"
    elif mutation == "wrong_connection_tag":
        iam.document["Role"]["Tags"][1]["Value"] = "other-connection"
    elif mutation == "extra_tag":
        iam.document["Role"]["Tags"].append({"Key": "Extra", "Value": "unexpected"})
    elif mutation == "duplicate_tag":
        iam.document["Role"]["Tags"].append({"Key": "ManagedBy", "Value": "davdeploy"})
    elif mutation == "extra_trust_statement":
        iam.document["Role"]["AssumeRolePolicyDocument"]["Statement"].append(
            {"Effect": "Allow", "Principal": {"AWS": "*"}, "Action": "sts:AssumeRole"}
        )
    elif mutation == "wrong_session_duration":
        iam.document["Role"]["MaxSessionDuration"] = 43200
    elif mutation == "extra_allow":
        iam.document["PolicyDocument"]["Statement"][0]["Action"].append("s3:GetObject")
    elif mutation == "wrong_allow_resource":
        iam.document["PolicyDocument"]["Statement"][0]["Resource"] = "arn:aws:s3:::*"
    elif mutation == "missing_deny":
        iam.document["PolicyDocument"]["Statement"].pop()
    elif mutation == "wrong_account_deny":
        iam.document["PolicyDocument"]["Statement"][1]["Condition"]["StringNotEquals"][
            "aws:ResourceAccount"
        ] = "000000000000"
    elif mutation == "attached_policy":
        iam.attached = [{"PolicyArn": "arn:aws:iam::aws:policy/ReadOnlyAccess"}]
    elif mutation == "extra_inline_policy":
        iam.inline_names.append("unexpected")
    elif mutation == "wrong_role_arn":
        iam.document["Role"]["Arn"] = f"arn:aws:iam::{ACCOUNT}:role/davdeployPlan-other"

    with pytest.raises(NovaPlanRoleProfileError):
        verify(iam)
