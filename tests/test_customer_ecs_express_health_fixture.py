import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

FIXTURE = Path("tests/fixtures/customer-ecs-express-health/server.py")


def start_fixture(*, version: str, fail_health: bool):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    environment = {
        **os.environ,
        "DAVDEPLOY_TEST_VERSION": version,
        "DAVDEPLOY_TEST_SCOPE": "same-account-customer-sandbox",
        "DAVDEPLOY_TEST_FAIL_HEALTH": str(fail_health).lower(),
        "PORT": str(port),
    }
    process = subprocess.Popen(
        [sys.executable, str(FIXTURE)],
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    origin = f"http://127.0.0.1:{port}"
    for _ in range(50):
        if process.poll() is not None:
            raise AssertionError("health fixture exited before accepting requests")
        try:
            with urllib.request.urlopen(f"{origin}/version", timeout=0.2) as response:
                if response.status == 200:
                    return process, origin
        except (OSError, urllib.error.URLError):
            time.sleep(0.02)
    process.terminate()
    process.wait(timeout=2)
    raise AssertionError("health fixture did not become ready")


def stop_fixture(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def test_health_fixture_reports_release_version():
    process, origin = start_fixture(version="v2", fail_health=False)
    try:
        with urllib.request.urlopen(f"{origin}/healthz", timeout=2) as response:
            payload = json.load(response)
        assert payload == {
            "scope": "same-account-customer-sandbox",
            "status": "ok",
            "version": "v2",
        }
    finally:
        stop_fixture(process)


def test_health_fixture_can_inject_a_failed_revision():
    process, origin = start_fixture(version="broken", fail_health=True)
    try:
        try:
            urllib.request.urlopen(f"{origin}/healthz", timeout=2)
        except urllib.error.HTTPError as error:
            assert error.code == 503
            assert json.load(error) == {
                "scope": "same-account-customer-sandbox",
                "status": "unhealthy",
                "version": "broken",
            }
        else:
            raise AssertionError("failed revision unexpectedly passed its health probe")

        with urllib.request.urlopen(f"{origin}/version", timeout=2) as response:
            assert json.load(response)["version"] == "broken"
    finally:
        stop_fixture(process)
