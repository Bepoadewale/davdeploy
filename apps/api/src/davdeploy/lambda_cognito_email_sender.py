"""Cognito custom-email sender that delivers one-time codes through Resend."""

from __future__ import annotations

import base64
import html
import os
from typing import Any

import aws_encryption_sdk
import httpx
from aws_encryption_sdk import CommitmentPolicy
from aws_encryption_sdk.key_providers.kms import StrictAwsKmsMasterKeyProvider

from davdeploy.invitation_email import _resend_api_key_from_environment


def _decrypt_code(ciphertext: str, key_arn: str) -> str:
    """Decrypt Cognito's AWS Encryption SDK ciphertext without logging the secret."""
    client = aws_encryption_sdk.EncryptionSDKClient(
        commitment_policy=CommitmentPolicy.REQUIRE_ENCRYPT_ALLOW_DECRYPT
    )
    key_provider = StrictAwsKmsMasterKeyProvider(key_ids=[key_arn])
    plaintext, _header = client.decrypt(
        source=base64.b64decode(ciphertext), key_provider=key_provider
    )
    return plaintext.decode("utf-8")


def _message(trigger_source: str, code: str) -> tuple[str, str, str]:
    if trigger_source in {"CustomEmailSender_SignUp", "CustomEmailSender_ResendCode"}:
        return (
            "Confirm your DavDeploy account",
            f"Your DavDeploy verification code is: {code}\n\nIt expires soon. If you did not request it, you can ignore this email.",
            f"<p>Your DavDeploy verification code is:</p><p><strong>{html.escape(code)}</strong></p><p>It expires soon. If you did not request it, you can ignore this email.</p>",
        )
    if trigger_source == "CustomEmailSender_Authentication":
        return (
            "Your DavDeploy sign-in code",
            f"Your DavDeploy sign-in code is: {code}\n\nIt expires soon. If you did not request it, you can ignore this email.",
            f"<p>Your DavDeploy sign-in code is:</p><p><strong>{html.escape(code)}</strong></p><p>It expires soon. If you did not request it, you can ignore this email.</p>",
        )
    if trigger_source == "CustomEmailSender_ForgotPassword":
        return (
            "Reset your DavDeploy password",
            f"Your DavDeploy password-reset code is: {code}\n\nIt expires soon. If you did not request it, you can ignore this email.",
            f"<p>Your DavDeploy password-reset code is:</p><p><strong>{html.escape(code)}</strong></p><p>It expires soon. If you did not request it, you can ignore this email.</p>",
        )
    return (
        "Your DavDeploy verification code",
        f"Your DavDeploy verification code is: {code}\n\nIt expires soon. If you did not request it, you can ignore this email.",
        f"<p>Your DavDeploy verification code is:</p><p><strong>{html.escape(code)}</strong></p><p>It expires soon. If you did not request it, you can ignore this email.</p>",
    )


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Send every Cognito email trigger through the configured Resend domain."""
    request = event.get("request") or {}
    email = (request.get("userAttributes") or {}).get("email")
    ciphertext = request.get("code")
    key_arn = os.getenv("DAVDEPLOY_COGNITO_EMAIL_KMS_KEY_ARN", "")
    api_key = _resend_api_key_from_environment()
    if not email or not ciphertext or not key_arn or not api_key:
        raise RuntimeError("Cognito email sender is not completely configured")
    code = _decrypt_code(str(ciphertext), key_arn)
    subject, text, body_html = _message(str(event.get("triggerSource", "")), code)
    response = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "from": os.getenv("DAVDEPLOY_RESEND_FROM_ADDRESS", "DavDeploy <notify@davdeploy.tech>"),
            "to": [email],
            "reply_to": os.getenv("DAVDEPLOY_RESEND_REPLY_TO_ADDRESS", "support@davdeploy.tech"),
            "subject": subject,
            "text": text,
            "html": body_html,
        },
        timeout=10,
    )
    response.raise_for_status()
    if not response.json().get("id"):
        raise RuntimeError("Resend did not return a message identifier")
    return event
