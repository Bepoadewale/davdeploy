from davdeploy import main
from davdeploy.product_readiness import security_headers
from davdeploy.rate_limit import SlidingWindowRateLimiter
from fastapi.testclient import TestClient


def test_optional_rate_limit_and_security_headers_are_explicit():
    limiter = SlidingWindowRateLimiter(limit=2)
    assert limiter.allow("tenant-a") is True
    assert limiter.allow("tenant-a") is True
    assert limiter.allow("tenant-a") is False
    headers = security_headers()
    assert "Content-Security-Policy" in headers
    assert headers["X-Frame-Options"] == "DENY"


def test_application_rate_limit_returns_a_safe_retryable_response(monkeypatch):
    monkeypatch.setattr(main, "RATE_LIMIT", SlidingWindowRateLimiter(limit=1))
    client = TestClient(main.app)

    assert client.get("/status").status_code == 200
    limited = client.get("/status")

    assert limited.status_code == 429
    assert limited.json() == {"detail": "rate limit exceeded"}
    assert limited.headers["retry-after"] == "60"
