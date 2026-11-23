"""Redacted direct-service failure and recovery probe for the isolated fixture."""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def receive(sqs, queue_url: str, marker_prefix: str, deadline: float) -> tuple[bool, bool]:
    while time.monotonic() < deadline:
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=2,
            VisibilityTimeout=10,
            MessageAttributeNames=["All"],
        )
        for message in response.get("Messages", []):
            matched = marker_prefix in message.get("Body", "")
            sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=message["ReceiptHandle"],
            )
            return True, matched
    return False, False


def publish(events, bus_name: str, marker: str) -> None:
    response = events.put_events(
        Entries=[
            {
                "EventBusName": bus_name,
                "Source": "davdeploy.nova.test",
                "DetailType": "eventbridge-dlq-test",
                "Detail": json.dumps({"marker": marker}),
            }
        ]
    )
    if response.get("FailedEntryCount") != 0:
        raise RuntimeError("event submission failed")


def run(stage: str, region: str, bus_name: str, target_url: str, dlq_url: str) -> dict:
    session = boto3.Session(region_name=region)
    events = session.client("events")
    sqs = session.client("sqs")
    marker = f"nova-eventbridge-452-{uuid.uuid4()}"
    publish(events, bus_name, marker)
    deadline = time.monotonic() + 300

    if stage == "failure":
        target_received, _ = receive(
            sqs, target_url, "nova-eventbridge-452-", time.monotonic() + 15
        )
        if target_received:
            return {"published": True, "target_blocked": False, "body_omitted": True}
        dlq_received, marker_matched = receive(
            sqs, dlq_url, "nova-eventbridge-452-", deadline
        )
        return {
            "published": True,
            "target_blocked": True,
            "dlq_received": dlq_received,
            "marker_matched": marker_matched,
            "body_omitted": True,
        }

    target_received, marker_matched = receive(
        sqs, target_url, "nova-eventbridge-452-", deadline
    )
    return {
        "published": True,
        "target_received": target_received,
        "marker_matched": marker_matched,
        "body_omitted": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("failure", "recovery"))
    parser.add_argument("--region", required=True)
    parser.add_argument("--bus-name", required=True)
    parser.add_argument("--target-queue-url", required=True)
    parser.add_argument("--dlq-url", required=True)
    args = parser.parse_args()
    try:
        result = run(
            args.stage,
            args.region,
            args.bus_name,
            args.target_queue_url,
            args.dlq_url,
        )
    except (
        AttributeError,
        BotoCoreError,
        ClientError,
        KeyError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as error:
        print(json.dumps({"ok": False, "error_type": type(error).__name__}))
        return 1
    print(json.dumps(result, sort_keys=True))
    expected = (
        result.get("published")
        and result.get("body_omitted")
        and (
            result.get("dlq_received") and result.get("marker_matched")
            if args.stage == "failure"
            else result.get("target_received") and result.get("marker_matched")
        )
    )
    return 0 if expected else 1


if __name__ == "__main__":
    sys.exit(main())
