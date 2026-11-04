"""Secret-safe inspection of Terraform's JSON plan, without execution authority."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MAX_RESOURCE_CHANGES = 2_000
MAX_ADDRESS_LENGTH = 1_024
MAX_SENSITIVITY_NODES = 100_000
SUPPORTED_ACTIONS = {
    ("no-op",),
    ("read",),
    ("create",),
    ("update",),
    ("delete",),
    ("forget",),
    ("delete", "create"),
    ("create", "delete"),
}


class TerraformPlanInspectionError(ValueError):
    """The supplied Terraform plan cannot be safely summarized."""


@dataclass(frozen=True)
class ResourceChangeSummary:
    address: str
    resource_type: str
    actions: tuple[str, ...]
    category: str
    contains_sensitive_changes: bool


@dataclass(frozen=True)
class TerraformPlanSummary:
    format_version: str
    resource_changes: tuple[ResourceChangeSummary, ...]
    create_count: int
    update_count: int
    delete_count: int
    replacement_count: int
    read_count: int
    no_op_count: int
    drift_count: int
    contains_sensitive_changes: bool


def inspect_terraform_plan(document: dict[str, Any]) -> TerraformPlanSummary:
    """Summarize plan effects only; never return Terraform before/after values.

    The input is expected to be parsed output from ``terraform show -json``. This
    pure function does not invoke Terraform, read files, contact AWS, or approve
    changes.
    """
    if not isinstance(document, dict):
        raise TerraformPlanInspectionError("Terraform plan must be a JSON object")
    version = document.get("format_version")
    if not isinstance(version, str) or not version.startswith("1."):
        raise TerraformPlanInspectionError("unsupported Terraform plan JSON format version")

    changes = document.get("resource_changes", [])
    drift = document.get("resource_drift", [])
    if not isinstance(changes, list) or not isinstance(drift, list):
        raise TerraformPlanInspectionError("Terraform resource changes must be arrays")
    if len(changes) > MAX_RESOURCE_CHANGES or len(drift) > MAX_RESOURCE_CHANGES:
        raise TerraformPlanInspectionError("Terraform plan exceeds the resource change limit")

    summaries: list[ResourceChangeSummary] = []
    counts = {name: 0 for name in ("create", "update", "delete", "replacement", "read", "no_op")}
    sensitive_any = False
    for item in changes:
        summary = _resource_summary(item)
        summaries.append(summary)
        if summary.category in counts:
            counts[summary.category] += 1
        sensitive_any = sensitive_any or summary.contains_sensitive_changes

    drift_count = 0
    for item in drift:
        drift_summary = _resource_summary(item)
        if drift_summary.category != "no_op":
            drift_count += 1
        sensitive_any = sensitive_any or drift_summary.contains_sensitive_changes

    return TerraformPlanSummary(
        format_version=version,
        resource_changes=tuple(summaries),
        create_count=counts["create"],
        update_count=counts["update"],
        delete_count=counts["delete"],
        replacement_count=counts["replacement"],
        read_count=counts["read"],
        no_op_count=counts["no_op"],
        drift_count=drift_count,
        contains_sensitive_changes=sensitive_any,
    )


def _resource_summary(item: Any) -> ResourceChangeSummary:
    if not isinstance(item, dict):
        raise TerraformPlanInspectionError("Terraform resource change must be an object")
    address = item.get("address")
    resource_type = item.get("type")
    change = item.get("change")
    if (
        not isinstance(address, str)
        or not address
        or len(address) > MAX_ADDRESS_LENGTH
        or not isinstance(resource_type, str)
        or not resource_type
        or len(resource_type) > 256
        or not isinstance(change, dict)
    ):
        raise TerraformPlanInspectionError("Terraform resource change is missing valid metadata")

    raw_actions = change.get("actions")
    if not isinstance(raw_actions, list) or not all(isinstance(a, str) for a in raw_actions):
        raise TerraformPlanInspectionError("Terraform resource actions must be strings")
    actions = tuple(raw_actions)
    if actions not in SUPPORTED_ACTIONS:
        raise TerraformPlanInspectionError("Terraform resource actions are unsupported")

    category = {
        ("no-op",): "no_op",
        ("read",): "read",
        ("create",): "create",
        ("update",): "update",
        ("delete",): "delete",
        ("forget",): "delete",
        ("delete", "create"): "replacement",
        ("create", "delete"): "replacement",
    }[actions]
    sensitive = _contains_sensitive(change.get("before_sensitive", False)) or _contains_sensitive(
        change.get("after_sensitive", False)
    )
    return ResourceChangeSummary(
        address=address,
        resource_type=resource_type,
        actions=actions,
        category=category,
        contains_sensitive_changes=sensitive,
    )


def _contains_sensitive(value: Any) -> bool:
    """Read only Terraform's sensitivity shape, with bounded traversal."""
    stack = [(value, 0)]
    visited = 0
    while stack:
        current, depth = stack.pop()
        visited += 1
        if visited > MAX_SENSITIVITY_NODES or depth > 64:
            raise TerraformPlanInspectionError("Terraform sensitivity metadata exceeds its limit")
        if current is True:
            return True
        if current is False or current is None:
            continue
        if isinstance(current, dict):
            stack.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            stack.extend((child, depth + 1) for child in current)
        else:
            raise TerraformPlanInspectionError("Terraform sensitivity metadata is malformed")
    return False
