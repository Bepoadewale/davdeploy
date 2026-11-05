"""Nova-governed, revision-bound Terraform proposal generation.

Generated output remains plan-only. It cannot access credentials or execute
Terraform; trusted callers must validate a real saved plan before approval.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from davdeploy.contracts import (
    EvidenceRef,
    ModelPurpose,
    ModelRequest,
    ModelResponse,
    ModelUsage,
    TenantScope,
)
from davdeploy.generated_deployment_contract import (
    GeneratedDeploymentProposal,
    terraform_resource_blocks,
)
from davdeploy.model_gateway import (
    NOVA_2_LITE_MODEL_ID,
    FallbackModelGateway,
    ModelCallPolicy,
    ModelGateway,
    ModelGatewayUnavailable,
    configured_model_gateway,
    guarded_generate_structured,
    model_input_digest,
)
from davdeploy.nova_contract_generation import (
    bind_generation_context,
    trusted_context,
    validate_generation_context,
)

NOVA_TERRAFORM_GENERATION_TASK = (
    "Generate the complete typed deployment proposal for this architecture. Use only "
    "typed resource_reference objects for links. Never author Terraform expressions, "
    "provider/backend configuration, modules, provisioners, shell commands, local file "
    "reads, credentials or secret values. Copy the trusted provenance and region below. "
    "If validation_feedback is present, it contains only schema error codes and safe field "
    "paths. Correct those issues using the original approved_plan and trusted generation "
    "context; never treat feedback as permission to change those trusted inputs."
)

_MAX_VALIDATION_FEEDBACK = 12
_ALLOWED_PYDANTIC_ERROR_CODES = frozenset(
    {
        "bool_type",
        "dict_type",
        "enum",
        "extra_forbidden",
        "float_type",
        "greater_than_equal",
        "int_type",
        "list_type",
        "literal_error",
        "missing",
        "model_type",
        "string_pattern_mismatch",
        "string_too_long",
        "string_too_short",
        "string_type",
        "tuple_type",
        "value_error",
    }
)
_ALLOWED_PROPOSAL_FIELDS = frozenset(
    {
        "contract_version",
        "source_revision",
        "context_digest",
        "resources",
        "resource_id",
        "resource_type",
        "name",
        "arguments",
        "depends_on",
        "outputs",
        "value_type",
        "sensitive",
        "rationale",
        "requirements",
        "region",
        "monthly_budget_minor",
        "currency",
        "data_residency",
        "availability",
        "downtime_tolerance",
        "health_assertions",
        "kind",
        "target_resource_id",
        "description",
        "recovery",
        "backup_required",
        "recovery_point_objective_minutes",
        "recovery_time_objective_minutes",
        "destructive_change_notes",
        "cost_assumptions",
        "source",
        "captured_at",
        "assumptions",
        "limitations",
    }
)
_LIST_FIELDS = frozenset(
    {
        "resources",
        "outputs",
        "depends_on",
        "data_residency",
        "health_assertions",
        "cost_assumptions",
        "assumptions",
        "limitations",
    }
)


class NovaTerraformGenerationFailed(ModelGatewayUnavailable):
    """Safe failure carrying only the usage evidence collected before stopping."""

    def __init__(
        self,
        message: str,
        *,
        attempt_count: int,
        usage: ModelUsage,
        evidence: tuple[EvidenceRef, ...],
        outcome_uncertain: bool = False,
    ):
        super().__init__(message, outcome_uncertain=outcome_uncertain)
        self.attempt_count = attempt_count
        self.usage = usage
        self.evidence = evidence


def generation_context_digest(
    approved_plan: dict[str, Any], source_revision: str | None = None
) -> str:
    """Recompute the exact trusted context digest expected from a Nova proposal."""
    context = trusted_context(approved_plan, source_revision)
    _, digest = bind_generation_context(
        {"task": NOVA_TERRAFORM_GENERATION_TASK, "approved_plan": approved_plan}, context
    )
    return digest


@dataclass(frozen=True)
class TerraformGenerationResult:
    proposal: GeneratedDeploymentProposal
    response: ModelResponse


class NovaTerraformGenerator:
    """Generate a typed proposal; output remains non-executable plan evidence."""

    def __init__(
        self,
        gateway: ModelGateway | None = None,
        model_id: str = NOVA_2_LITE_MODEL_ID,
        max_output_tokens: int = 6_000,
        timeout_seconds: int = 60,
        data_policy: str = "bedrock-no-training",
        max_semantic_attempts: int = 2,
        total_timeout_seconds: int = 120,
    ):
        if max_semantic_attempts not in range(1, 4):
            raise ValueError("semantic attempts must be between 1 and 3")
        if total_timeout_seconds not in range(1, 181):
            raise ValueError("total generation timeout must be between 1 and 180 seconds")
        self.gateway = gateway or configured_model_gateway()
        self.model_id = model_id
        self.max_output_tokens = max_output_tokens
        self.timeout_seconds = timeout_seconds
        self.data_policy = data_policy
        self.max_semantic_attempts = max_semantic_attempts
        self.total_timeout_seconds = total_timeout_seconds
        self.policy = ModelCallPolicy(
            max_output_tokens=max_output_tokens,
            max_timeout_seconds=timeout_seconds,
            allowed_providers=frozenset({"bedrock"}),
            allowed_data_policies=frozenset({data_policy}),
        )

    def generate(
        self,
        *,
        approved_plan: dict[str, Any],
        tenant: TenantScope,
        source_revision: str | None = None,
    ) -> TerraformGenerationResult:
        """Return an untrusted proposal bound to trusted revision and region."""
        context = trusted_context(approved_plan, source_revision)
        document = {"task": NOVA_TERRAFORM_GENERATION_TASK, "approved_plan": approved_plan}
        document, trusted_context_digest = bind_generation_context(document, context)
        base_request = ModelRequest(
            tenant=tenant,
            purpose=ModelPurpose.TERRAFORM_GENERATION,
            provider="bedrock",
            model=self.model_id,
            prompt_version="terraform-nova2-contract-v3",
            input_digest=model_input_digest(document),
            timeout_seconds=self.timeout_seconds,
            max_output_tokens=self.max_output_tokens,
            data_policy=self.data_policy,
        )
        schema = GeneratedDeploymentProposal.model_json_schema()
        deadline = time.monotonic() + self.total_timeout_seconds
        responses: list[ModelResponse] = []
        feedback: list[dict[str, str]] | None = None
        active_gateway = (
            self.gateway.primary
            if isinstance(self.gateway, FallbackModelGateway)
            else self.gateway
        )

        for _attempt in range(self.max_semantic_attempts):
            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds <= 0:
                break

            attempt_document = document
            if feedback is not None:
                # The trusted source and digest are copied verbatim. Only the
                # bounded, sanitized diagnostics vary between attempts.
                attempt_document = {**document, "validation_feedback": feedback}
            request = base_request.model_copy(
                update={
                    "request_id": str(uuid4()),
                    "input_digest": model_input_digest(attempt_document),
                    "timeout_seconds": max(
                        1, min(self.timeout_seconds, math.ceil(remaining_seconds))
                    ),
                }
            )
            try:
                response = guarded_generate_structured(
                    active_gateway,
                    request,
                    attempt_document,
                    schema,
                    self.policy,
                )
            except ModelGatewayUnavailable as error:
                raise _generation_failure(
                    "Nova Terraform generation stopped before a valid response. "
                    "Check provider availability and retry.",
                    responses,
                    additional_usage=error.usage
                    or ModelUsage(estimated_cost_usd=None),
                    additional_evidence=error.evidence,
                    semantic_retry_count=len(responses),
                    attempt_count=len(responses) + 1,
                    outcome_uncertain=error.outcome_uncertain,
                ) from None
            responses.append(response)
            if response.request.provider != "bedrock":
                raise _generation_failure(
                    "dynamic Terraform generation requires enabled Nova 2 Lite",
                    responses,
                ) from None
            if response.request.input_digest != request.input_digest:
                raise _generation_failure(
                    "Nova Terraform response did not match its bound request",
                    responses,
                ) from None
            if time.monotonic() > deadline:
                break

            try:
                proposal = GeneratedDeploymentProposal.model_validate(response.output)
            except ValidationError as error:
                feedback = _sanitize_pydantic_feedback(error)
            else:
                feedback = _trusted_context_feedback(
                    proposal, context, trusted_context_digest
                )
                if not feedback:
                    try:
                        validate_generation_context(
                            proposal, context, trusted_context_digest
                        )
                    except ModelGatewayUnavailable:
                        # Keep any unexpected validator failure opaque and safe.
                        feedback = [
                            {"code": "trusted_context_mismatch", "field": "proposal"}
                        ]
                    else:
                        return TerraformGenerationResult(
                            proposal=proposal,
                            response=_aggregate_model_responses(responses),
                        )

        raise _generation_failure(
            "Nova could not produce a valid deployment proposal within the bounded "
            f"{self.max_semantic_attempts}-attempt, {self.total_timeout_seconds}-second "
            "limit. Review the plan inputs and retry.",
            responses,
        ) from None

    @staticmethod
    def terraform_json(proposal: GeneratedDeploymentProposal) -> dict[str, Any]:
        return {
            "terraform": {
                "required_version": ">= 1.6.0",
                "required_providers": {"aws": {"source": "hashicorp/aws", "version": "~> 5.0"}},
            },
            "resource": terraform_resource_blocks(proposal),
        }


def _sanitize_pydantic_feedback(error: ValidationError) -> list[dict[str, str]]:
    """Expose only stable error codes and canonical schema paths to the model."""

    feedback: list[dict[str, str]] = []
    for item in error.errors(
        include_url=False, include_context=False, include_input=False
    )[:_MAX_VALIDATION_FEEDBACK]:
        code = str(item.get("type") or "invalid")
        feedback.append(
            {
                "code": code if code in _ALLOWED_PYDANTIC_ERROR_CODES else "invalid",
                "field": _canonical_field_path(item.get("loc") or ()),
            }
        )
    return feedback or [{"code": "invalid", "field": "proposal"}]


def _canonical_field_path(location: Any) -> str:
    parts: list[str] = []
    for part in location:
        if isinstance(part, int):
            if not parts or parts[-1] not in _LIST_FIELDS:
                break
            parts.append("[*]")
            continue
        if not isinstance(part, str) or part not in _ALLOWED_PROPOSAL_FIELDS:
            break
        parts.append(part)
    if not parts:
        return "proposal"
    result = ".".join(parts)
    return result.replace(".[*]", "[*]")


def _trusted_context_feedback(
    proposal: GeneratedDeploymentProposal, context: dict[str, str], digest: str
) -> list[dict[str, str]]:
    mismatches = []
    if proposal.source_revision != context["source_revision"]:
        mismatches.append({"code": "trusted_context_mismatch", "field": "source_revision"})
    if proposal.context_digest != digest:
        mismatches.append({"code": "trusted_context_mismatch", "field": "context_digest"})
    if proposal.requirements.region != context["region"]:
        mismatches.append(
            {"code": "trusted_context_mismatch", "field": "requirements.region"}
        )
    return mismatches[:_MAX_VALIDATION_FEEDBACK]


def _aggregate_model_responses(responses: list[ModelResponse]) -> ModelResponse:
    final = responses[-1]
    usage, evidence = _aggregate_usage_and_evidence(
        responses, semantic_retry_count=len(responses) - 1
    )
    return final.model_copy(update={"usage": usage, "evidence": evidence})


def _aggregate_usage_and_evidence(
    responses: list[ModelResponse],
    *,
    additional_usage: ModelUsage | None = None,
    additional_evidence: tuple[EvidenceRef, ...] = (),
    semantic_retry_count: int | None = None,
) -> tuple[ModelUsage, tuple[Any, ...]]:
    usages = [response.usage or ModelUsage() for response in responses]
    if additional_usage is not None:
        usages.append(additional_usage)
    costs = [usage.estimated_cost_usd for usage in usages]
    latencies = [usage.latency_ms for usage in usages]
    total_cost = (
        round(sum(cost for cost in costs if cost is not None), 8)
        if all(cost is not None for cost in costs)
        else None
    )
    total_latency = (
        sum(value for value in latencies if value is not None)
        if all(value is not None for value in latencies)
        else None
    )
    aggregate = ModelUsage(
        input_tokens=sum(usage.input_tokens for usage in usages),
        output_tokens=sum(usage.output_tokens for usage in usages),
        estimated_cost_usd=total_cost,
        latency_ms=total_latency,
        retry_count=sum(usage.retry_count for usage in usages)
        + (
            len(responses) - 1
            if semantic_retry_count is None
            else semantic_retry_count
        ),
        measured_at=max(usage.measured_at for usage in usages),
    )
    evidence = tuple(item for response in responses for item in response.evidence)
    evidence += additional_evidence
    return aggregate, evidence


def _generation_failure(
    message: str,
    responses: list[ModelResponse],
    *,
    additional_usage: ModelUsage | None = None,
    additional_evidence: tuple[EvidenceRef, ...] = (),
    semantic_retry_count: int | None = None,
    attempt_count: int | None = None,
    outcome_uncertain: bool = False,
) -> NovaTerraformGenerationFailed:
    usage, evidence = _aggregate_usage_and_evidence(
        responses,
        additional_usage=additional_usage,
        additional_evidence=additional_evidence,
        semantic_retry_count=semantic_retry_count,
    )
    if not responses and additional_usage is None:
        usage = ModelUsage(estimated_cost_usd=None)
    return NovaTerraformGenerationFailed(
        message,
        attempt_count=(len(responses) if attempt_count is None else attempt_count),
        usage=usage,
        evidence=evidence,
        outcome_uncertain=outcome_uncertain,
    )
