"""Nova-governed, revision-bound Terraform proposal generation.

Generated output remains plan-only. It cannot access credentials or execute
Terraform; trusted callers must validate a real saved plan before approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from davdeploy.contracts import ModelPurpose, ModelRequest, ModelResponse, TenantScope
from davdeploy.generated_deployment_contract import (
    GeneratedDeploymentProposal,
    terraform_resource_blocks,
)
from davdeploy.model_gateway import (
    NOVA_2_LITE_MODEL_ID,
    ModelCallPolicy,
    ModelGateway,
    ModelGatewayUnavailable,
    configured_model_gateway,
    guarded_generate_structured,
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
    "reads, credentials or secret values. Copy the trusted provenance and region below."
)


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
    ):
        self.gateway = gateway or configured_model_gateway()
        self.model_id = model_id
        self.max_output_tokens = max_output_tokens
        self.timeout_seconds = timeout_seconds
        self.data_policy = data_policy
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
        document, context_digest = bind_generation_context(document, context)
        request = ModelRequest(
            tenant=tenant,
            purpose=ModelPurpose.TERRAFORM_GENERATION,
            provider="bedrock",
            model=self.model_id,
            prompt_version="terraform-nova2-contract-v2",
            input_digest=context_digest,
            timeout_seconds=self.timeout_seconds,
            max_output_tokens=self.max_output_tokens,
            data_policy=self.data_policy,
        )
        response = guarded_generate_structured(
            self.gateway,
            request,
            document,
            GeneratedDeploymentProposal.model_json_schema(),
            self.policy,
        )
        if response.request.provider != "bedrock":
            raise ModelGatewayUnavailable(
                "dynamic Terraform generation requires enabled Nova 2 Lite"
            )
        try:
            proposal = GeneratedDeploymentProposal.model_validate(response.output)
        except ValidationError as error:
            raise ModelGatewayUnavailable(
                "Nova Terraform proposal violated the generation schema"
            ) from error
        validate_generation_context(proposal, context, context_digest)
        return TerraformGenerationResult(proposal=proposal, response=response)

    @staticmethod
    def terraform_json(proposal: GeneratedDeploymentProposal) -> dict[str, Any]:
        return {
            "terraform": {
                "required_version": ">= 1.6.0",
                "required_providers": {"aws": {"source": "hashicorp/aws", "version": "~> 5.0"}},
            },
            "resource": terraform_resource_blocks(proposal),
        }
