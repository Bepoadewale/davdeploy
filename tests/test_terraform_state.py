import hashlib
import io
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from davdeploy import main
from davdeploy.models import Base, TerraformRemoteState, TerraformStateLock
from davdeploy.terraform_state import (
    TerraformStateError,
    TerraformStateLocked,
    TerraformStateStorage,
    credential_matches,
    issue_terraform_state_credential,
    parse_terraform_lock,
    parse_terraform_state,
    terraform_state_scope_digest,
    trusted_codebuild_role_matches,
    validate_terraform_state_lock_id,
)
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

ORG = "7d1d82be-9e2a-4de1-8dd1-c78c9241a3a0"
PROJECT = "e8ed4511-06cb-4f75-89ee-5022a4a535fd"
ENVIRONMENT = "15b86c6a-7a57-4f8c-a9c0-4cfae295fe20"


def test_state_scope_is_stable_and_requires_environment_identity():
    scope = terraform_state_scope_digest(
        organization_id=ORG,
        project_id=PROJECT,
        environment_id=ENVIRONMENT,
        target_account_id="654654474502",
        region="us-east-1",
    )
    assert len(scope) == 64
    assert scope == terraform_state_scope_digest(
        organization_id=ORG,
        project_id=PROJECT,
        environment_id=ENVIRONMENT,
        target_account_id="654654474502",
        region="us-east-1",
    )
    with pytest.raises(TerraformStateError, match="environment identity"):
        terraform_state_scope_digest(
            organization_id=ORG,
            project_id=PROJECT,
            environment_id=None,
            target_account_id="654654474502",
            region="us-east-1",
        )


def test_state_parser_returns_metadata_and_rejects_malformed_values():
    lineage = "bd90a8a5-8101-44f2-b79e-f14a22b1abe5"
    raw = json.dumps({"version": 4, "lineage": lineage, "serial": 3, "resources": []}).encode()
    metadata = parse_terraform_state(raw)
    assert metadata.lineage == lineage
    assert metadata.serial == 3
    assert metadata.byte_length == len(raw)
    for value in (
        b"not-json",
        json.dumps({"version": 4, "lineage": lineage, "serial": True, "resources": []}).encode(),
        json.dumps({"version": 4, "lineage": "bad", "serial": 0, "resources": []}).encode(),
    ):
        with pytest.raises(TerraformStateError):
            parse_terraform_state(value)


def test_lock_parser_requires_terraform_lock_shape():
    lock = {
        "ID": "lock-1",
        "Operation": "OperationTypePlan",
        "Info": "",
        "Who": "runner",
        "Version": "1.9.0",
        "Created": "2026-11-10T10:00:00Z",
        "Path": "state",
    }
    assert parse_terraform_lock(json.dumps(lock).encode()) == ("lock-1", lock)
    with pytest.raises(TerraformStateError, match="lock ID"):
        parse_terraform_lock(b'{"ID":""}')


def test_state_write_requires_exact_lock_id_from_http_backend():
    validate_terraform_state_lock_id("lock-1", "lock-1")
    for supplied in (None, "", "another-lock", "🔒"):
        with pytest.raises(TerraformStateError, match="lock ID"):
            validate_terraform_state_lock_id(supplied, "lock-1")


def test_state_credential_is_high_entropy_and_expires_or_revokes():
    issued, digest = issue_terraform_state_credential()
    assert issued.password not in digest
    assert credential_matches(
        issued.password,
        digest,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        revoked_at=None,
    )
    assert not credential_matches(
        issued.password,
        digest,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        revoked_at=None,
    )
    assert not credential_matches(
        issued.password,
        digest,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        revoked_at=datetime.now(UTC),
    )


def test_bootstrap_principal_must_be_the_exact_assumed_codebuild_role():
    expected = "arn:aws:iam::654654474502:role/davdeploy-nova-plan-only"
    assert trusted_codebuild_role_matches(
        "arn:aws:sts::654654474502:assumed-role/davdeploy-nova-plan-only/AWSCodeBuild-abc123",
        expected,
    )
    assert not trusted_codebuild_role_matches(
        "arn:aws:sts::654654474502:assumed-role/customer-role/AWSCodeBuild-abc123", expected
    )
    assert not trusted_codebuild_role_matches(
        "arn:aws:sts::111122223333:assumed-role/davdeploy-nova-plan-only/AWSCodeBuild-abc123",
        expected,
    )
    assert not trusted_codebuild_role_matches(expected, expected)


def test_bootstrap_rejects_environment_from_another_tenant_or_project():
    class FakeDb:
        def get(self, _model, _environment_id):
            return type(
                "Environment", (), {"organization_id": ORG, "project_id": "other-project"}
            )()

    with pytest.raises(HTTPException) as error:
        main._require_state_environment(FakeDb(), ENVIRONMENT, ORG, PROJECT)
    assert getattr(error.value, "status_code", None) == 403


def test_bootstrap_binds_the_exact_durable_attempt_and_build_arn():
    run = SimpleNamespace(
        state="BUILD_STARTED",
        codebuild_project="fixed-plan",
        codebuild_build_id="fixed-plan:build-1",
        runner_run_id="attempt-2",
        result_metadata={
            "codebuild_build_arn": "arn:aws:codebuild:us-east-1:654654474502:build/fixed-plan:build-1"
        },
    )
    build = {
        "id": "fixed-plan:build-1",
        "projectName": "fixed-plan",
        "buildStatus": "IN_PROGRESS",
        "arn": run.result_metadata["codebuild_build_arn"],
        "environment": {
            "environmentVariables": [{"name": "DAVDEPLOY_NOVA_PLAN_RUN_ID", "value": "attempt-2"}]
        },
    }
    assert main._build_matches_generated_plan_run(build, run, "fixed-plan")
    build["environment"]["environmentVariables"][0]["value"] = "control-plane-run-id"
    assert not main._build_matches_generated_plan_run(build, run, "fixed-plan")
    build["environment"]["environmentVariables"][0]["value"] = "attempt-2"
    build["arn"] = "arn:aws:codebuild:us-east-1:654654474502:build/another:run"
    assert not main._build_matches_generated_plan_run(build, run, "fixed-plan")


def test_state_credential_bootstrap_stays_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DAVDEPLOY_TERRAFORM_STATE_ENABLED", raising=False)
    response = TestClient(main.app).post(
        "/api/v1/terraform-state/credentials",
        json={
            "run_id": "7d1d82be-9e2a-4de1-8dd1-c78c9241a3a0",
            "codebuild_build_id": "fixed-plan:build-id",
        },
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Terraform remote state is not enabled"}


def test_state_credential_bootstrap_rejects_non_runner_role_before_aws_call(monkeypatch):
    monkeypatch.setenv("DAVDEPLOY_TERRAFORM_STATE_ENABLED", "true")
    monkeypatch.setenv(
        "DAVDEPLOY_NOVA_PLAN_ONLY_ROLE_ARN", "arn:aws:iam::654654474502:role/fixed-plan"
    )
    monkeypatch.setattr(
        main.boto3,
        "client",
        lambda *_args, **_kwargs: pytest.fail("untrusted caller must not trigger AWS lookups"),
    )
    response = TestClient(main.app).post(
        "/api/v1/terraform-state/credentials",
        headers={
            "x-davdeploy-bootstrap-principal": "arn:aws:sts::654654474502:assumed-role/other-role/build"
        },
        json={
            "run_id": "7d1d82be-9e2a-4de1-8dd1-c78c9241a3a0",
            "codebuild_build_id": "fixed-plan:build-id",
        },
    )
    assert response.status_code == 403


class _FakeS3:
    def __init__(self):
        self.objects = {}
        self.put_count = 0
        self.lose_first_response = False

    def head_object(self, *, Key, **_kwargs):
        if Key not in self.objects:
            from botocore.exceptions import ClientError

            raise ClientError({"Error": {"Code": "404", "Message": "missing"}}, "HeadObject")
        return self.objects[Key]

    def put_object(self, *, Key, Body, Metadata, **_kwargs):
        self.put_count += 1
        self.objects[Key] = {
            "VersionId": f"version-{self.put_count}",
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": "arn:aws:kms:us-east-1:654654474502:key/state-key",
            "Metadata": Metadata,
            "Body": Body,
        }
        if self.lose_first_response:
            self.lose_first_response = False
            from botocore.exceptions import ClientError

            raise ClientError({"Error": {"Code": "InternalError", "Message": "lost"}}, "PutObject")
        return {"VersionId": self.objects[Key]["VersionId"]}

    def get_object(self, *, Key, VersionId, **_kwargs):
        value = self.objects[Key]
        assert value["VersionId"] == VersionId
        return {**value, "Body": io.BytesIO(value["Body"])}


def _state_storage(s3: _FakeS3):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    state = TerraformRemoteState(
        scope_sha256=hashlib.sha256(str(uuid4()).encode()).hexdigest(),
        organization_id=ORG,
        project_id=PROJECT,
        environment_id=ENVIRONMENT,
        target_account_id="654654474502",
        region="us-east-1",
    )
    db.add(state)
    db.commit()
    storage = TerraformStateStorage(
        db,
        s3_client=s3,
        bucket="davdeploy-test-state",
        kms_key_arn="arn:aws:kms:us-east-1:654654474502:key/state-key",
        expected_bucket_owner="654654474502",
    )
    return engine, db, state, storage


def _state_bytes(*, serial: int, lineage: str | None = None) -> bytes:
    return json.dumps(
        {
            "version": 4,
            "lineage": lineage or "bd90a8a5-8101-44f2-b79e-f14a22b1abe5",
            "serial": serial,
            "resources": [],
        }
    ).encode()


def _lock_bytes(lock_id: str = "lock-1") -> bytes:
    return json.dumps(
        {
            "ID": lock_id,
            "Operation": "OperationTypePlan",
            "Info": "",
            "Who": "runner",
            "Version": "1.9.0",
            "Created": "2026-11-10T10:00:00Z",
            "Path": "state",
        }
    ).encode()


def test_state_storage_commits_exact_encrypted_object_version_and_lock_owner():
    s3 = _FakeS3()
    engine, db, state, storage = _state_storage(s3)
    now = datetime.now(UTC)
    document = storage.lock(
        state_id=state.id,
        run_id="run-1",
        build_id="project:build-1",
        raw=_lock_bytes(),
        expires_at=now + timedelta(minutes=5),
    )
    assert document["ID"] == "lock-1"
    with pytest.raises(TerraformStateLocked):
        storage.lock(
            state_id=state.id,
            run_id="run-2",
            build_id="project:build-2",
            raw=_lock_bytes("lock-2"),
            expires_at=now + timedelta(minutes=5),
        )

    metadata = storage.write(
        state_id=state.id,
        run_id="run-1",
        build_id="project:build-1",
        lock_id="lock-1",
        raw=_state_bytes(serial=0),
    )
    assert metadata.serial == 0
    assert storage.read(state.id) == _state_bytes(serial=0)
    with pytest.raises(TerraformStateError, match="serial"):
        storage.write(
            state_id=state.id,
            run_id="run-1",
            build_id="project:build-1",
            lock_id="lock-1",
            raw=_state_bytes(serial=2),
        )
    storage.unlock(
        state_id=state.id,
        run_id="run-1",
        build_id="project:build-1",
        raw=_lock_bytes(),
    )
    db.close()
    engine.dispose()


def test_state_storage_reconciles_lost_upload_response_from_exact_object_metadata():
    s3 = _FakeS3()
    s3.lose_first_response = True
    engine, db, state, storage = _state_storage(s3)
    storage.lock(
        state_id=state.id,
        run_id="run-1",
        build_id="project:build-1",
        raw=_lock_bytes(),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    state_bytes = _state_bytes(serial=0)
    with pytest.raises(TerraformStateError, match="uncertain"):
        storage.write(
            state_id=state.id,
            run_id="run-1",
            build_id="project:build-1",
            lock_id="lock-1",
            raw=state_bytes,
        )
    result = storage.write(
        state_id=state.id,
        run_id="run-1",
        build_id="project:build-1",
        lock_id="lock-1",
        raw=state_bytes,
    )
    assert result.serial == 0
    assert s3.put_count == 1
    assert storage.read(state.id) == state_bytes
    db.close()
    engine.dispose()


def test_expired_lock_requires_exact_terminal_build_before_reclaim():
    engine, db, state, storage = _state_storage(_FakeS3())
    storage.lock(
        state_id=state.id,
        run_id="run-1",
        build_id="project:build-1",
        raw=_lock_bytes(),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    db.get(TerraformStateLock, state.id).expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    with pytest.raises(TerraformStateError, match="terminal build evidence"):
        storage.reclaim_expired_lock(
            state_id=state.id,
            expected_lock_id="lock-1",
            expected_run_id="run-1",
            expected_build_id="project:build-1",
            observed_build_status="IN_PROGRESS",
        )
    assert storage.reclaim_expired_lock(
        state_id=state.id,
        expected_lock_id="lock-1",
        expected_run_id="run-1",
        expected_build_id="project:build-1",
        observed_build_status="FAILED",
    )
    document = storage.lock(
        state_id=state.id,
        run_id="run-2",
        build_id="project:build-2",
        raw=_lock_bytes("lock-2"),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    assert document["ID"] == "lock-2"
    db.close()
    engine.dispose()
