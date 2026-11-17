"""SigV4 clients for the fixed Nova exact-plan apply API routes."""

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

from davdeploy.nova_apply_contract import (
    NovaApplyContractError,
    NovaApplyRequest,
    validate_nova_apply_request,
)

MAX_INPUT_RESPONSE_BYTES = 1_000_000
MAX_CREDENTIAL_RESPONSE_BYTES = 64 * 1024
MAX_APPLY_CREDENTIAL_TTL = timedelta(minutes=15)
INPUT_PATH = "/api/v1/nova-apply/input"
CREDENTIAL_PATH = "/api/v1/nova-apply/credentials"


class NovaApplyApiError(RuntimeError):
    """The authenticated control plane rejected an exact apply API request."""


@dataclass(frozen=True)
class NovaApplyRoleCredentials:
    role_arn: str
    account_id: str
    region: str
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


def request_nova_apply_input(
    *,
    input_url: str,
    run_id: str,
    codebuild_project: str,
    codebuild_build_arn: str,
    artifact_bucket: str,
    credentials,
    opener: Callable[..., object] = _open_without_redirects,
) -> NovaApplyRequest:
    """Fetch and strictly validate the server-issued, build-specific request."""
    _validate_identity(run_id, input_url, INPUT_PATH)
    raw = _signed_post(
        url=input_url,
        document={"run_id": run_id},
        credentials=credentials,
        maximum_bytes=MAX_INPUT_RESPONSE_BYTES,
        opener=opener,
    )
    try:
        document = json.loads(raw)
        return validate_nova_apply_request(
            document,
            expected_run_id=run_id,
            expected_codebuild_project=codebuild_project,
            expected_codebuild_build_arn=codebuild_build_arn,
            expected_artifact_bucket=artifact_bucket,
            require_staged_artifacts=True,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, NovaApplyContractError):
        raise NovaApplyApiError("Nova apply input contract failed validation") from None


def request_nova_apply_credentials(
    *,
    broker_url: str,
    run_id: str,
    expected_account_id: str,
    expected_region: str,
    credentials,
    opener: Callable[..., object] = _open_without_redirects,
) -> NovaApplyRoleCredentials:
    """Request customer credentials only for the exact active apply run."""
    _validate_identity(run_id, broker_url, CREDENTIAL_PATH)
    if not re.fullmatch(r"\d{12}", expected_account_id) or not re.fullmatch(
        r"[a-z]{2}(?:-[a-z0-9]+)+-\d", expected_region
    ):
        raise NovaApplyApiError("trusted Nova apply target is invalid")
    raw = _signed_post(
        url=broker_url,
        document={"run_id": run_id},
        credentials=credentials,
        maximum_bytes=MAX_CREDENTIAL_RESPONSE_BYTES,
        opener=opener,
    )
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise NovaApplyApiError("Nova apply credential response is invalid") from None
    return _validate_credentials(
        document,
        expected_run_id=run_id,
        expected_account_id=expected_account_id,
        expected_region=expected_region,
    )


def _signed_post(
    *,
    url: str,
    document: dict[str, str],
    credentials,
    maximum_bytes: int,
    opener: Callable[..., object],
) -> bytes:
    signing_region = _signing_region(url)
    if signing_region is None or credentials is None:
        raise NovaApplyApiError("trusted Nova apply API configuration is invalid")
    try:
        frozen = credentials.get_frozen_credentials()
        if not all(
            isinstance(value, str) and value
            for value in (frozen.access_key, frozen.secret_key, frozen.token)
        ):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        raise NovaApplyApiError("CodeBuild service-role credentials are unavailable") from None
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    aws_request = AWSRequest(
        method="POST",
        url=url,
        data=payload,
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
        with opener(request, timeout=20) as response:
            if response.status != 200:
                raise NovaApplyApiError("Nova apply API request was rejected")
            raw = response.read(maximum_bytes + 1)
    except NovaApplyApiError:
        raise
    except HTTPError:
        raise NovaApplyApiError("Nova apply API request was rejected") from None
    except (URLError, OSError, TimeoutError, TypeError, ValueError):
        raise NovaApplyApiError("Nova apply API request failed") from None
    if not isinstance(raw, bytes) or not raw or len(raw) > maximum_bytes:
        raise NovaApplyApiError("Nova apply API response exceeded its limit")
    return raw


def _validate_identity(run_id: str, url: str, expected_path: str) -> None:
    try:
        if str(UUID(run_id)) != run_id:
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        raise NovaApplyApiError("durable Nova apply run ID is invalid") from None
    if _signing_region(url, expected_path=expected_path) is None:
        raise NovaApplyApiError("trusted Nova apply API URL is invalid")


def _validate_credentials(
    document: object,
    *,
    expected_run_id: str,
    expected_account_id: str,
    expected_region: str,
) -> NovaApplyRoleCredentials:
    try:
        if str(UUID(expected_run_id)) != expected_run_id:
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        raise NovaApplyApiError("durable apply run ID is invalid") from None
    expected_fields = {"contract", "role_arn", "account_id", "region", "credentials"}
    if not isinstance(document, dict) or set(document) != expected_fields:
        raise NovaApplyApiError("Nova apply credential response shape is invalid")
    credentials = document.get("credentials")
    if not isinstance(credentials, dict) or set(credentials) != {
        "access_key_id",
        "secret_access_key",
        "session_token",
        "expires_at",
    }:
        raise NovaApplyApiError("Nova apply credential response shape is invalid")
    role_arn = document.get("role_arn")
    if (
        document.get("contract") != "davdeploy.nova-apply-credentials.v1"
        or document.get("account_id") != expected_account_id
        or document.get("region") != expected_region
        or not isinstance(role_arn, str)
        or re.fullmatch(
            rf"arn:aws:iam::{expected_account_id}:role/davdeployNovaApply-[A-Za-z0-9-]{{1,128}}",
            role_arn,
        ) is None
    ):
        raise NovaApplyApiError("Nova apply credentials do not match the approved target")
    access_key = credentials.get("access_key_id")
    secret_key = credentials.get("secret_access_key")
    token = credentials.get("session_token")
    if (
        not isinstance(access_key, str)
        or re.fullmatch(r"ASIA[A-Z0-9]{16}", access_key) is None
        or not isinstance(secret_key, str)
        or re.fullmatch(r"[A-Za-z0-9/+=]{40}", secret_key) is None
        or not isinstance(token, str)
        or not 16 <= len(token) <= 8192
    ):
        raise NovaApplyApiError("temporary Nova apply credentials are malformed")
    try:
        expires_at = datetime.fromisoformat(credentials.get("expires_at"))
        if expires_at.tzinfo is None:
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        raise NovaApplyApiError("temporary Nova apply credential expiry is invalid") from None
    now = datetime.now(UTC)
    if not now < expires_at <= now + MAX_APPLY_CREDENTIAL_TTL + timedelta(seconds=30):
        raise NovaApplyApiError("temporary Nova apply credentials are expired or too long-lived")
    return NovaApplyRoleCredentials(
        role_arn=role_arn,
        account_id=expected_account_id,
        region=expected_region,
        access_key_id=access_key,
        secret_access_key=secret_key,
        session_token=token,
        expires_at=expires_at.astimezone(UTC),
    )


def _signing_region(value: str, *, expected_path: str | None = None) -> str | None:
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or (expected_path is not None and parsed.path != expected_path)
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
