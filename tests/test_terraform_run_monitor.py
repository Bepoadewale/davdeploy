import os
from pathlib import Path

from scripts import terraform_run_monitor as monitor


def test_monitor_marks_missing_pid_finished_and_persists_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("DAVDEPLOY_TERRAFORM_RUN_HOME", str(tmp_path))
    runs = {"run": {"pid": 999999, "state": "RUNNING", "root": "/tmp/root"}}
    monitor.save(runs)
    loaded = monitor.load()
    monitor.refresh(loaded)
    assert loaded["run"]["state"] == "FINISHED_UNKNOWN_EXIT"
    assert monitor.registry_path() == Path(tmp_path) / "runs.json"
    assert "DAVDEPLOY_TERRAFORM_RUN_HOME" in os.environ
