#!/usr/bin/env python3
"""Create a deterministic Lambda ZIP from a pinned, public repository commit.

This script never executes customer build commands. Its input contract is a
root ``index.py`` file and optional regular files under ``vendor/``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

MAX_FILES = 10_000
MAX_UNCOMPRESSED_BYTES = 240 * 1024 * 1024
MAX_COMPRESSED_BYTES = 49 * 1024 * 1024
REPOSITORY_COMPONENT_RE = re.compile(r"[A-Za-z0-9_.-]+\Z")
CONNECTION_RE = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
PROJECT_RE = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
RUN_RE = re.compile(r"[A-Za-z0-9_-]{1,80}\Z")
SHA256_RE = re.compile(r"[a-f0-9]{64}\Z")
COMMIT_RE = re.compile(r"[a-f0-9]{40}\Z")


def required(environment: dict[str, str], name: str) -> str:
    value = environment.get(name, "")
    if not value:
        raise ValueError(f"{name} is required")
    return value


def s3_bucket_key(uri: str) -> tuple[str, str]:
    parsed = urlsplit(uri)
    if (
        parsed.scheme != "s3"
        or not parsed.netloc
        or not parsed.path.startswith("/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("S3 URI is invalid")
    bucket, key = parsed.netloc, parsed.path[1:]
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket) or not key:
        raise ValueError("S3 URI is invalid")
    return bucket, key


def validate_repository_url(repository: str) -> None:
    parsed = urlsplit(repository)
    components = parsed.path.removeprefix("/").split("/")
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or parsed.query
        or parsed.fragment
        or len(components) != 2
        or any(component in {"", ".", ".."} for component in components)
        or not all(REPOSITORY_COMPONENT_RE.fullmatch(component) for component in components)
    ):
        raise ValueError("Source repository must be a canonical public GitHub HTTPS URL")


def validate_environment(environment: dict[str, str]) -> dict[str, str]:
    repository = required(environment, "DAVDEPLOY_CUSTOMER_SOURCE_REPOSITORY")
    commit = required(environment, "DAVDEPLOY_CUSTOMER_SOURCE_COMMIT").lower()
    connection_id = required(environment, "DAVDEPLOY_CUSTOMER_CONNECTION_ID")
    project_id = required(environment, "DAVDEPLOY_CUSTOMER_PROJECT_ID")
    plan_digest = required(environment, "DAVDEPLOY_CUSTOMER_PLAN_DIGEST").lower()
    run_id = required(environment, "DAVDEPLOY_EXECUTION_RUN_ID")
    region = required(environment, "AWS_REGION")
    artifact_uri = required(environment, "DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI")
    result_uri = required(environment, "DAVDEPLOY_EXECUTION_RESULT_S3_URI")

    if environment.get("DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION") != "true":
        raise ValueError("Serverless API hosted certification route is disabled")
    if environment.get("DAVDEPLOY_EXECUTION_OPERATION") != "build-artifact":
        raise ValueError("Serverless artifact builder requires the typed build-artifact operation")
    validate_repository_url(repository)
    if not COMMIT_RE.fullmatch(commit):
        raise ValueError("Source commit must be a full immutable Git commit SHA")
    if not CONNECTION_RE.fullmatch(connection_id):
        raise ValueError("Customer connection identifier is invalid")
    if not PROJECT_RE.fullmatch(project_id):
        raise ValueError("Customer project identifier is invalid")
    if not SHA256_RE.fullmatch(plan_digest):
        raise ValueError("Customer plan digest must be a SHA-256 digest")
    if not RUN_RE.fullmatch(run_id):
        raise ValueError("Execution run identifier is invalid")
    if not re.fullmatch(r"[a-z]{2}(?:-gov|-cn)?-[a-z]+-[0-9]+", region):
        raise ValueError("AWS region is invalid")

    artifact_bucket, artifact_key = s3_bucket_key(artifact_uri)
    result_bucket, result_key = s3_bucket_key(result_uri)
    scope = f"davdeploy/customer/{connection_id}/projects/{project_id}/"
    expected_artifact_key = f"{scope}artifacts/{plan_digest}/{run_id}/lambda.zip"
    expected_result_key = f"{scope}runs/{run_id}/result.json"
    if artifact_bucket != result_bucket or artifact_key != expected_artifact_key:
        raise ValueError("Lambda artifact URI is outside its connection, project, plan, and run scope")
    if result_key != expected_result_key:
        raise ValueError("Execution result URI is outside its connection, project, and run scope")
    return {
        "repository": repository,
        "commit": commit,
        "connection_id": connection_id,
        "project_id": project_id,
        "plan_digest": plan_digest,
        "run_id": run_id,
        "region": region,
        "artifact_uri": artifact_uri,
        "result_uri": result_uri,
        "bucket": artifact_bucket,
    }


def _source_files(source: Path) -> list[tuple[Path, str]]:
    entrypoint = source / "index.py"
    try:
        entrypoint_mode = entrypoint.lstat().st_mode
    except FileNotFoundError as error:
        raise ValueError("Pinned repository must contain a regular root index.py entrypoint") from error
    if not stat.S_ISREG(entrypoint_mode):
        raise ValueError("Lambda index.py entrypoint must be a regular file, not a link")

    files: list[tuple[Path, str]] = [(entrypoint, "index.py")]
    vendor_root = source / "vendor"
    if vendor_root.exists() or vendor_root.is_symlink():
        if vendor_root.is_symlink() or not vendor_root.is_dir():
            raise ValueError("vendor must be a regular directory")
        for path in sorted(vendor_root.rglob("*")):
            mode = path.lstat().st_mode
            if stat.S_ISDIR(mode):
                continue
            if not stat.S_ISREG(mode):
                raise ValueError("vendor may contain regular files and directories only")
            relative = path.relative_to(vendor_root).as_posix()
            pure_path = PurePosixPath(relative)
            if (
                "\\" in relative
                or pure_path.is_absolute()
                or any(part in {"", ".", ".."} for part in pure_path.parts)
            ):
                raise ValueError("vendor contains an unsafe archive path")
            if relative == "index.py":
                raise ValueError("vendor may not replace the Lambda index.py entrypoint")
            files.append((path, relative))

    if len(files) > MAX_FILES:
        raise ValueError("Lambda source artifact contains too many files")
    total_bytes = sum(path.stat().st_size for path, _ in files)
    if total_bytes > MAX_UNCOMPRESSED_BYTES:
        raise ValueError("Lambda source artifact exceeds the uncompressed size limit")
    return files


def package_source(source: Path, output: Path) -> tuple[str, int, int, tuple[str, ...]]:
    """Write a deterministic archive of only the approved source paths."""
    files = _source_files(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source_path, archive_path in sorted(files, key=lambda item: item[1]):
            info = zipfile.ZipInfo(archive_path, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, source_path.read_bytes())
    archive_size = output.stat().st_size
    if archive_size > MAX_COMPRESSED_BYTES:
        raise ValueError("Lambda source artifact exceeds the compressed size limit")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return digest, archive_size, sum(path.stat().st_size for path, _ in files), tuple(
        archive_path for _, archive_path in sorted(files, key=lambda item: item[1])
    )


def run(environment: dict[str, str] | None = None) -> dict[str, object]:
    env = dict(os.environ if environment is None else environment)
    context = validate_environment(env)
    with tempfile.TemporaryDirectory(prefix="davdeploy-lambda-source-") as temporary:
        root = Path(temporary)
        checkout = root / "source"
        git_template = root / "git-template"
        git_template.mkdir()
        archive = root / "lambda.zip"
        git_environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(root),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
        subprocess.run(
            [
                "git",
                "-c",
                "credential.helper=",
                "-c",
                "core.hooksPath=/dev/null",
                "clone",
                "--template",
                str(git_template),
                "--filter=blob:none",
                "--no-checkout",
                context["repository"],
                str(checkout),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
            env=git_environment,
        )
        subprocess.run(
            [
                "git",
                "-c",
                "credential.helper=",
                "-c",
                "core.hooksPath=/dev/null",
                "-C",
                str(checkout),
                "checkout",
                "--detach",
                context["commit"],
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
            env=git_environment,
        )
        checked_out_commit = subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
            env=git_environment,
        ).stdout.strip().lower()
        if checked_out_commit != context["commit"]:
            raise ValueError("Checked out source commit does not match the approved commit")
        digest, archive_size, source_size, files = package_source(checkout, archive)
        artifact_bucket, artifact_key = s3_bucket_key(context["artifact_uri"])
        subprocess.run(
            [
                "aws",
                "s3",
                "cp",
                str(archive),
                context["artifact_uri"],
                "--region",
                context["region"],
                "--metadata",
                f"sha256={digest}",
                "--only-show-errors",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        object_metadata = subprocess.run(
            [
                "aws",
                "s3api",
                "head-object",
                "--bucket",
                artifact_bucket,
                "--key",
                artifact_key,
                "--region",
                context["region"],
                "--query",
                "{encryption:ServerSideEncryption,sha256:Metadata.sha256}",
                "--output",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        verified_metadata = json.loads(object_metadata.stdout)
        if verified_metadata.get("encryption") not in {"AES256", "aws:kms", "aws:kms:dsse"}:
            raise ValueError("Lambda source artifact is not encrypted at rest")
        if verified_metadata.get("sha256") != digest:
            raise ValueError("Uploaded Lambda source artifact digest metadata does not match")
        detail = {
            "artifact_s3_uri": context["artifact_uri"],
            "artifact_sha256": digest,
            "artifact_size_bytes": archive_size,
            "source_size_bytes": source_size,
            "source_repository": context["repository"],
            "source_commit": checked_out_commit,
            "handler": "index.handler",
            "runtime": "python3.12",
            "files": list(files),
        }
        result = {
            "schema_version": "davdeploy.customer_execution_result.v1",
            "run_id": context["run_id"],
            "phase": "artifact-build",
            "status": "SUCCEEDED",
            "connection_id": context["connection_id"],
            "project_id": context["project_id"],
            "plan_digest": context["plan_digest"],
            "generated_at": datetime.now(UTC).isoformat(),
            "detail": detail,
        }
        result_file = root / "result.json"
        result_file.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        subprocess.run(
            [
                "aws",
                "s3",
                "cp",
                str(result_file),
                context["result_uri"],
                "--region",
                context["region"],
                "--only-show-errors",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {"bucket": artifact_bucket, "artifact_key": artifact_key, "result": result}


def main() -> int:
    try:
        run()
    except (OSError, ValueError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        print(f"Serverless artifact build failed: {error}", file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
