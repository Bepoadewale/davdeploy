from __future__ import annotations

import json
import subprocess
import time
from types import SimpleNamespace

import pytest
from davdeploy import cli, cli_auth


class FakeCognito:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def initiate_auth(self, **kwargs):
        self.calls.append(("initiate_auth", kwargs))
        return next(self.responses)

    def respond_to_auth_challenge(self, **kwargs):
        self.calls.append(("respond_to_auth_challenge", kwargs))
        return next(self.responses)


def _jwt_with_exp(expiry: int) -> str:
    payload = json.dumps({"exp": expiry}).encode()
    import base64

    segment = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"header.{segment}.signature"


def test_keychain_secret_uses_native_swift_access_without_logging_value(monkeypatch):
    secret = '{"identity_token":"synthetic-token"}'
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout=secret, stderr="")

    monkeypatch.setattr(cli_auth.sys, "platform", "darwin")
    monkeypatch.setattr(cli_auth.shutil, "which", lambda name: "/usr/bin/swift" if name == "swift" else None)
    monkeypatch.setattr(cli_auth.subprocess, "run", fake_run)

    assert cli_auth._keychain_secret() == secret
    assert calls[0][0][:2] == ["/usr/bin/swift", "-e"]
    assert json.loads(calls[0][1]["input"]) == {
        "service": cli_auth.KEYCHAIN_SERVICE,
        "account": cli_auth.KEYCHAIN_ACCOUNT,
    }
    assert calls[0][1]["timeout"] == 45


def test_keychain_secret_returns_none_for_missing_native_item(monkeypatch):
    monkeypatch.setattr(cli_auth.sys, "platform", "darwin")
    monkeypatch.setattr(cli_auth.shutil, "which", lambda name: "/usr/bin/swift" if name == "swift" else None)
    monkeypatch.setattr(
        cli_auth.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 44, stdout="", stderr=""),
    )

    assert cli_auth._keychain_secret() is None


def test_keychain_secret_hides_native_keychain_errors(monkeypatch):
    monkeypatch.setattr(cli_auth.sys, "platform", "darwin")
    monkeypatch.setattr(cli_auth.shutil, "which", lambda name: "/usr/bin/swift" if name == "swift" else None)
    monkeypatch.setattr(
        cli_auth.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 1, stdout="synthetic-secret", stderr="synthetic-secret detail"
        ),
    )

    with pytest.raises(RuntimeError, match="Could not read the DavDeploy CLI session") as error:
        cli_auth._keychain_secret()
    assert "synthetic-secret" not in str(error.value)


def test_login_requires_password_and_totp_and_stores_only_verified_session(monkeypatch):
    cognito = FakeCognito(
        [
            {"ChallengeName": "SOFTWARE_TOKEN_MFA", "Session": "challenge-session"},
            {
                "AuthenticationResult": {
                    "IdToken": "identity-token",
                    "RefreshToken": "refresh-token",
                    "ExpiresIn": 3600,
                }
            },
        ]
    )
    monkeypatch.setattr(cli_auth.boto3, "client", lambda *args, **kwargs: cognito)
    prompts = iter(("password-from-hidden-prompt", "123456"))
    monkeypatch.setattr(cli_auth.getpass, "getpass", lambda prompt: next(prompts))
    monkeypatch.setattr(cli_auth.sys.stdin, "isatty", lambda: True)
    verified = []

    class Api:
        def __init__(self, api_url, token):
            verified.append((api_url, token))

        def request(self, method, path):
            verified.append((method, path))
            return {"role": "administrator"}

    stored = []
    monkeypatch.setattr(cli_auth, "ProductApiClient", Api)
    monkeypatch.setattr(cli_auth, "_save_session", stored.append)

    result = cli_auth.login(
        api_url="https://api.example.test",
        username="ADMIN@example.test",
        region="us-east-1",
        client_id="public-client-id",
    )

    assert result["authenticated"] is True
    assert result["workspace_verified"] is True
    assert "identity-token" not in json.dumps(result)
    assert verified == [
        ("https://api.example.test", "identity-token"),
        ("GET", "/api/v1/me"),
    ]
    assert stored[0].username == "admin@example.test"
    assert stored[0].api_url == "https://api.example.test"
    assert stored[0].identity_token == "identity-token"
    assert stored[0].refresh_token == "refresh-token"
    assert cognito.calls[0][1]["AuthParameters"] == {
        "USERNAME": "admin@example.test",
        "PASSWORD": "password-from-hidden-prompt",
    }
    assert cognito.calls[1][1]["ChallengeResponses"]["SOFTWARE_TOKEN_MFA_CODE"] == "123456"


def test_login_does_not_store_a_session_without_software_token_challenge(monkeypatch):
    cognito = FakeCognito([{"ChallengeName": "MFA_SETUP", "Session": "setup-session"}])
    monkeypatch.setattr(cli_auth.boto3, "client", lambda *args, **kwargs: cognito)
    monkeypatch.setattr(cli_auth.getpass, "getpass", lambda _prompt: "password")
    monkeypatch.setattr(cli_auth.sys.stdin, "isatty", lambda: True)
    stored = []
    monkeypatch.setattr(cli_auth, "_save_session", stored.append)

    with pytest.raises(RuntimeError, match="did not require the configured authenticator"):
        cli_auth.login(
            api_url="https://api.example.test",
            username="admin@example.test",
            region="us-east-1",
            client_id="public-client-id",
        )

    assert not stored


def test_login_rejects_insecure_or_credential_bearing_api_urls():
    for api_url in (
        "http://api.example.test",
        "https://user:pass@api.example.test",
        "https://api.example.test/?token=secret",
    ):
        with pytest.raises(RuntimeError, match="API URL"):
            cli_auth.login(
                api_url=api_url,
                username="admin@example.test",
                region="us-east-1",
                client_id="public-client-id",
            )


def test_login_reports_only_safe_api_status_when_identity_verification_fails(monkeypatch):
    cognito = FakeCognito(
        [
            {"ChallengeName": "SOFTWARE_TOKEN_MFA", "Session": "challenge-session"},
            {
                "AuthenticationResult": {
                    "IdToken": "identity-token",
                    "RefreshToken": "refresh-token",
                    "ExpiresIn": 3600,
                }
            },
        ]
    )
    monkeypatch.setattr(cli_auth.boto3, "client", lambda *args, **kwargs: cognito)
    monkeypatch.setattr(cli_auth.getpass, "getpass", lambda _prompt: "synthetic-secret")
    monkeypatch.setattr(cli_auth.sys.stdin, "isatty", lambda: True)

    class Api:
        def __init__(self, *_args):
            pass

        def request(self, *_args):
            raise RuntimeError("davdeploy API 403: sensitive detail")

    monkeypatch.setattr(cli_auth, "ProductApiClient", Api)
    monkeypatch.setattr(cli_auth, "_save_session", lambda _session: pytest.fail("must not save"))

    with pytest.raises(RuntimeError, match="HTTP 403") as error:
        cli_auth.login(
            api_url="https://api.example.test",
            username="admin@example.test",
            region="us-east-1",
            client_id="public-client-id",
        )
    assert "sensitive detail" not in str(error.value)


def test_explicit_token_takes_precedence_over_keychain(monkeypatch):
    monkeypatch.setattr(cli_auth, "load_session", lambda: pytest.fail("Keychain should not be read"))
    assert cli_auth.resolve_token("explicit-token", api_url="https://api.example.test") == "explicit-token"


def test_cli_refreshes_expired_identity_token_before_api_use(monkeypatch):
    old = cli_auth.CliSession(
        username="admin@example.test",
        api_url="https://api.example.test",
        region="us-east-1",
        client_id="public-client-id",
        identity_token=_jwt_with_exp(int(time.time()) - 1),
        refresh_token="refresh-token",
        expires_at=int(time.time()) - 1,
    )
    cognito = SimpleNamespace(
        initiate_auth=lambda **kwargs: {
            "AuthenticationResult": {"IdToken": "new-identity-token", "ExpiresIn": 3600}
        }
    )
    monkeypatch.setattr(cli_auth, "load_session", lambda: old)
    monkeypatch.setattr(cli_auth.boto3, "client", lambda *args, **kwargs: cognito)
    stored = []
    monkeypatch.setattr(cli_auth, "_save_session", stored.append)

    assert cli_auth.resolve_token(None, api_url="https://api.example.test") == "new-identity-token"
    assert stored[0].identity_token == "new-identity-token"


def test_saved_session_is_not_sent_to_a_different_api(monkeypatch):
    session = cli_auth.CliSession(
        username="admin@example.test",
        api_url="https://api.example.test",
        region="us-east-1",
        client_id="public-client-id",
        identity_token="identity-token",
        refresh_token="refresh-token",
        expires_at=int(time.time()) + 3600,
    )
    monkeypatch.setattr(cli_auth, "load_session", lambda: session)

    with pytest.raises(RuntimeError, match="different API URL"):
        cli_auth.resolve_token(None, api_url="https://untrusted.example.test")


def test_auth_login_cli_outputs_only_safe_status(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "cognito_login",
        lambda **kwargs: {
            "authenticated": True,
            "workspace_verified": True,
        },
    )

    assert cli.main(
        [
            "--api-url",
            "https://api.example.test",
            "auth",
            "login",
            "--username",
            "admin@example.test",
        ]
    ) == 0
    output = capsys.readouterr().out
    assert "authenticated" in output
    assert "identity_token" not in output
