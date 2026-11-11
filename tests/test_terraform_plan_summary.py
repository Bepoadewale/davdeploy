from __future__ import annotations

import importlib.util
import io
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/summarize_terraform_plan.py"
SPEC = importlib.util.spec_from_file_location("terraform_plan_summary", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
terraform_plan_summary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(terraform_plan_summary)
FLAG_NAMES = terraform_plan_summary.FLAG_NAMES
PlanSummaryError = terraform_plan_summary.PlanSummaryError
summarize_plan = terraform_plan_summary.summarize_plan


def _run_main(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, raw: bytes):
    monkeypatch.setattr(terraform_plan_summary.sys, "stdin", io.TextIOWrapper(io.BytesIO(raw)))
    result = terraform_plan_summary.main()
    return result, capsys.readouterr()


def _plan() -> dict:
    flags = {name: "false" for name in FLAG_NAMES}
    flags["ALLOW_CLOUD_APPLY"] = "true"
    return {
        "terraform_version": "1.14.7",
        "applyable": True,
        "errored": False,
        "complete": True,
        "resource_changes": [
            {
                "address": "aws_lambda_function.api",
                "type": "aws_lambda_function",
                "change": {
                    "actions": ["update"],
                    "before": {
                        "environment": {"variables": {"PRIVATE_TOKEN": "old-secret"}},
                        "s3_key": "old-package.zip",
                    },
                    "after": {
                        "environment": {"variables": {"PRIVATE_TOKEN": "new-secret"}},
                        "s3_key": "new-package.zip",
                    },
                },
            },
            {
                "address": "aws_s3_bucket.plan_artifacts",
                "type": "aws_s3_bucket",
                "change": {
                    "actions": ["no-op"],
                    "before": {"bucket": "private-customer-bucket"},
                    "after": {"bucket": "private-customer-bucket"},
                },
            },
        ],
        "planned_values": {
            "root_module": {
                "resources": [
                    {
                        "address": "aws_lambda_function.api",
                        "type": "aws_lambda_function",
                        "values": {
                            "environment": {"variables": flags},
                            "description": "sensitive-description-value",
                        },
                    }
                ]
            }
        },
        "variables": {"session_secret": {"value": "private-variable-value"}},
    }


def test_summary_contains_actions_changed_field_names_and_boolean_flags_only():
    summary = "\n".join(summarize_plan(_plan()))

    assert "actions add=0 change=1 destroy=0 replace=0 other=0" in summary
    assert "resource address=aws_lambda_function.api type=aws_lambda_function" in summary
    assert "actions=update changed_fields=environment,s3_key" in summary
    assert "runtime_flag ALLOW_CLOUD_APPLY=True" in summary
    assert "runtime_flag DAVDEPLOY_NOVA_PLAN_RUNNER_READY=False" in summary
    for sensitive_value in (
        "old-secret",
        "new-secret",
        "private-customer-bucket",
        "sensitive-description-value",
        "private-variable-value",
    ):
        assert sensitive_value not in summary


def test_summary_reports_drift_and_output_counts_without_values():
    plan = _plan()
    plan["resource_drift"] = [
        {
            "address": "aws_s3_bucket.state",
            "change": {"before": {"bucket": "old-sensitive-name"}},
        }
    ]
    plan["output_changes"] = {"private_endpoint": {"after": "sensitive-endpoint-value"}}

    summary = "\n".join(summarize_plan(plan))

    assert "drift_count=1 output_change_count=1" in summary
    assert "old-sensitive-name" not in summary
    assert "sensitive-endpoint-value" not in summary


@pytest.mark.parametrize(
    "field,value", [("applyable", False), ("errored", True), ("complete", False)]
)
def test_non_applyable_or_errored_plan_fails_closed(field: str, value: bool):
    plan = _plan()
    plan[field] = value

    with pytest.raises(PlanSummaryError):
        summarize_plan(plan)


def test_unknown_runtime_gate_value_fails_without_echoing_value():
    plan = _plan()
    plan["planned_values"]["root_module"]["resources"][0]["values"]["environment"]["variables"][
        "DAVDEPLOY_NOVA_PLAN_RUNNER_READY"
    ] = "sensitive-unknown-value"

    with pytest.raises(PlanSummaryError, match="literal boolean"):
        summarize_plan(plan)


def test_missing_runtime_gate_fails_closed():
    plan = _plan()
    del plan["planned_values"]["root_module"]["resources"][0]["values"]["environment"]["variables"][
        "DAVDEPLOY_NOVA_PLAN_RUNNER_READY"
    ]

    with pytest.raises(PlanSummaryError, match="required runtime feature gates"):
        summarize_plan(plan)


@pytest.mark.parametrize("actions", [["sensitive-action-text"], [], ["create", "update"]])
def test_invalid_action_does_not_echo_untrusted_action_text(actions: list[str]):
    plan = _plan()
    plan["resource_changes"][0]["change"]["actions"] = actions

    with pytest.raises(PlanSummaryError, match="resource action metadata"):
        summarize_plan(plan)


def test_malformed_json_error_does_not_echo_raw_input(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    result, output = _run_main(monkeypatch, capsys, b"sensitive-plan-value")

    assert result == 2
    assert "raw plan output was suppressed" in output.err
    assert "sensitive-plan-value" not in output.err


def test_oversized_plan_fails_without_echoing_input(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    monkeypatch.setattr(terraform_plan_summary, "MAX_PLAN_JSON_BYTES", 8)
    result, output = _run_main(monkeypatch, capsys, b"sensitive-plan-value")

    assert result == 2
    assert "raw plan output was suppressed" in output.err
    assert "sensitive-plan-value" not in output.err
