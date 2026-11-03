#!/usr/bin/env python3
"""Run bounded, disposable Terraform certification roots and write evidence.

The caller must explicitly opt in per scenario.  The script never reads
customer credentials or accepts arbitrary Terraform arguments.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from davdeploy.certification_factory import certification_scenarios

ROOTS = {
    "web-application": ("delivery", "cloudfront"),
    "saas-backend": ("data-services",),
    "async-data": ("events", "batch"),
    "ai-rag": ("ai", "bedrock", "opensearch"),
    "kubernetes": ("eks",),
    "hybrid-network": ("vpn",),
    "multi-region": ("dns-failover",),
    "machine-learning": ("sagemaker",),
}


def run(command: list[str], *, env: dict[str, str]) -> dict[str, object]:
    completed = subprocess.run(command, text=True, capture_output=True, env=env, check=False)
    return {"command": command, "returncode": completed.returncode, "stdout": completed.stdout[-4000:], "stderr": completed.stderr[-4000:]}


def main() -> int:
    choices = tuple(item.identifier for item in certification_scenarios())
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=choices)
    parser.add_argument("--test-id", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()

    if args.apply and os.environ.get("DAVDEPLOY_DISPOSABLE_CERTIFICATION") != args.test_id:
        raise SystemExit("set DAVDEPLOY_DISPOSABLE_CERTIFICATION exactly to --test-id before apply")
    profile = os.environ.get("AWS_PROFILE", "")
    if args.apply and not profile:
        raise SystemExit("AWS_PROFILE is required for a real certification run")

    root_base = Path(__file__).resolve().parents[1] / "infrastructure" / "terraform" / "module-validation"
    environment = os.environ.copy()
    results: list[dict[str, object]] = []
    for root in ROOTS[args.scenario]:
        directory = root_base / root
        results.append(run(["terraform", f"-chdir={directory}", "init", "-input=false"], env=environment))
        if args.apply:
            if root == "sagemaker":
                results.append(
                    {
                        "command": ["scripts/certify_sagemaker_endpoint.py"],
                        "returncode": 2,
                        "stdout": "",
                        "stderr": "SageMaker certification requires its artifact upload and live inference probe workflow.",
                    }
                )
            else:
                results.append(run(["terraform", f"-chdir={directory}", "apply", "-auto-approve", "-input=false", f"-var=test_id={args.test_id}"], env=environment))
                results.append(run(["terraform", f"-chdir={directory}", "destroy", "-auto-approve", "-input=false", f"-var=test_id={args.test_id}"], env=environment))
        else:
            results.append(run(["terraform", f"-chdir={directory}", "validate"], env=environment))
    evidence = {"scenario": args.scenario, "test_id": args.test_id, "executed_at": datetime.now(UTC).isoformat(), "apply": args.apply, "roots": ROOTS[args.scenario], "results": results, "limitations": ("SageMaker certification uses scripts/certify_sagemaker_endpoint.py to build an owned artifact, probe a real endpoint, and clean up through the PID-based Terraform monitor." if args.scenario == "machine-learning" else "Service-specific readiness probes are required before activation.")}
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(evidence, indent=2) + "\n")
    return 0 if all(result["returncode"] == 0 for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
