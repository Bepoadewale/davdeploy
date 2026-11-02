#!/usr/bin/env python3
"""Verify bounded HTTP health and cleanup evidence for certification runs."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from urllib.error import URLError
from urllib.request import urlopen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--expected-status", type=int, default=200)
    parser.add_argument("--evidence", required=True)
    args = parser.parse_args()
    try:
        with urlopen(args.url, timeout=20) as response:
            status = response.status
            body = response.read(512).decode("utf-8", errors="replace")
    except URLError as error:
        status, body = 0, str(error)
    result = {"url": args.url, "status": status, "expected_status": args.expected_status, "healthy": status == args.expected_status, "body_sample": body, "observed_at": datetime.now(UTC).isoformat()}
    with open(args.evidence, "w") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    return 0 if result["healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
