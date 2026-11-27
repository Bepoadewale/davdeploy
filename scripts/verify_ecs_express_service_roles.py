"""Verify the fixed customer-side ECS Express service-role profile."""

from __future__ import annotations

import argparse
import json
import os
import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from davdeploy.ecs_express_service_roles import (
    EcsExpressServiceRoleProfileError,
    profile_evidence,
    verify_ecs_express_service_roles,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--connection-id", required=True)
    args = parser.parse_args()

    try:
        session = boto3.Session(profile_name=os.environ.get("AWS_PROFILE"))
        profile = verify_ecs_express_service_roles(
            session.client("iam"),
            account_id=args.account_id,
            connection_id=args.connection_id,
        )
    except EcsExpressServiceRoleProfileError as error:
        print(str(error), file=sys.stderr)
        return 3
    except (BotoCoreError, ClientError, ValueError):
        print("ECS Express service-role verification could not complete", file=sys.stderr)
        return 3

    print(json.dumps(profile_evidence(profile), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
