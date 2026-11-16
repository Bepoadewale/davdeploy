"""Emit a value-free, bounded summary of the hosted control-plane plan."""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from typing import Any

MAX_PLAN_JSON_BYTES = 64 * 1024 * 1024
MAX_SUMMARY_RESOURCES = 250
MAX_CHANGED_FIELDS = 64
MAX_POLICY_DETAILS = 128
MAX_POLICY_TEXT = 4096
MAX_OUTPUT_DETAILS = 128
SAFE_ADDRESS = re.compile(r"[A-Za-z0-9_.\[\]-]{1,512}\Z")
SAFE_RESOURCE_TYPE = re.compile(r"[A-Za-z0-9_]{1,128}\Z")
SAFE_FIELD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}\Z")
SAFE_VARIABLE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,127}\Z")
SAFE_OUTPUT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_-]{0,127}\Z")
SAFE_POLICY_ACTION = re.compile(r"[A-Za-z0-9-]+:[A-Za-z0-9*]+\Z")
SAFE_POLICY_VALUE = re.compile(r"[A-Za-z0-9:_./*?+=,-]{1,512}\Z")
SAFE_POLICY_KEY = re.compile(r"[A-Za-z0-9:_./-]{1,256}\Z")
SAFE_POLICY_OPERATOR = re.compile(r"[A-Za-z0-9:_-]{1,128}\Z")
SAFE_TERRAFORM_VERSION = re.compile(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?\Z")
ALLOWED_ACTIONS = {"create", "read", "update", "delete", "no-op"}
CODEBUILD_BOOLEAN_VARIABLES = {
    "TF_VAR_enable_nova_plan_reviews",
    "TF_VAR_enable_nova_plan_role_verification",
    "TF_VAR_enable_nova_plan_credential_broker",
    "TF_VAR_enable_nova_plan_only_runner",
    "TF_VAR_enable_nova_terraform_state_storage",
    "TF_VAR_enable_nova_terraform_state_api",
    "TF_VAR_enable_nova_exact_plan_apply_runner",
    "TF_VAR_enable_serverless_api_hosted_certification",
    "TF_VAR_enable_customer_cloud_execution",
}
FLAG_NAMES = (
    "DAVDEPLOY_NOVA_PLAN_RUNNER_READY",
    "DAVDEPLOY_NOVA_PLAN_ROLE_VERIFY_ENABLED",
    "DAVDEPLOY_NOVA_PLAN_CREDENTIAL_BROKER_ENABLED",
    "DAVDEPLOY_NOVA_PLAN_REVIEWS_ENABLED",
    "DAVDEPLOY_TERRAFORM_STATE_ENABLED",
    "DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION",
    "DAVDEPLOY_CLOUD_EXECUTION_COMMAND_ENABLED",
    "ALLOW_CLOUD_PLAN",
    "ALLOW_CLOUD_APPLY",
)
RUNTIME_GATE_VARIABLES = {
    "DAVDEPLOY_NOVA_PLAN_RUNNER_READY": "enable_nova_plan_only_runner",
    "DAVDEPLOY_NOVA_PLAN_ROLE_VERIFY_ENABLED": "enable_nova_plan_role_verification",
    "DAVDEPLOY_NOVA_PLAN_CREDENTIAL_BROKER_ENABLED": "enable_nova_plan_credential_broker",
    "DAVDEPLOY_NOVA_PLAN_REVIEWS_ENABLED": "enable_nova_plan_reviews",
    "DAVDEPLOY_TERRAFORM_STATE_ENABLED": "enable_nova_terraform_state_api",
    "DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION": "enable_serverless_api_hosted_certification",
    "DAVDEPLOY_CLOUD_EXECUTION_COMMAND_ENABLED": "enable_customer_cloud_execution",
    "ALLOW_CLOUD_PLAN": "enable_customer_cloud_execution",
    "ALLOW_CLOUD_APPLY": "enable_customer_cloud_execution",
}
SAFE_FAILURE_CODES = {
    "plan JSON exceeds the configured size limit": "plan_json_too_large",
    "plan JSON root is not an object": "invalid_plan_root",
    "plan is incomplete, not applyable, or has errors": "plan_not_applyable",
    "resource changes are missing": "resource_changes_missing",
    "invalid resource change entry": "invalid_resource_change_entry",
    "invalid resource change metadata": "invalid_resource_change_metadata",
    "invalid resource action metadata": "invalid_resource_actions",
    "resource drift metadata is invalid": "invalid_resource_drift",
    "output change metadata is invalid": "invalid_output_changes",
    "output change action metadata is invalid": "invalid_output_actions",
    "plan policy summary metadata is invalid": "invalid_policy_summary",
    "CodeBuild environment summary metadata is invalid": "invalid_codebuild_environment_summary",
    "runtime feature gate is not a literal boolean": "runtime_gate_not_boolean",
    "required runtime feature gates are missing": "runtime_gates_missing",
    "runtime feature gates disagree across functions": "runtime_gate_disagreement",
}


class PlanSummaryError(ValueError):
    """Raised when a plan cannot be summarized without making assumptions."""

    def __init__(
        self,
        message: str,
        *,
        missing_gates: tuple[str, ...] = (),
        gate_shape: tuple[tuple[str, int], ...] = (),
        gate_names: tuple[tuple[str, tuple[str, ...]], ...] = (),
    ):
        super().__init__(message)
        self.missing_gates = missing_gates
        self.gate_shape = gate_shape
        self.gate_names = gate_names


def _safe_address(value: Any) -> str:
    if isinstance(value, str) and SAFE_ADDRESS.fullmatch(value):
        return value
    return "redacted-address"


def _resource_actions(change: dict[str, Any]) -> list[str]:
    actions = change.get("actions")
    if not isinstance(actions, list) or not all(
        isinstance(action, str) and action in ALLOWED_ACTIONS for action in actions
    ):
        raise PlanSummaryError("invalid resource action metadata")
    if (
        not actions
        or len(actions) > 2
        or len(set(actions)) != len(actions)
        or (len(actions) == 2 and set(actions) != {"create", "delete"})
    ):
        raise PlanSummaryError("invalid resource action metadata")
    return actions


def _changed_fields(change: dict[str, Any]) -> list[str]:
    before = change.get("before")
    after = change.get("after")
    before = before if isinstance(before, dict) else {}
    after = after if isinstance(after, dict) else {}
    fields = [
        key
        for key in before.keys() | after.keys()
        if isinstance(key, str) and SAFE_FIELD.fullmatch(key) and before.get(key) != after.get(key)
    ]
    return sorted(fields)[:MAX_CHANGED_FIELDS]


def _policy_entries(value: Any) -> list[tuple[str, Any]]:
    """Extract IAM policy documents without returning their raw values."""
    if value is None:
        return []
    if isinstance(value, str):
        try:
            return [("", json.loads(value))]
        except (json.JSONDecodeError, RecursionError):
            raise PlanSummaryError("plan policy summary metadata is invalid") from None
    if isinstance(value, dict):
        return [("", value)]
    if isinstance(value, list):
        if len(value) > MAX_POLICY_DETAILS:
            raise PlanSummaryError("plan policy summary metadata is invalid")
        entries: list[tuple[str, Any]] = []
        for item in value:
            if not isinstance(item, dict) or "policy" not in item:
                raise PlanSummaryError("plan policy summary metadata is invalid")
            name = item.get("name", "")
            if name and (not isinstance(name, str) or not SAFE_VARIABLE_NAME.fullmatch(name)):
                raise PlanSummaryError("plan policy summary metadata is invalid")
            nested = _policy_entries(item.get("policy"))
            entries.extend((name, policy) for _, policy in nested)
        return entries
    raise PlanSummaryError("plan policy summary metadata is invalid")


def _policy_values(value: Any, *, field: str) -> list[str]:
    if value is None:
        return []
    items = [value] if isinstance(value, str) else value
    if not isinstance(items, list) or len(items) > MAX_POLICY_DETAILS:
        raise PlanSummaryError("plan policy summary metadata is invalid")
    pattern = SAFE_POLICY_ACTION if field.endswith("Action") else SAFE_POLICY_VALUE
    result = []
    for item in items:
        if not isinstance(item, str) or not pattern.fullmatch(item):
            raise PlanSummaryError("plan policy summary metadata is invalid")
        if field.endswith("Resource"):
            item = re.sub(r"(?<=:)\d{12}(?=:)", "ACCOUNT", item)
        result.append(item)
    return sorted(set(result))


def _principal_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, dict):
        values = []
        for key, nested in value.items():
            if not isinstance(key, str) or not SAFE_FIELD.fullmatch(key):
                raise PlanSummaryError("plan policy summary metadata is invalid")
            values.extend([nested] if isinstance(nested, str) else nested if isinstance(nested, list) else [])
            if not isinstance(nested, (str, list)):
                raise PlanSummaryError("plan policy summary metadata is invalid")
    elif isinstance(value, list):
        values = value
    else:
        raise PlanSummaryError("plan policy summary metadata is invalid")
    if len(values) > MAX_POLICY_DETAILS:
        raise PlanSummaryError("plan policy summary metadata is invalid")
    result = []
    for item in values:
        if not isinstance(item, str) or not SAFE_POLICY_VALUE.fullmatch(item):
            raise PlanSummaryError("plan policy summary metadata is invalid")
        result.append(re.sub(r"(?<=:)\d{12}(?=:)", "ACCOUNT", item))
    return sorted(set(result))


def _condition_keys(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, dict) or len(value) > MAX_POLICY_DETAILS:
        raise PlanSummaryError("plan policy summary metadata is invalid")
    result = []
    for operator, conditions in value.items():
        if not isinstance(operator, str) or not SAFE_POLICY_OPERATOR.fullmatch(operator):
            raise PlanSummaryError("plan policy summary metadata is invalid")
        if not isinstance(conditions, dict) or len(conditions) > MAX_POLICY_DETAILS:
            raise PlanSummaryError("plan policy summary metadata is invalid")
        for key in conditions:
            if not isinstance(key, str) or not SAFE_POLICY_KEY.fullmatch(key):
                raise PlanSummaryError("plan policy summary metadata is invalid")
            result.append(f"{operator}:{key}")
    return sorted(set(result))


def _policy_line(address: str, side: str, name: str, document: Any) -> str:
    if not isinstance(document, dict):
        raise PlanSummaryError("plan policy summary metadata is invalid")
    statements = document.get("Statement")
    if isinstance(statements, dict):
        statements = [statements]
    if not isinstance(statements, list) or len(statements) > MAX_POLICY_DETAILS:
        raise PlanSummaryError("plan policy summary metadata is invalid")
    effects: set[str] = set()
    actions: set[str] = set()
    resources: set[str] = set()
    principals: set[str] = set()
    condition_keys: set[str] = set()
    for statement in statements:
        if not isinstance(statement, dict):
            raise PlanSummaryError("plan policy summary metadata is invalid")
        effect = statement.get("Effect")
        if effect not in {"Allow", "Deny"}:
            raise PlanSummaryError("plan policy summary metadata is invalid")
        effects.add(effect)
        for field, destination in (
            ("Action", actions),
            ("NotAction", actions),
            ("Resource", resources),
            ("NotResource", resources),
        ):
            destination.update(_policy_values(statement.get(field), field=field))
        principals.update(_principal_values(statement.get("Principal")))
        principals.update(_principal_values(statement.get("NotPrincipal")))
        condition_keys.update(_condition_keys(statement.get("Condition")))
    parts = [
        f"policy_detail address={address} side={side}",
        f"name={name or 'unnamed'}",
        f"statements={len(statements)}",
        "effects=" + (",".join(sorted(effects)) if effects else "none"),
        "actions=" + (",".join(sorted(actions)) if actions else "none"),
        "resources=" + (",".join(sorted(resources)) if resources else "none"),
        "principals=" + (",".join(sorted(principals)) if principals else "none"),
        "condition_keys=" + (",".join(sorted(condition_keys)) if condition_keys else "none"),
    ]
    line = " ".join(parts)
    if len(line) > MAX_POLICY_TEXT:
        raise PlanSummaryError("plan policy summary metadata is invalid")
    return line


def _policy_lines(item: dict[str, Any], change: dict[str, Any]) -> list[str]:
    resource_type = item.get("type")
    if not isinstance(resource_type, str) or not resource_type.startswith("aws_iam_"):
        return []
    address = _safe_address(item.get("address"))
    before = change.get("before")
    after = change.get("after")
    before = before if isinstance(before, dict) else {}
    after = after if isinstance(after, dict) else {}
    lines = []
    for field in ("policy", "assume_role_policy", "inline_policy"):
        if before.get(field) == after.get(field):
            continue
        for side, values in (("before", before.get(field)), ("after", after.get(field))):
            for name, document in _policy_entries(values):
                lines.append(_policy_line(address, side, name, document))
    return lines


def _codebuild_environment_lines(item: dict[str, Any], change: dict[str, Any]) -> list[str]:
    if item.get("type") != "aws_codebuild_project":
        return []

    def variables(value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, list) or len(value) > MAX_POLICY_DETAILS:
            raise PlanSummaryError("CodeBuild environment summary metadata is invalid")
        result = {}
        for environment in value:
            if not isinstance(environment, dict):
                raise PlanSummaryError("CodeBuild environment summary metadata is invalid")
            name = environment.get("name")
            if not isinstance(name, str) or not SAFE_VARIABLE_NAME.fullmatch(name):
                raise PlanSummaryError("CodeBuild environment summary metadata is invalid")
            if name in result:
                raise PlanSummaryError("CodeBuild environment summary metadata is invalid")
            result[name] = environment.get("value")
        return result

    before = change.get("before") if isinstance(change.get("before"), dict) else {}
    after = change.get("after") if isinstance(change.get("after"), dict) else {}
    before_environment = before.get("environment")
    after_environment = after.get("environment")
    if isinstance(before_environment, list):
        before_environment = before_environment[0] if before_environment else {}
    if isinstance(after_environment, list):
        after_environment = after_environment[0] if after_environment else {}
    if before_environment is None:
        before_environment = {}
    if after_environment is None:
        after_environment = {}
    if not isinstance(before_environment, dict) or not isinstance(after_environment, dict):
        raise PlanSummaryError("CodeBuild environment summary metadata is invalid")
    before_variables = variables(before_environment.get("environment_variable"))
    after_variables = variables(after_environment.get("environment_variable"))
    changed = sorted(
        name
        for name in before_variables.keys() | after_variables.keys()
        if before_variables.get(name) != after_variables.get(name)
    )
    lines = []
    for name in changed[:MAX_POLICY_DETAILS]:
        value = after_variables.get(name)
        if name in CODEBUILD_BOOLEAN_VARIABLES:
            if isinstance(value, bool):
                safe_value = str(value).lower()
            elif isinstance(value, str) and value.lower() in {"true", "false"}:
                safe_value = value.lower()
            else:
                raise PlanSummaryError("CodeBuild environment summary metadata is invalid")
        else:
            safe_value = "redacted"
        lines.append(f"codebuild_environment name={name} value={safe_value}")
    if len(changed) > MAX_POLICY_DETAILS:
        lines.append("codebuild_environment_details=truncated")
    return lines


def _output_lines(output_changes: dict[str, Any]) -> list[str]:
    if len(output_changes) > MAX_OUTPUT_DETAILS:
        raise PlanSummaryError("output change metadata is invalid")
    lines = []
    for name, change in sorted(output_changes.items()):
        safe_name = name if isinstance(name, str) and SAFE_OUTPUT_NAME.fullmatch(name) else "redacted-output"
        if not isinstance(change, dict):
            raise PlanSummaryError("output change metadata is invalid")
        try:
            actions = _resource_actions(change)
        except PlanSummaryError:
            raise PlanSummaryError("output change action metadata is invalid") from None
        before_sensitive = change.get("before_sensitive", False)
        after_sensitive = change.get("after_sensitive", change.get("sensitive", False))
        if type(before_sensitive) is not bool or type(after_sensitive) is not bool:
            raise PlanSummaryError("output change metadata is invalid")
        lines.append(
            f"output_change name={safe_name} actions={','.join(actions)}"
            f" sensitive_before={str(before_sensitive).lower()}"
            f" sensitive_after={str(after_sensitive).lower()}"
        )
    return lines


def _module_resources(module: Any):
    stack = [module]
    while stack:
        current = stack.pop()
        if not isinstance(current, dict):
            continue
        resources = current.get("resources")
        if isinstance(resources, list):
            yield from (resource for resource in resources if isinstance(resource, dict))
        children = current.get("child_modules")
        if isinstance(children, list):
            stack.extend(children)


def _runtime_flags(plan: dict[str, Any]) -> tuple[dict[str, set[bool]], bool]:
    flags: dict[str, set[bool]] = defaultdict(set)
    gate_presence = {"planned": set(), "change": set()}
    shape = {
        "planned_lambdas": 0,
        "planned_environments": 0,
        "planned_variable_maps": 0,
        "change_lambdas": 0,
        "change_environments": 0,
        "change_variable_maps": 0,
    }

    def add_runtime_flags(values: Any, *, source: str) -> None:
        if not isinstance(values, dict):
            return
        environment = values.get("environment") or {}
        if isinstance(environment, list):
            environment = environment[0] if environment else {}
        if not isinstance(environment, dict):
            return
        shape[f"{source}_environments"] += 1
        variables = environment.get("variables")
        if not isinstance(variables, dict):
            return
        shape[f"{source}_variable_maps"] += 1
        for name in FLAG_NAMES:
            if name not in variables:
                continue
            gate_presence[source].add(name)
            raw_value = variables[name]
            if isinstance(raw_value, bool):
                value = raw_value
            elif isinstance(raw_value, str) and raw_value.lower() in {"true", "false"}:
                value = raw_value.lower() == "true"
            else:
                raise PlanSummaryError("runtime feature gate is not a literal boolean")
            flags[name].add(value)

    planned_values = plan.get("planned_values")
    root = planned_values.get("root_module") if isinstance(planned_values, dict) else None
    for resource in _module_resources(root):
        if resource.get("type") != "aws_lambda_function":
            continue
        shape["planned_lambdas"] += 1
        add_runtime_flags(resource.get("values"), source="planned")

    # Terraform plan JSON provides planned_values and resource_changes as
    # separate representations. Collect only fixed runtime-gate names from
    # both, and require agreement whenever both include a value.
    for resource_change in plan.get("resource_changes", []):
        if not isinstance(resource_change, dict):
            continue
        if resource_change.get("type") != "aws_lambda_function":
            continue
        shape["change_lambdas"] += 1
        change = resource_change.get("change")
        if isinstance(change, dict):
            add_runtime_flags(change.get("after"), source="change")

    # The control-plane Terraform configuration maps these exact input
    # variables to the fixed Lambda environment gates above. Provider plans can
    # omit a partially unknown environment map, so use the typed plan inputs
    # only for values absent from both resource representations. Any present
    # resource value is still compared against its corresponding input.
    plan_variables = plan.get("variables")
    plan_variables = plan_variables if isinstance(plan_variables, dict) else {}
    used_plan_inputs = False
    for gate_name, variable_name in RUNTIME_GATE_VARIABLES.items():
        if variable_name not in plan_variables:
            continue
        variable = plan_variables[variable_name]
        raw_value = variable.get("value") if isinstance(variable, dict) else None
        if isinstance(raw_value, bool):
            value = raw_value
        elif isinstance(raw_value, str) and raw_value.lower() in {"true", "false"}:
            value = raw_value.lower() == "true"
        else:
            raise PlanSummaryError("runtime feature gate is not a literal boolean")
        if not flags[gate_name]:
            used_plan_inputs = True
        flags[gate_name].add(value)

    missing = sorted(set(FLAG_NAMES) - set(flags))
    if missing:
        safe_missing = tuple(name for name in FLAG_NAMES if name in missing)
        raise PlanSummaryError(
            "required runtime feature gates are missing",
            missing_gates=safe_missing,
            gate_shape=tuple(
                (name, count)
                for name, count in shape.items()
                if name in {
                    "planned_lambdas",
                    "planned_environments",
                    "planned_variable_maps",
                    "change_lambdas",
                    "change_environments",
                    "change_variable_maps",
                }
            ),
            gate_names=tuple(
                (
                    source,
                    tuple(name for name in FLAG_NAMES if name in gate_presence[source]),
                )
                for source in ("planned", "change")
            ),
        )
    if any(len(values) != 1 for values in flags.values()):
        raise PlanSummaryError("runtime feature gates disagree across functions")
    return flags, used_plan_inputs


def summarize_plan(plan: Any) -> list[str]:
    """Return allowlisted action, field-name and boolean-gate evidence only."""
    if not isinstance(plan, dict):
        raise PlanSummaryError("plan JSON root is not an object")
    if (
        plan.get("applyable") is not True
        or plan.get("errored") is not False
        or plan.get("complete") is not True
    ):
        raise PlanSummaryError("plan is incomplete, not applyable, or has errors")

    resource_changes = plan.get("resource_changes")
    if not isinstance(resource_changes, list):
        raise PlanSummaryError("resource changes are missing")
    resource_drift = plan.get("resource_drift") or []
    if not isinstance(resource_drift, list):
        raise PlanSummaryError("resource drift metadata is invalid")
    output_changes = plan.get("output_changes") or {}
    if not isinstance(output_changes, dict):
        raise PlanSummaryError("output change metadata is invalid")
    counts = {"add": 0, "change": 0, "destroy": 0, "replace": 0, "other": 0}
    details: list[tuple[str, str, list[str], list[str]]] = []
    structural_details: list[str] = []
    for item in resource_changes:
        if not isinstance(item, dict):
            raise PlanSummaryError("invalid resource change entry")
        change = item.get("change")
        if not isinstance(change, dict):
            raise PlanSummaryError("invalid resource change metadata")
        actions = _resource_actions(change)
        if actions in (["no-op"], ["read"]):
            continue
        structural_details.extend(_policy_lines(item, change))
        structural_details.extend(_codebuild_environment_lines(item, change))
        if "create" in actions and "delete" in actions:
            category = "replace"
        elif actions == ["create"]:
            category = "add"
        elif actions == ["update"]:
            category = "change"
        elif actions == ["delete"]:
            category = "destroy"
        else:
            category = "other"
        counts[category] += 1
        if len(details) < MAX_SUMMARY_RESOURCES:
            details.append(
                (
                    _safe_address(item.get("address")),
                    (
                        item["type"]
                        if isinstance(item.get("type"), str)
                        and SAFE_RESOURCE_TYPE.fullmatch(item["type"])
                        else "redacted-type"
                    ),
                    actions,
                    _changed_fields(change),
                )
            )

    drift_details: list[tuple[str, str, list[str], list[str]]] = []
    for item in resource_drift[:MAX_SUMMARY_RESOURCES]:
        if not isinstance(item, dict):
            raise PlanSummaryError("resource drift metadata is invalid")
        change = item.get("change")
        if not isinstance(change, dict):
            raise PlanSummaryError("resource drift metadata is invalid")
        actions = _resource_actions(change)
        structural_details.extend(_policy_lines(item, change))
        resource_type = item.get("type")
        if not isinstance(resource_type, str) or not SAFE_RESOURCE_TYPE.fullmatch(resource_type):
            resource_type = "redacted-type"
        drift_details.append(
            (
                _safe_address(item.get("address")),
                resource_type,
                actions,
                _changed_fields(change),
            )
        )

    flags, used_plan_inputs = _runtime_flags(plan)
    version = plan.get("terraform_version")
    if not isinstance(version, str) or not SAFE_TERRAFORM_VERSION.fullmatch(version):
        version = "unknown"
    lines = [
        (
            "terraform_plan_summary"
            f" terraform_version={version}"
            f" applyable={plan['applyable']} errored={plan['errored']}"
            f" complete={plan.get('complete') is True}"
        ),
        "actions " + " ".join(f"{name}={counts[name]}" for name in counts),
        f"drift_count={len(resource_drift)} output_change_count={len(output_changes)}",
    ]
    for address, resource_type, actions, fields in details:
        action_text = ",".join(actions)
        field_text = ",".join(fields) if fields else "none"
        lines.append(
            f"resource address={address} type={resource_type}"
            f" actions={action_text} changed_fields={field_text}"
        )
    for address, resource_type, actions, fields in drift_details:
        action_text = ",".join(actions)
        field_text = ",".join(fields) if fields else "none"
        lines.append(
            f"drift address={address} type={resource_type}"
            f" actions={action_text} changed_fields={field_text}"
        )
    lines.extend(structural_details[:MAX_SUMMARY_RESOURCES * 4])
    if len(structural_details) > MAX_SUMMARY_RESOURCES * 4:
        lines.append("structural_details=truncated")
    lines.extend(_output_lines(output_changes))
    if sum(counts.values()) > MAX_SUMMARY_RESOURCES:
        lines.append("resource_details=truncated")
    if len(resource_drift) > MAX_SUMMARY_RESOURCES:
        lines.append("drift_details=truncated")
    for name in FLAG_NAMES:
        lines.append(f"runtime_flag {name}={next(iter(flags[name]))}")
    if used_plan_inputs:
        lines.append("runtime_flag_source=terraform_plan_input_variables")
    return lines


def main() -> int:
    try:
        raw = sys.stdin.buffer.read(MAX_PLAN_JSON_BYTES + 1)
        if len(raw) > MAX_PLAN_JSON_BYTES:
            raise PlanSummaryError("plan JSON exceeds the configured size limit")
        plan = json.loads(raw)
        lines = summarize_plan(plan)
    except (json.JSONDecodeError, PlanSummaryError, UnicodeDecodeError, RecursionError) as error:
        if isinstance(error, PlanSummaryError):
            reason = SAFE_FAILURE_CODES.get(str(error), "plan_validation_failed")
        elif isinstance(error, json.JSONDecodeError):
            reason = "invalid_plan_json"
        elif isinstance(error, UnicodeDecodeError):
            reason = "invalid_plan_encoding"
        else:
            reason = "plan_json_too_deep"
        missing_gates = ()
        gate_shape = ()
        gate_names = ()
        if isinstance(error, PlanSummaryError) and reason == "runtime_gates_missing":
            candidates = error.missing_gates
            if (
                isinstance(candidates, tuple)
                and candidates
                and all(name in FLAG_NAMES for name in candidates)
            ):
                missing_gates = candidates
            allowed_shape_names = {
                "planned_lambdas",
                "planned_environments",
                "planned_variable_maps",
                "change_lambdas",
                "change_environments",
                "change_variable_maps",
            }
            shape_candidates = error.gate_shape
            if (
                isinstance(shape_candidates, tuple)
                and all(
                    isinstance(item, tuple)
                    and len(item) == 2
                    and item[0] in allowed_shape_names
                    and type(item[1]) is int
                    and item[1] >= 0
                    for item in shape_candidates
                )
            ):
                gate_shape = shape_candidates
            name_candidates = error.gate_names
            if (
                isinstance(name_candidates, tuple)
                and all(
                    isinstance(item, tuple)
                    and len(item) == 2
                    and item[0] in {"planned", "change"}
                    and isinstance(item[1], tuple)
                    and all(name in FLAG_NAMES for name in item[1])
                    for item in name_candidates
                )
            ):
                gate_names = name_candidates
        detail = f" missing_gates={','.join(missing_gates)}" if missing_gates else ""
        if gate_shape:
            detail += " gate_shape=" + ",".join(f"{name}:{count}" for name, count in gate_shape)
        if gate_names:
            detail += " gate_names=" + ";".join(
                f"{source}:{','.join(names) if names else 'none'}" for source, names in gate_names
            )
        print(
            "Terraform plan summary failed closed; "
            f"reason={reason};{detail} raw plan output was suppressed.",
            file=sys.stderr,
        )
        return 2
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
