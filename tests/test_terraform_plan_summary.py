from __future__ import annotations

import importlib.util
import io
import json
import re
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/summarize_terraform_plan.py"
SPEC = importlib.util.spec_from_file_location("terraform_plan_summary", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
terraform_plan_summary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(terraform_plan_summary)
FLAG_NAMES = terraform_plan_summary.FLAG_NAMES
RUNTIME_GATE_VARIABLES = terraform_plan_summary.RUNTIME_GATE_VARIABLES
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


def test_runtime_gates_fall_back_to_change_after_without_exposing_other_values():
    plan = _plan()
    planned_variables = plan["planned_values"]["root_module"]["resources"][0]["values"][
        "environment"
    ]["variables"]
    gate_values = {name: planned_variables[name] for name in FLAG_NAMES}
    plan["planned_values"]["root_module"]["resources"][0]["values"]["environment"] = {
        "variables": {"PRIVATE_TOKEN": "sensitive-planned-value"}
    }
    plan["resource_changes"][0]["change"]["after"]["environment"] = {
        "variables": {**gate_values, "PRIVATE_TOKEN": "sensitive-change-value"}
    }

    summary = "\n".join(summarize_plan(plan))

    assert "runtime_flag ALLOW_CLOUD_APPLY=True" in summary
    assert "runtime_flag DAVDEPLOY_NOVA_PLAN_RUNNER_READY=False" in summary
    assert "sensitive-planned-value" not in summary
    assert "sensitive-change-value" not in summary


def test_runtime_gate_disagreement_between_plan_representations_fails_closed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    plan = _plan()
    plan["resource_changes"][0]["change"]["after"]["environment"] = {
        "variables": {"DAVDEPLOY_NOVA_PLAN_RUNNER_READY": "true"}
    }
    raw = json.dumps(plan).encode()

    result, output = _run_main(monkeypatch, capsys, raw)

    assert result == 2
    assert "reason=runtime_gate_disagreement" in output.err
    assert "sensitive-description-value" not in output.err
    assert "private-variable-value" not in output.err


def test_runtime_gate_inputs_fill_values_omitted_from_lambda_resources():
    plan = _plan()
    for resource in plan["planned_values"]["root_module"]["resources"]:
        resource["values"]["environment"]["variables"] = {"PRIVATE_TOKEN": "hidden"}
    for resource in plan["resource_changes"]:
        if resource["type"] == "aws_lambda_function":
            resource["change"]["after"]["environment"] = {
                "variables": {"PRIVATE_TOKEN": "hidden"}
            }
    plan["variables"].update(
        {
            "enable_nova_plan_only_runner": {"value": True},
            "enable_nova_plan_role_verification": {"value": True},
            "enable_nova_plan_credential_broker": {"value": True},
            "enable_nova_plan_reviews": {"value": True},
            "enable_nova_terraform_state_api": {"value": True},
            "enable_serverless_api_hosted_certification": {"value": False},
            "enable_customer_cloud_execution": {"value": False},
        }
    )

    summary = "\n".join(summarize_plan(plan))

    assert "runtime_flag DAVDEPLOY_NOVA_PLAN_RUNNER_READY=True" in summary
    assert "runtime_flag DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION=False" in summary
    assert "runtime_flag ALLOW_CLOUD_APPLY=False" in summary
    assert "runtime_flag_source=terraform_plan_input_variables" in summary
    assert "hidden" not in summary
    assert "PRIVATE_TOKEN" not in summary


def test_runtime_gate_plan_inputs_must_match_present_resource_values(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    plan = _plan()
    plan["variables"]["enable_customer_cloud_execution"] = {"value": False}
    raw = json.dumps(plan).encode()

    result, output = _run_main(monkeypatch, capsys, raw)

    assert result == 2
    assert "reason=runtime_gate_disagreement" in output.err
    assert "private-variable-value" not in output.err


def test_runtime_gate_plan_inputs_reject_non_boolean_values_without_echoing_them(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    plan = _plan()
    plan["variables"]["enable_customer_cloud_execution"] = {
        "value": "secret-runtime-value"
    }
    raw = json.dumps(plan).encode()

    result, output = _run_main(monkeypatch, capsys, raw)

    assert result == 2
    assert "reason=runtime_gate_not_boolean" in output.err
    assert "secret-runtime-value" not in output.err


def test_runtime_gate_variable_map_matches_control_plane_terraform():
    terraform = (
        Path(__file__).resolve().parents[1]
        / "infrastructure/terraform/serverless-control-plane/main.tf"
    ).read_text(encoding="utf-8")

    for gate_name, variable_name in RUNTIME_GATE_VARIABLES.items():
        assert re.search(
            rf"^\s*{re.escape(gate_name)}\s*=\s*tostring\(var\.{re.escape(variable_name)}\)\s*$",
            terraform,
            re.MULTILINE,
        )
    assert terraform.count("variables = local.runtime_environment") == 3


def test_summary_reports_drift_and_output_counts_without_values():
    plan = _plan()
    plan["resource_drift"] = [
        {
            "address": "aws_s3_bucket.state",
            "type": "aws_s3_bucket",
            "change": {
                "actions": ["update"],
                "before": {"bucket": "old-sensitive-name", "force_destroy": False},
                "after": {"bucket": "new-sensitive-name", "force_destroy": True},
            },
        }
    ]
    plan["output_changes"] = {
        "private_endpoint": {
            "actions": ["update"],
            "before_sensitive": False,
            "after_sensitive": True,
            "after": "sensitive-endpoint-value",
        }
    }

    summary = "\n".join(summarize_plan(plan))

    assert "drift_count=1 output_change_count=1" in summary
    assert (
        "drift address=aws_s3_bucket.state type=aws_s3_bucket "
        "actions=update changed_fields=bucket,force_destroy" in summary
    )
    assert "old-sensitive-name" not in summary
    assert "new-sensitive-name" not in summary
    assert "sensitive-endpoint-value" not in summary
    assert (
        "output_change name=private_endpoint actions=update "
        "sensitive_before=false sensitive_after=true" in summary
    )


def test_iam_policy_summary_exposes_scope_shape_but_not_condition_values():
    plan = _plan()
    before_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetObjectVersion", "execute-api:Invoke"],
                "Resource": [
                    "arn:aws:s3:::davdeploy-artifacts/plans/*",
                    "arn:aws:execute-api:us-east-1:654654474502:api/*/POST/terraform-state",
                ],
                "Principal": {
                    "Service": "codebuild.amazonaws.com",
                    "AWS": "654654474502",
                },
                "Condition": {
                    "ArnLike": {
                        "codebuild:BuildArn": "private-condition-value"
                    }
                },
            }
        ],
    }
    after_policy = json.loads(json.dumps(before_policy))
    after_policy["Statement"].append(
        {
            "Effect": "Deny",
            "Action": "s3:DeleteObject",
            "Resource": "arn:aws:s3:::davdeploy-artifacts/plans/*",
            "Condition": {
                "StringEquals": {"aws:SourceAccount": "654654474502"}
            },
        }
    )
    plan["resource_changes"].append(
        {
            "address": "aws_iam_role_policy.nova_plan_only",
            "type": "aws_iam_role_policy",
            "change": {
                "actions": ["update"],
                "before": {"policy": json.dumps(before_policy)},
                "after": {"policy": json.dumps(after_policy)},
            },
        }
    )

    summary = "\n".join(summarize_plan(plan))

    assert "policy_detail address=aws_iam_role_policy.nova_plan_only side=after" in summary
    assert "effects=Allow,Deny" in summary
    assert "s3:GetObjectVersion" in summary
    assert "s3:DeleteObject" in summary
    assert "arn:aws:execute-api:us-east-1:ACCOUNT:" in summary
    assert "principals=ACCOUNT,codebuild.amazonaws.com" in summary
    assert "codebuild:BuildArn" in summary
    assert "private-condition-value" not in summary
    assert "654654474502" not in summary


def test_iam_policy_summary_preserves_aws_policy_variable_placeholders():
    plan = _plan()
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "s3:GetObject",
                "Resource": "arn:aws:s3:::davdeploy-artifacts/plans/${codebuild:buildArn}/*",
            }
        ],
    }
    plan["resource_changes"].append(
        {
            "address": "aws_iam_role_policy.nova_plan_only",
            "type": "aws_iam_role_policy",
            "change": {
                "actions": ["update"],
                "before": {
                    "policy": json.dumps(
                        {
                            "Statement": {
                                "Effect": "Allow",
                                "Action": "s3:GetObject",
                                "Resource": "arn:aws:s3:::davdeploy-artifacts/plans/*",
                            }
                        }
                    )
                },
                "after": {"policy": json.dumps(policy)},
            },
        }
    )

    summary = "\n".join(summarize_plan(plan))

    assert "plans/${codebuild:buildArn}/*" in summary


def test_malformed_aws_policy_variable_fails_closed_without_echoing_value(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    plan = _plan()
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "s3:GetObject",
                "Resource": "arn:aws:s3:::bucket/${private account id}",
            }
        ],
    }
    plan["resource_changes"].append(
        {
            "address": "aws_iam_role_policy.nova_plan_only",
            "type": "aws_iam_role_policy",
            "change": {
                "actions": ["update"],
                "before": {
                    "policy": json.dumps(
                        {
                            "Statement": {
                                "Effect": "Allow",
                                "Action": "s3:GetObject",
                                "Resource": "arn:aws:s3:::bucket/*",
                            }
                        }
                    )
                },
                "after": {"policy": json.dumps(policy)},
            },
        }
    )

    result, output = _run_main(monkeypatch, capsys, json.dumps(plan).encode())

    assert result == 2
    assert "reason=invalid_policy_summary" in output.err
    assert "private account id" not in output.err


def test_codebuild_environment_summary_redacts_values_and_reports_fixed_boolean_flags():
    plan = _plan()
    plan["resource_changes"].append(
        {
            "address": "aws_codebuild_project.nova_plan_only",
            "type": "aws_codebuild_project",
            "change": {
                "actions": ["update"],
                "before": {
                    "environment": {
                        "environment_variable": [
                            {
                                "name": "DAVDEPLOY_NOVA_PLAN_CREDENTIAL_BROKER_URL",
                                "value": "https://old-sensitive-endpoint",
                            },
                            {
                                "name": "TF_VAR_enable_nova_exact_plan_apply_runner",
                                "value": "true",
                            },
                        ]
                    }
                },
                "after": {
                    "environment": {
                        "environment_variable": [
                            {
                                "name": "DAVDEPLOY_NOVA_PLAN_CREDENTIAL_BROKER_URL",
                                "value": "https://new-sensitive-endpoint",
                            },
                            {
                                "name": "TF_VAR_enable_nova_exact_plan_apply_runner",
                                "value": "false",
                            },
                        ]
                    }
                },
            },
        }
    )

    summary = "\n".join(summarize_plan(plan))

    assert (
        "codebuild_environment name=DAVDEPLOY_NOVA_PLAN_CREDENTIAL_BROKER_URL "
        "value=redacted" in summary
    )
    assert (
        "codebuild_environment name=TF_VAR_enable_nova_exact_plan_apply_runner "
        "value=false" in summary
    )
    assert "old-sensitive-endpoint" not in summary
    assert "new-sensitive-endpoint" not in summary


def test_malformed_iam_policy_fails_with_fixed_error_without_echoing_input(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    plan = _plan()
    plan["resource_changes"].append(
        {
            "address": "aws_iam_role_policy.nova_plan_only",
            "type": "aws_iam_role_policy",
            "change": {
                "actions": ["update"],
                "before": {
                    "policy": json.dumps(
                        {
                            "Statement": {
                                "Effect": "Allow",
                                "Action": "s3:GetObject",
                                "Resource": "arn:aws:s3:::bucket/*",
                            }
                        }
                    )
                },
                "after": {"policy": "private-policy-value"},
            },
        }
    )

    result, output = _run_main(monkeypatch, capsys, json.dumps(plan).encode())

    assert result == 2
    assert "reason=invalid_policy_summary" in output.err
    assert (
        "policy_resource=aws_iam_role_policy.nova_plan_only "
        "policy_side=after policy_field=policy" in output.err
    )
    assert "private-policy-value" not in output.err


def test_malformed_output_change_actions_fail_closed_without_echoing_value(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    plan = _plan()
    plan["output_changes"] = {
        "endpoint": {"actions": ["private-action"], "after": "private-output-value"}
    }

    result, output = _run_main(monkeypatch, capsys, json.dumps(plan).encode())

    assert result == 2
    assert "reason=invalid_output_actions" in output.err
    assert "private-action" not in output.err
    assert "private-output-value" not in output.err


def test_invalid_drift_actions_fail_with_fixed_reason_without_echoing_values(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    plan = _plan()
    plan["resource_drift"] = [
        {
            "address": "aws_s3_bucket.state",
            "type": "aws_s3_bucket",
            "change": {
                "actions": ["secret-action"],
                "before": {"bucket": "private-bucket-name"},
            },
        }
    ]

    result, output = _run_main(monkeypatch, capsys, json.dumps(plan).encode())

    assert result == 2
    assert "reason=invalid_resource_actions" in output.err
    assert "secret-action" not in output.err
    assert "private-bucket-name" not in output.err


def test_drift_detail_output_is_bounded():
    plan = _plan()
    plan["resource_drift"] = [
        {
            "address": f"aws_s3_bucket.state_{index}",
            "type": "aws_s3_bucket",
            "change": {"actions": ["update"], "before": {}, "after": {}},
        }
        for index in range(251)
    ]

    summary = summarize_plan(plan)

    assert sum(line.startswith("drift address=") for line in summary) == 250
    assert "drift_details=truncated" in summary


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
    assert "reason=invalid_plan_json" in output.err
    assert "raw plan output was suppressed" in output.err
    assert "sensitive-plan-value" not in output.err


def test_oversized_plan_fails_without_echoing_input(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    monkeypatch.setattr(terraform_plan_summary, "MAX_PLAN_JSON_BYTES", 8)
    result, output = _run_main(monkeypatch, capsys, b"sensitive-plan-value")

    assert result == 2
    assert "reason=plan_json_too_large" in output.err
    assert "raw plan output was suppressed" in output.err
    assert "sensitive-plan-value" not in output.err


def test_invalid_plan_reports_only_a_fixed_safe_reason_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    plan = _plan()
    plan["applyable"] = False
    raw = json.dumps(plan).encode()

    result, output = _run_main(monkeypatch, capsys, raw)

    assert result == 2
    assert "reason=plan_not_applyable" in output.err
    assert "PRIVATE_TOKEN" not in output.err
    assert "old-secret" not in output.err


def test_missing_runtime_gate_reports_fixed_code_without_plan_values(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    plan = _plan()
    del plan["planned_values"]["root_module"]["resources"][0]["values"]["environment"][
        "variables"
    ]["DAVDEPLOY_NOVA_PLAN_RUNNER_READY"]
    raw = json.dumps(plan).encode()

    result, output = _run_main(monkeypatch, capsys, raw)

    assert result == 2
    assert "reason=runtime_gates_missing" in output.err
    assert "missing_gates=DAVDEPLOY_NOVA_PLAN_RUNNER_READY" in output.err
    assert "gate_shape=planned_lambdas:1,planned_environments:1" in output.err
    assert "gate_names=planned:DAVDEPLOY_NOVA_PLAN_ROLE_VERIFY_ENABLED" in output.err
    assert "sensitive-description-value" not in output.err
    assert "private-variable-value" not in output.err


def test_runtime_gate_shape_diagnostic_exposes_only_bounded_counts_and_allowlist(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    plan = _plan()
    plan["planned_values"]["root_module"]["resources"][0]["values"]["environment"] = {
        "variables": {"PRIVATE_TOKEN": "private-plan-value"}
    }
    plan["resource_changes"][0]["change"]["after"]["environment"] = {
        "variables": {"UNTRUSTED_GATE": "private-change-value"}
    }
    raw = json.dumps(plan).encode()

    result, output = _run_main(monkeypatch, capsys, raw)

    assert result == 2
    assert "gate_shape=planned_lambdas:1,planned_environments:1" in output.err
    assert "gate_names=planned:none;change:none" in output.err
    assert "PRIVATE_TOKEN" not in output.err
    assert "UNTRUSTED_GATE" not in output.err
    assert "private-plan-value" not in output.err
    assert "private-change-value" not in output.err


def test_missing_gate_detail_does_not_echo_unexpected_environment_names(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    plan = _plan()
    variables = plan["planned_values"]["root_module"]["resources"][0]["values"][
        "environment"
    ]["variables"]
    del variables["DAVDEPLOY_NOVA_PLAN_RUNNER_READY"]
    variables["PRIVATE_TOKEN"] = "private-token-value"
    raw = json.dumps(plan).encode()

    result, output = _run_main(monkeypatch, capsys, raw)

    assert result == 2
    assert "missing_gates=DAVDEPLOY_NOVA_PLAN_RUNNER_READY" in output.err
    assert "PRIVATE_TOKEN" not in output.err
    assert "private-token-value" not in output.err
