from __future__ import annotations

import uuid

import pytest
from davdeploy.nova_apply_dispatch import (
    NovaApplyDispatchError,
    NovaExactPlanApplyDispatcher,
)

PROJECT = "davdeploy-nova-saved-plan-apply"
RUN_ID = "12345678-1234-4234-8234-123456789012"
TOKEN = "a" * 64
BUILD_ID = f"{PROJECT}:build-token"
BUILD_ARN = f"arn:aws:codebuild:us-east-1:654654474502:build/{BUILD_ID}"


def build(*, run_id=RUN_ID, project=PROJECT, build_id=BUILD_ID, arn=BUILD_ARN, status="IN_PROGRESS"):
    return {
        "id": build_id,
        "arn": arn,
        "projectName": project,
        "buildStatus": status,
        "environment": {
            "environmentVariables": [
                {"name": "DAVDEPLOY_NOVA_APPLY_RUN_ID", "value": run_id, "type": "PLAINTEXT"}
            ]
        },
    }


class FakeCodeBuild:
    def __init__(self, response=None, builds=None, pages=None):
        self.response = {"build": build()} if response is None else response
        self.builds = builds if builds is not None else [build()]
        self.pages = pages or [{"ids": [BUILD_ID]}]
        self.calls = []

    def start_build(self, **kwargs):
        self.calls.append(("start_build", kwargs))
        return self.response

    def batch_get_builds(self, **kwargs):
        self.calls.append(("batch_get_builds", kwargs))
        return {"builds": [item for item in self.builds if item["id"] in kwargs["ids"]]}

    def list_builds_for_project(self, **kwargs):
        self.calls.append(("list_builds_for_project", kwargs))
        return self.pages.pop(0) if self.pages else {"ids": []}


def test_start_build_uses_only_fixed_project_and_durable_run_override():
    codebuild = FakeCodeBuild()
    dispatcher = NovaExactPlanApplyDispatcher(project_name=PROJECT, codebuild_client=codebuild)

    result = dispatcher.start_build(RUN_ID, TOKEN)

    assert result.build_id == BUILD_ID
    assert result.run_id == RUN_ID
    assert result.build_arn == BUILD_ARN
    name, request = codebuild.calls[0]
    assert name == "start_build"
    assert request == {
        "projectName": PROJECT,
        "idempotencyToken": TOKEN,
        "environmentVariablesOverride": [
            {
                "name": "DAVDEPLOY_NOVA_APPLY_RUN_ID",
                "value": RUN_ID,
                "type": "PLAINTEXT",
            }
        ],
    }


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"build": build(run_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")},
        {"build": build(run_id=None)},
        {"build": build(project="wrong-project")},
        {"build": build(arn="arn:aws:codebuild:us-east-1:654654474502:build/wrong:token")},
    ],
)
def test_start_build_rejects_missing_or_mismatched_build_identity(response):
    dispatcher = NovaExactPlanApplyDispatcher(
        project_name=PROJECT, codebuild_client=FakeCodeBuild(response=response)
    )

    with pytest.raises((ValueError, NovaApplyDispatchError)):
        dispatcher.start_build(RUN_ID, TOKEN)


def test_start_build_marks_transport_error_as_uncertain():
    class LostResponse(FakeCodeBuild):
        def start_build(self, **kwargs):
            self.calls.append(("start_build", kwargs))
            raise OSError("response lost")

    dispatcher = NovaExactPlanApplyDispatcher(project_name=PROJECT, codebuild_client=LostResponse())

    with pytest.raises(NovaApplyDispatchError) as error:
        dispatcher.start_build(RUN_ID, TOKEN)

    assert error.value.outcome_uncertain is True
    assert error.value.phase == "build_start"


def test_reconcile_build_requires_exact_project_and_run_identity():
    codebuild = FakeCodeBuild(builds=[build()])
    dispatcher = NovaExactPlanApplyDispatcher(project_name=PROJECT, codebuild_client=codebuild)

    result = dispatcher.describe_build(BUILD_ID)

    assert result.run_id == RUN_ID
    assert result.status == "IN_PROGRESS"
    assert codebuild.calls == [("batch_get_builds", {"ids": [BUILD_ID]})]


def test_find_build_by_run_id_is_bounded_and_rejects_ambiguous_matches():
    other_build_id = f"{PROJECT}:other"
    codebuild = FakeCodeBuild(
        builds=[
            build(),
            build(
                build_id=other_build_id,
                arn=f"arn:aws:codebuild:us-east-1:654654474502:build/{other_build_id}",
            ),
        ],
        pages=[{"ids": [BUILD_ID, other_build_id]}],
    )
    dispatcher = NovaExactPlanApplyDispatcher(project_name=PROJECT, codebuild_client=codebuild)

    with pytest.raises(NovaApplyDispatchError, match="multiple"):
        dispatcher.find_build_by_run_id(RUN_ID)


def test_dispatcher_stays_disabled_without_explicit_runner_flag(monkeypatch):
    monkeypatch.delenv("DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_PROJECT", raising=False)
    monkeypatch.setenv("DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_RUNNER_READY", "false")

    assert NovaExactPlanApplyDispatcher.from_environment() is None


def test_invalid_run_and_idempotency_values_fail_before_codebuild_call():
    codebuild = FakeCodeBuild()
    dispatcher = NovaExactPlanApplyDispatcher(project_name=PROJECT, codebuild_client=codebuild)

    with pytest.raises(ValueError):
        dispatcher.start_build(str(uuid.uuid4()).upper(), TOKEN)
    with pytest.raises(ValueError):
        dispatcher.start_build(RUN_ID, "not-a-token")
    assert codebuild.calls == []
