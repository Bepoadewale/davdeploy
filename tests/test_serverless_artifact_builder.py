from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/customer-serverless-artifact-build.py"
SPEC = importlib.util.spec_from_file_location("serverless_artifact_build", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
artifact_builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(artifact_builder)


def _source_tree(root: Path) -> None:
    (root / "vendor").mkdir(parents=True)
    (root / "index.py").write_text("def handler(event, context):\n    return {'statusCode': 200}\n")
    (root / "vendor" / "dependency.py").write_text("VALUE = 42\n")
    (root / "requirements.txt").write_text("untrusted-build-dependency\n")
    (root / "build.sh").write_text("touch SHOULD_NOT_RUN\n")
    (root / ".env").write_text("SHOULD_NOT_BE_PACKAGED=yes\n")


def _environment() -> dict[str, str]:
    connection_id = "connection_123"
    plan_digest = "a" * 64
    run_id = "run_123"
    prefix = f"davdeploy/customer/{connection_id}"
    return {
        "DAVDEPLOY_CUSTOMER_SOURCE_REPOSITORY": "https://github.com/example/customer-api",
        "DAVDEPLOY_CUSTOMER_SOURCE_COMMIT": "b" * 40,
        "DAVDEPLOY_CUSTOMER_CONNECTION_ID": connection_id,
        "DAVDEPLOY_CUSTOMER_PLAN_DIGEST": plan_digest,
        "DAVDEPLOY_EXECUTION_RUN_ID": run_id,
        "DAVDEPLOY_EXECUTION_OPERATION": "build-artifact",
        "DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION": "true",
        "AWS_REGION": "eu-west-1",
        "DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI": (
            f"s3://davdeploy-state/{prefix}/artifacts/{plan_digest}/{run_id}/lambda.zip"
        ),
        "DAVDEPLOY_EXECUTION_RESULT_S3_URI": (
            f"s3://davdeploy-state/{prefix}/runs/{run_id}/result.json"
        ),
    }


def test_package_source_is_deterministic_and_includes_only_entrypoint_and_vendor(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    _source_tree(source)
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"

    first_digest, _, _, first_files = artifact_builder.package_source(source, first)
    second_digest, _, _, second_files = artifact_builder.package_source(source, second)

    assert first.read_bytes() == second.read_bytes()
    assert first_digest == second_digest == hashlib.sha256(first.read_bytes()).hexdigest()
    assert first_files == second_files == ("dependency.py", "index.py")
    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == ["dependency.py", "index.py"]
        assert "untrusted-build-dependency" not in archive.read("index.py").decode()
        assert "SHOULD_NOT_BE_PACKAGED" not in " ".join(archive.namelist())


def test_package_source_rejects_missing_entrypoint_symlinks_and_entrypoint_override(tmp_path: Path):
    missing = tmp_path / "missing"
    missing.mkdir()
    with pytest.raises(ValueError, match="index.py"):
        artifact_builder.package_source(missing, tmp_path / "missing.zip")

    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "target.py").write_text("pass\n")
    (linked / "index.py").symlink_to(linked / "target.py")
    with pytest.raises(ValueError, match="regular file"):
        artifact_builder.package_source(linked, tmp_path / "linked.zip")

    collision = tmp_path / "collision"
    collision.mkdir()
    _source_tree(collision)
    (collision / "vendor" / "index.py").write_text("def handler(): pass\n")
    with pytest.raises(ValueError, match="may not replace"):
        artifact_builder.package_source(collision, tmp_path / "collision.zip")


def test_package_source_enforces_uncompressed_size_limit(monkeypatch, tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "index.py").write_text("x" * 20)
    monkeypatch.setattr(artifact_builder, "MAX_UNCOMPRESSED_BYTES", 10)
    with pytest.raises(ValueError, match="uncompressed size limit"):
        artifact_builder.package_source(source, tmp_path / "artifact.zip")


def test_artifact_environment_requires_pinned_public_repo_and_exact_scoped_s3_paths():
    context = artifact_builder.validate_environment(_environment())
    assert context["commit"] == "b" * 40

    invalid_repo = _environment()
    invalid_repo["DAVDEPLOY_CUSTOMER_SOURCE_REPOSITORY"] = "https://example.com/customer-api"
    with pytest.raises(ValueError, match="public GitHub"):
        artifact_builder.validate_environment(invalid_repo)

    unsafe_repo = _environment()
    unsafe_repo["DAVDEPLOY_CUSTOMER_SOURCE_REPOSITORY"] = "https://github.com/../customer-api"
    with pytest.raises(ValueError, match="canonical public GitHub"):
        artifact_builder.validate_environment(unsafe_repo)

    invalid_commit = _environment()
    invalid_commit["DAVDEPLOY_CUSTOMER_SOURCE_COMMIT"] = "main"
    with pytest.raises(ValueError, match="full immutable"):
        artifact_builder.validate_environment(invalid_commit)

    invalid_key = _environment()
    invalid_key["DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI"] = (
        "s3://davdeploy-state/davdeploy/customer/another-connection/artifacts/"
        + "a" * 64
        + "/run_123/lambda.zip"
    )
    with pytest.raises(ValueError, match="outside its connection"):
        artifact_builder.validate_environment(invalid_key)

    invalid_query = _environment()
    invalid_query["DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI"] += "?version=1"
    with pytest.raises(ValueError, match="S3 URI is invalid"):
        artifact_builder.validate_environment(invalid_query)

    disabled = _environment()
    disabled["DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION"] = "false"
    with pytest.raises(ValueError, match="route is disabled"):
        artifact_builder.validate_environment(disabled)


def test_run_checks_out_exact_commit_and_uploads_digest_bound_artifact_and_result(monkeypatch):
    env = _environment()
    source_content = b"def handler(event, context): return {'statusCode': 200}\n"
    uploaded: dict[str, bytes] = {}

    def fake_run(command, **kwargs):
        if command[0] == "git" and "clone" in command:
            checkout = Path(command[-1])
            checkout.mkdir()
            (checkout / "index.py").write_bytes(source_content)
            (checkout / "build.sh").write_text("exit 100\n")
            assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
            assert kwargs["env"]["GIT_CONFIG_NOSYSTEM"] == "1"
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[0] == "git" and "checkout" in command:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[0] == "git" and "rev-parse" in command:
            return subprocess.CompletedProcess(command, 0, env["DAVDEPLOY_CUSTOMER_SOURCE_COMMIT"], "")
        if command[:3] == ["aws", "s3", "cp"]:
            source = Path(command[3])
            target_uri = command[4]
            uploaded[target_uri] = source.read_bytes()
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:3] == ["aws", "s3api", "head-object"]:
            artifact_digest = hashlib.sha256(
                uploaded[env["DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI"]]
            ).hexdigest()
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps({"encryption": "aws:kms", "sha256": artifact_digest}),
                "",
            )
        raise AssertionError(f"unexpected subprocess call: {command}")

    monkeypatch.setattr(artifact_builder.subprocess, "run", fake_run)
    result = artifact_builder.run(env)

    artifact_uri = env["DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI"]
    result_uri = env["DAVDEPLOY_EXECUTION_RESULT_S3_URI"]
    with zipfile.ZipFile(BytesIO(uploaded[artifact_uri])) as archive:
        assert archive.namelist() == ["index.py"]
        assert archive.read("index.py") == source_content
    evidence = json.loads(uploaded[result_uri])
    assert evidence["phase"] == "artifact-build"
    assert evidence["status"] == "SUCCEEDED"
    assert evidence["detail"]["source_commit"] == env["DAVDEPLOY_CUSTOMER_SOURCE_COMMIT"]
    assert evidence["detail"]["artifact_sha256"] == hashlib.sha256(uploaded[artifact_uri]).hexdigest()
    assert result["artifact_key"].endswith("/lambda.zip")
