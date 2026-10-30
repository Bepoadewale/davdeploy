"""Cloudflare-to-origin guard for the public control-plane API.

The token is retrieved from SSM only inside Lambda and is never a Terraform
input, a browser value, or a repository secret. An empty parameter name keeps
local development and the staged rollout path usable.
"""

from __future__ import annotations

import hmac
import os
from functools import lru_cache

import boto3


@lru_cache(maxsize=1)
def configured_origin_token() -> str | None:
    parameter_name = os.getenv("DAVDEPLOY_EDGE_ORIGIN_TOKEN_SSM_PARAMETER", "").strip()
    if not parameter_name:
        return None
    response = boto3.client("ssm").get_parameter(Name=parameter_name, WithDecryption=True)
    value = str(response.get("Parameter", {}).get("Value", ""))
    if not value:
        raise RuntimeError("edge origin token parameter is empty")
    return value


def edge_origin_is_authorized(header_value: str | None) -> bool:
    """Accept only the Worker-injected secret when the guard is configured."""
    expected = configured_origin_token()
    if expected is None:
        return True
    return bool(header_value) and hmac.compare_digest(header_value, expected)
