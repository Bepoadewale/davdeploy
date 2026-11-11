import re
from pathlib import Path

from davdeploy.nova_plan_access import PLAN_ROLE_READ_ACTIONS

ROOT = Path("infrastructure/terraform/customer-connection")


def test_customer_discovery_is_read_only_and_execution_is_profile_bounded():
    configuration = (ROOT / "main.tf").read_text()
    assert 'resource "aws_iam_role" "discovery"' in configuration
    assert 'resource "aws_iam_role" "execution_contract"' in configuration
    assert 'resource "aws_iam_role_policy" "discovery"' in configuration
    assert 'resources = ["*"]' in configuration
    assert "Create" not in configuration
    assert "Delete" not in configuration
    assert "Put" not in configuration
    assert "Update" not in configuration
    assert "secretsmanager:" not in configuration
    assert "GetSecretValue" not in configuration
    execution_section = configuration.split('resource "aws_iam_role" "execution_contract"', 1)[1]
    assert "aws_iam_role_policy" not in execution_section


def test_customer_connection_apply_and_destroy_require_explicit_confirmation():
    script = Path("scripts/customer-aws-connection.sh").read_text()
    assert "AWS account guard failed" in script
    assert "APPLY_DAVDEPLOY_CUSTOMER_CONNECTION" in script
    assert "DESTROY_DAVDEPLOY_CUSTOMER_CONNECTION" in script
    assert "davdeploy/customer-connections/${CUSTOMER_CONNECTION_ID}.tfstate" in script


def test_quick_create_template_makes_administrator_pilot_explicit_and_separate():
    template = Path("infrastructure/cloudformation/customer-discovery-role.yaml").read_text()
    assert "AWS::IAM::Role" in template
    assert "sts:ExternalId" in template
    assert "secretsmanager:DescribeSecret" in template
    assert "secretsmanager:GetSecretValue" not in template
    assert "s3:GetObject" not in template
    assert "AccessMode" in template
    assert "CreateAdministratorPilotRole" in template
    assert "ExecutionRole" in template
    assert "AdministratorAccess" in template
    assert "AppRunnerEcrAccessRole" in template
    assert "Condition: CreateAdministratorPilotRole" in template
    assert "- !Ref davdeployExecutionBrokerRoleArn" in template
    assert "- !Ref davdeployDiscoveryBrokerRoleArn" in template
    assert "iam:PassRole" not in template
    assert "GetSecretValue" not in template


def test_quick_create_plan_role_is_separate_and_has_bounded_read_only_actions():
    template = Path("infrastructure/cloudformation/customer-discovery-role.yaml").read_text()
    plan_role = template.split("\n  NovaPlanOnlyRole:\n", 1)[1].split("\n  ExecutionRole:\n", 1)[0]
    policy = plan_role.split("Policies:", 1)[1]

    assert "plan-only" in template
    assert any(
        line.startswith("Description: davdeploy AWS connection.")
        and "bounded planning metadata reads" in line
        for line in template.splitlines()
    )
    assert 'RoleName: !Sub "davdeployPlan-${ConnectionId}"' in plan_role
    assert "Condition: CreateNovaPlanOnlyRole" in plan_role
    assert "davdeployDiscoveryBrokerRoleArn" in plan_role
    assert "davdeployNovaPlanBrokerRoleArn" in plan_role
    assert "sts:ExternalId: !Ref ExternalId" in plan_role
    assert "Effect: Deny" in policy
    assert "NotAction:" in policy
    assert "aws:ResourceAccount: !Ref AWS::AccountId" in policy
    assert 'Resource: "*"' in policy
    assert "Effect: Allow" in policy
    assert "lambda:Get*" in policy
    assert "dynamodb:Describe*" in policy
    assert "s3:ListBucket" in policy
    assert "s3:GetObject" not in policy
    assert "dynamodb:GetItem" not in policy
    assert "lambda:InvokeFunction" not in policy
    assert "iam:PassRole" not in policy
    template_actions = set(
        re.findall(r"^\s+- ([a-z0-9*]+:[A-Za-z0-9*]+)$", policy, re.MULTILINE)
    )
    assert template_actions == set(PLAN_ROLE_READ_ACTIONS)
    assert "AdministratorAccess" not in plan_role
    assert "NovaPlanOnlyRoleArn" in template


def test_quick_create_omits_optional_nova_broker_principal_when_runner_is_disabled():
    template = Path("infrastructure/cloudformation/customer-discovery-role.yaml").read_text()
    plan_role = template.split("\n  NovaPlanOnlyRole:\n", 1)[1].split("\n  ExecutionRole:\n", 1)[0]

    assert "Default: unused" in template
    assert "CreateNovaPlanBrokerTrust: !Not [!Equals [!Ref davdeployNovaPlanBrokerRoleArn, unused]]" in template
    assert "AWS: !If" in plan_role
    assert "[!Ref davdeployDiscoveryBrokerRoleArn, !Ref davdeployNovaPlanBrokerRoleArn]" in plan_role
    assert "- !Ref davdeployDiscoveryBrokerRoleArn" in plan_role
    assert "DavDeploy does not attest effective permissions" in template
    assert "It has no customer service permissions" not in template


def test_plan_role_broker_permissions_are_explicit_follow_up_not_added_to_existing_executor():
    configuration = Path("infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    executor = configuration.split('resource "aws_iam_role_policy" "customer_executor"', 1)[
        1
    ].split('resource "aws_codebuild_project" "customer_executor"', 1)[0]

    assert 'Resource = "arn:aws:iam::*:role/davdeployExecution-*"' in executor
    assert "davdeployPlan-*" not in executor


def test_public_template_host_allows_only_versioned_template_reads_and_is_confirmation_gated():
    configuration = Path("infrastructure/terraform/connection-template-host/main.tf").read_text()
    variables = Path("infrastructure/terraform/connection-template-host/variables.tf").read_text()
    script = Path("scripts/customer-aws-template-host.sh").read_text()
    assert 'actions   = ["s3:GetObject"]' in configuration
    assert 'resources = ["${aws_s3_bucket.templates.arn}/cloudformation/*"]' in configuration
    assert "s3:ListBucket" not in configuration
    assert 'resource "aws_s3_object" "published_customer_discovery_role"' in configuration
    assert 'resource "aws_s3_object" "retained_customer_templates"' in configuration
    assert "from = aws_s3_object.active_customer_discovery_role" in configuration
    assert "aws_s3_object.active_customer_discovery_role" not in (
        Path("infrastructure/terraform/connection-template-host/outputs.tf").read_text()
    )
    assert "prevent_destroy = true" in configuration
    assert "retained_template_keys" in variables
    current_live_key = (
        "cloudformation/customer-discovery-role-"
        "7e03683a397f0d4e2a5f68b9559d2790ff127e5513540457b47e9c4779b2b793.yaml"
    )
    assert current_live_key in variables
    assert (
        f'to   = aws_s3_object.retained_customer_templates["{current_live_key}"]'
        in configuration
    )
    assert (
        "from = aws_s3_object.active_customer_discovery_role\n"
        in configuration
    )
    assert 'resource "aws_s3_object" "current_customer_discovery_role"' not in configuration
    assert "customer-discovery-role-0e3209bff02286acf582ec3ed73858266261b294ae0c7e0d30ae37550a8926b2.yaml" not in variables
    outputs = Path("infrastructure/terraform/connection-template-host/outputs.tf").read_text()
    assert "aws_s3_object.published_customer_discovery_role.key" in outputs
    assert "APPLY_DAVDEPLOY_TEMPLATE_HOST" in script
    assert "DESTROY_DAVDEPLOY_TEMPLATE_HOST" in script


def test_control_plane_identity_can_assume_the_quick_create_role_name_pattern():
    configuration = Path("infrastructure/terraform/management-identity/main.tf").read_text()
    assert "role/davdeployDiscovery-*" in configuration


def test_hosted_control_plane_can_verify_the_separate_execution_role_pattern():
    configuration = Path("infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    assert "role/davdeployDiscovery-*" in configuration
    assert "role/davdeployExecution-*" in configuration
