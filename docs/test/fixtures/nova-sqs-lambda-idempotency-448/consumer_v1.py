import json
import os

import boto3
from botocore.exceptions import ClientError


table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


def handler(event, context):
    for record in event.get("Records", []):
        payload = json.loads(record["body"])
        if payload.get("mode") == "fail":
            raise RuntimeError("controlled-v1-failure")
        try:
            table.put_item(
                Item={
                    "idempotency_key": payload["idempotency_key"],
                    "consumer_version": "v1",
                },
                ConditionExpression="attribute_not_exists(idempotency_key)",
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise

    return {"processed": len(event.get("Records", [])), "version": "v1"}
