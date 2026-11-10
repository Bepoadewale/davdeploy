from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from types import SimpleNamespace

import pytest
from botocore.exceptions import BotoCoreError, ClientError
from davdeploy.db import run_migrations
from davdeploy.domain import GeneratedPlanGenerationReconciliationRequest
from davdeploy.generated_deployment_contract import (
    GeneratedDeploymentProposal,
    GeneratedResource,
    WorkloadRequirements,
)
from davdeploy.generated_plan_artifacts import canonical_json_digest
from davdeploy.model_gateway import ModelGatewayUnavailable
from davdeploy.models import GeneratedPlanArtifact, GeneratedPlanRun, GeneratedPlanRunIdempotencyKey
from davdeploy.nova_plan_dispatch import NovaPlanBuild, NovaPlanDispatchError
from davdeploy.security import Principal
from davdeploy.service import ProductService, plan_hash
from davdeploy.terraform_generation import generation_context_digest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
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
        self.lookups = []
        self.lookup_result = None
        self.build_run_ids = {}
        self.build_staged = []

    @staticmethod
    def input_key(run_id):
        return f"plans/nova-generated/requests/{run_id}/input.json"

    @staticmethod
    def result_key(run_id):
        return f"plans/nova-generated/requests/{run_id}/result.json"

    @staticmethod
    def build_arn(run_id):
        return FakeDispatcher.build_arn_for_id(f"{PROJECT}:{run_id}")

    @staticmethod
    def build_arn_for_id(build_id):
        return f"arn:aws:codebuild:us-east-1:654654474502:build/{build_id}"

    @staticmethod
    def build_input_key(build_arn):
        return f"plans/nova-generated/builds/{build_arn}/input.json"

    @staticmethod
    def build_result_key(build_arn):
        return f"plans/nova-generated/builds/{build_arn}/result.json"

    def stage_input(self, run_id, document):
        key = self.input_key(run_id)
        digest = canonical_json_digest(document)
        version = "fixture-input-version"
        self.staged.append((run_id, document, key, digest, version))
        return key, digest, version

    def inspect_staged_input(self, run_id, key, digest):
        if key == self.input_key(run_id):
            matches = [item for item in self.staged if item[2] == key and item[3] == digest]
        else:
            matches = [item for item in self.build_staged if item[2] == key and item[3] == digest]
        if key != self.input_key(run_id) and not key.startswith(
            "plans/nova-generated/builds/"
        ):
            raise NovaPlanDispatchError(
                "fixture input key mismatch", outcome_uncertain=True, phase="input_stage"
            )
        return matches[0][4] if matches else None

    def read_staged_input_document(self, run_id, key, version_id, expected_sha256):
        del run_id
        for item in [*self.staged, *self.build_staged]:
            if item[2] == key and item[3] == expected_sha256 and item[4] == version_id:
                return item[1]
        raise NovaPlanDispatchError("fixture input version is unavailable", outcome_uncertain=True)

    def stage_build_input(self, run_id, build_arn, document):
        key = self.build_input_key(build_arn)
        digest = canonical_json_digest(document)
        version = "fixture-build-input-version"
        self.build_staged.append((run_id, document, key, digest, version))
        return key, digest, version

    def start_build(self, run_id, idempotency_token):
        from davdeploy.nova_plan_dispatch import NovaPlanBuild

        build = NovaPlanBuild(
            f"{PROJECT}:{run_id}",
            PROJECT,
            "IN_PROGRESS",
            run_id,
            self.build_arn(run_id),
        )
        self.started.append((run_id, idempotency_token, build))
        self.build_run_ids[build.build_id] = run_id
        return build

    def find_build_by_run_id(self, run_id):
        self.lookups.append(run_id)
        return self.lookup_result

    def describe_build(self, build_id):
        from davdeploy.nova_plan_dispatch import NovaPlanBuild

        run_id = self.build_run_ids.get(build_id)
        return NovaPlanBuild(
            build_id,
            PROJECT,
            self.status,
            run_id,
            self.build_arn_for_id(build_id) if run_id else None,
        )

    def read_result(self, _run_id, _key, _build_id):
        raise NovaPlanDispatchError("fixture has no immutable result envelope")


def service_with_dispatcher(status="IN_PROGRESS"):
    generator = StaticGenerator()
    service, db = make_service(terraform_generator=generator)
    dispatcher = FakeDispatcher(status=status)
    service.nova_plan_dispatcher = dispatcher
    return service, db, generator, dispatcher


def test_generation_abandon_requires_explicit_true_confirmation():
    with pytest.raises(ValidationError):
        GeneratedPlanGenerationReconciliationRequest(abandon_attempt=False)

    request = GeneratedPlanGenerationReconciliationRequest(abandon_attempt=True)
    assert request.abandon_attempt is True


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
    assert dispatcher.started[0][1] == db.get(GeneratedPlanRun, first["id"]).codebuild_idempotency_token
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

    assert updated["state"] == "RECONCILIATION_REQUIRED"
    assert updated["error_code"] == "PLAN_RESULT_RECONCILIATION_REQUIRED"
    assert updated["artifact_id"] is None
    assert "No plan is approvable" in updated["error_summary"]
    db.close()


def test_transient_result_read_can_be_reconciled_and_returns_review_artifact():
    service, db, _, dispatcher = service_with_dispatcher(status="SUCCEEDED")
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-result-retry-fixture-0001"
    )
    assert service.run_next_generated_plan_run() is True
    run = db.get(GeneratedPlanRun, request["id"])
    assert run and run.codebuild_build_id and run.result_key

    result = {
        "manifest": {
            "artifact": {
                "bucket": "plan-artifacts",
                "key": "plans/review/saved.tfplan",
                "version_id": "saved-plan-version",
            },
            "digests": {"saved_plan_sha256": "d" * 64},
        },
        "manifest_sha256": "e" * 64,
    }
    read_attempts = []

    def transient_then_successful_read(_run_id, _key, _build_id, _build_arn):
        read_attempts.append(True)
        if len(read_attempts) == 1:
            raise NovaPlanDispatchError(
                "fixture result read temporarily unavailable", outcome_uncertain=True
            )
        return result, "result-version", "f" * 64

    dispatcher.read_result = transient_then_successful_read
    service._persist_verified_nova_plan_result = lambda *_args: SimpleNamespace(
        id="artifact-review-123"
    )

    assert service.reconcile_generated_plan_build(run.codebuild_build_id) is True
    uncertain = service.generated_plan_run_detail(founder(), request["id"])
    assert uncertain["state"] == "RECONCILIATION_REQUIRED"
    assert uncertain["error_code"] == "PLAN_RESULT_RECONCILIATION_REQUIRED"
    assert uncertain["artifact_id"] is None

    recovered = service.reconcile_generated_plan_build_attempt(founder(), request["id"])
    assert recovered["state"] == "PLAN_READY_REVIEW_ONLY"
    assert recovered["artifact_id"] == "artifact-review-123"
    assert len(read_attempts) == 2
    db.close()


def test_saved_plan_verification_error_enters_reconciliation_state():
    from davdeploy.generated_plan_artifacts import GeneratedPlanArtifactError

    service, db, _, dispatcher = service_with_dispatcher(status="SUCCEEDED")
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-artifact-error-reconcile-0001"
    )
    assert service.run_next_generated_plan_run() is True
    run = db.get(GeneratedPlanRun, request["id"])
    assert run and run.codebuild_build_id and run.result_key
    dispatcher.read_result = lambda *_args: (
        {
            "manifest": {
                "artifact": {
                    "bucket": "plan-artifacts",
                    "key": "plans/review/saved.tfplan",
                    "version_id": "saved-plan-version",
                },
                "digests": {"saved_plan_sha256": "d" * 64},
            },
            "manifest_sha256": "e" * 64,
        },
        "result-version",
        "f" * 64,
    )

    def fail_artifact_verification(*_args):
        raise GeneratedPlanArtifactError("fixture saved-plan verification failed")

    service._persist_verified_nova_plan_result = fail_artifact_verification

    assert service.reconcile_generated_plan_build(run.codebuild_build_id) is True
    updated = service.generated_plan_run_detail(founder(), request["id"])
    assert updated["state"] == "RECONCILIATION_REQUIRED"
    assert updated["error_code"] == "PLAN_RESULT_RECONCILIATION_REQUIRED"
    assert "No plan is approvable" in updated["error_summary"]
    db.close()


@pytest.mark.parametrize(
    "aws_error",
    [
        BotoCoreError(error_message="fixture Secrets Manager transport failure"),
        ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": "fixture unavailable"}},
            "GetSecretValue",
        ),
    ],
)
def test_secrets_manager_read_errors_leave_build_recoverable(aws_error):
    service, db, _, dispatcher = service_with_dispatcher(status="SUCCEEDED")
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-secret-read-reconcile-0001"
    )
    assert service.run_next_generated_plan_run() is True
    run = db.get(GeneratedPlanRun, request["id"])
    assert run and run.codebuild_build_id
    dispatcher.read_result = lambda *_args: ({}, "result-version", "f" * 64)

    def secret_store_failure(*_args):
        raise aws_error

    service._persist_verified_nova_plan_result = secret_store_failure

    assert service.reconcile_generated_plan_build(run.codebuild_build_id) is True
    updated = service.generated_plan_run_detail(founder(), request["id"])
    assert updated["state"] == "RECONCILIATION_REQUIRED"
    assert updated["error_code"] == "PLAN_RESULT_RECONCILIATION_REQUIRED"
    assert "No plan is approvable" in updated["error_summary"]
    db.close()


def test_unconfirmed_codebuild_status_can_be_retried_for_exact_bound_build():
    service, db, _, dispatcher = service_with_dispatcher(status="SUCCEEDED")
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-status-retry-0001"
    )
    assert service.run_next_generated_plan_run() is True
    run = db.get(GeneratedPlanRun, request["id"])
    build_id = run.codebuild_build_id

    def temporary_failure(_build_id):
        raise NovaPlanDispatchError("temporary CodeBuild API timeout", outcome_uncertain=True)

    dispatcher.describe_build = temporary_failure
    assert service.reconcile_generated_plan_build(build_id) is True
    failed_lookup = service.generated_plan_run_detail(founder(), request["id"])
    assert failed_lookup["state"] == "RECONCILIATION_REQUIRED"
    assert failed_lookup["error_code"] == "BUILD_STATUS_UNCONFIRMED"

    dispatcher.describe_build = lambda exact_id: NovaPlanBuild(
        exact_id,
        PROJECT,
        "SUCCEEDED",
        run.runner_run_id,
        FakeDispatcher.build_arn_for_id(exact_id),
    )
    recovered = service.reconcile_generated_plan_build_attempt(founder(), request["id"])
    assert recovered["state"] == "RECONCILIATION_REQUIRED"
    assert recovered["error_code"] == "PLAN_RESULT_RECONCILIATION_REQUIRED"
    db.close()


def test_disabled_runner_status_reconciliation_is_recoverable_after_reenable(monkeypatch):
    service, db, _, dispatcher = service_with_dispatcher(status="SUCCEEDED")
    db.autoflush = False
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-disabled-runner-retry-0001"
    )
    assert service.run_next_generated_plan_run() is True
    run = db.get(GeneratedPlanRun, request["id"])
    db.refresh(run)
    assert run.preparation_phase is None
    build_id = run.codebuild_build_id
    run.preparation_phase = "STARTING_BUILD"
    run.error_code = "BUILD_START_RECONCILIATION_REQUIRED"
    db.commit()
    service.nova_plan_dispatcher = None
    monkeypatch.setattr(
        "davdeploy.service.NovaPlanOnlyDispatcher.from_environment",
        classmethod(lambda _cls: None),
    )

    assert service.reconcile_generated_plan_build(build_id) is True
    unavailable = service.generated_plan_run_detail(founder(), request["id"])
    assert unavailable["state"] == "RECONCILIATION_REQUIRED"
    assert unavailable["error_code"] == "BUILD_STATUS_UNCONFIRMED"

    service.nova_plan_dispatcher = dispatcher
    recovered = service.reconcile_generated_plan_build_attempt(founder(), request["id"])
    assert recovered["state"] == "RECONCILIATION_REQUIRED"
    assert recovered["error_code"] == "PLAN_RESULT_RECONCILIATION_REQUIRED"
    db.close()


def test_late_start_response_cannot_bind_old_build_to_new_runner_attempt():
    service, db, _, _dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-late-build-id-race-0001"
    )
    claimed = service._claim_next_generated_plan_run()
    assert claimed is not None
    run, lease_token = claimed
    original_runner_id = run.runner_run_id
    original_token = run.codebuild_idempotency_token
    run.proposal_sha256 = "a" * 64
    run.input_sha256 = "b" * 64
    run.input_version_id = "fixture-input-version"
    run.preparation_phase = "STARTING_BUILD"
    run.preparation_lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert service._expire_generated_plan_run_lease(run, datetime.now(UTC)) is True

    run = db.get(GeneratedPlanRun, request["id"])
    run.runner_run_id = "nova-plan-new-runner-attempt-0001"
    run.codebuild_idempotency_token = run.runner_run_id
    run.input_key = f"plans/nova-generated/requests/{run.runner_run_id}/input.json"
    run.result_key = f"plans/nova-generated/requests/{run.runner_run_id}/result.json"
    run.input_sha256 = None
    run.input_version_id = None
    run.proposal_sha256 = None
    run.state = "RECONCILIATION_REQUIRED"
    run.error_code = "BUILD_START_RECONCILIATION_REQUIRED"
    run.preparation_phase = "STARTING_BUILD"
    db.commit()

    bound = service._finish_generated_plan_run_claim(
        run,
        lease_token,
        state="RECONCILIATION_REQUIRED",
        error_code="BUILD_START_RECONCILIATION_REQUIRED",
        error_summary="Late response from the old runner attempt.",
        action="generated_plan_run.build_start_uncertain",
        codebuild_build_id=f"{PROJECT}:{original_runner_id}",
        expected_runner_run_id=original_runner_id,
        expected_idempotency_token=original_token,
    )

    db.refresh(run)
    assert bound is False
    assert run.runner_run_id == "nova-plan-new-runner-attempt-0001"
    assert run.codebuild_build_id is None
    assert run.codebuild_idempotency_token == run.runner_run_id
    db.close()


def test_old_build_completion_cannot_overwrite_a_new_queued_attempt():
    service, db, _, dispatcher = service_with_dispatcher(status="FAILED")
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-old-build-race-0001"
    )
    assert service.run_next_generated_plan_run() is True
    run = db.get(GeneratedPlanRun, request["id"])
    old_build_id = run.codebuild_build_id

    def finish_after_retry(exact_build_id):
        assert exact_build_id == old_build_id
        run.state = "QUEUED"
        run.codebuild_build_id = None
        run.runner_run_id = "new-runner-attempt-after-retry"
        run.error_code = None
        run.error_summary = None
        db.commit()
        from davdeploy.nova_plan_dispatch import NovaPlanBuild

        return NovaPlanBuild(exact_build_id, PROJECT, "FAILED")

    dispatcher.describe_build = finish_after_retry
    assert service.reconcile_generated_plan_build(old_build_id) is True
    db.refresh(run)
    assert run.state == "QUEUED"
    assert run.codebuild_build_id is None
    assert run.runner_run_id == "new-runner-attempt-after-retry"
    db.close()


def test_late_transient_status_error_cannot_overwrite_terminal_completion():
    service, db, _, dispatcher = service_with_dispatcher(status="SUCCEEDED")
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-status-race-0001"
    )
    assert service.run_next_generated_plan_run() is True
    run = db.get(GeneratedPlanRun, request["id"])
    build_id = run.codebuild_build_id

    def transient_error_after_completion(_build_id):
        run.state = "BUILD_SUCCEEDED_UNVERIFIED"
        run.error_code = "PLAN_RESULT_NOT_VERIFIED"
        run.error_summary = "The build finished, but its result remains unverified."
        db.commit()
        raise NovaPlanDispatchError("late transient status lookup error", outcome_uncertain=True)

    dispatcher.describe_build = transient_error_after_completion
    assert service.reconcile_generated_plan_build(build_id) is True
    db.refresh(run)
    assert run.state == "BUILD_SUCCEEDED_UNVERIFIED"
    assert run.error_code == "PLAN_RESULT_NOT_VERIFIED"
    db.close()


def test_generation_failure_is_recorded_by_the_worker_without_starting_codebuild():
    service, db, _, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    wakes = []
    service._wake_worker = lambda kind, job_id: wakes.append((kind, job_id))

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

    # The original request key remains replay-only after failure.
    replayed = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-request-fixture-0005"
    )
    assert replayed["id"] == run["id"]
    assert replayed["state"] == "FAILED"
    assert len(wakes) == 1

    retry_key = "nova-plan-request-retry-fixture-0005"
    service.terraform_generator = StaticGenerator()
    retried = service.retry_generated_plan_run(founder(), run["id"], retry_key)
    assert retried["id"] == run["id"]
    assert retried["state"] == "QUEUED"
    assert wakes[-1] == ("generated_plan_run", run["id"])
    assert service.run_next_generated_plan_run() is True
    started = service.generated_plan_run_detail(founder(), run["id"])
    assert started["state"] == "BUILD_STARTED"
    assert len(dispatcher.started) == 1

    # A network replay of the explicit retry key does not create another attempt.
    retry_replay = service.retry_generated_plan_run(founder(), run["id"], retry_key)
    assert retry_replay["state"] == "BUILD_STARTED"
    assert len(dispatcher.started) == 1
    retry_binding = db.query(GeneratedPlanRunIdempotencyKey).filter_by(
        idempotency_key_sha256=hashlib.sha256(retry_key.encode()).hexdigest()
    ).one()
    assert retry_binding.run_id == run["id"]
    db.close()


def test_lost_generation_response_stays_blocked_until_explicit_abandon():
    service, db, _, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None

    class UncertainOnceGenerator(StaticGenerator):
        def generate(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise ModelGatewayUnavailable(
                    "fixture response lost after Bedrock accepted request",
                    outcome_uncertain=True,
                )
            self.calls -= 1
            return super().generate(**kwargs)

    generator = UncertainOnceGenerator()
    service.terraform_generator = generator
    run = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-generation-timeout-0001"
    )

    assert service.run_next_generated_plan_run() is True
    uncertain = service.generated_plan_run_detail(founder(), run["id"])
    assert uncertain["state"] == "RECONCILIATION_REQUIRED"
    assert uncertain["error_code"] == "PROPOSAL_GENERATION_RECONCILIATION_REQUIRED"
    assert "reconcile-generation" in uncertain["error_summary"]
    assert dispatcher.started == []
    with pytest.raises(ValueError, match="confirmed failed"):
        service.retry_generated_plan_run(
            founder(), run["id"], "nova-plan-generation-timeout-no-retry-0001"
        )

    abandoned = service.abandon_generated_plan_generation_attempt(founder(), run["id"])
    assert abandoned["state"] == "FAILED"
    assert abandoned["error_code"] == "GENERATION_ATTEMPT_ABANDONED"
    retry = service.retry_generated_plan_run(
        founder(), run["id"], "nova-plan-generation-timeout-explicit-retry-0001"
    )
    assert retry["state"] == "QUEUED"
    assert service.run_next_generated_plan_run() is True
    assert service.generated_plan_run_detail(founder(), run["id"])["state"] == "BUILD_STARTED"
    assert generator.calls == 2
    assert len(dispatcher.started) == 1
    db.close()


def test_retry_after_input_staging_uses_a_new_durable_runner_key(monkeypatch):
    service, db, _, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    first_runner_id = None
    original_start = dispatcher.start_build

    def reject_first_start(run_id, idempotency_token):
        nonlocal first_runner_id
        if first_runner_id is None:
            first_runner_id = run_id
            raise NovaPlanDispatchError("fixture rejected the first known build start")
        return original_start(run_id, idempotency_token)

    dispatcher.start_build = reject_first_start
    request_key = "nova-plan-request-staged-retry-0001"
    run = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, request_key
    )
    assert service.run_next_generated_plan_run() is True
    failed = db.get(GeneratedPlanRun, run["id"])
    assert failed.state == "FAILED"
    assert failed.input_sha256
    assert failed.input_version_id == "fixture-input-version"
    assert failed.runner_run_id == run["id"] == first_runner_id
    first_input_key = failed.input_key

    retry_key = "nova-plan-request-staged-retry-0002"
    retried = service.retry_generated_plan_run(founder(), run["id"], retry_key)
    queued = db.get(GeneratedPlanRun, run["id"])
    assert retried["state"] == "QUEUED"
    assert queued.runner_run_id != first_runner_id
    assert queued.input_key != first_input_key
    assert queued.input_key == dispatcher.input_key(queued.runner_run_id)
    assert queued.result_key == dispatcher.result_key(queued.runner_run_id)
    assert queued.input_sha256 is None
    assert queued.input_version_id is None

    assert service.run_next_generated_plan_run() is True
    started = service.generated_plan_run_detail(founder(), run["id"])
    assert started["state"] == "BUILD_STARTED"
    assert len(dispatcher.staged) == 2
    first_stage, retry_stage = dispatcher.staged
    assert first_stage[0] == first_runner_id
    assert retry_stage[0] == queued.runner_run_id
    assert first_stage[2] != retry_stage[2]
    assert retry_stage[1]["run_id"] == queued.runner_run_id
    assert retry_stage[1]["control_plane_run_id"] == run["id"]
    assert dispatcher.started[-1][0] == queued.runner_run_id
    assert db.get(GeneratedPlanRun, run["id"]).input_key == dispatcher.build_input_key(
        dispatcher.build_arn(queued.runner_run_id)
    )
    assert retry_stage[2] == dispatcher.input_key(queued.runner_run_id)

    queued = db.get(GeneratedPlanRun, run["id"])
    assert queued.runner_run_id != queued.id
    manifest = {}
    retry_result = {
        "contract": "davdeploy.nova-plan-result.v1",
        "run_id": queued.runner_run_id,
        "codebuild_project": queued.codebuild_project,
        "codebuild_build_id": queued.codebuild_build_id,
        "codebuild_build_arn": queued.result_metadata["codebuild_build_arn"],
        "input": {},
        "binding": {},
        "policy_evidence": {},
        "policy_sha256": "f" * 64,
        "manifest": manifest,
        "manifest_sha256": canonical_json_digest(manifest),
        "planning_boundary": "INITIAL_PLAN_NO_REMOTE_STATE",
    }

    class ReachedDurableRevisionValidation(Exception):
        pass

    def stop_after_attempt_binding(*_args):
        raise ReachedDurableRevisionValidation

    monkeypatch.setattr(service, "_infrastructure_revision", stop_after_attempt_binding)
    remote_retry_result = {
        **retry_result,
        "planning_boundary": "TENANT_ISOLATED_HTTP_STATE",
        "remote_state": {
            "state_id": "12345678-1234-4234-8234-123456789012",
            "scope_sha256": "c" * 64,
        },
    }
    with pytest.raises(ReachedDurableRevisionValidation):
        service._persist_verified_nova_plan_result(
            queued, dispatcher, remote_retry_result, "result-version", "e" * 64
        )
    with pytest.raises(ReachedDurableRevisionValidation):
        service._persist_verified_nova_plan_result(
            queued, dispatcher, retry_result, "result-version", "e" * 64
        )

    retry_result["run_id"] = queued.id
    with pytest.raises(ValueError, match="exact durable CodeBuild run"):
        service._persist_verified_nova_plan_result(
            queued, dispatcher, retry_result, "result-version", "e" * 64
        )
    db.close()


def test_uncertain_build_start_requires_reconciliation_without_retrying():
    service, db, _, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    original_start = dispatcher.start_build

    def uncertain_start(run_id, _idempotency_token):
        dispatcher.started.append((run_id, "uncertain"))
        raise NovaPlanDispatchError(
            "start result unknown", outcome_uncertain=True, phase="build_start"
        )

    dispatcher.start_build = uncertain_start
    run = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-request-fixture-0006"
    )

    assert service.run_next_generated_plan_run() is True
    uncertain = service.generated_plan_run_detail(founder(), run["id"])
    assert uncertain["state"] == "RECONCILIATION_REQUIRED"
    assert uncertain["error_code"] == "BUILD_START_RECONCILIATION_REQUIRED"
    assert uncertain["finished_at"] is None
    with pytest.raises(ValueError, match="confirmed failed"):
        service.retry_generated_plan_run(
            founder(), run["id"], "nova-plan-request-retry-uncertain-0006"
        )
    assert service.run_next_generated_plan_run() is False
    assert len(dispatcher.started) == 1
    dispatcher.start_build = original_start
    db.close()


def test_uncertain_input_stage_requires_reconciliation_without_retrying():
    service, db, generator, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    original_stage = dispatcher.stage_input

    def stage_then_lose_confirmation(run_id, document):
        original_stage(run_id, document)
        raise NovaPlanDispatchError(
            "fixture lost input-stage confirmation",
            outcome_uncertain=True,
            phase="input_stage",
        )

    dispatcher.stage_input = stage_then_lose_confirmation
    run = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-request-stage-uncertain-0001"
    )

    assert service.run_next_generated_plan_run() is True
    uncertain = service.generated_plan_run_detail(founder(), run["id"])
    assert uncertain["state"] == "RECONCILIATION_REQUIRED"
    assert uncertain["error_code"] == "INPUT_STAGE_RECONCILIATION_REQUIRED"
    stored = db.get(GeneratedPlanRun, run["id"])
    assert stored.input_sha256
    assert stored.proposal_sha256
    assert stored.input_version_id is None
    with pytest.raises(ValueError, match="confirmed failed"):
        service.retry_generated_plan_run(
            founder(), run["id"], "nova-plan-request-retry-stage-uncertain-0001"
        )
    assert dispatcher.started == []

    reconciled = service.reconcile_generated_plan_input(founder(), run["id"])
    assert reconciled["state"] == "QUEUED"
    assert db.get(GeneratedPlanRun, run["id"]).input_version_id == "fixture-input-version"
    assert service.run_next_generated_plan_run() is True
    resumed = service.generated_plan_run_detail(founder(), run["id"])
    assert resumed["state"] == "BUILD_STARTED"
    assert generator.calls == 1
    assert len(dispatcher.staged) == 1
    assert len(dispatcher.started) == 1
    db.close()


def test_input_stage_reconciliation_can_abandon_mismatch_then_retry_fresh_key():
    service, db, _, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    original_stage = dispatcher.stage_input

    def stage_then_lose_confirmation(run_id, document):
        original_stage(run_id, document)
        raise NovaPlanDispatchError(
            "fixture lost input-stage confirmation",
            outcome_uncertain=True,
            phase="input_stage",
        )

    dispatcher.stage_input = stage_then_lose_confirmation
    run = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-request-stage-abandon-001"
    )
    assert service.run_next_generated_plan_run() is True

    def mismatch(*_args):
        raise NovaPlanDispatchError(
            "Nova plan input object metadata does not match this attempt; reconcile it",
            outcome_uncertain=True,
            phase="input_stage",
        )

    dispatcher.inspect_staged_input = mismatch
    with pytest.raises(NovaPlanDispatchError, match="metadata does not match"):
        service.reconcile_generated_plan_input(founder(), run["id"])
    assert service.generated_plan_run_detail(founder(), run["id"])["state"] == "RECONCILIATION_REQUIRED"

    abandoned = service.reconcile_generated_plan_input(
        founder(), run["id"], abandon_attempt=True
    )
    assert abandoned["state"] == "FAILED"
    assert abandoned["error_code"] == "INPUT_ATTEMPT_ABANDONED"
    old_runner_id = db.get(GeneratedPlanRun, run["id"]).runner_run_id
    dispatcher.stage_input = original_stage
    retried = service.retry_generated_plan_run(
        founder(), run["id"], "nova-plan-request-stage-abandon-retry-001"
    )
    assert retried["state"] == "QUEUED"
    assert db.get(GeneratedPlanRun, run["id"]).runner_run_id != old_runner_id
    assert service.run_next_generated_plan_run() is True
    assert db.get(GeneratedPlanRun, run["id"]).state == "BUILD_STARTED"
    db.close()


@pytest.mark.parametrize("inspected_version", ["fixture-input-version", None])
def test_delayed_input_inspection_cannot_mutate_a_later_attempt(inspected_version):
    service, db, _, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    original_stage = dispatcher.stage_input

    def stage_then_lose_confirmation(run_id, document):
        original_stage(run_id, document)
        raise NovaPlanDispatchError(
            "fixture lost input-stage confirmation",
            outcome_uncertain=True,
            phase="input_stage",
        )

    dispatcher.stage_input = stage_then_lose_confirmation
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-input-race-0001"
    )
    service._wake_worker = lambda *_args: None
    assert service.run_next_generated_plan_run() is True
    run = db.get(GeneratedPlanRun, request["id"])
    original_runner_id = run.runner_run_id

    def delayed_inspection(run_id, key, digest):
        assert run_id == original_runner_id
        assert key == dispatcher.input_key(original_runner_id)
        assert digest == run.input_sha256
        run.state = "RECONCILIATION_REQUIRED"
        run.error_code = "INPUT_STAGE_RECONCILIATION_REQUIRED"
        run.error_summary = "The later retry requires its own input reconciliation."
        run.runner_run_id = "nova-plan-race-retry-attempt-0001"
        run.input_key = dispatcher.input_key(run.runner_run_id)
        run.result_key = dispatcher.result_key(run.runner_run_id)
        run.input_sha256 = "c" * 64
        run.proposal_sha256 = "d" * 64
        run.input_version_id = None
        db.commit()
        return inspected_version

    dispatcher.inspect_staged_input = delayed_inspection
    recovered = service.reconcile_generated_plan_input(founder(), request["id"])
    db.refresh(run)
    assert recovered["state"] == "RECONCILIATION_REQUIRED"
    assert run.runner_run_id == "nova-plan-race-retry-attempt-0001"
    assert run.input_key == dispatcher.input_key(run.runner_run_id)
    assert run.input_sha256 == "c" * 64
    assert run.input_version_id is None
    db.close()


def test_preparation_lease_expired_before_generation_can_be_explicitly_abandoned_and_retried():
    service, db, generator, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-expire-before-call-0001"
    )
    claimed = service._claim_next_generated_plan_run()
    assert claimed is not None
    run, _lease_token = claimed
    assert run.preparation_phase is None
    run.preparation_lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert service._expire_generated_plan_run_lease(run, datetime.now(UTC)) is True
    expired = service.generated_plan_run_detail(founder(), request["id"])
    assert expired["state"] == "RECONCILIATION_REQUIRED"
    assert expired["error_code"] == "PREPARATION_LEASE_EXPIRED"
    assert generator.calls == 0
    assert dispatcher.started == []

    abandoned = service.abandon_generated_plan_generation_attempt(founder(), request["id"])
    assert abandoned["state"] == "FAILED"
    assert abandoned["error_code"] == "PREPARATION_ATTEMPT_ABANDONED"
    retried = service.retry_generated_plan_run(
        founder(), request["id"], "nova-plan-expire-before-call-retry-0001"
    )
    assert retried["state"] == "QUEUED"
    assert service.run_next_generated_plan_run() is True
    assert generator.calls == 1
    assert len(dispatcher.started) == 1
    db.close()


def test_worker_persists_each_phase_before_external_calls():
    service, db, generator, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-phase-boundaries-0001"
    )

    def current_phase():
        with Session(bind=db.get_bind()) as observer:
            observed = observer.scalar(
                select(GeneratedPlanRun)
                .where(GeneratedPlanRun.id == request["id"])
                .execution_options(populate_existing=True)
            )
            return observed.preparation_phase, observed.input_sha256, observed.input_version_id

    original_generate = generator.generate

    def generate(**kwargs):
        assert current_phase()[0] == "GENERATING_PROPOSAL"
        return original_generate(**kwargs)

    generator.generate = generate
    original_stage = dispatcher.stage_input

    def stage_input(run_id, document):
        phase, input_sha256, _version = current_phase()
        assert phase == "STAGING_INPUT"
        assert input_sha256
        assert document["run_id"] == run_id
        return original_stage(run_id, document)

    dispatcher.stage_input = stage_input
    original_start = dispatcher.start_build

    def start_build(run_id, idempotency_token):
        phase, input_sha256, input_version_id = current_phase()
        assert phase == "STARTING_BUILD"
        assert input_sha256
        assert input_version_id == "fixture-input-version"
        return original_start(run_id, idempotency_token)

    dispatcher.start_build = start_build

    assert service.run_next_generated_plan_run() is True
    completed = db.get(GeneratedPlanRun, request["id"])
    assert completed.state == "BUILD_STARTED", completed.error_summary
    assert completed.preparation_phase is None
    db.close()


def test_expired_input_stage_phase_uses_safe_input_reconciliation():
    service, db, _, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-expired-input-phase-001"
    )
    claimed = service._claim_next_generated_plan_run()
    assert claimed is not None
    run, _lease_token = claimed
    run.proposal_sha256 = "a" * 64
    pending_document = {"run_id": run.runner_run_id, "proposal_sha256": run.proposal_sha256}
    run.input_key = dispatcher.input_key(run.runner_run_id)
    run.input_sha256 = canonical_json_digest(pending_document)
    run.input_version_id = "fixture-input-version"
    dispatcher.staged.append(
        (
            run.runner_run_id,
            pending_document,
            run.input_key,
            run.input_sha256,
            run.input_version_id,
        )
    )
    run.preparation_phase = "STAGING_INPUT"
    run.preparation_lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    assert service._expire_generated_plan_run_lease(run, datetime.now(UTC)) is True
    expired = service.generated_plan_run_detail(founder(), request["id"])
    assert expired["state"] == "RECONCILIATION_REQUIRED"
    assert expired["error_code"] == "INPUT_STAGE_RECONCILIATION_REQUIRED"
    assert service.reconcile_generated_plan_input(founder(), request["id"])["state"] == "QUEUED"
    assert db.get(GeneratedPlanRun, request["id"]).input_version_id == "fixture-input-version"
    assert dispatcher.started == []
    db.close()


def test_expired_codebuild_start_phase_stays_blocked_without_replaying_build():
    service, db, _, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-expired-build-phase-001"
    )
    claimed = service._claim_next_generated_plan_run()
    assert claimed is not None
    run, _lease_token = claimed
    run.proposal_sha256 = "a" * 64
    run.input_sha256 = "b" * 64
    run.input_version_id = "fixture-input-version"
    run.preparation_phase = "STARTING_BUILD"
    run.preparation_lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    assert service._expire_generated_plan_run_lease(run, datetime.now(UTC)) is True
    blocked = service.generated_plan_run_detail(founder(), request["id"])
    assert blocked["state"] == "RECONCILIATION_REQUIRED"
    assert blocked["error_code"] == "BUILD_START_RECONCILIATION_REQUIRED"
    assert "Do not retry" in blocked["error_summary"]
    with pytest.raises(ValueError, match="only an ambiguous pre-build input"):
        service.reconcile_generated_plan_input(founder(), request["id"])
    with pytest.raises(ValueError, match="confirmed failed"):
        service.retry_generated_plan_run(
            founder(), request["id"], "nova-plan-expired-build-retry-0001"
        )
    assert service.run_next_generated_plan_run() is False
    assert dispatcher.started == []
    db.close()


def test_expired_build_input_handoff_reconciles_exact_build_without_restarting():
    service, db, _, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-expired-build-input-001"
    )

    original_stage = dispatcher.stage_build_input
    stage_calls = []

    def crash_after_durable_build_start(run_id, build_arn, document):
        run = db.get(GeneratedPlanRun, request["id"])
        assert run.codebuild_build_id
        assert run.preparation_phase == "STAGING_BUILD_INPUT"
        assert run.result_metadata["codebuild_build_arn"] == build_arn
        run.preparation_lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
        assert service._expire_generated_plan_run_lease(run, datetime.now(UTC)) is True
        # Model a process exit before it can make the build-scoped S3 call.
        raise SystemExit("fixture worker crashed before input copy")

    dispatcher.stage_build_input = crash_after_durable_build_start
    with pytest.raises(SystemExit, match="worker crashed"):
        service.run_next_generated_plan_run()

    blocked = service.generated_plan_run_detail(founder(), request["id"])
    run = db.get(GeneratedPlanRun, request["id"])
    assert blocked["error_code"] == "BUILD_INPUT_STAGE_RECONCILIATION_REQUIRED"
    assert run.preparation_phase == "STAGING_BUILD_INPUT"
    build_id = run.codebuild_build_id
    assert build_id and len(dispatcher.started) == 1
    assert dispatcher.build_staged == []

    def inaccessible_head(*_args):
        raise NovaPlanDispatchError(
            "fixture HeadObject returned 403 for a missing object",
            outcome_uncertain=True,
            phase="input_stage",
        )

    dispatcher.inspect_staged_input = inaccessible_head

    def count_stage(*args):
        stage_calls.append(args)
        return original_stage(*args)

    dispatcher.stage_build_input = count_stage
    recovered = service.reconcile_generated_plan_input(founder(), request["id"])

    assert recovered["state"] == "BUILD_STARTED"
    assert db.get(GeneratedPlanRun, request["id"]).codebuild_build_id == build_id
    assert len(stage_calls) == 1
    assert len(dispatcher.started) == 1
    assert len(dispatcher.build_staged) == 1
    db.close()


def test_lost_build_input_copy_response_reconciles_existing_version_without_duplicate_put():
    service, db, _, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-lost-build-copy-001"
    )
    original_stage = dispatcher.stage_build_input
    attempts = []

    def copy_then_lose_response(run_id, build_arn, document):
        attempts.append((run_id, build_arn))
        original_stage(run_id, build_arn, document)
        raise NovaPlanDispatchError(
            "fixture build input PutObject response was lost",
            outcome_uncertain=True,
            phase="build_input_stage",
        )

    dispatcher.stage_build_input = copy_then_lose_response
    assert service.run_next_generated_plan_run() is True
    uncertain = service.generated_plan_run_detail(founder(), request["id"])
    stored = db.get(GeneratedPlanRun, request["id"])
    assert uncertain["state"] == "RECONCILIATION_REQUIRED"
    assert uncertain["error_code"] == "BUILD_INPUT_STAGE_RECONCILIATION_REQUIRED"
    assert stored.codebuild_build_id
    assert stored.preparation_phase == "STAGING_BUILD_INPUT"
    assert len(attempts) == len(dispatcher.build_staged) == len(dispatcher.started) == 1

    recovered = service.reconcile_generated_plan_input(founder(), request["id"])

    assert recovered["state"] == "BUILD_STARTED"
    stored = db.get(GeneratedPlanRun, request["id"])
    assert stored.input_key == dispatcher.build_input_key(
        stored.result_metadata["codebuild_build_arn"]
    )
    assert stored.input_version_id == "fixture-build-input-version"
    assert len(attempts) == len(dispatcher.build_staged) == len(dispatcher.started) == 1
    db.close()


def test_completion_rejects_result_bound_to_another_tenant():
    service, db, _, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-wrong-result-tenant-001"
    )
    assert service.run_next_generated_plan_run() is True
    run = db.get(GeneratedPlanRun, request["id"])
    assert run and run.state == "BUILD_STARTED"
    result = {
        "contract": "davdeploy.nova-plan-result.v1",
        "run_id": run.runner_run_id,
        "codebuild_project": run.codebuild_project,
        "codebuild_build_id": run.codebuild_build_id,
        "codebuild_build_arn": run.result_metadata["codebuild_build_arn"],
        "input": {
            "key": run.input_key,
            "version_id": run.input_version_id,
            "sha256": run.input_sha256,
        },
        "binding": {
            "organization_id": "other-tenant",
            "project_id": run.project_id,
            "plan_id": run.request_document["plan_id"],
            "revision_id": run.revision_id,
            "revision_sha256": run.revision_sha256,
            "account_id": run.request_document["target_account_id"],
            "region": run.request_document["region"],
            "proposal_sha256": run.proposal_sha256,
            "context_sha256": "c" * 64,
        },
        "policy_evidence": {},
        "policy_sha256": canonical_json_digest({}),
        "manifest": {},
        "manifest_sha256": canonical_json_digest({}),
        "planning_boundary": "INITIAL_PLAN_NO_REMOTE_STATE",
    }

    with pytest.raises(ValueError, match="tenant, revision, or target binding"):
        service._persist_verified_nova_plan_result(
            run, dispatcher, result, "fixture-result-version", "d" * 64
        )

    assert db.query(GeneratedPlanArtifact).count() == 0
    db.close()


def test_expired_generation_requires_explicit_abandon_before_fresh_retry():
    service, db, generator, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-expired-generation-0001"
    )
    claimed = service._claim_next_generated_plan_run()
    assert claimed is not None
    run, _lease_token = claimed
    original_runner_id = run.runner_run_id
    run.preparation_phase = "GENERATING_PROPOSAL"
    run.preparation_lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    assert service._expire_generated_plan_run_lease(run, datetime.now(UTC)) is True
    uncertain = service.generated_plan_run_detail(founder(), request["id"])
    assert uncertain["state"] == "RECONCILIATION_REQUIRED"
    assert uncertain["error_code"] == "PROPOSAL_GENERATION_RECONCILIATION_REQUIRED"
    with pytest.raises(ValueError, match="confirmed failed"):
        service.retry_generated_plan_run(
            founder(), request["id"], "nova-plan-generation-no-abandon-0001"
        )

    abandoned = service.abandon_generated_plan_generation_attempt(founder(), request["id"])
    assert abandoned["state"] == "FAILED"
    assert abandoned["error_code"] == "GENERATION_ATTEMPT_ABANDONED"
    assert service.run_next_generated_plan_run() is False
    assert dispatcher.started == []

    retried = service.retry_generated_plan_run(
        founder(), request["id"], "nova-plan-generation-explicit-retry-0001"
    )
    assert retried["state"] == "QUEUED"
    assert db.get(GeneratedPlanRun, request["id"]).runner_run_id != original_runner_id
    assert service.run_next_generated_plan_run() is True
    assert db.get(GeneratedPlanRun, request["id"]).state == "BUILD_STARTED"
    assert generator.calls == 1
    assert len(dispatcher.started) == 1
    db.close()


def test_lost_codebuild_start_response_reconciles_one_exact_run_id_match():
    service, db, _, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-start-response-lost-0001"
    )
    original_start = dispatcher.start_build

    def start_then_lose_response(run_id, idempotency_token):
        original_start(run_id, idempotency_token)
        raise NovaPlanDispatchError(
            "fixture StartBuild response was lost",
            outcome_uncertain=True,
            phase="build_start",
        )

    dispatcher.start_build = start_then_lose_response
    assert service.run_next_generated_plan_run() is True

    blocked = service.generated_plan_run_detail(founder(), request["id"])
    stored = db.get(GeneratedPlanRun, request["id"])
    assert blocked["state"] == "RECONCILIATION_REQUIRED"
    assert blocked["error_code"] == "BUILD_START_RECONCILIATION_REQUIRED"
    assert stored.codebuild_build_id is None
    assert stored.preparation_phase == "STARTING_BUILD"
    assert len(dispatcher.started) == 1
    started_run_id, started_token, _ = dispatcher.started[0]
    assert started_token == stored.codebuild_idempotency_token == started_run_id

    dispatcher.lookup_result = NovaPlanBuild(
        f"{PROJECT}:{started_run_id}",
        PROJECT,
        "IN_PROGRESS",
        started_run_id,
        dispatcher.build_arn(started_run_id),
    )
    recovered = service.reconcile_generated_plan_build_attempt(founder(), request["id"])

    assert recovered["state"] == "BUILD_STARTED"
    stored = db.get(GeneratedPlanRun, request["id"])
    assert stored.codebuild_build_id == f"{PROJECT}:{started_run_id}"
    assert stored.preparation_phase is None
    assert dispatcher.lookups == [started_run_id]
    assert len(dispatcher.started) == 1
    with pytest.raises(ValueError, match="ambiguous pre-build input attempt"):
        service.reconcile_generated_plan_input(founder(), request["id"])
    db.close()


def test_zero_build_lookup_keeps_start_attempt_blocked_and_non_retryable():
    service, db, _, dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-start-no-match-0001"
    )
    def uncertain_start(_run_id, _idempotency_token):
        raise NovaPlanDispatchError(
            "fixture StartBuild outcome is uncertain",
            outcome_uncertain=True,
            phase="build_start",
        )

    dispatcher.start_build = uncertain_start
    assert service.run_next_generated_plan_run() is True
    blocked = service.generated_plan_run_detail(founder(), request["id"])
    assert blocked["error_code"] == "BUILD_START_RECONCILIATION_REQUIRED"
    assert service.reconcile_generated_plan_build_attempt(founder(), request["id"])["state"] == (
        "RECONCILIATION_REQUIRED"
    )
    assert db.get(GeneratedPlanRun, request["id"]).codebuild_build_id is None
    with pytest.raises(ValueError, match="confirmed failed"):
        service.retry_generated_plan_run(
            founder(), request["id"], "nova-plan-start-no-match-retry-0001"
        )
    assert dispatcher.lookups == [db.get(GeneratedPlanRun, request["id"]).runner_run_id]
    assert dispatcher.started == []
    db.close()


def test_reconcile_build_uses_already_durable_build_id_without_search():
    service, db, _, dispatcher = service_with_dispatcher(status="SUCCEEDED")
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-known-start-id-0001"
    )
    run = db.get(GeneratedPlanRun, request["id"])
    run.codebuild_build_id = f"{PROJECT}:already-durable"
    dispatcher.build_run_ids[run.codebuild_build_id] = run.runner_run_id
    pending_document = {"run_id": run.runner_run_id}
    run.input_key = dispatcher.input_key(run.runner_run_id)
    run.input_sha256 = canonical_json_digest(pending_document)
    run.input_version_id = "fixture-input-version"
    run.proposal_sha256 = "a" * 64
    dispatcher.staged.append(
        (
            run.runner_run_id,
            pending_document,
            run.input_key,
            run.input_sha256,
            run.input_version_id,
        )
    )
    build_arn = dispatcher.build_arn_for_id(run.codebuild_build_id)
    build_document = {**pending_document, "codebuild_build_arn": build_arn}
    dispatcher.build_staged.append(
        (
            run.runner_run_id,
            build_document,
            dispatcher.build_input_key(build_arn),
            canonical_json_digest(build_document),
            "fixture-build-input-version",
        )
    )
    run.result_metadata = {"codebuild_build_arn": build_arn}
    run.preparation_phase = "STARTING_BUILD"
    run.state = "RECONCILIATION_REQUIRED"
    run.error_code = "BUILD_START_RECONCILIATION_REQUIRED"
    db.commit()

    reconciled = service.reconcile_generated_plan_build_attempt(founder(), request["id"])

    assert reconciled["state"] == "RECONCILIATION_REQUIRED"
    assert reconciled["error_code"] == "PLAN_RESULT_RECONCILIATION_REQUIRED"
    assert dispatcher.lookups == []
    db.close()


def test_known_codebuild_id_after_expired_start_is_bound_for_existing_reconciler():
    service, db, _, _dispatcher = service_with_dispatcher()
    _, _, revision = make_submitted_revision(service)
    service._wake_worker = lambda *_args: None
    request = service.request_generated_plan_run(
        founder(), revision.id, revision.content_digest, "nova-plan-expired-build-id-known-001"
    )
    claimed = service._claim_next_generated_plan_run()
    assert claimed is not None
    run, lease_token = claimed
    runner_run_id = run.runner_run_id
    idempotency_token = run.codebuild_idempotency_token
    run.proposal_sha256 = "a" * 64
    pending_document = {"run_id": run.runner_run_id, "proposal_sha256": run.proposal_sha256}
    run.input_key = _dispatcher.input_key(run.runner_run_id)
    run.input_sha256 = canonical_json_digest(pending_document)
    run.input_version_id = "fixture-input-version"
    _dispatcher.staged.append(
        (
            run.runner_run_id,
            pending_document,
            run.input_key,
            run.input_sha256,
            run.input_version_id,
        )
    )
    run.preparation_phase = "STARTING_BUILD"
    run.preparation_lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    assert service._expire_generated_plan_run_lease(run, datetime.now(UTC)) is True
    build_id = f"{PROJECT}:known-after-lease-expiry"
    _dispatcher.build_run_ids[build_id] = run.runner_run_id
    assert service._finish_generated_plan_run_claim(
        run,
        lease_token,
        state="RECONCILIATION_REQUIRED",
        error_code="BUILD_START_RECONCILIATION_REQUIRED",
        error_summary="Build start response arrived after the lease expired.",
        action="generated_plan_run.build_start_uncertain",
        codebuild_build_id=build_id,
        codebuild_build_arn=_dispatcher.build_arn_for_id(build_id),
        expected_runner_run_id=runner_run_id,
        expected_idempotency_token=idempotency_token,
    ) is True
    recovered = db.get(GeneratedPlanRun, request["id"])
    db.refresh(recovered)
    assert recovered.codebuild_build_id == build_id
    assert recovered.state == "RECONCILIATION_REQUIRED"
    assert recovered.error_code == "BUILD_INPUT_STAGE_RECONCILIATION_REQUIRED"
    assert recovered.preparation_phase == "STAGING_BUILD_INPUT"
    assert service.reconcile_generated_plan_input(founder(), request["id"])["state"] == (
        "BUILD_STARTED"
    )
    assert len(_dispatcher.started) == 0
    assert len(_dispatcher.build_staged) == 1
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
