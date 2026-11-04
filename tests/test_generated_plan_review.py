from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

import pytest
from davdeploy.db import make_engine, run_migrations
from davdeploy.domain import InfrastructurePlanDecision
from davdeploy.generated_deployment_contract import (
    GeneratedDeploymentProposal,
    GeneratedResource,
    WorkloadRequirements,
)
from davdeploy.generated_plan_artifacts import StoredPlanObject, canonical_json_digest
from davdeploy.generated_plan_inspection import TerraformPlanSummary
from davdeploy.generated_plan_policy import (
    GeneratedPlanPolicyResult,
    PlanPolicyFinding,
    PlanPolicyVerdict,
)
from davdeploy.generated_terraform_plan import GeneratedTerraformPlan
from davdeploy.main import app, product_service
from davdeploy.models import GeneratedPlanApproval, GeneratedPlanArtifact
from davdeploy.policy import PolicyClient
from davdeploy.security import Principal, issue_local_token
from davdeploy.service import ProductService, plan_hash
from davdeploy.terraform_generation import generation_context_digest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from test_customer_plan_review import complete_prompt
from test_product import LocalExecutor, founder, make_service, operator

ACCOUNT_ID = "654654474502"
PLAN_BYTES = b"opaque saved plan bytes"
RUN_ID = str(uuid.uuid4())


def administrator():
    return Principal("user-administrator", "org-demo", "administrator")


class ArtifactStoreFixture:
    def __init__(self, *, missing_on_verify: bool = False):
        self.missing_on_verify = missing_on_verify
        self.saved = []
        self.verified = []

    def store_saved_plan(self, path, **kwargs):
        assert Path(path).read_bytes() == PLAN_BYTES
        self.saved.append(kwargs)
        return StoredPlanObject(
            "davdeploy-tfplans-654654474502",
            "plans/nova-generated/org-hash/project-hash/revision-hash/run/plan.tfplan",
            "version-exact-1",
            len(PLAN_BYTES),
            hashlib.sha256(PLAN_BYTES).hexdigest(),
        )

    def verify_stored_plan(self, stored, *, run_id, **_scope):
        self.verified.append((stored, run_id))
        if self.missing_on_verify:
            from davdeploy.generated_plan_artifacts import GeneratedPlanArtifactError

            raise GeneratedPlanArtifactError("not found")


def make_approved_revision(service):
    project = service.create_project(
        founder(), "nova-artifact-project", "https://github.com/example/nova-artifact", "main"
    )
    connection = service.create_cloud_connection(
        founder(), "Verified test account", "aws", "byoc_role_contract"
    )
    connection.account_id = ACCOUNT_ID
    connection.setup_state = "VERIFIED"
    service.db.commit()
    snapshot = service.cloud_discovery.inventory("local-aws-fixture", "us-east-1")
    service.record_cloud_inventory_snapshot(
        founder(),
        connection.id,
        "us-east-1",
        snapshot.provenance,
        snapshot.discovered_at,
        snapshot.model_dump(mode="json"),
    )
    intent = service.create_intent(
        founder(),
        project.id,
        complete_prompt(500),
        project.repository_url,
        connection.id,
        "nova-generated-artifact-intent",
    )
    deployment = service.plan_intent(founder(), intent.id)
    revision = service.create_customer_plan_review(founder(), deployment.id)
    revision.content["target"]["account_id"] = ACCOUNT_ID
    revision.content["target"]["region"] = "us-east-1"
    revision.content_digest = plan_hash(revision.content)
    service.db.commit()
    service.submit_infrastructure_plan(founder(), revision.id)
    approved = service.decide_infrastructure_plan(
        operator(), revision.id, InfrastructurePlanDecision.APPROVED, revision.content_digest
    )
    return project, connection, approved


def generated_runner_result(tmp_path, revision):
    plan_file = tmp_path / "saved.tfplan"
    plan_file.write_bytes(PLAN_BYTES)
    os.chmod(plan_file, 0o600)
    proposal = GeneratedDeploymentProposal(
        contract_version="1.0",
        source_revision=revision.id,
        context_digest=generation_context_digest(revision.content, revision.id),
        resources=(
            GeneratedResource(
                resource_id="app-storage",
                resource_type="aws_s3_bucket",
                name="app_data",
                arguments={"bucket": "private-test-data"},
                rationale="Private application storage.",
            ),
        ),
        requirements=WorkloadRequirements(region="us-east-1"),
    )
    proposal_digest = hashlib.sha256(
        json.dumps(proposal.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    policy = GeneratedPlanPolicyResult(
        PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW, "generated-plan-policy-test", ()
    )
    summary = TerraformPlanSummary(
        format_version="1.2",
        applyable=True,
        errored=False,
        resource_changes=(),
        create_count=1,
        update_count=0,
        delete_count=0,
        replacement_count=0,
        read_count=0,
        no_op_count=0,
        drift_count=0,
        contains_sensitive_changes=False,
    )
    generated = GeneratedTerraformPlan(
        summary=summary,
        policy=policy,
        target_account_id=ACCOUNT_ID,
        region="us-east-1",
        terraform_version="1.14.7",
        aws_provider_version="5.100.0",
        provider_lockfile_sha256="b" * 64,
        proposal_sha256=proposal_digest,
        context_sha256=proposal.context_digest,
        configuration_sha256="c" * 64,
        saved_plan_sha256=hashlib.sha256(PLAN_BYTES).hexdigest(),
        saved_plan_path=str(plan_file),
    )
    return proposal, generated


def service_with_artifact_store(store):
    service, db = make_service()
    service.generated_plan_artifact_store = store
    return service, db


def service_with_file_database(store, database_path):
    engine = make_engine(f"sqlite+pysqlite:///{database_path}")
    run_migrations(engine)
    db = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    service = ProductService(
        db,
        policy=PolicyClient(fixture=True),
        executor=LocalExecutor(),
        generated_plan_artifact_store=store,
    )
    service.seed_local_identity()
    return service, db


def test_generated_plan_manifest_persists_and_admin_approves_exact_artifact(tmp_path):
    store = ArtifactStoreFixture()
    service, db = service_with_artifact_store(store)
    _, _, revision = make_approved_revision(service)
    proposal, generated = generated_runner_result(tmp_path, revision)

    artifact = service.persist_generated_plan_artifact(
        founder(), revision.id, RUN_ID, proposal, generated
    )
    detail = service.generated_plan_artifact_detail(founder(), artifact.id)

    assert detail["state"] == "AWAITING_HUMAN_APPROVAL"
    assert detail["execution"] == "NOT_APPLIED_REVIEW_ONLY"
    assert detail["manifest_sha256"] == canonical_json_digest(artifact.manifest)
    assert "artifact_bucket" not in detail
    assert "artifact_key" not in detail
    assert "version-exact-1" not in repr(detail)
    assert len(store.saved) == 1

    with pytest.raises(IntegrityError, match="generated plan evidence is immutable"):
        db.execute(
            update(GeneratedPlanArtifact)
            .where(GeneratedPlanArtifact.id == artifact.id)
            .values(policy_verdict="DENY")
        )
    db.rollback()
    with pytest.raises(IntegrityError, match="generated plan evidence is immutable"):
        db.execute(
            delete(GeneratedPlanArtifact).where(GeneratedPlanArtifact.id == artifact.id)
        )
    db.rollback()

    with pytest.raises(PermissionError, match="administrator role"):
        service.approve_generated_plan_artifact(founder(), artifact.id, artifact.manifest_sha256)

    with pytest.raises(PermissionError, match="administrator role"):
        service.approve_generated_plan_artifact(operator(), artifact.id, artifact.manifest_sha256)

    approved = service.approve_generated_plan_artifact(
        administrator(), artifact.id, artifact.manifest_sha256
    )
    record = db.scalar(
        select(GeneratedPlanApproval).where(GeneratedPlanApproval.artifact_id == artifact.id)
    )
    assert approved["state"] == "APPROVED"
    assert record.approved_manifest_sha256 == artifact.manifest_sha256
    assert record.is_self_approval is False
    assert store.verified[0][1] == RUN_ID
    assert (
        service.infrastructure_plan_revision_detail(founder(), revision.id)["state"] == "APPROVED"
    )
    with pytest.raises(ValueError, match="already been approved"):
        service.approve_generated_plan_artifact(
            administrator(), artifact.id, artifact.manifest_sha256
        )


def test_generated_plan_approval_rejects_tampering_expiry_and_missing_object(tmp_path):
    store = ArtifactStoreFixture(missing_on_verify=True)
    service, _ = service_with_artifact_store(store)
    _, _, revision = make_approved_revision(service)
    proposal, generated = generated_runner_result(tmp_path, revision)
    artifact = service.persist_generated_plan_artifact(
        founder(), revision.id, RUN_ID, proposal, generated
    )

    with pytest.raises(ValueError, match="digest does not match"):
        service.approve_generated_plan_artifact(administrator(), artifact.id, "0" * 64)

    with pytest.raises(ValueError, match="missing or failed integrity"):
        service.approve_generated_plan_artifact(
            administrator(), artifact.id, artifact.manifest_sha256
        )
    assert not service.db.scalar(
        select(GeneratedPlanApproval.id).where(GeneratedPlanApproval.artifact_id == artifact.id)
    )


def test_generated_plan_persistence_rejects_denied_policy_and_wrong_parent_state(tmp_path):
    store = ArtifactStoreFixture()
    service, _ = service_with_artifact_store(store)
    _, _, revision = make_approved_revision(service)
    proposal, generated = generated_runner_result(tmp_path, revision)
    denied = GeneratedPlanPolicyResult(PlanPolicyVerdict.DENY, "generated-plan-policy-test", ())
    generated = GeneratedTerraformPlan(**(generated.__dict__ | {"policy": denied}))

    with pytest.raises(ValueError, match="trusted runner evidence"):
        service.persist_generated_plan_artifact(
            founder(), revision.id, str(uuid.uuid4()), proposal, generated
        )
    assert store.saved == []


def test_generated_plan_policy_rejects_deny_finding_even_with_reviewable_verdict(tmp_path):
    store = ArtifactStoreFixture()
    service, _ = service_with_artifact_store(store)
    _, _, revision = make_approved_revision(service)
    proposal, generated = generated_runner_result(tmp_path, revision)
    contradictory_policy = GeneratedPlanPolicyResult(
        PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW,
        "generated-plan-policy-test",
        (PlanPolicyFinding("public_database", "deny", "aws_db_instance.db", "Public database."),),
    )
    generated = GeneratedTerraformPlan(**(generated.__dict__ | {"policy": contradictory_policy}))

    with pytest.raises(ValueError, match="trusted runner evidence"):
        service.persist_generated_plan_artifact(
            founder(), revision.id, str(uuid.uuid4()), proposal, generated
        )
    assert store.saved == []


def test_generated_plan_persistence_binds_proposal_to_exact_customer_revision(tmp_path):
    store = ArtifactStoreFixture()
    service, _ = service_with_artifact_store(store)
    _, _, revision = make_approved_revision(service)
    proposal, generated = generated_runner_result(tmp_path, revision)
    detached_proposal = proposal.model_copy(update={"context_digest": "f" * 64})
    generated = GeneratedTerraformPlan(
        **(
            generated.__dict__
            | {
                "proposal_sha256": hashlib.sha256(
                    json.dumps(
                        detached_proposal.model_dump(mode="json"),
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                ).hexdigest(),
                "context_sha256": "f" * 64,
            }
        )
    )

    with pytest.raises(ValueError, match="trusted runner evidence"):
        service.persist_generated_plan_artifact(
            founder(), revision.id, str(uuid.uuid4()), detached_proposal, generated
        )
    assert store.saved == []


def test_generated_plan_review_routes_are_tenant_scoped_and_admin_only(tmp_path):
    store = ArtifactStoreFixture()
    service, _ = service_with_file_database(store, tmp_path / "api-test.db")
    _, _, revision = make_approved_revision(service)
    proposal, generated = generated_runner_result(tmp_path, revision)
    artifact = service.persist_generated_plan_artifact(
        founder(), revision.id, str(uuid.uuid4()), proposal, generated
    )

    app.dependency_overrides[product_service] = lambda: service
    try:
        with TestClient(app) as client:
            detail = client.get(
                f"/api/v1/generated-plan-artifacts/{artifact.id}",
                headers={"Authorization": f"Bearer {issue_local_token('founder')}"},
            )
            assert detail.status_code == 200
            assert detail.json()["manifest_sha256"] == artifact.manifest_sha256
            assert "artifact_key" not in detail.text

            cross_tenant = client.get(
                f"/api/v1/generated-plan-artifacts/{artifact.id}",
                headers={"Authorization": f"Bearer {issue_local_token('other-tenant')}"},
            )
            assert cross_tenant.status_code == 403

            operator_attempt = client.post(
                f"/api/v1/generated-plan-artifacts/{artifact.id}/approve",
                json={"manifest_sha256": artifact.manifest_sha256},
                headers={"Authorization": f"Bearer {issue_local_token('operator')}"},
            )
            assert operator_attempt.status_code == 403

            approved = client.post(
                f"/api/v1/generated-plan-artifacts/{artifact.id}/approve",
                json={"manifest_sha256": artifact.manifest_sha256},
                headers={"Authorization": f"Bearer {issue_local_token('administrator')}"},
            )
            assert approved.status_code == 200
            assert approved.json()["state"] == "APPROVED"
            assert approved.json()["execution"] == "NOT_APPLIED_REVIEW_ONLY"
    finally:
        app.dependency_overrides.pop(product_service, None)
