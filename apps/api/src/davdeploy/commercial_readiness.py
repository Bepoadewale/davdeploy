"""Customer commercial-readiness boundary for composed plans."""

from __future__ import annotations

from davdeploy.domain import CommercialReadiness


def commercial_readiness() -> CommercialReadiness:
    return CommercialReadiness(
        onboarding=["verified identity", "workspace membership", "connected cloud account"],
        support=["workspace support ticket", "support email", "incident/status guidance"],
        entitlement_state="WORKSPACE_SUBSCRIPTION_AND_USAGE_LIMITS_REQUIRED",
        billing_boundary="subscription records are product entitlements; payment collection requires a configured provider",
    )
