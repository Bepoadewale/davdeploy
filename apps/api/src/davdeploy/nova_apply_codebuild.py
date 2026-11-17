"""Fixed CodeBuild entrypoint for exact approved Nova saved-plan apply."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from davdeploy.generated_terraform_plan import (
    PINNED_AWS_PROVIDER_VERSION,
    PINNED_TERRAFORM_VERSION,
)
from davdeploy.nova_apply_clients import (
    NovaApplyApiError,
    NovaApplyRoleCredentials,
    request_nova_apply_credentials,
    request_nova_apply_input,
)
from davdeploy.nova_apply_contract import (
    NovaApplyContractError,
    NovaApplyRequest,
    validate_nova_apply_request,
)
from davdeploy.nova_apply_workspace import (
    NovaApplyWorkspaceError,
    prepare_nova_apply_workspace,
)
from davdeploy.nova_terraform_state_client import (
    TerraformHTTPBackend,
    TerraformStateBootstrapError,
    request_terraform_http_backend,
)

RUN_ID_ENV = "DAVDEPLOY_NOVA_APPLY_RUN_ID"
MAX_RESULT_BYTES = 64 * 1024
APPLY_TIMEOUT_SECONDS = 720


class NovaApplyBuildError(RuntimeError):
    """The fixed apply pipeline failed closed or needs outcome reconciliation."""

    def __init__(self, message: str, *, outcome_uncertain: bool = False):
        super().__init__(message)
        self.outcome_uncertain = outcome_uncertain


def run_nova_apply_build(
    run_id: str,
    *,
    environment: dict[str, str] | None = None,
    s3_client: Any | None = None,
    input_requester: Callable[..., NovaApplyRequest] | None = None,
    state_bootstrapper: Callable[..., TerraformHTTPBackend] | None = None,
    credential_requester: Callable[..., NovaApplyRoleCredentials] | None = None,
    terraform_runner: Callable[..., subprocess.CompletedProcess] | None = None,
    workspace_root: str | Path | None = None,
    command_timeout_seconds: int = APPLY_TIMEOUT_SECONDS,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, Any]:
    """Restore the exact approved workspace and apply only its saved plan."""
    env = dict(os.environ if environment is None else environment)
    run_id = _canonical_run_id(run_id)
    if env.get(RUN_ID_ENV) != run_id:
        raise NovaApplyBuildError("durable apply ID does not match CodeBuild environment")
    build_id = _required_value(env.get("CODEBUILD_BUILD_ID"), "CodeBuild build ID")
    project_name = _required_project(env.get("DAVDEPLOY_NOVA_APPLY_PROJECT_NAME"))
    build_arn = _required_build_arn(env.get("CODEBUILD_BUILD_ARN"), project_name, build_id)
    if not build_id.startswith(f"{project_name}:"):
        raise NovaApplyBuildError("CodeBuild build ID does not match the fixed project")
    bucket = _required_bucket(env.get("DAVDEPLOY_NOVA_APPLY_ARTIFACT_BUCKET"))
    owner = _required_account(env.get("DAVDEPLOY_NOVA_APPLY_BUCKET_OWNER"))
    kms_key = _required_kms_key(env.get("DAVDEPLOY_NOVA_APPLY_KMS_KEY_ARN"))
    input_url = _required_api_url(env.get("DAVDEPLOY_NOVA_APPLY_INPUT_URL"), "/api/v1/nova-apply/input")
    credential_url = _required_api_url(
        env.get("DAVDEPLOY_NOVA_APPLY_CREDENTIAL_BROKER_URL"),
        "/api/v1/nova-apply/credentials",
    )
    region = env.get("AWS_DEFAULT_REGION") or env.get("AWS_REGION")
    if not isinstance(region, str) or not re.fullmatch(r"[a-z]{2}(?:-[a-z0-9]+)+-\d", region):
        raise NovaApplyBuildError("trusted CodeBuild region is invalid")
    if command_timeout_seconds < 60 or command_timeout_seconds > APPLY_TIMEOUT_SECONDS:
        raise NovaApplyBuildError("Terraform apply timeout is outside the fixed bound")
    if any(key.startswith("AWS_ENDPOINT_URL") for key in env):
        raise NovaApplyBuildError("custom AWS endpoints are not allowed for exact apply")
    if env.get("DAVDEPLOY_TERRAFORM_STATE_ENABLED", "false").lower() != "true":
        raise NovaApplyBuildError("tenant-scoped Terraform state is not enabled")
    bootstrap_url = _required_api_url(
        env.get("DAVDEPLOY_TERRAFORM_STATE_BOOTSTRAP_URL"),
        "/api/v1/terraform-state/credentials",
    )
    state_api_url = env.get("DAVDEPLOY_TERRAFORM_STATE_API_URL", "").strip()
    if not _valid_https_origin(state_api_url):
        raise NovaApplyBuildError("trusted Terraform state API is not configured")

    # Capture CodeBuild credentials and create the artifact client before the
    # customer role credentials are requested. Artifact reads use only the
    # current build's staged prefix.
    base_credentials = boto3.Session().get_credentials()
    if base_credentials is None:
        raise NovaApplyBuildError("CodeBuild service-role credentials are unavailable")
    s3 = s3_client or boto3.client("s3", region_name=region)
    input_fetch = input_requester or request_nova_apply_input
    try:
        request = input_fetch(
            input_url=input_url,
            run_id=run_id,
            codebuild_project=project_name,
            codebuild_build_arn=build_arn,
            artifact_bucket=bucket,
            credentials=base_credentials,
        )
        if not isinstance(request, NovaApplyRequest):
            raise NovaApplyBuildError("apply input did not produce a validated contract")
    except NovaApplyBuildError:
        raise
    except (NovaApplyApiError, BotoCoreError, ClientError, OSError, TypeError, ValueError):
        raise NovaApplyBuildError("exact approved apply input could not be retrieved") from None
    _revalidate_request(request, run_id, project_name, build_arn, bucket, clock())

    root = Path(workspace_root) if workspace_root else Path(tempfile.gettempdir())
    workspace_path = root / f"davdeploy-nova-apply-{run_id}"
    try:
        prepared = prepare_nova_apply_workspace(
            request,
            s3_client=s3,
            expected_bucket_owner=owner,
            expected_kms_key_arn=kms_key,
            workspace_root=workspace_path,
            expected_terraform_version=PINNED_TERRAFORM_VERSION,
            expected_aws_provider_version=PINNED_AWS_PROVIDER_VERSION,
        )
    except (NovaApplyWorkspaceError, OSError, TypeError, ValueError):
        raise NovaApplyBuildError("exact approved plan workspace could not be restored") from None

    try:
        _revalidate_request(request, run_id, project_name, build_arn, bucket, clock())
        backend = (state_bootstrapper or request_terraform_http_backend)(
            bootstrap_url=bootstrap_url,
            state_api_url=state_api_url,
            durable_run_id=run_id,
            region=request.region,
            credentials=base_credentials,
        )
    except (
        NovaApplyBuildError,
        TerraformStateBootstrapError,
        BotoCoreError,
        ClientError,
        OSError,
        TypeError,
        ValueError,
    ):
        raise NovaApplyBuildError("tenant-scoped Terraform state authorization failed") from None
    expected_state = request.manifest.get("remote_state")
    if (
        not isinstance(expected_state, dict)
        or backend.state_id != expected_state.get("state_id")
        or backend.scope_sha256 != expected_state.get("scope_sha256")
    ):
        raise NovaApplyBuildError("state service returned a different tenant state")

    terraform_binary = _trusted_terraform_binary()
    runner = terraform_runner or _run_terraform
    init_environment = _terraform_environment(env, backend, credentials=None, region=request.region)
    try:
        version_result = runner(
            terraform_binary,
            ["version", "-json"],
            cwd=prepared.root,
            env=init_environment,
            timeout=60,
        )
        if (
            version_result.returncode != 0
            or _terraform_version(version_result.stdout) != PINNED_TERRAFORM_VERSION
        ):
            raise NovaApplyBuildError("Terraform CLI does not match the approved toolchain")
        init_result = runner(
            terraform_binary,
            ["init", "-reconfigure", "-input=false", "-lockfile=readonly", "-no-color"],
            cwd=prepared.root,
            env=init_environment,
            timeout=min(command_timeout_seconds, 300),
        )
    except NovaApplyBuildError:
        raise
    except (OSError, subprocess.TimeoutExpired, TypeError, ValueError):
        raise NovaApplyBuildError("Terraform backend initialization failed") from None
    if init_result.returncode != 0:
        raise NovaApplyBuildError("Terraform backend initialization failed")

    _revalidate_request(request, run_id, project_name, build_arn, bucket, clock())
    credential_fetch = credential_requester or request_nova_apply_credentials
    apply_access = request.manifest.get("customer_apply_access")
    if not isinstance(apply_access, dict):
        raise NovaApplyBuildError("approved-plan apply permission scope is unavailable")
    try:
        customer_credentials = credential_fetch(
            broker_url=credential_url,
            run_id=run_id,
            expected_account_id=request.target_account_id,
            expected_region=request.region,
            expected_policy_version=apply_access.get("version"),
            expected_policy_sha256=apply_access.get("session_policy_sha256"),
            credentials=base_credentials,
        )
        if (
            customer_credentials.policy_version != apply_access.get("version")
            or customer_credentials.policy_sha256
            != apply_access.get("session_policy_sha256")
        ):
            raise NovaApplyBuildError("credential broker apply permission scope did not match")
        _verify_customer_identity(customer_credentials, request, run_id)
        _require_execution_credentials_lifetime(
            customer_credentials.expires_at,
            backend.expires_at,
            now=clock(),
            apply_timeout_seconds=command_timeout_seconds,
        )
    except NovaApplyBuildError:
        raise
    except (NovaApplyApiError, BotoCoreError, ClientError, OSError, TypeError, ValueError, AttributeError):
        raise NovaApplyBuildError("approved customer execution role could not be verified") from None

    apply_environment = _terraform_environment(
        env,
        backend,
        credentials=customer_credentials.boto3_credentials(),
        region=request.region,
    )
    started_at = clock().astimezone(UTC)
    try:
        result = runner(
            terraform_binary,
            ["apply", "-input=false", "-no-color", str(prepared.saved_plan_path)],
            cwd=prepared.root,
            env=apply_environment,
            timeout=command_timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired, TypeError, ValueError):
        raise NovaApplyBuildError(
            "saved-plan apply outcome requires reconciliation", outcome_uncertain=True
        ) from None
    finished_at = clock().astimezone(UTC)
    if result.returncode != 0:
        raise NovaApplyBuildError(
            "saved-plan apply outcome requires reconciliation", outcome_uncertain=True
        )

    result_document = _result_document(
        request,
        project_name=project_name,
        build_arn=build_arn,
        execution_status="APPLIED_UNVERIFIED",
        started_at=started_at,
        finished_at=finished_at,
        terraform_version=prepared.terraform_version,
        provider_version=prepared.aws_provider_version,
    )
    _put_result(
        s3,
        result_document,
        bucket=bucket,
        key=_result_key(build_arn),
        expected_bucket_owner=owner,
        kms_key_arn=kms_key,
    )
    return result_document


def _revalidate_request(
    request: NovaApplyRequest,
    run_id: str,
    project_name: str,
    build_arn: str,
    bucket: str,
    now: datetime,
) -> None:
    try:
        validate_nova_apply_request(
            request.model_dump(mode="json"),
            expected_run_id=run_id,
            expected_codebuild_project=project_name,
            expected_codebuild_build_arn=build_arn,
            expected_artifact_bucket=bucket,
            now=now,
            require_staged_artifacts=True,
        )
    except NovaApplyContractError:
        raise NovaApplyBuildError("apply authorization expired or changed") from None


def _verify_customer_identity(
    credentials: NovaApplyRoleCredentials,
    request: NovaApplyRequest,
    run_id: str,
) -> None:
    role_name = credentials.role_arn.rsplit("/", 1)[-1]
    expected_session = f"davdeploy-nova-apply-{run_id}"
    session = boto3.Session(
        aws_access_key_id=credentials.access_key_id,
        aws_secret_access_key=credentials.secret_access_key,
        aws_session_token=credentials.session_token,
        region_name=request.region,
    )
    identity = session.client("sts").get_caller_identity()
    expected_arn = (
        f"arn:aws:sts::{request.target_account_id}:assumed-role/"
        f"{role_name}/{expected_session}"
    )
    if (
        credentials.account_id != request.target_account_id
        or not role_name.startswith("davdeployNovaApply-")
        or not isinstance(identity, dict)
        or identity.get("Account") != request.target_account_id
        or identity.get("Arn") != expected_arn
    ):
        raise NovaApplyBuildError("customer execution role identity does not match the approved target")


def _require_execution_credentials_lifetime(
    customer_expires_at: datetime,
    state_expires_at: datetime,
    *,
    now: datetime,
    apply_timeout_seconds: int,
) -> None:
    """Do not start a mutation unless both credentials cover its full bound."""
    try:
        cutoff = now.astimezone(UTC) + timedelta(seconds=apply_timeout_seconds + 30)
        if (
            customer_expires_at.tzinfo is None
            or state_expires_at.tzinfo is None
            or customer_expires_at.astimezone(UTC) < cutoff
            or state_expires_at.astimezone(UTC) < cutoff
        ):
            raise ValueError
    except (AttributeError, OverflowError, TypeError, ValueError):
        raise NovaApplyBuildError(
            "apply credentials do not remain valid for the bounded execution window"
        ) from None


def _terraform_environment(
    source: dict[str, str],
    backend: TerraformHTTPBackend,
    *,
    credentials: dict[str, str] | None,
    region: str,
) -> dict[str, str]:
    env = dict(source)
    for key in tuple(env):
        if key.startswith("TF_CLI_ARGS") or key in {
            "TF_CLI_CONFIG_FILE",
            "TF_WORKSPACE",
            "AWS_PROFILE",
            "AWS_SHARED_CREDENTIALS_FILE",
            "AWS_CONFIG_FILE",
            "AWS_ROLE_ARN",
            "AWS_WEB_IDENTITY_TOKEN_FILE",
        }:
            env.pop(key, None)
    for key in ("AWS_SHARED_CREDENTIALS_FILE", "AWS_CONFIG_FILE"):
        env[key] = os.devnull
    env.update(backend.environment())
    env["AWS_REGION"] = region
    env["AWS_DEFAULT_REGION"] = region
    env["TF_IN_AUTOMATION"] = "1"
    env["TF_INPUT"] = "0"
    env["TF_LOG"] = "OFF"
    if credentials is not None:
        env["AWS_ACCESS_KEY_ID"] = credentials["AccessKeyId"]
        env["AWS_SECRET_ACCESS_KEY"] = credentials["SecretAccessKey"]
        env["AWS_SESSION_TOKEN"] = credentials["SessionToken"]
    return env


def _run_terraform(
    binary: str,
    arguments: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [binary, *arguments],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _terraform_version(raw: str) -> str | None:
    try:
        version = json.loads(raw).get("terraform_version")
    except (AttributeError, json.JSONDecodeError, TypeError):
        return None
    return version if isinstance(version, str) else None


def _result_document(
    request: NovaApplyRequest,
    *,
    project_name: str,
    build_arn: str,
    execution_status: str,
    started_at: datetime,
    finished_at: datetime,
    terraform_version: str,
    provider_version: str,
) -> dict[str, Any]:
    return {
        "contract": "davdeploy.nova-apply-result.v1",
        "run_id": request.run_id,
        "codebuild_project": project_name,
        "codebuild_build_id": build_arn.rsplit("/", 1)[-1],
        "codebuild_build_arn": build_arn,
        "source_plan_run_id": request.tenant.source_plan_run_id,
        "manifest_sha256": request.manifest_sha256,
        "saved_plan_sha256": request.saved_plan.sha256,
        "execution_workspace_sha256": request.execution_workspace.sha256,
        "state_id": request.manifest["remote_state"]["state_id"],
        "state_scope_sha256": request.manifest["remote_state"]["scope_sha256"],
        "account_id": request.target_account_id,
        "region": request.region,
        "execution_status": execution_status,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "terraform_version": terraform_version,
        "aws_provider_version": provider_version,
    }


def _put_result(
    s3_client: Any,
    document: dict[str, Any],
    *,
    bucket: str,
    key: str,
    expected_bucket_owner: str,
    kms_key_arn: str,
) -> None:
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_RESULT_BYTES:
        raise NovaApplyBuildError("safe apply result exceeds its size limit", outcome_uncertain=True)
    checksum = hashlib.sha256(raw).digest()
    try:
        response = s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=raw,
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=kms_key_arn,
            BucketKeyEnabled=True,
            ChecksumSHA256=base64.b64encode(checksum).decode("ascii"),
            IfNoneMatch="*",
            ExpectedBucketOwner=expected_bucket_owner,
            Metadata={
                "davdeploy-run-id": document["run_id"],
                "davdeploy-build-id": document["codebuild_build_id"],
                "davdeploy-result-sha256": hashlib.sha256(raw).hexdigest(),
            },
        )
    except (BotoCoreError, ClientError, OSError, TypeError, ValueError):
        raise NovaApplyBuildError(
            "apply result could not be stored; outcome requires reconciliation",
            outcome_uncertain=True,
        ) from None
    version_id = response.get("VersionId") if isinstance(response, dict) else None
    if (
        not isinstance(version_id, str)
        or not version_id
        or version_id == "null"
        or response.get("ChecksumSHA256") != base64.b64encode(checksum).decode("ascii")
    ):
        raise NovaApplyBuildError(
            "apply result has no immutable object version; outcome requires reconciliation",
            outcome_uncertain=True,
        )


def _result_key(build_arn: str) -> str:
    return f"plans/nova-generated/apply-builds/{build_arn}/result.json"


def _canonical_run_id(value: object) -> str:
    try:
        canonical = str(UUID(value))
    except (AttributeError, TypeError, ValueError):
        raise NovaApplyBuildError("durable apply run ID is invalid") from None
    if canonical != value:
        raise NovaApplyBuildError("durable apply run ID is not canonical")
    return canonical


def _required_value(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NovaApplyBuildError(f"trusted {label} is invalid")
    return value.strip()


def _required_project(value: object) -> str:
    project = _required_value(value, "CodeBuild project")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,254}", project) is None:
        raise NovaApplyBuildError("fixed CodeBuild project name is invalid")
    return project


def _required_build_arn(value: object, project_name: str, build_id: str) -> str:
    build_arn = _required_value(value, "CodeBuild build ARN")
    expected = re.fullmatch(
        rf"arn:aws(?:-us-gov|-cn)?:codebuild:[a-z0-9-]+:\d{{12}}:build/{re.escape(project_name)}:([A-Za-z0-9-]+)",
        build_arn,
    )
    if expected is None or build_id != f"{project_name}:{expected.group(1)}":
        raise NovaApplyBuildError("CodeBuild build ARN does not match its fixed project")
    return build_arn


def _required_bucket(value: object) -> str:
    bucket = _required_value(value, "Nova artifact bucket")
    if re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket) is None:
        raise NovaApplyBuildError("Nova artifact bucket name is invalid")
    return bucket


def _required_account(value: object) -> str:
    account = _required_value(value, "artifact bucket owner")
    if re.fullmatch(r"\d{12}", account) is None:
        raise NovaApplyBuildError("artifact bucket owner is invalid")
    return account


def _required_kms_key(value: object) -> str:
    key = _required_value(value, "artifact KMS key")
    if re.fullmatch(r"arn:aws:kms:[a-z0-9-]+:\d{12}:key/[a-f0-9-]+", key) is None:
        raise NovaApplyBuildError("artifact KMS key is invalid")
    return key


def _required_api_url(value: object, path: str) -> str:
    url = _required_value(value, "apply API URL")
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.path != path
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.port not in {None, 443}
            or parsed.hostname is None
            or re.fullmatch(
                r"[a-z0-9-]+\.execute-api\.[a-z]{2}(?:-[a-z0-9]+)+-\d\.amazonaws\.com(?:\.cn)?",
                parsed.hostname.lower(),
            ) is None
        ):
            raise ValueError
    except (TypeError, ValueError):
        raise NovaApplyBuildError("trusted apply API URL is invalid") from None
    return url


def _valid_https_origin(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return bool(
            parsed.scheme == "https"
            and parsed.hostname
            and parsed.username is None
            and parsed.password is None
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
            and parsed.port in {None, 443}
        )
    except ValueError:
        return False


def _trusted_terraform_binary() -> str:
    binary = shutil.which("terraform")
    if binary is None:
        raise NovaApplyBuildError("pinned Terraform binary is unavailable")
    return binary


def main() -> int:
    run_id = os.getenv(RUN_ID_ENV, "")
    try:
        run_nova_apply_build(run_id)
    except NovaApplyBuildError:
        sys.stderr.write("DavDeploy exact-plan apply did not complete; inspect the durable run.\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
