"""Nova-governed, revision-bound Terraform proposal generation.

Generated output remains plan-only. It cannot access credentials or execute
Terraform; trusted callers must validate a real saved plan before approval.
"""

from __future__ import annotations

import math
import re
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
    HEALTH_ASSERTION_TARGET_RESOURCE_TYPES,
    SECRET_REFERENCE_LOCATION_CATEGORIES,
    GeneratedDeploymentProposal,
    IncompatibleHealthTargetError,
    InvalidSecretReferenceLocationError,
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
    normalize_generated_resource_ids,
    normalize_managed_lambda_secret_reference,
    trusted_context,
    validate_generation_context,
)

_RESOURCE_CREDENTIAL_EXAMPLE = (
    "Supported database-secret shape (example only; include full required provider fields): "
    'declare an aws_rds_cluster resource with '
    '"arguments":{"manage_master_user_password":true} and '
    '"outputs":[{"name":"master_user_secret[0].secret_arn",'
    '"value_type":"secret_reference","sensitive":true}]. In an '
    'aws_lambda_function resource, put exactly this object at '
    '"arguments":{"environment":[{"variables":{"DATABASE_SECRET_ARN":'
    '{"kind":"resource_reference","resource_id":"db",'
    '"output_name":"master_user_secret[0].secret_arn",'
    '"value_type":"secret_reference"}}}]}. The referenced resource ID '
    "must be declared, and the output path and type must match exactly. "
    "Use this only for database credentials; omit secret outputs and variables "
    "when the application does not need them. Never put a secret value or ARN string in the proposal. "
)

_RESOURCE_NAME_GUIDANCE = (
    "The Terraform `name` is a local label, separate from `resource_id`. Use a `name` matching "
    "^[a-z][a-z0-9_]{0,62}$: lowercase letters, digits, and underscores only; no hyphens, "
    "uppercase, spaces, or punctuation. Keep the stable `resource_id` matching "
    "^[a-z][a-z0-9-]{0,23}$ with lowercase letters, digits, and optional hyphens. Valid pairs: "
    "resource_id=db-primary with name=primary_database; resource_id=job-queue with name=job_queue. "
    "Never copy a hyphenated resource_id into the Terraform `name` field."
)

_GENERIC_VALIDATION_GUIDANCE = (
    "The proposal did not match the typed deployment contract. Regenerate the complete proposal "
    "with every required field using its exact JSON type and an allowed value. Preserve the trusted "
    "revision, region, account, and context exactly; do not infer or change them."
)
_UNKNOWN_RESOURCE_FIELD_GUIDANCE = (
    "Correct the indicated resources[*] field to match the typed deployment contract. Use the exact "
    "JSON type and allowed value for that field; preserve the declared resource IDs and trusted context."
)
_RESOURCE_OBJECT_SHAPE_GUIDANCE = {
    "missing": (
        "Each resources[*] item must be a complete object with required fields "
        "resource_id, resource_type, name, arguments, and rationale. Only depends_on and outputs "
        "are optional. Preserve the selected architecture, resource identities, typed references, "
        "and trusted context."
    ),
    "extra_forbidden": (
        "Each resources[*] item may contain only resource_id, resource_type, name, arguments, "
        "depends_on, outputs, and rationale. Put AWS resource-specific attributes under arguments; "
        "remove wrapper or undeclared keys. Preserve the selected architecture, resource identities, "
        "typed references, and trusted context."
    ),
}
_UNKNOWN_ARGUMENTS_FIELD_GUIDANCE = (
    "Correct resources[*].arguments to match the selected AWS provider resource schema. Use literal "
    "JSON values only; never add Terraform expressions, credentials, provider/backend settings, "
    "provisioners, or file and shell operations."
)
_UNKNOWN_OUTPUT_FIELD_GUIDANCE = (
    "Correct the indicated resources[*].outputs field to the typed output contract. Use a unique "
    "output name, a supported value type, and a declared provider output path; secret references are "
    "allowed only for an RDS-managed master secret ARN."
)
_UNKNOWN_HEALTH_FIELD_GUIDANCE = (
    "Correct the indicated health_assertions[*] field to the selected assertion kind's typed schema. "
    "Use only supported fields and reference declared resource IDs. A proposed assertion is not "
    "evidence that a health check ran."
)
_HEALTH_PAYLOAD_SIZE_GUIDANCE = (
    "Set payload_size_bytes only on storage_roundtrip or queue_roundtrip, as an integer from 1 to "
    "4096 inclusive. Omit it for every other assertion kind. For http_response use max_response_bytes; "
    "for inference_response use minimum_response_bytes."
)
_ID_PATTERN_GUIDANCE = (
    "Treat resource IDs and references as short machine keys, not prose labels or AWS type names. "
    "Prefer IDs from "
    "this fixed vocabulary: api, web, app, db, files, bucket, table, queue, topic, events, worker, "
    "function, network, subnet, role, cache, logs. Declared resource IDs must be unique. For another "
    "resource with the same role, append a numeric suffix such as -2 or -3. Every ID must match "
    "^[a-z][a-z0-9-]{0,23}$: begin with a "
    "lowercase letter, use only lowercase letters, digits, and hyphens, and stay within 24 characters. "
    "Never use underscores, uppercase, spaces, dots, slashes, or long natural-language labels. Keep "
    "Terraform name as a separate snake_case local label; copy every reference exactly from its declared resource_id."
)
_UNKNOWN_COST_FIELD_GUIDANCE = (
    "Correct the indicated cost_assumptions[*] field to the typed cost schema. Reference a declared "
    "resource ID and report only supported usage assumptions; unknown prices must remain explicit."
)
_UNKNOWN_REQUIREMENTS_FIELD_GUIDANCE = (
    "Correct the indicated requirements field to its exact typed contract and allowed value. Preserve "
    "the trusted region, account, revision, and context."
)
_UNKNOWN_CONTRACT_FIELD_GUIDANCE = (
    "Correct the indicated contract field to its exact JSON type and allowed schema value. Regenerate "
    "the complete proposal while preserving all trusted context exactly."
)
_LAMBDA_CONTAINER_READINESS_GUIDANCE = (
    "`container_readiness` measures a container service and cannot target Lambda. Preserve the "
    "declared Lambda and the original application-health requirement. If the declared resource "
    "graph includes an API Gateway stage whose declared API integration is wired to this Lambda, "
    "use `http_response` targeting that stage to check the same HTTP behavior. If the requirement "
    "is processing queued work, use `event_processing` targeting the Lambda and the declared SQS "
    "source only when the graph already contains the matching SQS-to-Lambda event binding. Do "
    "not invent or add a service, remove or weaken an assertion, or label Lambda as a container. "
    "If no declared compatible path preserves the requirement, report that limitation."
)
_HEALTH_TARGET_PAIR_GUIDANCE = {
    ("container_readiness", "aws_lambda_function"): _LAMBDA_CONTAINER_READINESS_GUIDANCE,
}
_HEALTH_TARGET_COMPATIBILITY_GUIDANCE = (
    "Use a declared target resource type compatible with the assertion kind. Allowed types: "
    + "; ".join(
        f"{kind}: {', '.join(sorted(resource_types))}"
        for kind, resource_types in sorted(HEALTH_ASSERTION_TARGET_RESOURCE_TYPES.items())
    )
    + ". For database_roundtrip with relational SQL, target the declared aws_db_instance or "
    "aws_rds_cluster resource itself; do not target the API, worker, secret, network, or security "
    "group. These are typed proposals, not evidence that any check ran. "
    + _LAMBDA_CONTAINER_READINESS_GUIDANCE
)

NOVA_TERRAFORM_GENERATION_TASK = (
    "Generate the complete typed deployment proposal for this architecture and set "
    "contract_version to 1.1. Use only "
    "Terraform resource names that match `^[a-z][a-z0-9_]{0,62}$`; use lowercase "
    "letters, digits, and underscores only (for example, `api` or `primary_database`). "
    "Do not use hyphens, uppercase letters, spaces, or punctuation in resources[].name. "
    "The Terraform `name` is separate from `resource_id`: valid pairs include "
    "resource_id=db-primary with name=primary_database and resource_id=job-queue with "
    "name=job_queue. Never copy a hyphenated resource_id into resources[].name. "
    + _ID_PATTERN_GUIDANCE
    + " Use target_resource_id in every "
    "health assertion and source_resource_id only for event_processing; both must "
    "reference declared resources. Use typed resource_reference objects for links. Each "
    "resource arguments object may contain "
    "only literal JSON values for AWS provider resource attributes. Never add provider, "
    "provisioner, connection, backend, required_providers, access_key, secret_key, "
    "session_token, private_key, password, or user_data fields. Never author Terraform "
    "interpolation/directives, file reads, shell commands, credentials or secret values. "
    "Use a typed resource_reference for credentials only in a Lambda environment variable "
    "whose name ends with _SECRET_ARN. Its exact object shape is `kind=resource_reference`, "
    "`resource_id=<declared ID>`, `output_name=<declared secret output>`, and "
    "`value_type=secret_reference`; place it only at "
    "`environment[0].variables.<NAME>_SECRET_ARN`. Do not use a string ARN or secret value "
    "there. For database credentials, enable the AWS-managed master secret and expose its "
    "declared secret_reference output; never set password arguments. "
    + _RESOURCE_CREDENTIAL_EXAMPLE
    + "Omit all DavDeploy-"
    "prefixed tags because trusted code injects them. "
    "Health assertions are proposed requirements, "
    "not evidence that a check ran. Use only the enumerated health assertion kinds and "
    "their bounded schema fields. Use payload_size_bytes only for storage_roundtrip or "
    "queue_roundtrip, as an integer from 1 to 4096 inclusive; omit it for every other kind. "
    "For http_response use max_response_bytes; for inference_response use minimum_response_bytes. "
    + _HEALTH_TARGET_COMPATIBILITY_GUIDANCE
    + " "
    "Use only the fixed fixture IDs allowed by the schema; "
    "never invent URLs, hostnames, commands, headers, secrets or fixture IDs. "
    "Copy the trusted provenance and region below. "
    "If validation_feedback is present, it contains only fixed schema error codes, safe "
    "field paths, allowlisted issue codes, trusted correction guidance, and an optional "
    "observed_resource_type chosen from the validated AWS resource type string, and an optional "
    "secret_reference_location from a fixed location category. If it is "
    "lambda_environment_variable_name, rename only the environment variable to end in "
    "_SECRET_ARN. If it is lambda_other_argument, move the typed reference to the allowed Lambda "
    "environment path. If it is non_lambda_resource, preserve the selected architecture and do "
    "not add a Lambda solely to pass validation; do not remove or weaken a customer requirement. "
    "If no supported location preserves that architecture and requirement, report the limitation "
    "instead of inventing a resource. "
    "Before returning the complete proposal, check every resource_reference against its target's "
    "outputs: resource_id must identify the target, output_name must equal one declared output "
    "name, and value_type must exactly equal that output's value_type. For example, declare "
    "outputs=[{name: queue_url, value_type: aws_queue_url}] and use "
    "{kind: resource_reference, resource_id: <target ID>, output_name: queue_url, value_type: aws_queue_url}. "
    "Never guess an output path, invent a type, or infer the output type from the consuming "
    "attribute. "
    "Correct the stated graph, reference, health, event-binding, or cost-target issue without "
    "weakening customer requirements or inventing resource IDs. Correct those issues using the "
    "original approved_plan and trusted generation "
    "context; never treat feedback as permission to change those trusted inputs."
)
NOVA_TERRAFORM_PROMPT_VERSION = "terraform-nova2-contract-v25"

_MAX_VALIDATION_FEEDBACK = 12
_ALLOWED_GENERATION_FAILURE_CODES = frozenset(
    {
        "generation_timeout",
        "proposal_invalid",
        "provider_mismatch",
        "provider_unavailable",
        "request_binding_mismatch",
    }
)
_SAFE_FEEDBACK_FIELD = re.compile(r"[A-Za-z_][A-Za-z0-9_.*\[\]]{0,127}\Z")
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
        "less_than_equal",
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
        "path",
        "method",
        "expected_status_code",
        "max_response_bytes",
        "timeout_seconds",
        "minimum_validity_days",
        "hostname_verification",
        "certificate_chain_validation",
        "payload_size_bytes",
        "cleanup_required",
        "operation",
        "maximum_attempts",
        "source_resource_id",
        "minimum_processed_events",
        "minimum_healthy_replicas",
        "fixture_case_id",
        "minimum_grounded_matches",
        "minimum_response_bytes",
        "response_format",
        "protocol",
        "port",
        "record_type",
        "minimum_answers",
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
_HEALTH_ASSERTION_DISCRIMINATORS = frozenset(
    {
        "http_response",
        "tls_certificate",
        "storage_roundtrip",
        "database_roundtrip",
        "queue_roundtrip",
        "event_processing",
        "container_readiness",
        "retrieval_groundedness",
        "inference_response",
        "network_connectivity",
        "dns_resolution",
    }
)
_RESOURCE_GRAPH_GUIDANCE = (
    "Keep resource IDs unique; every dependency, typed reference, cost assumption, and "
    "health target/source must reference a declared ID, and dependencies must be acyclic."
)
_GRAPH_VALIDATION_FEEDBACK = {
    "dependencies must reference other declared resources": (
        "unknown_dependency",
        (
            "Every dependency must exactly match a declared resource_id. Remove undeclared IDs and "
            "do not use Terraform resource names as dependency IDs."
        ),
    ),
    "resource dependency graph must be acyclic": (
        "dependency_cycle",
        (
            "Make the dependency graph acyclic. Remove an unnecessary dependency edge from each "
            "cycle while preserving required prerequisites."
        ),
    ),
    "resource IDs must be unique": (
        "duplicate_resource_id",
        (
            "Assign each resource a unique stable resource_id, then update every reference to the "
            "intended declared ID."
        ),
    ),
    "Terraform resource addresses must be unique": (
        "duplicate_terraform_address",
        (
            "Give each resource a unique Terraform name within its resource type. Keep each stable "
            "resource_id separate from that local name."
        ),
    ),
    "references must target a declared resource": (
        "unknown_resource_reference",
        "Every typed resource_reference must target a declared resource_id and a declared output.",
    ),
    "reference must match a declared output type": (
        "reference_type_mismatch",
        (
            "For each typed reference, find the target resource's declared outputs entry whose "
            "name exactly equals output_name, then copy that entry's value_type exactly. For "
            "example, output {name: queue_url, value_type: aws_queue_url} pairs only with a reference "
            "{kind: resource_reference, resource_id: <target ID>, output_name: queue_url, "
            "value_type: aws_queue_url}. Do not infer a type from the destination field or guess an output "
            "path; if no declared, provider-schema-valid output exists, preserve the architecture "
            "and report the limitation."
        ),
    ),
    "health assertions must target declared resources": (
        "unknown_health_target",
        (
            "Every health assertion target_resource_id and source_resource_id must match a declared "
            "resource_id."
        ),
    ),
    "proposal assumptions and limitations must be bounded text": (
        "invalid_assumption_text",
        "Keep every assumption and limitation as plain text of at most 500 characters.",
    ),
    "secret_reference values may only populate a Lambda secret ARN environment variable": (
        "invalid_secret_reference_location",
        (
            "Use secret_reference values only in a Lambda environment variable whose name ends "
            "with _SECRET_ARN; use the declared resource ID and output name."
        ),
    ),
    "health assertion target resource type is incompatible": (
        "incompatible_health_target",
        _HEALTH_TARGET_COMPATIBILITY_GUIDANCE,
    ),
    "event probes must reference a declared source queue": (
        "unknown_event_source",
        "Set source_resource_id to the resource_id of a declared queue used by event processing.",
    ),
    "event probe source must be an SQS queue": (
        "unsupported_event_source",
        "Use an aws_sqs_queue resource as the source of an event_processing assertion.",
    ),
    "event probes require a declared SQS-to-Lambda event binding": (
        "missing_event_binding",
        (
            "Declare an aws_lambda_event_source_mapping that references both the source SQS queue "
            "and the target Lambda function."
        ),
    ),
    "cost assumptions must target declared resources": (
        "unknown_cost_resource",
        "Set each cost assumption resource_id to an ID declared in resources.",
    ),
}
_RESOURCE_ARGUMENT_GUIDANCE = (
    "Use only literal JSON values for AWS resource attributes. Remove provider, provisioner, "
    "connection, backend, required_providers, access_key, secret_key, session_token, "
    "private_key, password, and user_data fields."
)
_RESOURCE_EXPRESSION_GUIDANCE = (
    "Use literal JSON values only; remove Terraform interpolation, directives, file reads, "
    "template functions, and other expressions. Use typed resource_reference objects for links."
)
_RESOURCE_CREDENTIAL_GUIDANCE = (
    "Never include a credential, plaintext secret, or string ARN. Use the exact typed "
    "resource_reference shape only at environment[0].variables.<NAME>_SECRET_ARN on a Lambda "
    "resource. For database credentials, enable the AWS-managed master secret and reference "
    "its declared secret_reference output; never set a password argument. "
    + _RESOURCE_CREDENTIAL_EXAMPLE
)
_RESOURCE_RESERVED_TAG_GUIDANCE = (
    "Remove every tag whose key starts with DavDeploy. Trusted execution code adds the "
    "required ownership tags."
)
_RESOURCE_OUTPUT_GUIDANCE = (
    "Give every output a unique name. Use secret_reference outputs only on "
    "aws_db_instance or aws_rds_cluster with "
    "manage_master_user_password=true, and use the exact output name "
    "master_user_secret[0].secret_arn. Remove every other secret_reference output. "
    "A Lambda secret ARN environment reference must point to that declared output. "
    "Do not add resources or change the selected architecture to repair this output."
)
_SECRET_REFERENCE_LOCATION_GUIDANCE = {
    "non_lambda_resource": (
        "The secret reference is on a non-Lambda resource. Preserve the selected architecture; "
        "do not add a Lambda solely to pass validation or remove a customer requirement. Use the "
        "supported secret location only when an existing declared Lambda needs the credential."
    ),
    "lambda_environment_variable_name": (
        "Keep the declared Lambda and typed secret reference; rename only its environment variable "
        "so the name ends with _SECRET_ARN. Do not change the secret output or add a resource."
    ),
    "lambda_other_argument": (
        "Keep the declared Lambda and typed secret reference; move it only to "
        "environment[0].variables.<NAME>_SECRET_ARN. Do not change the secret output or add a resource."
    ),
}
_ALLOWED_FEEDBACK_GUIDANCE = frozenset(
    {
        _ID_PATTERN_GUIDANCE,
        _RESOURCE_NAME_GUIDANCE,
        _GENERIC_VALIDATION_GUIDANCE,
        _RESOURCE_GRAPH_GUIDANCE,
        _RESOURCE_ARGUMENT_GUIDANCE,
        _RESOURCE_EXPRESSION_GUIDANCE,
        _RESOURCE_CREDENTIAL_GUIDANCE,
        _RESOURCE_RESERVED_TAG_GUIDANCE,
        _RESOURCE_OUTPUT_GUIDANCE,
        *_SECRET_REFERENCE_LOCATION_GUIDANCE.values(),
        _HEALTH_PAYLOAD_SIZE_GUIDANCE,
        _UNKNOWN_RESOURCE_FIELD_GUIDANCE,
        *_RESOURCE_OBJECT_SHAPE_GUIDANCE.values(),
        _UNKNOWN_ARGUMENTS_FIELD_GUIDANCE,
        _UNKNOWN_OUTPUT_FIELD_GUIDANCE,
        _UNKNOWN_HEALTH_FIELD_GUIDANCE,
        _UNKNOWN_COST_FIELD_GUIDANCE,
        _UNKNOWN_REQUIREMENTS_FIELD_GUIDANCE,
        _UNKNOWN_CONTRACT_FIELD_GUIDANCE,
        _LAMBDA_CONTAINER_READINESS_GUIDANCE,
        *(guidance for _, guidance in _GRAPH_VALIDATION_FEEDBACK.values()),
    }
)
_ALLOWED_VALIDATION_ISSUES = frozenset(
    {
        "forbidden_argument_key",
        "terraform_expression",
        "credential_value",
        "reserved_ownership_tag",
        "duplicate_output_name",
        "unsupported_secret_output",
        "unknown_dependency",
        "dependency_cycle",
        "duplicate_resource_id",
        "duplicate_terraform_address",
        "unknown_resource_reference",
        "reference_type_mismatch",
        "unknown_health_target",
        *(issue for issue, _ in _GRAPH_VALIDATION_FEEDBACK.values()),
    }
)


class NovaTerraformGenerationFailed(ModelGatewayUnavailable):
    """Safe failure carrying bounded usage and validation evidence."""

    def __init__(
        self,
        message: str,
        *,
        attempt_count: int,
        usage: ModelUsage,
        evidence: tuple[EvidenceRef, ...],
        failure_code: str = "proposal_invalid",
        validation_feedback: tuple[dict[str, str], ...] = (),
        outcome_uncertain: bool = False,
    ):
        super().__init__(message, outcome_uncertain=outcome_uncertain)
        self.attempt_count = attempt_count
        self.usage = usage
        self.evidence = evidence
        self.failure_code = (
            failure_code
            if isinstance(failure_code, str)
            and failure_code in _ALLOWED_GENERATION_FAILURE_CODES
            else "proposal_invalid"
        )
        sanitized_feedback = []
        for item in validation_feedback[:_MAX_VALIDATION_FEEDBACK]:
            safe_invalid = (
                isinstance(item, dict)
                and item.get("code") == "invalid"
                and isinstance(item.get("field"), str)
                and _is_canonical_feedback_path(item["field"])
                and isinstance(item.get("guidance"), str)
                and item.get("guidance") in _ALLOWED_FEEDBACK_GUIDANCE
            )
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("code"), str)
                or not (
                    item.get("code") in _ALLOWED_PYDANTIC_ERROR_CODES
                    or item.get("code") == "trusted_context_mismatch"
                    or safe_invalid
                )
                or not isinstance(item.get("field"), str)
                or not _SAFE_FEEDBACK_FIELD.fullmatch(item["field"])
            ):
                continue
            sanitized = {"code": item["code"], "field": item["field"]}
            issue = item.get("issue")
            if isinstance(issue, str) and issue in _ALLOWED_VALIDATION_ISSUES:
                sanitized["issue"] = issue
            guidance = item.get("guidance")
            if isinstance(guidance, str) and guidance in _ALLOWED_FEEDBACK_GUIDANCE:
                sanitized["guidance"] = guidance
            assertion_kind = item.get("assertion_kind")
            if (
                isinstance(assertion_kind, str)
                and assertion_kind in HEALTH_ASSERTION_TARGET_RESOURCE_TYPES
            ):
                sanitized["assertion_kind"] = assertion_kind
            resource_type = item.get("observed_resource_type")
            if isinstance(resource_type, str) and re.fullmatch(
                r"aws_[a-z0-9_]{2,120}", resource_type
            ):
                sanitized["observed_resource_type"] = resource_type
            secret_location = item.get("secret_reference_location")
            if (
                isinstance(secret_location, str)
                and secret_location in SECRET_REFERENCE_LOCATION_CATEGORIES
            ):
                sanitized["secret_reference_location"] = secret_location
            sanitized_feedback.append(sanitized)
        self.validation_feedback = tuple(sanitized_feedback)


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
            prompt_version=NOVA_TERRAFORM_PROMPT_VERSION,
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
                    failure_code="provider_unavailable",
                    validation_feedback=feedback or [],
                    outcome_uncertain=error.outcome_uncertain,
                ) from None
            responses.append(response)
            if response.request.provider != "bedrock":
                raise _generation_failure(
                    "dynamic Terraform generation requires enabled Nova 2 Lite",
                    responses,
                    failure_code="provider_mismatch",
                ) from None
            if response.request.input_digest != request.input_digest:
                raise _generation_failure(
                    "Nova Terraform response did not match its bound request",
                    responses,
                    failure_code="request_binding_mismatch",
                ) from None
            if time.monotonic() > deadline:
                break

            try:
                normalized_output = normalize_generated_resource_ids(response.output)
                normalized_output = normalize_managed_lambda_secret_reference(normalized_output)
                proposal = GeneratedDeploymentProposal.model_validate(
                    normalized_output
                )
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
            failure_code="proposal_invalid" if feedback else "generation_timeout",
            validation_feedback=feedback or [],
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
    """Expose stable error codes, canonical schema paths, and fixed guidance."""

    feedback: list[dict[str, str]] = []
    for item in error.errors(
        include_url=False, include_context=True, include_input=False
    )[:_MAX_VALIDATION_FEEDBACK]:
        code = str(item.get("type") or "invalid")
        safe_code = code if code in _ALLOWED_PYDANTIC_ERROR_CODES else "invalid"
        safe_field = (
            _canonical_field_path(item.get("loc") or ())
        )
        entry = {"code": safe_code, "field": safe_field}
        context = item.get("ctx") or {}
        cause = context.get("error") if isinstance(context, dict) else None
        issue = _validation_issue(safe_code, safe_field, cause)
        if issue:
            entry["issue"] = issue
        guidance = _validation_guidance(safe_code, safe_field, cause)
        if guidance:
            entry["guidance"] = guidance
        feedback_field = safe_field
        if (
            safe_code == "value_error"
            and safe_field == "proposal"
            and isinstance(cause, IncompatibleHealthTargetError)
        ):
            feedback_field = "health_assertions[*].target_resource_id"
            assertion_kind = cause.assertion_kind
            resource_type = cause.resource_type
            if assertion_kind in HEALTH_ASSERTION_TARGET_RESOURCE_TYPES:
                entry["assertion_kind"] = assertion_kind
            if re.fullmatch(r"aws_[a-z0-9_]{2,120}", resource_type):
                entry["observed_resource_type"] = resource_type
            pair_guidance = _HEALTH_TARGET_PAIR_GUIDANCE.get(
                (assertion_kind, resource_type)
            )
            if pair_guidance:
                entry["guidance"] = pair_guidance
        if (
            safe_code == "value_error"
            and safe_field in {"proposal", "resources[*]"}
            and isinstance(cause, InvalidSecretReferenceLocationError)
        ):
            feedback_field = "resources[*].arguments"
            entry["issue"] = "invalid_secret_reference_location"
            location = cause.location
            if isinstance(location, str) and location in SECRET_REFERENCE_LOCATION_CATEGORIES:
                entry["guidance"] = _SECRET_REFERENCE_LOCATION_GUIDANCE[location]
                entry["secret_reference_location"] = location
            else:
                entry["guidance"] = _RESOURCE_CREDENTIAL_GUIDANCE
            if re.fullmatch(r"aws_[a-z0-9_]{2,120}", cause.resource_type):
                entry["observed_resource_type"] = cause.resource_type
        entry["field"] = feedback_field
        feedback.append(entry)
    return feedback or [{"code": "invalid", "field": "proposal"}]


_RESOURCE_ARGUMENT_FEEDBACK = {
    "generated arguments contain a forbidden field": (
        "forbidden_argument_key",
        _RESOURCE_ARGUMENT_GUIDANCE,
    ),
    "model-authored Terraform expressions are forbidden": (
        "terraform_expression",
        _RESOURCE_EXPRESSION_GUIDANCE,
    ),
    "credential and secret fields must use a typed secret_reference": (
        "credential_value",
        _RESOURCE_CREDENTIAL_GUIDANCE,
    ),
    "generated arguments cannot set reserved DavDeploy ownership tags": (
        "reserved_ownership_tag",
        _RESOURCE_RESERVED_TAG_GUIDANCE,
    ),
}
_RESOURCE_OUTPUT_FEEDBACK = {
    "generated output names must be unique": (
        "duplicate_output_name",
        _RESOURCE_OUTPUT_GUIDANCE,
    ),
    "secret_reference outputs must identify an RDS-managed master secret ARN": (
        "unsupported_secret_output",
        _RESOURCE_OUTPUT_GUIDANCE,
    ),
}


def _resource_feedback(code: str, field: str, cause: Any = None) -> tuple[str, str] | None:
    if code != "value_error" or field != "resources[*]" or not isinstance(cause, ValueError):
        return None
    return _RESOURCE_ARGUMENT_FEEDBACK.get(str(cause)) or _RESOURCE_OUTPUT_FEEDBACK.get(
        str(cause)
    )


def _validation_issue(code: str, field: str, cause: Any = None) -> str | None:
    result = _resource_feedback(code, field, cause)
    if result:
        return result[0]
    graph_feedback = _graph_feedback(code, field, cause)
    return graph_feedback[0] if graph_feedback else None


def _graph_feedback(code: str, field: str, cause: Any = None) -> tuple[str, str] | None:
    if code != "value_error" or field != "proposal" or not isinstance(cause, ValueError):
        return None
    return _GRAPH_VALIDATION_FEEDBACK.get(str(cause))


def _validation_guidance(code: str, field: str, cause: Any = None) -> str | None:
    if code == "invalid":
        return _unknown_validation_guidance(field)
    if field == "resources[*]" and code in _RESOURCE_OBJECT_SHAPE_GUIDANCE:
        return _RESOURCE_OBJECT_SHAPE_GUIDANCE[code]
    if code == "string_pattern_mismatch" and field == "resources[*].name":
        return _RESOURCE_NAME_GUIDANCE
    if (
        field == "health_assertions[*].payload_size_bytes"
        and code in {"extra_forbidden", "greater_than_equal", "less_than_equal"}
    ):
        return _HEALTH_PAYLOAD_SIZE_GUIDANCE
    identifier_fields = {
        "resources[*].resource_id",
        "health_assertions[*].target_resource_id",
        "health_assertions[*].source_resource_id",
        "cost_assumptions[*].resource_id",
    }
    if code == "string_pattern_mismatch" and field in identifier_fields:
        return _ID_PATTERN_GUIDANCE
    resource_feedback = _resource_feedback(code, field, cause)
    if resource_feedback:
        return resource_feedback[1]
    graph_feedback = _graph_feedback(code, field, cause)
    if graph_feedback:
        return graph_feedback[1]
    if code == "value_error" and field == "proposal" and isinstance(cause, ValueError):
        return _RESOURCE_GRAPH_GUIDANCE
    return None


def _unknown_validation_guidance(field: str) -> str:
    """Choose fixed guidance using only a canonical contract field path."""

    if field == "resources[*].name":
        return _RESOURCE_NAME_GUIDANCE
    if field in {
        "resources[*].resource_id",
        "health_assertions[*].target_resource_id",
        "health_assertions[*].source_resource_id",
        "cost_assumptions[*].resource_id",
    }:
        return _ID_PATTERN_GUIDANCE
    if field == "health_assertions[*].payload_size_bytes":
        return _HEALTH_PAYLOAD_SIZE_GUIDANCE
    if field == "resources[*].arguments" or field.startswith("resources[*].arguments."):
        return _UNKNOWN_ARGUMENTS_FIELD_GUIDANCE
    if field == "resources[*].outputs" or field.startswith("resources[*].outputs["):
        return _UNKNOWN_OUTPUT_FIELD_GUIDANCE
    if field.startswith("resources[*]."):
        return _UNKNOWN_RESOURCE_FIELD_GUIDANCE
    if field.startswith("health_assertions[*]."):
        return _UNKNOWN_HEALTH_FIELD_GUIDANCE
    if field.startswith("cost_assumptions[*]."):
        return _UNKNOWN_COST_FIELD_GUIDANCE
    if field.startswith("requirements."):
        return _UNKNOWN_REQUIREMENTS_FIELD_GUIDANCE
    if field == "proposal":
        return _GENERIC_VALIDATION_GUIDANCE
    return _UNKNOWN_CONTRACT_FIELD_GUIDANCE


def _canonical_field_path(location: Any) -> str:
    if not isinstance(location, (tuple, list)):
        return "proposal"
    parts: list[str] = []
    for part in location:
        if isinstance(part, int):
            if not parts or parts[-1] not in _LIST_FIELDS:
                break
            parts.append("[*]")
            continue
        if (
            isinstance(part, str)
            and part in _HEALTH_ASSERTION_DISCRIMINATORS
            and len(parts) >= 2
            and parts[-2:] == ["health_assertions", "[*]"]
        ):
            continue
        if not isinstance(part, str) or part not in _ALLOWED_PROPOSAL_FIELDS:
            break
        parts.append(part)
    if not parts:
        return "proposal"
    result = ".".join(parts)
    return result.replace(".[*]", "[*]")


def _is_canonical_feedback_path(field: str) -> bool:
    """Accept only field paths produced by the schema allowlist canonicalizer."""

    if not isinstance(field, str) or not _SAFE_FEEDBACK_FIELD.fullmatch(field):
        return False
    tokens = re.findall(r"\[\*\]|[A-Za-z_][A-Za-z0-9_]*", field)
    if not tokens:
        return False
    location = tuple(0 if token == "[*]" else token for token in tokens)
    return _canonical_field_path(location) == field


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
    failure_code: str = "proposal_invalid",
    validation_feedback: list[dict[str, str]] | None = None,
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
        failure_code=failure_code,
        validation_feedback=tuple(validation_feedback or ()),
        outcome_uncertain=outcome_uncertain,
    )
