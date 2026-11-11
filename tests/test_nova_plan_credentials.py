from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest
from davdeploy.nova_plan_credentials import (
    NovaPlanCredentialError,
    _validate_credentials_document,
    request_nova_plan_credentials,
)

RUN_ID = "12345678-1234-1234-1234-123456789012"
ROLE_ARN = "arn:aws:iam::654654474502:role/davdeployPlan-connection-a"
ACCOUNT = "654654474502"
REGION = "us-east-1"
POLICY_SHA256 = "a" * 64
URL = "https://api-id.execute-api.us-east-1.amazonaws.com/api/v1/nova-plan/credentials"


def credentials_response(**overrides):
    document = {
        "contract": "davdeploy.nova-plan-credentials.v1",
        "role_arn": ROLE_ARN,
        "account_id": ACCOUNT,
        "region": REGION,
        "policy_version": "nova-plan-read-v1.1",
        "policy_sha256": POLICY_SHA256,
        "credentials": {
            "access_key_id": "ASIAABCDEFGHIJKLMNOP",
            "secret_access_key": "A" * 40,
            "session_token": "temporary-session-token-value",
            "expires_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        },
    }
    document.update(overrides)
    return document


class FrozenCredentials:
    access_key = "ASIAABCDEFGHIJKLMNOP"
    secret_key = "B" * 40
    token = "codebuild-session-token"


class Response:
    def __init__(self, document, *, status=200):
        self.document = document
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _limit):
        return json.dumps(self.document).encode()


def request(**overrides):
    values = {
        "broker_url": URL,
        "durable_run_id": RUN_ID,
        "region": REGION,
        "expected_role_arn": ROLE_ARN,
        "expected_account_id": ACCOUNT,
        "expected_policy_version": "nova-plan-read-v1.1",
        "expected_policy_sha256": POLICY_SHA256,
        "credentials": SimpleNamespace(get_frozen_credentials=lambda: FrozenCredentials()),
    }
    values.update(overrides)
    return values


def test_request_sigv4s_only_durable_run_and_returns_redacted_repr():
    seen = {}
    document = credentials_response()

    def opener(http_request, *, timeout):
        seen["method"] = http_request.method
        seen["url"] = http_request.full_url
        seen["headers"] = dict(http_request.header_items())
        seen["body"] = http_request.data
        seen["timeout"] = timeout
        return Response(document)

    result = request_nova_plan_credentials(**request(), opener=opener)

    assert seen["method"] == "POST"
    assert seen["url"] == URL
    assert "authorization" in {name.lower() for name in seen["headers"]}
    assert json.loads(seen["body"]) == {"run_id": RUN_ID}
    assert seen["timeout"] == 15
    assert result.role_arn == ROLE_ARN
    assert result.account_id == ACCOUNT
    assert result.boto3_credentials()["SecretAccessKey"] == "A" * 40
    assert "A" * 40 not in repr(result)


def test_pending_build_publication_gets_bounded_retry_then_credentials():
    attempts = []
    delays = []

    def opener(_request, *, timeout):
        attempts.append(timeout)
        if len(attempts) == 1:
            raise HTTPError(URL, 425, "Too Early", {}, BytesIO())
        if len(attempts) == 2:
            return Response({}, status=425)
        return Response(credentials_response())

    issued = request_nova_plan_credentials(
        **request(opener=opener, sleeper=delays.append)
    )

    assert len(attempts) == 3
    assert attempts == [15, 15, 15]
    assert delays == [0.1, 0.25]
    assert issued.role_arn == ROLE_ARN


def test_pending_build_publication_retry_is_bounded():
    attempts = []
    delays = []

    def opener(_request, *, timeout):
        attempts.append(timeout)
        return Response({}, status=425)

    with pytest.raises(NovaPlanCredentialError, match="remained pending"):
        request_nova_plan_credentials(
            **request(opener=opener, sleeper=delays.append)
        )

    assert len(attempts) == 5
    assert delays == [0.1, 0.25, 0.5, 1.0]


def test_authorization_failure_is_not_retried():
    attempts = []
    delays = []

    def opener(_request, *, timeout):
        attempts.append(timeout)
        return Response({}, status=403)

    with pytest.raises(NovaPlanCredentialError, match="was rejected"):
        request_nova_plan_credentials(
            **request(opener=opener, sleeper=delays.append)
        )

    assert attempts == [15]
    assert delays == []


@pytest.mark.parametrize(
    "override",
    [
        {"account_id": "111111111111"},
        {"role_arn": "arn:aws:iam::111111111111:role/davdeployPlan-foreign"},
        {"region": "us-west-2"},
        {"policy_sha256": "b" * 64},
        {"unexpected": True},
    ],
)
def test_credential_response_must_match_exact_trusted_bindings(override):
    with pytest.raises(NovaPlanCredentialError):
        _validate_credentials_document(
            credentials_response(**override),
            expected_role_arn=ROLE_ARN,
            expected_account_id=ACCOUNT,
            expected_region=REGION,
            expected_policy_version="nova-plan-read-v1.1",
            expected_policy_sha256=POLICY_SHA256,
        )


def test_credential_response_rejects_expired_or_long_lived_material():
    for expires_at in (
        (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        (datetime.now(UTC) + timedelta(minutes=20)).isoformat(),
    ):
        document = credentials_response()
        document["credentials"]["expires_at"] = expires_at
        with pytest.raises(NovaPlanCredentialError, match="expired or too long-lived"):
            _validate_credentials_document(
                document,
                expected_role_arn=ROLE_ARN,
                expected_account_id=ACCOUNT,
                expected_region=REGION,
                expected_policy_version="nova-plan-read-v1.1",
                expected_policy_sha256=POLICY_SHA256,
            )


def test_request_rejects_non_gateway_url():
    with pytest.raises(NovaPlanCredentialError, match="incomplete"):
        request_nova_plan_credentials(**request(broker_url="http://example.com/credentials"))


def test_control_plane_signing_region_is_independent_of_customer_region():
    seen = {}
    document = credentials_response(region="eu-west-1")

    def opener(http_request, *, timeout):
        del timeout
        seen["authorization"] = http_request.get_header("Authorization")
        return Response(document)

    result = request_nova_plan_credentials(
        **request(region="eu-west-1"), opener=opener
    )
    assert "us-east-1/execute-api/aws4_request" in seen["authorization"]
    assert result.region == "eu-west-1"
