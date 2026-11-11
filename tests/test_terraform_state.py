import hashlib
import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest
from davdeploy import main
from davdeploy.models import (
    Base,
    Environment,
    GeneratedPlanRun,
    InfrastructurePlan,
    InfrastructurePlanRevision,
    Organization,
    Project,
    TerraformRemoteState,
    TerraformStateCredential,
    TerraformStateLock,
    TerraformStateWrite,
)
from davdeploy.terraform_state import (
    TerraformStateError,
    TerraformStateLocked,
    TerraformStateStorage,
    credential_matches,
    issue_terraform_state_credential,
    parse_terraform_lock,
    parse_terraform_state,
    terraform_state_scope_digest,
    trusted_codebuild_build_matches,
    trusted_codebuild_role_matches,
    validate_terraform_state_lock_id,
)
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

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


def test_codebuild_principal_must_match_the_exact_build_session_uuid():
    expected = "arn:aws:iam::654654474502:role/service-role/davdeploy-nova-plan-only"
    build_id = "davdeploy-nova-plan-only:12345678-1234-4234-8234-123456789abc"
    caller = (
        "arn:aws:sts::654654474502:assumed-role/service-role/davdeploy-nova-plan-only/"
        "AWSCodeBuild-12345678-1234-4234-8234-123456789abc"
    )
    assert trusted_codebuild_build_matches(
        caller, expected, "davdeploy-nova-plan-only", build_id
    )
    assert not trusted_codebuild_build_matches(
        caller,
        expected,
        "davdeploy-nova-plan-only",
        "davdeploy-nova-plan-only:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    )
    assert not trusted_codebuild_build_matches(
        caller.replace("/AWSCodeBuild-", "/manual-session-"),
        expected,
        "davdeploy-nova-plan-only",
        build_id,
    )
    assert not trusted_codebuild_build_matches(
        caller,
        expected,
        "davdeploy-nova-plan-only",
        "another-project:12345678-1234-4234-8234-123456789abc",
    )


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


def test_state_bootstrap_issues_scope_bound_credential_and_rejects_other_state(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    plan_id = "d1dd65f5-4f21-4e26-85b7-74d75fc7db8c"
    revision_id = "fdac3a35-9b91-4b45-84a7-c6067106d485"
    run_id = "7d1d82be-9e2a-4de1-8dd1-c78c9241a3a0"
    attempt_id = "ed350f1b-61b1-4edc-9799-35332aa96283"
    build_id = "fixed-plan:build-1"
    build_arn = "arn:aws:codebuild:us-east-1:654654474502:build/fixed-plan:build-1"
    account_id = "654654474502"
    region = "us-east-1"
    build_role = "arn:aws:iam::654654474502:role/fixed-plan"
    assumed_build_role = (
        "arn:aws:sts::654654474502:assumed-role/fixed-plan/AWSCodeBuild-session"
    )
    other_org = "27af5383-fba8-4b93-a7cb-37a603fc2ee8"
    other_project = "a2c9862d-2203-47c1-a83b-46d6d7ef6ab0"
    other_environment = "c87bc13e-c3bb-4b46-b852-9f2884c1c981"
    other_state = "12345678-1234-4234-8234-123456789012"
    plan_content = {
        "target": {
            "environment_id": ENVIRONMENT,
            "account_id": account_id,
            "region": region,
        }
    }
    request_document = {"target_account_id": account_id, "region": region}
    db.add_all(
        [
            Organization(id=ORG, name="state-test-org"),
            Project(id=PROJECT, organization_id=ORG, name="state-test-project"),
            Environment(
                id=ENVIRONMENT,
                organization_id=ORG,
                project_id=PROJECT,
                name="production",
                environment_type="production",
                state="READY",
                desired_state={},
                observed_state={},
            ),
            InfrastructurePlan(
                id=plan_id,
                organization_id=ORG,
                project_id=PROJECT,
                creator_subject="founder",
                title="State test",
            ),
            InfrastructurePlanRevision(
                id=revision_id,
                infrastructure_plan_id=plan_id,
                organization_id=ORG,
                revision_number=1,
                state="SUBMITTED",
                content=plan_content,
                content_digest="a" * 64,
            ),
            GeneratedPlanRun(
                id=run_id,
                organization_id=ORG,
                project_id=PROJECT,
                revision_id=revision_id,
                requester_subject="founder",
                idempotency_key_sha256="b" * 64,
                request_sha256="c" * 64,
                request_document=request_document,
                runner_run_id=attempt_id,
                revision_sha256="d" * 64,
                state="BUILD_STARTED",
                codebuild_project="fixed-plan",
                codebuild_build_id=build_id,
                input_key="plan-input.json",
                result_key="plan-result.json",
                result_metadata={"codebuild_build_arn": build_arn},
            ),
            TerraformRemoteState(
                id=other_state,
                scope_sha256="e" * 64,
                organization_id=other_org,
                project_id=other_project,
                environment_id=other_environment,
                target_account_id=account_id,
                region=region,
            ),
        ]
    )
    db.commit()

    def override_session():
        yield db

    class FakeCodeBuild:
        def __init__(self):
            self.calls = []

        def batch_get_builds(self, *, ids):
            self.calls.append(ids)
            return {
                "builds": [
                    {
                        "id": build_id,
                        "projectName": "fixed-plan",
                        "buildStatus": "IN_PROGRESS",
                        "arn": build_arn,
                        "environment": {
                            "environmentVariables": [
                                {"name": "DAVDEPLOY_NOVA_PLAN_RUN_ID", "value": attempt_id}
                            ]
                        },
                    }
                ]
            }

    codebuild = FakeCodeBuild()
    monkeypatch.setenv("DAVDEPLOY_TERRAFORM_STATE_ENABLED", "true")
    monkeypatch.setenv("DAVDEPLOY_NOVA_PLAN_ONLY_ROLE_ARN", build_role)
    monkeypatch.setenv("DAVDEPLOY_NOVA_PLAN_PROJECT", "fixed-plan")
    monkeypatch.setenv("DAVDEPLOY_TERRAFORM_STATE_API_URL", "https://api.davdeploy.tech")
    monkeypatch.setattr(main, "ensure_aurora_ready", lambda: None)
    monkeypatch.setattr(main.boto3, "client", lambda name, **_kwargs: codebuild if name == "codebuild" else None)
    monkeypatch.setitem(main.app.dependency_overrides, main.session, override_session)
    headers = {"x-davdeploy-bootstrap-principal": assumed_build_role}

    with TestClient(main.app) as client:
        response = client.post(
            "/api/v1/terraform-state/credentials",
            headers=headers,
            json={"run_id": run_id, "codebuild_build_id": build_id},
        )
        assert response.status_code == 200
        credential_document = response.json()
        assert credential_document["scope_sha256"] == terraform_state_scope_digest(
            organization_id=ORG,
            project_id=PROJECT,
            environment_id=ENVIRONMENT,
            target_account_id=account_id,
            region=region,
        )
        assert credential_document["address"].endswith(
            f"/api/v1/terraform-state/{credential_document['state_id']}"
        )
        credential = db.scalar(
            select(TerraformStateCredential).where(
                TerraformStateCredential.username == credential_document["username"]
            )
        )
        assert credential is not None
        assert credential.run_id == run_id
        assert credential.codebuild_build_id == build_id
        assert credential.password_sha256 != credential_document["password"]

        cross_tenant = client.get(
            f"/api/v1/terraform-state/{other_state}",
            auth=(credential_document["username"], credential_document["password"]),
        )
        assert cross_tenant.status_code == 401

    assert len(codebuild.calls) == 1
    db.close()
    engine.dispose()


class _FakeS3:
    def __init__(self):
        self.objects = {}
        self.put_count = 0
        self.put_conditions = []
        self.lose_first_response = False
        self.missing_head_code = "404"
        self.conditional_precondition_once = False
        self.conditional_conflict_once = False
        self.fail_before_put_once = False

    def head_object(self, *, Key, **_kwargs):
        if Key not in self.objects:
            from botocore.exceptions import ClientError

            status = int(self.missing_head_code) if self.missing_head_code.isdecimal() else 403
            raise ClientError(
                {
                    "Error": {"Code": self.missing_head_code, "Message": "missing"},
                    "ResponseMetadata": {"HTTPStatusCode": status},
                },
                "HeadObject",
            )
        return self.objects[Key]

    def put_object(self, *, Key, Body, Metadata, IfNoneMatch=None, **_kwargs):
        self.put_count += 1
        self.put_conditions.append(IfNoneMatch)
        if self.fail_before_put_once:
            self.fail_before_put_once = False
            from botocore.exceptions import ClientError

            raise ClientError({"Error": {"Code": "InternalError", "Message": "failed"}}, "PutObject")
        self.objects[Key] = {
            "VersionId": f"version-{self.put_count}",
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": "arn:aws:kms:us-east-1:654654474502:key/state-key",
            "Metadata": Metadata,
            "Body": Body,
        }
        if self.conditional_conflict_once:
            self.conditional_conflict_once = False
            from botocore.exceptions import ClientError

            self.objects.pop(Key)
            raise ClientError(
                {
                    "Error": {"Code": "ConditionalRequestConflict", "Message": "conflict"},
                    "ResponseMetadata": {"HTTPStatusCode": 409},
                },
                "PutObject",
            )
        if self.conditional_precondition_once:
            self.conditional_precondition_once = False
            from botocore.exceptions import ClientError

            raise ClientError(
                {
                    "Error": {"Code": "PreconditionFailed", "Message": "exists"},
                    "ResponseMetadata": {"HTTPStatusCode": 412},
                },
                "PutObject",
            )
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


def _reclaim_failed_state_lock(db, storage, state, *, run_id: str, build_id: str, lock_id: str):
    db.get(TerraformStateLock, state.id).expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert storage.reclaim_expired_lock(
        state_id=state.id,
        expected_lock_id=lock_id,
        expected_run_id=run_id,
        expected_build_id=build_id,
        observed_build_status="FAILED",
    )


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


def test_state_storage_first_write_uses_conditional_put_after_403_head_without_list_permission():
    s3 = _FakeS3()
    s3.missing_head_code = "403"
    engine, db, state, storage = _state_storage(s3)
    storage.lock(
        state_id=state.id,
        run_id="run-1",
        build_id="project:build-1",
        raw=_lock_bytes(),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    result = storage.write(
        state_id=state.id,
        run_id="run-1",
        build_id="project:build-1",
        lock_id="lock-1",
        raw=_state_bytes(serial=0),
    )

    assert result.serial == 0
    assert s3.put_count == 1
    assert s3.put_conditions == ["*"]
    assert storage.read(state.id) == _state_bytes(serial=0)
    db.close()
    engine.dispose()


def test_state_storage_reconciles_conditional_put_precondition_from_exact_metadata():
    s3 = _FakeS3()
    s3.conditional_precondition_once = True
    engine, db, state, storage = _state_storage(s3)
    storage.lock(
        state_id=state.id,
        run_id="run-1",
        build_id="project:build-1",
        raw=_lock_bytes(),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    result = storage.write(
        state_id=state.id,
        run_id="run-1",
        build_id="project:build-1",
        lock_id="lock-1",
        raw=_state_bytes(serial=0),
    )

    assert result.serial == 0
    assert s3.put_count == 1
    assert s3.put_conditions == ["*"]
    assert storage.read(state.id) == _state_bytes(serial=0)
    db.close()
    engine.dispose()


def test_state_storage_retries_one_conditional_conflict():
    s3 = _FakeS3()
    s3.conditional_conflict_once = True
    engine, db, state, storage = _state_storage(s3)
    storage.lock(
        state_id=state.id,
        run_id="run-1",
        build_id="project:build-1",
        raw=_lock_bytes(),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    result = storage.write(
        state_id=state.id,
        run_id="run-1",
        build_id="project:build-1",
        lock_id="lock-1",
        raw=_state_bytes(serial=0),
    )

    assert result.serial == 0
    assert s3.put_count == 2
    assert s3.put_conditions == ["*", "*"]
    assert storage.read(state.id) == _state_bytes(serial=0)
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


def test_state_storage_adopts_valid_pending_object_after_build_recovery():
    s3 = _FakeS3()
    s3.lose_first_response = True
    engine, db, state, storage = _state_storage(s3)
    state_bytes = _state_bytes(serial=0)
    storage.lock(
        state_id=state.id,
        run_id="run-1",
        build_id="project:build-1",
        raw=_lock_bytes(),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    with pytest.raises(TerraformStateError, match="uncertain"):
        storage.write(
            state_id=state.id,
            run_id="run-1",
            build_id="project:build-1",
            lock_id="lock-1",
            raw=state_bytes,
        )
    _reclaim_failed_state_lock(
        db,
        storage,
        state,
        run_id="run-1",
        build_id="project:build-1",
        lock_id="lock-1",
    )
    storage.lock(
        state_id=state.id,
        run_id="run-2",
        build_id="project:build-2",
        raw=_lock_bytes("lock-2"),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    result = storage.write(
        state_id=state.id,
        run_id="run-2",
        build_id="project:build-2",
        lock_id="lock-2",
        raw=state_bytes,
    )

    write = db.scalar(select(TerraformStateWrite).where(TerraformStateWrite.state_id == state.id))
    assert result.serial == 0
    assert s3.put_count == 1
    assert write.status == "COMMITTED"
    assert write.run_id == "run-1"
    assert write.object_version_id == "version-1"
    assert storage.read(state.id) == state_bytes
    db.close()
    engine.dispose()


@pytest.mark.parametrize("missing_head_code", ["403", "404"])
def test_state_storage_recovers_absent_pending_object_under_current_lock(missing_head_code):
    s3 = _FakeS3()
    s3.fail_before_put_once = True
    s3.missing_head_code = missing_head_code
    engine, db, state, storage = _state_storage(s3)
    state_bytes = _state_bytes(serial=0)
    storage.lock(
        state_id=state.id,
        run_id="run-1",
        build_id="project:build-1",
        raw=_lock_bytes(),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    with pytest.raises(TerraformStateError, match="uncertain"):
        storage.write(
            state_id=state.id,
            run_id="run-1",
            build_id="project:build-1",
            lock_id="lock-1",
            raw=state_bytes,
        )
    old_write = db.scalar(
        select(TerraformStateWrite).where(TerraformStateWrite.state_id == state.id)
    )
    old_key = old_write.object_key
    _reclaim_failed_state_lock(
        db,
        storage,
        state,
        run_id="run-1",
        build_id="project:build-1",
        lock_id="lock-1",
    )
    storage.lock(
        state_id=state.id,
        run_id="run-2",
        build_id="project:build-2",
        raw=_lock_bytes("lock-2"),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    result = storage.write(
        state_id=state.id,
        run_id="run-2",
        build_id="project:build-2",
        lock_id="lock-2",
        raw=state_bytes,
    )

    assert result.serial == 0
    assert old_write.status == "COMMITTED"
    if missing_head_code == "403":
        assert old_write.object_key == old_key
        assert old_write.run_id == "run-1"
        assert old_write.attempt_history == []
        assert s3.put_count == 2
    else:
        assert old_write.object_key != old_key
        assert old_write.run_id == "run-2"
        assert old_write.attempt_history[0]["object_key"] == old_key
        assert old_write.attempt_history[0]["run_id"] == "run-1"
        assert old_write.attempt_history[0]["outcome"] == "ABANDONED_UNVERIFIED_OBJECT"
    assert storage.read(state.id) == state_bytes
    db.close()
    engine.dispose()


def test_state_storage_abandons_unverifiable_pending_object_and_rotates_key():
    s3 = _FakeS3()
    s3.lose_first_response = True
    engine, db, state, storage = _state_storage(s3)
    state_bytes = _state_bytes(serial=0)
    storage.lock(
        state_id=state.id,
        run_id="run-1",
        build_id="project:build-1",
        raw=_lock_bytes(),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    with pytest.raises(TerraformStateError, match="uncertain"):
        storage.write(
            state_id=state.id,
            run_id="run-1",
            build_id="project:build-1",
            lock_id="lock-1",
            raw=state_bytes,
        )
    write = db.scalar(select(TerraformStateWrite).where(TerraformStateWrite.state_id == state.id))
    old_key = write.object_key
    s3.objects[old_key]["Metadata"]["davdeploy-state-sha256"] = "f" * 64
    _reclaim_failed_state_lock(
        db,
        storage,
        state,
        run_id="run-1",
        build_id="project:build-1",
        lock_id="lock-1",
    )
    storage.lock(
        state_id=state.id,
        run_id="run-2",
        build_id="project:build-2",
        raw=_lock_bytes("lock-2"),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    result = storage.write(
        state_id=state.id,
        run_id="run-2",
        build_id="project:build-2",
        lock_id="lock-2",
        raw=state_bytes,
    )

    assert result.serial == 0
    assert write.status == "COMMITTED"
    assert write.run_id == "run-2"
    assert write.object_key != old_key
    assert write.attempt_history == [
        {
            "run_id": "run-1",
            "build_id_sha256": hashlib.sha256(b"project:build-1").hexdigest(),
            "object_key": old_key,
            "outcome": "ABANDONED_UNVERIFIED_OBJECT",
            "recorded_at": write.attempt_history[0]["recorded_at"],
        }
    ]
    assert storage.read(state.id) == state_bytes
    db.close()
    engine.dispose()


def test_state_storage_commits_prior_pending_version_before_rejecting_changed_same_serial():
    s3 = _FakeS3()
    s3.lose_first_response = True
    engine, db, state, storage = _state_storage(s3)
    prior_bytes = _state_bytes(serial=0)
    changed_document = json.loads(prior_bytes)
    changed_document["resources"] = [{"mode": "managed", "type": "aws_s3_bucket"}]
    changed_bytes = json.dumps(changed_document).encode()
    storage.lock(
        state_id=state.id,
        run_id="run-1",
        build_id="project:build-1",
        raw=_lock_bytes(),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    with pytest.raises(TerraformStateError, match="uncertain"):
        storage.write(
            state_id=state.id,
            run_id="run-1",
            build_id="project:build-1",
            lock_id="lock-1",
            raw=prior_bytes,
        )
    _reclaim_failed_state_lock(
        db,
        storage,
        state,
        run_id="run-1",
        build_id="project:build-1",
        lock_id="lock-1",
    )
    storage.lock(
        state_id=state.id,
        run_id="run-2",
        build_id="project:build-2",
        raw=_lock_bytes("lock-2"),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    with pytest.raises(TerraformStateError, match="prior Terraform state version was recovered"):
        storage.write(
            state_id=state.id,
            run_id="run-2",
            build_id="project:build-2",
            lock_id="lock-2",
            raw=changed_bytes,
        )

    assert storage.read(state.id) == prior_bytes
    assert db.get(TerraformRemoteState, state.id).serial == 0
    write = db.scalar(select(TerraformStateWrite).where(TerraformStateWrite.state_id == state.id))
    assert write.status == "COMMITTED"
    assert write.state_sha256 == hashlib.sha256(prior_bytes).hexdigest()
    assert s3.put_count == 1
    db.close()
    engine.dispose()


def test_state_storage_rotates_missing_pending_attempt_to_changed_same_serial_payload():
    s3 = _FakeS3()
    s3.fail_before_put_once = True
    engine, db, state, storage = _state_storage(s3)
    prior_bytes = _state_bytes(serial=0)
    changed_document = json.loads(prior_bytes)
    changed_document["resources"] = [{"mode": "managed", "type": "aws_s3_bucket"}]
    changed_bytes = json.dumps(changed_document).encode()
    storage.lock(
        state_id=state.id,
        run_id="run-1",
        build_id="project:build-1",
        raw=_lock_bytes(),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    with pytest.raises(TerraformStateError, match="uncertain"):
        storage.write(
            state_id=state.id,
            run_id="run-1",
            build_id="project:build-1",
            lock_id="lock-1",
            raw=prior_bytes,
        )
    write = db.scalar(select(TerraformStateWrite).where(TerraformStateWrite.state_id == state.id))
    old_key = write.object_key
    _reclaim_failed_state_lock(
        db,
        storage,
        state,
        run_id="run-1",
        build_id="project:build-1",
        lock_id="lock-1",
    )
    storage.lock(
        state_id=state.id,
        run_id="run-2",
        build_id="project:build-2",
        raw=_lock_bytes("lock-2"),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    result = storage.write(
        state_id=state.id,
        run_id="run-2",
        build_id="project:build-2",
        lock_id="lock-2",
        raw=changed_bytes,
    )

    assert result.sha256 == hashlib.sha256(changed_bytes).hexdigest()
    assert storage.read(state.id) == changed_bytes
    assert write.status == "COMMITTED"
    assert write.run_id == "run-2"
    assert write.object_key != old_key
    assert write.state_sha256 == hashlib.sha256(changed_bytes).hexdigest()
    assert write.attempt_history[0]["run_id"] == "run-1"
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


def test_concurrent_state_lock_acquisition_keeps_one_owner(tmp_path):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'terraform-state-lock-race.db'}",
        connect_args={"timeout": 10},
    )
    Base.metadata.create_all(engine)
    state = TerraformRemoteState(
        scope_sha256=hashlib.sha256(str(uuid4()).encode()).hexdigest(),
        organization_id=ORG,
        project_id=PROJECT,
        environment_id=ENVIRONMENT,
        target_account_id="654654474502",
        region="us-east-1",
    )
    with Session(engine) as setup:
        setup.add(state)
        setup.commit()
        state_id = state.id

    barrier = Barrier(2)

    def attempt(run_id: str, build_id: str, lock_id: str) -> str:
        with Session(engine) as db:
            storage = TerraformStateStorage(
                db,
                s3_client=_FakeS3(),
                bucket="davdeploy-test-state",
                kms_key_arn="arn:aws:kms:us-east-1:654654474502:key/state-key",
                expected_bucket_owner="654654474502",
            )
            original_get = db.get
            first_lock_read = True

            def synchronized_get(entity, *args, **kwargs):
                nonlocal first_lock_read
                result = original_get(entity, *args, **kwargs)
                if entity is TerraformStateLock and first_lock_read:
                    first_lock_read = False
                    barrier.wait(timeout=5)
                return result

            db.get = synchronized_get
            try:
                storage.lock(
                    state_id=state_id,
                    run_id=run_id,
                    build_id=build_id,
                    raw=_lock_bytes(lock_id),
                    expires_at=datetime.now(UTC) + timedelta(minutes=5),
                )
                return "ACQUIRED"
            except TerraformStateLocked:
                return "LOCKED"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(
            executor.map(
                lambda values: attempt(*values),
                (
                    ("run-1", "project:build-1", "lock-1"),
                    ("run-2", "project:build-2", "lock-2"),
                ),
            )
        )

    assert sorted(outcomes) == ["ACQUIRED", "LOCKED"]
    with Session(engine) as db:
        active = db.get(TerraformStateLock, state_id)
        assert active is not None
        assert (active.run_id, active.codebuild_build_id) in {
            ("run-1", "project:build-1"),
            ("run-2", "project:build-2"),
        }
    engine.dispose()


def test_expired_lock_reclaim_racing_new_acquisition_requires_retry(tmp_path):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'terraform-state-reclaim-race.db'}",
        connect_args={"timeout": 10},
    )
    Base.metadata.create_all(engine)
    state = TerraformRemoteState(
        scope_sha256=hashlib.sha256(str(uuid4()).encode()).hexdigest(),
        organization_id=ORG,
        project_id=PROJECT,
        environment_id=ENVIRONMENT,
        target_account_id="654654474502",
        region="us-east-1",
    )
    with Session(engine) as setup:
        setup.add(state)
        setup.commit()
        state_id = state.id
        storage = TerraformStateStorage(
            setup,
            s3_client=_FakeS3(),
            bucket="davdeploy-test-state",
            kms_key_arn="arn:aws:kms:us-east-1:654654474502:key/state-key",
            expected_bucket_owner="654654474502",
        )
        storage.lock(
            state_id=state_id,
            run_id="old-run",
            build_id="project:old-build",
            raw=_lock_bytes("old-lock"),
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        setup.get(TerraformStateLock, state_id).expires_at = datetime.now(UTC) - timedelta(seconds=1)
        setup.commit()

    barrier = Barrier(2)

    def race_read(db):
        original_get = db.get
        first_lock_read = True

        def synchronized_get(entity, *args, **kwargs):
            nonlocal first_lock_read
            result = original_get(entity, *args, **kwargs)
            if entity is TerraformStateLock and first_lock_read:
                first_lock_read = False
                barrier.wait(timeout=5)
            return result

        db.get = synchronized_get

    def reclaim() -> bool:
        with Session(engine) as db:
            race_read(db)
            storage = TerraformStateStorage(
                db,
                s3_client=_FakeS3(),
                bucket="davdeploy-test-state",
                kms_key_arn="arn:aws:kms:us-east-1:654654474502:key/state-key",
                expected_bucket_owner="654654474502",
            )
            return storage.reclaim_expired_lock(
                state_id=state_id,
                expected_lock_id="old-lock",
                expected_run_id="old-run",
                expected_build_id="project:old-build",
                observed_build_status="FAILED",
            )

    def acquire_new() -> str:
        with Session(engine) as db:
            race_read(db)
            storage = TerraformStateStorage(
                db,
                s3_client=_FakeS3(),
                bucket="davdeploy-test-state",
                kms_key_arn="arn:aws:kms:us-east-1:654654474502:key/state-key",
                expected_bucket_owner="654654474502",
            )
            try:
                storage.lock(
                    state_id=state_id,
                    run_id="new-run",
                    build_id="project:new-build",
                    raw=_lock_bytes("new-lock"),
                    expires_at=datetime.now(UTC) + timedelta(minutes=5),
                )
                return "ACQUIRED"
            except TerraformStateLocked:
                return "RETRY"

    with ThreadPoolExecutor(max_workers=2) as executor:
        reclaim_future = executor.submit(reclaim)
        acquire_future = executor.submit(acquire_new)
        assert reclaim_future.result(timeout=10) is True
        assert acquire_future.result(timeout=10) == "RETRY"

    with Session(engine) as db:
        storage = TerraformStateStorage(
            db,
            s3_client=_FakeS3(),
            bucket="davdeploy-test-state",
            kms_key_arn="arn:aws:kms:us-east-1:654654474502:key/state-key",
            expected_bucket_owner="654654474502",
        )
        storage.lock(
            state_id=state_id,
            run_id="new-run",
            build_id="project:new-build",
            raw=_lock_bytes("new-lock"),
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        active = db.get(TerraformStateLock, state_id)
        assert (active.run_id, active.codebuild_build_id, active.lock_id) == (
            "new-run",
            "project:new-build",
            "new-lock",
        )
    engine.dispose()
