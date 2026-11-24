"""Verify a disposable private S3 bucket and synthetic object-version lifecycle."""

from __future__ import annotations

import argparse
import json
import re
from typing import Any

import boto3

BUCKET_PREFIX = "davdeploy-nova-artifacts-491-"
TEST_ID_PATTERN = re.compile(r"^[a-z0-9-]{6,24}$")


def verify_account(sts: Any, expected_account: str) -> None:
    if sts.get_caller_identity().get("Account") != expected_account:
        raise RuntimeError("AWS caller account does not match the expected test account.")


def object_key(test_id: str) -> str:
    if not TEST_ID_PATTERN.fullmatch(test_id):
        raise ValueError("test_id must contain 6-24 lowercase letters, digits, or hyphens.")
    return f"nova-s3-artifacts-491/{test_id}/synthetic.txt"


def verify_bucket_configuration(s3: Any, bucket_name: str, test_id: str) -> dict[str, str]:
    if not bucket_name.startswith(BUCKET_PREFIX):
        raise ValueError("bucket name is outside the dedicated PR #491 test prefix.")

    expected_tag = f"nova-s3-artifacts-491-{test_id}"
    tags = {item["Key"]: item["Value"] for item in s3.get_bucket_tagging(Bucket=bucket_name)["TagSet"]}
    if tags.get("TestId") != expected_tag:
        raise RuntimeError("bucket TestId tag does not match this test run.")

    public_access = s3.get_public_access_block(Bucket=bucket_name)["PublicAccessBlockConfiguration"]
    public_fields = (
        "BlockPublicAcls",
        "BlockPublicPolicy",
        "IgnorePublicAcls",
        "RestrictPublicBuckets",
    )
    if not all(public_access.get(field) is True for field in public_fields):
        raise RuntimeError("bucket public-access block is incomplete.")

    rules = s3.get_bucket_ownership_controls(Bucket=bucket_name)["OwnershipControls"]["Rules"]
    if len(rules) != 1 or rules[0].get("ObjectOwnership") != "BucketOwnerEnforced":
        raise RuntimeError("bucket ownership is not BucketOwnerEnforced.")

    if s3.get_bucket_versioning(Bucket=bucket_name).get("Status") != "Enabled":
        raise RuntimeError("bucket versioning is not enabled.")

    encryption_rules = s3.get_bucket_encryption(Bucket=bucket_name)["ServerSideEncryptionConfiguration"]["Rules"]
    if not any(
        rule.get("ApplyServerSideEncryptionByDefault", {}).get("SSEAlgorithm") == "AES256"
        for rule in encryption_rules
    ):
        raise RuntimeError("bucket default server-side encryption is not AES256.")

    return {
        "public_access_block": "verified",
        "ownership": "BucketOwnerEnforced",
        "versioning": "Enabled",
        "default_encryption": "AES256",
    }


def _exact_key_versions(s3: Any, bucket_name: str, key: str) -> list[dict[str, str]]:
    paginator = s3.get_paginator("list_object_versions")
    matches: list[dict[str, str]] = []
    for page in paginator.paginate(Bucket=bucket_name, Prefix=key):
        for field in ("Versions", "DeleteMarkers"):
            for item in page.get(field, []):
                if item.get("Key") == key:
                    matches.append({"Key": key, "VersionId": item["VersionId"]})
    return matches


def cleanup_exact_object(s3: Any, bucket_name: str, test_id: str) -> int:
    """Remove only versions and delete markers for this run's exact synthetic key."""
    verify_bucket_configuration(s3, bucket_name, test_id)
    key = object_key(test_id)
    versions = _exact_key_versions(s3, bucket_name, key)
    if versions:
        s3.delete_objects(
            Bucket=bucket_name,
            Delete={"Objects": versions, "Quiet": True},
        )
    if _exact_key_versions(s3, bucket_name, key):
        raise RuntimeError("synthetic object versions remain after exact-key cleanup.")
    return len(versions)


def _read_object(s3: Any, bucket_name: str, key: str, version_id: str | None = None) -> tuple[bytes, str]:
    request: dict[str, str] = {"Bucket": bucket_name, "Key": key}
    if version_id is not None:
        request["VersionId"] = version_id
    response = s3.get_object(**request)
    body = response["Body"].read()
    if response.get("ServerSideEncryption") != "AES256":
        raise RuntimeError("synthetic object response did not report AES256 encryption.")
    return body, response["VersionId"]


def exercise_object_lifecycle(s3: Any, bucket_name: str, test_id: str) -> dict[str, Any]:
    configuration = verify_bucket_configuration(s3, bucket_name, test_id)
    key = object_key(test_id)
    version_ids: list[str] = []
    cleaned_versions = 0
    owns_key = False
    try:
        if _exact_key_versions(s3, bucket_name, key):
            raise RuntimeError("the exact synthetic object key already has versions.")

        first = s3.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=b"davdeploy synthetic artifact v1",
            ContentType="text/plain",
        )
        owns_key = True
        version_ids.append(first["VersionId"])
        if _read_object(s3, bucket_name, key, first["VersionId"])[0] != b"davdeploy synthetic artifact v1":
            raise RuntimeError("version 1 object content did not match.")

        second = s3.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=b"davdeploy synthetic artifact v2",
            ContentType="text/plain",
        )
        version_ids.append(second["VersionId"])
        if first["VersionId"] == second["VersionId"]:
            raise RuntimeError("versioned object update did not create a new version.")
        if _read_object(s3, bucket_name, key)[0] != b"davdeploy synthetic artifact v2":
            raise RuntimeError("latest object content did not match version 2.")
        if _read_object(s3, bucket_name, key, first["VersionId"])[0] != b"davdeploy synthetic artifact v1":
            raise RuntimeError("previous object version was not readable.")

        listed = _exact_key_versions(s3, bucket_name, key)
        listed_ids = {item["VersionId"] for item in listed}
        if set(version_ids) - listed_ids:
            raise RuntimeError("expected object versions were not present in S3 version history.")
        result = {
            "bucket_name": bucket_name,
            "test_id": test_id,
            "object_versions_verified": len(version_ids),
            "latest_version_id": second["VersionId"],
            "previous_version_readable": True,
            **configuration,
        }
    finally:
        if owns_key:
            cleaned_versions = cleanup_exact_object(s3, bucket_name, test_id)
            if cleaned_versions < len(version_ids):
                raise RuntimeError("not all versions created by this test were removed.")

    return {**result, "cleaned_version_count": cleaned_versions}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--bucket-name", required=True)
    parser.add_argument("--test-id", required=True)
    parser.add_argument("--profile")
    args = parser.parse_args()

    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    verify_account(session.client("sts"), args.account_id)
    result = exercise_object_lifecycle(session.client("s3"), args.bucket_name, args.test_id)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
