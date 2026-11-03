#!/usr/bin/env python3
"""Supervise isolated Terraform mutations and record authoritative outcomes.

The supervisor waits for Terraform's exit code, keeps an OS lock for the
Terraform root, and atomically records local operational metadata. It never
stores credentials or raw Terraform variable values.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ACTIVE_STATES = {"STARTING", "RUNNING"}
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")


def home() -> Path:
    configured = os.environ.get("DAVDEPLOY_TERRAFORM_RUN_HOME")
    temporary = os.environ.get("TMPDIR", "/tmp")
    return Path(configured or (Path(temporary) / "davdeploy-terraform-runs"))


def registry_path() -> Path:
    return home() / "runs.json"


def _ensure_home() -> None:
    home().mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(home(), 0o700)
    (home() / ".locks").mkdir(exist_ok=True, mode=0o700)


@contextmanager
def registry_guard() -> Iterator[None]:
    _ensure_home()
    with (home() / ".registry.lock").open("a+") as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def load() -> dict[str, dict[str, object]]:
    path = registry_path()
    return json.loads(path.read_text()) if path.exists() else {}


def _save_unlocked(runs: dict[str, dict[str, object]]) -> None:
    _ensure_home()
    fd, temporary_name = tempfile.mkstemp(prefix=".runs-", suffix=".json", dir=home())
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(runs, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, registry_path())
        directory_fd = os.open(home(), os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def save(runs: dict[str, dict[str, object]]) -> None:
    with registry_guard():
        _save_unlocked(runs)


def _root_lock_path(root: str) -> Path:
    digest = hashlib.sha256(root.encode()).hexdigest()
    return home() / ".locks" / f"{digest}.lock"


def _open_root_lock(root: str) -> int:
    _ensure_home()
    path = _root_lock_path(root)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    os.chmod(path, 0o600)
    return fd


def alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def refresh(runs: dict[str, dict[str, object]]) -> None:
    """Keep active runs active while a supervisor or Terraform child is alive."""
    for run in runs.values():
        if run.get("state") not in ACTIVE_STATES:
            continue
        supervisor_pid = run.get("supervisor_pid")
        terraform_pid = run.get("terraform_pid") or run.get("pid")
        if not alive(_int_or_none(supervisor_pid)) and not alive(_int_or_none(terraform_pid)):
            run["state"] = "FINISHED_UNKNOWN_EXIT"
            run["finished_at"] = datetime.now(UTC).isoformat()
            run["exit_code"] = None
            run["outcome_note"] = "Supervisor and Terraform process are absent; exit status is unknown."


def _int_or_none(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _redacted_command(command: list[str]) -> list[str]:
    """Hide Terraform variable, backend-config, and credential-like values."""
    result: list[str] = []
    redact_next = False
    for argument in command:
        if redact_next:
            result.append("[REDACTED]")
            redact_next = False
            continue
        if argument in {"-var", "-var-file", "-backend-config"}:
            result.append(argument)
            redact_next = True
            continue
        if argument.startswith(("-var=", "-var-file=", "-backend-config=")):
            key = argument.split("=", 1)[0]
            result.append(f"{key}=[REDACTED]")
            continue
        if re.search(r"(?i)(secret|password|token|credential|private.?key)", argument):
            result.append("[REDACTED]")
            continue
        result.append(argument)
    return result


def _active_root_runs(runs: dict[str, dict[str, object]], root: str) -> list[str]:
    return [
        run_id
        for run_id, run in runs.items()
        if run.get("root") == root and run.get("state") in ACTIVE_STATES
    ]


def launch(args: argparse.Namespace) -> None:
    root = str(Path(args.root).resolve())
    run_id = args.run_id or f"tf-{uuid4()}"
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise SystemExit("run ID may contain only letters, digits, dot, underscore, and hyphen")
    log = home() / f"{run_id}.log"
    monitor_log = home() / f"{run_id}.monitor.log"
    command = [
        "terraform",
        f"-chdir={root}",
        args.operation,
        "-auto-approve",
        "-input=false",
        *args.terraform_arg,
    ]

    root_lock_fd = _open_root_lock(root)
    try:
        try:
            fcntl.flock(root_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise SystemExit(f"a Terraform mutation is already running for {root}") from error

        read_fd, write_fd = os.pipe()
        try:
            with registry_guard():
                runs = load()
                refresh(runs)
                if run_id in runs:
                    raise SystemExit(f"Terraform run ID already exists: {run_id}")
                active = _active_root_runs(runs, root)
                if active:
                    raise SystemExit(
                        f"a Terraform mutation is already active for {root}: {active[0]}"
                    )
                record: dict[str, object] = {
                    "run_id": run_id,
                    "root": root,
                    "operation": args.operation,
                    "state": "STARTING",
                    "started_at": datetime.now(UTC).isoformat(),
                    "log": str(log),
                    "monitor_log": str(monitor_log),
                    "command": _redacted_command(command),
                    "terraform_pid": None,
                    "supervisor_pid": None,
                    "exit_code": None,
                }
                runs[run_id] = record
                _save_unlocked(runs)
                os.close(root_lock_fd)
                root_lock_fd = -1
                supervisor_command = [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "_watch",
                    run_id,
                    str(read_fd),
                ]
                with monitor_log.open("ab") as supervisor_output:
                    supervisor = subprocess.Popen(
                        supervisor_command,
                        stdin=subprocess.DEVNULL,
                        stdout=supervisor_output,
                        stderr=subprocess.STDOUT,
                        close_fds=True,
                        pass_fds=(read_fd,),
                        start_new_session=True,
                    )
                record["supervisor_pid"] = supervisor.pid
                runs[run_id] = record
                _save_unlocked(runs)
        except BaseException:
            os.close(read_fd)
            os.close(write_fd)
            raise
        os.close(read_fd)
        payload = json.dumps(command).encode()
        with os.fdopen(write_fd, "wb") as command_pipe:
            command_pipe.write(payload)
        print(json.dumps(record, sort_keys=True), flush=True)
    finally:
        if root_lock_fd >= 0:
            fcntl.flock(root_lock_fd, fcntl.LOCK_UN)
            os.close(root_lock_fd)


def _write_state(run_id: str, **updates: object) -> dict[str, object]:
    with registry_guard():
        runs = load()
        if run_id not in runs:
            raise RuntimeError("Terraform run record is missing")
        run = runs[run_id]
        run.update(updates)
        runs[run_id] = run
        _save_unlocked(runs)
        return run


def supervise(run_id: str, command_fd: int) -> int:
    child: subprocess.Popen | None = None
    root_lock_fd: int | None = None
    try:
        with os.fdopen(command_fd, "rb") as pipe:
            command = json.loads(pipe.read())
        if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
            raise ValueError("invalid monitor command payload")

        with registry_guard():
            runs = load()
            run = runs.get(run_id)
            if not run or run.get("state") != "STARTING":
                raise RuntimeError("Terraform run is not in its expected starting state")
            root = str(run["root"])

        root_lock_fd = _open_root_lock(root)
        fcntl.flock(root_lock_fd, fcntl.LOCK_EX)
        _write_state(
            run_id,
            state="RUNNING",
            supervisor_pid=os.getpid(),
            supervisor_started_at=datetime.now(UTC).isoformat(),
        )
        run = load()[run_id]
        log_path = Path(str(run["log"]))
        with log_path.open("ab") as output:
            child = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                close_fds=True,
                pass_fds=(root_lock_fd,),
                start_new_session=True,
            )
            _write_state(
                run_id,
                terraform_pid=child.pid,
                state="RUNNING",
                terraform_started_at=datetime.now(UTC).isoformat(),
            )
            exit_code = child.wait()
        final_state = "SUCCEEDED" if exit_code == 0 else "FAILED"
        _write_state(
            run_id,
            state=final_state,
            exit_code=exit_code,
            finished_at=datetime.now(UTC).isoformat(),
        )
        return exit_code
    except (OSError, RuntimeError, ValueError, TypeError, subprocess.SubprocessError) as error:
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
        try:
            _write_state(
                run_id,
                state="FAILED",
                exit_code=child.returncode if child is not None else None,
                finished_at=datetime.now(UTC).isoformat(),
                monitor_error=type(error).__name__,
            )
        except (OSError, RuntimeError, json.JSONDecodeError):
            pass
        return child.returncode if child is not None and child.returncode is not None else 1
    finally:
        if root_lock_fd is not None:
            fcntl.flock(root_lock_fd, fcntl.LOCK_UN)
            os.close(root_lock_fd)


def status(args: argparse.Namespace) -> None:
    with registry_guard():
        runs = load()
        refresh(runs)
        _save_unlocked(runs)
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
    internal = commands.add_parser("_watch", help=argparse.SUPPRESS)
    internal.add_argument("run_id")
    internal.add_argument("command_fd", type=int)
    internal.set_defaults(func=lambda args: supervise(args.run_id, args.command_fd))
    args = parser.parse_args()
    result = args.func(args)
    return result if isinstance(result, int) else 0


if __name__ == "__main__":
    sys.exit(main())
