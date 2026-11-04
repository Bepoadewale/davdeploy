"""Nova-governed, revision-bound Terraform generation.

The generator produces a *plan-only* resource graph.  It has no filesystem,
shell, cloud credential, apply, or approval capability.  The caller must run
the generated JSON through normal policy, Terraform validation, saved-plan and
approval gates before an execution runner can use it.
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
    model_input_digest,
)


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
        """Return an untrusted typed proposal for a reviewed architecture context.

        A fixture/disabled gateway is intentionally rejected: a fixture cannot
        be represented as a real generated infrastructure definition.
        """
        target = approved_plan.get("target") or {}
        requirements = approved_plan.get("requirements") or {}
        region = str(target.get("region") or requirements.get("region") or "")
        if not region:
            raise ModelGatewayUnavailable("approved plan has no trusted AWS region")
        trusted_revision = (
            source_revision
            or str(approved_plan.get("revision_id") or approved_plan.get("revision") or "")
            or model_input_digest(approved_plan)
        )
        document = {
            "task": (
                "Generate the complete typed deployment proposal for this architecture. Use only "
                "typed resource_reference objects for links. Never author Terraform expressions, "
                "provider/backend configuration, modules, provisioners, shell commands, local file "
                "reads, credentials or secret values. Copy the trusted provenance and region below."
            ),
            "approved_plan": approved_plan,
            "trusted_generation_context": {
                "source_revision": trusted_revision,
                "region": region,
            },
        }
        context_digest = model_input_digest(document)
        document["trusted_generation_context"]["context_digest"] = context_digest
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
            raise ModelGatewayUnavailable("dynamic Terraform generation requires enabled Nova 2 Lite")
        try:
            proposal = GeneratedDeploymentProposal.model_validate(response.output)
        except ValidationError as error:
            raise ModelGatewayUnavailable("Nova Terraform proposal violated the generation schema") from error
        if proposal.source_revision != trusted_revision:
            raise ModelGatewayUnavailable("Nova proposal source revision did not match trusted input")
        if proposal.context_digest != context_digest:
            raise ModelGatewayUnavailable("Nova proposal context digest did not match trusted input")
        if proposal.requirements.region != region:
            raise ModelGatewayUnavailable("Nova proposal region did not match trusted input")
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
