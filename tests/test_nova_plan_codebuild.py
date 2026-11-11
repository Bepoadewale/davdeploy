from __future__ import annotations

import ast
import hashlib
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import davdeploy.nova_plan_codebuild as codebuild_runner
import pytest
from botocore.exceptions import ClientError
from davdeploy.generated_deployment_contract import (
    GeneratedDeploymentProposal,
    GeneratedResource,
    WorkloadRequirements,
)
from davdeploy.generated_plan_artifacts import canonical_json_digest
from davdeploy.generated_plan_inspection import TerraformPlanSummary
from davdeploy.generated_plan_ownership import PlanOwnershipScope
from davdeploy.generated_plan_policy import (
    GeneratedPlanPolicyResult,
    PlanPolicyVerdict,
)
from davdeploy.generated_terraform_plan import (
    PINNED_AWS_PROVIDER_VERSION,
    PINNED_TERRAFORM_VERSION,
    GeneratedTerraformPlan,
)
from davdeploy.nova_terraform_state_client import (
    TerraformHTTPBackend,
    TerraformStateBootstrapError,
)
from davdeploy.terraform_generation import generation_context_digest
from davdeploy.terraform_state import terraform_state_scope_digest
from test_nova_plan_only_infra import ROOT

RUN_ID = "12345678-1234-1234-1234-123456789012"
PROJECT = "davdeploy-nova-plan-only"
ACCOUNT_A = "654654474502"
CONNECTION_A = "connection-a"
EXTERNAL_A = "external-id-for-connection-a-0123456789"
ACCOUNT_B = "111111111111"
CONNECTION_B = "connection-b"
EXTERNAL_B = "external-id-for-connection-b-0123456789"
BUCKET = "davdeploy-tfplans-654654474502"
KMS_KEY = "arn:aws:kms:us-east-1:654654474502:key/12345678-1234-1234-1234-123456789012"


def make_input_document(
    *,
    run_id=RUN_ID,
    build_arn=None,
    account_id=ACCOUNT_A,
    connection_id=CONNECTION_A,
    external_id=EXTERNAL_A,
    organization_id="org-a",
    project_id="project-a",
    plan_id="plan-a",
    revision_id="revision-a",
    control_plane_run_id=None,
    environment_id="production",
    region="us-east-1",
):
    build_arn = build_arn or build_arn_for(run_id)
    source_plan_id = f"source-{plan_id}"
    revision = {
        "target": {
            "account_id": account_id,
            "region": region,
            "connection_id": connection_id,
            "environment_id": environment_id,
        },
        "source_deployment_plan_id": source_plan_id,
    }
    revision_sha256 = canonical_json_digest(revision)
    ownership = PlanOwnershipScope(
        organization_id=organization_id,
        workspace_id=organization_id,
        project_id=project_id,
        plan_id=plan_id,
        revision_id=revision_id,
        environment_id=environment_id,
    )
    proposal = GeneratedDeploymentProposal(
        contract_version="1.0",
        source_revision=revision_id,
        context_digest=generation_context_digest(revision, revision_id),
        resources=(
            GeneratedResource(
                resource_id="bucket",
                resource_type="aws_s3_bucket",
                name="app_data",
                arguments={"bucket": "fixture-app-storage"},
                rationale="Private application storage.",
            ),
        ),
        requirements=WorkloadRequirements(region=region),
    )
    request_document = {
        "contract": "davdeploy.nova-plan-request.v1",
        "organization_id": organization_id,
        "project_id": project_id,
        "plan_id": plan_id,
        "revision_id": revision_id,
        "revision_sha256": revision_sha256,
        "target_account_id": account_id,
        "region": region,
        "connection_id": connection_id,
        "plan_role_arn": f"arn:aws:iam::{account_id}:role/davdeployPlan-{connection_id}",
        "source_deployment_plan_id": source_plan_id,
        "generator_model": "fixture-nova-model",
        "runner_project": PROJECT,
    }
    proposal_document = proposal.model_dump(mode="json")
    return {
        **request_document,
        "contract": codebuild_runner.INPUT_CONTRACT,
        "run_id": run_id,
        "control_plane_run_id": control_plane_run_id or run_id,
        "runner_project": PROJECT,
        "codebuild_build_arn": build_arn,
        "request_document": request_document,
        "request_sha256": canonical_json_digest(request_document),
        "customer_revision": revision,
        "revision_id": revision_id,
        "revision_sha256": revision_sha256,
        "proposal": proposal_document,
        "proposal_sha256": canonical_json_digest(proposal_document),
        "plan_role": {"arn": f"arn:aws:iam::{account_id}:role/davdeployPlan-{connection_id}"},
        "ownership_scope": {
            "organization_id": ownership.organization_id,
            "workspace_id": ownership.workspace_id,
            "project_id": ownership.project_id,
            "plan_id": ownership.plan_id,
            "revision_id": ownership.revision_id,
            "environment_id": ownership.environment_id,
            "scope_sha256": ownership.scope_sha256(),
            "plan_id_sha256": ownership.plan_id_sha256(),
            "tags": ownership.tags(),
        },
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


def build_arn_for(run_id=RUN_ID, project=PROJECT):
    return f"arn:aws:codebuild:us-east-1:{ACCOUNT_A}:build/{project}:{run_id}"


def build_env(run_id=RUN_ID, project=PROJECT, build_arn=None):
    return {
        codebuild_runner.RUN_ID_ENV: run_id,
        "CODEBUILD_BUILD_ID": f"{project}:{run_id}",
        "CODEBUILD_BUILD_ARN": build_arn or build_arn_for(run_id, project),
        "DAVDEPLOY_NOVA_PLAN_PROJECT_NAME": project,
        "DAVDEPLOY_NOVA_PLAN_ARTIFACT_BUCKET": BUCKET,
        "DAVDEPLOY_NOVA_PLAN_KMS_KEY_ARN": KMS_KEY,
        "DAVDEPLOY_NOVA_PLAN_BUCKET_OWNER": ACCOUNT_A,
        "AWS_DEFAULT_REGION": "us-east-1",
        "DAVDEPLOY_NOVA_PLAN_CREDENTIAL_BROKER_URL": (
            "https://fixture.execute-api.us-east-1.amazonaws.com/api/v1/nova-plan/credentials"
        ),
    }


class FakeS3:
    def __init__(self, *, get_version_id=None):
        self.objects = {}
        self.get_version_id = get_version_id
        self.head_calls = []
        self.get_calls = []
        self.put_calls = []

    def seed_input(self, build_arn, document):
        key = codebuild_runner._build_object_key(build_arn, "input.json")
        body = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        version_id = "input-version-1"
        self.objects[(BUCKET, key, version_id)] = {
            "Body": body,
            "Metadata": {
                "davdeploy-run-id": document["run_id"],
                "davdeploy-input-sha256": canonical_json_digest(document),
            },
            "VersionId": version_id,
        }
        return key, version_id

    def head_object(self, *, Bucket, Key, ExpectedBucketOwner):
        self.head_calls.append((Bucket, Key, ExpectedBucketOwner))
        obj = self._latest(Bucket, Key)
        return {
            "VersionId": obj["VersionId"],
            "ContentLength": len(obj["Body"]),
            "Metadata": obj["Metadata"],
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": KMS_KEY,
            "BucketKeyEnabled": True,
        }

    def get_object(self, *, Bucket, Key, VersionId, ExpectedBucketOwner):
        self.get_calls.append((Bucket, Key, VersionId, ExpectedBucketOwner))
        obj = self.objects[(Bucket, Key, VersionId)]
        return {
            "Body": io.BytesIO(obj["Body"]),
            "VersionId": self.get_version_id or VersionId,
            "ContentLength": len(obj["Body"]),
            "Metadata": obj["Metadata"],
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": KMS_KEY,
            "BucketKeyEnabled": True,
        }

    def put_object(self, **kwargs):
        body = kwargs["Body"]
        payload = body if isinstance(body, bytes) else body.read()
        key = (kwargs["Bucket"], kwargs["Key"])
        self.put_calls.append((kwargs, payload))
        version_id = f"output-version-{len(self.put_calls)}"
        self.objects[(key[0], key[1], version_id)] = {
            "Body": payload,
            "Metadata": kwargs["Metadata"],
            "VersionId": version_id,
        }
        return {"VersionId": version_id, "BucketKeyEnabled": True}

    def _latest(self, bucket, key):
        matches = [
            (version, value)
            for (stored_bucket, stored_key, version), value in self.objects.items()
            if stored_bucket == bucket and stored_key == key
        ]
        if not matches:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey"}, "ResponseMetadata": {"HTTPStatusCode": 404}},
                "HeadObject",
            )
        return max(matches, key=lambda item: item[0])[1]


class FakeSTS:
    def __init__(self, accepted_external_ids):
        self.accepted_role_arns = set(accepted_external_ids)
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["expected_role_arn"] not in self.accepted_role_arns:
            raise codebuild_runner.NovaPlanCredentialError("credential broker denied role")
        return SimpleNamespace(
            role_arn=kwargs["expected_role_arn"],
            account_id=kwargs["expected_account_id"],
            region=kwargs["region"],
            policy_version=kwargs["expected_policy_version"],
            policy_sha256=kwargs["expected_policy_sha256"],
            boto3_credentials=lambda: {
                "AccessKeyId": "ASIAFIXTUREACCESSKEY",
                "SecretAccessKey": "fixture-secret-credential",
                "SessionToken": "fixture-session-token",
            },
        )


class FakeSession:
    def __init__(self, **kwargs):
        self.credentials = kwargs

    def get_credentials(self):
        frozen = SimpleNamespace(
            access_key="ASIAFIXTUREACCESSKEY",
            secret_key="fixture-codebuild-secret",
            token="fixture-codebuild-session-token",
        )
        return SimpleNamespace(get_frozen_credentials=lambda: frozen)

    def client(self, name):
        assert name == "sts"
        return SimpleNamespace(get_caller_identity=lambda: {"Account": ACCOUNT_A})


class FakePlanRunner:
    def __init__(self, *, verdict=PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW):
        self.verdict = verdict
        self.calls = []

    def plan(
        self,
        proposal,
        *,
        expected_account_id,
        region,
        ownership_scope,
        workspace,
        aws_credentials,
        remote_state=None,
        plan_access_policy_version="NOT_APPLICABLE",
        plan_access_policy_sha256="0" * 64,
    ):
        self.calls.append(
            {
                "proposal": proposal,
                "expected_account_id": expected_account_id,
                "region": region,
                "ownership_scope": ownership_scope,
                "workspace": workspace,
                "aws_credentials": aws_credentials,
                "remote_state": remote_state,
                "plan_access_policy_version": plan_access_policy_version,
                "plan_access_policy_sha256": plan_access_policy_sha256,
            }
        )
        saved_plan = Path(workspace) / "saved.tfplan"
        saved_plan.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        saved_plan.write_bytes(b"opaque saved plan fixture")
        plan_digest = hashlib.sha256(saved_plan.read_bytes()).hexdigest()
        policy = GeneratedPlanPolicyResult(
            verdict=self.verdict,
            policy_version="fixture-policy-v1",
            findings=(),
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
        return GeneratedTerraformPlan(
            summary=summary,
            policy=policy,
            target_account_id=expected_account_id,
            region=region,
            terraform_version=PINNED_TERRAFORM_VERSION,
            aws_provider_version=PINNED_AWS_PROVIDER_VERSION,
            provider_lockfile_sha256="a" * 64,
            proposal_sha256=canonical_json_digest(proposal.model_dump(mode="json")),
            context_sha256=proposal.context_digest,
            configuration_sha256="b" * 64,
            ownership_scope_sha256=ownership_scope.scope_sha256(),
            ownership_plan_id_sha256=ownership_scope.plan_id_sha256(),
            saved_plan_sha256=plan_digest,
            saved_plan_path=str(saved_plan),
            plan_access_policy_version=plan_access_policy_version,
            plan_access_policy_sha256=plan_access_policy_sha256,
        )


def run_build(
    monkeypatch,
    tmp_path,
    *,
    document=None,
    runner=None,
    sts=None,
    s3=None,
    env=None,
    state_bootstrapper=None,
):
    build_arn = build_arn_for()
    document = document or make_input_document(build_arn=build_arn)
    s3 = s3 or FakeS3()
    key, version_id = s3.seed_input(build_arn, document)
    sts = sts or FakeSTS(
        {f"arn:aws:iam::{ACCOUNT_A}:role/davdeployPlan-{CONNECTION_A}": EXTERNAL_A}
    )
    runner = runner or FakePlanRunner()
    monkeypatch.setattr(codebuild_runner.boto3, "Session", FakeSession)
    result = codebuild_runner.run_nova_plan_build(
        RUN_ID,
        environment=env or build_env(),
        s3_client=s3,
        runner=runner,
        workspace_root=tmp_path,
        input_poll_attempts=1,
        input_poll_interval_seconds=0,
        state_bootstrapper=state_bootstrapper,
        credential_requester=sts,
    )
    return result, document, key, version_id, s3, sts, runner


def test_build_reads_exact_build_input_and_writes_encrypted_versioned_artifacts(
    monkeypatch, tmp_path
):
    result, document, input_key, input_version, s3, sts, runner = run_build(
        monkeypatch, tmp_path
    )

    assert s3.head_calls == [(BUCKET, input_key, ACCOUNT_A)]
    assert s3.get_calls == [(BUCKET, input_key, input_version, ACCOUNT_A)]
    assert sts.calls[0]["expected_role_arn"] == f"arn:aws:iam::{ACCOUNT_A}:role/davdeployPlan-{CONNECTION_A}"
    assert sts.calls[0]["expected_account_id"] == ACCOUNT_A
    assert sts.calls[0]["expected_policy_sha256"] == runner.calls[0]["plan_access_policy_sha256"]
    assert "external_id" not in document["plan_role"]
    assert EXTERNAL_A not in json.dumps(document)
    assert runner.calls[0]["aws_credentials"]["SecretAccessKey"] == "fixture-secret-credential"
    assert len(s3.put_calls) == 2

    keys = [call[0]["Key"] for call in s3.put_calls]
    expected_plan_prefix = f"plans/nova-generated/builds/{build_arn_for()}/"
    assert all(key.startswith(expected_plan_prefix) for key in keys)
    assert f"plans/nova-generated/builds/{build_arn_for()}/result.json" in keys
    for call, _payload in s3.put_calls:
        assert call["ServerSideEncryption"] == "aws:kms"
        assert call["SSEKMSKeyId"] == KMS_KEY
        assert call["BucketKeyEnabled"] is True
        assert call["IfNoneMatch"] == "*"
        assert call["ExpectedBucketOwner"] == ACCOUNT_A

    result_put = next(call for call, _payload in s3.put_calls if call["Key"].endswith("result.json"))
    result_bytes = next(payload for call, payload in s3.put_calls if call is result_put)
    result_document = json.loads(result_bytes)
    assert result["result_key"] == result_put["Key"]
    assert result["result_version_id"] == "output-version-2"
    assert result_document["run_id"] == RUN_ID
    assert result_document["codebuild_build_arn"] == build_arn_for()
    assert result_document["input"] == {
        "key": input_key,
        "version_id": input_version,
        "sha256": canonical_json_digest(document),
    }
    assert result_document["planning_boundary"] == "INITIAL_PLAN_NO_REMOTE_STATE"
    assert EXTERNAL_A not in result_bytes.decode()
    assert "fixture-secret-credential" not in result_bytes.decode()
    assert result["saved_plan"].version_id == "output-version-1"
    assert not hasattr(runner, "apply")
    assert not hasattr(runner, "destroy")


def test_broker_checks_customer_target_region_not_codebuild_region(monkeypatch, tmp_path):
    document = make_input_document(region="us-west-2")
    _result, _document, _key, _version, _s3, broker, runner = run_build(
        monkeypatch, tmp_path, document=document
    )
    assert broker.calls[0]["region"] == "us-west-2"
    assert runner.calls[0]["region"] == "us-west-2"


def test_retry_attempt_can_bind_a_distinct_control_plane_request_id(monkeypatch, tmp_path):
    control_plane_run_id = "87654321-4321-4321-4321-210987654321"
    document = make_input_document(control_plane_run_id=control_plane_run_id)

    _, _, _, _, s3, _, runner = run_build(monkeypatch, tmp_path, document=document)
    result_document = next(
        json.loads(payload)
        for call, payload in s3.put_calls
        if call["Key"].endswith("result.json")
    )

    assert result_document["run_id"] == RUN_ID
    assert result_document["run_id"] != control_plane_run_id
    assert len(runner.calls) == 1


def test_remote_state_bootstrap_uses_durable_request_and_keeps_credentials_out_of_result(
    monkeypatch, tmp_path
):
    control_plane_run_id = "87654321-4321-4321-4321-210987654321"
    document = make_input_document(
        control_plane_run_id=control_plane_run_id,
        organization_id="12345678-1234-4234-8234-123456789012",
        project_id="22345678-1234-4234-8234-123456789012",
        environment_id="32345678-1234-4234-8234-123456789012",
    )
    target = document["customer_revision"]["target"]
    expected_scope_sha256 = terraform_state_scope_digest(
        organization_id=document["request_document"]["organization_id"],
        project_id=document["request_document"]["project_id"],
        environment_id=target["environment_id"],
        target_account_id=document["request_document"]["target_account_id"],
        region=document["request_document"]["region"],
    )
    state_id = "12345678-1234-4234-8234-123456789012"
    state_backend = TerraformHTTPBackend(
        state_id=state_id,
        scope_sha256=expected_scope_sha256,
        address=f"https://api.davdeploy.tech/api/v1/terraform-state/{state_id}",
        lock_address=f"https://api.davdeploy.tech/api/v1/terraform-state/{state_id}/lock",
        unlock_address=f"https://api.davdeploy.tech/api/v1/terraform-state/{state_id}/unlock",
        username="u" * 32,
        password="p" * 64,
        expires_at=datetime.now(UTC) + timedelta(minutes=20),
    )
    calls = []

    def bootstrap(**kwargs):
        calls.append(kwargs)
        return state_backend

    env = {
        **build_env(),
        "DAVDEPLOY_TERRAFORM_STATE_ENABLED": "true",
        "DAVDEPLOY_TERRAFORM_STATE_BOOTSTRAP_URL": "https://api-id.execute-api.us-east-1.amazonaws.com/api/v1/terraform-state/credentials",
        "DAVDEPLOY_TERRAFORM_STATE_API_URL": "https://api.davdeploy.tech",
    }
    result, _, _, _, s3, _, runner = run_build(
        monkeypatch,
        tmp_path,
        document=document,
        env=env,
        state_bootstrapper=bootstrap,
    )
    assert calls == [
        {
            "bootstrap_url": env["DAVDEPLOY_TERRAFORM_STATE_BOOTSTRAP_URL"],
            "state_api_url": env["DAVDEPLOY_TERRAFORM_STATE_API_URL"],
            "durable_run_id": control_plane_run_id,
            "region": "us-east-1",
        }
    ]
    assert runner.calls[0]["remote_state"] is state_backend
    stored_result = next(
        payload for call, payload in s3.put_calls if call["Key"].endswith("result.json")
    )
    result_document = json.loads(stored_result)
    assert result_document["planning_boundary"] == "TENANT_ISOLATED_HTTP_STATE"
    assert result_document["remote_state"] == {
        "state_id": state_backend.state_id,
        "scope_sha256": state_backend.scope_sha256,
    }
    assert result_document["manifest"]["manifest_version"] == 5
    assert state_backend.password not in stored_result.decode()
    assert state_backend.username not in stored_result.decode()
    assert result["result_version_id"] == "output-version-2"


def test_remote_state_scope_mismatch_fails_before_terraform_plan(monkeypatch, tmp_path):
    document = make_input_document(
        control_plane_run_id="87654321-4321-4321-4321-210987654321",
        organization_id="12345678-1234-4234-8234-123456789012",
        project_id="22345678-1234-4234-8234-123456789012",
        environment_id="32345678-1234-4234-8234-123456789012",
    )
    state_id = "12345678-1234-4234-8234-123456789012"
    backend = TerraformHTTPBackend(
        state_id=state_id,
        scope_sha256="c" * 64,
        address=f"https://api.davdeploy.tech/api/v1/terraform-state/{state_id}",
        lock_address=f"https://api.davdeploy.tech/api/v1/terraform-state/{state_id}/lock",
        unlock_address=f"https://api.davdeploy.tech/api/v1/terraform-state/{state_id}/unlock",
        username="u" * 32,
        password="p" * 64,
        expires_at=datetime.now(UTC) + timedelta(minutes=20),
    )
    env = {
        **build_env(),
        "DAVDEPLOY_TERRAFORM_STATE_ENABLED": "true",
        "DAVDEPLOY_TERRAFORM_STATE_BOOTSTRAP_URL": "https://api-id.execute-api.us-east-1.amazonaws.com/api/v1/terraform-state/credentials",
        "DAVDEPLOY_TERRAFORM_STATE_API_URL": "https://api.davdeploy.tech",
    }
    s3 = FakeS3()
    s3.seed_input(build_arn_for(), document)
    sts = FakeSTS({f"arn:aws:iam::{ACCOUNT_A}:role/davdeployPlan-{CONNECTION_A}": EXTERNAL_A})
    runner = FakePlanRunner()

    with pytest.raises(
        codebuild_runner.NovaPlanBuildError, match="wrong tenant scope"
    ):
        run_build(
            monkeypatch,
            tmp_path,
            document=document,
            env=env,
            s3=s3,
            sts=sts,
            runner=runner,
            state_bootstrapper=lambda **_kwargs: backend,
        )

    assert runner.calls == []
    assert s3.put_calls == []


def test_enabled_remote_state_fails_closed_without_trusted_bootstrap_configuration(
    monkeypatch, tmp_path
):
    env = {**build_env(), "DAVDEPLOY_TERRAFORM_STATE_ENABLED": "true"}
    document = make_input_document(
        control_plane_run_id="87654321-4321-4321-4321-210987654321"
    )
    s3 = FakeS3()
    s3.seed_input(build_arn_for(), document)
    sts = FakeSTS({f"arn:aws:iam::{ACCOUNT_A}:role/davdeployPlan-{CONNECTION_A}": EXTERNAL_A})
    runner = FakePlanRunner()
    monkeypatch.setattr(codebuild_runner.boto3, "Session", FakeSession)

    with pytest.raises(codebuild_runner.NovaPlanBuildError, match="not configured"):
        codebuild_runner.run_nova_plan_build(
            RUN_ID,
            environment=env,
            s3_client=s3,
            credential_requester=sts,
            runner=runner,
            workspace_root=tmp_path,
            input_poll_attempts=1,
            input_poll_interval_seconds=0,
        )

    assert len(sts.calls) == 1
    assert runner.calls == []
    assert s3.put_calls == []


def test_enabled_remote_state_does_not_fall_back_when_bootstrap_fails(monkeypatch, tmp_path):
    env = {
        **build_env(),
        "DAVDEPLOY_TERRAFORM_STATE_ENABLED": "true",
        "DAVDEPLOY_TERRAFORM_STATE_BOOTSTRAP_URL": "https://api-id.execute-api.us-east-1.amazonaws.com/api/v1/terraform-state/credentials",
        "DAVDEPLOY_TERRAFORM_STATE_API_URL": "https://api.davdeploy.tech",
    }
    document = make_input_document(
        control_plane_run_id="87654321-4321-4321-4321-210987654321"
    )
    s3 = FakeS3()
    s3.seed_input(build_arn_for(), document)
    sts = FakeSTS({f"arn:aws:iam::{ACCOUNT_A}:role/davdeployPlan-{CONNECTION_A}": EXTERNAL_A})
    runner = FakePlanRunner()
    monkeypatch.setattr(codebuild_runner.boto3, "Session", FakeSession)

    def reject_bootstrap(**_kwargs):
        raise TerraformStateBootstrapError("fixture transport failure")

    with pytest.raises(codebuild_runner.NovaPlanBuildError, match="bootstrap failed"):
        codebuild_runner.run_nova_plan_build(
            RUN_ID,
            environment=env,
            s3_client=s3,
            credential_requester=sts,
            runner=runner,
            workspace_root=tmp_path,
            input_poll_attempts=1,
            input_poll_interval_seconds=0,
            state_bootstrapper=reject_bootstrap,
        )

    assert len(sts.calls) == 1
    assert runner.calls == []
    assert s3.put_calls == []


def test_invalid_control_plane_request_id_is_rejected_before_assume_role(monkeypatch, tmp_path):
    document = make_input_document(control_plane_run_id="not-a-uuid")
    s3 = FakeS3()
    s3.seed_input(build_arn_for(), document)
    sts = FakeSTS({f"arn:aws:iam::{ACCOUNT_A}:role/davdeployPlan-{CONNECTION_A}": EXTERNAL_A})
    runner = FakePlanRunner()
    monkeypatch.setattr(codebuild_runner.boto3, "Session", FakeSession)

    with pytest.raises(codebuild_runner.NovaPlanBuildError, match="control-plane request ID"):
        codebuild_runner.run_nova_plan_build(
            RUN_ID,
            environment=build_env(),
            s3_client=s3,
            credential_requester=sts,
            runner=runner,
            workspace_root=tmp_path,
            input_poll_attempts=1,
            input_poll_interval_seconds=0,
        )

    assert sts.calls == []
    assert runner.calls == []
    assert s3.put_calls == []


@pytest.mark.parametrize(
    "changes",
    [
        {"run_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"},
        {"codebuild_build_arn": "arn:aws:codebuild:us-east-1:654654474502:build/other:run"},
        {"organization_id": "org-b"},
    ],
)
def test_tampered_input_wrong_run_build_or_tenant_stops_before_assume_role(
    monkeypatch, tmp_path, changes
):
    document = make_input_document(build_arn=build_arn_for())
    if "organization_id" in changes:
        document["ownership_scope"]["organization_id"] = changes["organization_id"]
    else:
        document.update(changes)
    s3 = FakeS3()
    s3.seed_input(build_arn_for(), document)
    sts = FakeSTS({f"arn:aws:iam::{ACCOUNT_A}:role/davdeployPlan-{CONNECTION_A}": EXTERNAL_A})
    runner = FakePlanRunner()
    monkeypatch.setattr(codebuild_runner.boto3, "Session", FakeSession)

    with pytest.raises(codebuild_runner.NovaPlanBuildError):
        codebuild_runner.run_nova_plan_build(
            RUN_ID,
            environment=build_env(),
            s3_client=s3,
            credential_requester=sts,
            runner=runner,
            workspace_root=tmp_path,
            input_poll_attempts=1,
            input_poll_interval_seconds=0,
        )

    assert sts.calls == []
    assert runner.calls == []
    assert s3.put_calls == []


def test_wrong_input_version_is_rejected_before_assume_role(monkeypatch, tmp_path):
    s3 = FakeS3(get_version_id="another-input-version")
    document = make_input_document(build_arn=build_arn_for())
    s3.seed_input(build_arn_for(), document)
    sts = FakeSTS({f"arn:aws:iam::{ACCOUNT_A}:role/davdeployPlan-{CONNECTION_A}": EXTERNAL_A})
    runner = FakePlanRunner()
    monkeypatch.setattr(codebuild_runner.boto3, "Session", FakeSession)

    with pytest.raises(codebuild_runner.NovaPlanBuildError, match="not immutably versioned"):
        codebuild_runner.run_nova_plan_build(
            RUN_ID,
            environment=build_env(),
            s3_client=s3,
            credential_requester=sts,
            runner=runner,
            workspace_root=tmp_path,
            input_poll_attempts=1,
            input_poll_interval_seconds=0,
        )

    assert sts.calls == []
    assert runner.calls == []
    assert s3.put_calls == []


@pytest.mark.parametrize("tamper", ["revision_account", "revision_id"])
def test_input_revision_or_account_tampering_is_rejected_before_assume_role(
    monkeypatch, tmp_path, tamper
):
    document = make_input_document(build_arn=build_arn_for())
    if tamper == "revision_account":
        document["customer_revision"]["target"]["account_id"] = ACCOUNT_B
    else:
        document["revision_id"] = "revision-tampered"
    s3 = FakeS3()
    s3.seed_input(build_arn_for(), document)
    sts = FakeSTS({f"arn:aws:iam::{ACCOUNT_A}:role/davdeployPlan-{CONNECTION_A}": EXTERNAL_A})
    runner = FakePlanRunner()
    monkeypatch.setattr(codebuild_runner.boto3, "Session", FakeSession)

    with pytest.raises(codebuild_runner.NovaPlanBuildError):
        codebuild_runner.run_nova_plan_build(
            RUN_ID,
            environment=build_env(),
            s3_client=s3,
            credential_requester=sts,
            runner=runner,
            workspace_root=tmp_path,
            input_poll_attempts=1,
            input_poll_interval_seconds=0,
        )

    assert sts.calls == []
    assert runner.calls == []
    assert s3.put_calls == []


def test_input_body_digest_tampering_is_rejected_before_assume_role(monkeypatch, tmp_path):
    s3 = FakeS3()
    document = make_input_document(build_arn=build_arn_for())
    key, version_id = s3.seed_input(build_arn_for(), document)
    stored = s3.objects[(BUCKET, key, version_id)]
    tampered = dict(document)
    tampered["proposal_sha256"] = "f" * 64
    stored["Body"] = json.dumps(tampered, sort_keys=True, separators=(",", ":")).encode()
    sts = FakeSTS({f"arn:aws:iam::{ACCOUNT_A}:role/davdeployPlan-{CONNECTION_A}": EXTERNAL_A})
    runner = FakePlanRunner()
    monkeypatch.setattr(codebuild_runner.boto3, "Session", FakeSession)

    with pytest.raises(codebuild_runner.NovaPlanBuildError, match="digest check"):
        codebuild_runner.run_nova_plan_build(
            RUN_ID,
            environment=build_env(),
            s3_client=s3,
            credential_requester=sts,
            runner=runner,
            workspace_root=tmp_path,
            input_poll_attempts=1,
            input_poll_interval_seconds=0,
        )

    assert sts.calls == []
    assert runner.calls == []
    assert s3.put_calls == []


def test_unsupported_proposal_fails_before_customer_role_assumption(monkeypatch, tmp_path):
    s3 = FakeS3()
    document = make_input_document(build_arn=build_arn_for())
    document["proposal"]["resources"][0]["resource_type"] = "aws_ec2_instance"
    document["proposal_sha256"] = canonical_json_digest(document["proposal"])
    s3.seed_input(build_arn_for(), document)
    sts = FakeSTS({f"arn:aws:iam::{ACCOUNT_A}:role/davdeployPlan-{CONNECTION_A}": EXTERNAL_A})
    runner = FakePlanRunner()
    monkeypatch.setattr(codebuild_runner.boto3, "Session", FakeSession)

    with pytest.raises(
        codebuild_runner.NovaPlanBuildError,
        match="exceeds the fixed customer plan permission profile",
    ):
        codebuild_runner.run_nova_plan_build(
            RUN_ID,
            environment=build_env(),
            s3_client=s3,
            credential_requester=sts,
            runner=runner,
            workspace_root=tmp_path,
            input_poll_attempts=1,
            input_poll_interval_seconds=0,
        )

    assert sts.calls == []
    assert runner.calls == []
    assert s3.put_calls == []


def test_denied_plan_policy_stores_no_plan_or_result(monkeypatch, tmp_path):
    s3 = FakeS3()
    sts = FakeSTS({f"arn:aws:iam::{ACCOUNT_A}:role/davdeployPlan-{CONNECTION_A}": EXTERNAL_A})
    runner = FakePlanRunner(verdict=PlanPolicyVerdict.DENY)
    monkeypatch.setattr(codebuild_runner.boto3, "Session", FakeSession)

    with pytest.raises(codebuild_runner.NovaPlanBuildError, match="policy denied"):
        run_build(monkeypatch, tmp_path, runner=runner, sts=sts, s3=s3)

    assert len(sts.calls) == 1
    assert len(runner.calls) == 1
    assert s3.put_calls == []


def test_tampered_saved_plan_is_rejected_before_s3_write(tmp_path):
    plan_path = tmp_path / "saved.tfplan"
    plan_path.write_bytes(b"tampered saved plan")
    s3 = FakeS3()

    with pytest.raises(codebuild_runner.NovaPlanBuildError, match="integrity verification"):
        codebuild_runner._put_saved_plan(
            s3,
            BUCKET,
            ACCOUNT_A,
            KMS_KEY,
            RUN_ID,
            f"plans/nova-generated/builds/{build_arn_for()}/plan.tfplan",
            str(plan_path),
            hashlib.sha256(b"expected saved plan").hexdigest(),
        )

    assert s3.put_calls == []


def test_cross_account_plan_role_credentials_fail_identity_check(monkeypatch, tmp_path):
    build_arn = build_arn_for()
    document = make_input_document(
        build_arn=build_arn,
        account_id=ACCOUNT_B,
        connection_id=CONNECTION_B,
        external_id=EXTERNAL_A,
        organization_id="org-b",
        project_id="project-b",
        plan_id="plan-b",
        revision_id="revision-b",
    )
    role_b = f"arn:aws:iam::{ACCOUNT_B}:role/davdeployPlan-{CONNECTION_B}"
    s3 = FakeS3()
    s3.seed_input(build_arn, document)
    sts = FakeSTS({role_b: EXTERNAL_B})
    runner = FakePlanRunner()
    monkeypatch.setattr(codebuild_runner.boto3, "Session", FakeSession)

    with pytest.raises(codebuild_runner.NovaPlanBuildError, match="account does not match"):
        codebuild_runner.run_nova_plan_build(
            RUN_ID,
            environment=build_env(),
            s3_client=s3,
            credential_requester=sts,
            runner=runner,
            workspace_root=tmp_path,
            input_poll_attempts=1,
            input_poll_interval_seconds=0,
        )

    assert len(sts.calls) == 1
    assert sts.calls[0]["expected_role_arn"] == role_b
    assert sts.calls[0]["expected_account_id"] == ACCOUNT_B
    assert runner.calls == []
    assert s3.put_calls == []


@pytest.mark.parametrize(
    "tamper",
    [
        lambda document: document.update(external_id=EXTERNAL_A),
        lambda document: document["plan_role"].update(external_id=EXTERNAL_A),
        lambda document: document["request_document"].update(unreviewed=True),
    ],
)
def test_staged_input_rejects_secret_or_unrecognized_fields_before_broker_call(
    monkeypatch, tmp_path, tamper
):
    document = make_input_document(build_arn=build_arn_for())
    tamper(document)
    s3 = FakeS3()
    s3.seed_input(build_arn_for(), document)
    broker = FakeSTS({f"arn:aws:iam::{ACCOUNT_A}:role/davdeployPlan-{CONNECTION_A}": EXTERNAL_A})
    runner = FakePlanRunner()
    monkeypatch.setattr(codebuild_runner.boto3, "Session", FakeSession)

    with pytest.raises(codebuild_runner.NovaPlanBuildError, match="binding is invalid|role ARN"):
        codebuild_runner.run_nova_plan_build(
            RUN_ID,
            environment=build_env(),
            s3_client=s3,
            credential_requester=broker,
            runner=runner,
            workspace_root=tmp_path,
            input_poll_attempts=1,
            input_poll_interval_seconds=0,
        )

    assert broker.calls == []
    assert runner.calls == []
    assert s3.put_calls == []


def test_customer_plan_role_trust_requires_external_id_and_read_only_permission_guard():
    template = (ROOT / "infrastructure/cloudformation/customer-discovery-role.yaml").read_text()
    plan_role = template.split("  NovaPlanOnlyRole:", 1)[1].split("  ExecutionRole:", 1)[0]
    assert "!Ref davdeployNovaPlanBrokerRoleArn" not in plan_role
    assert "AWS: !Ref davdeployDiscoveryBrokerRoleArn" in plan_role
    assert "StringEquals:" in plan_role
    assert "sts:ExternalId: !Ref ExternalId" in plan_role
    assert "Effect: Deny" in plan_role
    assert "NotAction:" in plan_role
    assert "lambda:InvokeFunction" not in plan_role
    assert "iam:PassRole" not in plan_role
    assert "s3:GetObject" not in plan_role
    assert 'Resource: "*"' in plan_role


def test_fixed_build_runner_has_no_resource_mutation_calls():
    module = ast.parse(Path(codebuild_runner.__file__).read_text())
    mutation_calls = [
        node.func.attr
        for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr.casefold() in {"apply", "destroy", "delete_resource"}
    ]
    assert mutation_calls == []
    assert not hasattr(codebuild_runner.GeneratedTerraformPlanRunner, "apply")
    assert not hasattr(codebuild_runner.GeneratedTerraformPlanRunner, "destroy")
