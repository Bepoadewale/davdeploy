"""Run redacted success and Catch/recovery executions for the test fixture."""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def wait_for_execution(client, execution_arn: str) -> dict:
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        result = client.describe_execution(executionArn=execution_arn)
        if result.get("status") in {
            "SUCCEEDED",
            "FAILED",
            "TIMED_OUT",
            "ABORTED",
        }:
            return result
        time.sleep(2)
    raise TimeoutError("Step Functions execution did not finish before deadline")


def event_types(client, execution_arn: str) -> set[str]:
    result: set[str] = set()
    token = None
    while True:
        request = {"executionArn": execution_arn, "includeExecutionData": False}
        if token:
            request["nextToken"] = token
        response = client.get_execution_history(**request)
        result.update(
            event.get("type", "")
            for event in response.get("events", [])
            if isinstance(event, dict)
        )
        token = response.get("nextToken")
        if not token:
            return result


def run(region: str, state_machine_arn: str) -> dict:
    client = boto3.Session(region_name=region).client("stepfunctions")
    marker = f"nova-stepfn-454-{uuid.uuid4()}"

    failed_arn = client.start_execution(
        stateMachineArn=state_machine_arn,
        input=json.dumps({"should_fail": True, "marker": marker}),
    )["executionArn"]
    failed_result = wait_for_execution(client, failed_arn)
    failed_history = event_types(client, failed_arn)
    try:
        recovered_output = json.loads(failed_result.get("output", "{}"))
    except (TypeError, ValueError):
        recovered_output = {}

    success_marker = f"{marker}-success"
    success_arn = client.start_execution(
        stateMachineArn=state_machine_arn,
        input=json.dumps({"should_fail": False, "marker": success_marker}),
    )["executionArn"]
    success_result = wait_for_execution(client, success_arn)
    success_history = event_types(client, success_arn)
    try:
        success_output = json.loads(success_result.get("output", "{}"))
    except (TypeError, ValueError):
        success_output = {}

    return {
        "body_omitted": True,
        "failure_execution_succeeded": failed_result.get("status") == "SUCCEEDED",
        "failure_was_observed": "LambdaFunctionFailed" in failed_history,
        "recovery_task_succeeded": "LambdaFunctionSucceeded" in failed_history,
        "recovery_marker_matched": recovered_output.get("marker") == marker,
        "recovery_flag_set": recovered_output.get("recovered") is True,
        "success_execution_succeeded": success_result.get("status") == "SUCCEEDED",
        "success_task_succeeded": "LambdaFunctionSucceeded" in success_history,
        "success_marker_matched": success_output.get("marker") == success_marker,
        "success_path_not_recovered": success_output.get("recovered") is False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--state-machine-arn", required=True)
    args = parser.parse_args()
    try:
        result = run(args.region, args.state_machine_arn)
    except (BotoCoreError, ClientError, KeyError, TimeoutError, TypeError, ValueError) as error:
        print(json.dumps({"ok": False, "error_type": type(error).__name__}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if all(result.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
