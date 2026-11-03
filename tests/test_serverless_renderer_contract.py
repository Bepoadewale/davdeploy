from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_serverless_api_renderer_is_artifact_bound_and_has_bounded_operations():
    script = (ROOT / "scripts/customer-workload-serverless-api.sh").read_text()
    assert "DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI" in script
    assert "DAVDEPLOY_SERVERLESS_ARTIFACT_SHA256" in script
    assert "shasum -a 256 --check --status" in script
    assert "plan, apply, health, destroy, verify-cleanup" in script
    assert "terraform apply" not in script


def test_serverless_api_root_has_account_guard_and_no_unscoped_iam_policy():
    root = (ROOT / "infrastructure/terraform/customer-workload-serverless-api/main.tf").read_text()
    assert "account_guard" in root
    assert "expected_account_id" in root
    assert "AWSLambdaBasicExecutionRole" in root
    assert '"Action": "*"' not in root
