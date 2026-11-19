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
    assert "davdeployNovaPlanBrokerRoleArn" not in plan_role
    assert "sts:ExternalId: !Ref ExternalId" in plan_role
    assert "Effect: Deny" in policy
    assert "NotAction:" in policy
    assert "aws:ResourceAccount: !Ref AWS::AccountId" in policy
    assert 'Resource: "*"' in policy
    assert "Effect: Allow" in policy
    assert "lambda:Get*" in policy
    assert "dynamodb:Describe*" in policy
    assert "rds:DescribeDBInstances" in policy
    assert "rds:DescribeDBClusters" in policy
    assert "rds:ListTagsForResource" in policy
    assert "rds:DescribeDBSubnetGroups" in policy
    assert "s3:ListBucket" in policy
    assert "s3:GetObject" not in policy
    assert "dynamodb:GetItem" not in policy
    assert "lambda:InvokeFunction" not in policy
    assert "iam:PassRole" not in policy
    assert "rds:ModifyDBInstance" not in policy
    assert "rds:CreateDBSubnetGroup" not in policy
    assert "rds:ModifyDBSubnetGroup" not in policy
    assert "rds:DeleteDBSubnetGroup" not in policy
    assert "rds:DeleteDBCluster" not in policy
    assert "rds:RestoreDBInstanceFromDBSnapshot" not in policy
    assert "rds:StartExportTask" not in policy
    assert "rds:DownloadDBLogFilePortion" not in policy
    assert "rds-data:ExecuteStatement" not in policy
    assert "secretsmanager:GetSecretValue" not in policy
    template_actions = set(
        re.findall(r"^\s+- ([a-z0-9*]+:[A-Za-z0-9*]+)$", policy, re.MULTILINE)
    )
    assert template_actions == set(PLAN_ROLE_READ_ACTIONS)
    assert "AdministratorAccess" not in plan_role
    assert "NovaPlanOnlyRoleArn" in template


def test_quick_create_plan_role_trusts_only_the_control_plane_broker():
    template = Path("infrastructure/cloudformation/customer-discovery-role.yaml").read_text()
    plan_role = template.split("\n  NovaPlanOnlyRole:\n", 1)[1].split("\n  ExecutionRole:\n", 1)[0]

    assert "CreateNovaPlanBrokerTrust" not in template
    assert "davdeployNovaPlanBrokerRoleArn" not in template
    assert "AWS: !Ref davdeployDiscoveryBrokerRoleArn" in plan_role
    assert "DavDeploy does not attest effective permissions" in template
    assert "It has no customer service permissions" not in template


def test_plan_role_broker_permissions_are_explicit_follow_up_not_added_to_existing_executor():
    configuration = Path("infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    executor = configuration.split('resource "aws_iam_role_policy" "customer_executor"', 1)[
        1
    ].split('resource "aws_codebuild_project" "customer_executor"', 1)[0]

    assert 'Resource = "arn:aws:iam::*:role/davdeployExecution-*"' in executor
    assert "davdeployPlan-*" not in executor


def test_public_template_host_publishes_append_only_hash_keyed_objects():
    configuration = Path("infrastructure/terraform/connection-template-host/main.tf").read_text()
    variables = Path("infrastructure/terraform/connection-template-host/variables.tf").read_text()
    outputs = Path("infrastructure/terraform/connection-template-host/outputs.tf").read_text()
    script = Path("scripts/customer-aws-template-host.sh").read_text()

    assert 'actions   = ["s3:GetObject"]' in configuration
    assert 'resources = ["${aws_s3_bucket.templates.arn}/cloudformation/*"]' in configuration
    assert "s3:ListBucket" not in configuration
    assert 'resource "aws_s3_object" "published_customer_templates"' in configuration
    assert "for_each = local.published_keys" in configuration
    assert "published_keys = setunion(var.retained_template_keys, toset(keys(local.current_template_sources)))" in configuration
    assert 'key    = each.key' in configuration
    assert 'source       = lookup(local.current_template_sources, each.key, null)' in configuration
    assert "(local.template_key)            = local.template_source" in configuration
    assert "(local.nova_apply_template_key) = local.nova_apply_template_source" in configuration
    assert "contains(keys(local.current_template_sources), each.key)" in configuration
    assert "prevent_destroy = true" in configuration
    assert "ignore_changes  = all" in configuration
    assert 'resource "aws_s3_object" "current_customer_discovery_role"' not in configuration
    assert 'resource "aws_s3_object" "retained_customer_templates"' not in configuration

    current_live_key = (
        "cloudformation/customer-discovery-role-"
        "8c5d1c82682b3bb90ff1f45d121b475e7b33b484f556feabafbf387c335aea4e.yaml"
    )
    moves = re.findall(
        r"(?ms)^moved\s*\{\s*from\s*=\s*(.+?)\s*to\s*=\s*(.+?)\s*\}",
        configuration,
    )
    move_sources = [source for source, _ in moves]
    assert len(move_sources) == len(set(move_sources)), "each Terraform source address must have one move destination"

    expected_moves = {
        "aws_s3_object.current_customer_discovery_role": (
            f'aws_s3_object.published_customer_templates["{current_live_key}"]'
        ),
        "aws_s3_object.customer_discovery_role": (
            'aws_s3_object.retained_customer_templates["cloudformation/customer-discovery-role-'
            '600858c0ab944fd3f5aef06626ec5bc6ef9ed46352b418d87d651e05196bc11d.yaml"]'
        ),
        "aws_s3_object.active_customer_discovery_role": (
            'aws_s3_object.retained_customer_templates["cloudformation/customer-discovery-role-'
            '7e03683a397f0d4e2a5f68b9559d2790ff127e5513540457b47e9c4779b2b793.yaml"]'
        ),
        "aws_s3_object.published_customer_discovery_role": (
            'aws_s3_object.retained_customer_templates["cloudformation/customer-discovery-role-'
            'f3d9e1e5776fe147bbbc10107e41d221497f9b98c6b641eb8ac08467fd54aedb.yaml"]'
        ),
    }
    prior_keys = (
        "cloudformation/customer-discovery-role-600858c0ab944fd3f5aef06626ec5bc6ef9ed46352b418d87d651e05196bc11d.yaml",
        "cloudformation/customer-discovery-role-7e03683a397f0d4e2a5f68b9559d2790ff127e5513540457b47e9c4779b2b793.yaml",
        "cloudformation/customer-discovery-role-f3d9e1e5776fe147bbbc10107e41d221497f9b98c6b641eb8ac08467fd54aedb.yaml",
    )
    for prior_key in prior_keys:
        assert prior_key in variables
        retained_address = f'aws_s3_object.retained_customer_templates["{prior_key}"]'
        published_address = f'aws_s3_object.published_customer_templates["{prior_key}"]'
        expected_moves[retained_address] = published_address

    assert dict(moves) == expected_moves

    assert re.search(r"template_hash\s*=\s*filesha256\(local\.template_source\)", configuration)
    assert re.search(
        r'template_key\s*=\s*"cloudformation/customer-discovery-role-\$\{local\.template_hash\}\.yaml"',
        configuration,
    )
    assert "aws_s3_object.published_customer_templates[local.template_key].key" in outputs
    assert "APPLY_DAVDEPLOY_TEMPLATE_HOST" in script
    assert "DESTROY_DAVDEPLOY_TEMPLATE_HOST" in script


def test_public_template_host_publishes_nova_apply_role_in_protected_collection():
    configuration = Path("infrastructure/terraform/connection-template-host/main.tf").read_text()
    variables = Path("infrastructure/terraform/connection-template-host/variables.tf").read_text()
    outputs = Path("infrastructure/terraform/connection-template-host/outputs.tf").read_text()

    assert "customer-nova-apply-role.yaml" in configuration
    assert "customer-nova-apply-role-${local.nova_apply_template_hash}.yaml" in configuration
    assert "(local.nova_apply_template_key) = local.nova_apply_template_source" in configuration
    assert 'resource "aws_s3_object" "current_customer_nova_apply_role"' not in configuration
    assert "prevent_destroy = true" in configuration
    assert "ignore_changes  = all" in configuration
    assert "nova-apply-role" in variables
    assert "customer_nova_apply_role_template_url" in outputs
    assert "published_customer_templates[local.nova_apply_template_key].key" in outputs


def test_nova_apply_role_onboarding_is_default_off_and_uses_public_template_configuration():
    configuration = Path("infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    variables = Path("infrastructure/terraform/serverless-control-plane/variables.tf").read_text()

    assert 'variable "enable_nova_apply_role_onboarding"' in variables
    onboarding = variables.split(
        'variable "enable_nova_apply_role_onboarding"', 1
    )[1].split("variable ", 1)[0]
    assert "default     = false" in onboarding
    assert 'variable "nova_apply_role_template_url"' in variables
    assert "DAVDEPLOY_NOVA_APPLY_ROLE_SETUP_ENABLED" in configuration
    assert "DAVDEPLOY_NOVA_APPLY_ROLE_TEMPLATE_URL" in configuration
    assert "DAVDEPLOY_NOVA_APPLY_BROKER_ROLE_ARN" in configuration


def test_control_plane_identity_can_assume_the_quick_create_role_name_pattern():
    configuration = Path("infrastructure/terraform/management-identity/main.tf").read_text()
    assert "role/davdeployDiscovery-*" in configuration


def test_hosted_control_plane_can_verify_the_separate_execution_role_pattern():
    configuration = Path("infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    assert "role/davdeployDiscovery-*" in configuration
    assert "role/davdeployExecution-*" in configuration
