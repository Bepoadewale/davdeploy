from __future__ import annotations

import os
import hashlib
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/customer-workload-serverless-api.sh"


def test_artifact_digest_mismatch_stops_before_terraform(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    aws = bin_dir / "aws"
    aws.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "secretsmanager" ]]; then echo external-id; exit 0; fi
if [[ "$1" == "sts" && "$2" == "assume-role" ]]; then echo 'ASIA secret session'; exit 0; fi
if [[ "$1" == "sts" && "$2" == "get-caller-identity" ]]; then echo 123456789012; exit 0; fi
if [[ "$1" == "s3" && "$2" == "cp" ]]; then
  destination="${@: -2:1}"
  if [[ "$destination" == *.tfplan ]]; then
    printf 'approved-plan-bytes' >"$destination"
  else
    printf 'synthetic-lambda-package' >"$destination"
  fi
  exit 0
fi
echo "unexpected aws call: $*" >&2
exit 9
""",
        encoding="utf-8",
    )
    aws.chmod(0o755)
    terraform_log = tmp_path / "terraform-called"
    terraform = bin_dir / "terraform"
    terraform.write_text(
        f"#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >>{terraform_log}\nexit 0\n",
        encoding="utf-8",
    )
    terraform.chmod(0o755)

    env = os.environ.copy()
    env.pop("AWS_PROFILE", None)
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "HOME": str(tmp_path),
            "AWS_SHARED_CREDENTIALS_FILE": str(tmp_path / "credentials"),
            "AWS_REGION": "us-east-1",
            "EXPECTED_AWS_ACCOUNT_ID": "123456789012",
            "TF_STATE_BUCKET": "davdeploy-test-state",
            "TF_LOCK_TABLE": "davdeploy-test-locks",
            "DAVDEPLOY_CUSTOMER_CONNECTION_ID": "connection-test",
            "DAVDEPLOY_CUSTOMER_EXECUTION_ROLE_ARN": "arn:aws:iam::123456789012:role/davdeployExecution-test",
            "DAVDEPLOY_EXTERNAL_ID_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test",
            "DAVDEPLOY_EXECUTION_RUN_ID": f"digest-test-{os.getpid()}",
            "DAVDEPLOY_EXECUTION_RESULT_S3_URI": "s3://davdeploy-test-state/davdeploy/customer/connection-test/result.json",
            "DAVDEPLOY_CUSTOMER_PLAN_DIGEST": "a" * 64,
            "DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI": f"s3://davdeploy-test-state/davdeploy/customer/connection-test/{'a' * 64}/approved.tfplan",
            "DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI": "s3://davdeploy-test-state/function.zip",
            "DAVDEPLOY_SERVERLESS_ARTIFACT_SHA256": "0" * 64,
            "DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256": "0" * 64,
        }
    )
    (tmp_path / "credentials").write_text("", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(SCRIPT), "plan"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Serverless artifact digest mismatch" in result.stderr
    assert not terraform_log.exists()

    env["DAVDEPLOY_SERVERLESS_ARTIFACT_SHA256"] = hashlib.sha256(b"synthetic-lambda-package").hexdigest()
    result = subprocess.run(
        ["bash", str(SCRIPT), "apply-saved-plan"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Saved Terraform plan digest mismatch" in result.stderr
    terraform_calls = terraform_log.read_text(encoding="utf-8").splitlines()
    assert any(" init " in f" {call} " for call in terraform_calls)
    assert not any(" apply " in f" {call} " for call in terraform_calls)
