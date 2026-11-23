"""Publish and receive one synthetic SNS-to-SQS delivery without printing its body."""

import json
import os
import sys

import boto3


def main() -> int:
    topic_arn = os.environ["TEST_TOPIC_ARN"]
    queue_url = os.environ["TEST_QUEUE_URL"]
    expected = {
        "test_run": "davdeploy-nova-sns-sqs-449-nov23a1",
        "message_id": "synthetic-001",
        "kind": "sns-delivery",
    }
    sns = boto3.client("sns", region_name="us-east-1")
    sqs = boto3.client("sqs", region_name="us-east-1")
    result = sns.publish(TopicArn=topic_arn, Message=json.dumps(expected))
    for _ in range(15):
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=2,
            AttributeNames=["ApproximateReceiveCount"],
        )
        messages = response.get("Messages", [])
        if not messages:
            continue
        message = messages[0]
        received = json.loads(message["Body"])
        matched = received == expected
        if matched:
            sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=message["ReceiptHandle"],
            )
        print(
            json.dumps(
                {
                    "published": bool(result.get("MessageId")),
                    "received": True,
                    "payload_matched": matched,
                    "receive_count": message.get("Attributes", {}).get(
                        "ApproximateReceiveCount"
                    ),
                    "message_body_omitted": True,
                },
                sort_keys=True,
            )
        )
        return 0 if matched else 1
    print(json.dumps({"published": bool(result.get("MessageId")), "received": False}))
    return 1


if __name__ == "__main__":
    sys.exit(main())
