from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from davdeploy.nova_apply_access import NOVA_APPLY_ACCESS_POLICY_VERSION
from davdeploy.nova_apply_clients import (
    NovaApplyApiError,
    request_nova_apply_credentials,
    request_nova_apply_input,
)
from test_nova_apply_contract import _request_document

RUN_ID = "4e3a0bf8-78b8-46ce-b5e1-94e5e3d18f34"
ACCOUNT = "654654474502"
REGION = "us-east-1"
API = f"https://abc123.execute-api.{REGION}.amazonaws.com"
BUILD_ARN = f"arn:aws:codebuild:{REGION}:{ACCOUNT}:build/davdeploy-nova-apply:build-1"


class FrozenCredentials:
    access_key = "ASIA" + "A" * 16
    secret_key = "s" * 40
    token = "codebuild-session-token"


class Credentials:
    def get_frozen_credentials(self):
        return FrozenCredentials()


class Response:
    status = 200

    def __init__(self, value):
        self.raw = json.dumps(value).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, size):
        return self.raw[:size]


def _staged_request_document():
    document = _request_document()
    document["run_id"] = RUN_ID
    document["codebuild_project"] = "davdeploy-nova-apply"
    document["codebuild_build_arn"] = BUILD_ARN
    prefix = f"plans/nova-generated/apply-builds/{BUILD_ARN}/artifacts/{RUN_ID}/"
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
    return document


def test_input_client_signs_fixed_route_and_validates_staged_contract():
    document = _staged_request_document()
    captured = {}

    def opener(request, *, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response(document)

    result = request_nova_apply_input(
        input_url=API + "/api/v1/nova-apply/input",
        run_id=RUN_ID,
        codebuild_project=document["codebuild_project"],
        codebuild_build_arn=BUILD_ARN,
        artifact_bucket=document["saved_plan"]["bucket"],
        credentials=Credentials(),
        opener=opener,
    )

    assert result.run_id == RUN_ID
    assert result.staged_saved_plan.key.endswith("/saved.tfplan")
    assert captured["request"].get_header("Authorization").startswith("AWS4-HMAC-SHA256")
    assert captured["timeout"] == 20


def test_input_client_rejects_redirect_like_wrong_path_before_request():
    called = False

    def opener(*_args, **_kwargs):
        nonlocal called
        called = True
        return Response({})

    with pytest.raises(NovaApplyApiError, match="API URL is invalid"):
        request_nova_apply_input(
            input_url=API + "/redirect",
            run_id=RUN_ID,
            codebuild_project="davdeploy-nova-apply",
            codebuild_build_arn=BUILD_ARN,
            artifact_bucket="davdeploy-plans-654654474502",
            credentials=Credentials(),
            opener=opener,
        )
    assert not called


def test_credential_client_validates_role_account_and_short_lifetime():
    expires = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    document = {
        "contract": "davdeploy.nova-apply-credentials.v1",
        "role_arn": f"arn:aws:iam::{ACCOUNT}:role/davdeployNovaApply-connection-1",
        "account_id": ACCOUNT,
        "region": REGION,
        "policy_version": NOVA_APPLY_ACCESS_POLICY_VERSION,
        "policy_sha256": "a" * 64,
        "credentials": {
            "access_key_id": "ASIA" + "B" * 16,
            "secret_access_key": "S" * 40,
            "session_token": "temporary-session-token-long-enough",
            "expires_at": expires,
        },
    }

    result = request_nova_apply_credentials(
        broker_url=API + "/api/v1/nova-apply/credentials",
        run_id=RUN_ID,
        expected_account_id=ACCOUNT,
        expected_region=REGION,
        expected_policy_version=NOVA_APPLY_ACCESS_POLICY_VERSION,
        expected_policy_sha256="a" * 64,
        credentials=Credentials(),
        opener=lambda *_args, **_kwargs: Response(document),
    )

    assert result.account_id == ACCOUNT
    assert result.role_arn.endswith("davdeployNovaApply-connection-1")
    assert "S" * 40 not in repr(result)


def test_credential_client_rejects_wrong_account():
    document = {
        "contract": "davdeploy.nova-apply-credentials.v1",
        "role_arn": "arn:aws:iam::111111111111:role/davdeployNovaApply-connection-1",
        "account_id": "111111111111",
        "region": REGION,
        "policy_version": NOVA_APPLY_ACCESS_POLICY_VERSION,
        "policy_sha256": "a" * 64,
        "credentials": {
            "access_key_id": "ASIA" + "B" * 16,
            "secret_access_key": "S" * 40,
            "session_token": "temporary-session-token-long-enough",
            "expires_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        },
    }
    with pytest.raises(NovaApplyApiError, match="approved target"):
        request_nova_apply_credentials(
            broker_url=API + "/api/v1/nova-apply/credentials",
            run_id=RUN_ID,
            expected_account_id=ACCOUNT,
            expected_region=REGION,
            expected_policy_version=NOVA_APPLY_ACCESS_POLICY_VERSION,
            expected_policy_sha256="a" * 64,
            credentials=Credentials(),
            opener=lambda *_args, **_kwargs: Response(document),
        )
