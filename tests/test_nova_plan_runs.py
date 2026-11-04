from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest
from davdeploy.db import run_migrations
from davdeploy.generated_deployment_contract import (
    GeneratedDeploymentProposal,
    GeneratedResource,
    WorkloadRequirements,
)
from davdeploy.generated_plan_artifacts import canonical_json_digest
from davdeploy.model_gateway import ModelGatewayUnavailable
from davdeploy.models import GeneratedPlanRun, GeneratedPlanRunIdempotencyKey
from davdeploy.nova_plan_dispatch import NovaPlanDispatchError
from davdeploy.security import Principal
from davdeploy.service import ProductService, plan_hash
from davdeploy.terraform_generation import generation_context_digest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from test_generated_plan_review import make_submitted_revision
from test_product import founder, make_service

PROJECT = "davdeploy-nova-plan-only"


class StaticGenerator:
    model_id = "fixture-nova-model"

    def __init__(self):
        self.calls = 0

    def generate(self, *, approved_plan, tenant, source_revision):
        del tenant
        self.calls += 1
        proposal = GeneratedDeploymentProposal(
            contract_version="1.0",
            source_revision=source_revision,
            context_digest=generation_context_digest(approved_plan, source_revision),
            resources=(
                GeneratedResource(
                    resource_id="app-storage",
                    resource_type="aws_s3_bucket",
                    name="app_data",
                    arguments={"bucket_prefix": "davdeploy-plan-test"},
                    rationale="Private application storage.",
                ),
            ),
            requirements=WorkloadRequirements(region=approved_plan["target"]["region"]),
        )
        return SimpleNamespace(
            proposal=proposal,
            response=SimpleNamespace(
                request=SimpleNamespace(
                    request_id="fixture-request",
                    provider="bedrock",
                    model=self.model_id,
                    prompt_version="fixture-v1",
                ),
                usage=None,
            ),
        )


class FakeDispatcher:
    project_name = PROJECT

    def __init__(self, status="IN_PROGRESS"):
        self.status = status
        self.staged = []
        self.started = []

    @staticmethod
    def input_key(run_id):
        return f"plans/nova-generated/requests/{run_id}/input.json"

    @staticmethod
    def result_key(run_id):
        return f"plans/nova-generated/requests/{run_id}/result.json"

    def stage_input(self, run_id, document):
        key = self.input_key(run_id)
        digest = canonical_json_digest(document)
        version = "fixture-input-version"
        self.staged.append((run_id, document, key, digest, version))
        return key, digest, version

    def start_build(self, run_id):
        from davdeploy.nova_plan_dispatch import NovaPlanBuild

        build = NovaPlanBuild(f"{PROJECT}:{run_id}", PROJECT, "IN_PROGRESS")
        self.started.append((run_id, build))
        return build

    def describe_build(self, build_id):
        from davdeploy.nova_plan_dispatch import NovaPlanBuild

        return NovaPlanBuild(build_id, PROJECT, self.status)


def service_with_dispatcher(status="IN_PROGRESS"):
    generator = StaticGenerator()
    service, db = make_service(terraform_generator=generator)
    dispatcher = FakeDispatcher(status=status)
    service.nova_plan_dispatcher = dispatcher
    return service, db, generator, dispatcher


def test_submitted_revision_is_queued_idempotently_then_dispatched_once_by_worker():
    service, db, generator, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    key = "nova-plan-request-fixture-0001"
    wakes = []
    service._wake_worker = lambda kind, job_id: wakes.append((kind, job_id))

    first = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, key
    )
    second = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, key
    )
    duplicate_with_new_key = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-request-alternate-0001"
    )

    assert first["id"] == second["id"]
    assert first["id"] == duplicate_with_new_key["id"]
    bindings = db.query(GeneratedPlanRunIdempotencyKey).all()
    assert len(bindings) == 2
    assert {binding.idempotency_key_sha256 for binding in bindings} == {
        hashlib.sha256(key.encode("utf-8")).hexdigest(),
        hashlib.sha256(b"nova-plan-request-alternate-0001").hexdigest(),
    }
    assert all(binding.organization_id == founder().organization_id for binding in bindings)
    assert all(binding.run_id == first["id"] for binding in bindings)
    assert all(binding.request_sha256 for binding in bindings)
    assert first["state"] == "QUEUED"
    assert first["proposal_sha256"] is None
    assert "cannot apply or destroy" in first["execution_boundary"]
    assert generator.calls == 0
    assert dispatcher.staged == dispatcher.started == []
    assert len(wakes) == 3
    assert all(kind == "generated_plan_run" and job_id == first["id"] for kind, job_id in wakes)

    assert service.run_next_generated_plan_run() is True
    assert service.run_next_generated_plan_run() is False
    completed_dispatch = service.generated_plan_run_detail(founder(), first["id"])
    assert completed_dispatch["state"] == "BUILD_STARTED"
    assert completed_dispatch["proposal_sha256"]
    assert generator.calls == 1
    assert len(dispatcher.staged) == len(dispatcher.started) == 1
    run_id, document, input_key, input_sha, input_version = dispatcher.staged[0]
    assert input_key == dispatcher.input_key(run_id)
    assert document["run_id"] == run_id
    assert document["revision_id"] == revision.id
    assert document["revision_sha256"] == revision.content_digest
    assert document["proposal_sha256"] == completed_dispatch["proposal_sha256"]
    assert document["ownership_scope"]["revision_id"] == revision.id
    assert input_sha
    assert input_version == "fixture-input-version"
    db.close()


def test_reused_idempotency_key_with_different_revision_is_rejected():
    service, db, _, _ = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    key = "nova-plan-request-fixture-0002"
    alternate_key = "nova-plan-request-alternate-0002"

    service.request_generated_plan_run(founder(), revision.id, revision.content_digest, key)
    service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, alternate_key
    )
    existing_run = db.query(GeneratedPlanRun).one()
    bindings = db.query(GeneratedPlanRunIdempotencyKey).all()
    assert len(bindings) == 2
    assert any(
        binding.idempotency_key_sha256
        == hashlib.sha256(alternate_key.encode("utf-8")).hexdigest()
        and binding.run_id == existing_run.id
        and binding.request_sha256 == existing_run.request_sha256
        for binding in bindings
    )
    second = service.create_customer_plan_review(
        founder(), revision.content["source_deployment_plan_id"]
    )
    second.content["target"]["account_id"] = revision.content["target"]["account_id"]
    second.content["target"]["region"] = "eu-west-1"
    second.content_digest = plan_hash(second.content)
    db.commit()
    service.submit_infrastructure_plan(founder(), second.id)

    with pytest.raises(ValueError, match="Idempotency-Key was already used"):
        service.request_generated_plan_run(
            founder(), second.id, second.content_digest, alternate_key
        )
    db.close()


def test_successful_codebuild_is_not_promoted_to_a_verified_plan():
    service, db, _, _ = service_with_dispatcher(status="SUCCEEDED")
    _, _, revision = make_submitted_revision(service)

    run = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-request-fixture-0003"
    )
    assert run["state"] == "QUEUED"
    assert service.run_next_generated_plan_run() is True
    assert service.reconcile_generated_plan_build(f"{PROJECT}:{run['id']}") is True
    updated = service.generated_plan_run_detail(founder(), run["id"])

    assert updated["state"] == "BUILD_SUCCEEDED_UNVERIFIED"
    assert updated["error_code"] == "PLAN_RESULT_NOT_VERIFIED"
    assert "no Terraform plan is available" in updated["error_summary"]
    db.close()


def test_generation_failure_is_recorded_by_the_worker_without_starting_codebuild():
    service, db, _, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)

    class FailingGenerator(StaticGenerator):
        def generate(self, **_kwargs):
            self.calls += 1
            raise ModelGatewayUnavailable("fixture Bedrock outage")

    service.terraform_generator = FailingGenerator()
    # Keep the queued request bound to the same configured model as the fixture generator.
    run = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-request-fixture-0005"
    )
    assert run["state"] == "QUEUED"
    assert service.run_next_generated_plan_run() is True
    failed = service.generated_plan_run_detail(founder(), run["id"])

    assert failed["state"] == "FAILED"
    assert failed["error_code"] == "NOVA_GENERATION_UNAVAILABLE"
    assert dispatcher.started == []
    db.close()


def test_uncertain_build_start_requires_reconciliation_without_retrying():
    service, db, _, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    original_start = dispatcher.start_build

    def uncertain_start(run_id):
        dispatcher.started.append((run_id, "uncertain"))
        raise NovaPlanDispatchError("start result unknown", outcome_uncertain=True)

    dispatcher.start_build = uncertain_start
    run = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-request-fixture-0006"
    )

    assert service.run_next_generated_plan_run() is True
    uncertain = service.generated_plan_run_detail(founder(), run["id"])
    assert uncertain["state"] == "RECONCILIATION_REQUIRED"
    assert uncertain["error_code"] == "DISPATCH_UNCERTAIN"
    assert uncertain["finished_at"] is None
    assert service.run_next_generated_plan_run() is False
    assert len(dispatcher.started) == 1
    dispatcher.start_build = original_start
    db.close()


def test_concurrent_worker_wakeups_claim_a_queued_run_once(tmp_path):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'nova-plan-claims.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    run_migrations(engine)
    run_id = str(uuid.uuid4())
    with Session(engine) as seed_db:
        seed_db.add(
            GeneratedPlanRun(
                id=run_id,
                organization_id="org-demo",
                project_id="project-demo",
                revision_id="revision-demo",
                requester_subject="founder-demo",
                idempotency_key_sha256="a" * 64,
                request_sha256="b" * 64,
                revision_sha256="c" * 64,
                state="QUEUED",
                codebuild_project=PROJECT,
                input_key=f"plans/nova-generated/requests/{run_id}/input.json",
                result_key=f"plans/nova-generated/requests/{run_id}/result.json",
            )
        )
        seed_db.commit()

    start = Barrier(2)

    def claim():
        with Session(engine) as claim_db:
            service = ProductService(claim_db)
            start.wait(timeout=5)
            return service._claim_next_generated_plan_run()

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _index: claim(), range(2)))

    assert sum(claim is not None for claim in claims) == 1
    with Session(engine) as verify_db:
        saved = verify_db.get(GeneratedPlanRun, run_id)
        assert saved is not None
        assert saved.state == "PREPARING"
        assert saved.preparation_lease_token
        assert saved.preparation_lease_expires_at
    engine.dispose()


def test_expired_preparation_lease_is_reconciled_without_restarting_generation():
    from datetime import UTC, datetime, timedelta

    service, db, generator, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    run = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-request-fixture-0007"
    )
    saved = db.get(GeneratedPlanRun, run["id"])
    assert saved is not None
    saved.state = "PREPARING"
    saved.preparation_lease_token = "expired-worker-lease"
    saved.preparation_lease_expires_at = datetime.now(UTC) - timedelta(seconds=5)
    db.commit()

    assert service.run_next_generated_plan_run() is False
    reconciled = service.generated_plan_run_detail(founder(), run["id"])
    assert reconciled["state"] == "RECONCILIATION_REQUIRED"
    assert reconciled["error_code"] == "PREPARATION_LEASE_EXPIRED"
    assert generator.calls == 0
    assert dispatcher.started == []
    db.close()


def test_plan_run_is_not_visible_across_organizations():
    service, db, _, _ = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    run = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-request-fixture-0004"
    )

    with pytest.raises(PermissionError, match="not found in this organization"):
        service.generated_plan_run_detail(
            Principal("other-user", "other-organization", "administrator"), run["id"]
        )
    db.close()
