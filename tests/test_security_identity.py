from __future__ import annotations

import pytest
from davdeploy import security
from fastapi import HTTPException


class Membership:
    subject = "user-external"
    organization_id = "org-server"
    role = "developer"


class FakeQuery:
    def filter(self, *_args):
        return self

    def one_or_none(self):
        return Membership()


class FakeDb:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def query(self, *_args):
        return FakeQuery()


def test_external_identity_uses_server_membership_not_claimed_org_or_role(monkeypatch):
    monkeypatch.setattr(security, "SessionLocal", lambda: FakeDb())

    principal = security.principal_from_claims(
        {
            "sub": "user-external",
            "org": "attacker-org",
            "role": "administrator",
        },
        server_membership=True,
    )

    assert principal.subject == "user-external"
    assert principal.organization_id == "org-server"
    assert principal.role == "developer"


def test_external_identity_without_server_membership_is_denied(monkeypatch):
    class EmptyDb(FakeDb):
        def query(self, *_args):
            return type("EmptyQuery", (), {"filter": lambda self, *_: self, "one_or_none": lambda self: None})()

    monkeypatch.setattr(security, "SessionLocal", lambda: EmptyDb())

    with pytest.raises(HTTPException) as error:
        security.principal_from_claims({"sub": "unknown"}, server_membership=True)

    assert error.value.status_code == 403


def test_hosted_mode_requires_jwks_configuration(monkeypatch):
    monkeypatch.setenv("DAVDEPLOY_HOSTED_MODE", "true")
    monkeypatch.delenv("DAVDEPLOY_JWKS_URL", raising=False)
    monkeypatch.delenv("DAVDEPLOY_OIDC_ISSUER", raising=False)

    with pytest.raises(HTTPException) as error:
        security.configured_verifier()

    assert error.value.status_code == 503


def test_cognito_issuer_derives_standard_jwks_url(monkeypatch):
    observed = {}

    class CaptureVerifier:
        def __init__(self, jwks_url, issuer, audience):
            observed.update(jwks_url=jwks_url, issuer=issuer, audience=audience)

    monkeypatch.setenv("DAVDEPLOY_HOSTED_MODE", "true")
    monkeypatch.setenv(
        "DAVDEPLOY_OIDC_ISSUER",
        "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_example",
    )
    monkeypatch.setenv("DAVDEPLOY_OIDC_AUDIENCE", "frontend-client")
    monkeypatch.delenv("DAVDEPLOY_JWKS_URL", raising=False)
    monkeypatch.setattr(security, "JwksIdentityVerifier", CaptureVerifier)

    security.configured_verifier()

    assert observed == {
        "jwks_url": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_example/.well-known/jwks.json",
        "issuer": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_example",
        "audience": "frontend-client",
    }


def test_explicit_jwks_url_remains_authoritative_for_other_oidc(monkeypatch):
    observed = {}

    class CaptureVerifier:
        def __init__(self, jwks_url, issuer, audience):
            observed.update(jwks_url=jwks_url, issuer=issuer, audience=audience)

    monkeypatch.setenv("DAVDEPLOY_HOSTED_MODE", "true")
    monkeypatch.setenv("DAVDEPLOY_OIDC_ISSUER", "https://identity.example.test/issuer")
    monkeypatch.setenv("DAVDEPLOY_OIDC_AUDIENCE", "frontend-client")
    monkeypatch.setenv("DAVDEPLOY_JWKS_URL", "https://identity.example.test/keys.json")
    monkeypatch.setattr(security, "JwksIdentityVerifier", CaptureVerifier)

    security.configured_verifier()

    assert observed == {
        "jwks_url": "https://identity.example.test/keys.json",
        "issuer": "https://identity.example.test/issuer",
        "audience": "frontend-client",
    }
