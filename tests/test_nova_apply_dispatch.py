from __future__ import annotations

import base64
import hashlib
import json
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
    def __init__(self, response=None, builds=None, pages=None, batch_responses=None):
        self.response = {"build": build()} if response is None else response
        self.builds = builds if builds is not None else [build()]
        self.pages = pages or [{"ids": [BUILD_ID]}]
        self.batch_responses = batch_responses
        self.calls = []

    def start_build(self, **kwargs):
        self.calls.append(("start_build", kwargs))
        return self.response

    def batch_get_builds(self, **kwargs):
        self.calls.append(("batch_get_builds", kwargs))
        if self.batch_responses is not None:
            return self.batch_responses.pop(0)
        return {
            "builds": [
                item
                for item in self.builds
                if isinstance(item, dict) and item.get("id") in kwargs["ids"]
            ]
        }

    def list_builds_for_project(self, **kwargs):
        self.calls.append(("list_builds_for_project", kwargs))
        return self.pages.pop(0) if self.pages else {"ids": []}


class FakeBody:
    def __init__(self, raw):
        self.raw = raw

    def read(self, size):
        return self.raw[:size]

    def close(self):
        return None


class FakeS3:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get_object(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


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


def test_find_build_by_run_id_returns_none_only_after_complete_valid_search():
    other_run = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    other_build = build(run_id=other_run, build_id=f"{PROJECT}:other")
    other_build["arn"] = f"arn:aws:codebuild:us-east-1:654654474502:build/{other_build['id']}"
    codebuild = FakeCodeBuild(builds=[other_build], pages=[{"ids": [other_build["id"]]}])
    dispatcher = NovaExactPlanApplyDispatcher(project_name=PROJECT, codebuild_client=codebuild)

    assert dispatcher.find_build_by_run_id(RUN_ID) is None


@pytest.mark.parametrize(
    "page",
    [
        None,
        {},
        {"ids": ["another-project:build"]},
        {"ids": [None]},
        {"ids": [BUILD_ID, BUILD_ID]},
        {"ids": [], "nextToken": "page-1"},
    ],
)
def test_find_build_by_run_id_fails_closed_on_malformed_lookup_pages(page):
    pages = (
        [page, {"ids": [], "nextToken": "page-1"}]
        if page == {"ids": [], "nextToken": "page-1"}
        else [page]
    )
    dispatcher = NovaExactPlanApplyDispatcher(
        project_name=PROJECT,
        codebuild_client=FakeCodeBuild(pages=pages),
    )

    with pytest.raises(NovaApplyDispatchError) as error:
        dispatcher.find_build_by_run_id(RUN_ID)

    assert error.value.outcome_uncertain is True
    assert error.value.phase == "build_start"


@pytest.mark.parametrize(
    "batch_response",
    [
        None,
        [],
        {},
        {"builds": []},
        {"builds": [build()], "buildsNotFound": [BUILD_ID]},
        {"builds": [build(build_id=f"{PROJECT}:unexpected")]},
        {"builds": [build(arn="arn:aws:codebuild:us-east-1:654654474502:build/wrong:token")]},
    ],
)
def test_find_build_by_run_id_fails_closed_on_incomplete_or_malformed_build_details(batch_response):
    dispatcher = NovaExactPlanApplyDispatcher(
        project_name=PROJECT,
        codebuild_client=FakeCodeBuild(
            pages=[{"ids": [BUILD_ID]}],
            batch_responses=[batch_response],
        ),
    )

    with pytest.raises(NovaApplyDispatchError) as error:
        dispatcher.find_build_by_run_id(RUN_ID)

    assert error.value.outcome_uncertain is True
    assert error.value.phase == "build_start"


def test_find_build_by_run_id_rejects_duplicate_run_identity_fields():
    malformed = build()
    malformed["environment"]["environmentVariables"].append(
        {"name": "DAVDEPLOY_NOVA_APPLY_RUN_ID", "value": RUN_ID, "type": "PLAINTEXT"}
    )
    dispatcher = NovaExactPlanApplyDispatcher(
        project_name=PROJECT,
        codebuild_client=FakeCodeBuild(builds=[malformed]),
    )

    with pytest.raises(NovaApplyDispatchError) as error:
        dispatcher.find_build_by_run_id(RUN_ID)

    assert error.value.outcome_uncertain is True
    assert error.value.phase == "build_start"


def test_dispatcher_stays_disabled_without_explicit_runner_flag(monkeypatch):
    monkeypatch.delenv("DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_PROJECT", raising=False)
    monkeypatch.setenv("DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_RUNNER_READY", "false")

    assert NovaExactPlanApplyDispatcher.from_environment() is None


def test_enabled_dispatcher_loads_the_encrypted_result_bucket(monkeypatch):
    clients = {"s3": object(), "codebuild": object()}
    monkeypatch.setenv("DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_RUNNER_READY", "true")
    monkeypatch.setenv("DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_PROJECT", PROJECT)
    monkeypatch.setenv("DAVDEPLOY_NOVA_PLAN_ARTIFACT_BUCKET", "davdeploy-plans-654654474502")
    monkeypatch.setenv("DAVDEPLOY_NOVA_APPLY_BUCKET_OWNER", "654654474502")
    monkeypatch.setenv(
        "DAVDEPLOY_NOVA_APPLY_KMS_KEY_ARN",
        "arn:aws:kms:us-east-1:654654474502:key/abc",
    )
    monkeypatch.setattr(
        "davdeploy.nova_apply_dispatch.boto3.client",
        lambda name, **_kwargs: clients[name],
    )

    dispatcher = NovaExactPlanApplyDispatcher.from_environment()

    assert dispatcher is not None
    assert dispatcher.s3 is clients["s3"]
    assert dispatcher.codebuild is clients["codebuild"]


def test_invalid_run_and_idempotency_values_fail_before_codebuild_call():
    codebuild = FakeCodeBuild()
    dispatcher = NovaExactPlanApplyDispatcher(project_name=PROJECT, codebuild_client=codebuild)

    with pytest.raises(ValueError):
        dispatcher.start_build(str(uuid.uuid4()).upper(), TOKEN)
    with pytest.raises(ValueError):
        dispatcher.start_build(RUN_ID, "not-a-token")
    assert codebuild.calls == []


def test_read_result_accepts_only_exact_versioned_approved_run_result():
    plan_sha256 = "a" * 64
    workspace_sha256 = "b" * 64
    manifest_sha256 = "c" * 64
    state_id = "tenant-state-1"
    state_scope_sha256 = "d" * 64
    request_document = {
        "source_plan_run_id": "source-run-1",
        "manifest_sha256": manifest_sha256,
        "saved_plan": {"sha256": plan_sha256},
        "execution_workspace": {"sha256": workspace_sha256},
    }
    result = {
        "contract": "davdeploy.nova-apply-result.v1",
        "run_id": RUN_ID,
        "codebuild_project": PROJECT,
        "codebuild_build_id": BUILD_ID,
        "codebuild_build_arn": BUILD_ARN,
        "source_plan_run_id": "source-run-1",
        "manifest_sha256": manifest_sha256,
        "saved_plan_sha256": plan_sha256,
        "execution_workspace_sha256": workspace_sha256,
        "state_id": state_id,
        "state_scope_sha256": state_scope_sha256,
        "account_id": "123456789012",
        "region": "us-east-1",
        "execution_status": "APPLIED_UNVERIFIED",
        "started_at": "2026-11-17T10:00:00+00:00",
        "finished_at": "2026-11-17T10:01:00+00:00",
        "terraform_version": "1.14.7",
        "aws_provider_version": "6.0.0",
    }
    raw = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    raw_sha256 = hashlib.sha256(raw).digest()
    digest = raw_sha256.hex()
    s3 = FakeS3(
        {
            "Body": FakeBody(raw),
            "VersionId": "result-version-1",
            "ContentLength": len(raw),
            "ChecksumSHA256": base64.b64encode(raw_sha256).decode(),
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": "arn:aws:kms:us-east-1:654654474502:key/abc",
            "BucketKeyEnabled": True,
            "Metadata": {
                "davdeploy-run-id": RUN_ID,
                "davdeploy-build-id": BUILD_ID,
                "davdeploy-result-sha256": digest,
            },
        }
    )
    dispatcher = NovaExactPlanApplyDispatcher(
        project_name=PROJECT,
        codebuild_client=FakeCodeBuild(),
        s3_client=s3,
        artifact_bucket="davdeploy-plans-654654474502",
        expected_bucket_owner="654654474502",
        kms_key_arn="arn:aws:kms:us-east-1:654654474502:key/abc",
    )

    verified, version_id, result_sha256 = dispatcher.read_result(
        RUN_ID,
        request_document,
        BUILD_ID,
        BUILD_ARN,
        expected_state_id=state_id,
        expected_state_scope_sha256=state_scope_sha256,
        expected_account_id="123456789012",
        expected_region="us-east-1",
    )

    assert verified == result
    assert version_id == "result-version-1"
    assert result_sha256 == digest
    assert s3.calls == [
        {
            "Bucket": "davdeploy-plans-654654474502",
            "Key": f"plans/nova-generated/apply-builds/{BUILD_ARN}/result.json",
            "ExpectedBucketOwner": "654654474502",
            "ChecksumMode": "ENABLED",
        }
    ]


def test_read_result_rejects_a_result_from_a_different_manifest():
    altered = {
        "contract": "davdeploy.nova-apply-result.v1",
        "run_id": RUN_ID,
        "codebuild_project": PROJECT,
        "codebuild_build_id": BUILD_ID,
        "codebuild_build_arn": BUILD_ARN,
        "source_plan_run_id": "source-run-1",
        "manifest_sha256": "e" * 64,
    }
    raw = json.dumps(altered, sort_keys=True, separators=(",", ":")).encode()
    digest_bytes = hashlib.sha256(raw).digest()
    digest = digest_bytes.hex()
    dispatcher = NovaExactPlanApplyDispatcher(
        project_name=PROJECT,
        codebuild_client=FakeCodeBuild(),
        s3_client=FakeS3(
            {
                "Body": FakeBody(raw),
                "VersionId": "result-version-1",
                "ContentLength": len(raw),
                "ChecksumSHA256": base64.b64encode(digest_bytes).decode(),
                "ServerSideEncryption": "aws:kms",
                "SSEKMSKeyId": "arn:aws:kms:us-east-1:654654474502:key/abc",
                "BucketKeyEnabled": True,
                "Metadata": {
                    "davdeploy-run-id": RUN_ID,
                    "davdeploy-build-id": BUILD_ID,
                    "davdeploy-result-sha256": digest,
                },
            }
        ),
        artifact_bucket="davdeploy-plans-654654474502",
        expected_bucket_owner="654654474502",
        kms_key_arn="arn:aws:kms:us-east-1:654654474502:key/abc",
    )

    with pytest.raises(NovaApplyDispatchError, match="approved run and saved plan"):
        dispatcher.read_result(
            RUN_ID,
            {
                "source_plan_run_id": "source-run-1",
                "manifest_sha256": "c" * 64,
                "saved_plan": {"sha256": "a" * 64},
                "execution_workspace": {"sha256": "b" * 64},
            },
            BUILD_ID,
            BUILD_ARN,
            expected_state_id="tenant-state-1",
            expected_state_scope_sha256="d" * 64,
            expected_account_id="123456789012",
            expected_region="us-east-1",
        )
