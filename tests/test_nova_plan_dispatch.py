from __future__ import annotations

import hashlib
import io
import json
import uuid

import pytest
from botocore.exceptions import ClientError, ReadTimeoutError
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
        self.metadata = kwargs["Metadata"]
        return {"VersionId": self.version_id, "BucketKeyEnabled": True}

    def head_object(self, **kwargs):
        del kwargs
        if not hasattr(self, "uploaded"):
            raise ClientError(
                {"Error": {"Code": "NoSuchKey"}, "ResponseMetadata": {"HTTPStatusCode": 404}},
                "HeadObject",
            )
        return {
            "Metadata": self.metadata,
            "VersionId": self.version_id,
            "BucketKeyEnabled": True,
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": KMS_KEY,
        }


class FakeCodeBuild:
    def __init__(self, response=None, builds=None):
        self.response = response or {
            "build": {
                "id": f"{PROJECT}:{RUN_ID}",
                "arn": f"arn:aws:codebuild:us-east-1:{OWNER}:build/{PROJECT}:{RUN_ID}",
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
    assert call["BucketKeyEnabled"] is True
    assert call["Metadata"] == {
        "davdeploy-run-id": RUN_ID,
        "davdeploy-input-sha256": digest,
    }


def test_build_scoped_input_and_result_paths_are_distinct_per_build_arn():
    configured = dispatcher()
    build_a = f"arn:aws:codebuild:us-east-1:{OWNER}:build/{PROJECT}:run-a"
    build_b = f"arn:aws:codebuild:us-east-1:{OWNER}:build/{PROJECT}:run-b"

    input_a = configured.build_input_key(build_a)
    input_b = configured.build_input_key(build_b)
    result_a = configured.build_result_key(build_a)
    result_b = configured.build_result_key(build_b)

    assert input_a == f"plans/nova-generated/builds/{build_a}/input.json"
    assert input_b == f"plans/nova-generated/builds/{build_b}/input.json"
    assert result_a == f"plans/nova-generated/builds/{build_a}/result.json"
    assert result_b == f"plans/nova-generated/builds/{build_b}/result.json"
    assert input_a != input_b
    assert result_a != result_b


def result_object_s3(result, *, version_id="result-version-1", stored_digest=None):
    body = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    digest = stored_digest or hashlib.sha256(body).hexdigest()

    class ResultS3:
        def get_object(self, **kwargs):
            assert kwargs == {
                "Bucket": BUCKET,
                "Key": configured.build_result_key(build_arn),
                "ExpectedBucketOwner": OWNER,
            }
            return {
                "Body": io.BytesIO(body),
                "VersionId": version_id,
                "ContentLength": len(body),
                "Metadata": {
                    "davdeploy-run-id": RUN_ID,
                    "davdeploy-build-id": build_id,
                    "davdeploy-result-sha256": digest,
                },
                "ServerSideEncryption": "aws:kms",
                "SSEKMSKeyId": KMS_KEY,
                "BucketKeyEnabled": True,
            }

    build_id = f"{PROJECT}:{RUN_ID}"
    build_arn = f"arn:aws:codebuild:us-east-1:{OWNER}:build/{build_id}"
    configured = dispatcher(s3=ResultS3())
    return configured, build_id, build_arn, digest


def test_read_result_binds_exact_run_build_build_arn_and_object_version():
    build_id = f"{PROJECT}:{RUN_ID}"
    build_arn = f"arn:aws:codebuild:us-east-1:{OWNER}:build/{build_id}"
    result = {
        "contract": "davdeploy.nova-plan-result.v1",
        "run_id": RUN_ID,
        "codebuild_project": PROJECT,
        "codebuild_build_id": build_id,
        "codebuild_build_arn": build_arn,
    }
    configured, build_id, build_arn, digest = result_object_s3(result)

    document, version_id, result_sha256 = configured.read_result(
        RUN_ID,
        configured.build_result_key(build_arn),
        build_id,
        build_arn,
    )

    assert document == result
    assert version_id == "result-version-1"
    assert result_sha256 == digest


@pytest.mark.parametrize("tamper", ["run_id", "build_arn", "metadata_digest", "version"])
def test_read_result_rejects_tampered_identity_digest_or_missing_version(tamper):
    build_id = f"{PROJECT}:{RUN_ID}"
    build_arn = f"arn:aws:codebuild:us-east-1:{OWNER}:build/{build_id}"
    result = {
        "contract": "davdeploy.nova-plan-result.v1",
        "run_id": RUN_ID,
        "codebuild_project": PROJECT,
        "codebuild_build_id": build_id,
        "codebuild_build_arn": build_arn,
    }
    version_id = "result-version-1"
    stored_digest = None
    if tamper == "run_id":
        result["run_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    elif tamper == "build_arn":
        result["codebuild_build_arn"] = build_arn.replace(RUN_ID, "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    elif tamper == "version":
        version_id = "null"
    elif tamper == "metadata_digest":
        stored_digest = "f" * 64
    configured, build_id, build_arn, _digest = result_object_s3(
        result, version_id=version_id, stored_digest=stored_digest
    )

    with pytest.raises(NovaPlanDispatchError, match="did not match|metadata did not match"):
        configured.read_result(
            RUN_ID,
            configured.build_result_key(build_arn),
            build_id,
            build_arn,
        )


def test_stage_input_fails_closed_without_bucket_versioning():
    configured = dispatcher(s3=FakeS3(version_id="null"))

    with pytest.raises(NovaPlanDispatchError, match="no immutable version") as error:
        configured.stage_input(RUN_ID, {"run_id": RUN_ID})
    assert error.value.outcome_uncertain
    assert error.value.phase == "input_stage"


def test_stage_input_reconciles_put_success_with_lost_response_without_duplicate_put():
    class LostResponseS3(FakeS3):
        def put_object(self, **kwargs):
            super().put_object(**kwargs)
            raise OSError("fixture storage response was lost")

    client = LostResponseS3()
    configured = dispatcher(s3=client)
    key, digest, version = configured.stage_input(RUN_ID, {"run_id": RUN_ID})

    assert key == configured.input_key(RUN_ID)
    assert digest == client.metadata["davdeploy-input-sha256"]
    assert version == "v-input-1"
    assert len(client.calls) == 1


def test_stage_input_retries_once_only_after_head_confirms_absence():
    class AbsentThenSucceedsS3(FakeS3):
        def put_object(self, **kwargs):
            if not self.calls:
                self.calls.append(kwargs)
                raise OSError("fixture first put response was lost")
            return super().put_object(**kwargs)

    client = AbsentThenSucceedsS3()
    configured = dispatcher(s3=client)
    key, _digest, version = configured.stage_input(RUN_ID, {"run_id": RUN_ID})

    assert key == configured.input_key(RUN_ID)
    assert version == "v-input-1"
    assert len(client.calls) == 2
    assert all(call["IfNoneMatch"] == "*" for call in client.calls)


@pytest.mark.parametrize("inspection", ["mismatch", "unavailable", "forbidden"])
def test_stage_input_fails_closed_without_retry_when_head_is_not_trustworthy(inspection):
    class UntrustworthyHeadS3(FakeS3):
        def put_object(self, **kwargs):
            self.calls.append(kwargs)
            raise OSError("fixture storage response was lost")

        def head_object(self, **kwargs):
            del kwargs
            if inspection == "unavailable":
                raise OSError("fixture head request failed")
            if inspection == "forbidden":
                raise ClientError(
                    {"Error": {"Code": "AccessDenied"}, "ResponseMetadata": {"HTTPStatusCode": 403}},
                    "HeadObject",
                )
            return {
                "Metadata": {
                    "davdeploy-run-id": RUN_ID,
                    "davdeploy-input-sha256": "f" * 64,
                },
                "VersionId": "v-foreign",
            }

    client = UntrustworthyHeadS3()
    configured = dispatcher(s3=client)
    with pytest.raises(NovaPlanDispatchError) as error:
        configured.stage_input(RUN_ID, {"run_id": RUN_ID})

    assert error.value.outcome_uncertain
    assert error.value.phase == "input_stage"
    assert len(client.calls) == 1


def test_start_build_sets_only_server_owned_run_id_override():
    codebuild = FakeCodeBuild()
    configured = dispatcher(codebuild=codebuild)

    result = configured.start_build(RUN_ID, RUN_ID)

    assert result.build_id == f"{PROJECT}:{RUN_ID}"
    assert result.project_name == PROJECT
    call = codebuild.calls[0][1]
    assert call == {
        "projectName": PROJECT,
        "idempotencyToken": RUN_ID,
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
        configured.start_build(RUN_ID, RUN_ID)


@pytest.mark.parametrize(
    ("status", "error_code", "uncertain"),
    [
        (400, "InvalidInputException", False),
        (400, "RequestTimeout", True),
        (408, "TimeoutException", True),
        (503, "ServiceUnavailableException", True),
        (None, "UnknownError", True),
    ],
)
def test_start_build_classifies_client_error_acceptance_uncertainty(status, error_code, uncertain):
    class FailingCodeBuild:
        def start_build(self, **_kwargs):
            response = {"Error": {"Code": error_code}}
            if status is not None:
                response["ResponseMetadata"] = {"HTTPStatusCode": status}
            raise ClientError(response, "StartBuild")

    configured = dispatcher(codebuild=FailingCodeBuild())

    with pytest.raises(NovaPlanDispatchError) as error:
        configured.start_build(RUN_ID, RUN_ID)

    assert error.value.outcome_uncertain is uncertain
    if uncertain:
        assert error.value.phase == "build_start"


def test_start_build_transport_timeout_is_reconciliation_required():
    class TimeoutCodeBuild:
        def start_build(self, **_kwargs):
            raise ReadTimeoutError(endpoint_url="https://codebuild.example.test")

    configured = dispatcher(codebuild=TimeoutCodeBuild())

    with pytest.raises(NovaPlanDispatchError) as error:
        configured.start_build(RUN_ID, RUN_ID)

    assert error.value.outcome_uncertain
    assert error.value.phase == "build_start"


def test_describe_build_requires_exact_project_and_id():
    build_id = f"{PROJECT}:{RUN_ID}"
    codebuild = FakeCodeBuild(
        builds=[
            {
                "id": build_id,
                "arn": f"arn:aws:codebuild:us-east-1:{OWNER}:build/{build_id}",
                "projectName": PROJECT,
                "buildStatus": "SUCCEEDED",
                "environment": {
                    "environmentVariables": [
                        {
                            "name": "DAVDEPLOY_NOVA_PLAN_RUN_ID",
                            "value": RUN_ID,
                            "type": "PLAINTEXT",
                        }
                    ]
                },
            }
        ]
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


class LookupCodeBuild:
    def __init__(self, pages, builds_by_id):
        self.pages = pages
        self.builds_by_id = builds_by_id
        self.list_calls = []
        self.batch_calls = []

    def list_builds_for_project(self, **kwargs):
        self.list_calls.append(kwargs)
        token = kwargs.get("nextToken")
        return self.pages[token]

    def batch_get_builds(self, **kwargs):
        self.batch_calls.append(kwargs)
        return {"builds": [self.builds_by_id[build_id] for build_id in kwargs["ids"]]}


def _lookup_build(build_id, run_id):
    return {
        "id": build_id,
        "arn": f"arn:aws:codebuild:us-east-1:{OWNER}:build/{build_id}",
        "projectName": PROJECT,
        "buildStatus": "IN_PROGRESS",
        "environment": {
            "environmentVariables": [
                {
                    "name": "DAVDEPLOY_NOVA_PLAN_RUN_ID",
                    "value": run_id,
                    "type": "PLAINTEXT",
                }
            ]
        },
    }


def test_find_build_by_run_id_scans_exact_project_pages_and_accepts_one_match():
    match_id = f"{PROJECT}:matched-build"
    other_id = f"{PROJECT}:other-build"
    client = LookupCodeBuild(
        pages={None: {"ids": [other_id], "nextToken": "page-2"}, "page-2": {"ids": [match_id]}},
        builds_by_id={
            other_id: _lookup_build(other_id, str(uuid.uuid4())),
            match_id: _lookup_build(match_id, RUN_ID),
        },
    )
    configured = dispatcher(codebuild=client)

    build = configured.find_build_by_run_id(RUN_ID)

    assert build is not None
    assert build.build_id == match_id
    assert client.list_calls == [
        {"projectName": PROJECT},
        {"projectName": PROJECT, "nextToken": "page-2"},
    ]
    assert client.batch_calls == [{"ids": [other_id, match_id]}]


def test_find_build_by_run_id_rejects_multiple_exact_matches():
    first_id = f"{PROJECT}:first-build"
    second_id = f"{PROJECT}:second-build"
    client = LookupCodeBuild(
        pages={None: {"ids": [first_id, second_id]}},
        builds_by_id={
            first_id: _lookup_build(first_id, RUN_ID),
            second_id: _lookup_build(second_id, RUN_ID),
        },
    )
    configured = dispatcher(codebuild=client)

    with pytest.raises(NovaPlanDispatchError, match="Multiple Nova plan builds") as error:
        configured.find_build_by_run_id(RUN_ID)

    assert error.value.outcome_uncertain
    assert error.value.phase == "build_start"


def test_find_build_by_run_id_keeps_zero_or_incomplete_search_blocked():
    client = LookupCodeBuild(
        pages={None: {"ids": [f"{PROJECT}:other-build"]}},
        builds_by_id={f"{PROJECT}:other-build": _lookup_build(f"{PROJECT}:other-build", "other-run")},
    )
    configured = dispatcher(codebuild=client)
    assert configured.find_build_by_run_id(RUN_ID) is None

    client.pages = {None: {"ids": [], "nextToken": "continued"}}
    configured._BUILD_LOOKUP_PAGE_LIMIT = 1
    with pytest.raises(NovaPlanDispatchError, match="pagination limit") as error:
        configured.find_build_by_run_id(RUN_ID)
    assert error.value.outcome_uncertain


def test_find_build_by_run_id_keeps_unavailable_lookup_blocked():
    class UnavailableCodeBuild:
        def list_builds_for_project(self, **_kwargs):
            raise OSError("fixture CodeBuild API unavailable")

    configured = dispatcher(codebuild=UnavailableCodeBuild())
    with pytest.raises(NovaPlanDispatchError, match="build search could not be confirmed") as error:
        configured.find_build_by_run_id(RUN_ID)
    assert error.value.outcome_uncertain


@pytest.mark.parametrize(
    "build",
    [
        {"id": f"{PROJECT}:missing-environment", "projectName": PROJECT},
        {
            "id": f"{PROJECT}:missing-variables",
            "projectName": PROJECT,
            "environment": {},
        },
        {
            "id": f"{PROJECT}:malformed-variable",
            "projectName": PROJECT,
            "environment": {"environmentVariables": [None]},
        },
        {
            "id": f"{PROJECT}:malformed-run-id",
            "projectName": PROJECT,
            "environment": {
                "environmentVariables": [
                    {"name": "DAVDEPLOY_NOVA_PLAN_RUN_ID", "value": RUN_ID}
                ]
            },
        },
    ],
)
def test_find_build_by_run_id_fails_closed_on_malformed_environment(build):
    build_id = build["id"]
    configured = dispatcher(
        codebuild=LookupCodeBuild(
            pages={None: {"ids": [build_id]}}, builds_by_id={build_id: build}
        )
    )

    with pytest.raises(NovaPlanDispatchError) as error:
        configured.find_build_by_run_id(RUN_ID)

    assert error.value.outcome_uncertain
    assert error.value.phase == "build_start"


@pytest.mark.parametrize("response", [None, [], {"builds": None}, {"builds": [None]}])
def test_find_build_by_run_id_fails_closed_on_malformed_batch_response(response):
    class MalformedBatchResponse:
        def list_builds_for_project(self, **_kwargs):
            return {"ids": [f"{PROJECT}:malformed"]}

        def batch_get_builds(self, **_kwargs):
            return response

    configured = dispatcher(codebuild=MalformedBatchResponse())

    with pytest.raises(NovaPlanDispatchError) as error:
        configured.find_build_by_run_id(RUN_ID)

    assert error.value.outcome_uncertain
    assert error.value.phase == "build_start"


@pytest.mark.parametrize("response", [None, [], {"builds": None}, {"builds": [None]}])
def test_describe_build_fails_closed_on_malformed_batch_response(response):
    class MalformedBatchResponse:
        def batch_get_builds(self, **_kwargs):
            return response

    configured = dispatcher(codebuild=MalformedBatchResponse())

    with pytest.raises(NovaPlanDispatchError) as error:
        configured.describe_build(f"{PROJECT}:{RUN_ID}")

    assert error.value.outcome_uncertain


def test_run_id_path_is_canonicalized_to_lowercase_uuid():
    configured = dispatcher()
    run_id = str(uuid.uuid4())

    assert configured.input_key(run_id.upper()) == configured.input_key(run_id)
