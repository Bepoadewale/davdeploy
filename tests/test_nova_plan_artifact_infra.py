from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_nova_plan_storage_access_is_opt_in_and_prefix_scoped() -> None:
    terraform = (ROOT / "infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    variables = (
        ROOT / "infrastructure/terraform/serverless-control-plane/variables.tf"
    ).read_text()
    policy = terraform.split('resource "aws_iam_role_policy" "api"', 1)[1].split(
        'resource "aws_iam_role" "customer_executor"', 1
    )[0]

    assert 'variable "enable_nova_plan_reviews"' in variables
    assert (
        "default     = false"
        in variables.split('variable "enable_nova_plan_reviews"', 1)[1].split("}", 1)[0]
    )
    assert "var.enable_nova_plan_reviews ? [{" in policy
    assert '"s3:PutObject", "s3:GetObjectVersion"' in policy
    assert "plans/nova-generated/*" in policy
    assert 'Action   = ["s3:GetObject"]' in policy
    assert "plans/nova-generated/requests/????????-????-????-????-????????????/input.json" in policy
    assert 'Action = ["s3:ListBucket"]' not in policy
    assert 'Action   = ["s3:ListBucket"]' not in policy
    assert '"kms:Decrypt", "kms:GenerateDataKey"' in policy
    assert '"kms:ViaService"' in policy
    assert '"kms:EncryptionContext:aws:s3:arn"' in policy


def test_nova_build_reconciliation_is_limited_to_the_plan_project():
    terraform = (ROOT / "infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    policy = terraform.split('resource "aws_iam_role_policy" "api"', 1)[1].split(
        'resource "aws_iam_role" "customer_executor"', 1
    )[0]

    recovery = policy.split("# Recovery can inspect only", 1)[1].split("}],", 1)[0]
    assert '"codebuild:ListBuildsForProject", "codebuild:BatchGetBuilds"' in recovery
    assert '"codebuild:StartBuild"' not in recovery
    assert "var.enable_nova_plan_reviews ? [{" in policy.split(
        "# Recovery can inspect only", 1
    )[0][-100:]
    assert (
        "arn:aws:codebuild:${var.region}:${data.aws_caller_identity.current.account_id}:"
        "project/${local.name}-nova-plan-only"
    ) in recovery
    assert 'Action   = ["codebuild:ListBuildsForProject"]\n        Resource = "*"' not in policy


def test_nova_plan_storage_runtime_uses_existing_ci_bucket_and_key_with_reviews_disabled_by_default() -> (
    None
):
    terraform = (ROOT / "infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    workflow = (ROOT / ".github/workflows/terraform-plan.yml").read_text()

    assert "DAVDEPLOY_NOVA_PLAN_REVIEWS_ENABLED" in terraform
    assert "DAVDEPLOY_NOVA_PLAN_ARTIFACT_BUCKET" in terraform
    assert "DAVDEPLOY_NOVA_PLAN_KMS_KEY_ARN" in terraform
    assert "DAVDEPLOY_NOVA_PLAN_BUCKET_OWNER" in terraform
    assert "TF_VAR_nova_plan_artifact_bucket: ${{ vars.TF_PLAN_BUCKET }}" in workflow
    assert "TF_VAR_nova_plan_kms_key_arn: ${{ vars.TF_PLAN_KMS_KEY_ARN }}" in workflow
    assert "vars.NOVA_PLAN_REVIEWS_ENABLED || 'false'" in workflow
