from __future__ import annotations

import pytest
from davdeploy.generated_plan_inspection import (
    TerraformPlanInspectionError,
    inspect_terraform_plan,
)


def change(address: str, actions: list[str], **metadata):
    return {
        "address": address,
        "type": "aws_test_resource",
        "change": {"actions": actions, **metadata},
    }


def plan(changes=None, drift=None):
    return {
        "format_version": "1.2",
        "applyable": True,
        "errored": False,
        "resource_changes": changes or [],
        "resource_drift": drift or [],
    }


def test_inspection_classifies_create_update_delete_replacement_and_noop():
    result = inspect_terraform_plan(
        plan(
            [
                change("aws_test_resource.create", ["create"]),
                change("aws_test_resource.update", ["update"]),
                change("aws_test_resource.delete", ["delete"]),
                change("aws_test_resource.replace", ["delete", "create"]),
                change("aws_test_resource.keep", ["no-op"]),
            ]
        )
    )
    assert (result.create_count, result.update_count, result.delete_count) == (1, 1, 1)
    assert result.replacement_count == 1
    assert result.no_op_count == 1


def test_sensitive_values_are_not_in_summary():
    secret = "must-not-appear-in-evidence"
    document = plan(
        [
            change(
                "aws_test_resource.secret",
                ["update"],
                before={"password": secret},
                after={"password": secret},
                after_sensitive={"password": True},
            )
        ]
    )
    summary = inspect_terraform_plan(document)
    assert summary.contains_sensitive_changes is True
    assert summary.resource_changes[0].contains_sensitive_changes is True
    assert secret not in repr(summary)


def test_drift_is_counted_without_values():
    result = inspect_terraform_plan(
        plan(drift=[change("aws_test_resource.drift", ["update"], after={"value": "hidden"})])
    )
    assert result.drift_count == 1
    assert "hidden" not in repr(result)


@pytest.mark.parametrize(
    "document, message",
    [
        ([], "JSON object"),
        ({"format_version": "2.0"}, "format version"),
        ({**plan(), "resource_changes": {}}, "arrays"),
        (plan([change("aws.test", ["run-command"])]), "actions are unsupported"),
        (plan([{"address": "", "type": "aws_test", "change": {"actions": ["create"]}}]), "metadata"),
    ],
)
def test_rejects_malformed_or_unsupported_plan(document, message):
    with pytest.raises(TerraformPlanInspectionError, match=message):
        inspect_terraform_plan(document)


def test_rejects_plan_above_resource_limit():
    too_many = [change(f"aws_test_resource.item_{i}", ["no-op"]) for i in range(2_001)]
    with pytest.raises(TerraformPlanInspectionError, match="change limit"):
        inspect_terraform_plan(plan(too_many))


def test_rejects_malformed_sensitivity_shape():
    with pytest.raises(TerraformPlanInspectionError, match="sensitivity metadata is malformed"):
        inspect_terraform_plan(
            plan([change("aws_test_resource.bad", ["create"], after_sensitive="password")])
        )


def test_read_action_is_reported_separately():
    result = inspect_terraform_plan(plan([change("data.aws_test_resource.lookup", ["read"])]))
    assert result.read_count == 1


def test_non_applyable_or_errored_plan_flags_are_preserved():
    document = plan()
    document["applyable"] = False
    document["errored"] = True
    result = inspect_terraform_plan(document)
    assert result.applyable is False
    assert result.errored is True


def test_requires_applyable_and_error_flags():
    with pytest.raises(TerraformPlanInspectionError, match="flags are required"):
        inspect_terraform_plan({"format_version": "1.2", "resource_changes": []})
