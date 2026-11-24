from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

from scripts import dynamodb_pitr_lifecycle as lifecycle


class ResourceNotFound(Exception):
    pass


class FakeDynamoDB:
    exceptions = SimpleNamespace(ResourceNotFoundException=ResourceNotFound)

    def __init__(self):
        self.table = {
            "TableName": "test-source",
            "TableArn": "arn:aws:dynamodb:us-east-1:654654474502:table/test-source",
            "TableStatus": "ACTIVE",
            "BillingModeSummary": {"BillingMode": "PAY_PER_REQUEST"},
            "SSEDescription": {"Status": "ENABLED"},
            "DeletionProtectionEnabled": True,
        }
        self.recovery = {
            "PointInTimeRecoveryStatus": "ENABLED",
            "RecoveryPeriodInDays": 35,
            "EarliestRestorableDateTime": datetime(2026, 11, 24, tzinfo=UTC),
            "LatestRestorableDateTime": datetime(2026, 11, 24, tzinfo=UTC),
        }
        self.recovery_responses = []
        self.tags = None
        self.updated_table = None
        self.deleted = None
        self.delete_failures = 0
        self.items = {}
        self.read_requests = []

    def describe_table(self, *, TableName):
        if self.table is None:
            raise ResourceNotFound
        assert TableName in {"test-source", "test-restored"}
        return {"Table": self.table}

    def describe_continuous_backups(self, *, TableName):
        if self.recovery_responses:
            response = self.recovery_responses.pop(0)
        else:
            response = self.recovery
        return {"ContinuousBackupsDescription": {"PointInTimeRecoveryDescription": response}}

    def get_item(self, *, TableName, Key, ConsistentRead):
        self.read_requests.append((TableName, Key, ConsistentRead))
        item = self.items.get(Key["pk"]["S"])
        return {"Item": {"payload": {"S": item}}} if item is not None else {}

    def tag_resource(self, *, ResourceArn, Tags):
        self.tags = (ResourceArn, Tags)

    def update_table(self, **kwargs):
        self.updated_table = kwargs["TableName"]
        self.table["DeletionProtectionEnabled"] = kwargs["DeletionProtectionEnabled"]

    def delete_table(self, *, TableName):
        if self.delete_failures:
            self.delete_failures -= 1
            raise ClientError(
                {"Error": {"Code": "ResourceInUseException", "Message": "tags updating"}},
                "DeleteTable",
            )
        self.deleted = TableName
        self.table = None


def test_wait_for_restore_point_requires_enabled_pitr_and_a_post_write_snapshot(monkeypatch):
    fake = FakeDynamoDB()
    baseline = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
    early = {**fake.recovery, "LatestRestorableDateTime": baseline + timedelta(seconds=1)}
    ready = {**fake.recovery, "LatestRestorableDateTime": baseline + timedelta(seconds=3)}
    fake.recovery_responses = [
        {**early, "PointInTimeRecoveryStatus": "ENABLING"},
        early,
        ready,
    ]
    monkeypatch.setattr(lifecycle.time, "sleep", lambda _seconds: None)

    point, recovery = lifecycle.wait_for_restore_point(
        fake,
        "test-source",
        baseline,
        timeout_seconds=1,
    )

    assert point == ready["LatestRestorableDateTime"]
    assert recovery["PointInTimeRecoveryStatus"] == "ENABLED"


def test_verify_source_table_checks_data_safety_settings():
    fake = FakeDynamoDB()

    result = lifecycle.verify_source_table(fake, "test-source")

    assert result["status"] == "ACTIVE"
    assert result["billing_mode"] == "PAY_PER_REQUEST"
    assert result["encryption"] == "ENABLED"
    assert result["deletion_protection"] is True
    assert result["pitr_status"] == "ENABLED"


def test_require_item_payload_uses_consistent_read():
    fake = FakeDynamoDB()
    fake.items["test-key"] = "synthetic-value"

    lifecycle.require_item_payload(fake, "test-table", "test-key", "synthetic-value")

    assert fake.read_requests == [
        ("test-table", {"pk": {"S": "test-key"}}, True)
    ]


def test_verify_source_table_fails_closed_when_deletion_protection_is_off():
    fake = FakeDynamoDB()
    fake.table["DeletionProtectionEnabled"] = False

    with pytest.raises(AssertionError, match="deletion protection"):
        lifecycle.verify_source_table(fake, "test-source")


def test_cleanup_restored_table_tags_exact_target_then_deletes(monkeypatch):
    fake = FakeDynamoDB()
    fake.table["TableName"] = "test-restored"
    fake.table["TableArn"] = "arn:aws:dynamodb:us-east-1:654654474502:table/test-restored"
    fake.table["DeletionProtectionEnabled"] = False
    monkeypatch.setattr(lifecycle.time, "sleep", lambda _seconds: None)

    lifecycle.cleanup_restored_table(fake, "test-restored", "test-id-487")

    assert fake.tags == (
        "arn:aws:dynamodb:us-east-1:654654474502:table/test-restored",
        [
            {"Key": "TestId", "Value": "test-id-487"},
            {"Key": "Purpose", "Value": "davdeploy-nova-dynamodb-pitr-recovery-test"},
        ],
    )
    assert fake.deleted == "test-restored"
    assert fake.table is None


def test_cleanup_disables_protection_only_on_restored_table(monkeypatch):
    fake = FakeDynamoDB()
    fake.table["TableName"] = "test-restored"
    fake.table["TableArn"] = "arn:aws:dynamodb:us-east-1:654654474502:table/test-restored"
    monkeypatch.setattr(lifecycle.time, "sleep", lambda _seconds: None)

    lifecycle.cleanup_restored_table(fake, "test-restored", "test-id-487")

    assert fake.deleted == "test-restored"
    assert fake.updated_table == "test-restored"
    assert fake.table is None


def test_cleanup_retries_delete_while_tags_are_updating(monkeypatch):
    fake = FakeDynamoDB()
    fake.table["TableName"] = "test-restored"
    fake.table["TableArn"] = "arn:aws:dynamodb:us-east-1:654654474502:table/test-restored"
    fake.table["DeletionProtectionEnabled"] = False
    fake.delete_failures = 2
    sleeps = []
    monkeypatch.setattr(lifecycle.time, "sleep", sleeps.append)

    lifecycle.cleanup_restored_table(fake, "test-restored", "test-id-487")

    assert fake.deleted == "test-restored"
    assert sleeps == [2, 4]
    assert fake.table is None
