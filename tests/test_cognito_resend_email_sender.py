from __future__ import annotations

from types import SimpleNamespace

from davdeploy import lambda_cognito_email_sender as sender


def test_custom_cognito_email_sender_delivers_sign_up_code_with_resend(monkeypatch) -> None:
    sent: dict = {}
    monkeypatch.setenv("DAVDEPLOY_COGNITO_EMAIL_KMS_KEY_ARN", "arn:aws:kms:us-east-1:123:key/test")
    monkeypatch.setenv("DAVDEPLOY_RESEND_API_KEY", "re_test")
    monkeypatch.setenv("DAVDEPLOY_RESEND_FROM_ADDRESS", "DavDeploy <notify@davdeploy.tech>")
    monkeypatch.setenv("DAVDEPLOY_RESEND_REPLY_TO_ADDRESS", "support@davdeploy.tech")
    monkeypatch.setattr(sender, "_decrypt_code", lambda ciphertext, key_arn: "123456")

    def post(url, *, headers, json, timeout):
        sent.update(url=url, headers=headers, json=json, timeout=timeout)
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"id": "email-1"})

    monkeypatch.setattr(sender.httpx, "post", post)
    event = {
        "triggerSource": "CustomEmailSender_SignUp",
        "request": {"code": "encrypted", "userAttributes": {"email": "customer@example.com"}},
    }

    assert sender.handler(event, None) == event
    assert sent["url"] == "https://api.resend.com/emails"
    assert sent["headers"] == {"Authorization": "Bearer re_test"}
    assert sent["json"]["to"] == ["customer@example.com"]
    assert sent["json"]["subject"] == "Confirm your DavDeploy account"
    assert "123456" in sent["json"]["text"]


def test_custom_cognito_email_sender_uses_sign_in_copy() -> None:
    subject, text, body_html = sender._message("CustomEmailSender_Authentication", "654321")

    assert subject == "Your DavDeploy sign-in code"
    assert "654321" in text
    assert "654321" in body_html
