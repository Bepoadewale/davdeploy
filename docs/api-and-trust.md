# API and trust surfaces

The versioned HTTP API is documented interactively at `/docs` and as OpenAPI at
`/openapi.json`. All authenticated product APIs use `/api/v1` and emit
`X-davdeploy-API-Version: v1`.

## Local developer workflow

1. Use local fixture sign-in only in local mode.
2. Create a scoped API credential through `/api/v1/api-credentials`; its token
   is shown once and only its digest is persisted.
3. Revoke a credential through its tenant-scoped delete endpoint.
4. Use `/status`, `/healthz`, `/metrics`, and the self-hosted runbook for
   diagnostic and operational evidence.

## Privacy and consent

The data-lifecycle API creates audited tenant export/deletion requests. The
control plane does not claim automatic deletion until an operator-configured
retention backend is present. Terms, privacy notices, payment collection, and
identity-provider consent pages are legal/provider-owned content and must be
configured by the deploying organization before public sign-up.

## Security boundary

Bearer-token API use avoids browser-cookie CSRF exposure. CSP, anti-framing,
strict referrer, permissions and optional rate-limit protections are included.
The hosted control plane enforces a broad API Gateway limit and stricter route limits before
email delivery, model work, cloud verification, support-ticket creation, or API credential changes.
It also keeps a per-runtime fallback limit. The fallback is defense in depth only; Gateway limits
are the shared control. Repeated API 401, 403, and 429 responses, Cognito sign-in failures, and
Cognito sign-in throttling notify the operations topic.
