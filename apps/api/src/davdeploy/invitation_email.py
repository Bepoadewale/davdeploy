"""Bounded workspace invitation delivery adapters."""

from __future__ import annotations

import html
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from urllib.parse import urlencode

import boto3
import httpx


class InvitationDeliveryUnavailable(RuntimeError):
    """Raised when an invitation was recorded but could not be delivered."""


@dataclass(frozen=True)
class InvitationDelivery:
    provider: str
    message_id: str
    execution: str


class InvitationEmailSender(Protocol):
    execution: str

    def send(
        self,
        *,
        email: str,
        role: str,
        token: str,
        workspace_name: str,
        expires_at: datetime,
    ) -> InvitationDelivery: ...


class FixtureInvitationEmailSender:
    """Deterministic local adapter that never contacts an email provider."""

    execution = "SIMULATED"

    def send(self, **_invitation) -> InvitationDelivery:
        return InvitationDelivery("fixture", "fixture-invitation-message", self.execution)


class DisabledInvitationEmailSender:
    execution = "DISABLED"

    def send(self, **_invitation) -> InvitationDelivery:
        raise InvitationDeliveryUnavailable("workspace invitation email delivery is not configured")


class SesInvitationEmailSender:
    """Send one transactional invitation through Amazon SES v2."""

    execution = "EXECUTED"

    def __init__(
        self,
        *,
        from_address: str,
        frontend_origin: str,
        region: str,
        client=None,
    ) -> None:
        if not from_address or not frontend_origin.startswith("https://"):
            raise ValueError("SES invitation delivery requires a sender and HTTPS frontend origin")
        self.from_address = from_address
        self.frontend_origin = frontend_origin.rstrip("/")
        self.client = client or boto3.client("sesv2", region_name=region)

    def send(
        self,
        *,
        email: str,
        role: str,
        token: str,
        workspace_name: str,
        expires_at: datetime,
    ) -> InvitationDelivery:
        invitation_url = f"{self.frontend_origin}/login?{urlencode({'invite': token})}"
        safe_workspace = html.escape(workspace_name)
        safe_role = html.escape(role)
        safe_url = html.escape(invitation_url, quote=True)
        expires = expires_at.strftime("%d %B %Y at %H:%M UTC")
        response = self.client.send_email(
            FromEmailAddress=self.from_address,
            Destination={"ToAddresses": [email]},
            Content={
                "Simple": {
                    "Subject": {"Data": f"Join {workspace_name} on DavDeploy", "Charset": "UTF-8"},
                    "Body": {
                        "Text": {
                            "Data": (
                                f"You were invited to join {workspace_name} as {role}.\n\n"
                                f"Accept invitation: {invitation_url}\n\n"
                                f"This invitation expires {expires}. If you did not expect it, "
                                "you can ignore this email."
                            ),
                            "Charset": "UTF-8",
                        },
                        "Html": {
                            "Data": (
                                "<h1>Join your DavDeploy workspace</h1>"
                                f"<p>You were invited to join <strong>{safe_workspace}</strong> "
                                f"as <strong>{safe_role}</strong>.</p>"
                                f'<p><a href="{safe_url}">Accept invitation</a></p>'
                                f"<p>This invitation expires {expires}. If you did not expect it, "
                                "you can ignore this email.</p>"
                            ),
                            "Charset": "UTF-8",
                        },
                    },
                }
            },
        )
        message_id = str(response.get("MessageId") or "")
        if not message_id:
            raise InvitationDeliveryUnavailable("Amazon SES did not return a message identifier")
        return InvitationDelivery("amazon_ses", message_id, self.execution)


class ResendInvitationEmailSender:
    """Send one transactional invitation through Resend's HTTPS API."""

    execution = "EXECUTED"

    def __init__(
        self,
        *,
        api_key: str,
        from_address: str,
        reply_to_address: str,
        frontend_origin: str,
        client: httpx.Client | None = None,
    ) -> None:
        if (
            not api_key
            or not from_address
            or not reply_to_address
            or not frontend_origin.startswith("https://")
        ):
            raise ValueError(
                "Resend invitation delivery requires an API key, sender, reply-to, and HTTPS frontend origin"
            )
        self.api_key = api_key
        self.from_address = from_address
        self.reply_to_address = reply_to_address
        self.frontend_origin = frontend_origin.rstrip("/")
        self.client = client or httpx.Client(timeout=10)

    def send(
        self,
        *,
        email: str,
        role: str,
        token: str,
        workspace_name: str,
        expires_at: datetime,
    ) -> InvitationDelivery:
        invitation_url = f"{self.frontend_origin}/login?{urlencode({'invite': token})}"
        safe_workspace = html.escape(workspace_name)
        safe_role = html.escape(role)
        safe_url = html.escape(invitation_url, quote=True)
        expires = expires_at.strftime("%d %B %Y at %H:%M UTC")
        payload = {
            "from": self.from_address,
            "to": [email],
            "reply_to": self.reply_to_address,
            "subject": f"Join {workspace_name} on DavDeploy",
            "text": (
                f"You were invited to join {workspace_name} as {role}.\n\n"
                f"Accept invitation: {invitation_url}\n\n"
                f"This invitation expires {expires}. If you did not expect it, you can ignore this email."
            ),
            "html": (
                "<h1>Join your DavDeploy workspace</h1>"
                f"<p>You were invited to join <strong>{safe_workspace}</strong> as "
                f"<strong>{safe_role}</strong>.</p>"
                f'<p><a href="{safe_url}">Accept invitation</a></p>'
                f"<p>This invitation expires {expires}. If you did not expect it, you can ignore this email.</p>"
            ),
        }
        try:
            response = self.client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            message_id = str(response.json().get("id") or "")
        except (httpx.HTTPError, ValueError) as error:
            raise InvitationDeliveryUnavailable(
                "Resend invitation email delivery failed"
            ) from error
        if not message_id:
            raise InvitationDeliveryUnavailable("Resend did not return a message identifier")
        return InvitationDelivery("resend", message_id, self.execution)


def configured_invitation_sender() -> InvitationEmailSender:
    if os.getenv("DAVDEPLOY_HOSTED_MODE", "false").lower() != "true":
        return FixtureInvitationEmailSender()
    provider = os.getenv("DAVDEPLOY_EMAIL_PROVIDER", "disabled")
    if provider == "resend":
        api_key = os.getenv("DAVDEPLOY_RESEND_API_KEY", "")
        from_address = os.getenv("DAVDEPLOY_RESEND_FROM_ADDRESS", "")
        reply_to_address = os.getenv("DAVDEPLOY_RESEND_REPLY_TO_ADDRESS", from_address)
        frontend_origin = os.getenv("DAVDEPLOY_FRONTEND_ORIGIN", "")
        if not api_key or not from_address or not reply_to_address or not frontend_origin:
            return DisabledInvitationEmailSender()
        return ResendInvitationEmailSender(
            api_key=api_key,
            from_address=from_address,
            reply_to_address=reply_to_address,
            frontend_origin=frontend_origin,
        )
    if provider != "ses":
        return DisabledInvitationEmailSender()
    from_address = os.getenv("DAVDEPLOY_SES_FROM_ADDRESS", "")
    frontend_origin = os.getenv("DAVDEPLOY_FRONTEND_ORIGIN", "")
    if not from_address or not frontend_origin:
        return DisabledInvitationEmailSender()
    return SesInvitationEmailSender(
        from_address=from_address,
        frontend_origin=frontend_origin,
        region=os.getenv("AWS_REGION", "us-east-1"),
    )
