from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

import pytest
from davdeploy.ecs_express_service_roles import (
    EXPRESS_INFRASTRUCTURE_POLICY_ARN,
    TASK_EXECUTION_POLICY_ARN,
    EcsExpressServiceRoleProfileError,
    verify_ecs_express_service_roles,
)

ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = "654654474502"
CONNECTION_ID = "connection-123"


class FakeIam:
    def __init__(self):
        self.roles = {
            f"davdeployEcsExpressTask-{CONNECTION_ID}": self._role(
                f"davdeployEcsExpressTask-{CONNECTION_ID}",
                "ecs-tasks.amazonaws.com",
                "ecs-express-task-execution",
            ),
            f"davdeployEcsExpressInfra-{CONNECTION_ID}": self._role(
                f"davdeployEcsExpressInfra-{CONNECTION_ID}",
                "ecs.amazonaws.com",
                "ecs-express-infrastructure",
            ),
        }
        self.policies = {
            f"davdeployEcsExpressTask-{CONNECTION_ID}": [TASK_EXECUTION_POLICY_ARN],
            f"davdeployEcsExpressInfra-{CONNECTION_ID}": [
                EXPRESS_INFRASTRUCTURE_POLICY_ARN
            ],
        }
        self.inline = {name: [] for name in self.roles}

    @staticmethod
    def _role(name: str, service: str, purpose: str) -> dict:
        return {
            "RoleName": name,
            "Arn": f"arn:aws:iam::{ACCOUNT}:role/{name}",
            "Path": "/",
            "PermissionsBoundary": None,
            "AssumeRolePolicyDocument": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": service},
                        "Action": "sts:AssumeRole",
                    }
                ],
            },
            "Tags": [
                {"Key": "ManagedBy", "Value": "davdeploy"},
                {"Key": "ConnectionId", "Value": CONNECTION_ID},
                {"Key": "Purpose", "Value": purpose},
            ],
        }

    def get_role(self, *, RoleName):
        if RoleName not in self.roles:
            raise RuntimeError("NoSuchEntity")
        return {"Role": self.roles[RoleName]}

    def list_attached_role_policies(self, *, RoleName, **_kwargs):
        return {
            "AttachedPolicies": [
                {"PolicyArn": arn} for arn in self.policies[RoleName]
            ],
            "IsTruncated": False,
        }

    def list_role_policies(self, *, RoleName, **_kwargs):
        return {"PolicyNames": self.inline[RoleName], "IsTruncated": False}


def test_ecs_express_service_role_profile_accepts_exact_connection_roles():
    profile = verify_ecs_express_service_roles(
        FakeIam(), account_id=ACCOUNT, connection_id=CONNECTION_ID
    )

    assert profile.task_execution_role_arn == (
        f"arn:aws:iam::{ACCOUNT}:role/davdeployEcsExpressTask-{CONNECTION_ID}"
    )
    assert profile.infrastructure_role_arn == (
        f"arn:aws:iam::{ACCOUNT}:role/davdeployEcsExpressInfra-{CONNECTION_ID}"
    )
    assert len(profile.sha256) == 64


@pytest.mark.parametrize(
    "mutate",
    [
        lambda iam: iam.roles[
            f"davdeployEcsExpressTask-{CONNECTION_ID}"
        ]["AssumeRolePolicyDocument"]["Statement"][0]["Principal"].update(
            Service="lambda.amazonaws.com"
        ),
        lambda iam: iam.policies[
            f"davdeployEcsExpressInfra-{CONNECTION_ID}"
        ].append("arn:aws:iam::aws:policy/AdministratorAccess"),
        lambda iam: iam.inline[
            f"davdeployEcsExpressTask-{CONNECTION_ID}"
        ].append("extra-permissions"),
        lambda iam: iam.roles[f"davdeployEcsExpressInfra-{CONNECTION_ID}"]["Tags"][1].update(
            Value="another-connection"
        ),
        lambda iam: iam.roles[f"davdeployEcsExpressTask-{CONNECTION_ID}"].pop("Tags"),
    ],
)
def test_ecs_express_service_role_profile_rejects_drift(mutate):
    iam = FakeIam()
    iam.roles = deepcopy(iam.roles)
    iam.policies = deepcopy(iam.policies)
    iam.inline = deepcopy(iam.inline)
    mutate(iam)

    with pytest.raises(EcsExpressServiceRoleProfileError):
        verify_ecs_express_service_roles(
            iam, account_id=ACCOUNT, connection_id=CONNECTION_ID
        )


def test_ecs_express_service_role_profile_rejects_invalid_scope_and_missing_roles():
    with pytest.raises(EcsExpressServiceRoleProfileError, match="connection ID"):
        verify_ecs_express_service_roles(
            FakeIam(), account_id=ACCOUNT, connection_id="../other"
        )

    iam = FakeIam()
    del iam.roles[f"davdeployEcsExpressTask-{CONNECTION_ID}"]
    with pytest.raises(EcsExpressServiceRoleProfileError, match="unavailable"):
        verify_ecs_express_service_roles(
            iam, account_id=ACCOUNT, connection_id=CONNECTION_ID
        )


def test_cloudformation_template_contains_only_the_connection_scoped_role_contract():
    template = (
        ROOT / "infrastructure/cloudformation/customer-ecs-express-roles.yaml"
    ).read_text()

    assert 'AllowedPattern: "^[a-z0-9-]{8,30}$"' in template
    assert 'RoleName: !Sub "davdeployEcsExpressTask-${ConnectionId}"' in template
    assert 'RoleName: !Sub "davdeployEcsExpressInfra-${ConnectionId}"' in template
    assert "Service: ecs-tasks.amazonaws.com" in template
    assert "Service: ecs.amazonaws.com" in template
    assert TASK_EXECUTION_POLICY_ARN in template
    assert EXPRESS_INFRASTRUCTURE_POLICY_ARN in template
    assert "AdministratorAccess" not in template
    assert "AWS::IAM::Policy" not in template


def test_ecs_express_terraform_root_looks_up_roles_without_owning_them():
    root = (
        ROOT
        / "infrastructure/terraform/customer-workload-ecs-express-pilot/main.tf"
    ).read_text()
    outputs = (
        ROOT
        / "infrastructure/terraform/customer-workload-ecs-express-pilot/outputs.tf"
    ).read_text()

    assert 'data "aws_iam_role" "execution"' in root
    assert 'data "aws_iam_role" "infrastructure"' in root
    assert 'resource "aws_iam_role"' not in root
    assert 'resource "aws_iam_role_policy_attachment"' not in root
    assert root.count("destroy = false") == 4
    assert re.search(
        r'name\s*=\s*"davdeployEcsExpressTask-\$\{var\.connection_id\}"', root
    )
    assert re.search(
        r'name\s*=\s*"davdeployEcsExpressInfra-\$\{var\.connection_id\}"', root
    )
    assert root.count("depends_on = [terraform_data.account_guard]") == 2
    assert "data.aws_iam_role.execution.arn" in root
    assert "data.aws_iam_role.infrastructure.arn" in root
    assert "data.aws_iam_role.execution.arn" in outputs
    assert "data.aws_iam_role.infrastructure.arn" in outputs


def test_template_host_publishes_service_roles_at_a_protected_content_hash_key():
    host = (ROOT / "infrastructure/terraform/connection-template-host/main.tf").read_text()
    outputs = (ROOT / "infrastructure/terraform/connection-template-host/outputs.tf").read_text()

    assert "customer-ecs-express-roles.yaml" in host
    assert "filesha256(local.ecs_express_roles_template_source)" in host
    assert (
        'cloudformation/customer-ecs-express-roles-${local.ecs_express_roles_template_hash}.yaml'
        in host
    )
    assert "(local.ecs_express_roles_template_key)" in host
    assert "prevent_destroy = true" in host
    assert "ignore_changes  = all" in host
    assert "customer_ecs_express_roles_template_url" in outputs
    assert "published_customer_templates[local.ecs_express_roles_template_key].key" in outputs


def test_runner_verifies_and_records_roles_but_retains_them_for_other_projects():
    runner = (ROOT / "scripts/customer-workload-ecs-express-pilot.sh").read_text()

    assert "scripts/verify_ecs_express_service_roles.py" in runner
    assert "service_role_profile:$role_profile[0]" in runner
    assert 'connection_service_roles:"retained_and_verified"' in runner
    assert 'Customer ECS Express service roles do not match the reviewed connection profile' in runner
    assert 'Legacy project-scoped ECS role remains; cleanup is not confirmed' in runner
