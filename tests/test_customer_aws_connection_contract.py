from pathlib import Path

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


def test_public_template_host_allows_only_versioned_template_reads_and_is_confirmation_gated():
    configuration = Path("infrastructure/terraform/connection-template-host/main.tf").read_text()
    script = Path("scripts/customer-aws-template-host.sh").read_text()
    assert 'actions   = ["s3:GetObject"]' in configuration
    assert 'resources = ["${aws_s3_bucket.templates.arn}/cloudformation/*"]' in configuration
    assert "s3:ListBucket" not in configuration
    assert "APPLY_DAVDEPLOY_TEMPLATE_HOST" in script
    assert "DESTROY_DAVDEPLOY_TEMPLATE_HOST" in script


def test_control_plane_identity_can_assume_the_quick_create_role_name_pattern():
    configuration = Path("infrastructure/terraform/management-identity/main.tf").read_text()
    assert "role/davdeployDiscovery-*" in configuration


def test_hosted_control_plane_can_verify_the_separate_execution_role_pattern():
    configuration = Path("infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    assert "role/davdeployDiscovery-*" in configuration
    assert "role/davdeployExecution-*" in configuration
