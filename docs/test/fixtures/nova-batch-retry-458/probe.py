"""Submit one disposable Batch retry job and report redacted assertions."""

from __future__ import annotations

import json
import re
import sys
import time

import boto3


TIMEOUT_SECONDS = 900
POLL_SECONDS = 10


def _attempt_marker(logs, log_stream_name: str) -> int | None:
    token = None
    lines: list[str] = []
    while True:
        arguments = {
            "logGroupName": sys.argv[3],
            "logStreamName": log_stream_name,
            "startFromHead": True,
            "limit": 100,
        }
        if token:
            arguments["nextToken"] = token
        response = logs.get_log_events(**arguments)
        lines.extend(event.get("message", "") for event in response.get("events", []))
        next_token = response.get("nextForwardToken")
        if not next_token or next_token == token:
            break
        token = next_token
    match = re.search(r"attempt=([12])", "\n".join(lines))
    return int(match.group(1)) if match else None


def main() -> int:
    if len(sys.argv) != 4:
        return 2
    batch = boto3.client("batch")
    logs = boto3.client("logs")
    submitted = batch.submit_job(
        jobName="davdeploy-nova-batch-retry-probe",
        jobQueue=sys.argv[1],
        jobDefinition=sys.argv[2],
    )
    job_id = submitted["jobId"]
    deadline = time.monotonic() + TIMEOUT_SECONDS
    job = None
    while time.monotonic() < deadline:
        jobs = batch.describe_jobs(jobs=[job_id]).get("jobs", [])
        job = jobs[0] if jobs else None
        if isinstance(job, dict) and job.get("status") in {"SUCCEEDED", "FAILED"}:
            break
        time.sleep(POLL_SECONDS)
    if not isinstance(job, dict) or job.get("status") != "SUCCEEDED":
        print(json.dumps({"job_succeeded": False, "retry_verified": False}))
        return 1

    attempts = job.get("attempts", [])
    by_number: dict[int, int | None] = {}
    for attempt in attempts:
        container = attempt.get("container", {}) if isinstance(attempt, dict) else {}
        stream = container.get("logStreamName") if isinstance(container, dict) else None
        exit_code = container.get("exitCode") if isinstance(container, dict) else None
        if isinstance(stream, str) and isinstance(exit_code, int):
            number = _attempt_marker(logs, stream)
            if number is not None:
                by_number[number] = exit_code

    first_failed = by_number.get(1) != 0
    second_succeeded = by_number.get(2) == 0
    retry_verified = by_number == {1: 1, 2: 0} and len(attempts) == 2
    print(
        json.dumps(
            {
                "job_succeeded": True,
                "attempt_count": len(attempts),
                "first_attempt_failed": first_failed,
                "second_attempt_succeeded": second_succeeded,
                "retry_verified": retry_verified,
            },
            sort_keys=True,
        )
    )
    return 0 if retry_verified else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print(json.dumps({"job_succeeded": False, "retry_verified": False}))
        raise SystemExit(1) from None
