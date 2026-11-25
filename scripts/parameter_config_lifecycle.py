"""Verify one test-owned SSM parameter without exposing its values."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import boto3


class LifecycleCheckError(RuntimeError):
    """Raised when the exact test parameter does not match expectations."""


def verify_account(sts: Any, expected_account_id: str) -> None:
    actual_account_id = sts.get_caller_identity().get("Account")
    if actual_account_id != expected_account_id:
        raise LifecycleCheckError("AWS caller account mismatch")


def _one_parameter(ssm: Any, name: str) -> dict[str, Any]:
    response = ssm.describe_parameters(
        ParameterFilters=[{"Key": "Name", "Option": "Equals", "Values": [name]}]
    )
    parameters = response.get("Parameters")
    if not isinstance(parameters, list) or len(parameters) != 1:
        raise LifecycleCheckError("expected exactly one parameter with the test name")
    parameter = parameters[0]
    if not isinstance(parameter, dict) or parameter.get("Name") != name:
        raise LifecycleCheckError("parameter metadata name mismatch")
    return parameter


def _verify_key(kms: Any, parameter: dict[str, Any]) -> str:
    key = kms.describe_key(KeyId="alias/aws/ssm").get("KeyMetadata")
    if not isinstance(key, dict):
        raise LifecycleCheckError("AWS managed SSM key metadata is missing")
    key_id = key.get("KeyId")
    key_arn = key.get("Arn")
    aliases = kms.list_aliases(KeyId=key_id).get("Aliases", [])
    if not isinstance(key_id, str) or not isinstance(key_arn, str):
        raise LifecycleCheckError("AWS managed SSM key identity is incomplete")
    if not any(alias.get("AliasName") == "alias/aws/ssm" for alias in aliases if isinstance(alias, dict)):
        raise LifecycleCheckError("the resolved KMS key is not alias/aws/ssm")
    if parameter.get("KeyId") not in {key_id, key_arn, "alias/aws/ssm"}:
        raise LifecycleCheckError("parameter KMS key does not match alias/aws/ssm")
    return key_arn


def _verify_tags(ssm: Any, *, name: str, test_id: str) -> None:
    response = ssm.list_tags_for_resource(ResourceType="Parameter", ResourceId=name)
    tags = response.get("TagList")
    if not isinstance(tags, list):
        raise LifecycleCheckError("parameter tags are missing")
    tag_map = {
        item.get("Key"): item.get("Value")
        for item in tags
        if isinstance(item, dict)
    }
    expected_tags = {
        "ManagedBy": "terraform",
        "Product": "davdeploy",
        "Purpose": "nova-parameter-config-493-test",
        "TestId": test_id,
    }
    if any(tag_map.get(key) != value for key, value in expected_tags.items()):
        raise LifecycleCheckError("parameter ownership tags do not match the test")


def verify_parameter_lifecycle(
    *,
    sts: Any,
    ssm: Any,
    kms: Any,
    expected_account_id: str,
    name: str,
    test_id: str,
    expected_v1: str,
    expected_v2: str,
) -> dict[str, Any]:
    verify_account(sts, expected_account_id)
    expected_name = f"/davdeploy/nova-parameter-config-493/{test_id}/synthetic"
    if name != expected_name:
        raise LifecycleCheckError("parameter name is not the exact test parameter")
    parameter = _one_parameter(ssm, name)
    if parameter.get("Type") != "SecureString" or parameter.get("Tier") != "Standard":
        raise LifecycleCheckError("parameter type or tier does not match the test profile")
    key_arn = _verify_key(kms, parameter)
    _verify_tags(ssm, name=name, test_id=test_id)

    current_version = parameter.get("Version")
    if current_version != 2:
        raise LifecycleCheckError("parameter must have exactly two Terraform-managed versions")

    for version, expected_value in ((1, expected_v1), (2, expected_v2)):
        response = ssm.get_parameter(Name=f"{name}:{version}", WithDecryption=True)
        current = response.get("Parameter")
        if not isinstance(current, dict):
            raise LifecycleCheckError("requested parameter version is missing")
        if current.get("Version") != version or current.get("Name") != name:
            raise LifecycleCheckError("parameter version metadata mismatch")
        if current.get("Value") != expected_value:
            raise LifecycleCheckError("synthetic parameter value mismatch")

    return {
        "status": "verified",
        "account_id": expected_account_id,
        "name": name,
        "test_id": test_id,
        "type": "SecureString",
        "tier": "Standard",
        "kms_key_arn": key_arn,
        "versions_verified": [1, 2],
        "values_match": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--test-id", required=True)
    parser.add_argument("--profile")
    args = parser.parse_args(argv)
    expected_v1 = os.environ.get("DAVDEPLOY_PARAMETER_CONFIG_EXPECTED_V1")
    expected_v2 = os.environ.get("DAVDEPLOY_PARAMETER_CONFIG_EXPECTED_V2")
    if expected_v1 is None or expected_v2 is None:
        print(json.dumps({"status": "failed", "reason": "synthetic expected values are not configured"}))
        return 2

    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    try:
        result = verify_parameter_lifecycle(
            sts=session.client("sts"),
            ssm=session.client("ssm"),
            kms=session.client("kms"),
            expected_account_id=args.account_id,
            name=args.name,
            test_id=args.test_id,
            expected_v1=expected_v1,
            expected_v2=expected_v2,
        )
    except LifecycleCheckError as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
