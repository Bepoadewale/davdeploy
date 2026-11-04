from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPATCHER = ROOT / "scripts/customer-workload-dispatcher.sh"


def _isolated_dispatcher(tmp_path: Path) -> tuple[Path, Path]:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    dispatcher = scripts / "customer-workload-dispatcher.sh"
    shutil.copyfile(DISPATCHER, dispatcher)
    runner = scripts / "customer-workload-app-runner-pilot.sh"
    marker = tmp_path / "invoked"
    runner.write_text(f"#!/usr/bin/env bash\nprintf '%s' \"$1\" >{marker}\n", encoding="utf-8")
    runner.chmod(0o755)
    serverless_runner = scripts / "customer-workload-serverless-api.sh"
    serverless_runner.write_text(
        f"#!/usr/bin/env bash\nprintf '%s' \"$1\" >{marker}\n", encoding="utf-8"
    )
    serverless_runner.chmod(0o755)
    storage_runner = scripts / "customer-workload-private-s3.sh"
    storage_runner.write_text(
        f"#!/usr/bin/env bash\nprintf '%s' \"$1\" >{marker}\n", encoding="utf-8"
    )
    storage_runner.chmod(0o755)
    artifact_builder = scripts / "customer-serverless-artifact-build.py"
    artifact_builder.write_text(
        f"#!/usr/bin/env python3\nfrom pathlib import Path\nPath('{marker}').write_text('build-artifact')\n",
        encoding="utf-8",
    )
    return dispatcher, marker


def _work(
    module_id: str = "aws-managed-application", operation: str = "apply"
) -> list[dict[str, object]]:
    is_serverless = module_id == "aws-serverless-api"
    terraform_root = (
        "infrastructure/terraform/customer-workload-serverless-api"
        if is_serverless
        else "infrastructure/terraform/customer-workload-app-runner-pilot"
    )
    runner_script = (
        "scripts/customer-workload-serverless-api.sh"
        if is_serverless
        else "scripts/customer-workload-app-runner-pilot.sh"
    )
    return [
        {
            "module_id": module_id,
            "instance_id": module_id,
            "operation": operation,
            "dependencies": [],
            "input_bindings": [],
            "resource_tags": {"ManagedBy": "davdeploy"},
            "renderer": {
                "terraform_root": terraform_root,
                "runner_script": runner_script,
            },
        }
    ]


def test_dispatcher_routes_only_registered_app_runner_saved_plan_work(tmp_path: Path) -> None:
    dispatcher, marker = _isolated_dispatcher(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON": json.dumps(_work()),
            "DAVDEPLOY_EXECUTION_OPERATION": "apply-saved-plan",
        }
    )
    result = subprocess.run(
        ["bash", str(dispatcher)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert marker.read_text(encoding="utf-8") == "apply-saved-plan"


def test_dispatcher_allows_the_fixed_commit_pinned_image_build(tmp_path: Path) -> None:
    dispatcher, marker = _isolated_dispatcher(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON": json.dumps(
                _work(operation="build-push-image")
            ),
            "DAVDEPLOY_EXECUTION_OPERATION": "build-push-image",
        }
    )
    result = subprocess.run(
        ["bash", str(dispatcher)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert marker.read_text(encoding="utf-8") == "build-push-image"


def test_dispatcher_rejects_unregistered_or_mixed_work_before_script(tmp_path: Path) -> None:
    dispatcher, marker = _isolated_dispatcher(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON": json.dumps(_work("aws-serverless-api")),
            "DAVDEPLOY_EXECUTION_OPERATION": "apply-saved-plan",
        }
    )
    result = subprocess.run(
        ["bash", str(dispatcher)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "certification route is disabled" in result.stderr
    assert not marker.exists()

    env["DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION"] = "true"
    result = subprocess.run(
        ["bash", str(dispatcher)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert marker.read_text(encoding="utf-8") == "apply-saved-plan"
    previous_invocation = marker.read_text(encoding="utf-8")

    env["DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON"] = json.dumps(_work() * 2)
    env.pop("DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION")
    result = subprocess.run(
        ["bash", str(dispatcher)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "one typed renderer entry" in result.stderr
    assert marker.read_text(encoding="utf-8") == previous_invocation


def test_dispatcher_rejects_unknown_fields_and_operation_mismatches(tmp_path: Path) -> None:
    dispatcher, marker = _isolated_dispatcher(tmp_path)
    work = _work()
    work[0]["command"] = "echo unsafe"
    env = os.environ.copy()
    env.update(
        {
            "DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON": json.dumps(work),
            "DAVDEPLOY_EXECUTION_OPERATION": "apply-saved-plan",
        }
    )
    result = subprocess.run(
        ["bash", str(dispatcher)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "one typed renderer entry" in result.stderr
    assert not marker.exists()

    env["DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON"] = json.dumps(_work())
    env["DAVDEPLOY_EXECUTION_OPERATION"] = "destroy-saved-plan"
    result = subprocess.run(
        ["bash", str(dispatcher)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "does not match" in result.stderr
    assert not marker.exists()


def test_dispatcher_requires_resolved_values_matching_module_input_references(
    tmp_path: Path,
) -> None:
    dispatcher, marker = _isolated_dispatcher(tmp_path)
    work = _work("aws-serverless-api", "apply")
    work[0]["dependencies"] = ["uploads"]
    work[0]["input_bindings"] = [
        {
            "input_name": "uploads_bucket_name",
            "source_instance_id": "uploads",
            "source_output": "bucket_name",
        }
    ]
    bucket_name = "davdeploy-123456789012-us-east-1-0123456789abcdef0123"
    env = os.environ.copy()
    env.update(
        {
            "DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON": json.dumps(work),
            "DAVDEPLOY_EXECUTION_OPERATION": "apply-saved-plan",
            "DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION": "true",
        }
    )
    result = subprocess.run(
        ["bash", str(dispatcher)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "Resolved inputs do not match" in result.stderr
    assert not marker.exists()

    env["DAVDEPLOY_RESOLVED_MODULE_INPUTS_JSON"] = json.dumps({"uploads_bucket_name": bucket_name})
    result = subprocess.run(
        ["bash", str(dispatcher)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert marker.read_text(encoding="utf-8") == "apply-saved-plan"

    env["DAVDEPLOY_RESOLVED_MODULE_INPUTS_JSON"] = json.dumps(
        {"uploads_bucket_name": bucket_name, "arbitrary": "value"}
    )
    result = subprocess.run(
        ["bash", str(dispatcher)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "unsupported or malformed" in result.stderr

    work[0]["input_bindings"][0]["value"] = "caller-controlled"
    env["DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON"] = json.dumps(work)
    env["DAVDEPLOY_RESOLVED_MODULE_INPUTS_JSON"] = json.dumps({"uploads_bucket_name": bucket_name})
    result = subprocess.run(
        ["bash", str(dispatcher)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "one typed renderer entry" in result.stderr


def test_dispatcher_routes_certification_lifecycle_only_to_serverless_renderer(
    tmp_path: Path,
) -> None:
    dispatcher, marker = _isolated_dispatcher(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON": json.dumps(
                _work("aws-serverless-api", "observe")
            ),
            "DAVDEPLOY_EXECUTION_OPERATION": "health",
            "DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION": "true",
        }
    )
    result = subprocess.run(
        ["bash", str(dispatcher)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert marker.read_text(encoding="utf-8") == "health"


def test_dispatcher_routes_private_storage_only_when_its_certification_gate_is_set(
    tmp_path: Path,
):
    dispatcher, marker = _isolated_dispatcher(tmp_path)
    work = _work()
    work[0].update(
        {
            "module_id": "aws-file-storage",
            "instance_id": "uploads",
            "operation": "observe",
            "renderer": {
                "terraform_root": "infrastructure/terraform/customer-workload-private-s3",
                "runner_script": "scripts/customer-workload-private-s3.sh",
            },
        }
    )
    env = os.environ.copy()
    env.update(
        {
            "DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON": json.dumps(work),
            "DAVDEPLOY_EXECUTION_OPERATION": "observe",
        }
    )
    result = subprocess.run(
        ["bash", str(dispatcher)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "Private S3 hosted certification route is disabled" in result.stderr
    assert not marker.exists()

    env["DAVDEPLOY_ENABLE_PRIVATE_S3_HOSTED_CERTIFICATION"] = "true"
    result = subprocess.run(
        ["bash", str(dispatcher)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert marker.read_text(encoding="utf-8") == "observe"

    env["DAVDEPLOY_EXECUTION_OPERATION"] = "health"
    result = subprocess.run(
        ["bash", str(dispatcher)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "does not match" in result.stderr

    env["DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON"] = json.dumps(
        _work("aws-managed-application", "observe")
    )
    result = subprocess.run(
        ["bash", str(dispatcher)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "operation does not match" in result.stderr


def test_dispatcher_enforces_exact_serverless_operation_mapping(tmp_path: Path) -> None:
    dispatcher, marker = _isolated_dispatcher(tmp_path)
    mappings = (
        ("plan", "plan"),
        ("plan", "destroy-plan"),
        ("destroy_plan", "destroy-plan"),
        ("build_artifact", "build-artifact"),
        ("apply", "apply-saved-plan"),
        ("observe", "health"),
        ("destroy", "destroy-saved-plan"),
        ("verify_cleanup", "verify-cleanup"),
    )
    env = os.environ.copy()
    env["DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION"] = "true"
    for work_operation, runner_operation in mappings:
        env["DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON"] = json.dumps(
            _work("aws-serverless-api", work_operation)
        )
        env["DAVDEPLOY_EXECUTION_OPERATION"] = runner_operation
        result = subprocess.run(
            ["bash", str(dispatcher)],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert marker.read_text(encoding="utf-8") == (
            "build-artifact" if runner_operation == "build-artifact" else runner_operation
        )

    env["DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON"] = json.dumps(
        _work("aws-serverless-api", "observe")
    )
    env["DAVDEPLOY_EXECUTION_OPERATION"] = "apply-saved-plan"
    result = subprocess.run(
        ["bash", str(dispatcher)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "operation does not match" in result.stderr


def test_codebuild_archive_contains_the_dispatcher_and_invoked_renderer():
    package_builder = (ROOT / "scripts/build_customer_executor_package.sh").read_text(
        encoding="utf-8"
    )
    buildspec = (ROOT / "infrastructure/terraform/serverless-control-plane/main.tf").read_text(
        encoding="utf-8"
    )
    assert "scripts/customer-workload-dispatcher.sh" in package_builder
    assert "scripts/customer-workload-app-runner-pilot.sh" in package_builder
    assert "infrastructure/terraform/customer-workload-serverless-api" in package_builder
    assert "scripts/customer-workload-serverless-api.sh" in package_builder
    assert "infrastructure/terraform/customer-workload-private-s3" in package_builder
    assert "scripts/customer-workload-private-s3.sh" in package_builder
    assert "scripts/customer-serverless-artifact-build.py" in package_builder
    assert "bash scripts/customer-workload-dispatcher.sh" in buildspec
