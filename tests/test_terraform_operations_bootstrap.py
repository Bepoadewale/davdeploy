from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "infrastructure" / "terraform" / "terraform-operations-bootstrap"


def bootstrap_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(BOOTSTRAP.glob("*.tf"))
    )


def test_bootstrap_reuses_existing_state_lock_and_oidc_provider() -> None:
    source = bootstrap_source()

    assert 'data "aws_s3_bucket" "state"' in source
    assert 'data "aws_dynamodb_table" "lock"' in source
    assert 'data "aws_iam_openid_connect_provider" "github"' in source
    assert 'resource "aws_iam_openid_connect_provider"' not in source


def test_bootstrap_separates_plan_and_apply_trust() -> None:
    source = bootstrap_source()

    assert '${var.github_oidc_repository_subject}:environment:terraform-plan' in source
    assert '${var.github_oidc_repository_subject}:environment:terraform-apply' in source
    assert 'default     = "repo:Bepoadewale@99020860/davdeploy@1391292548"' in source
    assert "sts:AssumeRoleWithWebIdentity" in source
    assert "AdministratorAccess" not in source
    assert "PowerUserAccess" not in source


def test_bootstrap_encrypts_and_expires_operational_artifacts() -> None:
    source = bootstrap_source()

    assert source.count('sse_algorithm     = "aws:kms"') == 2
    assert source.count("enable_key_rotation     = true") == 2
    assert 'resource "aws_s3_bucket_public_access_block" "plans"' in source
    assert 'resource "aws_s3_bucket_public_access_block" "releases"' in source
    assert "plan_retention_days" in source
    assert "release_retention_days" in source


def test_apply_role_is_limited_to_required_control_plane_services() -> None:
    source = bootstrap_source()

    assert 'resources = ["arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:role/davdeploy-*"]' in source
    assert 'resources = ["arn:${data.aws_partition.current.partition}:lambda:${var.region}:${data.aws_caller_identity.current.account_id}:function:davdeploy-*"]' in source
    assert 'actions   = ["iam:CreateServiceLinkedRole"]' in source
    assert 'values   = ["rds.amazonaws.com"]' in source
    assert 'apigateway:${var.region}::/apis*' in source
    assert 'apigateway:${var.region}::/tags/arn%3Aaws%3Aapigateway%3A${var.region}%3A%3A%2Fv2%2Fapis%2F*' in source
    assert '"apigateway:TagResource", "apigateway:UntagResource"' in source
    assert '"secretsmanager:CreateSecret", "secretsmanager:TagResource"' in source
    assert 'secret:rds!cluster-*' in source


def test_apply_role_can_manage_the_nova_plan_project_and_its_exact_log_group() -> None:
    source = bootstrap_source()
    project_lifecycle = source.split('sid    = "CodeBuildProjectLifecycle"', 1)[1].split(
        "statement {", 1
    )[0]
    nova_logs = source.split('sid    = "NovaPlanOnlyLogs"', 1)[1].split(
        "statement {", 1
    )[0]
    runtime_roles = source.split('sid    = "RuntimeRoles"', 1)[1].split(
        "statement {", 1
    )[0]

    assert '"codebuild:UpdateProject"' in project_lifecycle
    assert '"codebuild:DeleteProject"' in project_lifecycle
    assert 'project/davdeploy-customer-executor' in project_lifecycle
    assert 'project/davdeploy-nova-plan-only' in project_lifecycle
    assert 'log-group:/aws/codebuild/davdeploy-nova-plan-only"' in nova_logs
    assert 'log-group:/aws/codebuild/davdeploy-nova-plan-only:*' in nova_logs
    assert '"logs:CreateLogGroup"' in nova_logs
    assert '"logs:DeleteLogGroup"' in nova_logs
    assert '"logs:PutRetentionPolicy"' in nova_logs
    assert '"logs:ListTagsForResource"' in nova_logs
    assert 'log-group:/aws/codebuild/davdeploy-*' not in nova_logs
    assert '"iam:CreateRole"' in runtime_roles
    assert '"iam:PutRolePolicy"' in runtime_roles
    assert '"iam:PassRole"' in runtime_roles
    assert 'role/davdeploy-*' in runtime_roles


def test_plan_workflow_uses_one_production_cognito_domain() -> None:
    workflow = (ROOT / ".github" / "workflows" / "terraform-plan.yml").read_text(
        encoding="utf-8"
    )

    assert "TF_VAR_cognito_domain_prefix: ${{ vars.COGNITO_DOMAIN_PREFIX }}" in workflow
    assert "TF_VAR_aws_connection_template_url: ${{ vars.AWS_CONNECTION_TEMPLATE_URL }}" in workflow
    assert "TF_VAR_aws_connection_template_url; do" in workflow
    assert "inputs.environment" not in workflow
