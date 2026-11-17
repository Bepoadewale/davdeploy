from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERRAFORM = ROOT / "infrastructure/terraform/serverless-control-plane"
MAIN = (TERRAFORM / "main.tf").read_text()
VARIABLES = (TERRAFORM / "variables.tf").read_text()
OPERATIONS = (ROOT / "infrastructure/terraform/terraform-operations-bootstrap/main.tf").read_text()


def block(source: str, marker: str) -> str:
    start = source.index(marker)
    end = source.find("\nresource \"", start + 1)
    if end < 0:
        end = source.find("\ndata \"", start + 1)
    return source[start:] if end < 0 else source[start:end]


def test_apply_boundary_is_disabled_and_requires_plan_and_remote_state_gates() -> None:
    variable = block(VARIABLES, 'variable "enable_nova_exact_plan_apply_runner"')
    assert "default     = false" in variable
    assert "enable_nova_plan_only_runner" in variable
    assert "enable_nova_plan_reviews" in variable
    assert "enable_nova_terraform_state_api" in variable

    for kind, name in (
        ("aws_iam_role", "nova_exact_plan_apply"),
        ("aws_iam_role_policy", "nova_exact_plan_apply"),
        ("aws_cloudwatch_log_group", "nova_exact_plan_apply"),
        ("aws_codebuild_project", "nova_exact_plan_apply"),
        ("aws_cloudwatch_event_rule", "nova_exact_plan_apply_completion"),
        ("aws_cloudwatch_event_target", "nova_exact_plan_apply_completion"),
    ):
        resource = block(MAIN, f'resource "{kind}" "{name}"')
        assert "count = var.enable_nova_exact_plan_apply_runner ? 1 : 0" in resource

    assert (
        'DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_RUNNER_READY = '
        'tostring(var.enable_nova_exact_plan_apply_runner && '
        'var.enable_nova_exact_plan_apply_credential_broker)'
    ) in " ".join(MAIN.split())
    credential_broker = block(
        VARIABLES, 'variable "enable_nova_exact_plan_apply_credential_broker"'
    )
    assert "default     = false" in credential_broker
    assert "enable_nova_exact_plan_apply_runner" in credential_broker
    assert (
        'DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_CREDENTIAL_BROKER_ENABLED = '
        'tostring(var.enable_nova_exact_plan_apply_credential_broker)'
    ) in " ".join(MAIN.split())
    runtime_env = block(MAIN, "locals {\n  runtime_environment = {")
    assert "DAVDEPLOY_NOVA_APPLY_BUCKET_OWNER" in runtime_env
    assert "DAVDEPLOY_NOVA_APPLY_KMS_KEY_ARN" in runtime_env
    api_policy = block(MAIN, 'resource "aws_iam_role_policy" "api"')
    assert "var.enable_nova_exact_plan_apply_credential_broker ? [{" in api_policy
    assert "role/davdeployNovaApply-*" in api_policy
    assert '"davdeploy-apply-verify-*"' in api_policy
    assert '"davdeploy-nova-apply-*"' in api_policy
    apply_integration = block(
        MAIN,
        'resource "aws_apigatewayv2_integration" "nova_exact_plan_apply_credentials"',
    )
    apply_route = block(
        MAIN,
        'resource "aws_apigatewayv2_route" "nova_exact_plan_apply_credentials"',
    )
    assert "count = var.enable_nova_exact_plan_apply_credential_broker ? 1 : 0" in apply_integration
    assert "count = var.enable_nova_exact_plan_apply_credential_broker ? 1 : 0" in apply_route
    assert 'route_key          = "POST /api/v1/nova-apply/credentials"' in apply_route
    assert 'authorization_type = "AWS_IAM"' in apply_route
    assert '"$context.identity.userArn"' in apply_integration
    apply_input_integration = block(
        MAIN,
        'resource "aws_apigatewayv2_integration" "nova_exact_plan_apply_input"',
    )
    apply_input_route = block(
        MAIN,
        'resource "aws_apigatewayv2_route" "nova_exact_plan_apply_input"',
    )
    assert "count = var.enable_nova_exact_plan_apply_runner ? 1 : 0" in apply_input_integration
    assert "count = var.enable_nova_exact_plan_apply_runner ? 1 : 0" in apply_input_route
    assert 'route_key          = "POST /api/v1/nova-apply/input"' in apply_input_route
    assert 'authorization_type = "AWS_IAM"' in apply_input_route
    assert '"$context.identity.userArn"' in apply_input_integration


def test_apply_runner_is_separate_and_invokes_the_fixed_saved_plan_worker() -> None:
    project = block(MAIN, 'resource "aws_codebuild_project" "nova_exact_plan_apply"')
    assert 'name                   = local.nova_exact_plan_apply_project_name' in project
    assert 'service_role           = aws_iam_role.nova_exact_plan_apply[0].arn' in project
    assert 'type      = "NO_SOURCE"' in project
    assert 'artifacts { type = "NO_ARTIFACTS" }' in project
    assert 'privileged_mode             = false' in project
    assert "davdeploy.nova_apply_codebuild" in project
    assert "terraform/1.14.7/terraform_1.14.7_linux_amd64.zip" in project
    assert "e8bbcefea8015156e04e2a325cde37a0b2fb761728bda548e2fe3b8ad7c18c96" in project
    assert "sha256sum --check --status" in project
    assert "aws_iam_role.customer_executor" not in project
    assert "aws_codebuild_project.nova_plan_only" not in project
    for setting in (
        "DAVDEPLOY_TERRAFORM_STATE_BOOTSTRAP_URL",
        "DAVDEPLOY_TERRAFORM_STATE_ENABLED",
        "DAVDEPLOY_TERRAFORM_STATE_API_URL",
        "DAVDEPLOY_NOVA_APPLY_CODE_BUCKET",
        "DAVDEPLOY_NOVA_APPLY_CODE_KEY",
        "DAVDEPLOY_NOVA_APPLY_CODE_VERSION",
    ):
        assert setting in project

    role = block(MAIN, 'resource "aws_iam_role" "nova_exact_plan_apply"')
    assert 'Principal = { Service = "codebuild.amazonaws.com" }' in role
    assert '"aws:SourceAccount"' in role
    assert '"aws:SourceArn"' in role

    policy = block(MAIN, 'resource "aws_iam_role_policy" "nova_exact_plan_apply"')
    assert '"sts:AssumeRole"' not in policy
    assert '"terraform:Apply"' not in policy
    assert '"terraform:Destroy"' not in policy
    assert '"s3:GetObjectVersion"' in policy
    assert "local.nova_exact_plan_apply_scoped_plan_key" in policy
    assert "local.nova_exact_plan_apply_scoped_workspace_key" in policy
    assert "plans/nova-generated/builds/*" not in policy
    assert '"codebuild:BuildArn"' in policy
    assert "/POST/api/v1/nova-apply/credentials" in policy
    assert "/POST/api/v1/nova-apply/input" in policy
    assert "/POST/api/v1/terraform-state/credentials" in policy

    api_artifacts = block(
        MAIN,
        'resource "aws_iam_role_policy" "api_nova_exact_plan_apply_artifacts"',
    )
    assert "local.nova_plan_only_build_saved_plan_key" in api_artifacts
    assert "local.nova_plan_only_build_workspace_key" in api_artifacts
    assert "local.nova_exact_plan_apply_staged_plan_key" in api_artifacts
    assert "local.nova_exact_plan_apply_staged_workspace_key" in api_artifacts


def test_apply_dispatch_uses_only_durable_run_id_and_denies_build_overrides() -> None:
    data_policy = block(MAIN, 'data "aws_iam_policy" "api_nova_exact_plan_apply_codebuild"')
    assert "count = var.enable_nova_exact_plan_apply_runner ? 1 : 0" in data_policy
    assert "policy/nova-exact-plan-apply-codebuild" in data_policy
    attachment = block(
        MAIN,
        'resource "aws_iam_role_policy_attachment" "api_nova_exact_plan_apply_codebuild"',
    )
    assert "aws_iam_role.api.name" in attachment
    assert "data.aws_iam_policy.api_nova_exact_plan_apply_codebuild[0].arn" in attachment

    for name in (
        "nova_exact_plan_apply_start_build_overrides",
        "nova_exact_plan_apply_codebuild",
    ):
        assert f'resource "aws_iam_policy" "{name}"' in OPERATIONS

    guarded = block(
        OPERATIONS,
        'resource "aws_iam_policy" "nova_exact_plan_apply_start_build_overrides"',
    )
    for override in (
        "codebuild:source.buildspec",
        "codebuild:serviceRole",
        "codebuild:source",
        "codebuild:environment.image",
        "codebuild:environment.computeType",
        "codebuild:environment.privilegedMode",
        "codebuild:artifacts",
        "codebuild:secondarySources",
    ):
        assert override in OPERATIONS
    assert '"DAVDEPLOY_NOVA_APPLY_RUN_ID"' in guarded

    allow = block(OPERATIONS, 'resource "aws_iam_policy" "nova_exact_plan_apply_codebuild"')
    assert '"DAVDEPLOY_NOVA_APPLY_RUN_ID"' in allow
    assert '"codebuild:BatchGetBuilds"' in allow
    assert '"codebuild:environment.environmentVariables.name"' in allow
    assert '"codebuild:environment.environmentVariables/DAVDEPLOY_NOVA_APPLY_RUN_ID.value"' in allow
    assert '"codebuild:source.buildspec"' not in allow
