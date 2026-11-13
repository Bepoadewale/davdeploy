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
        'DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_RUNNER_READY         = '
        'tostring(var.enable_nova_exact_plan_apply_runner)'
    ) in MAIN


def test_apply_runner_is_separate_and_fails_closed_until_worker_is_wired() -> None:
    project = block(MAIN, 'resource "aws_codebuild_project" "nova_exact_plan_apply"')
    assert 'name                   = local.nova_exact_plan_apply_project_name' in project
    assert 'service_role           = aws_iam_role.nova_exact_plan_apply[0].arn' in project
    assert 'type      = "NO_SOURCE"' in project
    assert 'artifacts { type = "NO_ARTIFACTS" }' in project
    assert 'privileged_mode             = false' in project
    assert "The fixed Nova exact-plan apply worker is not wired." in project
    assert "exit 1" in project
    assert "aws_iam_role.customer_executor" not in project
    assert "aws_codebuild_project.nova_plan_only" not in project

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
    assert '"codebuild:BuildArn"' in policy
    assert "/POST/api/v1/nova-apply/credentials" in policy


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
