from __future__ import annotations

import base64

from davdeploy.nova_apply_artifacts import stage_nova_apply_artifacts
from davdeploy.nova_apply_contract import validate_nova_apply_request
from test_nova_apply_contract import _request_document

ACCOUNT = "654654474502"
BUCKET = f"davdeploy-plans-{ACCOUNT}"
KMS_KEY = f"arn:aws:kms:us-east-1:{ACCOUNT}:key/11111111-2222-3333-4444-555555555555"


class FakeS3:
    def __init__(self, request):
        self.objects = {}
        self.copy_calls = []
        for artifact, kind in (
            (request.saved_plan, "plan"),
            (request.execution_workspace, "workspace"),
        ):
            payload = (kind + " bytes").encode()
            # These fixtures use the exact expected source digest and size.
            payload = b"p" * artifact.size_bytes
            digest = artifact.sha256
            self.objects[(artifact.bucket, artifact.key, artifact.version_id)] = self._doc(
                payload,
                version_id=artifact.version_id,
                metadata={
                    f"davdeploy-{kind}-sha256": digest,
                    "davdeploy-run-id": request.tenant.source_plan_run_id,
                },
                digest=digest,
            )

    def head_object(self, *, Bucket, Key, VersionId=None, **_kwargs):
        candidates = [
            value
            for (bucket, key, version), value in self.objects.items()
            if bucket == Bucket and key == Key and (VersionId is None or version == VersionId)
        ]
        return candidates[-1] if candidates else {}

    def copy_object(self, *, Bucket, Key, CopySource, Metadata, **_kwargs):
        source = self.objects[(CopySource["Bucket"], CopySource["Key"], CopySource["VersionId"])]
        version_id = f"staged-{len(self.copy_calls) + 1}"
        self.copy_calls.append((CopySource, Bucket, Key))
        self.objects[(Bucket, Key, version_id)] = self._doc(
            source["_Body"],
            version_id=version_id,
            metadata=Metadata,
            digest=source["Metadata"][
                "davdeploy-plan-sha256"
                if CopySource["Key"].endswith(".tfplan")
                else "davdeploy-workspace-sha256"
            ],
        )
        return {"VersionId": version_id}

    @staticmethod
    def _doc(payload, *, version_id, metadata, digest):
        return {
            "VersionId": version_id,
            "ContentLength": len(payload),
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": KMS_KEY,
            "BucketKeyEnabled": True,
            "ChecksumSHA256": base64.b64encode(bytes.fromhex(digest)).decode(),
            "Metadata": metadata,
            "ETag": '"fixture-etag"',
            "_Body": payload,
        }


def test_stages_exact_versions_inside_the_active_apply_build_prefix():
    document = _request_document()
    request = validate_nova_apply_request(
        document,
        expected_run_id=document["run_id"],
        expected_codebuild_project=document["codebuild_project"],
        expected_codebuild_build_arn=document["codebuild_build_arn"],
        expected_artifact_bucket=BUCKET,
    )
    s3 = FakeS3(request)

    plan, workspace = stage_nova_apply_artifacts(
        request,
        s3_client=s3,
        expected_bucket_owner=ACCOUNT,
        expected_kms_key_arn=KMS_KEY,
    )

    prefix = (
        "plans/nova-generated/apply-builds/"
        f"{request.codebuild_build_arn}/artifacts/{request.run_id}/"
    )
    assert plan.key == prefix + "saved.tfplan"
    assert workspace.key == prefix + "execution-workspace.tar.gz"
    assert plan.sha256 == request.saved_plan.sha256
    assert workspace.sha256 == request.execution_workspace.sha256
    assert len(s3.copy_calls) == 2

    plan_again, workspace_again = stage_nova_apply_artifacts(
        request,
        s3_client=s3,
        expected_bucket_owner=ACCOUNT,
        expected_kms_key_arn=KMS_KEY,
    )
    assert plan_again.version_id == plan.version_id
    assert workspace_again.version_id == workspace.version_id
    assert len(s3.copy_calls) == 2


def test_staging_rejects_wrong_source_object_metadata():
    document = _request_document()
    request = validate_nova_apply_request(
        document,
        expected_run_id=document["run_id"],
        expected_codebuild_project=document["codebuild_project"],
        expected_codebuild_build_arn=document["codebuild_build_arn"],
        expected_artifact_bucket=BUCKET,
    )
    s3 = FakeS3(request)
    key = (request.saved_plan.bucket, request.saved_plan.key, request.saved_plan.version_id)
    s3.objects[key]["Metadata"]["davdeploy-run-id"] = "another-run"

    import pytest
    from davdeploy.nova_apply_artifacts import NovaApplyArtifactError

    with pytest.raises(NovaApplyArtifactError, match="source artifact metadata"):
        stage_nova_apply_artifacts(
            request,
            s3_client=s3,
            expected_bucket_owner=ACCOUNT,
            expected_kms_key_arn=KMS_KEY,
        )
