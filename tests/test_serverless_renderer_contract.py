import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_serverless_api_renderer_is_artifact_bound_and_has_bounded_operations():
    script = (ROOT / "scripts/customer-workload-serverless-api.sh").read_text()
    assert "DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI" in script
    assert "DAVDEPLOY_CUSTOMER_PROJECT_ID" in script
    assert 'project_id="$DAVDEPLOY_CUSTOMER_PROJECT_ID"' in script
    assert 'project_scope="${connection_id}:${project_id}"' in script
    assert 'service_name="davdeploy-${project_suffix}-api"' in script
    assert "DAVDEPLOY_SERVERLESS_ARTIFACT_SHA256" in script
    assert "shasum -a 256 --check --status" in script
    assert "plan|destroy-plan" in script
    assert "apply-saved-plan|destroy-saved-plan" in script
    assert 'terraform -chdir="$root" apply -input=false "$plan_file"' in script
    assert 'terraform -chdir="$root" apply -input=false -auto-approve' not in script
    assert (
        'saved_plan_prefix="${customer_state_prefix}${DAVDEPLOY_CUSTOMER_PLAN_DIGEST}/${saved_plan_kind}/"'
        in script
    )
    assert (
        'customer_state_prefix="s3://${TF_STATE_BUCKET}/davdeploy/customer/${connection_id}/projects/${project_id}/"'
        in script
    )
    assert (
        '-backend-config="key=davdeploy/customer/${connection_id}/projects/${project_id}/serverless-api.tfstate"'
        in script
    )
    assert (
        'artifact="/tmp/davdeploy-serverless-${connection_id}-${DAVDEPLOY_CUSTOMER_PLAN_DIGEST}.zip"'
        in script
    )
    assert "terraform apply" not in script


def test_serverless_api_root_has_account_guard_and_no_unscoped_iam_policy():
    root = (ROOT / "infrastructure/terraform/customer-workload-serverless-api/main.tf").read_text()
    assert "account_guard" in root
    assert "expected_account_id" in root
    assert "AWSLambdaBasicExecutionRole" in root
    assert "DavDeployProject    = var.project_id" in root
    assert (
        'variable "project_id" { type = string }'
        in (
            ROOT / "infrastructure/terraform/customer-workload-serverless-api/variables.tf"
        ).read_text()
    )
    assert '"Action": "*"' not in root


def test_serverless_runner_requires_live_cleanup_evidence():
    script = (ROOT / "scripts/customer-workload-serverless-api.sh").read_text()
    assert "aws lambda get-function" in script
    assert "aws apigatewayv2 get-apis" in script
    assert "aws iam get-role" in script
    assert "Could not verify Lambda cleanup" in script


def test_serverless_renderer_accepts_only_its_project_scoped_storage_and_database_inputs():
    root = ROOT / "infrastructure/terraform/customer-workload-serverless-api"
    main = (root / "main.tf").read_text()
    variables = (root / "variables.tf").read_text()
    script = (ROOT / "scripts/customer-workload-serverless-api.sh").read_text()
    lambda_module = (ROOT / "infrastructure/terraform/modules/lambda-service/main.tf").read_text()

    assert 'variable "uploads_bucket_name"' in variables
    assert 'variable "table_name"' in variables
    assert "UPLOADS_BUCKET_NAME = var.uploads_bucket_name" in main
    assert "DYNAMODB_TABLE_NAME = var.table_name" in main
    assert 'actions   = ["s3:ListBucket"]' in main
    assert '"s3:GetObject", "s3:PutObject", "s3:DeleteObject"' in main
    assert 'resources = ["arn:aws:s3:::${var.uploads_bucket_name}/*"]' in main
    assert '"dynamodb:DeleteItem", "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query", "dynamodb:UpdateItem"' in main
    assert 'resources = ["arn:${data.aws_partition.current.partition}:dynamodb:${var.region}:${var.expected_account_id}:table/${var.table_name}"]' in main
    assert '"dynamodb:Scan"' not in main
    assert "environment = local.lambda_environment" in main
    assert 'dynamic "environment"' in lambda_module
    assert "DAVDEPLOY_RESOLVED_MODULE_INPUTS_JSON" in script
    assert "expected_uploads_bucket" in script
    assert "does not match this account, project and region" in script
    assert '"-var=uploads_bucket_name=${uploads_bucket_name}"' in script
    assert '"-var=table_name=${table_name}"' in script


def test_serverless_runner_rejects_mismatched_or_extra_typed_inputs_before_aws_calls(tmp_path):
    script = ROOT / "scripts/customer-workload-serverless-api.sh"
    connection_id = "connection123"
    project_id = "project123"
    region = "us-east-1"
    digest = "a" * 64
    suffix = hashlib.sha256(f"{connection_id}:{project_id}:{region}".encode()).hexdigest()[:20]
    expected_bucket = f"davdeploy-654654474502-{region}-{suffix}"
    expected_table = f"davdeploy-654654474502-{region}-{suffix}"
    environment = os.environ.copy()
    environment.update(
        {
            "AWS_REGION": region,
            "EXPECTED_AWS_ACCOUNT_ID": "654654474502",
            "TF_STATE_BUCKET": "davdeploy-state",
            "TF_LOCK_TABLE": "davdeploy-locks",
            "DAVDEPLOY_CUSTOMER_CONNECTION_ID": connection_id,
            "DAVDEPLOY_CUSTOMER_PROJECT_ID": project_id,
            "DAVDEPLOY_CUSTOMER_EXECUTION_ROLE_ARN": "arn:aws:iam::654654474502:role/customerExecution",
            "DAVDEPLOY_EXTERNAL_ID_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:654654474502:secret:external-id",
            "DAVDEPLOY_EXECUTION_RUN_ID": "run123",
            "DAVDEPLOY_EXECUTION_RESULT_S3_URI": f"s3://davdeploy-state/davdeploy/customer/{connection_id}/projects/{project_id}/runs/run123/result.json",
            "DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI": f"s3://davdeploy-state/davdeploy/customer/{connection_id}/projects/{project_id}/{digest}/apply/run123.tfplan",
            "DAVDEPLOY_CUSTOMER_PLAN_DIGEST": digest,
            "DAVDEPLOY_RESOLVED_MODULE_INPUTS_JSON": json.dumps(
                {"uploads_bucket_name": "another-project-bucket"}
            ),
        }
    )

    result = subprocess.run(
        ["bash", str(script), "plan"], capture_output=True, text=True, env=environment, check=False
    )
    assert result.returncode == 2
    assert "does not match this account, project and region" in result.stderr
    assert "another-project-bucket" not in result.stderr

    environment["DAVDEPLOY_RESOLVED_MODULE_INPUTS_JSON"] = json.dumps(
        {"table_name": "another-project-table"}
    )
    result = subprocess.run(
        ["bash", str(script), "plan"], capture_output=True, text=True, env=environment, check=False
    )
    assert result.returncode == 2
    assert "DynamoDB table reference does not match this account, project and region" in result.stderr

    environment["DAVDEPLOY_RESOLVED_MODULE_INPUTS_JSON"] = json.dumps(
        {"uploads_bucket_name": expected_bucket, "table_name": expected_table, "extra": "value"}
    )
    result = subprocess.run(
        ["bash", str(script), "plan"], capture_output=True, text=True, env=environment, check=False
    )
    assert result.returncode == 2
    assert "unsupported or malformed values" in result.stderr

    aws_stub = tmp_path / "aws-stub"
    aws_stub.mkdir()
    aws_path = aws_stub / "aws"
    aws_path.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$AWS_CALL_LOG\"\nexit 42\n")
    aws_path.chmod(0o755)
    call_log = tmp_path / "aws-calls.log"
    environment["PATH"] = f"{aws_stub}:{environment['PATH']}"
    environment["AWS_CALL_LOG"] = str(call_log)
    environment["DAVDEPLOY_RESOLVED_MODULE_INPUTS_JSON"] = json.dumps(
        {"uploads_bucket_name": expected_bucket, "table_name": expected_table}
    )
    result = subprocess.run(
        ["bash", str(script), "plan"], capture_output=True, text=True, env=environment, check=False
    )
    assert result.returncode == 42
    assert "secretsmanager get-secret-value" in call_log.read_text()
