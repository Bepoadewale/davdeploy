from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "terraform-validate.sh"
EXPECTED_ROOTS = {
    "infrastructure/terraform/davdeploy-bootstrap",
    "infrastructure/terraform/bootstrap",
    "infrastructure/terraform/management-identity",
    "infrastructure/terraform/control-plane-runtime-identity",
    "infrastructure/terraform/customer-connection",
    "infrastructure/terraform/connection-template-host",
    "infrastructure/terraform/app-runner-runtime",
    "infrastructure/terraform/terraform-operations-bootstrap",
    "infrastructure/terraform/serverless-control-plane",
    "infrastructure/terraform/customer-workload-app-runner-pilot",
    "infrastructure/terraform/customer-workload-serverless-api",
    "infrastructure/terraform/renderers/app-runner-plan",
    "infrastructure/terraform/pilot",
}


def fake_terraform(tmp_path: Path) -> Path:
    executable = tmp_path / "terraform"
    executable.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "${LOG_FILE}"
if [[ -n "${TF_DATA_DIR:-}" ]]; then
  mkdir -p "${TF_DATA_DIR}"
  printf '%s\\n' "$*" > "${TF_DATA_DIR}/invocation"
fi
if [[ -n "${FAIL_MATCH:-}" && "$*" == *"${FAIL_MATCH}"* ]]; then
  exit 9
fi
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def run_validation(tmp_path: Path, *, fail_match: str | None = None) -> subprocess.CompletedProcess[str]:
    temp_root = tmp_path / "temporary"
    temp_root.mkdir()
    environment = os.environ.copy()
    environment.update(
        {
            "DAVDEPLOY_TERRAFORM_BIN": str(fake_terraform(tmp_path)),
            "TMPDIR": str(temp_root),
            "TF_PLUGIN_CACHE_DIR": str(tmp_path / "plugin-cache"),
            "LOG_FILE": str(tmp_path / "terraform.log"),
        }
    )
    if fail_match:
        environment["FAIL_MATCH"] = fail_match
    return subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_terraform_validation_cleans_temporary_data_after_success(tmp_path: Path) -> None:
    result = run_validation(tmp_path)

    assert result.returncode == 0, result.stderr
    assert list((tmp_path / "temporary").iterdir()) == []
    assert (tmp_path / "plugin-cache").is_dir()
    invocations = (tmp_path / "terraform.log").read_text(encoding="utf-8").splitlines()
    assert len(invocations) == 1 + (2 * len(EXPECTED_ROOTS))
    assert invocations[0] == "fmt -check -recursive infrastructure/terraform"
    initialized_roots = {
        invocation.split()[0].removeprefix("-chdir=")
        for invocation in invocations
        if " init " in f" {invocation} "
    }
    validated_roots = {
        invocation.split()[0].removeprefix("-chdir=")
        for invocation in invocations
        if invocation.endswith(" validate")
    }
    assert initialized_roots == EXPECTED_ROOTS
    assert validated_roots == EXPECTED_ROOTS


def test_terraform_validation_cleans_temporary_data_after_failure(tmp_path: Path) -> None:
    result = run_validation(tmp_path, fail_match="customer-connection")

    assert result.returncode == 9
    assert list((tmp_path / "temporary").iterdir()) == []
