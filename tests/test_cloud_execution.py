from __future__ import annotations

from davdeploy.cloud_execution import (
    CloudExecutionResult,
    CodeBuildCloudExecutionAdapter,
    DisabledCloudExecutionAdapter,
)
from davdeploy.models import (
    CloudExecutionRun,
    InfrastructurePlanDecisionRecord,
    InfrastructurePlanRevision,
)
from davdeploy.service import plan_hash
from sqlalchemy import select
from test_customer_plan_review import approved_app_runner_customer_review
from test_product import founder, make_service, operator


class FakeCloudExecutionAdapter:
    def __init__(self, state="READY"):
        self.state = state
        self.contexts = []

    def execute(self, context):
        self.contexts.append(context)
        return CloudExecutionResult(
            state=self.state,
            operations=({"operation": "pilot", "returncode": 0},),
            outputs={"application_url": "https://customer.example"},
            failure_reason=None if self.state == "READY" else "fixture failure",
        )


def test_disabled_cloud_adapter_never_executes():
    result = DisabledCloudExecutionAdapter().execute({"profile": "aws-app-runner"})
    assert result.state == "BLOCKED_CLOUD_EXECUTION_NOT_ENABLED"
    assert result.operations == ()


def test_codebuild_adapter_submits_only_the_fixed_execution_environment():
    calls = []

    class CodeBuild:
        def start_build(self, **kwargs):
            calls.append(kwargs)
            return {"build": {"id": "davdeploy:build-1", "arn": "arn:build-1"}}

    environment = {
        key: "value" for key in CodeBuildCloudExecutionAdapter.required_environment
    }
    environment["DAVDEPLOY_EXECUTION_OPERATION"] = "apply-foundation"
    adapter = CodeBuildCloudExecutionAdapter("davdeploy-customer-executor", client=CodeBuild())

    result = adapter.execute({"environment": environment})

    assert result.state == "SUBMITTED"
    assert result.outputs["codebuild_build_id"] == "davdeploy:build-1"
    assert calls[0]["projectName"] == "davdeploy-customer-executor"
    assert all(item["name"] != "COMMAND" for item in calls[0]["environmentVariablesOverride"])


def test_codebuild_completion_accepts_the_eventbridge_build_arn(monkeypatch):
    service, _ = make_service()
    short_id = "davdeploy-customer-executor:build-1"
    build_arn = f"arn:aws:codebuild:us-east-1:111122223333:build/{short_id}"
    run = CloudExecutionRun(
        organization_id=founder().organization_id,
        revision_id="revision-1",
        project_id="project-1",
        profile="aws-app-runner",
        state="SUBMITTED",
        mode="AUTHENTICATED_TERRAFORM_PLAN",
        attempt=1,
        command={},
        evidence={"result_s3_uri": "not-an-s3-uri"},
        outputs={"codebuild_build_id": short_id, "codebuild_build_arn": build_arn},
        content_digest="a" * 64,
        requested_by_subject=founder().subject,
    )
    service.db.add(run)
    service.db.commit()
    calls = []

    class CodeBuild:
        def batch_get_builds(self, *, ids):
            calls.append(ids)
            return {"builds": [{"buildStatus": "FAILED"}]}

    monkeypatch.setattr("davdeploy.service.boto3.client", lambda service_name: CodeBuild())

    assert service.reconcile_cloud_execution_build(build_arn) is True
    assert calls == [[short_id]]


def test_admin_can_reconcile_only_the_safe_encrypted_result_read_failure(monkeypatch):
    service, _ = make_service()
    build_id = "davdeploy-customer-executor:build-safe-retry"
    run = CloudExecutionRun(
        organization_id=founder().organization_id,
        revision_id="revision-safe-retry",
        project_id="project-safe-retry",
        profile="aws-app-runner",
        state="FAILED",
        mode="AUTHENTICATED_APP_RUNNER_APPLY",
        attempt=1,
        command={},
        evidence={"result_s3_uri": "s3://runner-results/run/result.json"},
        outputs={"codebuild_build_id": build_id, "failure_reason": "runner result artifact URI is missing"},
        content_digest="b" * 64,
        requested_by_subject=founder().subject,
    )
    service.db.add(run)
    service.db.commit()

    class Body:
        def read(self):
            return ('{"run_id": "' + run.id + '", "status": "SUCCEEDED", "detail": {"output": "ok"}}').encode()

    class CodeBuild:
        def batch_get_builds(self, *, ids):
            assert ids == [build_id]
            return {"builds": [{"buildStatus": "SUCCEEDED", "buildComplete": True}]}

    class S3:
        def get_object(self, *, Bucket, Key):
            assert (Bucket, Key) == ("runner-results", "run/result.json")
            return {"Body": Body()}

    monkeypatch.setattr(
        "davdeploy.service.boto3.client",
        lambda service_name: CodeBuild() if service_name == "codebuild" else S3(),
    )

    result = service.reconcile_cloud_execution_run_result(operator(), run.id)

    assert result["state"] == "SUCCEEDED_AWAITING_OBSERVATION"
    assert result["outputs"]["terraform_outputs"] == {"output": "ok"}


def test_reconciliation_reads_a_generated_legacy_result_uri(monkeypatch):
    service, _ = make_service()
    build_id = "davdeploy-customer-executor:legacy-result"
    run = CloudExecutionRun(
        organization_id=founder().organization_id,
        revision_id="revision-legacy-result",
        project_id="project-legacy-result",
        profile="aws-app-runner",
        state="SUBMITTED",
        mode="AUTHENTICATED_APP_RUNNER_APPLY",
        attempt=1,
        command={},
        evidence={
            "execution_environment": {
                "DAVDEPLOY_EXECUTION_RESULT_S3_URI": "s3://runner-results/legacy/result.json"
            }
        },
        outputs={"codebuild_build_id": build_id},
        content_digest="d" * 64,
        requested_by_subject=founder().subject,
    )
    service.db.add(run)
    service.db.commit()

    class Body:
        def read(self):
            return ('{"run_id": "' + run.id + '", "status": "SUCCEEDED", "detail": {}}').encode()

    class CodeBuild:
        def batch_get_builds(self, *, ids):
            return {"builds": [{"buildStatus": "SUCCEEDED", "buildComplete": True}]}

    class S3:
        def get_object(self, *, Bucket, Key):
            assert (Bucket, Key) == ("runner-results", "legacy/result.json")
            return {"Body": Body()}

    monkeypatch.setattr(
        "davdeploy.service.boto3.client",
        lambda service_name: CodeBuild() if service_name == "codebuild" else S3(),
    )

    assert service.reconcile_cloud_execution_build(build_id) is True
    assert service.db.get(CloudExecutionRun, run.id).state == "SUCCEEDED_AWAITING_OBSERVATION"


def test_result_reconciliation_rejects_non_retryable_failure():
    service, _ = make_service()
    run = CloudExecutionRun(
        organization_id=founder().organization_id,
        revision_id="revision-no-retry",
        project_id="project-no-retry",
        profile="aws-app-runner",
        state="FAILED",
        mode="AUTHENTICATED_APP_RUNNER_APPLY",
        attempt=1,
        command={},
        evidence={},
        outputs={"failure_reason": "Bounded CodeBuild runner failed."},
        content_digest="c" * 64,
        requested_by_subject=founder().subject,
    )
    service.db.add(run)
    service.db.commit()

    try:
        service.reconcile_cloud_execution_run_result(operator(), run.id)
    except ValueError as error:
        assert "not eligible" in str(error)
    else:
        raise AssertionError("non-retryable execution failure was reconciled")


def test_ready_cloud_run_is_queued_and_observed_by_trusted_worker():
    service, _ = make_service()
    adapter = FakeCloudExecutionAdapter()
    service.cloud_execution = adapter
    approved = approved_app_runner_customer_review(service)
    render = service.create_terraform_plan_render_for_revision(founder(), approved.id, approved.content_digest)
    preflight = service.create_cloud_readiness_preflight(
        operator(),
        approved.id,
        content_digest=approved.content_digest,
        expected_account_id=None,
        allowed_regions=["us-east-1"],
        required_tags={},
        budget_ceiling_usd=5000,
        execution_mode="PLAN_ONLY",
        require_reviewed_pr=False,
        runtime_identity_configured=True,
    )
    plan_review = service.create_terraform_plan_review_for_revision(
        operator(),
        approved.id,
        content_digest=approved.content_digest,
        preflight_id=preflight["id"],
        expected_account_id=None,
        expected_region="us-east-1",
        mode="LOCAL_CONTRACT_ONLY",
        allow_cloud_plan=False,
    )
    run = service.create_cloud_execution_run_for_revision(
        operator(),
        approved.id,
        content_digest=approved.content_digest,
        terraform_render_id=render["id"],
        preflight_id=preflight["id"],
        terraform_plan_review_id=plan_review["id"],
        expected_account_id=None,
        expected_region="us-east-1",
        mode="AUTHENTICATED_APP_RUNNER_APPLY",
        confirmation="EXECUTE_APP_RUNNER_WORKLOAD",
    )
    assert run["state"] != "READY_FOR_OPERATOR_APP_RUNNER_EXECUTION"
    # Local test config does not enable cloud apply, so it remains blocked.
    assert service.run_next_cloud_execution() is False


def test_cloud_run_queue_requires_admin_and_exact_confirmation():
    service, _ = make_service()
    approved = approved_app_runner_customer_review(service)
    run = service.create_cloud_execution_run_for_revision(
        operator(),
        approved.id,
        content_digest=approved.content_digest,
        terraform_render_id=None,
        preflight_id=None,
        terraform_plan_review_id=None,
        expected_account_id=None,
        expected_region=None,
        mode="GUARDED_CLOUD_EXECUTION",
        confirmation=None,
    )
    try:
        service.queue_cloud_execution_run(founder(), run["id"], approved.content_digest, "bad")
    except PermissionError:
        pass
    else:
        raise AssertionError("developer could queue cloud execution")


def test_queueing_a_ready_cloud_run_wakes_the_worker(monkeypatch):
    service, _ = make_service()
    run = CloudExecutionRun(
        organization_id=founder().organization_id,
        revision_id="revision-queued",
        project_id="project-queued",
        profile="aws-app-runner",
        state="READY_FOR_OPERATOR_APP_RUNNER_EXECUTION",
        mode="AUTHENTICATED_APP_RUNNER_APPLY",
        attempt=1,
        command={},
        evidence={},
        outputs={},
        content_digest="b" * 64,
        requested_by_subject=founder().subject,
    )
    service.db.add(run)
    service.db.commit()
    wakeups = []
    monkeypatch.setattr(service, "_wake_worker", lambda kind, job_id: wakeups.append((kind, job_id)))

    queued = service.queue_cloud_execution_run(
        operator(), run.id, run.content_digest, "EXECUTE_APP_RUNNER_WORKLOAD"
    )

    assert queued["state"] == "QUEUED"
    assert wakeups == [("cloud_execution", run.id)]


def test_reassigned_execution_context_is_durably_persisted():
    """Nested JSON context must be replaced, rather than mutated in place."""
    service, _ = make_service()
    run = CloudExecutionRun(
        organization_id=founder().organization_id,
        revision_id="revision-context",
        project_id="project-context",
        profile="aws-app-runner",
        state="READY_FOR_OPERATOR_APP_RUNNER_EXECUTION",
        mode="AUTHENTICATED_APP_RUNNER_APPLY",
        attempt=1,
        command={},
        evidence={"execution_environment": {"TF_STATE_BUCKET": "customer-state"}},
        outputs={},
        content_digest="c" * 64,
        requested_by_subject=founder().subject,
    )
    service.db.add(run)
    service.db.flush()
    environment = {
        **run.evidence["execution_environment"],
        "DAVDEPLOY_EXECUTION_RUN_ID": run.id,
        "DAVDEPLOY_EXECUTION_RESULT_S3_URI": f"s3://customer-state/runs/{run.id}/result.json",
    }
    run.evidence = {**run.evidence, "execution_environment": environment}
    service.db.commit()
    service.db.expire_all()

    persisted = service.db.get(CloudExecutionRun, run.id)
    assert persisted.evidence["execution_environment"] == environment


def test_cloud_execution_persists_the_result_uri_required_for_reconciliation(monkeypatch):
    service, _ = make_service()
    approved = approved_app_runner_customer_review(service)
    monkeypatch.setenv("ALLOW_CLOUD_APPLY", "true")
    monkeypatch.setenv("DAVDEPLOY_CUSTOMER_EXECUTION_STATE_BUCKET", "customer-state")
    monkeypatch.setenv("DAVDEPLOY_CUSTOMER_EXECUTION_LOCK_TABLE", "customer-locks")
    monkeypatch.setenv("DAVDEPLOY_CUSTOMER_EXECUTION_ARTIFACT_S3_URI", "s3://releases/runner.zip")
    connection = service.create_cloud_connection(
        founder(), "Verified customer cloud", "aws", "byoc_role_contract"
    )
    connection.setup_state = "VERIFIED"
    connection.account_id = "654654474502"
    connection.execution_role_arn = "arn:aws:iam::654654474502:role/davdeployExecution-test"
    connection.external_id_secret_ref = "arn:aws:secretsmanager:us-east-1:654654474502:secret:test"
    revision = service.db.get(InfrastructurePlanRevision, approved.id)
    assert revision is not None
    revision.content = {
        **revision.content,
        "target": {
            **revision.content["target"],
            "connection_id": connection.id,
            "account_id": connection.account_id,
            "region": "us-east-1",
        },
    }
    revision.content_digest = plan_hash(revision.content)
    decision = service.db.scalar(
        select(InfrastructurePlanDecisionRecord).where(
            InfrastructurePlanDecisionRecord.revision_id == revision.id
        )
    )
    assert decision is not None
    decision.approved_digest = revision.content_digest
    service.db.commit()

    run = service.create_cloud_execution_run_for_revision(
        operator(),
        approved.id,
        content_digest=revision.content_digest,
        terraform_render_id=None,
        preflight_id=None,
        terraform_plan_review_id=None,
        expected_account_id=None,
        expected_region="us-east-1",
        mode="AUTHENTICATED_APP_RUNNER_APPLY",
        confirmation="EXECUTE_APP_RUNNER_WORKLOAD",
    )

    assert run["evidence"]["result_s3_uri"].endswith(f"runs/{run['id']}/result.json")


def test_authenticated_cloud_run_requires_verified_connection_and_execution_role(monkeypatch):
    """A fixture/local plan may be reviewed, but never becomes an AWS apply request."""
    service, _ = make_service()
    approved = approved_app_runner_customer_review(service)
    monkeypatch.setenv("ALLOW_CLOUD_APPLY", "true")
    monkeypatch.setenv("DAVDEPLOY_ENABLE_APP_RUNNER_EXECUTION", "true")

    run = service.create_cloud_execution_run_for_revision(
        operator(),
        approved.id,
        content_digest=approved.content_digest,
        terraform_render_id=None,
        preflight_id=None,
        terraform_plan_review_id=None,
        expected_account_id=None,
        expected_region="us-east-1",
        mode="AUTHENTICATED_APP_RUNNER_APPLY",
        confirmation="EXECUTE_APP_RUNNER_WORKLOAD",
    )

    assert run["state"] != "READY_FOR_OPERATOR_APP_RUNNER_EXECUTION"
    assert "verified customer cloud connection" in " ".join(run["evidence"]["blockers"])


def test_customer_image_build_pins_source_and_requires_foundation(monkeypatch):
    service, _ = make_service()
    approved = approved_app_runner_customer_review(service)
    service.cloud_execution = FakeCloudExecutionAdapter(state="SUBMITTED")
    monkeypatch.setenv("ALLOW_CLOUD_APPLY", "true")
    monkeypatch.setenv("DAVDEPLOY_ENABLE_APP_RUNNER_EXECUTION", "true")
    monkeypatch.setenv("DAVDEPLOY_CUSTOMER_EXECUTION_STATE_BUCKET", "customer-state")
    monkeypatch.setenv("DAVDEPLOY_CUSTOMER_EXECUTION_LOCK_TABLE", "customer-locks")
    monkeypatch.setenv("DAVDEPLOY_CUSTOMER_EXECUTION_ARTIFACT_S3_URI", "s3://releases/runner.zip")
    connection = service.create_cloud_connection(
        founder(), "Verified customer cloud", "aws", "byoc_role_contract"
    )
    connection.setup_state = "VERIFIED"
    connection.account_id = "654654474502"
    connection.execution_role_arn = "arn:aws:iam::654654474502:role/davdeployExecution-test"
    connection.external_id_secret_ref = "arn:aws:secretsmanager:us-east-1:654654474502:secret:test"
    revision = service.db.get(InfrastructurePlanRevision, approved.id)
    assert revision is not None
    revision.content = {
        **revision.content,
        "target": {**revision.content["target"], "connection_id": connection.id, "account_id": connection.account_id},
    }
    revision.content_digest = plan_hash(revision.content)
    decision = service.db.scalar(
        select(InfrastructurePlanDecisionRecord).where(
            InfrastructurePlanDecisionRecord.revision_id == revision.id
        )
    )
    assert decision is not None
    decision.approved_digest = revision.content_digest
    _, infrastructure_plan, _ = service._approved_customer_revision(operator(), revision.id)
    foundation = CloudExecutionRun(
        organization_id=founder().organization_id,
        revision_id=revision.id,
        project_id=infrastructure_plan.project_id,
        profile="aws-app-runner",
        state="SUCCEEDED_AWAITING_OBSERVATION",
        mode="AUTHENTICATED_APP_RUNNER_APPLY",
        command={},
        evidence={},
        outputs={"terraform_outputs": {"ecr_repository_url": {"value": f"654654474502.dkr.ecr.us-east-1.amazonaws.com/davdeploy-{connection.id}-workload"}}},
        content_digest=revision.content_digest,
        requested_by_subject=operator().subject,
    )
    service.db.add(foundation)
    service.db.commit()

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"sha": "a" * 40}

    monkeypatch.setattr("davdeploy.service.httpx.get", lambda *args, **kwargs: Response())
    run = service.create_customer_image_build_for_revision(
        operator(),
        revision.id,
        content_digest=revision.content_digest,
        expected_account_id=connection.account_id,
        expected_region="us-east-1",
        confirmation="BUILD_CUSTOMER_IMAGE",
    )

    assert run["state"] == "READY_FOR_OPERATOR_APP_RUNNER_EXECUTION"
    persisted = service.db.get(CloudExecutionRun, run["id"])
    assert persisted is not None
    assert persisted.mode == "AUTHENTICATED_APP_RUNNER_IMAGE_BUILD"
    assert persisted.evidence["source"]["commit"] == "a" * 40
    assert persisted.evidence["execution_environment"]["DAVDEPLOY_CUSTOMER_ECR_REPOSITORY_URL"].endswith("-workload")
