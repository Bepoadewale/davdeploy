"""Exercise PITR restore behavior for one tagged disposable DynamoDB table."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from botocore.exceptions import ClientError


def wait_for_table(
    dynamodb: Any,
    table_name: str,
    expected_status: str,
    *,
    timeout_seconds: int = 1800,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            table = dynamodb.describe_table(TableName=table_name)["Table"]
        except dynamodb.exceptions.ResourceNotFoundException:
            if expected_status == "ABSENT":
                return {}
            time.sleep(10)
            continue
        if table.get("TableStatus") == expected_status:
            return table
        time.sleep(10)
    raise TimeoutError(f"DynamoDB table {table_name} did not reach {expected_status}.")


def continuous_backup_description(dynamodb: Any, table_name: str) -> dict[str, Any]:
    response = dynamodb.describe_continuous_backups(TableName=table_name)
    return response["ContinuousBackupsDescription"]["PointInTimeRecoveryDescription"]


def wait_for_restore_point(
    dynamodb: Any,
    table_name: str,
    baseline_written_at: datetime,
    *,
    timeout_seconds: int = 1200,
) -> tuple[datetime, dict[str, Any]]:
    deadline = time.monotonic() + timeout_seconds
    minimum_point = baseline_written_at + timedelta(seconds=2)
    while time.monotonic() < deadline:
        recovery = continuous_backup_description(dynamodb, table_name)
        latest = recovery.get("LatestRestorableDateTime")
        earliest = recovery.get("EarliestRestorableDateTime")
        if (
            recovery.get("PointInTimeRecoveryStatus") == "ENABLED"
            and latest is not None
            and earliest is not None
            and latest >= minimum_point
        ):
            return latest, recovery
        time.sleep(20)
    raise TimeoutError("DynamoDB did not expose a restorable point after the baseline write.")


def verify_source_table(dynamodb: Any, table_name: str) -> dict[str, Any]:
    table = wait_for_table(dynamodb, table_name, "ACTIVE")
    if table.get("BillingModeSummary", {}).get("BillingMode") != "PAY_PER_REQUEST":
        raise AssertionError("Source table is not PAY_PER_REQUEST.")
    if table.get("SSEDescription", {}).get("Status") != "ENABLED":
        raise AssertionError("Source table server-side encryption is not enabled.")
    if table.get("DeletionProtectionEnabled") is not True:
        raise AssertionError("Source table deletion protection is not enabled.")
    recovery = continuous_backup_description(dynamodb, table_name)
    if recovery.get("PointInTimeRecoveryStatus") != "ENABLED":
        raise AssertionError("Source table point-in-time recovery is not enabled.")
    return {
        "status": table["TableStatus"],
        "billing_mode": table["BillingModeSummary"]["BillingMode"],
        "encryption": table["SSEDescription"]["Status"],
        "deletion_protection": table["DeletionProtectionEnabled"],
        "pitr_status": recovery["PointInTimeRecoveryStatus"],
        "pitr_recovery_period_days": recovery.get("RecoveryPeriodInDays"),
        "table_arn": table["TableArn"],
    }


def cleanup_restored_table(dynamodb: Any, table_name: str, test_id: str) -> None:
    table = wait_for_table(dynamodb, table_name, "ACTIVE")
    dynamodb.tag_resource(
        ResourceArn=table["TableArn"],
        Tags=[
            {"Key": "TestId", "Value": test_id},
            {"Key": "Purpose", "Value": "davdeploy-nova-dynamodb-pitr-recovery-test"},
        ],
    )
    if table.get("DeletionProtectionEnabled") is True:
        dynamodb.update_table(
            TableName=table_name,
            DeletionProtectionEnabled=False,
        )
        table = wait_for_table(dynamodb, table_name, "ACTIVE")
        if table.get("DeletionProtectionEnabled") is not False:
            raise AssertionError("Restored table deletion protection did not disable.")
    dynamodb.delete_table(TableName=table_name)
    wait_for_table(dynamodb, table_name, "ABSENT")


def run(args: argparse.Namespace) -> dict[str, Any]:
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    account_id = session.client("sts").get_caller_identity()["Account"]
    if account_id != args.expected_account:
        raise RuntimeError(
            f"Refusing test: caller account {account_id} does not match expected account."
        )

    dynamodb = session.client("dynamodb")
    source = verify_source_table(dynamodb, args.source_table)
    try:
        dynamodb.describe_table(TableName=args.restore_table)
    except dynamodb.exceptions.ResourceNotFoundException:
        pass
    else:
        raise RuntimeError("Refusing test: the requested restore table already exists.")

    test_id = f"nova-dynamodb-pitr-487-{args.run_id}"
    baseline_key = f"{test_id}#baseline"
    later_key = f"{test_id}#after-restore-point"
    baseline_written_at = datetime.now(UTC)
    dynamodb.put_item(
        TableName=args.source_table,
        Item={"pk": {"S": baseline_key}, "payload": {"S": "baseline"}},
    )

    restore_at, recovery = wait_for_restore_point(
        dynamodb,
        args.source_table,
        baseline_written_at,
    )
    # RestoreDateTime is second-granular for this test; ensure the next write
    # cannot fall in the same second as the captured restore timestamp.
    time.sleep(2)
    dynamodb.put_item(
        TableName=args.source_table,
        Item={"pk": {"S": later_key}, "payload": {"S": "after-restore-point"}},
    )

    restore_started_at = datetime.now(UTC)
    dynamodb.restore_table_to_point_in_time(
        SourceTableName=args.source_table,
        TargetTableName=args.restore_table,
        RestoreDateTime=restore_at,
        BillingModeOverride="PAY_PER_REQUEST",
    )
    try:
        restored = wait_for_table(dynamodb, args.restore_table, "ACTIVE")

        baseline = dynamodb.get_item(
            TableName=args.restore_table,
            Key={"pk": {"S": baseline_key}},
            ConsistentRead=True,
        ).get("Item")
        later = dynamodb.get_item(
            TableName=args.restore_table,
            Key={"pk": {"S": later_key}},
            ConsistentRead=True,
        ).get("Item")
        if baseline is None or baseline.get("payload", {}).get("S") != "baseline":
            raise AssertionError("Restored table does not contain the baseline item.")
        if later is not None:
            raise AssertionError("Restored table unexpectedly contains the later item.")

        restored_encryption = restored.get("SSEDescription", {}).get("Status")
        if restored_encryption != "ENABLED":
            raise AssertionError("Restored table encryption is not enabled.")
        if restored.get("BillingModeSummary", {}).get("BillingMode") != "PAY_PER_REQUEST":
            raise AssertionError("Restored table is not PAY_PER_REQUEST.")
    finally:
        cleanup_restored_table(dynamodb, args.restore_table, test_id)

    return {
        "account_id": account_id,
        "region": args.region,
        "source_table": args.source_table,
        "restore_table": args.restore_table,
        "source": source,
        "pitr_status": recovery["PointInTimeRecoveryStatus"],
        "restore_timestamp": restore_at.isoformat(),
        "restore_started_at": restore_started_at.isoformat(),
        "restored_status": restored["TableStatus"],
        "restored_encryption": restored_encryption,
        "baseline_present": True,
        "post_restore_point_item_absent": True,
        "restored_table_absent_after_cleanup": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--expected-account", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-table", required=True)
    parser.add_argument("--restore-table", required=True)
    return parser.parse_args()


def main() -> int:
    try:
        result = run(parse_args())
    except (AssertionError, ClientError, RuntimeError, TimeoutError) as error:
        print(f"DynamoDB PITR lifecycle test failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
