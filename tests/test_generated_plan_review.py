from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path

import davdeploy.service as service_module
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
from davdeploy.generated_plan_ownership import PlanOwnershipScope
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


def make_submitted_revision(service):
    project = service.create_project(
        founder(), "nova-artifact-project", "https://github.com/example/nova-artifact", "main"
    )
    connection = service.create_cloud_connection(
        founder(), "Verified test account", "aws", "byoc_role_contract"
    )
    connection.account_id = ACCOUNT_ID
    connection.setup_state = "VERIFIED"
    connection.plan_role_arn = f"arn:aws:iam::{ACCOUNT_ID}:role/davdeployPlan-{connection.id}"
    connection.plan_role_setup_state = "VERIFIED"
    connection.external_id_secret_ref = service.connection_secrets.put_external_id(
        founder().organization_id, connection.id, "fixture-nova-plan-external-id"
    )
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
    return project, connection, revision


def make_approved_revision(service):
    project, connection, revision = make_submitted_revision(service)
    approved = service.decide_infrastructure_plan(
        operator(), revision.id, InfrastructurePlanDecision.APPROVED, revision.content_digest
    )
    return project, connection, approved


def generated_runner_result(
    tmp_path, revision, project, *, rationale="Private application storage."
):
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
                rationale=rationale,
            ),
        ),
        requirements=WorkloadRequirements(region="us-east-1"),
    )
    proposal_digest = canonical_json_digest(proposal.model_dump(mode="json"))
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
    ownership_scope = PlanOwnershipScope(
        organization_id=founder().organization_id,
        workspace_id=founder().organization_id,
        project_id=project.id,
        plan_id=revision.infrastructure_plan_id,
        revision_id=revision.id,
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
        ownership_scope_sha256=ownership_scope.scope_sha256(),
        ownership_plan_id_sha256=ownership_scope.plan_id_sha256(),
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


def test_submitted_generated_plan_persists_and_waits_for_cost_evidence(tmp_path):
    store = ArtifactStoreFixture()
    service, db = service_with_artifact_store(store)
    project, _, revision = make_submitted_revision(service)
    proposal, generated = generated_runner_result(
        tmp_path, revision, project, rationale="Stockage privé sécurisé."
    )

    artifact = service.persist_generated_plan_artifact(
        founder(), revision.id, RUN_ID, proposal, generated
    )
    detail = service.generated_plan_artifact_detail(founder(), artifact.id)

    assert detail["state"] == "BLOCKED_NO_REMOTE_STATE"
    assert detail["pricing"] == {
        "status": "UNAVAILABLE",
        "region": "us-east-1",
        "currency": None,
        "monthly_cost": None,
        "reason_code": "regional_pricing_evaluator_not_integrated",
        "evidence_complete": False,
        "message": "Waiting for complete regional cost evidence.",
    }
    assert detail["approval_allowed"] is False
    assert detail["approval_blockers"] == [
        "DURABLE_REMOTE_STATE_UNAVAILABLE",
        "COST_EVIDENCE_INCOMPLETE",
    ]
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
        db.execute(delete(GeneratedPlanArtifact).where(GeneratedPlanArtifact.id == artifact.id))
    db.rollback()

    with pytest.raises(PermissionError, match="administrator role"):
        service.approve_generated_plan_artifact(founder(), artifact.id, artifact.manifest_sha256)

    with pytest.raises(PermissionError, match="administrator role"):
        service.approve_generated_plan_artifact(operator(), artifact.id, artifact.manifest_sha256)

    with pytest.raises(ValueError, match="complete regional cost evidence is unavailable"):
        service.approve_generated_plan_artifact(
            administrator(), artifact.id, artifact.manifest_sha256
        )
    assert (
        db.scalar(
            select(GeneratedPlanApproval.id).where(GeneratedPlanApproval.artifact_id == artifact.id)
        )
        is None
    )
    assert (
        service.infrastructure_plan_revision_detail(founder(), revision.id)["state"] == "SUBMITTED"
    )
    assert store.verified == []


def test_complete_pricing_does_not_unblock_backend_free_plan_approval(tmp_path, monkeypatch):
    store = ArtifactStoreFixture()
    service, _ = service_with_artifact_store(store)
    project, _, revision = make_submitted_revision(service)
    proposal, generated = generated_runner_result(tmp_path, revision, project)

    original_manifest_builder = service_module.generated_plan_manifest

    def manifest_with_complete_pricing(**kwargs):
        manifest = original_manifest_builder(**kwargs)
        manifest["pricing"] = {
            "status": "COMPLETE",
            "region": "us-east-1",
            "currency": "USD",
            "monthly_cost": 12.5,
            "evidence_sha256": "d" * 64,
            "reason_code": None,
        }
        return manifest

    monkeypatch.setattr(service_module, "generated_plan_manifest", manifest_with_complete_pricing)
    artifact = service.persist_generated_plan_artifact(
        founder(), revision.id, RUN_ID, proposal, generated
    )

    detail = service.generated_plan_artifact_detail(founder(), artifact.id)

    assert detail["pricing"]["evidence_complete"] is True
    assert "approval_allowed" not in detail["pricing"]
    assert detail["approval_allowed"] is False
    assert detail["approval_blockers"] == ["DURABLE_REMOTE_STATE_UNAVAILABLE"]
    assert detail["state"] == "BLOCKED_NO_REMOTE_STATE"
    with pytest.raises(ValueError, match="durable remote Terraform state is unavailable"):
        service.approve_generated_plan_artifact(
            administrator(), artifact.id, artifact.manifest_sha256
        )


def test_generated_plan_approval_rejects_manifest_digest_tampering(tmp_path):
    store = ArtifactStoreFixture()
    service, _ = service_with_artifact_store(store)
    project, _, revision = make_submitted_revision(service)
    proposal, generated = generated_runner_result(tmp_path, revision, project)
    artifact = service.persist_generated_plan_artifact(
        founder(), revision.id, RUN_ID, proposal, generated
    )

    with pytest.raises(ValueError, match="digest does not match"):
        service.approve_generated_plan_artifact(administrator(), artifact.id, "0" * 64)

    original_digest = artifact.manifest_sha256
    artifact.manifest["pricing"]["status"] = "COMPLETE"
    with pytest.raises(ValueError, match="manifest failed integrity"):
        service.approve_generated_plan_artifact(administrator(), artifact.id, original_digest)
    assert not service.db.scalar(
        select(GeneratedPlanApproval.id).where(GeneratedPlanApproval.artifact_id == artifact.id)
    )


def test_submitted_generated_plan_rejects_stale_revision(tmp_path):
    store = ArtifactStoreFixture()
    service, _ = service_with_artifact_store(store)
    project, _, revision = make_submitted_revision(service)
    proposal, generated = generated_runner_result(tmp_path, revision, project)

    parent_plan = service._infrastructure_plan(founder(), revision.infrastructure_plan_id)
    service._new_infrastructure_plan_revision(
        parent_plan,
        founder(),
        revision.content,
        revision.revision_number + 1,
    )
    service.db.commit()

    with pytest.raises(ValueError, match="stale because a newer revision exists"):
        service.persist_generated_plan_artifact(
            founder(), revision.id, str(uuid.uuid4()), proposal, generated
        )
    assert store.saved == []


def test_submitted_generated_plan_rejects_customer_revision_tampering(tmp_path):
    store = ArtifactStoreFixture()
    service, _ = service_with_artifact_store(store)
    project, _, revision = make_submitted_revision(service)
    proposal, generated = generated_runner_result(tmp_path, revision, project)
    revision.content = {
        **revision.content,
        "target": {**revision.content["target"], "region": "eu-west-1"},
    }

    with pytest.raises(ValueError, match="revision failed integrity verification"):
        service.persist_generated_plan_artifact(
            founder(), revision.id, str(uuid.uuid4()), proposal, generated
        )
    assert store.saved == []


def test_generated_plan_persistence_rejects_denied_policy_and_wrong_parent_state(tmp_path):
    store = ArtifactStoreFixture()
    service, _ = service_with_artifact_store(store)
    project, _, revision = make_approved_revision(service)
    proposal, generated = generated_runner_result(tmp_path, revision, project)
    denied = GeneratedPlanPolicyResult(PlanPolicyVerdict.DENY, "generated-plan-policy-test", ())
    generated = GeneratedTerraformPlan(**(generated.__dict__ | {"policy": denied}))

    with pytest.raises(ValueError, match="trusted runner evidence"):
        service.persist_generated_plan_artifact(
            founder(), revision.id, str(uuid.uuid4()), proposal, generated
        )
    assert store.saved == []


@pytest.mark.parametrize(
    "scope_change",
    [
        {"workspace_id": "another-workspace"},
        {"project_id": "another-project"},
        {"plan_id": "another-plan"},
        {"revision_id": "another-revision"},
    ],
)
def test_generated_plan_persistence_rejects_cross_scope_ownership(tmp_path, scope_change):
    store = ArtifactStoreFixture()
    service, _ = service_with_artifact_store(store)
    project, _, revision = make_approved_revision(service)
    proposal, generated = generated_runner_result(tmp_path, revision, project)
    scope_values = {
        "organization_id": founder().organization_id,
        "workspace_id": founder().organization_id,
        "project_id": project.id,
        "plan_id": revision.infrastructure_plan_id,
        "revision_id": revision.id,
    }
    scope_values.update(scope_change)
    other_scope = PlanOwnershipScope(**scope_values)
    generated = GeneratedTerraformPlan(
        **(
            generated.__dict__
            | {
                "ownership_scope_sha256": other_scope.scope_sha256(),
                "ownership_plan_id_sha256": other_scope.plan_id_sha256(),
            }
        )
    )

    with pytest.raises(ValueError, match="trusted runner evidence"):
        service.persist_generated_plan_artifact(
            founder(), revision.id, str(uuid.uuid4()), proposal, generated
        )

    assert store.saved == []


def test_generated_plan_policy_rejects_deny_finding_even_with_reviewable_verdict(tmp_path):
    store = ArtifactStoreFixture()
    service, _ = service_with_artifact_store(store)
    project, _, revision = make_approved_revision(service)
    proposal, generated = generated_runner_result(tmp_path, revision, project)
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
    project, _, revision = make_approved_revision(service)
    proposal, generated = generated_runner_result(tmp_path, revision, project)
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
    project, _, revision = make_submitted_revision(service)
    proposal, generated = generated_runner_result(tmp_path, revision, project)
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

            approval_blocked = client.post(
                f"/api/v1/generated-plan-artifacts/{artifact.id}/approve",
                json={"manifest_sha256": artifact.manifest_sha256},
                headers={"Authorization": f"Bearer {issue_local_token('administrator')}"},
            )
            assert approval_blocked.status_code == 409
            assert "complete regional cost evidence is unavailable" in approval_blocked.text
            assert (
                service.infrastructure_plan_revision_detail(founder(), revision.id)["state"]
                == "SUBMITTED"
            )
    finally:
        app.dependency_overrides.pop(product_service, None)
