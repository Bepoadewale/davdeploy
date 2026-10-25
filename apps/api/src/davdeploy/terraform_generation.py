"""Nova-governed, revision-bound Terraform generation.

The generator produces a *plan-only* resource graph.  It has no filesystem,
shell, cloud credential, apply, or approval capability.  The caller must run
the generated JSON through normal policy, Terraform validation, saved-plan and
approval gates before an execution runner can use it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from davdeploy.contracts import ModelPurpose, ModelRequest, ModelResponse, TenantScope
from davdeploy.model_gateway import (
    NOVA_2_LITE_MODEL_ID,
    ModelCallPolicy,
    ModelGateway,
    ModelGatewayUnavailable,
    configured_model_gateway,
    guarded_generate_structured,
    model_input_digest,
)


class GeneratedResource(BaseModel):
    """One provider resource in a generated Terraform JSON graph."""

    model_config = ConfigDict(extra="forbid")

    resource_type: str = Field(pattern=r"^aws_[a-z0-9_]{2,120}$")
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")
    arguments: dict[str, Any]
    rationale: str = Field(min_length=1, max_length=500)


class TerraformGenerationProposal(BaseModel):
    """The constrained Nova output; raw HCL and provider configuration are forbidden."""

    model_config = ConfigDict(extra="forbid")

    resources: list[GeneratedResource] = Field(min_length=1, max_length=40)
    assumptions: list[str] = Field(default_factory=list, max_length=30)
    limitations: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("resources")
    @classmethod
    def unique_resource_addresses(cls, value: list[GeneratedResource]) -> list[GeneratedResource]:
        addresses = {(item.resource_type, item.name) for item in value}
        if len(addresses) != len(value):
            raise ValueError("generated Terraform resource addresses must be unique")
        return value


@dataclass(frozen=True)
class TerraformGenerationResult:
    proposal: TerraformGenerationProposal
    response: ModelResponse


class NovaTerraformGenerator:
    """Generate a typed resource graph and enforce a fail-closed safety subset."""

    _FORBIDDEN_KEYS = frozenset(
        {
            "provider",
            "provisioner",
            "connection",
            "local-exec",
            "remote-exec",
            "access_key",
            "secret_key",
            "session_token",
            "private_key",
            "password",
            "master_password",
            "token",
            "user_data",
        }
    )

    def __init__(
        self,
        gateway: ModelGateway | None = None,
        model_id: str = NOVA_2_LITE_MODEL_ID,
        max_output_tokens: int = 6_000,
        timeout_seconds: int = 90,
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
    ) -> TerraformGenerationResult:
        """Return an untrusted typed proposal for an already approved plan.

        A fixture/disabled gateway is intentionally rejected: a fixture cannot
        be represented as a real generated infrastructure definition.
        """
        document = {
            "task": (
                "Generate a minimal AWS Terraform resource graph for this already-approved "
                "architecture. Return resources only: no provider blocks, modules, data sources, "
                "provisioners, user-data, credentials, secrets, shell commands, or apply steps. "
                "Every taggable resource must include arguments.tags.ManagedBy=davdeploy. "
                "Use references and approved secret ARNs, never secret values."
            ),
            "approved_plan": approved_plan,
        }
        request = ModelRequest(
            tenant=tenant,
            purpose=ModelPurpose.TERRAFORM_GENERATION,
            provider="bedrock",
            model=self.model_id,
            prompt_version="terraform-nova2-v1",
            input_digest=model_input_digest(document),
            timeout_seconds=self.timeout_seconds,
            max_output_tokens=self.max_output_tokens,
            data_policy=self.data_policy,
        )
        response = guarded_generate_structured(
            self.gateway,
            request,
            document,
            TerraformGenerationProposal.model_json_schema(),
            self.policy,
        )
        if response.request.provider != "bedrock":
            raise ModelGatewayUnavailable("dynamic Terraform generation requires enabled Nova 2 Lite")
        try:
            proposal = TerraformGenerationProposal.model_validate(response.output)
        except ValidationError as error:
            raise ModelGatewayUnavailable("Nova Terraform proposal violated the generation schema") from error
        self._validate_safety(proposal)
        return TerraformGenerationResult(proposal=proposal, response=response)

    def _validate_safety(self, proposal: TerraformGenerationProposal) -> None:
        for resource in proposal.resources:
            self._validate_value(resource.arguments)
            tags = resource.arguments.get("tags")
            if not isinstance(tags, dict) or tags.get("ManagedBy") != "davdeploy":
                raise ModelGatewayUnavailable(
                    f"{resource.resource_type}.{resource.name} is missing ManagedBy=davdeploy"
                )

    def _validate_value(self, value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if str(key).lower() in self._FORBIDDEN_KEYS:
                    raise ModelGatewayUnavailable(f"generated Terraform contains forbidden field {key!r}")
                self._validate_value(nested)
        elif isinstance(value, list):
            for nested in value:
                self._validate_value(nested)
        elif isinstance(value, str) and any(marker in value for marker in ("${file(", "${templatefile(")):
            raise ModelGatewayUnavailable("generated Terraform cannot read arbitrary local files")

    @staticmethod
    def terraform_json(proposal: TerraformGenerationProposal) -> dict[str, Any]:
        resources: dict[str, dict[str, Any]] = {}
        for item in proposal.resources:
            resources.setdefault(item.resource_type, {})[item.name] = item.arguments
        return {
            "terraform": {
                "required_version": ">= 1.6.0",
                "required_providers": {"aws": {"source": "hashicorp/aws", "version": "~> 5.0"}},
            },
            "resource": resources,
        }
