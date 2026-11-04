from __future__ import annotations

import hashlib
import json
import uuid

import pytest
from davdeploy.nova_plan_dispatch import NovaPlanDispatchError, NovaPlanOnlyDispatcher

PROJECT = "davdeploy-nova-plan-only"
BUCKET = "davdeploy-tfplans-654654474502"
KMS_KEY = "arn:aws:kms:us-east-1:654654474502:key/12345678-1234-1234-1234-123456789012"
OWNER = "654654474502"
RUN_ID = "12345678-1234-1234-1234-123456789012"


class FakeS3:
    def __init__(self, *, version_id="v-input-1"):
        self.version_id = version_id
        self.calls = []

    def put_object(self, **kwargs):
        self.calls.append(kwargs)
        self.uploaded = kwargs["Body"]
        return {"VersionId": self.version_id}


class FakeCodeBuild:
    def __init__(self, response=None, builds=None):
        self.response = response or {
            "build": {
                "id": f"{PROJECT}:{RUN_ID}",
                "projectName": PROJECT,
                "buildStatus": "IN_PROGRESS",
            }
        }
        self.builds = builds or []
        self.calls = []

    def start_build(self, **kwargs):
        self.calls.append(("start_build", kwargs))
        return self.response

    def batch_get_builds(self, **kwargs):
        self.calls.append(("batch_get_builds", kwargs))
        return {"builds": self.builds}


def dispatcher(s3=None, codebuild=None):
    return NovaPlanOnlyDispatcher(
        project_name=PROJECT,
        bucket=BUCKET,
        kms_key_arn=KMS_KEY,
        expected_bucket_owner=OWNER,
        s3_client=s3 or FakeS3(),
        codebuild_client=codebuild or FakeCodeBuild(),
    )


def test_stage_input_is_encrypted_versioned_and_limited_to_run_key():
    client = FakeS3()
    configured = dispatcher(s3=client)
    document = {"run_id": RUN_ID, "request": {"safe": True}}

    key, digest, version_id = configured.stage_input(RUN_ID, document)

    call = client.calls[0]
    assert key == f"plans/nova-generated/requests/{RUN_ID}/input.json"
    assert digest == hashlib.sha256(client.uploaded).hexdigest()
    assert version_id == "v-input-1"
    assert json.loads(client.uploaded) == document
    assert call["IfNoneMatch"] == "*"
    assert call["ExpectedBucketOwner"] == OWNER
    assert call["ServerSideEncryption"] == "aws:kms"
    assert call["SSEKMSKeyId"] == KMS_KEY
    assert call["BucketKeyEnabled"] is False
    assert call["Metadata"] == {
        "davdeploy-run-id": RUN_ID,
        "davdeploy-input-sha256": digest,
    }


def test_stage_input_fails_closed_without_bucket_versioning():
    configured = dispatcher(s3=FakeS3(version_id="null"))

    with pytest.raises(NovaPlanDispatchError, match="versioning is unavailable"):
        configured.stage_input(RUN_ID, {"run_id": RUN_ID})


def test_start_build_sets_only_server_owned_run_id_override():
    codebuild = FakeCodeBuild()
    configured = dispatcher(codebuild=codebuild)

    result = configured.start_build(RUN_ID)

    assert result.build_id == f"{PROJECT}:{RUN_ID}"
    assert result.project_name == PROJECT
    call = codebuild.calls[0][1]
    assert call == {
        "projectName": PROJECT,
        "environmentVariablesOverride": [
            {
                "name": "DAVDEPLOY_NOVA_PLAN_RUN_ID",
                "value": RUN_ID,
                "type": "PLAINTEXT",
            }
        ],
    }


@pytest.mark.parametrize(
    "build",
    [
        {"id": f"another-project:{RUN_ID}", "projectName": PROJECT, "buildStatus": "IN_PROGRESS"},
        {"id": f"{PROJECT}:{RUN_ID}", "projectName": "another-project", "buildStatus": "IN_PROGRESS"},
        {"id": f"{PROJECT}:{RUN_ID}", "projectName": PROJECT, "buildStatus": "SUCCEEDED"},
    ],
)
def test_start_build_rejects_unexpected_project_or_terminal_state(build):
    configured = dispatcher(codebuild=FakeCodeBuild(response={"build": build}))

    with pytest.raises(NovaPlanDispatchError, match="identity could not be verified"):
        configured.start_build(RUN_ID)


def test_describe_build_requires_exact_project_and_id():
    build_id = f"{PROJECT}:{RUN_ID}"
    codebuild = FakeCodeBuild(
        builds=[{"id": build_id, "projectName": PROJECT, "buildStatus": "SUCCEEDED"}]
    )
    configured = dispatcher(codebuild=codebuild)

    result = configured.describe_build(build_id)

    assert result.status == "SUCCEEDED"
    assert codebuild.calls == [("batch_get_builds", {"ids": [build_id]})]


def test_describe_build_rejects_other_project():
    configured = dispatcher(
        codebuild=FakeCodeBuild(
            builds=[
                {
                    "id": f"{PROJECT}:{RUN_ID}",
                    "projectName": "other-project",
                    "buildStatus": "SUCCEEDED",
                }
            ]
        )
    )

    with pytest.raises(NovaPlanDispatchError, match="different project"):
        configured.describe_build(f"{PROJECT}:{RUN_ID}")


def test_run_id_path_is_canonicalized_to_lowercase_uuid():
    configured = dispatcher()
    run_id = str(uuid.uuid4())

    assert configured.input_key(run_id.upper()) == configured.input_key(run_id)
