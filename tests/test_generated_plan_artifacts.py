from __future__ import annotations

import hashlib
import os
import uuid
from dataclasses import replace
from io import BytesIO

import pytest
from botocore.exceptions import ClientError
from davdeploy.generated_deployment_contract import (
    CostAssumption,
    GeneratedDeploymentProposal,
    GeneratedResource,
    HealthAssertion,
    RecoveryRequirement,
    WorkloadRequirements,
)
from davdeploy.generated_plan_artifacts import (
    GeneratedPlanArtifactError,
    S3GeneratedPlanArtifactStore,
    StoredPlanObject,
    canonical_json_digest,
    generated_plan_manifest,
    has_complete_pricing_evidence,
    policy_allows_human_review,
    policy_evidence,
)
from davdeploy.generated_plan_inspection import TerraformPlanSummary
from davdeploy.generated_plan_ownership import UntaggedResourceOwnershipRecord
from davdeploy.generated_plan_policy import (
    GeneratedPlanPolicyResult,
    PlanPolicyFinding,
    PlanPolicyVerdict,
)
from davdeploy.generated_terraform_plan import GeneratedTerraformPlan

BUCKET = "davdeploy-tfplans-654654474502"
KMS_KEY = "arn:aws:kms:us-east-1:654654474502:key/12345678-1234-1234-1234-123456789012"
OWNER = "654654474502"
RUN_ID = str(uuid.UUID("12345678-1234-1234-1234-123456789012"))
PLAN_BYTES = b"encrypted plan fixture bytes"


def verification_proposal() -> GeneratedDeploymentProposal:
    return GeneratedDeploymentProposal(
        contract_version="1.0",
        source_revision="revision-1",
        context_digest="c" * 64,
        resources=(
            GeneratedResource(
                resource_id="storage",
                resource_type="aws_s3_bucket",
                name="app_storage",
                arguments={"bucket": "app-data-123"},
                rationale="Private application storage.",
            ),
        ),
        requirements=WorkloadRequirements(region="us-east-1"),
        health_assertions=(
            HealthAssertion(
                kind="storage_roundtrip",
                target_resource_id="storage",
                description="Application can store and retrieve a synthetic object.",
            ),
        ),
        recovery=RecoveryRequirement(
            backup_required=True,
            recovery_point_objective_minutes=60,
            recovery_time_objective_minutes=240,
            destructive_change_notes="Retain the prior version during recovery.",
        ),
        cost_assumptions=(
            CostAssumption(
                resource_id="storage",
                description="Low initial object volume.",
                source="customer assumption",
                captured_at="2026-11-13T00:00:00Z",
            ),
        ),
        assumptions=("Initial workload has low request volume.",),
        limitations=("This proposal has no executed health evidence.",),
    )


class FakeS3:
    def __init__(
        self, *, stored_bytes: bytes = PLAN_BYTES, head_overrides=None, version_id="v-plan-1"
    ):
        self.stored_bytes = stored_bytes
        self.head_overrides = head_overrides or {}
        self.version_id = version_id
        self.calls = []

    def put_object(self, **kwargs):
        self.calls.append(("put_object", kwargs))
        self.uploaded = kwargs["Body"].read()
        self.put_kwargs = kwargs
        return {"VersionId": self.version_id}

    def head_object(self, **kwargs):
        self.calls.append(("head_object", kwargs))
        result = {
            "ContentLength": len(PLAN_BYTES),
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": KMS_KEY,
            "Metadata": {
                "davdeploy-plan-sha256": hashlib.sha256(PLAN_BYTES).hexdigest(),
                "davdeploy-run-id": RUN_ID,
            },
        }
        result.update(self.head_overrides)
        return result

    def get_object(self, **kwargs):
        self.calls.append(("get_object", kwargs))
        return {"Body": BytesIO(self.stored_bytes)}


def store(client=None, *, max_bytes=1024):
    return S3GeneratedPlanArtifactStore(
        bucket=BUCKET,
        kms_key_arn=KMS_KEY,
        expected_bucket_owner=OWNER,
        client=client or FakeS3(),
        max_bytes=max_bytes,
    )


def private_plan_file(tmp_path, payload=PLAN_BYTES):
    path = tmp_path / "saved.tfplan"
    path.write_bytes(payload)
    os.chmod(path, 0o600)
    return path


def store_plan(tmp_path, client=None, *, expected_digest=None, **kwargs):
    path = private_plan_file(tmp_path)
    digest = expected_digest or hashlib.sha256(PLAN_BYTES).hexdigest()
    return store(client).store_saved_plan(
        path,
        organization_id="org-private-customer",
        project_id="project-private-name",
        revision_id="revision-abc",
        run_id=RUN_ID,
        expected_sha256=digest,
        **kwargs,
    )


def test_store_uploads_conditionally_with_kms_and_verifies_exact_version(tmp_path):
    client = FakeS3()
    result = store_plan(tmp_path, client)

    assert result.bucket == BUCKET
    assert result.version_id == "v-plan-1"
    assert result.sha256 == hashlib.sha256(PLAN_BYTES).hexdigest()
    assert result.size_bytes == len(PLAN_BYTES)
    assert result.key.startswith("plans/nova-generated/org-")
    assert "org-private-customer" not in result.key
    assert "project-private-name" not in result.key
    assert client.uploaded == PLAN_BYTES
    put = client.put_kwargs
    assert put["IfNoneMatch"] == "*"
    assert put["ServerSideEncryption"] == "aws:kms"
    assert put["SSEKMSKeyId"] == KMS_KEY
    assert put["ExpectedBucketOwner"] == OWNER
    assert put["Metadata"]["davdeploy-run-id"] == RUN_ID
    assert [name for name, _ in client.calls] == ["put_object", "head_object", "get_object"]
    for operation in ("head_object", "get_object"):
        call = next(kwargs for name, kwargs in client.calls if name == operation)
        assert call["VersionId"] == result.version_id
        assert call["ExpectedBucketOwner"] == OWNER
    head = next(kwargs for name, kwargs in client.calls if name == "head_object")
    assert head["ChecksumMode"] == "ENABLED"


def test_reverification_requires_exact_tenant_scoped_object_key():
    client = FakeS3()
    configured = store(client)
    digest = hashlib.sha256(PLAN_BYTES).hexdigest()
    expected_key = configured._key("org-1", "project-1", "revision-1", RUN_ID, digest)
    stored = StoredPlanObject(BUCKET, expected_key, "v-plan-1", len(PLAN_BYTES), digest)

    configured.verify_stored_plan(
        stored,
        run_id=RUN_ID,
        organization_id="org-1",
        project_id="project-1",
        revision_id="revision-1",
    )
    assert [name for name, _ in client.calls] == ["head_object", "get_object"]

    with pytest.raises(GeneratedPlanArtifactError, match="reference is invalid"):
        configured.verify_stored_plan(
            stored,
            run_id=RUN_ID,
            organization_id="org-1",
            project_id="different-project",
            revision_id="revision-1",
        )


@pytest.mark.parametrize(
    ("payload", "mode", "expected_digest", "limit", "message"),
    [
        (PLAN_BYTES, 0o644, None, 1024, "permissions are not private"),
        (PLAN_BYTES, 0o600, "0" * 64, 1024, "digest does not match"),
        (PLAN_BYTES * 2, 0o600, None, 1, "outside the allowed size limit"),
    ],
)
def test_rejects_untrusted_local_saved_plan_before_s3(
    tmp_path, payload, mode, expected_digest, limit, message
):
    path = private_plan_file(tmp_path, payload)
    os.chmod(path, mode)
    client = FakeS3()
    digest = expected_digest or hashlib.sha256(payload).hexdigest()
    with pytest.raises(GeneratedPlanArtifactError, match=message):
        store(client, max_bytes=limit).store_saved_plan(
            path,
            organization_id="org-1",
            project_id="project-1",
            revision_id="revision-1",
            run_id=RUN_ID,
            expected_sha256=digest,
        )
    assert client.calls == []


def test_rejects_symlink_saved_plan(tmp_path):
    source = private_plan_file(tmp_path, PLAN_BYTES)
    linked = tmp_path / "link.tfplan"
    linked.symlink_to(source)
    with pytest.raises(GeneratedPlanArtifactError, match="saved plan is unavailable"):
        store().store_saved_plan(
            linked,
            organization_id="org-1",
            project_id="project-1",
            revision_id="revision-1",
            run_id=RUN_ID,
            expected_sha256=hashlib.sha256(PLAN_BYTES).hexdigest(),
        )


@pytest.mark.parametrize("version_id", [None, "", "null"])
def test_requires_versioned_bucket_response(tmp_path, version_id):
    client = FakeS3(version_id=version_id)
    with pytest.raises(GeneratedPlanArtifactError, match="versioning is unavailable"):
        store_plan(tmp_path, client)
    assert [name for name, _ in client.calls] == ["put_object"]


@pytest.mark.parametrize(
    "head_overrides",
    [
        {"ContentLength": 1},
        {"ServerSideEncryption": "AES256"},
        {"SSEKMSKeyId": "arn:aws:kms:us-east-1:654654474502:key/wrong"},
        {"Metadata": {"davdeploy-plan-sha256": "wrong", "davdeploy-run-id": RUN_ID}},
    ],
)
def test_rejects_mismatched_s3_head_metadata(tmp_path, head_overrides):
    client = FakeS3(head_overrides=head_overrides)
    with pytest.raises(GeneratedPlanArtifactError, match="metadata failed verification"):
        store_plan(tmp_path, client)
    assert [name for name, _ in client.calls] == ["put_object", "head_object"]


@pytest.mark.parametrize("stored_bytes", [b"tampered bytes", PLAN_BYTES + b"extra"])
def test_rejects_readback_bytes_that_do_not_match_saved_plan(tmp_path, stored_bytes):
    client = FakeS3(stored_bytes=stored_bytes)
    with pytest.raises(GeneratedPlanArtifactError, match="integrity verification"):
        store_plan(tmp_path, client)


class FailingS3:
    def put_object(self, **_kwargs):
        raise ClientError(
            {
                "Error": {
                    "Code": "AccessDenied",
                    "Message": "sensitive provider values must not leak",
                }
            },
            "PutObject",
        )


def test_s3_errors_are_redacted(tmp_path):
    with pytest.raises(GeneratedPlanArtifactError) as error:
        store_plan(tmp_path, FailingS3())
    assert str(error.value) == "generated plan could not be securely stored and verified"
    assert "sensitive provider" not in str(error.value)


def test_canonical_manifest_digest_is_stable_and_binds_artifact_and_policy():
    left = {"b": 2, "nested": {"z": True, "a": [1, 2]}, "a": "value"}
    right = {"a": "value", "nested": {"a": [1, 2], "z": True}, "b": 2}
    digest = canonical_json_digest(left)
    assert digest == canonical_json_digest(right)
    assert digest != canonical_json_digest({**right, "b": 3})

    stored = StoredPlanObject(BUCKET, "plans/nova-generated/opaque.tfplan", "v42", 12, "a" * 64)
    policy = GeneratedPlanPolicyResult(
        PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW,
        "policy-v1",
        (
            PlanPolicyFinding(
                "safe_create", "review", "aws_s3_bucket.app", "Creates private storage."
            ),
        ),
    )
    evidence, evidence_digest = policy_evidence(policy)
    assert evidence["verdict"] == "ELIGIBLE_FOR_HUMAN_REVIEW"
    assert evidence_digest == canonical_json_digest(evidence)
    assert policy_allows_human_review(policy)

    proposal = verification_proposal()
    proposal_sha256 = canonical_json_digest(proposal.model_dump(mode="json"))
    plan = GeneratedTerraformPlan(
        summary=TerraformPlanSummary(
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
        ),
        policy=policy,
        target_account_id=OWNER,
        region="us-east-1",
        terraform_version="1.14.7",
        aws_provider_version="5.100.0",
        provider_lockfile_sha256="b" * 64,
        proposal_sha256=proposal_sha256,
        context_sha256="e" * 64,
        configuration_sha256="d" * 64,
        ownership_scope_sha256="f" * 64,
        ownership_plan_id_sha256="9" * 64,
        saved_plan_sha256="a" * 64,
        saved_plan_path="/private/path/not-in-manifest",
    )
    manifest = generated_plan_manifest(
        organization_id="org-1",
        project_id="project-1",
        revision_id="revision-1",
        revision_sha256="e" * 64,
        stored_object=stored,
        plan=plan,
        proposal=proposal,
        policy_digest=evidence_digest,
        created_at="2026-11-04T00:00:00Z",
    )
    assert manifest["artifact"]["version_id"] == "v42"
    assert manifest["digests"]["policy_sha256"] == evidence_digest
    assert manifest["manifest_version"] == 5
    assert manifest["proposal_requirements"] == {
        "status": "PROPOSED_UNVALIDATED_NOT_EXECUTED",
        "health_assertions": [
            {
                "kind": "storage_roundtrip",
                "target_resource_id": "storage",
                "description": "Application can store and retrieve a synthetic object.",
            }
        ],
        "recovery": {
            "backup_required": True,
            "recovery_point_objective_minutes": 60,
            "recovery_time_objective_minutes": 240,
            "destructive_change_notes": "Retain the prior version during recovery.",
        },
        "cost_assumptions": [
            {
                "resource_id": "storage",
                "description": "Low initial object volume.",
                "source": "customer assumption",
                "captured_at": "2026-11-13T00:00:00Z",
            }
        ],
        "assumptions": ["Initial workload has low request volume."],
        "limitations": ["This proposal has no executed health evidence."],
    }
    assert manifest["customer_plan_access"] == {
        "version": "NOT_APPLICABLE",
        "session_policy_sha256": "0" * 64,
    }
    assert manifest["pricing"] == {
        "status": "UNAVAILABLE",
        "region": "us-east-1",
        "currency": None,
        "monthly_cost": None,
        "evidence_sha256": None,
        "reason_code": "regional_pricing_evaluator_not_integrated",
    }
    assert not has_complete_pricing_evidence(manifest)
    assert manifest["digests"]["ownership_scope_sha256"] == "f" * 64
    assert manifest["digests"]["ownership_plan_id_sha256"] == "9" * 64
    assert "private/path" not in repr(manifest)
    assert canonical_json_digest(manifest) != canonical_json_digest(
        {**manifest, "created_at": "later"}
    )
    changed_proposal = proposal.model_copy(update={"limitations": ("different",)})
    with pytest.raises(GeneratedPlanArtifactError, match="proposal verification evidence"):
        generated_plan_manifest(
            organization_id="org-1",
            project_id="project-1",
            revision_id="revision-1",
            revision_sha256="e" * 64,
            stored_object=stored,
            plan=plan,
            proposal=changed_proposal,
            policy_digest=evidence_digest,
            created_at="2026-11-04T00:00:00Z",
        )

    remote_state = {"state_id": RUN_ID, "scope_sha256": "1" * 64}
    route_plan = replace(
        plan,
        untagged_resource_ownership=(
            UntaggedResourceOwnershipRecord(
                address="aws_apigatewayv2_route.application",
                resource_type="aws_apigatewayv2_route",
            ),
        ),
    )
    owned_manifest = generated_plan_manifest(
        organization_id="org-1",
        project_id="project-1",
        revision_id="revision-1",
        revision_sha256="e" * 64,
        stored_object=stored,
        plan=route_plan,
        proposal=proposal,
        policy_digest=evidence_digest,
        created_at="2026-11-04T00:00:00Z",
        remote_state=remote_state,
    )
    assert owned_manifest["manifest_version"] == 7
    assert owned_manifest["remote_state"] == remote_state
    assert owned_manifest["ownership_inventory"] == {
        "version": 1,
        "source": "TENANT_ISOLATED_HTTP_STATE",
        "untaggable_resources": [
            {
                "address": "aws_apigatewayv2_route.application",
                "resource_type": "aws_apigatewayv2_route",
            }
        ],
    }
    with pytest.raises(GeneratedPlanArtifactError, match="requires tenant-scoped remote state"):
        generated_plan_manifest(
            organization_id="org-1",
            project_id="project-1",
            revision_id="revision-1",
            revision_sha256="e" * 64,
            stored_object=stored,
            plan=route_plan,
            proposal=proposal,
            policy_digest=evidence_digest,
            created_at="2026-11-04T00:00:00Z",
        )


@pytest.mark.parametrize(
    "policy",
    [
        GeneratedPlanPolicyResult(PlanPolicyVerdict.DENY, "p1", ()),
        GeneratedPlanPolicyResult(PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW, "p1", (), False),
        GeneratedPlanPolicyResult(
            PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW,
            "p1",
            (PlanPolicyFinding("unknown_severity", "unknown", None, "Unknown."),),
        ),
    ],
)
def test_policy_must_require_human_approval_and_not_be_denied(policy):
    assert not policy_allows_human_review(policy)
