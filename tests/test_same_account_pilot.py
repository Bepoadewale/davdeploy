from pathlib import Path

CUSTOMER_MAIN = Path(
    "infrastructure/terraform/customer-workload-app-runner-pilot/main.tf"
).read_text(encoding="utf-8")
CUSTOMER_VARIABLES = Path(
    "infrastructure/terraform/customer-workload-app-runner-pilot/variables.tf"
).read_text(encoding="utf-8")
CUSTOMER_VERSIONS = Path(
    "infrastructure/terraform/customer-workload-app-runner-pilot/versions.tf"
).read_text(encoding="utf-8")
CUSTOMER_OUTPUTS = Path(
    "infrastructure/terraform/customer-workload-app-runner-pilot/outputs.tf"
).read_text(encoding="utf-8")
CUSTOMER_SCRIPT = Path("scripts/customer-workload-app-runner-pilot.sh").read_text(
    encoding="utf-8"
)
PLATFORM_MAIN = Path("infrastructure/terraform/app-runner-runtime/main.tf").read_text(
    encoding="utf-8"
)
PLATFORM_SCRIPT = Path("scripts/app-runner-runtime.sh").read_text(encoding="utf-8")


def test_platform_and_customer_use_explicit_non_overlapping_placements():
    assert 'Scope           = "platform"' in PLATFORM_MAIN
    assert 'Placement       = "platform"' in PLATFORM_MAIN
    assert 'default     = "10.42.0.0/16"' in Path(
        "infrastructure/terraform/app-runner-runtime/variables.tf"
    ).read_text(encoding="utf-8")
    assert 'default     = "customer-sandbox"' in CUSTOMER_VARIABLES
    assert 'default     = "10.84.0.0/16"' in CUSTOMER_VARIABLES
    assert "var.customer_vpc_cidr != var.platform_vpc_cidr" in CUSTOMER_MAIN
    assert "SAME_ACCOUNT_PILOT_NOT_CROSS_ACCOUNT" in CUSTOMER_OUTPUTS


def test_customer_sandbox_has_a_dedicated_private_vpc_boundary_with_https_egress():
    assert 'resource "aws_vpc" "customer_sandbox"' in CUSTOMER_MAIN
    assert 'resource "aws_subnet" "customer_private"' in CUSTOMER_MAIN
    assert 'resource "aws_apprunner_vpc_connector" "customer_sandbox"' in CUSTOMER_MAIN
    assert 'egress_type       = "VPC"' in CUSTOMER_MAIN
    # App Runner's VPC connector needs controlled outbound access while it pulls
    # the workload image and reaches HTTPS dependencies.  The workload remains
    # in private subnets; only the dedicated NAT subnet is public.
    assert 'resource "aws_nat_gateway" "customer_sandbox"' in CUSTOMER_MAIN
    assert 'resource "aws_internet_gateway" "customer_sandbox"' in CUSTOMER_MAIN
    assert 'resource "aws_route_table" "customer_private"' in CUSTOMER_MAIN
    assert 'nat_gateway_id = aws_nat_gateway.customer_sandbox.id' in CUSTOMER_MAIN
    assert 'resource "aws_vpc_security_group_egress_rule" "customer_runtime_https"' in CUSTOMER_MAIN
    assert 'from_port         = 443' in CUSTOMER_MAIN
    assert 'to_port           = 443' in CUSTOMER_MAIN
    assert "davdeploy-${var.connection_id}-workload" in CUSTOMER_MAIN
    assert "app_runner_ecr_access_role_arn" in CUSTOMER_MAIN
    assert "app_runner_runtime_role_arn" in CUSTOMER_MAIN
    assert "assume_role" not in CUSTOMER_VERSIONS
    assert "customer_execution_external_id" not in CUSTOMER_VARIABLES
    assert "customer_execution_external_id" not in CUSTOMER_SCRIPT
    assert 'profile = "davdeploy-customer"' in CUSTOMER_VERSIONS
    assert "AWS_SHARED_CREDENTIALS_FILE" in CUSTOMER_SCRIPT
    assert "customer_aws_args=(--profile \"$customer_profile\")" in CUSTOMER_SCRIPT
    assert 'Name=tag:ConnectionId,Values=${connection_id}' in CUSTOMER_SCRIPT


def test_customer_template_keeps_execution_to_explicit_administrator_pilot():
    template = Path("infrastructure/cloudformation/customer-discovery-role.yaml").read_text(
        encoding="utf-8"
    )
    assert 'ManagedBy             = "davdeploy"' in CUSTOMER_MAIN
    assert "aws:RequestTag/ManagedBy: davdeploy" not in template
    assert "AppRunner" not in template
    assert "AccessMode" in template
    assert "AdministratorAccess" in template


def test_state_and_teardown_are_scope_specific_and_account_guarded():
    assert "davdeploy/platform/app-runner-runtime.tfstate" in PLATFORM_SCRIPT
    assert "davdeploy/customer/${connection_id}/workload-app-runner.tfstate" in CUSTOMER_SCRIPT
    assert "EXPECTED_AWS_ACCOUNT_ID" in PLATFORM_SCRIPT
    assert "EXPECTED_AWS_ACCOUNT_ID" in CUSTOMER_SCRIPT
    assert "Customer sandbox VPC still exists" in CUSTOMER_SCRIPT
    assert "Connection roles are retained" in CUSTOMER_SCRIPT
    assert "ensure_app_runner_service_linked_role" in CUSTOMER_SCRIPT
    assert 'ensure_app_runner_service_linked_role apprunner.amazonaws.com "App Runner"' in CUSTOMER_SCRIPT
    assert "networking.apprunner.amazonaws.com" in CUSTOMER_SCRIPT
    assert "aws sts assume-role" in CUSTOMER_SCRIPT
    assert '"$DAVDEPLOY_CUSTOMER_EXECUTION_ROLE_ARN"' in CUSTOMER_SCRIPT
    assert '--external-id "$external_id"' in CUSTOMER_SCRIPT
    assert "export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN" not in CUSTOMER_SCRIPT
    assert "unset external_id" in CUSTOMER_SCRIPT
    combined = CUSTOMER_MAIN + CUSTOMER_SCRIPT + PLATFORM_MAIN + PLATFORM_SCRIPT
    assert "organizations create-account" not in combined
    assert "organizations invite-account" not in combined
