#!/usr/bin/env python3
"""Low-overhead monitor for isolated Terraform applies and destroys.

The monitor starts one child process per run, captures its complete output and
records only local operational metadata. It never stores credentials, and it
refuses overlapping mutations for the same Terraform root.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def home() -> Path:
    return Path(os.environ.get("DAVDEPLOY_TERRAFORM_RUN_HOME", Path(os.environ.get("TMPDIR", "/tmp")) / "davdeploy-terraform-runs"))


def registry_path() -> Path:
    return home() / "runs.json"


def load() -> dict[str, dict[str, object]]:
    path = registry_path()
    return json.loads(path.read_text()) if path.exists() else {}


def save(runs: dict[str, dict[str, object]]) -> None:
    home().mkdir(parents=True, exist_ok=True)
    registry_path().write_text(json.dumps(runs, indent=2, sort_keys=True) + "\n")


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def refresh(runs: dict[str, dict[str, object]]) -> None:
    for run in runs.values():
        if run["state"] == "RUNNING" and not alive(int(run["pid"])):
            run["state"] = "FINISHED_UNKNOWN_EXIT"
            run["finished_at"] = datetime.now(UTC).isoformat()


def launch(args: argparse.Namespace) -> None:
    root = str(Path(args.root).resolve())
    runs = load()
    refresh(runs)
    if any(item["root"] == root and item["state"] == "RUNNING" for item in runs.values()):
        raise SystemExit(f"a Terraform mutation is already running for {root}")
    run_id = args.run_id or f"tf-{uuid4()}"
    log = home() / f"{run_id}.log"
    home().mkdir(parents=True, exist_ok=True)
    command = ["terraform", f"-chdir={root}", args.operation, "-auto-approve", "-input=false", *args.terraform_arg]
    handle = log.open("w")
    process = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
    runs[run_id] = {"run_id": run_id, "root": root, "operation": args.operation, "pid": process.pid, "state": "RUNNING", "started_at": datetime.now(UTC).isoformat(), "log": str(log), "command": command}
    save(runs)
    print(json.dumps(runs[run_id]))


def status(args: argparse.Namespace) -> None:
    runs = load()
    refresh(runs)
    save(runs)
    selected = runs.get(args.run_id) if args.run_id else runs
    print(json.dumps(selected, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start")
    start.add_argument("operation", choices=("apply", "destroy"))
    start.add_argument("root")
    start.add_argument("--run-id")
    start.add_argument("--terraform-arg", action="append", default=[])
    start.set_defaults(func=launch)
    check = commands.add_parser("status")
    check.add_argument("run_id", nargs="?")
    check.set_defaults(func=status)
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
