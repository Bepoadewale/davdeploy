"""SigV4 client for run-scoped Nova customer-role credentials."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

MAX_RESPONSE_BYTES = 64 * 1024
MAX_CREDENTIAL_TTL = timedelta(minutes=15)
CREDENTIAL_PATH = "/api/v1/nova-plan/credentials"


class NovaPlanCredentialError(RuntimeError):
    """The trusted control plane did not issue a valid run-bound credential."""


@dataclass(frozen=True)
class NovaPlanRoleCredentials:
    role_arn: str
    account_id: str
    region: str
    policy_version: str
    policy_sha256: str
    access_key_id: str = field(repr=False)
    secret_access_key: str = field(repr=False)
    session_token: str = field(repr=False)
    expires_at: datetime

    def boto3_credentials(self) -> dict[str, str]:
        return {
            "AccessKeyId": self.access_key_id,
            "SecretAccessKey": self.secret_access_key,
            "SessionToken": self.session_token,
        }


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def _open_without_redirects(request: Request, *, timeout: int):
    return build_opener(_RejectRedirects()).open(request, timeout=timeout)


def request_nova_plan_credentials(
    *,
    broker_url: str,
    durable_run_id: str,
    region: str,
    expected_role_arn: str,
    expected_account_id: str,
    expected_policy_version: str,
    expected_policy_sha256: str,
    credentials,
    opener: Callable[..., object] = _open_without_redirects,
) -> NovaPlanRoleCredentials:
    """Request one exact customer role session from the authenticated API."""
    signing_region = _bootstrap_signing_region(broker_url)
    try:
        if str(UUID(durable_run_id)) != durable_run_id.lower():
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        raise NovaPlanCredentialError("durable Nova plan run ID is invalid") from None
    if (
        signing_region is None
        or not re.fullmatch(r"\d{12}", expected_account_id)
        or not re.fullmatch(
            rf"arn:aws:iam::{expected_account_id}:role/davdeployPlan-[A-Za-z0-9-]{{1,100}}",
            expected_role_arn,
        )
        or not re.fullmatch(r"[a-f0-9]{64}", expected_policy_sha256)
        or not isinstance(expected_policy_version, str)
        or not expected_policy_version
        or credentials is None
    ):
        raise NovaPlanCredentialError("trusted Nova plan credential request is incomplete")
    try:
        frozen = credentials.get_frozen_credentials()
        if not all(
            isinstance(value, str) and value
            for value in (frozen.access_key, frozen.secret_key, frozen.token)
        ):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        raise NovaPlanCredentialError("CodeBuild service-role credentials are unavailable") from None

    body = json.dumps(
        {"run_id": durable_run_id},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    aws_request = AWSRequest(
        method="POST",
        url=broker_url,
        data=body,
        headers={"content-type": "application/json"},
    )
    SigV4Auth(frozen, "execute-api", signing_region).add_auth(aws_request)
    prepared = aws_request.prepare()
    request = Request(
        prepared.url,
        data=prepared.body,
        headers=dict(prepared.headers.items()),
        method=prepared.method,
    )
    try:
        with opener(request, timeout=15) as response:
            if response.status != 200:
                raise NovaPlanCredentialError("Nova plan credential request was rejected")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except NovaPlanCredentialError:
        raise
    except (HTTPError, URLError, OSError, TimeoutError, TypeError, ValueError):
        raise NovaPlanCredentialError("Nova plan credential request failed") from None
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_RESPONSE_BYTES:
        raise NovaPlanCredentialError("Nova plan credential response is invalid")
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise NovaPlanCredentialError("Nova plan credential response is invalid") from None
    return _validate_credentials_document(
        document,
        expected_role_arn=expected_role_arn,
        expected_account_id=expected_account_id,
        expected_region=region,
        expected_policy_version=expected_policy_version,
        expected_policy_sha256=expected_policy_sha256,
    )


def _validate_credentials_document(
    document,
    *,
    expected_role_arn: str,
    expected_account_id: str,
    expected_region: str,
    expected_policy_version: str,
    expected_policy_sha256: str,
) -> NovaPlanRoleCredentials:
    fields = {
        "contract",
        "role_arn",
        "account_id",
        "region",
        "policy_version",
        "policy_sha256",
        "credentials",
    }
    if not isinstance(document, dict) or set(document) != fields:
        raise NovaPlanCredentialError("Nova plan credential response shape is invalid")
    credentials = document.get("credentials")
    if not isinstance(credentials, dict) or set(credentials) != {
        "access_key_id",
        "secret_access_key",
        "session_token",
        "expires_at",
    }:
        raise NovaPlanCredentialError("Nova plan credential response shape is invalid")
    if (
        document.get("contract") != "davdeploy.nova-plan-credentials.v1"
        or document.get("role_arn") != expected_role_arn
        or document.get("account_id") != expected_account_id
        or document.get("region") != expected_region
        or document.get("policy_version") != expected_policy_version
        or document.get("policy_sha256") != expected_policy_sha256
    ):
        raise NovaPlanCredentialError("Nova plan credentials do not match the requested trust scope")
    access_key = credentials.get("access_key_id")
    secret_key = credentials.get("secret_access_key")
    token = credentials.get("session_token")
    if (
        not isinstance(access_key, str)
        or not re.fullmatch(r"ASIA[A-Z0-9]{16}", access_key)
        or not isinstance(secret_key, str)
        or not re.fullmatch(r"[A-Za-z0-9/+=]{40}", secret_key)
        or not isinstance(token, str)
        or len(token) < 16
        or len(token) > 8192
    ):
        raise NovaPlanCredentialError("temporary Nova plan credentials are malformed")
    try:
        expires_at = datetime.fromisoformat(credentials.get("expires_at"))
        if expires_at.tzinfo is None:
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        raise NovaPlanCredentialError("temporary Nova plan credential expiry is invalid") from None
    now = datetime.now(UTC)
    if not now < expires_at <= now + MAX_CREDENTIAL_TTL + timedelta(minutes=1):
        raise NovaPlanCredentialError("temporary Nova plan credentials are expired or too long-lived")
    return NovaPlanRoleCredentials(
        role_arn=expected_role_arn,
        account_id=expected_account_id,
        region=expected_region,
        policy_version=expected_policy_version,
        policy_sha256=expected_policy_sha256,
        access_key_id=access_key,
        secret_access_key=secret_key,
        session_token=token,
        expires_at=expires_at.astimezone(UTC),
    )


def _bootstrap_signing_region(value: str) -> str | None:
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path != CREDENTIAL_PATH
            or parsed.query
            or parsed.fragment
            or parsed.port not in {None, 443}
            or parsed.hostname is None
        ):
            return None
        match = re.fullmatch(
            r"[a-z0-9-]+\.execute-api\.([a-z]{2}(?:-[a-z0-9]+)+-\d)\.amazonaws\.com(?:\.cn)?",
            parsed.hostname.lower(),
        )
    except (TypeError, ValueError):
        return None
    return match.group(1) if match else None
