"""SigV4 bootstrap for the tenant-scoped Terraform HTTP state backend."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

MAX_BOOTSTRAP_RESPONSE_BYTES = 64 * 1024
MAX_CREDENTIAL_TTL = timedelta(minutes=30)


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def _open_without_redirects(request: Request, *, timeout: int):
    return build_opener(_RejectRedirects()).open(request, timeout=timeout)


class TerraformStateBootstrapError(RuntimeError):
    """The trusted state service could not issue a valid backend contract."""


@dataclass(frozen=True)
class TerraformHTTPBackend:
    state_id: str
    scope_sha256: str
    address: str
    lock_address: str
    unlock_address: str
    username: str
    password: str = field(repr=False)
    expires_at: datetime

    def backend_configuration(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "lock_address": self.lock_address,
            "lock_method": "POST",
            "unlock_address": self.unlock_address,
            "unlock_method": "DELETE",
        }

    def environment(self) -> dict[str, str]:
        return {
            "TF_HTTP_USERNAME": self.username,
            "TF_HTTP_PASSWORD": self.password,
        }


def request_terraform_http_backend(
    *,
    bootstrap_url: str,
    state_api_url: str,
    durable_run_id: str,
    codebuild_build_id: str,
    region: str,
    credentials: Any,
    opener: Callable[..., Any] = _open_without_redirects,
) -> TerraformHTTPBackend:
    """Sign the fixed bootstrap request and validate the returned backend contract."""
    if (
        not _valid_bootstrap_url(bootstrap_url)
        or _https_origin(state_api_url) is None
    ):
        raise TerraformStateBootstrapError("trusted state bootstrap URL is invalid")
    try:
        if str(UUID(durable_run_id)) != durable_run_id.lower():
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        raise TerraformStateBootstrapError("durable control-plane request ID is invalid") from None
    if (
        not isinstance(codebuild_build_id, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{2,255}:[A-Za-z0-9_-]{1,255}", codebuild_build_id)
        or not isinstance(region, str)
        or not re.fullmatch(r"[a-z]{2}(?:-[a-z0-9]+)+-\d", region)
        or credentials is None
    ):
        raise TerraformStateBootstrapError("trusted CodeBuild identity is incomplete")
    try:
        frozen_credentials = credentials.get_frozen_credentials()
        if not all(
            isinstance(value, str) and value
            for value in (
                frozen_credentials.access_key,
                frozen_credentials.secret_key,
                frozen_credentials.token,
            )
        ):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        raise TerraformStateBootstrapError("CodeBuild service-role credentials are unavailable") from None

    payload = json.dumps(
        {"run_id": durable_run_id, "codebuild_build_id": codebuild_build_id},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    aws_request = AWSRequest(
        method="POST",
        url=bootstrap_url,
        data=payload,
        headers={"content-type": "application/json"},
    )
    SigV4Auth(frozen_credentials, "execute-api", region).add_auth(aws_request)
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
                raise TerraformStateBootstrapError("state credential bootstrap was rejected")
            raw = response.read(MAX_BOOTSTRAP_RESPONSE_BYTES + 1)
    except TerraformStateBootstrapError:
        raise
    except (HTTPError, URLError, OSError, TimeoutError, TypeError, ValueError):
        raise TerraformStateBootstrapError("state credential bootstrap request failed") from None
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BOOTSTRAP_RESPONSE_BYTES:
        raise TerraformStateBootstrapError("state credential bootstrap response is invalid")
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise TerraformStateBootstrapError("state credential bootstrap response is invalid") from None
    return _validate_backend_document(document, expected_state_api_url=state_api_url)


def _validate_backend_document(
    document: Any, *, expected_state_api_url: str
) -> TerraformHTTPBackend:
    if not isinstance(document, dict):
        raise TerraformStateBootstrapError("state credential bootstrap response is invalid")
    state_id = document.get("state_id")
    try:
        if not isinstance(state_id, str) or str(UUID(state_id)) != state_id.lower():
            raise ValueError
    except (TypeError, ValueError):
        raise TerraformStateBootstrapError("state identity in bootstrap response is invalid") from None

    base = _https_origin(expected_state_api_url)
    if base is None:
        raise TerraformStateBootstrapError("trusted state API URL is invalid")
    expected_address = f"{base}/api/v1/terraform-state/{state_id}"
    address = document.get("address")
    lock_address = document.get("lock_address")
    unlock_address = document.get("unlock_address")
    if (
        address != expected_address
        or lock_address != f"{expected_address}/lock"
        or unlock_address != f"{expected_address}/unlock"
    ):
        raise TerraformStateBootstrapError("state backend addresses do not match the trusted API")
    username = document.get("username")
    password = document.get("password")
    scope_sha256 = document.get("scope_sha256")
    if (
        not isinstance(username, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{20,64}", username)
        or not isinstance(password, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{40,96}", password)
        or not isinstance(scope_sha256, str)
        or not re.fullmatch(r"[a-f0-9]{64}", scope_sha256)
    ):
        raise TerraformStateBootstrapError("short-lived state credentials are invalid")
    expires_value = document.get("expires_at")
    try:
        expires_at = datetime.fromisoformat(expires_value)
        if expires_at.tzinfo is None:
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        raise TerraformStateBootstrapError("state credential expiry is invalid") from None
    now = datetime.now(UTC)
    if not now < expires_at <= now + MAX_CREDENTIAL_TTL:
        raise TerraformStateBootstrapError("state credentials are expired or have an unsafe lifetime")
    return TerraformHTTPBackend(
        state_id=state_id,
        scope_sha256=scope_sha256,
        address=address,
        lock_address=lock_address,
        unlock_address=unlock_address,
        username=username,
        password=password,
        expires_at=expires_at,
    )


def _https_origin(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            return None
        port = parsed.port
    except ValueError:
        return None
    host = parsed.hostname.lower()
    return f"https://{host}:{port}" if port is not None else f"https://{host}"


def _valid_bootstrap_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return bool(
            parsed.scheme == "https"
            and parsed.hostname
            and parsed.username is None
            and parsed.password is None
            and parsed.path == "/api/v1/terraform-state/credentials"
            and not parsed.query
            and not parsed.fragment
            and parsed.port in {None, 443}
        )
    except ValueError:
        return False
