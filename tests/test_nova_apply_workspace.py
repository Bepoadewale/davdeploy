from __future__ import annotations

import base64
import hashlib
import stat
from copy import deepcopy
from io import BytesIO
from pathlib import Path

import pytest
from davdeploy.generated_plan_artifacts import (
    S3GeneratedPlanArtifactStore,
    canonical_json_digest,
)
from davdeploy.generated_terraform_plan import (
    PINNED_AWS_PROVIDER_VERSION,
    PINNED_TERRAFORM_VERSION,
    create_execution_workspace_bundle,
)
from davdeploy.nova_apply_contract import (
    validate_nova_apply_request,
)
from davdeploy.nova_apply_workspace import (
    NovaApplyWorkspaceError,
    prepare_nova_apply_workspace,
)
from test_nova_apply_contract import _request_document

ACCOUNT_ID = "654654474502"
BUCKET = "davdeploy-plans-654654474502"
KMS_KEY = f"arn:aws:kms:us-east-1:{ACCOUNT_ID}:key/11111111-2222-3333-4444-555555555555"
PLAN_BYTES = b"exact terraform saved plan"
LOCKFILE_BYTES = (
    f'test lockfile with aws provider version "{PINNED_AWS_PROVIDER_VERSION}"\n'.encode()
)


class S3ArtifactFixture:
    def __init__(self, objects):
        self.objects = objects

    def head_object(self, *, Bucket, Key, VersionId, **_kwargs):
        payload, metadata = self.objects[(Bucket, Key, VersionId)]
        digest = hashlib.sha256(payload).hexdigest()
        return self._metadata(payload, metadata, digest)

    def get_object(self, *, Bucket, Key, VersionId, **_kwargs):
        payload, metadata = self.objects[(Bucket, Key, VersionId)]
        digest = hashlib.sha256(payload).hexdigest()
        return {**self._metadata(payload, metadata, digest), "Body": BytesIO(payload)}

    @staticmethod
    def _metadata(payload, metadata, digest):
        return {
            "VersionId": metadata["version_id"],
            "ContentLength": len(payload),
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": KMS_KEY,
            "BucketKeyEnabled": True,
            "ChecksumSHA256": base64.b64encode(
                bytes.fromhex(metadata.get("checksum_sha256", digest))
            ).decode("ascii"),
            "Metadata": metadata["metadata"],
        }


def _prepared_request(tmp_path: Path):
    request_document = _request_document()
    source_plan_run_id = request_document["tenant"]["source_plan_run_id"]
    plan_sha = hashlib.sha256(PLAN_BYTES).hexdigest()
    workspace_source = tmp_path / "workspace-source"
    (workspace_source / ".terraform/providers/hashicorp/aws").mkdir(parents=True)
    workspace_source.chmod(0o700)
    (workspace_source / "main.tf.json").write_text("{}", encoding="utf-8")
    saved_plan = workspace_source / "saved.tfplan"
    saved_plan.write_bytes(PLAN_BYTES)
    saved_plan.chmod(0o600)
    lockfile = workspace_source / ".terraform.lock.hcl"
    lockfile.write_bytes(LOCKFILE_BYTES)
    provider_binary = (
        workspace_source
        / ".terraform/providers/hashicorp/aws/5.99.0/darwin_arm64/terraform-provider-aws_v5.99.0"
    )
    provider_binary.parent.mkdir(parents=True)
    provider_binary.write_bytes(b"provider fixture")
    workspace_archive, workspace_sha = create_execution_workspace_bundle(workspace_source)
    workspace_bytes = workspace_archive.read_bytes()

    plan = {
        "bucket": BUCKET,
        "key": S3GeneratedPlanArtifactStore._key(
            "org-1", "project-1", "revision-1", source_plan_run_id, plan_sha
        ),
        "version_id": "plan-version-exact",
        "size_bytes": len(PLAN_BYTES),
        "sha256": plan_sha,
    }
    workspace = {
        "bucket": BUCKET,
        "key": S3GeneratedPlanArtifactStore._key(
            "org-1",
            "project-1",
            "revision-1",
            source_plan_run_id,
            workspace_sha,
            artifact_kind="workspace",
        ),
        "version_id": "workspace-version-exact",
        "size_bytes": len(workspace_bytes),
        "sha256": workspace_sha,
    }
    manifest = deepcopy(request_document["manifest"])
    manifest["toolchain"] = {
        "terraform_version": PINNED_TERRAFORM_VERSION,
        "aws_provider_version": PINNED_AWS_PROVIDER_VERSION,
        "provider_lockfile_sha256": hashlib.sha256(LOCKFILE_BYTES).hexdigest(),
    }
    manifest["artifact"] = {key: value for key, value in plan.items() if key != "sha256"}
    manifest["execution_workspace"] = workspace
    manifest["digests"]["saved_plan_sha256"] = plan_sha
    manifest["digests"]["workspace_sha256"] = workspace_sha
    manifest_sha = canonical_json_digest(manifest)
    request_document["manifest"] = manifest
    request_document["manifest_sha256"] = manifest_sha
    request_document["approval"]["approved_manifest_sha256"] = manifest_sha
    request_document["saved_plan"] = plan
    request_document["execution_workspace"] = workspace
    request = validate_nova_apply_request(
        request_document,
        expected_run_id=request_document["run_id"],
        expected_codebuild_project=request_document["codebuild_project"],
        expected_codebuild_build_arn=request_document["codebuild_build_arn"],
        expected_artifact_bucket=BUCKET,
    )
    objects = {
        (BUCKET, plan["key"], plan["version_id"]): (
            PLAN_BYTES,
            {
                "version_id": plan["version_id"],
                "metadata": {
                    "davdeploy-plan-sha256": plan_sha,
                    "davdeploy-run-id": source_plan_run_id,
                },
                "checksum_sha256": plan_sha,
            },
        ),
        (BUCKET, workspace["key"], workspace["version_id"]): (
            workspace_bytes,
            {
                "version_id": workspace["version_id"],
                "metadata": {
                    "davdeploy-workspace-sha256": workspace_sha,
                    "davdeploy-run-id": source_plan_run_id,
                },
            },
        ),
    }
    return request, objects, workspace_sha


def test_prepares_only_exact_encrypted_plan_and_workspace_versions(tmp_path):
    request, objects, workspace_sha = _prepared_request(tmp_path)

    prepared = prepare_nova_apply_workspace(
        request,
        s3_client=S3ArtifactFixture(objects),
        expected_bucket_owner=ACCOUNT_ID,
        expected_kms_key_arn=KMS_KEY,
        workspace_root=tmp_path / "apply-workspace",
    )

    assert prepared.saved_plan_path.read_bytes() == PLAN_BYTES
    assert prepared.saved_plan_path.name == "saved.tfplan"
    assert stat.S_IMODE(prepared.root.stat().st_mode) & 0o077 == 0
    assert stat.S_IMODE(prepared.saved_plan_path.stat().st_mode) & 0o077 == 0
    assert hashlib.sha256((prepared.root / ".terraform.lock.hcl").read_bytes()).hexdigest() == (
        request.manifest["toolchain"]["provider_lockfile_sha256"]
    )
    assert prepared.provider_lockfile_sha256 == request.manifest["toolchain"]["provider_lockfile_sha256"]
    assert request.execution_workspace.sha256 == workspace_sha
    assert (prepared.root / "main.tf.json").read_text(encoding="utf-8") == "{}"


def test_refuses_tampered_plan_bytes_after_exact_s3_version_read(tmp_path):
    request, objects, _ = _prepared_request(tmp_path)
    plan_key = (request.saved_plan.bucket, request.saved_plan.key, request.saved_plan.version_id)
    _old_bytes, metadata = objects[plan_key]
    objects[plan_key] = (b"x" * len(PLAN_BYTES), metadata)

    with pytest.raises(NovaApplyWorkspaceError, match="exact digest check"):
        prepare_nova_apply_workspace(
            request,
            s3_client=S3ArtifactFixture(objects),
            expected_bucket_owner=ACCOUNT_ID,
            expected_kms_key_arn=KMS_KEY,
            workspace_root=tmp_path / "apply-workspace",
        )


def test_refuses_mismatched_encryption_metadata(tmp_path):
    request, objects, _ = _prepared_request(tmp_path)
    plan_key = (request.saved_plan.bucket, request.saved_plan.key, request.saved_plan.version_id)
    plan_bytes, metadata = objects[plan_key]
    metadata["metadata"]["davdeploy-plan-sha256"] = "d" * 64

    with pytest.raises(NovaApplyWorkspaceError, match="metadata did not match"):
        prepare_nova_apply_workspace(
            request,
            s3_client=S3ArtifactFixture({plan_key: (plan_bytes, metadata)}),
            expected_bucket_owner=ACCOUNT_ID,
            expected_kms_key_arn=KMS_KEY,
            workspace_root=tmp_path / "apply-workspace",
        )


def test_refuses_existing_or_symlink_workspace_root(tmp_path):
    request, objects, _ = _prepared_request(tmp_path)
    existing = tmp_path / "existing"
    existing.mkdir()

    with pytest.raises(NovaApplyWorkspaceError, match="must be new and private"):
        prepare_nova_apply_workspace(
            request,
            s3_client=S3ArtifactFixture(objects),
            expected_bucket_owner=ACCOUNT_ID,
            expected_kms_key_arn=KMS_KEY,
            workspace_root=existing,
        )


def test_refuses_workspace_with_a_different_approved_lockfile_digest(tmp_path):
    request, objects, _ = _prepared_request(tmp_path)
    request.manifest["toolchain"]["provider_lockfile_sha256"] = "0" * 64

    with pytest.raises(NovaApplyWorkspaceError, match="toolchain does not match approval"):
        prepare_nova_apply_workspace(
            request,
            s3_client=S3ArtifactFixture(objects),
            expected_bucket_owner=ACCOUNT_ID,
            expected_kms_key_arn=KMS_KEY,
            workspace_root=tmp_path / "apply-workspace",
        )

