from __future__ import annotations

from typing import Any

from davdeploy import cli


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.calls.append((method, path, payload))
        return {"accepted": True}


def test_cli_inspects_generated_plan_artifact_with_safe_get_endpoint():
    args = cli._parser().parse_args(
        ["get-generated-plan-artifact", "--artifact-id", "artifact-123"]
    )
    client = RecordingClient()

    assert cli.run(args, client) == {"accepted": True}
    assert client.calls == [
        ("GET", "/api/v1/generated-plan-artifacts/artifact-123", None)
    ]


def test_cli_approval_binds_exact_generated_plan_manifest_digest():
    digest = "a" * 64
    args = cli._parser().parse_args(
        [
            "approve-generated-plan",
            "--artifact-id",
            "artifact-123",
            "--manifest-sha256",
            digest,
        ]
    )
    client = RecordingClient()

    assert cli.run(args, client) == {"accepted": True}
    assert client.calls == [
        (
            "POST",
            "/api/v1/generated-plan-artifacts/artifact-123/approve",
            {"manifest_sha256": digest},
        )
    ]
