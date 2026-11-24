"""Invoke a disposable Lambda and verify its synthetic response."""

from __future__ import annotations

import argparse
import json
from typing import Any

import boto3


def verify_account(sts: Any, expected_account: str) -> None:
    actual_account = sts.get_caller_identity()["Account"]
    if actual_account != expected_account:
        raise RuntimeError("AWS caller account does not match the expected test account.")


def invoke_and_verify(
    lambda_client: Any,
    function_name: str,
    expected_version: str,
    test_id: str,
) -> dict[str, str]:
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps({"test_id": test_id}).encode("utf-8"),
    )
    if response.get("FunctionError"):
        raise RuntimeError("Lambda invocation reported a function error.")
    if response.get("StatusCode") != 200:
        raise RuntimeError("Lambda invocation did not return HTTP-style status 200.")

    payload = json.loads(response["Payload"].read())
    if payload != {"version": expected_version, "test_id": test_id}:
        raise RuntimeError("Lambda returned an unexpected synthetic test response.")

    return {"function_name": function_name, "version": expected_version, "result": "verified"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--function-name", required=True)
    parser.add_argument("--version", required=True, choices=("v1", "v2"))
    parser.add_argument("--test-id", required=True)
    parser.add_argument("--profile")
    args = parser.parse_args()

    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    verify_account(session.client("sts"), args.account_id)
    result = invoke_and_verify(
        session.client("lambda"), args.function_name, args.version, args.test_id
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
