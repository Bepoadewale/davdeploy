"""Bind Nova proposals to caller-owned revision and workload context."""

from __future__ import annotations

import copy
import hashlib
import re
from typing import Any

from davdeploy.generated_deployment_contract import GeneratedDeploymentProposal
from davdeploy.model_gateway import ModelGatewayUnavailable, model_input_digest

_RESOURCE_ID = re.compile(r"^[a-z][a-z0-9-]{0,23}$")
_SAFE_SOURCE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9 _.-]{0,63}$")
_SENSITIVE_SOURCE_ID = re.compile(
    r"(?i)(?:secret|password|credential|access.?key|session.?token|api.?token|arn)"
)
_ACCOUNT_NUMBER = re.compile(r"(?<!\d)\d{12}(?!\d)")


def normalize_generated_resource_ids(output: Any) -> Any:
    """Canonicalize malformed unique IDs and their exact graph references.

    This repairs only identifier spelling. Duplicate source identities and
    malformed output shapes are left untouched for strict contract validation.
    """
    if not isinstance(output, dict) or not isinstance(output.get("resources"), list):
        return output

    resources = output["resources"]
    source_ids: list[str] = []
    for resource in resources:
        if not isinstance(resource, dict) or not isinstance(resource.get("resource_id"), str):
            return output
        source_ids.append(resource["resource_id"])
    if len(source_ids) != len(set(source_ids)):
        return output
    if any(
        not _SAFE_SOURCE_ID.fullmatch(value)
        or _SENSITIVE_SOURCE_ID.search(value)
        or _ACCOUNT_NUMBER.search(value)
        for value in source_ids
        if not _RESOURCE_ID.fullmatch(value)
    ):
        return output

    valid_ids = {value for value in source_ids if _RESOURCE_ID.fullmatch(value)}
    invalid_ids = [value for value in source_ids if not _RESOURCE_ID.fullmatch(value)]
    slugs = {value: _resource_id_slug(value) for value in invalid_ids}
    slug_counts: dict[str, int] = {}
    for slug in slugs.values():
        slug_counts[slug] = slug_counts.get(slug, 0) + 1

    mapping = {value: value for value in valid_ids}
    occupied = set(valid_ids)
    for original in sorted(invalid_ids):
        slug = slugs[original]
        if slug_counts[slug] == 1 and slug not in occupied:
            canonical = slug
        else:
            canonical = _resource_id_with_suffix(slug, original, occupied)
        if canonical is None:
            # Fail closed. Pydantic will reject the original value without
            # returning it in the sanitized validation diagnostics.
            return output
        mapping[original] = canonical
        occupied.add(canonical)

    if all(mapping[value] == value for value in source_ids):
        return output

    normalized = copy.deepcopy(output)
    for resource, source_id in zip(normalized["resources"], source_ids, strict=True):
        resource["resource_id"] = mapping[source_id]
        dependencies = resource.get("depends_on")
        if isinstance(dependencies, list):
            resource["depends_on"] = [mapping.get(value, value) for value in dependencies]
        arguments = resource.get("arguments")
        if isinstance(arguments, (dict, list)):
            resource["arguments"] = _rewrite_typed_references(arguments, mapping)

    for assertion in normalized.get("health_assertions", []):
        if isinstance(assertion, dict):
            for field in ("target_resource_id", "source_resource_id"):
                value = assertion.get(field)
                if isinstance(value, str):
                    assertion[field] = mapping.get(value, value)
    for assumption in normalized.get("cost_assumptions", []):
        if isinstance(assumption, dict) and isinstance(assumption.get("resource_id"), str):
            value = assumption["resource_id"]
            assumption["resource_id"] = mapping.get(value, value)
    return normalized


def _resource_id_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    if not slug:
        slug = "resource"
    if not slug[0].isalpha():
        slug = f"r-{slug}"
    return slug[:24].rstrip("-") or "resource"


def _resource_id_with_suffix(slug: str, original: str, occupied: set[str]) -> str | None:
    digest = hashlib.sha256(original.encode("utf-8")).hexdigest()
    for length in (6, 8, 10, 12, 16, 24, 32, 48, 64):
        suffix = f"-{digest[:length]}"
        candidate = f"{slug[: 24 - len(suffix)].rstrip('-')}{suffix}"
        if candidate not in occupied and _RESOURCE_ID.fullmatch(candidate):
            return candidate
    return None


def _rewrite_typed_references(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, dict):
        is_reference = value.get("kind") == "resource_reference"
        rewritten = {}
        for key, nested in value.items():
            if is_reference and key == "resource_id" and isinstance(nested, str):
                rewritten[key] = mapping.get(nested, nested)
            else:
                rewritten[key] = _rewrite_typed_references(nested, mapping)
        return rewritten
    if isinstance(value, list):
        return [_rewrite_typed_references(item, mapping) for item in value]
    return value


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
