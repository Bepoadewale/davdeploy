"""Fixed CodeBuild entrypoint for initial Nova plan-only builds.

The project buildspec and release artifact are fixed in Terraform. The worker
never reads customer source, a caller-selected backend, or Terraform commands
from a request. Remote state can be used only through an opt-in, server-issued
HTTP backend contract.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from davdeploy.generated_deployment_contract import GeneratedDeploymentProposal
from davdeploy.generated_plan_artifacts import (
    S3GeneratedPlanArtifactStore,
    StoredPlanObject,
    canonical_json_digest,
    generated_plan_manifest,
    policy_evidence,
)
from davdeploy.generated_plan_ownership import PlanOwnershipScope
from davdeploy.generated_plan_pricing import PlanPricingError, TrustedPlanPricingContext
from davdeploy.generated_terraform_plan import (
    PINNED_AWS_PROVIDER_VERSION,
    PINNED_TERRAFORM_VERSION,
    GeneratedTerraformPlanRunner,
    TerraformPlanExecutionError,
)
from davdeploy.nova_plan_access import (
    NovaPlanAccessError,
    build_nova_plan_access_policy,
)
from davdeploy.nova_plan_credentials import (
    NovaPlanCredentialError,
    request_nova_plan_credentials,
)
from davdeploy.nova_terraform_state_client import (
    TerraformHTTPBackend,
    TerraformStateBootstrapError,
    request_terraform_http_backend,
)
from davdeploy.terraform_generation import generation_context_digest
from davdeploy.terraform_state import terraform_state_scope_digest

RUN_ID_ENV = "DAVDEPLOY_NOVA_PLAN_RUN_ID"
INPUT_CONTRACT = "davdeploy.nova-plan-request.v1"
RESULT_CONTRACT = "davdeploy.nova-plan-result.v4"
MAX_INPUT_BYTES = 1_000_000
MAX_RESULT_BYTES = 1_000_000
MAX_PLAN_BYTES = 128 * 1024 * 1024


class NovaPlanBuildError(RuntimeError):
    """A CodeBuild plan request failed closed without exposing its input."""


def run_nova_plan_build(
    run_id: str,
    *,
    environment: dict[str, str] | None = None,
    s3_client: Any | None = None,
    runner: GeneratedTerraformPlanRunner | None = None,
    workspace_root: str | Path | None = None,
    input_poll_attempts: int = 30,
    input_poll_interval_seconds: float = 2.0,
    sleeper=time.sleep,
    state_bootstrapper=None,
    credential_requester=None,
) -> dict[str, Any]:
    """Verify one staged request, plan it, and write exact encrypted artifacts."""
    env = dict(os.environ if environment is None else environment)
    run_id = _validate_run_id(run_id)
    if env.get(RUN_ID_ENV) != run_id:
        raise NovaPlanBuildError("durable run ID does not match CodeBuild environment")
    build_id = _validate_build_id(env.get("CODEBUILD_BUILD_ID"))
    project_name = _validate_project(env.get("DAVDEPLOY_NOVA_PLAN_PROJECT_NAME"))
    if not build_id.startswith(f"{project_name}:"):
        raise NovaPlanBuildError("CodeBuild build ID does not match the fixed project")
    build_arn = _validate_build_arn(
        env.get("CODEBUILD_BUILD_ARN"), project_name=project_name, build_id=build_id
    )
    bucket = _required_bucket(env.get("DAVDEPLOY_NOVA_PLAN_ARTIFACT_BUCKET"))
    kms_key_arn = _required_kms_key(env.get("DAVDEPLOY_NOVA_PLAN_KMS_KEY_ARN"))
    bucket_owner = _required_account_id(env.get("DAVDEPLOY_NOVA_PLAN_BUCKET_OWNER"))
    region = env.get("AWS_DEFAULT_REGION") or env.get("AWS_REGION")
    if not isinstance(region, str) or not re.fullmatch(r"[a-z]{2}(?:-[a-z0-9]+)+-\d", region):
        raise NovaPlanBuildError("trusted CodeBuild region is invalid")

    s3 = s3_client or boto3.client("s3", region_name=region)
    input_key = _build_object_key(build_arn, "input.json")
    input_document, input_version_id, input_sha256 = _read_exact_input(
        s3,
        bucket,
        bucket_owner,
        kms_key_arn,
        run_id,
        input_key,
        poll_attempts=input_poll_attempts,
        poll_interval_seconds=input_poll_interval_seconds,
        sleeper=sleeper,
    )
    binding = _validate_input_document(input_document, run_id, project_name, build_arn)

    try:
        access_policy = build_nova_plan_access_policy(
            binding["proposal"],
            account_id=binding["account_id"],
            region=binding["region"],
        )
    except NovaPlanAccessError:
        raise NovaPlanBuildError(
            "proposal exceeds the fixed customer plan permission profile"
        ) from None

    broker_url = env.get("DAVDEPLOY_NOVA_PLAN_CREDENTIAL_BROKER_URL", "")
    try:
        credential_request = credential_requester or request_nova_plan_credentials
        broker_credentials = credential_request(
            broker_url=broker_url,
            durable_run_id=binding["control_plane_run_id"],
            region=binding["region"],
            expected_role_arn=binding["plan_role_arn"],
            expected_account_id=binding["account_id"],
            expected_policy_version=access_policy.version,
            expected_policy_sha256=access_policy.sha256,
            credentials=boto3.Session().get_credentials(),
        )
        if (
            broker_credentials.role_arn != binding["plan_role_arn"]
            or broker_credentials.account_id != binding["account_id"]
            or broker_credentials.region != binding["region"]
            or broker_credentials.policy_version != access_policy.version
            or broker_credentials.policy_sha256 != access_policy.sha256
        ):
            raise NovaPlanBuildError("credential broker response did not match the trusted plan")
        credentials = broker_credentials.boto3_credentials()
        session = boto3.Session(
            aws_access_key_id=credentials.get("AccessKeyId"),
            aws_secret_access_key=credentials.get("SecretAccessKey"),
            aws_session_token=credentials.get("SessionToken"),
            region_name=region,
        )
        identity = session.client("sts").get_caller_identity()
    except NovaPlanBuildError:
        raise
    except (
        NovaPlanCredentialError,
        BotoCoreError,
        ClientError,
        OSError,
        TypeError,
        ValueError,
        AttributeError,
    ):
        raise NovaPlanBuildError("the exact customer plan role could not be verified") from None
    if not isinstance(identity, dict) or identity.get("Account") != binding["account_id"]:
        raise NovaPlanBuildError("customer plan role account does not match the durable request")

    state_enabled = env.get("DAVDEPLOY_TERRAFORM_STATE_ENABLED", "false").lower()
    if state_enabled not in {"true", "false"}:
        raise NovaPlanBuildError("Terraform state feature configuration is invalid")
    remote_state = None
    if state_enabled == "true":
        bootstrap_url = env.get("DAVDEPLOY_TERRAFORM_STATE_BOOTSTRAP_URL")
        state_api_url = env.get("DAVDEPLOY_TERRAFORM_STATE_API_URL")
        if not bootstrap_url or not state_api_url:
            raise NovaPlanBuildError("trusted Terraform state service is not configured")
        try:
            if state_bootstrapper is not None:
                remote_state = state_bootstrapper(
                    bootstrap_url=bootstrap_url,
                    state_api_url=state_api_url,
                    durable_run_id=binding["control_plane_run_id"],
                    region=region,
                )
            else:
                remote_state = request_terraform_http_backend(
                    bootstrap_url=bootstrap_url,
                    state_api_url=state_api_url,
                    durable_run_id=binding["control_plane_run_id"],
                    region=region,
                    credentials=boto3.Session().get_credentials(),
                )
        except (TerraformStateBootstrapError, BotoCoreError, ClientError, OSError, TypeError, ValueError):
            raise NovaPlanBuildError("trusted Terraform state bootstrap failed") from None
        if not isinstance(remote_state, TerraformHTTPBackend):
            raise NovaPlanBuildError("trusted Terraform state bootstrap returned an invalid contract")
        try:
            expected_state_scope = terraform_state_scope_digest(
                organization_id=binding["organization_id"],
                project_id=binding["project_id"],
                environment_id=binding["ownership_scope"].environment_id,
                target_account_id=binding["account_id"],
                region=binding["region"],
            )
        except (KeyError, ValueError):
            raise NovaPlanBuildError("trusted plan request has no stable state scope") from None
        if remote_state.scope_sha256 != expected_state_scope:
            raise NovaPlanBuildError("trusted state bootstrap returned the wrong tenant scope")

    provider_lockfile = Path(__file__).with_name("terraform-provider.lock.hcl")
    plan_runner = runner or GeneratedTerraformPlanRunner(
        provider_lockfile=provider_lockfile,
        expected_terraform_version=PINNED_TERRAFORM_VERSION,
        expected_aws_provider_version=PINNED_AWS_PROVIDER_VERSION,
        terraform_binary=shutil.which("terraform") or "terraform",
        command_timeout_seconds=300,
        identity_provider=lambda: str(identity.get("Account") or ""),
    )
    workspace_base = Path(workspace_root) if workspace_root else Path(tempfile.gettempdir())
    workspace = workspace_base / f"davdeploy-nova-plan-{run_id}"
    try:
        generated_plan = plan_runner.plan(
            binding["proposal"],
            expected_account_id=binding["account_id"],
            region=binding["region"],
            ownership_scope=binding["ownership_scope"],
            workspace=workspace,
            trusted_pricing_context=binding["pricing_context"],
            aws_credentials=credentials,
            remote_state=remote_state,
            plan_access_policy_version=access_policy.version,
            plan_access_policy_sha256=access_policy.sha256,
        )
    except (TerraformPlanExecutionError, OSError, TypeError, ValueError):
        raise NovaPlanBuildError("the fixed Terraform plan pipeline rejected this request") from None
    if generated_plan.policy.verdict.value == "DENY":
        raise NovaPlanBuildError("the strict Terraform plan policy denied this request")
    if (
        generated_plan.target_account_id != binding["account_id"]
        or generated_plan.region != binding["region"]
        or generated_plan.proposal_sha256 != binding["proposal_sha256"]
        or generated_plan.context_sha256 != binding["context_sha256"]
    ):
        raise NovaPlanBuildError("Terraform plan output did not match the durable request")

    plan_key = S3GeneratedPlanArtifactStore._key(
        binding["organization_id"],
        binding["project_id"],
        binding["revision_id"],
        run_id,
        generated_plan.saved_plan_sha256,
        build_arn=build_arn,
    )
    stored_plan = _put_saved_plan(
        s3,
        bucket,
        bucket_owner,
        kms_key_arn,
        run_id,
        plan_key,
        generated_plan.saved_plan_path,
        generated_plan.saved_plan_sha256,
    )
    workspace_key = S3GeneratedPlanArtifactStore._key(
        binding["organization_id"],
        binding["project_id"],
        binding["revision_id"],
        run_id,
        generated_plan.workspace_bundle_sha256,
        build_arn=build_arn,
        artifact_kind="workspace",
    )
    stored_workspace = _put_execution_workspace(
        s3,
        bucket,
        bucket_owner,
        kms_key_arn,
        run_id,
        workspace_key,
        generated_plan.workspace_bundle_path,
        generated_plan.workspace_bundle_sha256,
    )
    policy_doc, policy_sha256 = policy_evidence(generated_plan.policy)
    manifest = generated_plan_manifest(
        organization_id=binding["organization_id"],
        project_id=binding["project_id"],
        revision_id=binding["revision_id"],
        revision_sha256=binding["revision_sha256"],
        stored_object=stored_plan,
        workspace_object=stored_workspace,
        plan=generated_plan,
        proposal=binding["proposal"],
        policy_digest=policy_sha256,
        created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        remote_state=(
            {"state_id": remote_state.state_id, "scope_sha256": remote_state.scope_sha256}
            if remote_state is not None
            else None
        ),
    )
    result = {
        "contract": RESULT_CONTRACT,
        "run_id": run_id,
        "codebuild_project": project_name,
        "codebuild_build_id": build_id,
        "codebuild_build_arn": build_arn,
        "input": {
            "key": input_key,
            "version_id": input_version_id,
            "sha256": input_sha256,
        },
        "binding": {
            key: binding[key]
            for key in (
                "organization_id",
                "project_id",
                "plan_id",
                "revision_id",
                "revision_sha256",
                "account_id",
                "region",
                "proposal_sha256",
                "context_sha256",
            )
        },
        "policy_evidence": policy_doc,
        "policy_sha256": policy_sha256,
        "untagged_resource_ownership": [
            {"address": item.address, "resource_type": item.resource_type}
            for item in generated_plan.untagged_resource_ownership
        ],
        "manifest": manifest,
        "manifest_sha256": canonical_json_digest(manifest),
        "planning_boundary": (
            "TENANT_ISOLATED_HTTP_STATE" if remote_state is not None else "INITIAL_PLAN_NO_REMOTE_STATE"
        ),
    }
    if remote_state is not None:
        result["remote_state"] = {
            "state_id": remote_state.state_id,
            "scope_sha256": remote_state.scope_sha256,
        }
    result_bytes = _canonical_json(result)
    if len(result_bytes) > MAX_RESULT_BYTES:
        raise NovaPlanBuildError("the verified plan result exceeds its size limit")
    if any(
        isinstance(secret, str) and secret and secret.encode("utf-8") in result_bytes
        for secret in (
            credentials.get("AccessKeyId"),
            credentials.get("SecretAccessKey"),
            credentials.get("SessionToken"),
        )
    ):
        raise NovaPlanBuildError("the verified plan result contains temporary credential material")
    result_sha256 = hashlib.sha256(result_bytes).hexdigest()
    result_key = _build_object_key(build_arn, "result.json")
    try:
        response = s3.put_object(
            Bucket=bucket,
            Key=result_key,
            Body=result_bytes,
            ContentLength=len(result_bytes),
            ContentType="application/json",
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=kms_key_arn,
            BucketKeyEnabled=True,
            IfNoneMatch="*",
            ExpectedBucketOwner=bucket_owner,
            Metadata={
                "davdeploy-run-id": run_id,
                "davdeploy-build-id": build_id,
                "davdeploy-result-sha256": result_sha256,
            },
        )
    except (BotoCoreError, ClientError, OSError, ValueError, TypeError):
        raise NovaPlanBuildError("the plan result could not be stored safely") from None
    version_id = _version_id(response)
    if (
        not isinstance(response, dict)
        or not version_id
        or response.get("BucketKeyEnabled") is not True
    ):
        raise NovaPlanBuildError("the plan result was not stored as a bucket-key version")
    return {
        "result_key": result_key,
        "result_version_id": version_id,
        "result_sha256": result_sha256,
        "saved_plan": stored_plan,
        "manifest_sha256": canonical_json_digest(manifest),
    }


def _read_exact_input(
    s3: Any,
    bucket: str,
    expected_bucket_owner: str,
    kms_key_arn: str,
    run_id: str,
    key: str,
    *,
    poll_attempts: int = 30,
    poll_interval_seconds: float = 2.0,
    sleeper=time.sleep,
) -> tuple[dict[str, Any], str, str]:
    if poll_attempts < 1 or poll_attempts > 60 or poll_interval_seconds < 0:
        raise NovaPlanBuildError("bounded build-input polling configuration is invalid")
    head = None
    version_id = None
    for attempt in range(poll_attempts):
        try:
            head = s3.head_object(
                Bucket=bucket,
                Key=key,
                ExpectedBucketOwner=expected_bucket_owner,
            )
            version_id = _version_id(head)
            break
        except ClientError as error:
            detail = error.response.get("Error") if isinstance(error.response, dict) else {}
            detail = detail if isinstance(detail, dict) else {}
            code = detail.get("Code")
            status = (error.response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
            if code == "NoSuchBucket" or (code not in {"AccessDenied", "403", "404", "NoSuchKey", "NotFound"} and status != 403 and status != 404):
                raise NovaPlanBuildError("the exact staged input could not be inspected") from None
            if attempt + 1 == poll_attempts:
                raise NovaPlanBuildError("the exact staged input did not become available") from None
            sleeper(poll_interval_seconds)
        except (BotoCoreError, OSError, TimeoutError, TypeError, ValueError, AttributeError):
            if attempt + 1 == poll_attempts:
                raise NovaPlanBuildError("the exact staged input could not be inspected") from None
            sleeper(poll_interval_seconds)
    if (
        not isinstance(head, dict)
        or not version_id
        or head.get("BucketKeyEnabled") is not True
        or head.get("ServerSideEncryption") != "aws:kms"
        or head.get("SSEKMSKeyId") != kms_key_arn
    ):
        raise NovaPlanBuildError("the exact staged input has no immutable object version")
    try:
        response = s3.get_object(
            Bucket=bucket,
            Key=key,
            VersionId=version_id,
            ExpectedBucketOwner=expected_bucket_owner,
        )
        body = response.get("Body")
        if body is None:
            raise NovaPlanBuildError("the exact staged input body is unavailable")
        try:
            raw = body.read(MAX_INPUT_BYTES + 1)
        finally:
            body.close()
    except (BotoCoreError, ClientError, OSError, KeyError, TypeError, ValueError, AttributeError):
        raise NovaPlanBuildError("the exact staged input could not be read") from None
    if not isinstance(raw, bytes) or len(raw) > MAX_INPUT_BYTES:
        raise NovaPlanBuildError("the exact staged input exceeds its size limit")
    metadata = response.get("Metadata")
    if (
        not version_id
        or response.get("VersionId") != version_id
        or response.get("ServerSideEncryption") != "aws:kms"
        or response.get("SSEKMSKeyId") != kms_key_arn
        or response.get("BucketKeyEnabled") is not True
        or response.get("ContentLength") != len(raw)
        or not isinstance(metadata, dict)
    ):
        raise NovaPlanBuildError("the exact staged input is not immutably versioned")
    try:
        document = json.loads(raw)
        digest = canonical_json_digest(document)
    except (json.JSONDecodeError, TypeError, ValueError):
        raise NovaPlanBuildError("the exact staged input is malformed") from None
    if (
        not isinstance(document, dict)
        or metadata.get("davdeploy-run-id") != run_id
        or metadata.get("davdeploy-input-sha256") != digest
    ):
        raise NovaPlanBuildError("the exact staged input failed its immutable digest check")
    return document, version_id, digest


def _validate_input_document(
    document: dict[str, Any], run_id: str, project_name: str, build_arn: str
) -> dict[str, Any]:
    expected_fields = {
        "contract",
        "run_id",
        "control_plane_run_id",
        "runner_project",
        "codebuild_build_arn",
        "request_document",
        "request_sha256",
        "customer_revision",
        "revision_id",
        "revision_sha256",
        "proposal",
        "proposal_sha256",
        "plan_role",
        "ownership_scope",
        "created_at",
    }
    expected_request_fields = {
        "contract",
        "organization_id",
        "project_id",
        "plan_id",
        "revision_id",
        "revision_sha256",
        "source_deployment_plan_id",
        "connection_id",
        "plan_role_arn",
        "target_account_id",
        "region",
        "generator_model",
        "runner_project",
    }
    request_document = document.get("request_document")
    request_sha256 = document.get("request_sha256")
    control_plane_run_id = document.get("control_plane_run_id")
    try:
        canonical_control_plane_run_id = str(uuid.UUID(control_plane_run_id))
    except (AttributeError, TypeError, ValueError):
        raise NovaPlanBuildError("durable control-plane request ID is invalid") from None
    if (
        set(document) != expected_fields | expected_request_fields
        or document.get("contract") != INPUT_CONTRACT
        or document.get("run_id") != run_id
        or canonical_control_plane_run_id != control_plane_run_id
        or document.get("runner_project") != project_name
        or document.get("codebuild_build_arn") != build_arn
        or not isinstance(request_document, dict)
        or set(request_document) != expected_request_fields
        or any(document.get(key) != request_document.get(key) for key in expected_request_fields)
        or not _is_digest(request_sha256)
        or canonical_json_digest(request_document) != request_sha256
    ):
        raise NovaPlanBuildError("durable plan request binding is invalid")
    revision = document.get("customer_revision")
    ownership_document = document.get("ownership_scope")
    plan_role = document.get("plan_role")
    if not isinstance(revision, dict) or not isinstance(ownership_document, dict):
        raise NovaPlanBuildError("durable revision or ownership data is missing")
    if not isinstance(plan_role, dict):
        raise NovaPlanBuildError("the verified customer plan role is missing")
    try:
        proposal = GeneratedDeploymentProposal.model_validate(document.get("proposal"))
    except (TypeError, ValueError):
        raise NovaPlanBuildError("the immutable proposal failed schema validation") from None

    revision_id = request_document.get("revision_id")
    revision_sha256 = request_document.get("revision_sha256")
    organization_id = request_document.get("organization_id")
    project_id = request_document.get("project_id")
    plan_id = request_document.get("plan_id")
    account_id = request_document.get("target_account_id")
    region = request_document.get("region")
    connection_id = request_document.get("connection_id")
    source_plan_id = request_document.get("source_deployment_plan_id")
    if (
        not all(isinstance(value, str) and value for value in (
            revision_id, organization_id, project_id, plan_id, connection_id, source_plan_id
        ))
        or not _is_digest(revision_sha256)
        or not isinstance(account_id, str)
        or not re.fullmatch(r"\d{12}", account_id)
        or not isinstance(region, str)
        or not re.fullmatch(r"[a-z]{2}(?:-[a-z0-9]+)+-\d", region)
        or document.get("revision_sha256") != revision_sha256
        or document.get("revision_id") != revision_id
        or document.get("proposal_sha256") != canonical_json_digest(
            proposal.model_dump(mode="json")
        )
        or proposal.source_revision != revision_id
        or proposal.requirements.region != region
        or proposal.context_digest != generation_context_digest(revision, revision_id)
        or _revision_digest(revision) != revision_sha256
        or not isinstance(revision.get("target"), dict)
    ):
        raise NovaPlanBuildError("proposal or immutable customer revision binding is invalid")
    target = revision["target"]
    if (
        target.get("account_id") != account_id
        or target.get("region") != region
        or target.get("connection_id") != connection_id
        or revision.get("source_deployment_plan_id") != source_plan_id
    ):
        raise NovaPlanBuildError("customer account or region does not match the revision")
    try:
        pricing_context = TrustedPlanPricingContext.from_persisted_revision(
            revision, expected_sha256=revision_sha256
        )
    except PlanPricingError:
        raise NovaPlanBuildError("trusted customer pricing context is invalid") from None
    if pricing_context.region != region:
        raise NovaPlanBuildError("trusted customer pricing region does not match the request")
    plan_role_arn = plan_role.get("arn")
    expected_role_arn = f"arn:aws:iam::{account_id}:role/davdeployPlan-{connection_id}"
    if set(plan_role) != {"arn"} or plan_role_arn != expected_role_arn:
        raise NovaPlanBuildError("customer plan role ARN binding is invalid")
    ownership_scope = PlanOwnershipScope(
        organization_id=organization_id,
        workspace_id=organization_id,
        project_id=project_id,
        plan_id=plan_id,
        revision_id=revision_id,
        environment_id=target.get("environment_id"),
    )
    expected_ownership_document = {
        "organization_id": ownership_scope.organization_id,
        "workspace_id": ownership_scope.workspace_id,
        "project_id": ownership_scope.project_id,
        "plan_id": ownership_scope.plan_id,
        "revision_id": ownership_scope.revision_id,
        "environment_id": ownership_scope.environment_id,
        "scope_sha256": ownership_scope.scope_sha256(),
        "plan_id_sha256": ownership_scope.plan_id_sha256(),
        "tags": ownership_scope.tags(),
    }
    if ownership_document != expected_ownership_document:
        raise NovaPlanBuildError("trusted ownership scope does not match this tenant and revision")
    return {
        "organization_id": organization_id,
        "project_id": project_id,
        "plan_id": plan_id,
        "control_plane_run_id": control_plane_run_id,
        "revision_id": revision_id,
        "revision_sha256": revision_sha256,
        "pricing_context": pricing_context,
        "account_id": account_id,
        "region": region,
        "connection_id": connection_id,
        "plan_role_arn": plan_role_arn,
        "proposal": proposal,
        "proposal_sha256": document["proposal_sha256"],
        "context_sha256": proposal.context_digest,
        "ownership_scope": ownership_scope,
    }


def _build_object_key(build_arn: str, filename: str) -> str:
    if filename not in {"input.json", "result.json"}:
        raise NovaPlanBuildError("CodeBuild artifact object name is invalid")
    return f"plans/nova-generated/builds/{build_arn}/{filename}"


def _validate_build_arn(value: Any, *, project_name: str, build_id: str) -> str:
    if (
        not isinstance(value, str)
        or not re.fullmatch(
            r"arn:aws(?:-us-gov|-cn)?:codebuild:[a-z0-9-]+:\d{12}:build/[A-Za-z0-9_-]+:[A-Za-z0-9-]+",
            value,
        )
        or not value.endswith(f":build/{build_id}")
        or not build_id.startswith(f"{project_name}:")
    ):
        raise NovaPlanBuildError("CodeBuild build ARN does not match its fixed project and ID")
    return value


def _put_saved_plan(
    s3: Any,
    bucket: str,
    expected_bucket_owner: str,
    kms_key_arn: str,
    run_id: str,
    key: str,
    path: str,
    expected_sha256: str,
) -> StoredPlanObject:
    plan_path = Path(path)
    if plan_path.is_symlink() or not plan_path.is_file():
        raise NovaPlanBuildError("saved plan output is unavailable")
    size = plan_path.stat().st_size
    if size <= 0 or size > MAX_PLAN_BYTES:
        raise NovaPlanBuildError("saved plan output is outside its size limit")
    digest = hashlib.sha256(plan_path.read_bytes()).hexdigest()
    if digest != expected_sha256:
        raise NovaPlanBuildError("saved plan output failed integrity verification")
    checksum = base64.b64encode(bytes.fromhex(digest)).decode("ascii")
    try:
        with plan_path.open("rb") as body:
            response = s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=body,
                ContentLength=size,
                ContentType="application/vnd.hashicorp.terraform.plan",
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=kms_key_arn,
                BucketKeyEnabled=True,
                ChecksumSHA256=checksum,
                IfNoneMatch="*",
                ExpectedBucketOwner=expected_bucket_owner,
                Metadata={"davdeploy-plan-sha256": digest, "davdeploy-run-id": run_id},
            )
    except (BotoCoreError, ClientError, OSError, ValueError, TypeError):
        raise NovaPlanBuildError("saved plan artifact could not be stored safely") from None
    version_id = _version_id(response)
    if (
        not isinstance(response, dict)
        or not version_id
        or response.get("BucketKeyEnabled") is not True
    ):
        raise NovaPlanBuildError("saved plan artifact is not a bucket-key version")
    return StoredPlanObject(bucket, key, version_id, size, digest)


def _put_execution_workspace(
    s3: Any,
    bucket: str,
    expected_bucket_owner: str,
    kms_key_arn: str,
    run_id: str,
    key: str,
    path: str,
    expected_sha256: str,
) -> StoredPlanObject:
    workspace_path = Path(path)
    if workspace_path.is_symlink() or not workspace_path.is_file():
        raise NovaPlanBuildError("Terraform execution workspace bundle is unavailable")
    size = workspace_path.stat().st_size
    if size <= 0 or size > MAX_PLAN_BYTES * 4:
        raise NovaPlanBuildError("Terraform execution workspace bundle exceeds its size limit")
    with workspace_path.open("rb") as workspace_file:
        digest = hashlib.file_digest(workspace_file, "sha256").hexdigest()
    if digest != expected_sha256:
        raise NovaPlanBuildError("Terraform execution workspace bundle failed integrity verification")
    checksum = base64.b64encode(bytes.fromhex(digest)).decode("ascii")
    try:
        with workspace_path.open("rb") as body:
            response = s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=body,
                ContentLength=size,
                ContentType="application/vnd.davdeploy.terraform-workspace+gzip",
                ServerSideEncryption="aws:kms",
                SSEKMSKeyId=kms_key_arn,
                BucketKeyEnabled=True,
                ChecksumSHA256=checksum,
                IfNoneMatch="*",
                ExpectedBucketOwner=expected_bucket_owner,
                Metadata={
                    "davdeploy-workspace-sha256": digest,
                    "davdeploy-run-id": run_id,
                },
            )
    except (BotoCoreError, ClientError, OSError, ValueError, TypeError):
        raise NovaPlanBuildError("Terraform execution workspace could not be stored safely") from None
    version_id = _version_id(response)
    if (
        not isinstance(response, dict)
        or not version_id
        or response.get("BucketKeyEnabled") is not True
    ):
        raise NovaPlanBuildError("Terraform workspace is not a bucket-key version")
    return StoredPlanObject(bucket, key, version_id, size, digest)


def _revision_digest(revision: dict[str, Any]) -> str:
    encoded = json.dumps(revision, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_json(document: dict[str, Any]) -> bytes:
    try:
        return json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise NovaPlanBuildError("plan result could not be encoded safely") from None


def _version_id(response: Any) -> str | None:
    version_id = response.get("VersionId") if isinstance(response, dict) else None
    return version_id if isinstance(version_id, str) and version_id not in {"", "null"} else None


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _validate_run_id(value: Any) -> str:
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, TypeError, ValueError):
        raise NovaPlanBuildError("durable Nova run ID is invalid") from None
    if str(parsed) != value.lower():
        raise NovaPlanBuildError("durable Nova run ID is invalid")
    return str(parsed)


def _validate_build_id(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{2,255}:[A-Za-z0-9_-]{2,255}", value
    ):
        raise NovaPlanBuildError("CodeBuild build ID is invalid")
    return value


def _validate_project(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,254}", value):
        raise NovaPlanBuildError("CodeBuild project name is invalid")
    return value


def _required_bucket(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", value):
        raise NovaPlanBuildError("plan artifact bucket configuration is invalid")
    return value


def _required_kms_key(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"arn:aws:kms:[a-z0-9-]+:\d{12}:key/[A-Za-z0-9-]+", value
    ):
        raise NovaPlanBuildError("plan artifact KMS key configuration is invalid")
    return value


def _required_account_id(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{12}", value):
        raise NovaPlanBuildError("plan artifact bucket owner configuration is invalid")
    return value


def main() -> int:
    """CodeBuild module entrypoint; failures never print request data or secrets."""
    run_id = os.getenv(RUN_ID_ENV, "")
    try:
        run_nova_plan_build(run_id)
    except Exception:  # noqa: BLE001 - never print request data or credentials
        print("Nova plan runner failed closed; no result was confirmed.")
        return 1
    print("Nova initial plan result was stored for authenticated reconciliation.")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by the CodeBuild entrypoint
    raise SystemExit(main())
