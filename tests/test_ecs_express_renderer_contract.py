from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/customer-workload-ecs-express-pilot.sh"
TERRAFORM_ROOT = ROOT / "infrastructure/terraform/customer-workload-ecs-express-pilot"


def test_ecs_express_root_and_runner_are_project_scoped_and_artifact_bound():
    versions = (TERRAFORM_ROOT / "versions.tf").read_text()
    main = (TERRAFORM_ROOT / "main.tf").read_text()
    variables = (TERRAFORM_ROOT / "variables.tf").read_text()
    script = SCRIPT.read_text()

    assert 'backend "s3" {}' in versions
    assert 'variable "project_id"' in variables
    assert 'sha256("${var.connection_id}:${var.project_id}:${var.region}")' in main
    assert "ProjectId" in main
    assert "@sha256:[a-f0-9]{64}" in variables
    assert "DAVDEPLOY_CUSTOMER_PROJECT_ID" in script
    assert "DAVDEPLOY_CUSTOMER_IMAGE_PUBLISH_ROLE_ARN" in script
    assert 'AWS_SHARED_CREDENTIALS_FILE="$original_credentials_file" aws --profile "$platform_profile"' in script
    assert 'awk -v target=' not in script
    assert 'key=davdeploy/customer/${connection_id}/projects/${project_id}/regions/${AWS_REGION}/ecs-express.tfstate' in script
    assert 'backend-config="bucket=${customer_state_bucket}"' in script
    assert 'backend-config="profile=${customer_profile}"' in script
    assert 'backend-config="kms_key_id=${customer_state_kms_key_arn}"' in script
    assert 'backend-config="use_lockfile=true"' in script
    assert "get-bucket-versioning" in script
    assert "get-public-access-block" in script
    assert "get-bucket-ownership-controls" in script
    assert "get-bucket-encryption" in script
    assert "get-bucket-location" in script
    assert "describe-key" in script
    assert 'KeyManager == "CUSTOMER"' in script
    assert 'saved_plan_prefix="${artifact_prefix}${DAVDEPLOY_CUSTOMER_PLAN_DIGEST}/${saved_plan_kind}/"' in script
    assert "shasum -a 256 --check --status" in script
    assert 'terraform -chdir="$root" apply -input=false "$plan_file"' in script
    assert 'terraform -chdir="$root" apply -input=false -auto-approve' not in script
    assert "describe-express-gateway-service" in script
    assert "confirmed_absent" in script
    assert '"-var=customer_profile=${customer_profile}"' in script


def _runner_env(tmp_path: Path) -> tuple[dict[str, str], Path]:
    connection_id = "connection123"
    project_id = "project123"
    region = "us-east-1"
    plan_digest = "a" * 64
    run_id = "run123"
    state_bucket = "davdeploy-artifacts"
    run_root = f"davdeploy/customer/{connection_id}/projects/{project_id}"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{tmp_path / 'bin'}:{env['PATH']}",
            "AWS_REGION": region,
            "EXPECTED_AWS_ACCOUNT_ID": "654654474502",
            "DAVDEPLOY_PLAN_ARTIFACT_BUCKET": state_bucket,
            "DAVDEPLOY_CUSTOMER_STATE_BUCKET": "customer-state",
            "DAVDEPLOY_CUSTOMER_STATE_KMS_KEY_ARN": "arn:aws:kms:us-east-1:654654474502:key/12345678-1234-1234-1234-123456789012",
            "DAVDEPLOY_CUSTOMER_CONNECTION_ID": connection_id,
            "DAVDEPLOY_CUSTOMER_PROJECT_ID": project_id,
            "DAVDEPLOY_CUSTOMER_EXECUTION_ROLE_ARN": "arn:aws:iam::654654474502:role/customerExecution",
            "DAVDEPLOY_EXTERNAL_ID_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:654654474502:secret:external-id",
            "DAVDEPLOY_EXECUTION_RUN_ID": run_id,
            "DAVDEPLOY_EXECUTION_RESULT_S3_URI": f"s3://{state_bucket}/{run_root}/runs/{run_id}/result.json",
            "DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI": f"s3://{state_bucket}/{run_root}/{plan_digest}/apply/{run_id}.tfplan",
            "DAVDEPLOY_CUSTOMER_PLAN_DIGEST": plan_digest,
            "DAVDEPLOY_CUSTOMER_SOURCE_REPOSITORY": "https://github.com/Bepoadewale/davdeploy",
            "DAVDEPLOY_CUSTOMER_SOURCE_COMMIT": "b" * 40,
        }
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    aws_log = tmp_path / "aws-calls.log"
    aws = bin_dir / "aws"
    aws.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$AWS_CALL_LOG"\nexit 42\n')
    aws.chmod(0o755)
    env["AWS_CALL_LOG"] = str(aws_log)
    return env, aws_log


def test_ecs_runner_rejects_an_image_from_another_project_before_aws_calls(tmp_path):
    env, aws_log = _runner_env(tmp_path)
    env["DAVDEPLOY_CUSTOMER_IMAGE_IDENTIFIER"] = (
        "654654474502.dkr.ecr.us-east-1.amazonaws.com/other-project@sha256:" + "c" * 64
    )

    result = subprocess.run(
        ["bash", str(SCRIPT), "plan"], capture_output=True, text=True, env=env, check=False
    )

    assert result.returncode == 2
    assert "same-account, same-region digest in this project's repository" in result.stderr
    assert not aws_log.exists()


def test_ecs_runner_rejects_saved_plan_or_result_paths_outside_the_project(tmp_path):
    env, aws_log = _runner_env(tmp_path)
    env["DAVDEPLOY_EXECUTION_RESULT_S3_URI"] = "s3://davdeploy-state/other-tenant/result.json"

    result = subprocess.run(
        ["bash", str(SCRIPT), "plan"], capture_output=True, text=True, env=env, check=False
    )

    assert result.returncode == 2
    assert "Execution result must be stored in this project's run prefix" in result.stderr
    assert not aws_log.exists()


def test_ecs_runner_rejects_unknown_operations_before_aws_calls(tmp_path):
    env, aws_log = _runner_env(tmp_path)

    result = subprocess.run(
        ["bash", str(SCRIPT), "shell"], capture_output=True, text=True, env=env, check=False
    )

    assert result.returncode == 2
    assert "allowed operations" in result.stderr
    assert not aws_log.exists()


def test_ecs_runner_requires_a_dedicated_project_image_publisher_role(tmp_path):
    env, aws_log = _runner_env(tmp_path)

    result = subprocess.run(
        ["bash", str(SCRIPT), "build-artifact"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 2
    assert "DAVDEPLOY_CUSTOMER_IMAGE_PUBLISH_ROLE_ARN is required" in result.stderr
    assert not aws_log.exists()
