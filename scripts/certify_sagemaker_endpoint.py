#!/usr/bin/env python3
"""Prepare and probe the isolated SageMaker endpoint certification.

Terraform owns the endpoint, its role and the temporary artifact bucket. This
helper never creates cloud resources itself: it builds an XGBoost artifact for
that bucket, uploads it with SSE-S3, and performs one bounded inference probe.
Run it through ``uv run --extra certification`` so the pinned local XGBoost
format matches the managed SageMaker XGBoost 1.7 container.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def require_opt_in(test_id: str) -> None:
    if os.environ.get("DAVDEPLOY_DISPOSABLE_CERTIFICATION") != test_id:
        raise SystemExit(
            "set DAVDEPLOY_DISPOSABLE_CERTIFICATION exactly to --test-id before a real certification action"
        )
    if not os.environ.get("AWS_PROFILE"):
        raise SystemExit("AWS_PROFILE is required for a real certification action")


def command(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, check=True, text=True, capture_output=True)


def prepare_artifact(bucket: str, test_id: str) -> dict[str, str]:
    require_opt_in(test_id)
    try:
        import xgboost as xgb
    except ImportError as error:
        raise SystemExit("run with `uv run --extra certification python scripts/certify_sagemaker_endpoint.py ...`") from error

    with tempfile.TemporaryDirectory(prefix="davdeploy-sagemaker-") as directory:
        output = Path(directory)
        model_path = output / "xgboost-model.json"
        archive_path = output / "model.tar.gz"
        training = xgb.DMatrix([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0], [3.0, 3.0]], label=[0.0, 1.0, 2.0, 3.0])
        model = xgb.train(
            {"objective": "reg:squarederror", "max_depth": 2, "eta": 0.3, "seed": 7},
            training,
            num_boost_round=8,
        )
        model.save_model(model_path)
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(model_path, arcname=model_path.name)
        key = f"model/{test_id}/model.tar.gz"
        command(["aws", "s3", "cp", str(archive_path), f"s3://{bucket}/{key}", "--sse", "AES256"])
    return {"bucket": bucket, "key": key, "model_data_url": f"s3://{bucket}/{key}"}


def probe_endpoint(endpoint: str, test_id: str) -> dict[str, object]:
    require_opt_in(test_id)
    with tempfile.TemporaryDirectory(prefix="davdeploy-sagemaker-response-") as directory:
        response_path = Path(directory) / "response.json"
        result = command(
            [
                "aws",
                "sagemaker-runtime",
                "invoke-endpoint",
                "--endpoint-name",
                endpoint,
                "--content-type",
                "text/csv",
                "--cli-binary-format",
                "raw-in-base64-out",
                "--body",
                "1.5,1.5",
                str(response_path),
            ]
        )
        body = response_path.read_text().strip()
    metadata = json.loads(result.stdout)
    if not body or "error" in body.lower():
        raise SystemExit(f"SageMaker endpoint returned an invalid body: {body!r}")
    return {"endpoint": endpoint, "response_metadata": metadata, "response_body": body}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-id", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    artifact = commands.add_parser("prepare-artifact")
    artifact.add_argument("--bucket", required=True)
    probe = commands.add_parser("probe")
    probe.add_argument("--endpoint", required=True)
    args = parser.parse_args()

    if args.command == "prepare-artifact":
        result = prepare_artifact(args.bucket, args.test_id)
    else:
        result = probe_endpoint(args.endpoint, args.test_id)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
