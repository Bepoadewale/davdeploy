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
SAFE_ADDRESS = re.compile(r"[A-Za-z0-9_.\[\]-]{1,512}\Z")
SAFE_RESOURCE_TYPE = re.compile(r"[A-Za-z0-9_]{1,128}\Z")
SAFE_FIELD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}\Z")
SAFE_TERRAFORM_VERSION = re.compile(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?\Z")
ALLOWED_ACTIONS = {"create", "read", "update", "delete", "no-op"}
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
    "runtime feature gate is not a literal boolean": "runtime_gate_not_boolean",
    "required runtime feature gates are missing": "runtime_gates_missing",
    "runtime feature gates disagree across functions": "runtime_gate_disagreement",
}


class PlanSummaryError(ValueError):
    """Raised when a plan cannot be summarized without making assumptions."""


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


def _runtime_flags(plan: dict[str, Any]) -> dict[str, set[bool]]:
    flags: dict[str, set[bool]] = defaultdict(set)
    planned_values = plan.get("planned_values")
    root = planned_values.get("root_module") if isinstance(planned_values, dict) else None
    for resource in _module_resources(root):
        if resource.get("type") != "aws_lambda_function":
            continue
        values = resource.get("values")
        values = values if isinstance(values, dict) else {}
        environment = values.get("environment") or {}
        if isinstance(environment, list):
            environment = environment[0] if environment else {}
        if not isinstance(environment, dict):
            continue
        variables = environment.get("variables")
        if not isinstance(variables, dict):
            continue
        for name in FLAG_NAMES:
            if name not in variables:
                continue
            raw_value = variables[name]
            if isinstance(raw_value, bool):
                value = raw_value
            elif isinstance(raw_value, str) and raw_value.lower() in {"true", "false"}:
                value = raw_value.lower() == "true"
            else:
                raise PlanSummaryError("runtime feature gate is not a literal boolean")
            flags[name].add(value)
    missing = sorted(set(FLAG_NAMES) - set(flags))
    if missing:
        raise PlanSummaryError("required runtime feature gates are missing")
    if any(len(values) != 1 for values in flags.values()):
        raise PlanSummaryError("runtime feature gates disagree across functions")
    return flags


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
    for item in resource_changes:
        if not isinstance(item, dict):
            raise PlanSummaryError("invalid resource change entry")
        change = item.get("change")
        if not isinstance(change, dict):
            raise PlanSummaryError("invalid resource change metadata")
        actions = _resource_actions(change)
        if actions in (["no-op"], ["read"]):
            continue
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

    flags = _runtime_flags(plan)
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
    if sum(counts.values()) > MAX_SUMMARY_RESOURCES:
        lines.append("resource_details=truncated")
    for name in FLAG_NAMES:
        lines.append(f"runtime_flag {name}={next(iter(flags[name]))}")
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
        print(
            "Terraform plan summary failed closed; "
            f"reason={reason}; raw plan output was suppressed.",
            file=sys.stderr,
        )
        return 2
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
