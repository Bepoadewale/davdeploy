from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta

import pytest
from davdeploy import nova_apply_codebuild as worker
from davdeploy.nova_apply_clients import NovaApplyRoleCredentials
from davdeploy.nova_apply_contract import validate_nova_apply_request
from davdeploy.nova_apply_workspace import PreparedNovaApplyWorkspace
from davdeploy.nova_terraform_state_client import TerraformHTTPBackend
from test_nova_apply_contract import _request_document


class FrozenCredentials:
    access_key = "ASIA" + "A" * 16
    secret_key = "s" * 40
    token = "codebuild-session-token"


class Credentials:
    def get_frozen_credentials(self):
        return FrozenCredentials()


class FakeS3:
    def __init__(self):
        self.puts = []

    def put_object(self, **kwargs):
        self.puts.append(kwargs)
        return {
            "VersionId": "result-version-1",
            "ChecksumSHA256": kwargs["ChecksumSHA256"],
        }


def _request():
    document = _request_document()
    prefix = (
        "plans/nova-generated/apply-builds/"
        f"{document['codebuild_build_arn']}/artifacts/{document['run_id']}/"
    )
    document["staged_saved_plan"] = {
        **document["saved_plan"],
        "key": prefix + "saved.tfplan",
        "version_id": "staged-plan-version",
    }
    document["staged_execution_workspace"] = {
        **document["execution_workspace"],
        "key": prefix + "execution-workspace.tar.gz",
        "version_id": "staged-workspace-version",
    }
    return validate_nova_apply_request(
        document,
        expected_run_id=document["run_id"],
        expected_codebuild_project=document["codebuild_project"],
        expected_codebuild_build_arn=document["codebuild_build_arn"],
        expected_artifact_bucket=document["saved_plan"]["bucket"],
        require_staged_artifacts=True,
    )


def _environment(request):
    build_arn = request.codebuild_build_arn
    build_id = f"{request.codebuild_project}:build-abc123"
    return {
        worker.RUN_ID_ENV: request.run_id,
        "CODEBUILD_BUILD_ID": build_id,
        "CODEBUILD_BUILD_ARN": build_arn,
        "DAVDEPLOY_NOVA_APPLY_PROJECT_NAME": request.codebuild_project,
        "DAVDEPLOY_NOVA_APPLY_ARTIFACT_BUCKET": request.saved_plan.bucket,
        "DAVDEPLOY_NOVA_APPLY_BUCKET_OWNER": request.target_account_id,
        "DAVDEPLOY_NOVA_APPLY_KMS_KEY_ARN": (
            f"arn:aws:kms:{request.region}:{request.target_account_id}:key/"
            "11111111-2222-3333-4444-555555555555"
        ),
        "DAVDEPLOY_NOVA_APPLY_INPUT_URL": (
            "https://abc123.execute-api.us-east-1.amazonaws.com/api/v1/nova-apply/input"
        ),
        "DAVDEPLOY_NOVA_APPLY_CREDENTIAL_BROKER_URL": (
            "https://abc123.execute-api.us-east-1.amazonaws.com/api/v1/nova-apply/credentials"
        ),
        "DAVDEPLOY_TERRAFORM_STATE_ENABLED": "true",
        "DAVDEPLOY_TERRAFORM_STATE_BOOTSTRAP_URL": (
            "https://abc123.execute-api.us-east-1.amazonaws.com/api/v1/terraform-state/credentials"
        ),
        "DAVDEPLOY_TERRAFORM_STATE_API_URL": "https://api.davdeploy.tech",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_REGION": "us-east-1",
    }


def test_fixed_runner_initializes_tenant_state_and_applies_only_saved_plan(monkeypatch, tmp_path):
    request = _request()
    environment = _environment(request)
    environment["TF_CLI_ARGS_apply"] = "-destroy"
    environment["TF_WORKSPACE"] = "caller-selected"
    s3 = FakeS3()
    applied_credentials = NovaApplyRoleCredentials(
        role_arn=f"arn:aws:iam::{request.target_account_id}:role/davdeployNovaApply-connection-1",
        account_id=request.target_account_id,
        region=request.region,
        policy_version=request.manifest["customer_apply_access"]["version"],
        policy_sha256=request.manifest["customer_apply_access"]["session_policy_sha256"],
        access_key_id="ASIA" + "B" * 16,
        secret_access_key="S" * 40,
        session_token="temporary-session-token-long-enough",
        expires_at=datetime.now(UTC) + timedelta(minutes=14),
    )
    state = request.manifest["remote_state"]
    backend = TerraformHTTPBackend(
        state_id=state["state_id"],
        scope_sha256=state["scope_sha256"],
        address="https://api.davdeploy.tech/api/v1/terraform-state/" + state["state_id"],
        lock_address="https://api.davdeploy.tech/api/v1/terraform-state/" + state["state_id"] + "/lock",
        unlock_address="https://api.davdeploy.tech/api/v1/terraform-state/" + state["state_id"] + "/unlock",
        username="state-username-1234567890",
        password="state-password-1234567890-abcdefghijklmnopqrstuv",
        expires_at=datetime.now(UTC) + timedelta(minutes=20),
    )
    monkeypatch.setattr(worker.boto3, "Session", lambda **_kwargs: type("Session", (), {"get_credentials": lambda self: Credentials()})())
    monkeypatch.setattr(worker, "_trusted_terraform_binary", lambda: "/tmp/terraform")
    monkeypatch.setattr(
        worker,
        "prepare_nova_apply_workspace",
        lambda *_args, **_kwargs: PreparedNovaApplyWorkspace(
            root=tmp_path,
            saved_plan_path=tmp_path / "saved.tfplan",
            terraform_version="1.14.7",
            aws_provider_version="6.0.0",
            provider_lockfile_sha256="c" * 64,
        ),
    )
    monkeypatch.setattr(worker, "_verify_customer_identity", lambda *_args: None)

    calls = []

    def terraform_runner(_binary, arguments, **kwargs):
        calls.append((arguments, kwargs))
        stdout = json.dumps({"terraform_version": "1.14.7"}) if arguments == ["version", "-json"] else ""
        return subprocess.CompletedProcess(arguments, 0, stdout=stdout, stderr="")

    result = worker.run_nova_apply_build(
        request.run_id,
        environment=environment,
        s3_client=s3,
        input_requester=lambda **_kwargs: request,
        state_bootstrapper=lambda **_kwargs: backend,
        credential_requester=lambda **_kwargs: applied_credentials,
        terraform_runner=terraform_runner,
        workspace_root=tmp_path,
    )

    assert [call[0][0] for call in calls] == ["version", "init", "apply"]
    assert calls[1][0][1] == "-reconfigure"
    assert calls[2][0][-1] == str(tmp_path / "saved.tfplan")
    assert all("plan" not in call[0] for call in calls[2:])
    assert calls[1][1]["env"]["TF_HTTP_PASSWORD"] == backend.password
    assert "TF_CLI_ARGS_apply" not in calls[1][1]["env"]
    assert "TF_WORKSPACE" not in calls[1][1]["env"]
    assert calls[2][1]["env"]["AWS_ACCESS_KEY_ID"] == applied_credentials.access_key_id
    assert result["execution_status"] == "APPLIED_UNVERIFIED"
    assert s3.puts[0]["Key"].endswith("/result.json")
    assert s3.puts[0]["ServerSideEncryption"] == "aws:kms"
    assert s3.puts[0]["IfNoneMatch"] == "*"
    assert s3.puts[0]["Metadata"]["davdeploy-build-id"] == request.codebuild_build_arn.rsplit("/", 1)[-1]


def test_runner_stops_before_any_credentials_when_remote_state_is_disabled(monkeypatch):
    request = _request()
    environment = _environment(request)
    environment["DAVDEPLOY_TERRAFORM_STATE_ENABLED"] = "false"
    calls = []
    monkeypatch.setattr(worker.boto3, "Session", lambda **_kwargs: type("Session", (), {"get_credentials": lambda self: Credentials()})())

    with pytest.raises(worker.NovaApplyBuildError, match="state is not enabled"):
        worker.run_nova_apply_build(
            request.run_id,
            environment=environment,
            input_requester=lambda **_kwargs: calls.append("input"),
            credential_requester=lambda **_kwargs: calls.append("customer-credentials"),
        )
    assert calls == []


def test_nonzero_saved_plan_apply_requires_reconciliation(monkeypatch, tmp_path):
    request = _request()
    environment = _environment(request)
    s3 = FakeS3()
    state = request.manifest["remote_state"]
    backend = TerraformHTTPBackend(
        state_id=state["state_id"],
        scope_sha256=state["scope_sha256"],
        address="https://api.davdeploy.tech/api/v1/terraform-state/" + state["state_id"],
        lock_address="https://api.davdeploy.tech/api/v1/terraform-state/" + state["state_id"] + "/lock",
        unlock_address="https://api.davdeploy.tech/api/v1/terraform-state/" + state["state_id"] + "/unlock",
        username="state-username-1234567890",
        password="state-password-1234567890-abcdefghijklmnopqrstuv",
        expires_at=datetime.now(UTC) + timedelta(minutes=20),
    )
    applied_credentials = NovaApplyRoleCredentials(
        role_arn=f"arn:aws:iam::{request.target_account_id}:role/davdeployNovaApply-connection-1",
        account_id=request.target_account_id,
        region=request.region,
        policy_version=request.manifest["customer_apply_access"]["version"],
        policy_sha256=request.manifest["customer_apply_access"]["session_policy_sha256"],
        access_key_id="ASIA" + "B" * 16,
        secret_access_key="S" * 40,
        session_token="temporary-session-token-long-enough",
        expires_at=datetime.now(UTC) + timedelta(minutes=14),
    )
    monkeypatch.setattr(worker.boto3, "Session", lambda **_kwargs: type("Session", (), {"get_credentials": lambda self: Credentials()})())
    monkeypatch.setattr(worker, "_trusted_terraform_binary", lambda: "/tmp/terraform")
    monkeypatch.setattr(
        worker,
        "prepare_nova_apply_workspace",
        lambda *_args, **_kwargs: PreparedNovaApplyWorkspace(
            root=tmp_path,
            saved_plan_path=tmp_path / "saved.tfplan",
            terraform_version="1.14.7",
            aws_provider_version="6.0.0",
            provider_lockfile_sha256="c" * 64,
        ),
    )
    monkeypatch.setattr(worker, "_verify_customer_identity", lambda *_args: None)
    calls = []

    def terraform_runner(_binary, arguments, **kwargs):
        calls.append(arguments)
        stdout = json.dumps({"terraform_version": "1.14.7"}) if arguments == ["version", "-json"] else ""
        status = 1 if arguments[0] == "apply" else 0
        return subprocess.CompletedProcess(arguments, status, stdout=stdout, stderr="")

    with pytest.raises(worker.NovaApplyBuildError, match="requires reconciliation") as error:
        worker.run_nova_apply_build(
            request.run_id,
            environment=environment,
            s3_client=s3,
            input_requester=lambda **_kwargs: request,
            state_bootstrapper=lambda **_kwargs: backend,
            credential_requester=lambda **_kwargs: applied_credentials,
            terraform_runner=terraform_runner,
            workspace_root=tmp_path,
        )
    assert error.value.outcome_uncertain
    assert calls[-1][0] == "apply"
    assert s3.puts == []


def test_runner_refuses_to_apply_when_credentials_cannot_cover_full_timeout(monkeypatch, tmp_path):
    request = _request()
    environment = _environment(request)
    state = request.manifest["remote_state"]
    backend = TerraformHTTPBackend(
        state_id=state["state_id"],
        scope_sha256=state["scope_sha256"],
        address="https://api.davdeploy.tech/api/v1/terraform-state/" + state["state_id"],
        lock_address="https://api.davdeploy.tech/api/v1/terraform-state/" + state["state_id"] + "/lock",
        unlock_address="https://api.davdeploy.tech/api/v1/terraform-state/" + state["state_id"] + "/unlock",
        username="state-username-1234567890",
        password="state-password-1234567890-abcdefghijklmnopqrstuv",
        expires_at=datetime.now(UTC) + timedelta(minutes=20),
    )
    short_lived_credentials = NovaApplyRoleCredentials(
        role_arn=f"arn:aws:iam::{request.target_account_id}:role/davdeployNovaApply-connection-1",
        account_id=request.target_account_id,
        region=request.region,
        policy_version=request.manifest["customer_apply_access"]["version"],
        policy_sha256=request.manifest["customer_apply_access"]["session_policy_sha256"],
        access_key_id="ASIA" + "B" * 16,
        secret_access_key="S" * 40,
        session_token="temporary-session-token-long-enough",
        expires_at=datetime.now(UTC) + timedelta(minutes=11),
    )
    monkeypatch.setattr(worker.boto3, "Session", lambda **_kwargs: type("Session", (), {"get_credentials": lambda self: Credentials()})())
    monkeypatch.setattr(worker, "_trusted_terraform_binary", lambda: "/tmp/terraform")
    monkeypatch.setattr(
        worker,
        "prepare_nova_apply_workspace",
        lambda *_args, **_kwargs: PreparedNovaApplyWorkspace(
            root=tmp_path,
            saved_plan_path=tmp_path / "saved.tfplan",
            terraform_version="1.14.7",
            aws_provider_version="6.0.0",
            provider_lockfile_sha256="c" * 64,
        ),
    )
    monkeypatch.setattr(worker, "_verify_customer_identity", lambda *_args: None)
    commands = []

    def terraform_runner(_binary, arguments, **kwargs):
        commands.append(arguments[0])
        stdout = json.dumps({"terraform_version": "1.14.7"}) if arguments == ["version", "-json"] else ""
        return subprocess.CompletedProcess(arguments, 0, stdout=stdout, stderr="")

    with pytest.raises(worker.NovaApplyBuildError, match="bounded execution window"):
        worker.run_nova_apply_build(
            request.run_id,
            environment=environment,
            s3_client=FakeS3(),
            input_requester=lambda **_kwargs: request,
            state_bootstrapper=lambda **_kwargs: backend,
            credential_requester=lambda **_kwargs: short_lived_credentials,
            terraform_runner=terraform_runner,
            workspace_root=tmp_path,
        )
    assert commands == ["version", "init"]
