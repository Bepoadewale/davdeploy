from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

import boto3
import jwt
from fastapi import Header, HTTPException

from davdeploy.db import SessionLocal
from davdeploy.models import ProductUser


def local_signing_key() -> str:
    secret_arn = os.getenv("DAVDEPLOY_LOCAL_SIGNING_KEY_SECRET_ARN")
    if secret_arn:
        return str(boto3.client("secretsmanager").get_secret_value(SecretId=secret_arn)["SecretString"])
    return os.getenv("DAVDEPLOY_LOCAL_SIGNING_KEY", "local-development-only-change-me")


LOCAL_ISSUER = "davdeploy-local"
LOCAL_AUDIENCE = "davdeploy-api"


@dataclass(frozen=True)
class Principal:
    subject: str
    organization_id: str
    role: str
    email: str | None = None
    email_verified: bool = False


@dataclass(frozen=True)
class IdentityClaims:
    """Provider-verified identity before davdeploy membership resolution."""

    subject: str
    email: str | None = None
    email_verified: bool = False


class IdentityVerifier(Protocol):
    """Converts a trusted bearer token into a tenant-bound principal."""

    def verify(self, token: str) -> Principal: ...

    def verify_claims(self, token: str) -> IdentityClaims: ...


LOCAL_USERS = {
    "founder": ("user-founder", "org-demo", "developer"),
    "administrator": ("user-administrator", "org-demo", "administrator"),
    # Keep the earlier fixture so existing local execution evidence remains reproducible.
    "operator": ("user-operator", "org-demo", "operator"),
    "other-tenant": ("user-other", "org-other", "developer"),
}


def issue_local_token(username: str) -> str:
    if username not in LOCAL_USERS:
        raise HTTPException(401, "unknown local demo user")
    subject, organization_id, role = LOCAL_USERS[username]
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": subject,
            "org": organization_id,
            "role": role,
            "iss": LOCAL_ISSUER,
            "aud": LOCAL_AUDIENCE,
            "iat": now,
            "exp": now + timedelta(minutes=30),
        },
        local_signing_key(),
        algorithm="HS256",
    )


def principal_from_claims(payload: dict, *, server_membership: bool = False) -> Principal:
    if server_membership:
        with SessionLocal() as db:
            membership = db.query(ProductUser).filter(ProductUser.subject == payload["sub"]).one_or_none()
        if membership is None:
            raise HTTPException(403, "identity is not a member of an davdeploy workspace")
        return Principal(
            subject=membership.subject,
            organization_id=membership.organization_id,
            role=membership.role,
            email=payload.get("email"),
            email_verified=(
                payload.get("email_verified") is True
                or payload.get("email_verified") == "true"
            ),
        )
    role = payload["role"]
    if role not in {"developer", "operator", "administrator"}:
        raise HTTPException(403, "role not allowed")
    return Principal(subject=payload["sub"], organization_id=payload["org"], role=role)


class LocalIdentityVerifier:
    def verify_claims(self, token: str) -> IdentityClaims:
        payload = self._decode(token)
        return IdentityClaims(subject=payload["sub"])

    def verify(self, token: str) -> Principal:
        return principal_from_claims(self._decode(token))

    @staticmethod
    def _decode(token: str) -> dict:
        try:
            return jwt.decode(
                token,
                local_signing_key(),
                algorithms=["HS256"],
                issuer=LOCAL_ISSUER,
                audience=LOCAL_AUDIENCE,
                options={"require": ["sub", "org", "role", "exp"]},
            )
        except jwt.PyJWTError as error:
            raise HTTPException(401, "invalid signed identity") from error


class JwksIdentityVerifier:
    """Production adapter. It is not configured or called by the local demo."""

    def __init__(self, jwks_url: str, issuer: str, audience: str):
        self.client = jwt.PyJWKClient(jwks_url)
        self.issuer = issuer
        self.audience = audience

    def verify(self, token: str) -> Principal:
        return principal_from_claims(self._decode(token), server_membership=True)

    def verify_claims(self, token: str) -> IdentityClaims:
        payload = self._decode(token)
        verified = payload.get("email_verified") is True or payload.get("email_verified") == "true"
        return IdentityClaims(
            subject=payload["sub"],
            email=payload.get("email"),
            email_verified=verified,
        )

    def _decode(self, token: str) -> dict:
        try:
            key = self.client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                key.key,
                algorithms=["RS256", "ES256"],
                issuer=self.issuer,
                options={"require": ["sub", "exp"], "verify_aud": False},
            )
            token_audience = payload.get("aud", payload.get("client_id"))
            audiences = token_audience if isinstance(token_audience, list) else [token_audience]
            if self.audience not in audiences:
                raise jwt.InvalidAudienceError("token audience does not match")
            if "cognito-idp." in self.issuer and payload.get("token_use") != "id":
                raise jwt.InvalidTokenError("Cognito identity token is required")
        except jwt.PyJWTError as error:
            raise HTTPException(401, "invalid trusted identity") from error
        return payload


def configured_verifier() -> IdentityVerifier:
    jwks_url = os.getenv("DAVDEPLOY_JWKS_URL")
    if jwks_url:
        issuer = os.environ["DAVDEPLOY_OIDC_ISSUER"]
        audience = os.environ["DAVDEPLOY_OIDC_AUDIENCE"]
        return JwksIdentityVerifier(jwks_url, issuer, audience)
    if os.getenv("DAVDEPLOY_HOSTED_MODE", "false").lower() == "true":
        raise HTTPException(503, "hosted identity is not configured; JWKS/OIDC settings are required")
    return LocalIdentityVerifier()


def verify_token(authorization: str = Header(...)) -> Principal:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "bearer token required")
    return configured_verifier().verify(authorization.removeprefix("Bearer "))


def verify_identity_token(authorization: str = Header(...)) -> IdentityClaims:
    """Verify provider identity without granting tenant or role authority."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "bearer token required")
    return configured_verifier().verify_claims(authorization.removeprefix("Bearer "))


def verify_local_token_for_test(authorization: str) -> Principal:
    """Compatibility helper for fast local tests."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "bearer token required")
    try:
        payload = jwt.decode(
            authorization.removeprefix("Bearer "),
            local_signing_key(),
            algorithms=["HS256"],
            issuer=LOCAL_ISSUER,
            audience=LOCAL_AUDIENCE,
            options={"require": ["sub", "org", "role", "exp"]},
        )
    except jwt.PyJWTError as error:
        raise HTTPException(401, "invalid signed identity") from error
    return principal_from_claims(payload)
