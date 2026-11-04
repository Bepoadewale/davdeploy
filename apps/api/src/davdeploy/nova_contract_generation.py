"""Bind Nova proposals to caller-owned revision and workload context."""

from __future__ import annotations

from typing import Any

from davdeploy.generated_deployment_contract import GeneratedDeploymentProposal
from davdeploy.model_gateway import ModelGatewayUnavailable, model_input_digest


def trusted_context(
    approved_plan: dict[str, Any], source_revision: str | None
) -> dict[str, str]:
    target = approved_plan.get("target") or {}
    requirements = approved_plan.get("requirements") or {}
    region = str(target.get("region") or requirements.get("region") or "")
    if not region:
        raise ModelGatewayUnavailable("approved plan has no trusted AWS region")
    revision = (
        source_revision
        or str(approved_plan.get("revision_id") or approved_plan.get("revision") or "")
        or model_input_digest(approved_plan)
    )
    return {"source_revision": revision, "region": region}


def bind_generation_context(
    document: dict[str, Any], context: dict[str, str]
) -> tuple[dict[str, Any], str]:
    """Add a digest over immutable trusted inputs before the model call."""
    bound = {**document, "trusted_generation_context": dict(context)}
    digest = model_input_digest(bound)
    bound["trusted_generation_context"]["context_digest"] = digest
    return bound, digest


def validate_generation_context(
    proposal: GeneratedDeploymentProposal, context: dict[str, str], digest: str
) -> None:
    if proposal.source_revision != context["source_revision"]:
        raise ModelGatewayUnavailable("Nova proposal source revision did not match trusted input")
    if proposal.context_digest != digest:
        raise ModelGatewayUnavailable("Nova proposal context digest did not match trusted input")
    if proposal.requirements.region != context["region"]:
        raise ModelGatewayUnavailable("Nova proposal region did not match trusted input")
