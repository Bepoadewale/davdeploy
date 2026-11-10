import ast
import re
from fnmatch import fnmatchcase
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
    assert (
        "condition     = !var.enable_nova_plan_only_runner || var.enable_nova_plan_reviews"
        in variable
    )
    assert "TF_VAR_enable_nova_plan_only_runner" in PLAN_WORKFLOW

    api_policy = resource_block(MAIN, "aws_iam_role_policy", "api")
    assert '"codebuild:ListBuildsForProject", "codebuild:BatchGetBuilds"' in api_policy
    assert "nova_plan_artifact_bucket}/plans/nova-generated/requests/" in api_policy

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
    assert re.search(r'type\s*=\s*"NO_SOURCE"', project)
    assert 'artifacts { type = "NO_ARTIFACTS" }' in project
    assert 'privileged_mode             = false' in project
    assert "python3.12 -m davdeploy.nova_plan_codebuild" in project
    assert "1.14.7" in project
    assert "sha256sum --check --status" in project
    assert 'DAVDEPLOY_NOVA_PLAN_PROJECT' in MAIN
    assert 'aws_codebuild_project.nova_plan_only[0].name : ""' in MAIN


def test_state_bootstrap_is_exact_route_signed_by_the_plan_only_role() -> None:
    route = resource_block(MAIN, "aws_apigatewayv2_route", "terraform_state_bootstrap")
    integration = resource_block(MAIN, "aws_apigatewayv2_integration", "terraform_state_bootstrap")
    role_policy = resource_block(MAIN, "aws_iam_role_policy", "nova_plan_only_state_bootstrap")
    assert 'route_key          = "POST /api/v1/terraform-state/credentials"' in route
    assert 'authorization_type = "AWS_IAM"' in route
    assert '"overwrite:header.x-davdeploy-bootstrap-principal"' in integration
    assert '"$context.identity.userArn"' in integration
    assert "execute-api:Invoke" in role_policy
    assert "terraform-state/credentials" in role_policy
    assert 'DAVDEPLOY_TERRAFORM_STATE_ENABLED                    = tostring(var.enable_nova_terraform_state_api)' in MAIN
    assert 'DAVDEPLOY_TERRAFORM_STATE_API_URL                    = var.enable_nova_terraform_state_api ? var.nova_terraform_state_api_url : ""' in MAIN
    state_policy = resource_block(MAIN, "aws_iam_role_policy", "nova_plan_only_state_bootstrap")
    assert "count = var.enable_nova_terraform_state_api ? 1 : 0" in state_policy
    state_api_toggle = VARIABLES.split('variable "enable_nova_terraform_state_api"', 1)[1].split(
        "\nvariable ", 1
    )[0]
    assert "default     = false" in state_api_toggle
    assert "var.enable_nova_plan_only_runner" in state_api_toggle
    assert "var.enable_nova_terraform_state_storage" in state_api_toggle
    project = resource_block(MAIN, "aws_codebuild_project", "nova_plan_only")
    assert 'name  = "DAVDEPLOY_TERRAFORM_STATE_ENABLED"' in project
    assert 'name  = "DAVDEPLOY_TERRAFORM_STATE_API_URL"' in project
    state_routes = resource_block(MAIN, "aws_apigatewayv2_route", "terraform_state")
    assert '"GET /api/v1/terraform-state/{state_id}"' in MAIN
    assert '"POST /api/v1/terraform-state/{state_id}/lock"' in MAIN
    assert '"DELETE /api/v1/terraform-state/{state_id}/unlock"' in MAIN
    assert 'authorization_type = "NONE"' in state_routes
    assert 'target             = "integrations/${aws_apigatewayv2_integration.api.id}"' in state_routes

    storage_toggle = VARIABLES.split('variable "enable_nova_terraform_state_storage"', 1)[1].split(
        "\nvariable ", 1
    )[0]
    assert "default     = false" in storage_toggle
    api_policy = resource_block(MAIN, "aws_iam_role_policy", "api")
    assert 'var.enable_nova_terraform_state_storage ? [{' in api_policy
    assert '"s3:GetObject", "s3:GetObjectVersion", "s3:PutObject"' in api_policy
    assert 'terraform-state/*' in api_policy
    state_object_policy = api_policy.split(
        'var.enable_nova_terraform_state_storage ? [{', 1
    )[1].split('}] : []', 1)[0]
    assert '"s3:ListBucket"' not in state_object_policy
    state_storage_source = (ROOT / "apps/api/src/davdeploy/terraform_state.py").read_text()
    assert 'IfNoneMatch="*"' in state_storage_source
    assert "status == 412" in state_storage_source
    state_bucket = resource_block(MAIN, "aws_s3_bucket", "nova_terraform_state")
    assert "var.enable_nova_terraform_state_storage ? 1 : 0" in state_bucket
    assert "prevent_destroy = true" in state_bucket
    encryption = resource_block(
        MAIN, "aws_s3_bucket_server_side_encryption_configuration", "nova_terraform_state"
    )
    versioning = resource_block(MAIN, "aws_s3_bucket_versioning", "nova_terraform_state")
    public_access = resource_block(MAIN, "aws_s3_bucket_public_access_block", "nova_terraform_state")
    assert 'sse_algorithm     = "aws:kms"' in encryption
    assert "bucket_key_enabled = true" in encryption
    assert 'versioning_configuration { status = "Enabled" }' in versioning
    assert "block_public_acls       = true" in public_access


def test_customer_plan_role_verification_is_separate_opt_in_and_role_prefix_scoped() -> None:
    variable = VARIABLES.split('variable "enable_nova_plan_role_verification"', 1)[1].split(
        "\nvariable ", 1
    )[0]
    assert 'default     = false' in variable
    assert (
        "TF_VAR_enable_nova_plan_role_verification: "
        "${{ vars.NOVA_PLAN_ROLE_VERIFICATION_ENABLED || 'false' }}"
    ) in PLAN_WORKFLOW
    assert "effective permissions" in variable
    assert "DAVDEPLOY_NOVA_PLAN_ROLE_VERIFY_ENABLED" in MAIN
    assert "tostring(var.enable_nova_plan_role_verification)" in MAIN
    assert 'var.enable_nova_plan_role_verification ? [{' in MAIN
    verification = MAIN.split('var.enable_nova_plan_role_verification ? [{', 1)[1].split(
        "}] : []", 1
    )[0]
    assert 'Action   = ["sts:AssumeRole"]' in verification
    assert 'Resource = "arn:aws:iam::*:role/davdeployPlan-*"' in verification
    assert '"sts:ExternalId"' in verification
    assert '"sts:RoleSessionName" = "davdeploy-plan-verify-*"' in verification
    assert 'Resource = "*"' not in verification

    runner_validation = VARIABLES.split('variable "enable_nova_plan_only_runner"', 1)[1].split(
        "\nvariable ", 1
    )[0]
    assert "var.enable_nova_plan_role_verification" in runner_validation


def test_plan_broker_env_is_derived_from_runner_and_not_required_for_setup_only() -> None:
    assert "DAVDEPLOY_NOVA_PLAN_BROKER_ROLE_ARN" in MAIN
    assert (
        'var.enable_nova_plan_only_runner ? aws_iam_role.nova_plan_only[0].arn : ""' in MAIN
    )


def test_nova_plan_only_service_role_is_scoped_to_plan_request_artifacts_and_logs() -> None:
    policy = resource_block(MAIN, "aws_iam_role_policy", "nova_plan_only")
    assert 'logs:CreateLogStream' in policy
    assert 'logs:PutLogEvents' in policy
    assert "aws_cloudwatch_log_group.nova_plan_only[0].arn" in policy
    assert '"s3:GetObject"' in policy
    assert '"s3:PutObject"' in policy
    assert "nova_plan_only_scoped_input_key" in policy
    assert "nova_plan_only_scoped_result_key" in policy
    assert "nova_plan_only_scoped_saved_plan_key" in policy
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
        '"terraform:Apply"',
        '"terraform:Destroy"',
    ):
        assert forbidden not in policy
    assert 'Action   = ["sts:AssumeRole"]' in policy
    assert 'role/davdeployPlan-*' in policy
    assert '"sts:ExternalId"      = "?*"' in policy
    assert '"sts:RoleSessionName" = "davdeploy-nova-plan-????????"' in policy

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
        "codebuild:autoRetryLimit",
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


def test_fixed_dispatcher_source_sends_no_other_start_build_arguments() -> None:
    source = (ROOT / "apps/api/src/davdeploy/nova_plan_dispatch.py").read_text()
    module = ast.parse(source)
    dispatcher_class = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "NovaPlanOnlyDispatcher"
    )
    start_build = next(
        node
        for node in dispatcher_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "start_build"
    )
    calls = [
        node
        for node in ast.walk(start_build)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "start_build"
    ]

    assert len(calls) == 1
    call = calls[0]
    assert all(keyword.arg is not None for keyword in call.keywords)
    assert {keyword.arg for keyword in call.keywords} == {
        "projectName",
        "idempotencyToken",
        "environmentVariablesOverride",
    }
    overrides = next(
        keyword.value
        for keyword in call.keywords
        if keyword.arg == "environmentVariablesOverride"
    )
    assert isinstance(overrides, ast.List)
    assert len(overrides.elts) == 1
    run_id_override = overrides.elts[0]
    assert isinstance(run_id_override, ast.Dict)
    assert {
        key.value for key in run_id_override.keys if isinstance(key, ast.Constant)
    } == {"name", "value", "type"}


def test_api_artifact_permissions_and_completion_events_are_exactly_scoped() -> None:
    api_artifacts = resource_block(MAIN, "aws_iam_role_policy", "api_nova_plan_only_artifacts")
    assert "count = var.enable_nova_plan_only_runner ? 1 : 0" in api_artifacts
    assert "nova_plan_only_input_key" in api_artifacts
    assert "nova_plan_only_build_result_key" in api_artifacts
    assert '"kms:EncryptionContext:aws:s3:arn"' in api_artifacts
    assert re.search(
        r'Action\s*=\s*\["s3:GetObject",\s*"s3:GetObjectVersion"\]\s*Resource\s*=\s*'
        r'"arn:\$\{data\.aws_partition\.current\.partition\}:s3:::'
        r'\$\{var\.nova_plan_artifact_bucket\}/\$\{local\.nova_plan_only_build_input_key\}"',
        api_artifacts,
    )

    event_rule = resource_block(MAIN, "aws_cloudwatch_event_rule", "nova_plan_only_completion")
    assert '"project-name" = [aws_codebuild_project.nova_plan_only[0].name]' in event_rule
    for status in ("SUCCEEDED", "FAILED", "FAULT", "TIMED_OUT", "STOPPED"):
        assert f'"{status}"' in event_rule
    target = resource_block(MAIN, "aws_cloudwatch_event_target", "nova_plan_only_completion")
    assert "aws_sqs_queue.worker.arn" in target


def test_plan_only_object_keys_require_object_level_sse_kms_context() -> None:
    assert re.search(
        r'nova_plan_only_input_key\s*=\s*"plans/nova-generated/requests/\*/input\.json"',
        MAIN,
    )
    assert re.search(
        r'nova_plan_only_build_result_key\s*=\s*"\$\{local\.nova_plan_only_build_prefix\}/result\.json"',
        MAIN,
    )
    role_policy = resource_block(MAIN, "aws_iam_role_policy", "nova_plan_only")
    assert "StringLike" in role_policy
    assert "nova_plan_only_scoped_input_key" in role_policy
    assert "nova_plan_only_scoped_result_key" in role_policy

    bootstrap = (ROOT / "infrastructure/terraform/terraform-operations-bootstrap/main.tf").read_text()
    plans_encryption = bootstrap.split(
        'resource "aws_s3_bucket_server_side_encryption_configuration" "plans"', 1
    )[1].split('\nresource "', 1)[0]
    assert "bucket_key_enabled = true" in plans_encryption
    api_artifacts = resource_block(MAIN, "aws_iam_role_policy", "api_nova_plan_only_artifacts")
    bucket_context = (
        '"kms:EncryptionContext:aws:s3:arn" = '
        '"arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}"'
    )
    assert api_artifacts.count(bucket_context) == 3
    assert re.search(
        r'Action\s*=\s*\["s3:GetObject",\s*"s3:GetObjectVersion"\]\s*Resource\s*=\s*'
        r'"arn:\$\{data\.aws_partition\.current\.partition\}:s3:::'
        r'\$\{var\.nova_plan_artifact_bucket\}/\$\{local\.nova_plan_only_build_input_key\}"',
        api_artifacts,
    )
    dispatcher = (ROOT / "apps/api/src/davdeploy/nova_plan_dispatch.py").read_text()
    codebuild_runner = (ROOT / "apps/api/src/davdeploy/nova_plan_codebuild.py").read_text()
    assert dispatcher.count("BucketKeyEnabled=True") == 1
    assert codebuild_runner.count("BucketKeyEnabled=True") == 2


def test_codebuild_artifact_permissions_are_scoped_to_its_exact_build_arn() -> None:
    policy = resource_block(MAIN, "aws_iam_role_policy", "nova_plan_only")
    assert re.search(
        r'nova_plan_only_scoped_prefix\s*=\s*"plans/nova-generated/builds/\$\$\{codebuild:buildArn\}"',
        MAIN,
    )
    for scoped_key in (
        "nova_plan_only_scoped_input_key",
        "nova_plan_only_scoped_result_key",
        "nova_plan_only_scoped_saved_plan_key",
    ):
        assert f"local.{scoped_key}" in policy
    for unscoped_key in (
        "local.nova_plan_only_input_key}",
        "local.nova_plan_only_build_input_key}",
        "local.nova_plan_only_build_result_key}",
        "local.nova_plan_only_build_saved_plan_key}",
    ):
        assert unscoped_key not in policy
    assert "plans/nova-generated/requests/" not in policy
    bucket_context = (
        '"kms:EncryptionContext:aws:s3:arn" = '
        '"arn:${data.aws_partition.current.partition}:s3:::${var.nova_plan_artifact_bucket}"'
    )
    assert policy.count(bucket_context) == 2
    assert "nova_plan_only_build_prefix}/*\"" not in policy

    scoped_prefix = "plans/nova-generated/builds/$${codebuild:buildArn}"
    build_a = "arn:aws:codebuild:us-east-1:654654474502:build/project-a:run-a"
    build_b = "arn:aws:codebuild:us-east-1:654654474502:build/project-a:run-b"
    for suffix, object_suffix in (
        ("/input.json", "/input.json"),
        ("/result.json", "/result.json"),
        (
            "/org-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/project-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/"
            "revision-cccccccccccccccccccccccccccccccc/" + "d" * 64 + ".tfplan",
            "/org-*/project-*/revision-*/*.tfplan",
        ),
    ):
        resource_pattern = scoped_prefix.replace("$${codebuild:buildArn}", build_a) + object_suffix
        key_a = f"plans/nova-generated/builds/{build_a}{suffix}"
        key_b = f"plans/nova-generated/builds/{build_b}{suffix}"
        assert fnmatchcase(key_a, resource_pattern)
        assert not fnmatchcase(key_b, resource_pattern)
