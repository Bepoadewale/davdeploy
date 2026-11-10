import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from davdeploy.nova_terraform_state_client import (
    TerraformStateBootstrapError,
    request_terraform_http_backend,
)

STATE_ID = "12345678-1234-4234-8234-123456789012"
STATE_URL = f"https://api.davdeploy.tech/api/v1/terraform-state/{STATE_ID}"


class _Response:
    def __init__(self, document, *, status=200):
        self.status = status
        self.payload = json.dumps(document).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, limit):
        return self.payload[:limit]


class _Credentials:
    def get_frozen_credentials(self):
        return SimpleNamespace(
            access_key="ASIAEXAMPLE",
            secret_key="example-secret",
            token="example-session-token",
        )


def _response_document(**overrides):
    document = {
        "state_id": STATE_ID,
        "scope_sha256": "a" * 64,
        "address": STATE_URL,
        "lock_address": f"{STATE_URL}/lock",
        "unlock_address": f"{STATE_URL}/unlock",
        "username": "u" * 32,
        "password": "p" * 64,
        "expires_at": (datetime.now(UTC) + timedelta(minutes=20)).isoformat(),
    }
    document.update(overrides)
    return document


def test_bootstrap_sigv4_binds_durable_request_and_build_identity():
    captured = {}

    def opener(request, *, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return _Response(_response_document())

    backend = request_terraform_http_backend(
        bootstrap_url="https://api-id.execute-api.us-east-1.amazonaws.com/api/v1/terraform-state/credentials",
        state_api_url="https://api.davdeploy.tech",
        durable_run_id="87654321-4321-4321-4321-210987654321",
        codebuild_build_id="davdeploy-nova-plan:build-attempt-1",
        region="eu-west-1",
        credentials=_Credentials(),
        opener=opener,
    )

    request = captured["request"]
    assert request.get_method() == "POST"
    assert captured["timeout"] == 15
    assert "AWS4-HMAC-SHA256 Credential=ASIAEXAMPLE/" in request.get_header("Authorization")
    assert "/us-east-1/execute-api/aws4_request" in request.get_header("Authorization")
    assert json.loads(request.data) == {
        "run_id": "87654321-4321-4321-4321-210987654321",
        "codebuild_build_id": "davdeploy-nova-plan:build-attempt-1",
    }
    assert backend.backend_configuration() == {
        "address": STATE_URL,
        "lock_address": f"{STATE_URL}/lock",
        "lock_method": "POST",
        "unlock_address": f"{STATE_URL}/unlock",
        "unlock_method": "DELETE",
    }
    assert backend.environment() == {
        "TF_HTTP_USERNAME": "u" * 32,
        "TF_HTTP_PASSWORD": "p" * 64,
    }
    assert "p" * 64 not in repr(backend)


@pytest.mark.parametrize(
    "overrides",
    [
        {"address": "https://attacker.example/state"},
        {"lock_address": "http://api.davdeploy.tech/state/lock"},
        {"expires_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()},
        {"username": "short"},
        {"password": "short"},
        {"scope_sha256": "wrong"},
    ],
)
def test_bootstrap_rejects_invalid_state_contract(overrides):
    with pytest.raises(TerraformStateBootstrapError):
        request_terraform_http_backend(
            bootstrap_url="https://api-id.execute-api.us-east-1.amazonaws.com/api/v1/terraform-state/credentials",
            state_api_url="https://api.davdeploy.tech",
            durable_run_id="87654321-4321-4321-4321-210987654321",
            codebuild_build_id="davdeploy-nova-plan:build-attempt-1",
            region="us-east-1",
            credentials=_Credentials(),
            opener=lambda *_args, **_kwargs: _Response(_response_document(**overrides)),
        )


def test_bootstrap_fails_closed_on_bad_identity_transport_or_server_status():
    request_args = {
        "state_api_url": "https://api.davdeploy.tech",
        "durable_run_id": "87654321-4321-4321-4321-210987654321",
        "codebuild_build_id": "davdeploy-nova-plan:build-attempt-1",
        "region": "us-east-1",
        "credentials": _Credentials(),
    }
    with pytest.raises(TerraformStateBootstrapError):
        request_terraform_http_backend(
            bootstrap_url="http://api-id.execute-api.us-east-1.amazonaws.com/bootstrap",
            opener=lambda *_args, **_kwargs: _Response(_response_document()),
            **request_args,
        )
    with pytest.raises(TerraformStateBootstrapError):
        request_terraform_http_backend(
            bootstrap_url="https://api-id.attacker.example/api/v1/terraform-state/credentials",
            opener=lambda *_args, **_kwargs: _Response(_response_document()),
            **request_args,
        )
    with pytest.raises(TerraformStateBootstrapError):
        request_terraform_http_backend(
            bootstrap_url="https://api-id.execute-api.us-east-1.amazonaws.com/bootstrap",
            opener=lambda *_args, **_kwargs: _Response(_response_document(), status=403),
            **request_args,
        )
