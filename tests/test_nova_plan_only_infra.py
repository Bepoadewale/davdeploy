from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TERRAFORM = ROOT / "infrastructure/terraform/serverless-control-plane"
MAIN = (TERRAFORM / "main.tf").read_text()
VARIABLES = (TERRAFORM / "variables.tf").read_text()
PLAN_WORKFLOW = (ROOT / ".github/workflows/terraform-plan.yml").read_text()


def resource_block(terraform: str, resource_type: str, resource_name: str) -> str:
    start = terraform.index(f'resource "{resource_type}" "{resource_name}"')
    next_resource = terraform.find('\nresource "', start + 1)
    return terraform[start:] if next_resource < 0 else terraform[start:next_resource]


def test_nova_plan_only_resources_are_opt_in_and_fail_closed() -> None:
    variable = VARIABLES.split('variable "enable_nova_plan_only_runner"', 1)[1].split(
        "\nvariable ", 1
    )[0]
    assert 'default     = false' in variable
    assert 'var.nova_plan_artifact_bucket != ""' in variable
    assert 'var.nova_plan_kms_key_arn != ""' in variable
    assert "TF_VAR_enable_nova_plan_only_runner" in PLAN_WORKFLOW

    for resource_type, resource_name in (
        ("aws_iam_role", "nova_plan_only"),
        ("aws_iam_role_policy", "nova_plan_only"),
        ("aws_cloudwatch_log_group", "nova_plan_only"),
        ("aws_codebuild_project", "nova_plan_only"),
        ("aws_cloudwatch_event_rule", "nova_plan_only_completion"),
        ("aws_cloudwatch_event_target", "nova_plan_only_completion"),
    ):
        block = resource_block(MAIN, resource_type, resource_name)
        assert "count = var.enable_nova_plan_only_runner ? 1 : 0" in block

    project = resource_block(MAIN, "aws_codebuild_project", "nova_plan_only")
    assert 'type = "NO_SOURCE"' in project
    assert 'artifacts { type = "NO_ARTIFACTS" }' in project
    assert 'privileged_mode             = false' in project
    assert "exit 78" in project
    assert 'DAVDEPLOY_NOVA_PLAN_PROJECT' in MAIN
    assert 'aws_codebuild_project.nova_plan_only[0].name : ""' in MAIN


def test_nova_plan_only_service_role_is_scoped_to_plan_request_artifacts_and_logs() -> None:
    policy = resource_block(MAIN, "aws_iam_role_policy", "nova_plan_only")
    assert 'logs:CreateLogStream' in policy
    assert 'logs:PutLogEvents' in policy
    assert "aws_cloudwatch_log_group.nova_plan_only[0].arn" in policy
    assert '"s3:GetObject"' in policy
    assert '"s3:PutObject"' in policy
    assert "nova_plan_only_input_key" in policy
    assert "nova_plan_only_result_key" in policy
    assert '"s3:x-amz-server-side-encryption"' in policy
    assert '"s3:x-amz-server-side-encryption-aws-kms-key-id"' in policy
    assert '"kms:ViaService"' in policy
    assert '"kms:EncryptionContext:aws:s3:arn"' in policy
    assert '"kms:Decrypt"' in policy
    assert '"kms:GenerateDataKey"' in policy
    for forbidden in (
        "customer_execution_state_bucket",
        "customer_execution_lock_table",
        "secretsmanager:",
        '"sts:AssumeRole"',
        '"terraform:Apply"',
        '"terraform:Destroy"',
    ):
        assert forbidden not in policy

    role = resource_block(MAIN, "aws_iam_role", "nova_plan_only")
    assert '"aws:SourceAccount"' in role
    assert '"aws:SourceArn"' in role
    assert "${local.nova_plan_only_project_name}" in role


def test_api_can_start_only_this_project_with_the_trusted_run_id_override() -> None:
    policy = resource_block(MAIN, "aws_iam_role_policy", "api_nova_plan_only_codebuild")
    assert "count = var.enable_nova_plan_only_runner ? 1 : 0" in policy
    assert 'Action   = ["codebuild:StartBuild"]' in policy
    assert 'Action   = ["codebuild:BatchGetBuilds"]' in policy
    assert "aws_codebuild_project.nova_plan_only[0].arn" in policy
    assert '"codebuild:environment.environmentVariables.name" = ["DAVDEPLOY_NOVA_PLAN_RUN_ID"]' in policy
    assert '"codebuild:environment.environmentVariables/DAVDEPLOY_NOVA_PLAN_RUN_ID.value" = "?*"' in policy
    assert '"ForAnyValue:StringNotEquals"' in policy
    assert "nova_plan_only_blocked_start_build_keys" in policy

    blocked_keys = MAIN.split("nova_plan_only_blocked_start_build_keys = [", 1)[1].split("]", 1)[0]
    for override in (
        "codebuild:source.buildspec",
        "codebuild:source.location",
        "codebuild:source.auth.resource",
        "codebuild:serviceRole",
        "codebuild:environment.image",
        "codebuild:environment.computeType",
        "codebuild:environment.privilegedMode",
        "codebuild:artifacts",
        "codebuild:secondarySources",
        "codebuild:secondaryArtifacts",
        "codebuild:encryptionKey",
        "codebuild:cache",
        "codebuild:logsConfig",
    ):
        assert override in blocked_keys


def test_api_artifact_permissions_and_completion_events_are_exactly_scoped() -> None:
    api_artifacts = resource_block(MAIN, "aws_iam_role_policy", "api_nova_plan_only_artifacts")
    assert "count = var.enable_nova_plan_only_runner ? 1 : 0" in api_artifacts
    assert "nova_plan_only_input_key" in api_artifacts
    assert "nova_plan_only_result_key" in api_artifacts
    assert '"kms:EncryptionContext:aws:s3:arn"' in api_artifacts

    event_rule = resource_block(MAIN, "aws_cloudwatch_event_rule", "nova_plan_only_completion")
    assert '"project-name" = [aws_codebuild_project.nova_plan_only[0].name]' in event_rule
    for status in ("SUCCEEDED", "FAILED", "FAULT", "TIMED_OUT", "STOPPED"):
        assert f'"{status}"' in event_rule
    target = resource_block(MAIN, "aws_cloudwatch_event_target", "nova_plan_only_completion")
    assert "aws_sqs_queue.worker.arn" in target


def test_plan_only_object_keys_require_object_level_sse_kms_context() -> None:
    assert 'nova_plan_only_input_key    = "plans/nova-generated/requests/*/input.json"' in MAIN
    assert 'nova_plan_only_result_key   = "plans/nova-generated/requests/*/result.json"' in MAIN
    role_policy = resource_block(MAIN, "aws_iam_role_policy", "nova_plan_only")
    assert "StringLike" in role_policy
    assert "nova_plan_only_input_key" in role_policy
    assert "nova_plan_only_result_key" in role_policy
