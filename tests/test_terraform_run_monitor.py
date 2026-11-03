import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scripts import terraform_run_monitor as monitor


def _fake_terraform(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    command = bin_dir / "terraform"
    command.write_text(
        "#!/bin/sh\n"
        "sleep \"${FAKE_TERRAFORM_SLEEP:-0.05}\"\n"
        "exit \"${FAKE_TERRAFORM_EXIT:-0}\"\n"
    )
    command.chmod(0o755)
    return bin_dir


def _environment(tmp_path: Path, bin_dir: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["DAVDEPLOY_TERRAFORM_RUN_HOME"] = str(tmp_path / "monitor")
    environment["PATH"] = f"{bin_dir}{os.pathsep}{environment['PATH']}"
    return environment


def _start(
    tmp_path: Path,
    bin_dir: Path,
    root: Path,
    run_id: str,
    *,
    exit_code: int = 0,
    sleep: float = 0.05,
    extra_args: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    environment = _environment(tmp_path, bin_dir)
    environment["FAKE_TERRAFORM_EXIT"] = str(exit_code)
    environment["FAKE_TERRAFORM_SLEEP"] = str(sleep)
    return subprocess.run(
        [
            sys.executable,
            str(Path(monitor.__file__).resolve()),
            "start",
            "apply",
            str(root),
            "--run-id",
            run_id,
            *extra_args,
        ],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
        timeout=10,
    )


def _wait_for_terminal(tmp_path: Path, run_id: str) -> dict[str, object]:
    environment = os.environ.copy()
    environment["DAVDEPLOY_TERRAFORM_RUN_HOME"] = str(tmp_path / "monitor")
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        result = subprocess.run(
            [sys.executable, str(Path(monitor.__file__).resolve()), "status", run_id],
            check=True,
            capture_output=True,
            env=environment,
            text=True,
            timeout=5,
        )
        record = json.loads(result.stdout)
        if record["state"] not in monitor.ACTIVE_STATES:
            return record
        time.sleep(0.02)
    raise AssertionError(f"Terraform monitor did not finish {run_id}")


def test_monitor_records_successful_child_exit(tmp_path):
    bin_dir = _fake_terraform(tmp_path)
    root = tmp_path / "terraform-root"
    root.mkdir()
    started = _start(tmp_path, bin_dir, root, "success-run")

    assert started.returncode == 0
    initial = json.loads(started.stdout)
    assert initial["state"] in {"STARTING", "RUNNING", "SUCCEEDED"}
    result = _wait_for_terminal(tmp_path, "success-run")
    assert result["state"] == "SUCCEEDED"
    assert result["exit_code"] == 0
    assert Path(result["log"]).exists()


def test_monitor_records_nonzero_child_exit(tmp_path):
    bin_dir = _fake_terraform(tmp_path)
    root = tmp_path / "terraform-root"
    root.mkdir()
    started = _start(tmp_path, bin_dir, root, "failure-run", exit_code=23)

    assert started.returncode == 0
    result = _wait_for_terminal(tmp_path, "failure-run")
    assert result["state"] == "FAILED"
    assert result["exit_code"] == 23


def test_monitor_refuses_concurrent_mutation_of_same_root(tmp_path):
    bin_dir = _fake_terraform(tmp_path)
    root = tmp_path / "terraform-root"
    root.mkdir()
    first = _start(tmp_path, bin_dir, root, "first-run", sleep=1)
    second = _start(tmp_path, bin_dir, root, "second-run", sleep=0.01)

    assert first.returncode == 0
    assert second.returncode != 0
    assert "already" in second.stderr
    assert _wait_for_terminal(tmp_path, "first-run")["state"] == "SUCCEEDED"


def test_monitor_allows_different_roots_and_keeps_both_records(tmp_path):
    bin_dir = _fake_terraform(tmp_path)
    first_root = tmp_path / "first-root"
    second_root = tmp_path / "second-root"
    first_root.mkdir()
    second_root.mkdir()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_start, tmp_path, bin_dir, first_root, "independent-a", sleep=0.3),
            pool.submit(_start, tmp_path, bin_dir, second_root, "independent-b", sleep=0.3),
        ]
        results = [future.result(timeout=10) for future in futures]

    assert all(result.returncode == 0 for result in results)
    assert _wait_for_terminal(tmp_path, "independent-a")["state"] == "SUCCEEDED"
    assert _wait_for_terminal(tmp_path, "independent-b")["state"] == "SUCCEEDED"
    registry = json.loads((tmp_path / "monitor" / "runs.json").read_text())
    assert set(registry) == {"independent-a", "independent-b"}


def test_monitor_redacts_variable_values_from_registry(tmp_path):
    bin_dir = _fake_terraform(tmp_path)
    root = tmp_path / "terraform-root"
    root.mkdir()
    result = _start(
        tmp_path,
        bin_dir,
        root,
        "redaction-run",
        sleep=0.3,
        extra_args=("--terraform-arg=-var=password=do-not-store",),
    )

    assert result.returncode == 0
    record = json.loads(result.stdout)
    serialized = json.dumps(monitor.load())
    assert "do-not-store" not in serialized
    assert "-var=[REDACTED]" in record["command"]
    assert _wait_for_terminal(tmp_path, "redaction-run")["state"] == "SUCCEEDED"


def test_monitor_marks_missing_process_unknown_not_success_and_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("DAVDEPLOY_TERRAFORM_RUN_HOME", str(tmp_path))
    runs = {
        "run": {
            "pid": 999999,
            "terraform_pid": 999999,
            "supervisor_pid": 999998,
            "state": "RUNNING",
            "root": "/tmp/root",
        }
    }
    monitor.save(runs)
    loaded = monitor.load()
    monitor.refresh(loaded)
    assert loaded["run"]["state"] == "FINISHED_UNKNOWN_EXIT"
    assert loaded["run"]["exit_code"] is None
    assert monitor.registry_path() == Path(tmp_path) / "runs.json"
    assert "DAVDEPLOY_TERRAFORM_RUN_HOME" in os.environ


def test_monitor_preserves_historical_unknown_outcome(tmp_path, monkeypatch):
    monkeypatch.setenv("DAVDEPLOY_TERRAFORM_RUN_HOME", str(tmp_path))
    historical = {
        "old-run": {
            "state": "FINISHED_UNKNOWN_EXIT",
            "exit_code": None,
            "root": "/tmp/old-root",
            "finished_at": "2026-11-02T12:00:00+00:00",
        }
    }
    monitor.save(historical)

    loaded = monitor.load()
    monitor.refresh(loaded)

    assert loaded["old-run"] == historical["old-run"]


def test_monitor_rejects_duplicate_run_id(tmp_path):
    bin_dir = _fake_terraform(tmp_path)
    root = tmp_path / "terraform-root"
    root.mkdir()
    assert _start(tmp_path, bin_dir, root, "duplicate-id").returncode == 0
    second = _start(tmp_path, bin_dir, root / "other", "duplicate-id")
    assert second.returncode != 0
    assert "run ID already exists" in second.stderr
    assert _wait_for_terminal(tmp_path, "duplicate-id")["state"] == "SUCCEEDED"
