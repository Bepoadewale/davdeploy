from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from davdeploy.cloud_execution import (
    CloudExecutionResult,
    CodeBuildCloudExecutionAdapter,
    DisabledCloudExecutionAdapter,
    validate_lifecycle_work,
)
from davdeploy.composed_deployment import ModuleLifecycleOutcome
from davdeploy.models import (
    CloudExecutionModuleInstance,
    CloudExecutionRun,
    InfrastructurePlanDecisionRecord,
    InfrastructurePlanRevision,
)
from davdeploy.service import plan_hash
from sqlalchemy import select
from test_customer_plan_review import (
    approved_app_runner_customer_review,
    ready_app_runner_preflight,
)
from test_product import founder, make_service, operator


def lifecycle_work(operation="apply"):
    return [
        {
            "module_id": "aws-managed-application",
            "operation": operation,
            "dependencies": [],
            "resource_tags": {"ManagedBy": "davdeploy"},
        }
    ]


def test_runner_work_validation_preserves_instance_identity_and_module_type():
    work = [
        {
            "module_id": "aws-managed-application",
            "instance_id": instance_id,
            "operation": "apply",
            "dependencies": [] if instance_id == "primary-app" else ["primary-app"],
            "input_bindings": []
            if instance_id == "primary-app"
            else [
                {
                    "input_name": "service_config",
                    "source_instance_id": "primary-app",
                    "source_output": "config_reference",
                }
            ],
            "resource_tags": {"DavDeployModuleInstance": instance_id},
        }
        for instance_id in ("primary-app", "admin-app")
    ]
    accepted = validate_lifecycle_work(work)

    assert set(accepted[0]) == {
        "module_id",
        "instance_id",
        "operation",
        "dependencies",
        "input_bindings",
        "resource_tags",
        "renderer",
    }
    assert [(item["module_id"], item["instance_id"]) for item in accepted] == [
        ("aws-managed-application", "primary-app"),
        ("aws-managed-application", "admin-app"),
    ]
    assert all(item["renderer"]["terraform_root"] for item in accepted)
    assert accepted[1]["input_bindings"] == [
        {
            "input_name": "service_config",
            "source_instance_id": "primary-app",
            "source_output": "config_reference",
        }
    ]


def allow_serverless_certification(monkeypatch, workspace_id):
    monkeypatch.setenv("DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION", "true")
    monkeypatch.setenv("DAVDEPLOY_SERVERLESS_CERTIFICATION_WORKSPACE_IDS", workspace_id)
    monkeypatch.setenv("DAVDEPLOY_CUSTOMER_EXECUTION_STATE_BUCKET", "customer-state")
    monkeypatch.setenv("DAVDEPLOY_CUSTOMER_EXECUTION_LOCK_TABLE", "customer-locks")
    monkeypatch.setenv("DAVDEPLOY_CUSTOMER_EXECUTION_ARTIFACT_S3_URI", "s3://releases/runner.zip")


def approved_serverless_customer_review(service, db):
    approved = approved_app_runner_customer_review(service)
    connection = service.create_cloud_connection(
        founder(), "Verified test cloud", "aws", "byoc_role_contract"
    )
    connection.setup_state = "VERIFIED"
    connection.account_id = "654654474502"
    connection.execution_role_arn = "arn:aws:iam::654654474502:role/davdeployExecution-test"
    connection.external_id_secret_ref = "arn:aws:secretsmanager:us-east-1:654654474502:secret:test"
    revision = db.get(InfrastructurePlanRevision, approved.id)
    assert revision is not None
    content = dict(revision.content)
    content["summary"] = {**content["summary"], "selected_profile": "aws-lambda-api"}
    content["target"] = {
        **content["target"],
        "connection_id": connection.id,
        "account_id": connection.account_id,
        "region": "us-east-1",
    }
    content["architecture"] = {
        **content["architecture"],
        "modules": [
            {
                "identifier": "aws-serverless-api",
                "display_name": "Serverless API",
                "purpose": "HTTP API backed by Lambda",
                "stage": "certification",
                "services": ["Lambda", "API Gateway"],
                "depends_on": [],
                "execution_supported": False,
            }
        ],
    }
    revision.content = content
    revision.content_digest = plan_hash(content)
    decision = db.scalar(
        select(InfrastructurePlanDecisionRecord).where(
            InfrastructurePlanDecisionRecord.revision_id == revision.id
        )
    )
    assert decision is not None
    decision.approved_digest = revision.content_digest
    db.commit()
    return revision, connection


@pytest.mark.parametrize(
    ("operation", "phase", "detail", "expected_state"),
    [
        (
            "build-artifact",
            "artifact-build",
            {
                "artifact_s3_uri": "s3://runner-artifacts/artifact.zip",
                "artifact_sha256": "a" * 64,
                "source_commit": "b" * 40,
            },
            "ARTIFACT_READY",
        ),
        (
            "plan",
            "plan",
            {
                "saved_plan_s3_uri": "s3://runner-artifacts/plan.tfplan",
                "saved_plan_sha256": "c" * 64,
                "artifact_sha256": "a" * 64,
                "plan_summary": {"resource_changes": []},
            },
            "PLAN_READY_FOR_REVIEW",
        ),
        (
            "destroy-plan",
            "destroy-plan",
            {
                "saved_plan_s3_uri": "s3://runner-artifacts/destroy.tfplan",
                "saved_plan_sha256": "c" * 64,
                "artifact_sha256": "a" * 64,
                "plan_summary": {"resource_changes": []},
            },
            "DESTROY_PLAN_READY_FOR_REVIEW",
        ),
        (
            "apply-saved-plan",
            "apply",
            {
                "saved_plan_sha256": "c" * 64,
                "artifact_sha256": "a" * 64,
                "outputs": {
                    "api_endpoint": {
                        "sensitive": False,
                        "type": "string",
                        "value": "https://api.example",
                    },
                    "lambda_arn": {
                        "sensitive": False,
                        "type": "string",
                        "value": "arn:aws:lambda:us-east-1:123456789012:function:davdeploy-api",
                    },
                },
            },
            "SUCCEEDED_AWAITING_OBSERVATION",
        ),
        (
            "health",
            "health",
            {"endpoint": "https://api.example", "response": '{"ok":true}'},
            "HEALTHY",
        ),
        (
            "destroy-saved-plan",
            "destroy",
            {"saved_plan_sha256": "c" * 64, "cleanup": "confirmed_absent"},
            "DESTROYED_VERIFIED",
        ),
        (
            "verify-cleanup",
            "verify-cleanup",
            {"cleanup": "confirmed_absent"},
            "CLEANUP_VERIFIED",
        ),
    ],
)
def test_serverless_results_are_bound_to_the_typed_operation_and_get_truthful_states(
    monkeypatch, operation, phase, detail, expected_state
):
    service, _ = make_service()
    connection_id = "connection-123"
    build_id = f"davdeploy:serverless-{operation}"
    run = CloudExecutionRun(
        organization_id=founder().organization_id,
        revision_id=f"revision-{operation}",
        project_id=f"project-{operation}",
        profile="aws-serverless-api",
        state="SUBMITTED",
        mode="AUTHENTICATED_SERVERLESS_CERTIFICATION",
        attempt=1,
        command={"operation": operation},
        evidence={
            "result_s3_uri": f"s3://runner-results/{operation}/result.json",
            "execution_environment": {
                "DAVDEPLOY_CUSTOMER_CONNECTION_ID": connection_id,
                "DAVDEPLOY_CUSTOMER_PROJECT_ID": f"project-{operation}",
                "DAVDEPLOY_EXECUTION_OPERATION": operation,
                "DAVDEPLOY_CUSTOMER_SOURCE_COMMIT": "b" * 40,
                "DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI": "s3://runner-artifacts/artifact.zip",
                "DAVDEPLOY_SERVERLESS_ARTIFACT_SHA256": "a" * 64,
                "DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI": detail.get("saved_plan_s3_uri", ""),
                "DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256": "c" * 64,
            },
        },
        outputs={"codebuild_build_id": build_id},
        content_digest="d" * 64,
        requested_by_subject=operator().subject,
    )
    service.db.add(run)
    service.db.flush()
    module_instance = CloudExecutionModuleInstance(
        organization_id=run.organization_id,
        project_id=run.project_id,
        execution_run_id=run.id,
        instance_id="aws-serverless-api",
        module_id="aws-serverless-api",
        state="SUBMITTED",
        operation="apply",
        attempt=1,
        input_digest=run.content_digest,
        idempotency_key=f"{run.id}:aws-serverless-api",
        dependencies=[],
        outputs={},
        evidence={},
        version=2,
        runner_build_id=build_id,
    )
    service.db.add(module_instance)
    if phase == "health":
        service.db.add(
            CloudExecutionRun(
                organization_id=run.organization_id,
                revision_id=run.revision_id,
                project_id=run.project_id,
                profile="aws-serverless-api",
                state="SUCCEEDED_AWAITING_OBSERVATION",
                mode="AUTHENTICATED_SERVERLESS_CERTIFICATION",
                attempt=1,
                command={"operation": "apply-saved-plan"},
                evidence={},
                outputs={
                    "runner_artifact": {
                        "detail": {"outputs": {"api_endpoint": {"value": "https://api.example"}}}
                    }
                },
                content_digest=run.content_digest,
                requested_by_subject=operator().subject,
            )
        )
    service.db.commit()
    payload = {
        "schema_version": "davdeploy.customer_execution_result.v1",
        "run_id": run.id,
        "status": "SUCCEEDED",
        "connection_id": connection_id,
        "project_id": f"project-{operation}",
        "plan_digest": run.content_digest,
        "phase": phase,
        "detail": detail,
    }

    class Body:
        def read(self):
            return json.dumps(payload).encode()

    class CodeBuild:
        def batch_get_builds(self, *, ids):
            assert ids == [build_id]
            return {"builds": [{"buildStatus": "SUCCEEDED", "buildComplete": True}]}

    class S3:
        def get_object(self, *, Bucket, Key):
            assert (Bucket, Key) == ("runner-results", f"{operation}/result.json")
            return {"Body": Body()}

    monkeypatch.setattr(
        "davdeploy.service.boto3.client",
        lambda service_name: CodeBuild() if service_name == "codebuild" else S3(),
    )

    assert service.reconcile_cloud_execution_build(build_id) is True
    reconciled = service.db.get(CloudExecutionRun, run.id)
    assert reconciled.state == expected_state, reconciled.outputs.get("failure_reason")
    assert service.db.get(CloudExecutionRun, run.id).outputs["runner_artifact"] == payload
    if phase == "apply":
        persisted_module = service.db.get(CloudExecutionModuleInstance, module_instance.id)
        assert persisted_module is not None
        assert persisted_module.outputs == {
            "api_url": "https://api.example",
            "lambda_arn": "arn:aws:lambda:us-east-1:123456789012:function:davdeploy-api",
        }


def test_serverless_sensitive_renderer_output_is_rejected_and_not_persisted(monkeypatch):
    service, _ = make_service()
    build_id = "davdeploy:serverless-sensitive-output"
    run = CloudExecutionRun(
        organization_id=founder().organization_id,
        revision_id="revision-sensitive-output",
        project_id="project-sensitive-output",
        profile="aws-serverless-api",
        state="SUBMITTED",
        mode="AUTHENTICATED_SERVERLESS_CERTIFICATION",
        attempt=1,
        command={"operation": "apply-saved-plan"},
        evidence={
            "result_s3_uri": "s3://runner-results/sensitive/result.json",
            "execution_environment": {
                "DAVDEPLOY_CUSTOMER_CONNECTION_ID": "connection-sensitive",
                "DAVDEPLOY_CUSTOMER_PROJECT_ID": "project-sensitive-output",
                "DAVDEPLOY_EXECUTION_OPERATION": "apply-saved-plan",
                "DAVDEPLOY_SERVERLESS_ARTIFACT_SHA256": "a" * 64,
                "DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256": "c" * 64,
            },
        },
        outputs={"codebuild_build_id": build_id},
        content_digest="d" * 64,
        requested_by_subject=operator().subject,
    )
    service.db.add(run)
    service.db.flush()
    node = CloudExecutionModuleInstance(
        organization_id=run.organization_id,
        project_id=run.project_id,
        execution_run_id=run.id,
        instance_id="aws-serverless-api",
        module_id="aws-serverless-api",
        state="SUBMITTED",
        operation="apply",
        attempt=1,
        input_digest=run.content_digest,
        idempotency_key=f"{run.id}:aws-serverless-api",
        dependencies=[],
        outputs={},
        evidence={},
        version=2,
        runner_build_id=build_id,
    )
    service.db.add(node)
    service.db.commit()
    payload = {
        "schema_version": "davdeploy.customer_execution_result.v1",
        "run_id": run.id,
        "status": "SUCCEEDED",
        "connection_id": "connection-sensitive",
        "project_id": "project-sensitive-output",
        "plan_digest": run.content_digest,
        "phase": "apply",
        "detail": {
            "saved_plan_sha256": "c" * 64,
            "artifact_sha256": "a" * 64,
            "outputs": {
                "api_endpoint": {
                    "sensitive": False,
                    "type": "string",
                    "value": "https://api.example.test",
                },
                "lambda_arn": {
                    "sensitive": True,
                    "type": "string",
                    "value": "sensitive-value-must-not-be-persisted",
                },
            },
        },
    }

    class Body:
        def read(self):
            return json.dumps(payload).encode()

    class CodeBuild:
        def batch_get_builds(self, *, ids):
            assert ids == [build_id]
            return {"builds": [{"buildStatus": "SUCCEEDED", "buildComplete": True}]}

    class S3:
        def get_object(self, *, Bucket, Key):
            assert (Bucket, Key) == ("runner-results", "sensitive/result.json")
            return {"Body": Body()}

    monkeypatch.setattr(
        "davdeploy.service.boto3.client",
        lambda service_name: CodeBuild() if service_name == "codebuild" else S3(),
    )

    assert service.reconcile_cloud_execution_build(build_id) is True
    persisted_run = service.db.get(CloudExecutionRun, run.id)
    persisted_node = service.db.get(CloudExecutionModuleInstance, node.id)
    assert persisted_run is not None and persisted_run.state == "FAILED"
    assert persisted_run.outputs["runner_artifact"] is None
    assert persisted_run.outputs["terraform_outputs"] is None
    assert "sensitive-value-must-not-be-persisted" not in json.dumps(persisted_run.outputs)
    assert persisted_node is not None and persisted_node.outputs == {}


@pytest.mark.parametrize(
    "mismatch",
    [
        {"plan_digest": "e" * 64},
        {"connection_id": "another-connection"},
        {"project_id": "another-project"},
        {"phase": "apply"},
        {"run_id": "another-run"},
    ],
)
def test_serverless_result_mismatches_never_mark_the_run_successful(monkeypatch, mismatch):
    service, _ = make_service()
    build_id = "davdeploy:serverless-mismatch"
    run = CloudExecutionRun(
        organization_id=founder().organization_id,
        revision_id="revision-serverless-mismatch",
        project_id="project-serverless-mismatch",
        profile="aws-serverless-api",
        state="SUBMITTED",
        mode="AUTHENTICATED_SERVERLESS_CERTIFICATION",
        attempt=1,
        command={"operation": "build-artifact"},
        evidence={
            "result_s3_uri": "s3://runner-results/serverless-mismatch/result.json",
            "execution_environment": {
                "DAVDEPLOY_CUSTOMER_CONNECTION_ID": "connection-456",
                "DAVDEPLOY_CUSTOMER_PROJECT_ID": "project-serverless-mismatch",
                "DAVDEPLOY_EXECUTION_OPERATION": "build-artifact",
                "DAVDEPLOY_CUSTOMER_SOURCE_COMMIT": "b" * 40,
                "DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI": "s3://runner-artifacts/artifact.zip",
                "DAVDEPLOY_SERVERLESS_ARTIFACT_SHA256": "a" * 64,
            },
        },
        outputs={"codebuild_build_id": build_id},
        content_digest="f" * 64,
        requested_by_subject=operator().subject,
    )
    service.db.add(run)
    service.db.commit()
    payload = {
        "schema_version": "davdeploy.customer_execution_result.v1",
        "run_id": run.id,
        "status": "SUCCEEDED",
        "connection_id": "connection-456",
        "project_id": "project-serverless-mismatch",
        "plan_digest": run.content_digest,
        "phase": "artifact-build",
        "detail": {
            "artifact_s3_uri": "s3://runner-artifacts/artifact.zip",
            "artifact_sha256": "a" * 64,
            "source_commit": "b" * 40,
        },
        **mismatch,
    }

    class Body:
        def read(self):
            return json.dumps(payload).encode()

    class CodeBuild:
        def batch_get_builds(self, *, ids):
            return {"builds": [{"buildStatus": "SUCCEEDED", "buildComplete": True}]}

    class S3:
        def get_object(self, *, Bucket, Key):
            return {"Body": Body()}

    monkeypatch.setattr(
        "davdeploy.service.boto3.client",
        lambda service_name: CodeBuild() if service_name == "codebuild" else S3(),
    )

    assert service.reconcile_cloud_execution_build(build_id) is True
    assert service.db.get(CloudExecutionRun, run.id).state == "FAILED"


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

    environment = {key: "value" for key in CodeBuildCloudExecutionAdapter.required_environment}
    environment["DAVDEPLOY_EXECUTION_OPERATION"] = "apply-saved-plan"
    adapter = CodeBuildCloudExecutionAdapter("davdeploy-customer-executor", client=CodeBuild())

    result = adapter.execute({"environment": environment, "lifecycle_work": lifecycle_work()})

    assert result.state == "SUBMITTED"
    assert result.outputs["codebuild_build_id"] == "davdeploy:build-1"
    assert calls[0]["projectName"] == "davdeploy-customer-executor"
    assert all(item["name"] != "COMMAND" for item in calls[0]["environmentVariablesOverride"])
    assert any(
        item["name"] == "DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON"
        for item in calls[0]["environmentVariablesOverride"]
    )


def test_codebuild_adapter_accepts_typed_plan_work_for_plan_review():
    calls = []

    class CodeBuild:
        def start_build(self, **kwargs):
            calls.append(kwargs)
            return {"build": {"id": "davdeploy:plan-1", "arn": "arn:plan-1"}}

    environment = {key: "value" for key in CodeBuildCloudExecutionAdapter.required_environment}
    environment["DAVDEPLOY_EXECUTION_OPERATION"] = "destroy-plan"
    result = CodeBuildCloudExecutionAdapter("executor", client=CodeBuild()).execute(
        {"environment": environment, "lifecycle_work": lifecycle_work("plan")}
    )
    assert result.state == "SUBMITTED"
    manifest = next(
        item["value"]
        for item in calls[0]["environmentVariablesOverride"]
        if item["name"] == "DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON"
    )
    assert '"operation":"plan"' in manifest


def test_codebuild_adapter_requires_durable_certification_mode_for_serverless_renderer(monkeypatch):
    calls = []

    class CodeBuild:
        def start_build(self, **kwargs):
            calls.append(kwargs)
            return {"build": {"id": "davdeploy:serverless-1", "arn": "arn:serverless-1"}}

    monkeypatch.setenv("DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION", "true")
    environment = {key: "value" for key in CodeBuildCloudExecutionAdapter.required_environment}
    environment["DAVDEPLOY_EXECUTION_OPERATION"] = "health"
    work = [
        {
            "module_id": "aws-serverless-api",
            "operation": "observe",
            "dependencies": [],
            "resource_tags": {"ManagedBy": "davdeploy"},
        }
    ]
    adapter = CodeBuildCloudExecutionAdapter("executor", client=CodeBuild())
    blocked = adapter.execute(
        {
            "environment": environment,
            "lifecycle_work": work,
            "profile": "aws-serverless-api",
            "mode": "AUTHENTICATED_APP_RUNNER_APPLY",
        }
    )
    assert blocked.state == "FAILED"
    assert "not enabled" in (blocked.failure_reason or "")
    assert calls == []

    submitted = adapter.execute(
        {
            "environment": environment,
            "lifecycle_work": work,
            "profile": "aws-serverless-api",
            "mode": "AUTHENTICATED_SERVERLESS_CERTIFICATION",
        }
    )
    assert submitted.state == "SUBMITTED"
    manifest = next(
        item["value"]
        for item in calls[0]["environmentVariablesOverride"]
        if item["name"] == "DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON"
    )
    assert '"module_id":"aws-serverless-api"' in manifest
    assert "customer-workload-serverless-api" in manifest
    assert {
        "name": "DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION",
        "value": "true",
        "type": "PLAINTEXT",
    } in calls[0]["environmentVariablesOverride"]


def test_worker_builds_certification_context_from_persisted_run_mode():
    service, _ = make_service()
    run = CloudExecutionRun(
        organization_id=founder().organization_id,
        revision_id="revision-serverless-worker-context",
        project_id="project-serverless-worker-context",
        profile="aws-serverless-api",
        state="QUEUED",
        mode="AUTHENTICATED_SERVERLESS_CERTIFICATION",
        attempt=1,
        command={
            "universal_lifecycle_work": [
                {
                    "module_id": "aws-serverless-api",
                    "operation": "build_artifact",
                    "dependencies": [],
                    "resource_tags": {"ManagedBy": "davdeploy"},
                }
            ]
        },
        evidence={"execution_environment": {"DAVDEPLOY_EXECUTION_OPERATION": "build-artifact"}},
        outputs={},
        content_digest="a" * 64,
        requested_by_subject=operator().subject,
    )
    service.db.add(run)
    service.db.flush()
    service.db.add(
        CloudExecutionModuleInstance(
            organization_id=run.organization_id,
            project_id=run.project_id,
            execution_run_id=run.id,
            instance_id="aws-serverless-api",
            module_id="aws-serverless-api",
            state="NOT_DISPATCHED",
            operation="apply",
            attempt=0,
            input_digest=run.content_digest,
            idempotency_key=f"{run.id}:aws-serverless-api",
            dependencies=[],
            outputs={},
            evidence={},
            version=1,
        )
    )
    service.db.commit()

    class CapturingAdapter:
        def __init__(self):
            self.context = None

        def execute(self, context):
            self.context = context
            return CloudExecutionResult("SUBMITTED", (), {"codebuild_build_id": "serverless-1"})

    adapter = CapturingAdapter()
    service.cloud_execution = adapter
    assert service.run_next_cloud_execution() is True
    assert adapter.context["profile"] == "aws-serverless-api"
    assert adapter.context["mode"] == "AUTHENTICATED_SERVERLESS_CERTIFICATION"
    assert adapter.context["lifecycle_work"][0]["operation"] == "build_artifact"
    node = service.db.scalar(
        select(CloudExecutionModuleInstance).where(
            CloudExecutionModuleInstance.execution_run_id == run.id
        )
    )
    assert node is not None
    assert node.runner_build_id == "serverless-1"
    assert node.evidence["runner_build_id"] == "serverless-1"


def test_serverless_certification_run_chains_pinned_artifact_and_saved_plan(monkeypatch):
    service, db = make_service()
    revision, connection = approved_serverless_customer_review(service, db)
    allow_serverless_certification(monkeypatch, founder().organization_id)
    source_commit = "b" * 40

    class GitHubResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"sha": source_commit}

    monkeypatch.setattr("davdeploy.service.httpx.get", lambda *args, **kwargs: GitHubResponse())
    wakeups = []
    monkeypatch.setattr(service, "_wake_worker", lambda kind, run_id: wakeups.append(run_id))

    artifact = service.create_cloud_execution_run_for_revision(
        operator(),
        revision.id,
        content_digest=revision.content_digest,
        terraform_render_id=None,
        preflight_id=None,
        terraform_plan_review_id=None,
        expected_account_id=connection.account_id,
        expected_region="us-east-1",
        mode="AUTHENTICATED_SERVERLESS_CERTIFICATION",
        confirmation=None,
        serverless_operation="build-artifact",
        source_commit=source_commit,
    )
    assert artifact["profile"] == "aws-serverless-api"
    assert artifact["state"] == "READY_FOR_OPERATOR_SERVERLESS_CERTIFICATION"
    assert artifact["evidence"]["execution_environment"][
        "DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI"
    ].endswith(f"/{artifact['id']}/lambda.zip")
    assert (
        service.queue_cloud_execution_run(
            operator(),
            artifact["id"],
            revision.content_digest,
            "RUN_SERVERLESS_CERTIFICATION_PHASE",
        )["state"]
        == "QUEUED"
    )
    assert wakeups == [artifact["id"]]

    artifact_run = db.get(CloudExecutionRun, artifact["id"])
    assert artifact_run is not None
    artifact_environment = dict(artifact_run.evidence["execution_environment"])
    artifact_run.state = "ARTIFACT_READY"
    artifact_run.outputs = {
        "runner_artifact": {
            "detail": {
                "artifact_s3_uri": artifact_environment["DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI"],
                "artifact_sha256": "a" * 64,
                "source_commit": source_commit,
            }
        }
    }
    db.commit()

    with pytest.raises(ValueError, match="prior lifecycle run is not eligible"):
        service.create_cloud_execution_run_for_revision(
            operator(),
            revision.id,
            content_digest=revision.content_digest,
            terraform_render_id=None,
            preflight_id=None,
            terraform_plan_review_id=None,
            expected_account_id=connection.account_id,
            expected_region="us-east-1",
            mode="AUTHENTICATED_SERVERLESS_CERTIFICATION",
            confirmation="APPLY_SERVERLESS_API_SAVED_PLAN",
            serverless_operation="apply-saved-plan",
            prior_run_id=artifact["id"],
        )

    plan = service.create_cloud_execution_run_for_revision(
        operator(),
        revision.id,
        content_digest=revision.content_digest,
        terraform_render_id=None,
        preflight_id=None,
        terraform_plan_review_id=None,
        expected_account_id=connection.account_id,
        expected_region="us-east-1",
        mode="AUTHENTICATED_SERVERLESS_CERTIFICATION",
        confirmation=None,
        serverless_operation="plan",
        prior_run_id=artifact["id"],
    )
    plan_run = db.get(CloudExecutionRun, plan["id"])
    assert plan_run is not None
    plan_environment = plan_run.evidence["execution_environment"]
    assert (
        plan_environment["DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI"]
        == artifact_environment["DAVDEPLOY_SERVERLESS_ARTIFACT_S3_URI"]
    )
    assert plan_environment["DAVDEPLOY_SERVERLESS_ARTIFACT_SHA256"] == "a" * 64
    assert (
        f"/{revision.content_digest}/apply/{plan['id']}.tfplan"
        == plan_environment["DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI"][
            len(
                "s3://customer-state/davdeploy/customer/"
                f"{connection.id}/projects/{plan_run.project_id}"
            ) :
        ]
    )

    plan_run.state = "PLAN_READY_FOR_REVIEW"
    plan_run.outputs = {
        "runner_artifact": {
            "detail": {
                "saved_plan_s3_uri": plan_environment["DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI"],
                "saved_plan_sha256": "c" * 64,
                "artifact_sha256": "a" * 64,
                "plan_summary": {"resource_changes": []},
            }
        }
    }
    db.commit()
    with pytest.raises(ValueError, match="explicit APPLY_SERVERLESS_API_SAVED_PLAN"):
        service.create_cloud_execution_run_for_revision(
            operator(),
            revision.id,
            content_digest=revision.content_digest,
            terraform_render_id=None,
            preflight_id=None,
            terraform_plan_review_id=None,
            expected_account_id=connection.account_id,
            expected_region="us-east-1",
            mode="AUTHENTICATED_SERVERLESS_CERTIFICATION",
            confirmation="wrong",
            serverless_operation="apply-saved-plan",
            prior_run_id=plan["id"],
        )

    apply_run = service.create_cloud_execution_run_for_revision(
        operator(),
        revision.id,
        content_digest=revision.content_digest,
        terraform_render_id=None,
        preflight_id=None,
        terraform_plan_review_id=None,
        expected_account_id=connection.account_id,
        expected_region="us-east-1",
        mode="AUTHENTICATED_SERVERLESS_CERTIFICATION",
        confirmation="APPLY_SERVERLESS_API_SAVED_PLAN",
        serverless_operation="apply-saved-plan",
        prior_run_id=plan["id"],
    )
    apply_environment = db.get(CloudExecutionRun, apply_run["id"]).evidence["execution_environment"]
    assert (
        apply_environment["DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI"]
        == plan_environment["DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI"]
    )
    assert apply_environment["DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256"] == "c" * 64
    with pytest.raises(ValueError, match="already been submitted"):
        service.create_cloud_execution_run_for_revision(
            operator(),
            revision.id,
            content_digest=revision.content_digest,
            terraform_render_id=None,
            preflight_id=None,
            terraform_plan_review_id=None,
            expected_account_id=connection.account_id,
            expected_region="us-east-1",
            mode="AUTHENTICATED_SERVERLESS_CERTIFICATION",
            confirmation="APPLY_SERVERLESS_API_SAVED_PLAN",
            serverless_operation="apply-saved-plan",
            prior_run_id=plan["id"],
        )

    apply_record = db.get(CloudExecutionRun, apply_run["id"])
    assert apply_record is not None
    apply_record.state = "SUCCEEDED_AWAITING_OBSERVATION"
    apply_record.outputs = {
        "runner_artifact": {
            "detail": {
                "saved_plan_sha256": "c" * 64,
                "artifact_sha256": "a" * 64,
                "outputs": {"api_endpoint": {"value": "https://api.example"}},
            }
        }
    }
    db.commit()

    health = service.create_cloud_execution_run_for_revision(
        operator(),
        revision.id,
        content_digest=revision.content_digest,
        terraform_render_id=None,
        preflight_id=None,
        terraform_plan_review_id=None,
        expected_account_id=connection.account_id,
        expected_region="us-east-1",
        mode="AUTHENTICATED_SERVERLESS_CERTIFICATION",
        confirmation=None,
        serverless_operation="health",
        prior_run_id=apply_run["id"],
    )
    health_record = db.get(CloudExecutionRun, health["id"])
    assert health_record is not None
    health_environment = health_record.evidence["execution_environment"]
    assert (
        health_environment["DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI"]
        == apply_environment["DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI"]
    )
    health_record.state = "HEALTHY"
    health_record.outputs = {
        "runner_artifact": {
            "detail": {"endpoint": "https://api.example", "response": '{"ok":true}'}
        }
    }
    db.commit()

    destroy_plan = service.create_cloud_execution_run_for_revision(
        operator(),
        revision.id,
        content_digest=revision.content_digest,
        terraform_render_id=None,
        preflight_id=None,
        terraform_plan_review_id=None,
        expected_account_id=connection.account_id,
        expected_region="us-east-1",
        mode="AUTHENTICATED_SERVERLESS_CERTIFICATION",
        confirmation=None,
        serverless_operation="destroy-plan",
        prior_run_id=health["id"],
    )
    destroy_plan_record = db.get(CloudExecutionRun, destroy_plan["id"])
    assert destroy_plan_record is not None
    destroy_plan_environment = destroy_plan_record.evidence["execution_environment"]
    assert (
        f"/{revision.content_digest}/destroy/{destroy_plan['id']}.tfplan"
        in destroy_plan_environment["DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI"]
    )
    destroy_plan_record.state = "DESTROY_PLAN_READY_FOR_REVIEW"
    destroy_plan_record.outputs = {
        "runner_artifact": {
            "detail": {
                "saved_plan_s3_uri": destroy_plan_environment[
                    "DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI"
                ],
                "saved_plan_sha256": "d" * 64,
                "artifact_sha256": "a" * 64,
                "plan_summary": {"resource_changes": []},
            }
        }
    }
    db.commit()

    destroy = service.create_cloud_execution_run_for_revision(
        operator(),
        revision.id,
        content_digest=revision.content_digest,
        terraform_render_id=None,
        preflight_id=None,
        terraform_plan_review_id=None,
        expected_account_id=connection.account_id,
        expected_region="us-east-1",
        mode="AUTHENTICATED_SERVERLESS_CERTIFICATION",
        confirmation="DESTROY_SERVERLESS_API_SAVED_PLAN",
        serverless_operation="destroy-saved-plan",
        prior_run_id=destroy_plan["id"],
    )
    destroy_record = db.get(CloudExecutionRun, destroy["id"])
    assert destroy_record is not None
    destroy_environment = destroy_record.evidence["execution_environment"]
    assert (
        destroy_environment["DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI"]
        == destroy_plan_environment["DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI"]
    )
    assert destroy_environment["DAVDEPLOY_EXECUTION_SAVED_PLAN_SHA256"] == "d" * 64
    destroy_record.state = "DESTROYED_VERIFIED"
    destroy_record.outputs = {
        "runner_artifact": {
            "detail": {"saved_plan_sha256": "d" * 64, "cleanup": "confirmed_absent"}
        }
    }
    db.commit()

    cleanup = service.create_cloud_execution_run_for_revision(
        operator(),
        revision.id,
        content_digest=revision.content_digest,
        terraform_render_id=None,
        preflight_id=None,
        terraform_plan_review_id=None,
        expected_account_id=connection.account_id,
        expected_region="us-east-1",
        mode="AUTHENTICATED_SERVERLESS_CERTIFICATION",
        confirmation=None,
        serverless_operation="verify-cleanup",
        prior_run_id=destroy["id"],
    )
    cleanup_record = db.get(CloudExecutionRun, cleanup["id"])
    assert cleanup_record is not None
    cleanup_environment = cleanup_record.evidence["execution_environment"]
    assert (
        f"/{revision.content_digest}/apply/{destroy['id']}.tfplan"
        in cleanup_environment["DAVDEPLOY_EXECUTION_SAVED_PLAN_S3_URI"]
    )


def test_serverless_certification_requires_an_explicit_workspace_allowlist(monkeypatch):
    service, db = make_service()
    revision, connection = approved_serverless_customer_review(service, db)
    monkeypatch.setenv("DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION", "true")
    monkeypatch.setenv("DAVDEPLOY_SERVERLESS_CERTIFICATION_WORKSPACE_IDS", "another-workspace")

    with pytest.raises(PermissionError, match="not allowlisted"):
        service.create_cloud_execution_run_for_revision(
            operator(),
            revision.id,
            content_digest=revision.content_digest,
            terraform_render_id=None,
            preflight_id=None,
            terraform_plan_review_id=None,
            expected_account_id=connection.account_id,
            expected_region="us-east-1",
            mode="AUTHENTICATED_SERVERLESS_CERTIFICATION",
            confirmation=None,
            serverless_operation="build-artifact",
            source_commit="b" * 40,
        )
    assert service.cloud_execution_runs(operator()) == []


def test_app_runner_mode_rejects_serverless_lifecycle_fields():
    service, _ = make_service()
    approved = approved_app_runner_customer_review(service)
    with pytest.raises(ValueError, match="require certification mode"):
        service.create_cloud_execution_run_for_revision(
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
            serverless_operation="build-artifact",
        )


def test_codebuild_adapter_constructs_only_the_fixed_app_runner_image_build_work():
    calls = []

    class CodeBuild:
        def start_build(self, **kwargs):
            calls.append(kwargs)
            return {"build": {"id": "davdeploy:image-1", "arn": "arn:image-1"}}

    environment = {key: "value" for key in CodeBuildCloudExecutionAdapter.required_environment}
    environment["DAVDEPLOY_EXECUTION_OPERATION"] = "build-push-image"
    result = CodeBuildCloudExecutionAdapter("executor", client=CodeBuild()).execute(
        {"environment": environment}
    )
    assert result.state == "SUBMITTED"
    manifest = next(
        item["value"]
        for item in calls[0]["environmentVariablesOverride"]
        if item["name"] == "DAVDEPLOY_UNIVERSAL_LIFECYCLE_WORK_JSON"
    )
    assert '"module_id":"aws-managed-application"' in manifest
    assert '"operation":"build-push-image"' in manifest


def test_authenticated_plan_review_submits_typed_plan_work_to_the_worker(monkeypatch):
    service, db = make_service()
    approved = approved_app_runner_customer_review(service)
    connection = service.create_cloud_connection(
        founder(), "Verified test cloud", "aws", "byoc_role_contract"
    )
    connection.setup_state = "VERIFIED"
    connection.account_id = "654654474502"
    connection.execution_role_arn = "arn:aws:iam::654654474502:role/davdeployExecution-test"
    connection.external_id_secret_ref = "arn:aws:secretsmanager:us-east-1:654654474502:secret:test"
    revision = db.get(InfrastructurePlanRevision, approved.id)
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
    decision = db.scalar(
        select(InfrastructurePlanDecisionRecord).where(
            InfrastructurePlanDecisionRecord.revision_id == revision.id
        )
    )
    assert decision is not None
    decision.approved_digest = revision.content_digest
    db.commit()
    preflight = ready_app_runner_preflight(service, db, revision)
    monkeypatch.setenv("ALLOW_CLOUD_PLAN", "true")
    monkeypatch.setenv("DAVDEPLOY_CUSTOMER_EXECUTION_STATE_BUCKET", "customer-state")
    monkeypatch.setenv("DAVDEPLOY_CUSTOMER_EXECUTION_LOCK_TABLE", "customer-locks")
    monkeypatch.setenv("DAVDEPLOY_CUSTOMER_EXECUTION_ARTIFACT_S3_URI", "s3://releases/runner.zip")
    monkeypatch.setenv("DAVDEPLOY_ENABLE_APP_RUNNER_EXECUTION", "true")
    monkeypatch.setenv("DAVDEPLOY_CLOUD_EXECUTION_COMMAND_ENABLED", "true")

    class Submitted:
        def __init__(self):
            self.contexts = []

        def execute(self, context):
            self.contexts.append(context)
            return CloudExecutionResult("SUBMITTED", (), {"codebuild_build_id": "plan-1"})

    adapter = Submitted()
    service.cloud_execution = adapter
    review = service.create_terraform_plan_review_for_revision(
        operator(),
        approved.id,
        content_digest=revision.content_digest,
        preflight_id=preflight["id"],
        expected_account_id=None,
        expected_region="us-east-1",
        mode="AUTHENTICATED_TERRAFORM_PLAN",
        allow_cloud_plan=True,
    )
    assert review["state"] == "AUTHENTICATED_PLAN_SUBMITTED"
    work = adapter.contexts[0]["lifecycle_work"]
    assert work[0]["module_id"] == "aws-managed-application"
    assert work[0]["operation"] == "plan"
    plan_run = db.scalar(
        select(CloudExecutionRun).where(CloudExecutionRun.terraform_plan_review_id == review["id"])
    )
    assert plan_run is not None
    assert plan_run.command["universal_lifecycle_work"] == work


def test_codebuild_adapter_rejects_untyped_lifecycle_work_without_a_cloud_call():
    calls = []

    class CodeBuild:
        def start_build(self, **kwargs):
            calls.append(kwargs)
            return {"build": {"id": "unexpected"}}

    environment = {key: "value" for key in CodeBuildCloudExecutionAdapter.required_environment}
    result = CodeBuildCloudExecutionAdapter("executor", client=CodeBuild()).execute(
        {"environment": environment, "lifecycle_work": [{"command": "terraform apply"}]}
    )
    assert result.state == "FAILED"
    assert "module identifier" in (result.failure_reason or "")
    assert calls == []


def test_codebuild_adapter_rejects_composed_runs_until_all_module_states_are_supported():
    calls = []

    class CodeBuild:
        def start_build(self, **kwargs):
            calls.append(kwargs)
            return {"build": {"id": "unexpected"}}

    environment = {key: "value" for key in CodeBuildCloudExecutionAdapter.required_environment}
    work = lifecycle_work() + [
        {
            "module_id": "aws-serverless-api",
            "operation": "apply",
            "dependencies": [],
            "resource_tags": {"ManagedBy": "davdeploy"},
        }
    ]
    result = CodeBuildCloudExecutionAdapter("executor", client=CodeBuild()).execute(
        {
            "environment": environment,
            "lifecycle_work": work,
            "mode": "AUTHENTICATED_SERVERLESS_CERTIFICATION",
            "profile": "aws-serverless-api",
        }
    )
    assert result.state == "FAILED"
    assert "one certified module" in (result.failure_reason or "")
    assert calls == []


def test_codebuild_adapter_rejects_incomplete_graph_before_renderer_or_cloud_call():
    calls = []

    class CodeBuild:
        def start_build(self, **kwargs):
            calls.append(kwargs)
            return {"build": {"id": "unexpected"}}

    environment = {key: "value" for key in CodeBuildCloudExecutionAdapter.required_environment}
    work = lifecycle_work() + [
        {
            "module_id": "aws-serverless-api",
            "operation": "apply",
            "dependencies": ["missing"],
            "resource_tags": {"ManagedBy": "davdeploy"},
        }
    ]
    result = CodeBuildCloudExecutionAdapter("executor", client=CodeBuild()).execute(
        {"environment": environment, "lifecycle_work": work}
    )
    assert result.state == "FAILED"
    assert "missing modules" in (result.failure_reason or "")
    assert calls == []


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
    primary = CloudExecutionModuleInstance(
        organization_id=run.organization_id,
        project_id=run.project_id,
        execution_run_id=run.id,
        instance_id="primary-module",
        module_id="aws-managed-application",
        state="SUBMITTED",
        operation="apply",
        attempt=1,
        input_digest=run.content_digest,
        idempotency_key=f"{run.id}:primary-module",
        dependencies=[],
        outputs={},
        evidence={},
        version=2,
        runner_build_id=short_id,
    )
    secondary = CloudExecutionModuleInstance(
        organization_id=run.organization_id,
        project_id=run.project_id,
        execution_run_id=run.id,
        instance_id="secondary-module",
        module_id="aws-managed-application",
        state="NOT_DISPATCHED",
        operation="apply",
        attempt=0,
        input_digest=run.content_digest,
        idempotency_key=f"{run.id}:secondary-module",
        dependencies=[],
        outputs={},
        evidence={},
        version=1,
    )
    run.module_instances.extend([primary, secondary])
    service.db.commit()
    calls = []

    class CodeBuild:
        def batch_get_builds(self, *, ids):
            calls.append(ids)
            return {"builds": [{"buildStatus": "FAILED"}]}

    monkeypatch.setattr("davdeploy.service.boto3.client", lambda service_name: CodeBuild())

    assert service.reconcile_cloud_execution_build(build_arn) is True
    assert calls == [[short_id]]
    assert service.db.get(CloudExecutionModuleInstance, primary.id).state == "FAILED"
    assert service.db.get(CloudExecutionModuleInstance, secondary.id).state == "NOT_DISPATCHED"


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
        outputs={
            "codebuild_build_id": build_id,
            "failure_reason": "runner result artifact URI is missing",
        },
        content_digest="b" * 64,
        requested_by_subject=founder().subject,
    )
    service.db.add(run)
    service.db.commit()

    class Body:
        def read(self):
            return (
                '{"run_id": "' + run.id + '", "status": "SUCCEEDED", "detail": {"output": "ok"}}'
            ).encode()

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


def test_run_creation_persists_repeated_module_types_as_distinct_instances():
    service, db = make_service()
    approved = approved_app_runner_customer_review(service)
    revision = db.get(InfrastructurePlanRevision, approved.id)
    assert revision is not None
    content = dict(revision.content)
    content["architecture"] = {
        **content["architecture"],
        "modules": [
            {
                "identifier": "aws-managed-application",
                "instance_id": "public-app",
                "display_name": "Public application",
                "purpose": "customer-facing application",
                "stage": "production",
                "services": ["App Runner"],
                "depends_on": [],
                "execution_supported": False,
            },
            {
                "identifier": "aws-managed-application",
                "instance_id": "admin-app",
                "display_name": "Admin application",
                "purpose": "administrative application",
                "stage": "production",
                "services": ["App Runner"],
                "depends_on": [],
                "execution_supported": False,
            },
        ],
    }
    revision.content = content
    revision.content_digest = plan_hash(content)
    decision = db.scalar(
        select(InfrastructurePlanDecisionRecord).where(
            InfrastructurePlanDecisionRecord.revision_id == revision.id
        )
    )
    assert decision is not None
    decision.approved_digest = revision.content_digest
    db.commit()

    run = service.create_cloud_execution_run_for_revision(
        operator(),
        approved.id,
        content_digest=revision.content_digest,
        terraform_render_id=None,
        preflight_id=None,
        terraform_plan_review_id=None,
        expected_account_id=None,
        expected_region=None,
        mode="GUARDED_CLOUD_EXECUTION",
        confirmation=None,
    )

    graph_modules = run["evidence"]["universal_execution"]["modules"]
    persisted = run["module_instances"]
    assert [(item["module_id"], item["instance_id"]) for item in persisted] == [
        ("aws-managed-application", "public-app"),
        ("aws-managed-application", "admin-app"),
    ]
    assert [(item["module_id"], item["instance_id"]) for item in graph_modules] == [
        ("aws-managed-application", "public-app"),
        ("aws-managed-application", "admin-app"),
    ]
    persisted_rows = db.get(CloudExecutionRun, run["id"]).module_instances
    assert [item.idempotency_key for item in persisted_rows] == [
        f"{run['id']}:public-app",
        f"{run['id']}:admin-app",
    ]


def test_ready_cloud_run_is_queued_and_observed_by_trusted_worker():
    service, _ = make_service()
    adapter = FakeCloudExecutionAdapter()
    service.cloud_execution = adapter
    approved = approved_app_runner_customer_review(service)
    render = service.create_terraform_plan_render_for_revision(
        founder(), approved.id, approved.content_digest
    )
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
    module_instances = run["module_instances"]
    assert module_instances
    assert {item["instance_id"] for item in module_instances} == {
        item["id"] for item in run["evidence"]["universal_execution"]["modules"]
    }
    assert all(item["state"] == "NOT_DISPATCHED" for item in module_instances)
    assert all(item["project_id"] == run["project_id"] for item in module_instances)
    assert all(item["input_digest"] == run["content_digest"] for item in module_instances)
    assert len({item["instance_id"] for item in module_instances}) == len(module_instances)
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


def test_module_instance_outcomes_are_idempotent_scoped_and_terminal():
    service, _ = make_service()
    approved = approved_app_runner_customer_review(service)
    created = service.create_cloud_execution_run_for_revision(
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
    run = service.db.get(CloudExecutionRun, created["id"])
    assert run is not None and run.module_instances
    node = run.module_instances[0]

    service._advance_cloud_execution_module_instances(run, "QUEUED")
    service._advance_cloud_execution_module_instances(run, "RUNNING")
    service._advance_cloud_execution_module_instances(run, "SUCCEEDED_AWAITING_OBSERVATION")
    version = node.version
    service._advance_cloud_execution_module_instances(run, "SUCCEEDED_AWAITING_OBSERVATION")
    assert node.version == version
    assert node.state == "SUCCEEDED_AWAITING_OBSERVATION"
    assert [item["to"] for item in node.evidence["transitions"]] == [
        "QUEUED",
        "RUNNING",
        "SUCCEEDED_AWAITING_OBSERVATION",
    ]

    with pytest.raises(ValueError, match="cannot be replayed or overwritten"):
        service._advance_cloud_execution_module_instances(run, "HEALTHY")

    node.project_id = "another-project"
    with pytest.raises(ValueError, match="outside its execution run scope"):
        service._advance_cloud_execution_module_instances(run, "FAILED")


def test_module_specific_outcomes_persist_only_the_selected_scoped_row():
    service, _ = make_service()
    approved = approved_app_runner_customer_review(service)
    created = service.create_cloud_execution_run_for_revision(
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
    run = service.db.get(CloudExecutionRun, created["id"])
    assert run is not None and run.module_instances
    primary = run.module_instances[0]
    primary.module_id = "aws-serverless-api"
    secondary = CloudExecutionModuleInstance(
        organization_id=run.organization_id,
        project_id=run.project_id,
        execution_run_id=run.id,
        instance_id="independent-module",
        module_id="aws-serverless-api",
        state="NOT_DISPATCHED",
        operation=primary.operation,
        attempt=0,
        input_digest=run.content_digest,
        idempotency_key=f"{run.id}:independent-module",
        dependencies=[],
        outputs={},
        evidence={},
        version=1,
    )
    run.module_instances.append(secondary)
    service.db.flush()

    outcome = ModuleLifecycleOutcome(
        state="QUEUED",
        outputs={"api_url": "https://api.example.test"},
        evidence={"runner": "fixed-registry"},
    )
    service._advance_cloud_execution_module_instances(
        run, module_outcomes={primary.instance_id: outcome}
    )
    assert primary.state == "QUEUED"
    assert primary.outputs == {"api_url": "https://api.example.test"}
    assert primary.evidence["module_outcome"] == {"runner": "fixed-registry"}
    assert secondary.state == "NOT_DISPATCHED"

    version = primary.version
    service._advance_cloud_execution_module_instances(
        run, module_outcomes={primary.instance_id: outcome}
    )
    assert primary.version == version
    with pytest.raises(ValueError, match="cannot overwrite"):
        service._advance_cloud_execution_module_instances(
            run,
            module_outcomes={
                primary.instance_id: ModuleLifecycleOutcome(
                    state="QUEUED", outputs={"api_url": "https://changed.example.test"}
                )
            },
        )
    with pytest.raises(ValueError, match="outside its execution run graph"):
        service._advance_cloud_execution_module_instances(
            run, module_outcomes={"unowned-module": ModuleLifecycleOutcome(state="QUEUED")}
        )

    with pytest.raises(ValueError, match="invalid https_url value"):
        service._advance_cloud_execution_module_instances(
            run,
            module_outcomes={
                primary.instance_id: ModuleLifecycleOutcome(
                    state="RUNNING", outputs={"api_url": "http://api.example.test"}
                )
            },
        )


def test_module_instance_records_reconciliation_required_after_worker_loss():
    service, _ = make_service()
    approved = approved_app_runner_customer_review(service)
    created = service.create_cloud_execution_run_for_revision(
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
    run = service.db.get(CloudExecutionRun, created["id"])
    assert run is not None and run.module_instances
    node = run.module_instances[0]

    for state in ("QUEUED", "RUNNING", "RECONCILIATION_REQUIRED"):
        service._advance_cloud_execution_module_instances(run, state)

    assert node.state == "RECONCILIATION_REQUIRED"
    assert [event["to"] for event in node.evidence["transitions"]] == [
        "QUEUED",
        "RUNNING",
        "RECONCILIATION_REQUIRED",
    ]


def test_submitted_codebuild_outcome_advances_module_without_claiming_health():
    service, _ = make_service()
    approved = approved_app_runner_customer_review(service)
    created = service.create_cloud_execution_run_for_revision(
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
    run = service.db.get(CloudExecutionRun, created["id"])
    assert run is not None and run.module_instances
    node = run.module_instances[0]

    for state in ("QUEUED", "RUNNING", "SUBMITTED", "PLAN_READY_FOR_REVIEW"):
        service._advance_cloud_execution_module_instances(run, state)

    assert node.state == "PLAN_READY_FOR_REVIEW"
    assert [item["to"] for item in node.evidence["transitions"]] == [
        "QUEUED",
        "RUNNING",
        "SUBMITTED",
        "PLAN_READY_FOR_REVIEW",
    ]


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
    monkeypatch.setattr(
        service, "_wake_worker", lambda kind, job_id: wakeups.append((kind, job_id))
    )

    queued = service.queue_cloud_execution_run(
        operator(), run.id, run.content_digest, "EXECUTE_APP_RUNNER_WORKLOAD"
    )

    assert queued["state"] == "QUEUED"
    assert wakeups == [("cloud_execution", run.id)]


def _queued_cloud_execution_run(service):
    run = CloudExecutionRun(
        organization_id=founder().organization_id,
        revision_id="revision-lease-test",
        project_id="project-lease-test",
        profile="aws-app-runner",
        state="QUEUED",
        mode="AUTHENTICATED_APP_RUNNER_APPLY",
        attempt=1,
        command={},
        evidence={},
        outputs={},
        content_digest="d" * 64,
        requested_by_subject=founder().subject,
    )
    service.db.add(run)
    service.db.commit()
    return run


def test_cloud_execution_worker_claim_is_exclusive_and_keeps_token_private():
    service, _ = make_service()
    run = _queued_cloud_execution_run(service)

    first_claim = service._claim_next_cloud_execution_run()
    second_claim = service._claim_next_cloud_execution_run()

    assert first_claim is not None
    claimed_run, lease_token = first_claim
    assert second_claim is None
    assert claimed_run.state == "RUNNING"
    assert claimed_run.worker_lease_token == lease_token
    assert claimed_run.attempt == 1
    assert claimed_run.worker_claim_version == 1
    assert claimed_run.worker_lease_expires_at is not None
    public_payload = service._cloud_execution_run_payload(claimed_run)
    assert lease_token not in json.dumps(public_payload)
    assert run.id == claimed_run.id


def test_expired_cloud_execution_lease_requires_reconciliation_without_replay(
    monkeypatch,
):
    service, _ = make_service()
    run = _queued_cloud_execution_run(service)
    claim = service._claim_next_cloud_execution_run()
    assert claim is not None
    claimed_run, lease_token = claim
    claimed_run.worker_lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    service.db.commit()
    monkeypatch.setattr("davdeploy.service._last_cloud_execution_lease_scan", 0.0)
    monkeypatch.setattr("davdeploy.service.CLOUD_EXECUTION_LEASE_SCAN_SECONDS", 0)

    service._scan_expired_cloud_execution_leases()

    refreshed = service.db.get(CloudExecutionRun, run.id)
    assert refreshed is not None
    assert refreshed.state == "RECONCILIATION_REQUIRED"
    assert refreshed.worker_lease_token is None
    assert refreshed.worker_lease_expires_at is None
    assert refreshed.evidence["worker_reconciliation"]["automatic_replay"] is False
    stale_result = CloudExecutionResult("READY", (), {"unexpected": True})
    assert service._complete_cloud_execution_claim(run.id, lease_token, stale_result) is False
    assert service.db.get(CloudExecutionRun, run.id).outputs == {}


def test_prelease_running_record_is_not_assumed_abandoned():
    service, _ = make_service()
    run = CloudExecutionRun(
        organization_id=founder().organization_id,
        revision_id="revision-legacy-running",
        project_id="project-legacy-running",
        profile="aws-app-runner",
        state="RUNNING",
        mode="AUTHENTICATED_APP_RUNNER_APPLY",
        attempt=1,
        command={},
        evidence={},
        outputs={},
        content_digest="e" * 64,
        requested_by_subject=founder().subject,
    )
    service.db.add(run)
    service.db.commit()
    service._scan_expired_cloud_execution_leases()

    persisted = service.db.get(CloudExecutionRun, run.id)
    assert persisted is not None
    assert persisted.state == "RUNNING"
    assert persisted.worker_lease_token is None


def test_adapter_exception_marks_run_uncertain_without_requeueing():
    service, _ = make_service()
    run = _queued_cloud_execution_run(service)

    class UncertainAdapter:
        def execute(self, context):
            del context
            raise TimeoutError("result not known")

    service.cloud_execution = UncertainAdapter()

    assert service.run_next_cloud_execution() is True
    persisted = service.db.get(CloudExecutionRun, run.id)
    assert persisted is not None
    assert persisted.state == "RECONCILIATION_REQUIRED"
    assert persisted.worker_lease_token is None
    assert persisted.evidence["worker_reconciliation"]["automatic_replay"] is False
    assert service.run_next_cloud_execution() is False


def test_worker_records_configured_adapter_result_and_releases_lease():
    service, _ = make_service()
    run = _queued_cloud_execution_run(service)
    service.cloud_execution = DisabledCloudExecutionAdapter()

    assert service.run_next_cloud_execution() is True

    persisted = service.db.get(CloudExecutionRun, run.id)
    assert persisted is not None
    assert persisted.state == "BLOCKED_CLOUD_EXECUTION_NOT_ENABLED"
    assert persisted.worker_lease_token is None
    assert persisted.worker_lease_expires_at is None
    assert persisted.worker_claim_version == 1
    assert persisted.attempt == 1
    assert persisted.outputs["failure_reason"]


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
        "target": {
            **revision.content["target"],
            "connection_id": connection.id,
            "account_id": connection.account_id,
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
        outputs={
            "terraform_outputs": {
                "ecr_repository_url": {
                    "value": f"654654474502.dkr.ecr.us-east-1.amazonaws.com/davdeploy-{connection.id}-workload"
                }
            }
        },
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
    assert persisted.evidence["execution_environment"][
        "DAVDEPLOY_CUSTOMER_ECR_REPOSITORY_URL"
    ].endswith("-workload")
