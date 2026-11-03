from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_serverless_api_renderer_is_artifact_bound_and_has_bounded_operations():
    script = (ROOT / "scripts/customer-workload-serverless-api.sh").read_text()
    assert "DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI" in script
    assert "DAVDEPLOY_SERVERLESS_ARTIFACT_SHA256" in script
    assert "shasum -a 256 --check --status" in script
    assert "plan|destroy-plan" in script
    assert "apply-saved-plan|destroy-saved-plan" in script
    assert 'terraform -chdir="$root" apply -input=false "$plan_file"' in script
    assert "terraform -chdir=\"$root\" apply -input=false -auto-approve" not in script
    assert "saved_plan_prefix=\"${customer_state_prefix}${DAVDEPLOY_CUSTOMER_PLAN_DIGEST}/${saved_plan_kind}/\"" in script
    assert "customer_state_prefix=\"s3://${TF_STATE_BUCKET}/davdeploy/customer/${connection_id}/\"" in script
    assert 'artifact="/tmp/davdeploy-serverless-${connection_id}-${DAVDEPLOY_CUSTOMER_PLAN_DIGEST}.zip"' in script
    assert "terraform apply" not in script


def test_serverless_api_root_has_account_guard_and_no_unscoped_iam_policy():
    root = (ROOT / "infrastructure/terraform/customer-workload-serverless-api/main.tf").read_text()
    assert "account_guard" in root
    assert "expected_account_id" in root
    assert "AWSLambdaBasicExecutionRole" in root
    assert '"Action": "*"' not in root


def test_serverless_runner_requires_live_cleanup_evidence():
    script = (ROOT / "scripts/customer-workload-serverless-api.sh").read_text()
    assert "aws lambda get-function" in script
    assert "aws apigatewayv2 get-apis" in script
    assert "aws iam get-role" in script
    assert "Could not verify Lambda cleanup" in script
