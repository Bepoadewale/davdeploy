import io
import json

import pytest

from scripts.lambda_service_lifecycle import invoke_and_verify, verify_account


class FakeSTS:
    def __init__(self, account_id):
        self.account_id = account_id

    def get_caller_identity(self):
        return {"Account": self.account_id}


class FakeLambda:
    def __init__(self, response):
        self.response = response
        self.request = None

    def invoke(self, **kwargs):
        self.request = kwargs
        return self.response


def test_verify_account_accepts_expected_account():
    verify_account(FakeSTS("654654474502"), "654654474502")


def test_verify_account_rejects_wrong_account():
    with pytest.raises(RuntimeError, match="expected test account"):
        verify_account(FakeSTS("111111111111"), "654654474502")


def test_invocation_checks_version_and_test_id():
    fake = FakeLambda(
        {"StatusCode": 200, "Payload": io.BytesIO(json.dumps({"version": "v2", "test_id": "synthetic"}).encode())}
    )

    result = invoke_and_verify(fake, "test-function", "v2", "synthetic")

    assert result["version"] == "v2"
    assert fake.request["InvocationType"] == "RequestResponse"
    assert json.loads(fake.request["Payload"]) == {"test_id": "synthetic"}


def test_invocation_fails_when_version_did_not_update():
    fake = FakeLambda(
        {"StatusCode": 200, "Payload": io.BytesIO(json.dumps({"version": "v1", "test_id": "synthetic"}).encode())}
    )

    with pytest.raises(RuntimeError, match="unexpected synthetic"):
        invoke_and_verify(fake, "test-function", "v2", "synthetic")
