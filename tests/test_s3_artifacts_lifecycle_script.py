from __future__ import annotations

import io

import pytest

from scripts.s3_artifacts_lifecycle import (
    cleanup_exact_object,
    exercise_object_lifecycle,
    verify_account,
    verify_bucket_configuration,
)


class FakeSTS:
    def __init__(self, account_id: str) -> None:
        self.account_id = account_id

    def get_caller_identity(self) -> dict[str, str]:
        return {"Account": self.account_id}


class FakePaginator:
    def __init__(self, client: FakeS3) -> None:
        self.client = client

    def paginate(self, *, Bucket: str, Prefix: str) -> list[dict[str, list[dict[str, str]]]]:
        assert Bucket == self.client.bucket_name
        versions = [
            {"Key": key, "VersionId": version_id}
            for key, version_id in self.client.versions
            if key.startswith(Prefix)
        ]
        return [{"Versions": versions, "DeleteMarkers": []}]


class FakeS3:
    def __init__(self, test_id: str = "20261124-a1b2c3") -> None:
        self.bucket_name = "davdeploy-nova-artifacts-491-20261124-a1b2c3"
        self.test_id = test_id
        self.tags = {
            "ManagedBy": "terraform",
            "Purpose": "davdeploy-nova-s3-artifacts-module-test",
            "TestId": f"nova-s3-artifacts-491-{test_id}",
        }
        self.objects: dict[tuple[str, str], bytes] = {}
        self.versions: list[tuple[str, str]] = []
        self.delete_requests: list[dict[str, object]] = []

    def get_bucket_tagging(self, *, Bucket: str) -> dict[str, list[dict[str, str]]]:
        assert Bucket == self.bucket_name
        return {"TagSet": [{"Key": key, "Value": value} for key, value in self.tags.items()]}

    def get_public_access_block(self, *, Bucket: str) -> dict[str, dict[str, bool]]:
        assert Bucket == self.bucket_name
        return {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            }
        }

    def get_bucket_ownership_controls(self, *, Bucket: str) -> dict[str, dict[str, list[dict[str, str]]]]:
        assert Bucket == self.bucket_name
        return {"OwnershipControls": {"Rules": [{"ObjectOwnership": "BucketOwnerEnforced"}]}}

    def get_bucket_versioning(self, *, Bucket: str) -> dict[str, str]:
        assert Bucket == self.bucket_name
        return {"Status": "Enabled"}

    def get_bucket_encryption(self, *, Bucket: str) -> dict[str, dict[str, list[dict[str, dict[str, str]]]]]:
        assert Bucket == self.bucket_name
        return {
            "ServerSideEncryptionConfiguration": {
                "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
            }
        }

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> dict[str, str]:
        assert Bucket == self.bucket_name
        assert ContentType == "text/plain"
        version_id = f"version-{len(self.versions) + 1}"
        self.objects[(Key, version_id)] = Body
        self.versions.append((Key, version_id))
        return {"VersionId": version_id}

    def get_object(self, *, Bucket: str, Key: str, VersionId: str | None = None) -> dict[str, object]:
        assert Bucket == self.bucket_name
        if VersionId is None:
            version_id = next(version for key, version in reversed(self.versions) if key == Key)
        else:
            version_id = VersionId
        return {
            "Body": io.BytesIO(self.objects[(Key, version_id)]),
            "VersionId": version_id,
            "ServerSideEncryption": "AES256",
        }

    def get_paginator(self, operation_name: str) -> FakePaginator:
        assert operation_name == "list_object_versions"
        return FakePaginator(self)

    def delete_objects(self, *, Bucket: str, Delete: dict[str, object]) -> dict[str, object]:
        assert Bucket == self.bucket_name
        objects = Delete["Objects"]
        self.delete_requests.append(Delete)
        for item in objects:
            key = item["Key"]
            version_id = item["VersionId"]
            self.objects.pop((key, version_id), None)
            self.versions.remove((key, version_id))
        return {"Deleted": objects}


def test_verify_account_accepts_only_expected_account() -> None:
    verify_account(FakeSTS("654654474502"), "654654474502")
    with pytest.raises(RuntimeError, match="expected test account"):
        verify_account(FakeSTS("111111111111"), "654654474502")


def test_bucket_configuration_verifies_module_safety_settings() -> None:
    client = FakeS3()

    result = verify_bucket_configuration(client, client.bucket_name, client.test_id)

    assert result == {
        "public_access_block": "verified",
        "ownership": "BucketOwnerEnforced",
        "versioning": "Enabled",
        "default_encryption": "AES256",
    }


def test_bucket_configuration_rejects_wrong_test_tag() -> None:
    client = FakeS3()
    client.tags["TestId"] = "unrelated-test"

    with pytest.raises(RuntimeError, match="TestId tag"):
        verify_bucket_configuration(client, client.bucket_name, client.test_id)


def test_object_lifecycle_reads_both_versions_and_cleans_exact_key() -> None:
    client = FakeS3()

    result = exercise_object_lifecycle(client, client.bucket_name, client.test_id)

    assert result["object_versions_verified"] == 2
    assert result["previous_version_readable"] is True
    assert result["cleaned_version_count"] == 2
    assert client.versions == []
    deleted = client.delete_requests[0]["Objects"]
    assert {item["Key"] for item in deleted} == {
        f"nova-s3-artifacts-491/{client.test_id}/synthetic.txt"
    }


def test_cleanup_rejects_wrong_test_tag_before_deleting() -> None:
    client = FakeS3()
    client.tags["TestId"] = "unrelated-test"

    with pytest.raises(RuntimeError, match="TestId tag"):
        cleanup_exact_object(client, client.bucket_name, client.test_id)

    assert client.delete_requests == []


def test_object_lifecycle_does_not_delete_preexisting_exact_key() -> None:
    client = FakeS3()
    key = f"nova-s3-artifacts-491/{client.test_id}/synthetic.txt"
    client.versions.append((key, "prior-version"))
    client.objects[(key, "prior-version")] = b"preserved"

    with pytest.raises(RuntimeError, match="already has versions"):
        exercise_object_lifecycle(client, client.bucket_name, client.test_id)

    assert client.delete_requests == []
    assert client.objects[(key, "prior-version")] == b"preserved"
