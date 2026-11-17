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
from davdeploy.generated_plan_artifacts import (
    S3GeneratedPlanArtifactStore,
    pricing_evidence_safe_summary,
)
from davdeploy.generated_plan_pricing import PlanPricingStatus, _evidence
from davdeploy.models import (
    AuditEvent,
    Base,
    CloudConnection,
    Environment,
    GeneratedPlanApplyRun,
    GeneratedPlanApproval,
    GeneratedPlanArtifact,
    GeneratedPlanRun,
    InfrastructurePlan,
    InfrastructurePlanRevision,
    Organization,
    ProductUser,
    Project,
    TerraformRemoteState,
    TerraformStateCredential,
    TerraformStateLock,
    TerraformStateWrite,
)
from davdeploy.nova_apply_access import build_nova_apply_access_policy
from davdeploy.nova_apply_contract import ApplyArtifactObject, validate_nova_apply_request
from davdeploy.terraform_state import (
    TerraformStateError,
    TerraformStateLocked,
    TerraformStateStorage,
    credential_matches,
    issue_terraform_state_credential,
    parse_terraform_lock,
    parse_terraform_state,
    terraform_state_scope_digest,
    trusted_codebuild_build_id,
    trusted_codebuild_role_matches,
    validate_terraform_state_lock_id,
)
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, update
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


def test_codebuild_build_id_is_derived_from_the_authenticated_session():
    expected = "arn:aws:iam::654654474502:role/service-role/davdeploy-nova-plan-only"
    build_id = "davdeploy-nova-plan-only:12345678-1234-4234-8234-123456789abc"
    caller = (
        "arn:aws:sts::654654474502:assumed-role/service-role/davdeploy-nova-plan-only/"
        "AWSCodeBuild-12345678-1234-4234-8234-123456789abc"
    )
    assert trusted_codebuild_build_id(
        caller, expected, "davdeploy-nova-plan-only"
    ) == build_id
    assert trusted_codebuild_build_id(
        caller, expected, "another-project"
    ) == "another-project:12345678-1234-4234-8234-123456789abc"
    assert trusted_codebuild_build_id(
        caller.replace("/AWSCodeBuild-", "/manual-session-"),
        expected,
        "davdeploy-nova-plan-only",
    ) is None
    assert trusted_codebuild_build_id(
        caller.replace("12345678-1234-4234-8234-123456789abc", "not-a-uuid"),
        expected,
        "davdeploy-nova-plan-only",
    ) is None


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
    build_uuid = "12345678-1234-4234-8234-123456789abc"
    build_id = f"fixed-plan:{build_uuid}"
    build_arn = f"arn:aws:codebuild:us-east-1:654654474502:build/{build_id}"
    account_id = "654654474502"
    region = "us-east-1"
    build_role = "arn:aws:iam::654654474502:role/fixed-plan"
    assumed_build_role = f"arn:aws:sts::654654474502:assumed-role/fixed-plan/AWSCodeBuild-{build_uuid}"
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
            json={"run_id": run_id},
        )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["pragma"] == "no-cache"
        assert codebuild.calls == [[build_id]]
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
        audit_event = db.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "terraform_state_credentials.issued"
            )
        )
        assert audit_event is not None
        assert audit_event.actor_subject == assumed_build_role
        assert audit_event.entity_id == run_id
        assert audit_event.detail == {
            "codebuild_build_arn": build_arn,
            "project_id": PROJECT,
            "revision_id": revision_id,
            "revision_sha256": "d" * 64,
            "state_id": credential_document["state_id"],
            "state_scope_sha256": credential_document["scope_sha256"],
            "target_account_id": account_id,
            "region": region,
        }
        assert credential_document["password"] not in repr(audit_event.detail)

        another_build_session = client.post(
            "/api/v1/terraform-state/credentials",
            headers={
                "x-davdeploy-bootstrap-principal": (
                    "arn:aws:sts::654654474502:assumed-role/fixed-plan/"
                    "AWSCodeBuild-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
                )
            },
            json={"run_id": run_id},
        )
        assert another_build_session.status_code == 403

        caller_selected_build = client.post(
            "/api/v1/terraform-state/credentials",
            headers=headers,
            json={"run_id": run_id, "codebuild_build_id": "fixed-plan:other-build"},
        )
        assert caller_selected_build.status_code == 422

        cross_tenant = client.get(
            f"/api/v1/terraform-state/{other_state}",
            auth=(credential_document["username"], credential_document["password"]),
        )
        assert cross_tenant.status_code == 401

    assert len(codebuild.calls) == 1
    db.close()


def test_state_bootstrap_binds_exact_plan_apply_to_active_approved_build(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    plan_id = "d1dd65f5-4f21-4e26-85b7-74d75fc7db8c"
    revision_id = "fdac3a35-9b91-4b45-84a7-c6067106d485"
    plan_run_id = "7d1d82be-9e2a-4de1-8dd1-c78c9241a3a0"
    artifact_id = "ed350f1b-61b1-4edc-9799-35332aa96283"
    approval_id = "8f7c5f1e-9200-4d9c-91d9-8afdd81ec52f"
    state_id = "11111111-1111-4111-8111-111111111111"
    apply_run_id = "12345678-1234-4234-8234-123456789abc"
    build_uuid = "abcdefff-1234-4234-8234-123456789abc"
    build_id = f"fixed-apply:{build_uuid}"
    build_arn = f"arn:aws:codebuild:us-east-1:654654474502:build/{build_id}"
    apply_role = "arn:aws:iam::654654474502:role/fixed-apply"
    assumed_apply_role = (
        f"arn:aws:sts::654654474502:assumed-role/fixed-apply/AWSCodeBuild-{build_uuid}"
    )
    connection_id = "66b3854d-745f-4553-90bf-46e5c4da390f"
    account_id = "654654474502"
    region = "us-east-1"
    revision_content = {
        "target": {
            "connection_id": connection_id,
            "environment_id": ENVIRONMENT,
            "account_id": account_id,
            "region": region,
        }
    }
    revision_digest = main.plan_hash(revision_content)
    state_scope = terraform_state_scope_digest(
        organization_id=ORG,
        project_id=PROJECT,
        environment_id=ENVIRONMENT,
        target_account_id=account_id,
        region=region,
    )
    pricing_evidence = _evidence(
        status=PlanPricingStatus.COMPLETE,
        region=region,
        currency="USD",
        captured_at=datetime.now(UTC).isoformat(),
        budget=None,
        document={},
        lines=(),
        findings=(),
        persisted_context_sha256="b" * 64,
    )
    pricing_document = pricing_evidence.as_manifest_document()
    apply_access = build_nova_apply_access_policy(
        {
            "resource_changes": [
                {
                    "mode": "managed",
                    "type": "aws_s3_bucket",
                    "address": "aws_s3_bucket.example",
                    "change": {
                        "actions": ["create"],
                        "before": None,
                        "after": {"bucket": "nova-test-bucket"},
                    },
                }
            ]
        },
        account_id=account_id,
        region=region,
    )
    plan_sha256 = "2" * 64
    workspace_sha256 = "6" * 64
    artifact_bucket = "davdeploy-plans-654654474502"
    plan_build_arn = "arn:aws:codebuild:us-east-1:654654474502:build/fixed-plan:old-plan-run"
    plan_key = S3GeneratedPlanArtifactStore._key(
        ORG,
        PROJECT,
        revision_id,
        plan_run_id,
        plan_sha256,
        build_arn=plan_build_arn,
    )
    workspace_key = S3GeneratedPlanArtifactStore._key(
        ORG,
        PROJECT,
        revision_id,
        plan_run_id,
        workspace_sha256,
        build_arn=plan_build_arn,
        artifact_kind="workspace",
    )
    digests = {
        "customer_revision_sha256": revision_digest,
        "saved_plan_sha256": plan_sha256,
        "workspace_sha256": workspace_sha256,
        "pricing_evidence_sha256": pricing_document["evidence_sha256"],
        "pricing_context_sha256": pricing_document["pricing_context_sha256"],
        "plan_json_sha256": pricing_document["plan_json_sha256"],
    }
    manifest = {
        "tenant": {
            "organization_id": ORG,
            "project_id": PROJECT,
            "revision_id": revision_id,
            "environment_id": ENVIRONMENT,
        },
        "target": {"account_id": account_id, "region": region},
        "remote_state": {"state_id": state_id, "scope_sha256": state_scope},
        "pricing": pricing_evidence.safe_summary(),
        "pricing_evidence": pricing_document,
        "customer_apply_access": {
            "status": "READY",
            "version": apply_access.version,
            "session_policy_sha256": apply_access.sha256,
            "session_policy": apply_access.document,
        },
        "policy": {"human_approval_required": True, "verdict": "REVIEW_REQUIRED"},
        "planning_boundary": {"approval_allowed": True, "execution_allowed": True},
        "artifact": {
            "bucket": artifact_bucket,
            "key": plan_key,
            "version_id": "plan-version",
            "size_bytes": 10,
            "sha256": plan_sha256,
        },
        "execution_workspace": {
            "bucket": artifact_bucket,
            "key": workspace_key,
            "version_id": "workspace-version",
            "size_bytes": 11,
            "sha256": workspace_sha256,
        },
        "digests": digests,
    }
    manifest_digest = main.canonical_json_digest(manifest)
    request_document = {
        "contract_version": 1,
        "organization_id": ORG,
        "project_id": PROJECT,
        "revision_id": revision_id,
        "revision_sha256": revision_digest,
        "source_plan_run_id": plan_run_id,
        "artifact_id": artifact_id,
        "approval_id": approval_id,
        "manifest_sha256": manifest_digest,
        "target": {"account_id": account_id, "region": region},
        "digests": digests,
        "saved_plan": {
            "bucket": artifact_bucket,
            "key": plan_key,
            "version_id": "plan-version",
            "size_bytes": 10,
            "sha256": plan_sha256,
        },
        "execution_workspace": {
            "bucket": artifact_bucket,
            "key": workspace_key,
            "version_id": "workspace-version",
            "size_bytes": 11,
            "sha256": workspace_sha256,
        },
        "requester_subject": "admin",
    }
    db.add_all(
        [
            Organization(id=ORG, name="state-apply-test-org"),
            Project(id=PROJECT, organization_id=ORG, name="state-apply-test-project"),
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
            ProductUser(id="apply-admin-user", organization_id=ORG, subject="admin", role="administrator"),
            CloudConnection(
                id=connection_id,
                organization_id=ORG,
                provider="aws",
                display_name="Verified account",
                account_id=account_id,
                execution_role_arn=f"arn:aws:iam::{account_id}:role/davdeployExecution-legacy",
                external_id_secret_ref="customer-connection-secret-ref",
                setup_state="VERIFIED",
            ),
            InfrastructurePlan(
                id=plan_id,
                organization_id=ORG,
                project_id=PROJECT,
                creator_subject="admin",
                title="Apply state test",
            ),
            InfrastructurePlanRevision(
                id=revision_id,
                infrastructure_plan_id=plan_id,
                organization_id=ORG,
                revision_number=1,
                state="APPROVED",
                content=revision_content,
                content_digest=revision_digest,
            ),
            GeneratedPlanRun(
                id=plan_run_id,
                organization_id=ORG,
                project_id=PROJECT,
                revision_id=revision_id,
                requester_subject="admin",
                idempotency_key_sha256="b" * 64,
                request_sha256="c" * 64,
                request_document={"target_account_id": account_id, "region": region},
                runner_run_id=plan_run_id,
                revision_sha256=revision_digest,
                state="PLAN_READY_REVIEW_ONLY",
                codebuild_project="fixed-plan",
                codebuild_build_id="fixed-plan:old-plan-run",
                input_key="plan-input.json",
                result_key="plan-result.json",
            ),
            GeneratedPlanArtifact(
                id=artifact_id,
                organization_id=ORG,
                project_id=PROJECT,
                revision_id=revision_id,
                run_id=plan_run_id,
                target_account_id=account_id,
                region=region,
                terraform_version="1.14.7",
                aws_provider_version="6.0.0",
                provider_lockfile_sha256="d" * 64,
                proposal_sha256="e" * 64,
                context_sha256="f" * 64,
                configuration_sha256="1" * 64,
                saved_plan_sha256=plan_sha256,
                policy_sha256="3" * 64,
                manifest_sha256=manifest_digest,
                manifest=manifest,
                policy_version="generated-plan-policy-v1",
                policy_verdict="REVIEW_REQUIRED",
                artifact_bucket=artifact_bucket,
                artifact_key=plan_key,
                artifact_version_id="plan-version",
                artifact_size_bytes=10,
                workspace_artifact_bucket=artifact_bucket,
                workspace_artifact_key=workspace_key,
                workspace_artifact_version_id="workspace-version",
                workspace_artifact_size_bytes=11,
                workspace_sha256=workspace_sha256,
                created_by_subject="admin",
                expires_at=datetime.now(UTC) + timedelta(minutes=30),
            ),
            GeneratedPlanApproval(
                id=approval_id,
                artifact_id=artifact_id,
                organization_id=ORG,
                project_id=PROJECT,
                revision_id=revision_id,
                approved_manifest_sha256=manifest_digest,
                approver_subject="admin",
                creator_subject="admin",
                is_self_approval=True,
                authorization_policy="workspace-administrator-self-approval-allowed",
            ),
            GeneratedPlanApplyRun(
                id=apply_run_id,
                organization_id=ORG,
                project_id=PROJECT,
                revision_id=revision_id,
                source_plan_run_id=plan_run_id,
                artifact_id=artifact_id,
                approval_id=approval_id,
                requester_subject="admin",
                idempotency_key_sha256="4" * 64,
                request_sha256=main.canonical_json_digest(request_document),
                manifest_sha256=manifest_digest,
                runner_run_id=apply_run_id,
                codebuild_idempotency_token=apply_run_id,
                codebuild_project="fixed-apply",
                codebuild_build_id=build_id,
                codebuild_build_arn=build_arn,
                state="BUILD_STARTED",
                request_document=request_document,
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
                        "projectName": "fixed-apply",
                        "serviceRole": apply_role,
                        "buildStatus": "IN_PROGRESS",
                        "arn": build_arn,
                        "environment": {
                            "environmentVariables": [
                                {"name": "DAVDEPLOY_NOVA_APPLY_RUN_ID", "value": apply_run_id}
                            ]
                        },
                    }
                ]
            }

    codebuild = FakeCodeBuild()
    monkeypatch.setenv("DAVDEPLOY_TERRAFORM_STATE_ENABLED", "true")
    monkeypatch.setenv("DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_RUNNER_READY", "true")
    monkeypatch.setenv("DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_ROLE_ARN", apply_role)
    monkeypatch.setenv("DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_PROJECT", "fixed-apply")
    monkeypatch.setenv("DAVDEPLOY_NOVA_PLAN_ARTIFACT_BUCKET", artifact_bucket)
    monkeypatch.setenv("DAVDEPLOY_NOVA_APPLY_BUCKET_OWNER", account_id)
    monkeypatch.setenv(
        "DAVDEPLOY_NOVA_APPLY_KMS_KEY_ARN",
        f"arn:aws:kms:{region}:{account_id}:key/11111111-2222-3333-4444-555555555555",
    )
    monkeypatch.setenv("DAVDEPLOY_TERRAFORM_STATE_API_URL", "https://api.davdeploy.tech")
    monkeypatch.setattr(main, "ensure_aurora_ready", lambda: None)
    staged_prefix = (
        "plans/nova-generated/apply-builds/"
        f"{build_arn}/artifacts/{apply_run_id}/"
    )
    monkeypatch.setattr(
        main,
        "stage_nova_apply_artifacts",
        lambda _request, **_kwargs: (
            ApplyArtifactObject(
                bucket=artifact_bucket,
                key=staged_prefix + "saved.tfplan",
                version_id="staged-plan-version",
                size_bytes=10,
                sha256=plan_sha256,
            ),
            ApplyArtifactObject(
                bucket=artifact_bucket,
                key=staged_prefix + "execution-workspace.tar.gz",
                version_id="staged-workspace-version",
                size_bytes=11,
                sha256=workspace_sha256,
            ),
        ),
    )
    monkeypatch.setattr(
        main.boto3,
        "client",
        lambda name, **_kwargs: codebuild if name == "codebuild" else None,
    )
    monkeypatch.setitem(main.app.dependency_overrides, main.session, override_session)

    with TestClient(main.app) as client:
        monkeypatch.setenv("DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_RUNNER_READY", "false")
        input_disabled = client.post(
            "/api/v1/nova-apply/input",
            headers={"x-davdeploy-bootstrap-principal": assumed_apply_role},
            json={"run_id": apply_run_id},
        )
        assert input_disabled.status_code == 404
        monkeypatch.setenv("DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_RUNNER_READY", "true")

        apply_input = client.post(
            "/api/v1/nova-apply/input",
            headers={"x-davdeploy-bootstrap-principal": assumed_apply_role},
            json={"run_id": apply_run_id},
        )
        assert apply_input.status_code == 200
        assert apply_input.headers["cache-control"] == "no-store"
        validated_input = validate_nova_apply_request(
            apply_input.json(),
            expected_run_id=apply_run_id,
            expected_codebuild_project="fixed-apply",
            expected_codebuild_build_arn=build_arn,
            expected_artifact_bucket=artifact_bucket,
            now=datetime.now(UTC),
            require_staged_artifacts=True,
        )
        assert validated_input.saved_plan.key == plan_key
        assert validated_input.execution_workspace.key == workspace_key
        assert validated_input.staged_saved_plan.key == staged_prefix + "saved.tfplan"
        input_event = db.scalar(
            select(AuditEvent).where(AuditEvent.action == "nova_apply_input.issued")
        )
        assert input_event is not None
        assert input_event.entity_id == apply_run_id

        broker_disabled = client.post(
            "/api/v1/nova-apply/credentials",
            headers={"x-davdeploy-bootstrap-principal": assumed_apply_role},
            json={"run_id": apply_run_id},
        )
        assert broker_disabled.status_code == 404

        response = client.post(
            "/api/v1/terraform-state/credentials",
            headers={"x-davdeploy-bootstrap-principal": assumed_apply_role},
            json={"run_id": apply_run_id},
        )
        assert response.status_code == 200
        assert codebuild.calls == [[build_id], [build_id]]
        credential_document = response.json()
        credential = db.scalar(
            select(TerraformStateCredential).where(
                TerraformStateCredential.username == credential_document["username"]
            )
        )
        assert credential is not None
        assert credential.run_id == plan_run_id
        assert credential.apply_run_id == apply_run_id
        state_credential, authorized_run = main._terraform_state_authorization(
            credential.state_id,
            SimpleNamespace(
                username=credential_document["username"],
                password=credential_document["password"],
            ),
            db,
        )
        assert state_credential.id == credential.id
        assert authorized_run.id == plan_run_id
        event = db.scalar(
            select(AuditEvent).where(AuditEvent.action == "terraform_state_credentials.issued")
        )
        assert event is not None
        assert event.entity_type == "generated_plan_apply_run"
        assert event.entity_id == apply_run_id

        expiration = datetime.now(UTC) + timedelta(minutes=15)

        class FakeSts:
            def __init__(self):
                self.calls = []

            def assume_role(self, **kwargs):
                self.calls.append(kwargs)
                return {
                    "Credentials": {
                        "AccessKeyId": "ASIAEXAMPLE",
                        "SecretAccessKey": "secret-example",
                        "SessionToken": "session-example",
                        "Expiration": expiration,
                    }
                }

        fake_sts = FakeSts()

        class FakeSession:
            identity_account = account_id

            def __init__(self, **_kwargs):
                pass

            def client(self, name):
                assert name == "sts"
                return SimpleNamespace(
                    get_caller_identity=lambda: {
                        "Account": self.identity_account,
                        "Arn": f"arn:aws:sts::{account_id}:assumed-role/"
                        f"davdeployNovaApply-{connection_id}/davdeploy-nova-apply-{apply_run_id}",
                    }
                )

        monkeypatch.setenv(
            "DAVDEPLOY_NOVA_EXACT_PLAN_APPLY_CREDENTIAL_BROKER_ENABLED", "true"
        )
        monkeypatch.setattr(
            main,
            "configured_connection_secret_store",
            lambda: SimpleNamespace(
                get_external_id=lambda secret_ref: (
                    "customer-external-id" if secret_ref == "customer-connection-secret-ref" else None
                )
            ),
        )
        monkeypatch.setattr(
            main.boto3,
            "client",
            lambda name, **_kwargs: codebuild if name == "codebuild" else fake_sts,
        )
        monkeypatch.setattr(
            main,
            "StsAwsDiscovery",
            lambda: SimpleNamespace(
                verify_apply_role=lambda _connection_id, role_arn, _external_id, _region: SimpleNamespace(
                    account_id=account_id,
                    role_arn=role_arn,
                    version="nova-apply-role-profile.v1",
                    sha256="a" * 64,
                )
            ),
        )
        monkeypatch.setattr(main.boto3, "Session", FakeSession)
        apply_credentials = client.post(
            "/api/v1/nova-apply/credentials",
            headers={"x-davdeploy-bootstrap-principal": assumed_apply_role},
            json={"run_id": apply_run_id},
        )
        assert apply_credentials.status_code == 200
        assert apply_credentials.headers["cache-control"] == "no-store"
        assert apply_credentials.json() == {
            "contract": "davdeploy.nova-apply-credentials.v1",
            "role_arn": f"arn:aws:iam::{account_id}:role/davdeployNovaApply-{connection_id}",
            "account_id": account_id,
            "region": region,
            "policy_version": apply_access.version,
            "policy_sha256": apply_access.sha256,
            "credentials": {
                "access_key_id": "ASIAEXAMPLE",
                "secret_access_key": "secret-example",
                "session_token": "session-example",
                "expires_at": expiration.isoformat(),
            },
        }
        assert fake_sts.calls == [
            {
                "RoleArn": f"arn:aws:iam::{account_id}:role/davdeployNovaApply-{connection_id}",
                "RoleSessionName": f"davdeploy-nova-apply-{apply_run_id}",
                "ExternalId": "customer-external-id",
                "DurationSeconds": 900,
                "Policy": json.dumps(
                    apply_access.document, sort_keys=True, separators=(",", ":")
                ),
            }
        ]
        apply_event = db.scalar(
            select(AuditEvent).where(AuditEvent.action == "nova_apply_credentials.issued")
        )
        assert apply_event is not None
        assert apply_event.entity_id == apply_run_id
        assert (
            apply_event.detail["execution_role_arn"]
            == f"arn:aws:iam::{account_id}:role/davdeployNovaApply-{connection_id}"
        )

        FakeSession.identity_account = "000000000000"
        wrong_account = client.post(
            "/api/v1/nova-apply/credentials",
            headers={"x-davdeploy-bootstrap-principal": assumed_apply_role},
            json={"run_id": apply_run_id},
        )
        assert wrong_account.status_code == 403
        assert db.query(AuditEvent).filter_by(action="nova_apply_credentials.issued").count() == 1

        FakeSession.identity_account = account_id
        expiration = datetime.now(UTC) - timedelta(minutes=1)
        expired_credentials = client.post(
            "/api/v1/nova-apply/credentials",
            headers={"x-davdeploy-bootstrap-principal": assumed_apply_role},
            json={"run_id": apply_run_id},
        )
        assert expired_credentials.status_code == 403
        assert db.query(AuditEvent).filter_by(action="nova_apply_credentials.issued").count() == 1

        artifact_record = db.get(GeneratedPlanArtifact, artifact_id)
        apply_run_record = db.get(GeneratedPlanApplyRun, apply_run_id)
        original_manifest = artifact_record.manifest
        original_manifest_sha256 = artifact_record.manifest_sha256
        original_request_document = apply_run_record.request_document
        original_request_sha256 = apply_run_record.request_sha256
        incomplete_pricing = _evidence(
            status=PlanPricingStatus.UNAVAILABLE,
            region=region,
            currency="USD",
            captured_at=datetime.now(UTC).isoformat(),
            budget=None,
            document={},
            lines=(),
            findings=(),
            persisted_context_sha256="b" * 64,
        ).as_manifest_document()
        incomplete_manifest = json.loads(json.dumps(original_manifest))
        incomplete_manifest["pricing_evidence"] = incomplete_pricing
        incomplete_manifest["pricing"] = pricing_evidence_safe_summary(incomplete_pricing)
        incomplete_manifest["digests"]["pricing_evidence_sha256"] = incomplete_pricing[
            "evidence_sha256"
        ]
        incomplete_manifest["digests"]["pricing_context_sha256"] = incomplete_pricing[
            "pricing_context_sha256"
        ]
        incomplete_manifest["digests"]["plan_json_sha256"] = incomplete_pricing[
            "plan_json_sha256"
        ]
        incomplete_manifest_sha256 = main.canonical_json_digest(incomplete_manifest)
        incomplete_request_document = json.loads(json.dumps(original_request_document))
        incomplete_request_document["manifest_sha256"] = incomplete_manifest_sha256
        incomplete_request_document["digests"] = incomplete_manifest["digests"]
        db.execute(
            update(GeneratedPlanArtifact)
            .where(GeneratedPlanArtifact.id == artifact_id)
            .values(
                manifest=incomplete_manifest,
                manifest_sha256=incomplete_manifest_sha256,
            )
        )
        db.execute(
            update(GeneratedPlanApproval)
            .where(GeneratedPlanApproval.id == approval_id)
            .values(approved_manifest_sha256=incomplete_manifest_sha256)
        )
        db.execute(
            update(GeneratedPlanApplyRun)
            .where(GeneratedPlanApplyRun.id == apply_run_id)
            .values(
                manifest_sha256=incomplete_manifest_sha256,
                request_document=incomplete_request_document,
                request_sha256=main.canonical_json_digest(incomplete_request_document),
            )
        )
        db.commit()
        db.expire_all()
        calls_before_incomplete_pricing = len(fake_sts.calls)
        incomplete_pricing_credentials = client.post(
            "/api/v1/nova-apply/credentials",
            headers={"x-davdeploy-bootstrap-principal": assumed_apply_role},
            json={"run_id": apply_run_id},
        )
        assert incomplete_pricing_credentials.status_code == 403
        assert len(fake_sts.calls) == calls_before_incomplete_pricing
        assert db.query(AuditEvent).filter_by(action="nova_apply_credentials.issued").count() == 1

        db.execute(
            update(GeneratedPlanArtifact)
            .where(GeneratedPlanArtifact.id == artifact_id)
            .values(
                manifest=original_manifest,
                manifest_sha256=original_manifest_sha256,
            )
        )
        db.execute(
            update(GeneratedPlanApproval)
            .where(GeneratedPlanApproval.id == approval_id)
            .values(approved_manifest_sha256=original_manifest_sha256)
        )
        db.execute(
            update(GeneratedPlanApplyRun)
            .where(GeneratedPlanApplyRun.id == apply_run_id)
            .values(
                manifest_sha256=original_manifest_sha256,
                request_document=original_request_document,
                request_sha256=original_request_sha256,
            )
        )
        db.commit()
        db.expire_all()

        db.get(ProductUser, "apply-admin-user").role = "developer"
        db.commit()
        revoked_admin = client.post(
            "/api/v1/nova-apply/credentials",
            headers={"x-davdeploy-bootstrap-principal": assumed_apply_role},
            json={"run_id": apply_run_id},
        )
        assert revoked_admin.status_code == 403
        codebuild.calls.clear()
        with pytest.raises(HTTPException, match="Current workspace administrator authorization"):
            main._terraform_state_authorization(
                credential.state_id,
                SimpleNamespace(
                    username=credential_document["username"],
                    password=credential_document["password"],
                ),
                db,
            )
        assert codebuild.calls == []
        denied = client.post(
            "/api/v1/terraform-state/credentials",
            headers={"x-davdeploy-bootstrap-principal": assumed_apply_role},
            json={"run_id": apply_run_id},
        )
        assert denied.status_code == 403
        assert codebuild.calls == []

    from davdeploy.nova_apply_dispatch import NovaApplyBuild

    class SuccessfulApplyResultReader:
        project_name = "fixed-apply"

        def describe_build(self, requested_build_id):
            assert requested_build_id == build_id
            return NovaApplyBuild(
                build_id=build_id,
                project_name="fixed-apply",
                status="SUCCEEDED",
                run_id=apply_run_id,
                build_arn=build_arn,
            )

        def read_result(self, requested_run_id, request, requested_build_id, requested_build_arn, **kwargs):
            assert requested_run_id == apply_run_id
            assert request == request_document
            assert requested_build_id == build_id
            assert requested_build_arn == build_arn
            assert kwargs == {
                "expected_state_id": state_id,
                "expected_state_scope_sha256": state_scope,
                "expected_account_id": account_id,
                "expected_region": region,
            }
            return (
                {
                    "execution_status": "APPLIED_UNVERIFIED",
                    "state_id": state_id,
                    "state_scope_sha256": state_scope,
                    "terraform_version": "1.14.7",
                    "aws_provider_version": "6.0.0",
                },
                "result-version-1",
                "a" * 64,
            )

        @staticmethod
        def result_key(requested_build_arn):
            return f"plans/nova-generated/apply-builds/{requested_build_arn}/result.json"

    reconciler = main.ProductService(db, nova_apply_dispatcher=SuccessfulApplyResultReader())
    assert reconciler.reconcile_generated_plan_apply_build(build_id) is True
    db.expire_all()
    reconciled_run = db.get(GeneratedPlanApplyRun, apply_run_id)
    assert reconciled_run.state == "APPLIED_UNVERIFIED"
    assert reconciled_run.result_metadata == {
        "codebuild_status": "SUCCEEDED",
        "codebuild_build_arn": build_arn,
        "result_key": f"plans/nova-generated/apply-builds/{build_arn}/result.json",
        "result_version_id": "result-version-1",
        "result_sha256": "a" * 64,
        "manifest_sha256": manifest_digest,
        "execution_status": "APPLIED_UNVERIFIED",
        "state_id": state_id,
        "state_scope_sha256": state_scope,
    }
    reconcile_event = db.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "generated_plan_apply.build_reconciled"
        )
    )
    assert reconcile_event is not None
    assert reconcile_event.entity_id == apply_run_id
    assert reconcile_event.detail["result_sha256"] == "a" * 64

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
