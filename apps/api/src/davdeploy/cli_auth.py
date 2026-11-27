"""Cognito authentication and macOS Keychain storage for the DavDeploy CLI."""

from __future__ import annotations

import base64
import getpass
import json
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlsplit

import boto3

from davdeploy.client import ProductApiClient

KEYCHAIN_SERVICE = "davdeploy-cli-session-v1"
KEYCHAIN_ACCOUNT = "active"

_SWIFT_KEYCHAIN_STORE = r"""
import Foundation
import Security

let input = FileHandle.standardInput.readDataToEndOfFile()
let payload = try JSONSerialization.jsonObject(with: input) as! [String: String]
let service = payload["service"]!
let account = payload["account"]!
let secret = payload["secret"]!
let query: [String: Any] = [
    kSecClass as String: kSecClassGenericPassword,
    kSecAttrService as String: service,
    kSecAttrAccount as String: account
]
let update: [String: Any] = [kSecValueData as String: Data(secret.utf8)]
var status = SecItemUpdate(query as CFDictionary, update as CFDictionary)
if status == errSecItemNotFound {
    var add = query
    add[kSecValueData as String] = Data(secret.utf8)
    status = SecItemAdd(add as CFDictionary, nil)
}
if status != errSecSuccess {
    fputs("Could not store the DavDeploy CLI session in Keychain.\n", stderr)
    exit(1)
}
"""


@dataclass
class CliSession:
    username: str
    api_url: str
    region: str
    client_id: str
    identity_token: str
    refresh_token: str
    expires_at: int


def _keychain_secret() -> str | None:
    security = shutil.which("security")
    if not security:
        raise RuntimeError("macOS Keychain is unavailable; use DAVDEPLOY_TOKEN instead.")
    result = subprocess.run(
        [
            security,
            "find-generic-password",
            "-s",
            KEYCHAIN_SERVICE,
            "-a",
            KEYCHAIN_ACCOUNT,
            "-w",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _store_keychain_secret(secret: str) -> None:
    swift = shutil.which("swift")
    if sys.platform != "darwin" or not swift:
        raise RuntimeError(
            "Secure CLI login currently requires macOS Keychain; use DAVDEPLOY_TOKEN on other platforms."
        )
    payload = json.dumps(
        {"service": KEYCHAIN_SERVICE, "account": KEYCHAIN_ACCOUNT, "secret": secret}
    )
    result = subprocess.run(
        [swift, "-e", _SWIFT_KEYCHAIN_STORE],
        input=payload,
        check=False,
        capture_output=True,
        text=True,
        timeout=45,
    )
    if result.returncode != 0:
        raise RuntimeError("Could not store the DavDeploy CLI session in macOS Keychain.")


def load_session() -> CliSession | None:
    value = _keychain_secret()
    if not value:
        return None
    try:
        payload = json.loads(value)
        return CliSession(**payload)
    except (json.JSONDecodeError, TypeError):
        raise RuntimeError("The stored DavDeploy CLI session is unreadable; run `davdeploy auth login`.")


def _save_session(session: CliSession) -> None:
    _store_keychain_secret(json.dumps(asdict(session), separators=(",", ":")))


def _validate_api_url(api_url: str) -> None:
    parsed = urlsplit(api_url)
    host = (parsed.hostname or "").lower()
    loopback = host in {"localhost", "127.0.0.1", "::1"}
    if not parsed.netloc or (parsed.scheme != "https" and not (parsed.scheme == "http" and loopback)):
        raise RuntimeError("Use an HTTPS DavDeploy API URL for sign-in; HTTP is allowed only for localhost.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeError("The sign-in API URL must not contain credentials, a query, or a fragment.")


def _jwt_expiry(token: str) -> int:
    try:
        payload = token.split(".")[1]
        decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        expiry = json.loads(decoded).get("exp")
        return int(expiry) if isinstance(expiry, (int, float)) else 0
    except (IndexError, ValueError, TypeError, json.JSONDecodeError):
        return 0


def _refresh_session(session: CliSession) -> CliSession:
    if not session.refresh_token:
        raise RuntimeError("The saved DavDeploy session expired; run `davdeploy auth login`.")
    try:
        result = boto3.client("cognito-idp", region_name=session.region).initiate_auth(
            AuthFlow="REFRESH_TOKEN_AUTH",
            ClientId=session.client_id,
            AuthParameters={"REFRESH_TOKEN": session.refresh_token},
        )
    except Exception as error:
        # Do not leak Cognito response details or credentials through CLI errors.
        raise RuntimeError("The saved DavDeploy session expired; run `davdeploy auth login`.") from error
    authentication = result.get("AuthenticationResult", {})
    identity_token = authentication.get("IdToken")
    if not identity_token:
        raise RuntimeError("The saved DavDeploy session expired; run `davdeploy auth login`.")
    refreshed = CliSession(
        username=session.username,
        api_url=session.api_url,
        region=session.region,
        client_id=session.client_id,
        identity_token=identity_token,
        refresh_token=authentication.get("RefreshToken") or session.refresh_token,
        expires_at=int(time.time()) + int(authentication.get("ExpiresIn", 3600)),
    )
    _save_session(refreshed)
    return refreshed


def resolve_token(explicit_token: str | None, *, api_url: str) -> str | None:
    if explicit_token:
        return explicit_token
    session = load_session()
    if not session:
        return None
    if session.api_url.rstrip("/") != api_url.rstrip("/"):
        raise RuntimeError(
            "The saved DavDeploy session belongs to a different API URL; sign in for this API before continuing."
        )
    if _jwt_expiry(session.identity_token) <= int(time.time()) + 60:
        session = _refresh_session(session)
    return session.identity_token


def login(
    *,
    api_url: str,
    username: str | None,
    region: str,
    client_id: str,
) -> dict[str, Any]:
    if not client_id:
        raise RuntimeError("Set DAVDEPLOY_COGNITO_CLIENT_ID or pass --cognito-client-id.")
    _validate_api_url(api_url)
    if not sys.stdin.isatty() and not sys.stderr.isatty():
        raise RuntimeError("Run `davdeploy auth login` from an interactive terminal to enter secrets safely.")
    normalized = (username or input("DavDeploy email: ")).strip().lower()
    if not normalized:
        raise RuntimeError("A DavDeploy email address is required.")
    password = getpass.getpass("Password: ")
    if not password:
        raise RuntimeError("A password is required.")
    cognito = boto3.client("cognito-idp", region_name=region)
    try:
        challenge = cognito.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            ClientId=client_id,
            AuthParameters={"USERNAME": normalized, "PASSWORD": password},
        )
    except Exception as error:
        raise RuntimeError("Cognito sign-in failed; check the email and password.") from error
    if challenge.get("ChallengeName") != "SOFTWARE_TOKEN_MFA" or not challenge.get("Session"):
        raise RuntimeError(
            "Cognito did not require the configured authenticator challenge; no session was saved."
        )
    code = getpass.getpass("Authenticator code: ").strip()
    try:
        response = cognito.respond_to_auth_challenge(
            ClientId=client_id,
            ChallengeName="SOFTWARE_TOKEN_MFA",
            Session=challenge["Session"],
            ChallengeResponses={
                "USERNAME": normalized,
                "SOFTWARE_TOKEN_MFA_CODE": code,
            },
        )
    except Exception as error:
        raise RuntimeError("Cognito could not verify the authenticator code.") from error
    authentication = response.get("AuthenticationResult", {})
    identity_token = authentication.get("IdToken")
    refresh_token = authentication.get("RefreshToken")
    if not identity_token or not refresh_token:
        raise RuntimeError("Cognito did not return a complete DavDeploy session.")
    try:
        ProductApiClient(api_url, identity_token).request("GET", "/api/v1/me")
    except Exception as error:
        raise RuntimeError("The signed-in identity could not be verified by DavDeploy.") from error
    session = CliSession(
        username=normalized,
        api_url=api_url.rstrip("/"),
        region=region,
        client_id=client_id,
        identity_token=identity_token,
        refresh_token=refresh_token,
        expires_at=int(time.time()) + int(authentication.get("ExpiresIn", 3600)),
    )
    _save_session(session)
    return {
        "authenticated": True,
        "workspace_verified": True,
        "expires_at": session.expires_at,
        "token_storage": "macOS Keychain",
    }
