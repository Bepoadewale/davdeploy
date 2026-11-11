"""Encrypted, version-pinned storage for generated Terraform saved plans."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from davdeploy.generated_plan_ownership import (
    UNTAGGABLE_RESOURCE_TYPES_WITH_STATE_OWNERSHIP,
    UntaggedResourceOwnershipRecord,
)
from davdeploy.generated_plan_policy import GeneratedPlanPolicyResult
from davdeploy.generated_terraform_plan import GeneratedTerraformPlan

MAX_SAVED_PLAN_BYTES = 128 * 1024 * 1024
NOVA_PLAN_OBJECT_PREFIX = "plans/nova-generated"
UNAVAILABLE_PRICING_REASON = "regional_pricing_evaluator_not_integrated"


class GeneratedPlanArtifactError(RuntimeError):
    """Plan artifact storage failed without exposing provider or customer data."""


@dataclass(frozen=True)
class StoredPlanObject:
    bucket: str
    key: str
    version_id: str
    size_bytes: int
    sha256: str


class S3GeneratedPlanArtifactStore:
    """Write one exact plan version and verify its bytes through S3 before use."""

    def __init__(
        self,
        *,
        bucket: str,
        kms_key_arn: str,
        expected_bucket_owner: str,
        client: Any | None = None,
        max_bytes: int = MAX_SAVED_PLAN_BYTES,
    ) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
            raise ValueError("generated-plan bucket name is invalid")
        if not re.fullmatch(r"arn:aws:kms:[a-z0-9-]+:\d{12}:key/[a-f0-9-]+", kms_key_arn):
            raise ValueError("generated-plan KMS key must be a concrete key ARN")
        if not re.fullmatch(r"\d{12}", expected_bucket_owner):
            raise ValueError("expected S3 bucket owner is invalid")
        if max_bytes < 1 or max_bytes > MAX_SAVED_PLAN_BYTES:
            raise ValueError("generated-plan size limit is invalid")
        self.bucket = bucket
        self.kms_key_arn = kms_key_arn
        self.expected_bucket_owner = expected_bucket_owner
        self.client = client or boto3.client("s3")
        self.max_bytes = max_bytes

    def store_saved_plan(
        self,
        path: str | Path,
        *,
        organization_id: str,
        project_id: str,
        revision_id: str,
        run_id: str,
        expected_sha256: str,
    ) -> StoredPlanObject:
        plan_path = Path(path)
        self._validate_plan_file(plan_path, expected_sha256)
        try:
            parsed_run_id = uuid.UUID(run_id)
        except (AttributeError, ValueError):
            parsed_run_id = None
        if parsed_run_id is None or str(parsed_run_id) != run_id.lower():
            raise GeneratedPlanArtifactError("generated-plan run identifier is invalid")
        run_id = str(parsed_run_id)

        size = plan_path.stat().st_size
        key = self._key(organization_id, project_id, revision_id, run_id, expected_sha256)
        checksum = base64.b64encode(bytes.fromhex(expected_sha256)).decode("ascii")
        try:
            with plan_path.open("rb") as body:
                response = self.client.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=body,
                    ContentLength=size,
                    ContentType="application/vnd.hashicorp.terraform.plan",
                    ServerSideEncryption="aws:kms",
                    SSEKMSKeyId=self.kms_key_arn,
                    ChecksumSHA256=checksum,
                    IfNoneMatch="*",
                    ExpectedBucketOwner=self.expected_bucket_owner,
                    Metadata={
                        "davdeploy-plan-sha256": expected_sha256,
                        "davdeploy-run-id": run_id,
                    },
                )
            version_id = response.get("VersionId")
            if not isinstance(version_id, str) or not version_id or version_id == "null":
                raise GeneratedPlanArtifactError("generated-plan bucket versioning is unavailable")
            stored = StoredPlanObject(self.bucket, key, version_id, size, expected_sha256)
            self.verify_stored_plan(
                stored,
                run_id=run_id,
                organization_id=organization_id,
                project_id=project_id,
                revision_id=revision_id,
            )
        except GeneratedPlanArtifactError:
            raise
        except (BotoCoreError, ClientError, OSError, ValueError, TypeError):
            raise GeneratedPlanArtifactError(
                "generated plan could not be securely stored and verified"
            ) from None

        return StoredPlanObject(self.bucket, key, version_id, size, expected_sha256)

    def verify_stored_plan(
        self,
        stored: StoredPlanObject,
        *,
        run_id: str,
        organization_id: str,
        project_id: str,
        revision_id: str,
        build_arn: str | None = None,
    ) -> None:
        """Verify the exact S3 object version before exposing or approving its manifest."""
        expected_key = self._key(
            organization_id,
            project_id,
            revision_id,
            run_id,
            stored.sha256,
            build_arn=build_arn,
        )
        if (
            stored.bucket != self.bucket
            or stored.key != expected_key
            or not stored.version_id
            or stored.version_id == "null"
            or not re.fullmatch(r"[a-f0-9]{64}", stored.sha256)
            or stored.size_bytes <= 0
            or stored.size_bytes > self.max_bytes
        ):
            raise GeneratedPlanArtifactError("generated-plan artifact reference is invalid")
        try:
            head = self.client.head_object(
                Bucket=stored.bucket,
                Key=stored.key,
                VersionId=stored.version_id,
                ChecksumMode="ENABLED",
                ExpectedBucketOwner=self.expected_bucket_owner,
            )
            self._verify_head(head, stored.size_bytes, stored.sha256, run_id)
            digest = hashlib.sha256()
            size = 0
            response = self.client.get_object(
                Bucket=stored.bucket,
                Key=stored.key,
                VersionId=stored.version_id,
                ExpectedBucketOwner=self.expected_bucket_owner,
            )
            stream = response.get("Body")
            if stream is None:
                raise GeneratedPlanArtifactError("stored generated plan could not be read back")
            try:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise GeneratedPlanArtifactError(
                            "stored generated plan exceeds its size limit"
                        )
                    digest.update(chunk)
            finally:
                stream.close()
            if size != stored.size_bytes or digest.hexdigest() != stored.sha256:
                raise GeneratedPlanArtifactError(
                    "stored generated plan failed integrity verification"
                )
        except GeneratedPlanArtifactError:
            raise
        except (BotoCoreError, ClientError, OSError, ValueError, TypeError):
            raise GeneratedPlanArtifactError(
                "stored generated plan could not be verified"
            ) from None

    def _verify_head(self, head: dict[str, Any], size: int, digest: str, run_id: str) -> None:
        if (
            head.get("ContentLength") != size
            or head.get("ServerSideEncryption") != "aws:kms"
            or head.get("SSEKMSKeyId") != self.kms_key_arn
            or head.get("Metadata", {}).get("davdeploy-plan-sha256") != digest
            or head.get("Metadata", {}).get("davdeploy-run-id") != run_id
        ):
            raise GeneratedPlanArtifactError("stored generated plan metadata failed verification")

    def _validate_plan_file(self, path: Path, expected_sha256: str) -> None:
        if not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
            raise GeneratedPlanArtifactError("generated-plan digest is invalid")
        if path.is_symlink() or not path.is_file():
            raise GeneratedPlanArtifactError("generated saved plan is unavailable")
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            raise GeneratedPlanArtifactError("generated saved plan permissions are not private")
        size = path.stat().st_size
        if size <= 0 or size > self.max_bytes:
            raise GeneratedPlanArtifactError(
                "generated saved plan is outside the allowed size limit"
            )
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected_sha256:
            raise GeneratedPlanArtifactError("generated saved plan digest does not match")

    @staticmethod
    def _key(
        organization_id: str,
        project_id: str,
        revision_id: str,
        run_id: str,
        digest: str,
        *,
        build_arn: str | None = None,
    ) -> str:
        identifiers = (organization_id, project_id, revision_id)
        if any(
            not isinstance(value, str) or not value or len(value) > 160 for value in identifiers
        ):
            raise GeneratedPlanArtifactError("generated-plan tenant scope is invalid")
        scope = [hashlib.sha256(value.encode("utf-8")).hexdigest()[:32] for value in identifiers]
        if build_arn is not None:
            if not re.fullmatch(
                r"arn:aws(?:-us-gov|-cn)?:codebuild:[a-z0-9-]+:\d{12}:build/[A-Za-z0-9_-]+:[A-Za-z0-9-]+",
                build_arn,
            ):
                raise GeneratedPlanArtifactError("generated-plan CodeBuild ARN is invalid")
            return (
                f"{NOVA_PLAN_OBJECT_PREFIX}/builds/{build_arn}/"
                f"org-{scope[0]}/project-{scope[1]}/revision-{scope[2]}/{digest}.tfplan"
            )
        return f"{NOVA_PLAN_OBJECT_PREFIX}/org-{scope[0]}/project-{scope[1]}/revision-{scope[2]}/{run_id}/{digest}.tfplan"


def configured_generated_plan_artifact_store() -> S3GeneratedPlanArtifactStore | None:
    enabled = os.getenv("DAVDEPLOY_NOVA_PLAN_REVIEWS_ENABLED", "false").lower() == "true"
    if not enabled:
        return None
    bucket = os.getenv("DAVDEPLOY_NOVA_PLAN_ARTIFACT_BUCKET", "").strip()
    kms_key_arn = os.getenv("DAVDEPLOY_NOVA_PLAN_KMS_KEY_ARN", "").strip()
    owner = os.getenv("DAVDEPLOY_NOVA_PLAN_BUCKET_OWNER", "").strip()
    if not bucket or not kms_key_arn or not owner:
        raise GeneratedPlanArtifactError("generated-plan artifact storage is not fully configured")
    try:
        return S3GeneratedPlanArtifactStore(
            bucket=bucket,
            kms_key_arn=kms_key_arn,
            expected_bucket_owner=owner,
        )
    except ValueError:
        raise GeneratedPlanArtifactError(
            "generated-plan artifact storage configuration is invalid"
        ) from None


def canonical_json_digest(document: dict[str, Any]) -> str:
    encoded = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def policy_evidence(policy: GeneratedPlanPolicyResult) -> tuple[dict[str, Any], str]:
    findings = [
        {
            "code": item.code,
            "severity": item.severity,
            "address": item.address,
            "message": item.message,
        }
        for item in policy.findings
    ]
    evidence = {
        "version": policy.policy_version,
        "verdict": policy.verdict.value,
        "human_approval_required": policy.human_approval_required,
        "findings": findings,
    }
    return evidence, canonical_json_digest(evidence)


def generated_plan_manifest(
    *,
    organization_id: str,
    project_id: str,
    revision_id: str,
    revision_sha256: str,
    stored_object: StoredPlanObject,
    plan: GeneratedTerraformPlan,
    policy_digest: str,
    created_at: str,
    remote_state: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build canonical, secret-free review material for exact plan bytes."""
    if remote_state is not None:
        try:
            state_id = remote_state.get("state_id")
            canonical_state_id = str(uuid.UUID(state_id))
        except (AttributeError, TypeError, ValueError):
            raise GeneratedPlanArtifactError("remote Terraform state evidence is malformed") from None
        if (
            set(remote_state) != {"state_id", "scope_sha256"}
            or state_id != canonical_state_id
            or not re.fullmatch(r"[a-f0-9]{64}", remote_state.get("scope_sha256", ""))
        ):
            raise GeneratedPlanArtifactError("remote Terraform state evidence is malformed")
    if (
        not isinstance(plan.plan_access_policy_version, str)
        or not plan.plan_access_policy_version
        or not isinstance(plan.plan_access_policy_sha256, str)
        or not re.fullmatch(r"[a-f0-9]{64}", plan.plan_access_policy_sha256)
    ):
        raise GeneratedPlanArtifactError("customer plan permission evidence is malformed")
    untagged_resources = plan.untagged_resource_ownership
    if untagged_resources and remote_state is None:
        raise GeneratedPlanArtifactError(
            "untaggable resource ownership requires tenant-scoped remote state"
        )
    if not isinstance(untagged_resources, tuple) or len(untagged_resources) > 2_000 or any(
        not isinstance(item, UntaggedResourceOwnershipRecord)
        or item.resource_type not in UNTAGGABLE_RESOURCE_TYPES_WITH_STATE_OWNERSHIP
        or not item.address.startswith(item.resource_type + ".")
        for item in untagged_resources
    ):
        raise GeneratedPlanArtifactError("untaggable resource ownership evidence is malformed")
    if len({item.address for item in untagged_resources}) != len(untagged_resources):
        raise GeneratedPlanArtifactError("untaggable resource ownership evidence is malformed")
    manifest = {
        "manifest_version": (
            6
            if untagged_resources
            else 5 if remote_state is not None else 4
        ),
        "tenant": {
            "organization_id": organization_id,
            "project_id": project_id,
            "revision_id": revision_id,
        },
        "target": {"account_id": plan.target_account_id, "region": plan.region},
        "toolchain": {
            "terraform_version": plan.terraform_version,
            "aws_provider_version": plan.aws_provider_version,
            "provider_lockfile_sha256": plan.provider_lockfile_sha256,
        },
        "digests": {
            "customer_revision_sha256": revision_sha256,
            "proposal_sha256": plan.proposal_sha256,
            "trusted_context_sha256": plan.context_sha256,
            "configuration_sha256": plan.configuration_sha256,
            "ownership_scope_sha256": plan.ownership_scope_sha256,
            "ownership_plan_id_sha256": plan.ownership_plan_id_sha256,
            "saved_plan_sha256": stored_object.sha256,
            "policy_sha256": policy_digest,
        },
        "policy": {
            "version": plan.policy.policy_version,
            "verdict": plan.policy.verdict.value,
            "human_approval_required": plan.policy.human_approval_required,
        },
        "customer_plan_access": {
            "version": plan.plan_access_policy_version,
            "session_policy_sha256": plan.plan_access_policy_sha256,
        },
        "summary": {
            "create_count": plan.summary.create_count,
            "update_count": plan.summary.update_count,
            "delete_count": plan.summary.delete_count,
            "replacement_count": plan.summary.replacement_count,
            "read_count": plan.summary.read_count,
            "no_op_count": plan.summary.no_op_count,
            "drift_count": plan.summary.drift_count,
            "contains_sensitive_changes": plan.summary.contains_sensitive_changes,
        },
        "planning_boundary": {
            "mode": (
                "TENANT_ISOLATED_HTTP_STATE"
                if remote_state is not None
                else "INITIAL_PLAN_NO_REMOTE_STATE"
            ),
            "approval_allowed": False,
            "execution_allowed": False,
        },
        "pricing": {
            "status": "UNAVAILABLE",
            "region": plan.region,
            "currency": None,
            "monthly_cost": None,
            "evidence_sha256": None,
            "reason_code": UNAVAILABLE_PRICING_REASON,
        },
        "artifact": {
            "bucket": stored_object.bucket,
            "key": stored_object.key,
            "version_id": stored_object.version_id,
            "size_bytes": stored_object.size_bytes,
        },
        "created_at": created_at,
    }
    if remote_state is not None:
        manifest["remote_state"] = remote_state
    if untagged_resources:
        manifest["ownership_inventory"] = {
            "version": 1,
            "source": "TENANT_ISOLATED_HTTP_STATE",
            "untaggable_resources": [
                {"address": item.address, "resource_type": item.resource_type}
                for item in untagged_resources
            ],
        }
    return manifest


def has_complete_pricing_evidence(manifest: dict[str, Any]) -> bool:
    """Require a region-bound digest before an exact plan can be approved."""
    pricing = manifest.get("pricing")
    target = manifest.get("target")
    return (
        isinstance(pricing, dict)
        and pricing.get("status") == "COMPLETE"
        and isinstance(target, dict)
        and pricing.get("region") == target.get("region")
        and isinstance(pricing.get("evidence_sha256"), str)
        and bool(re.fullmatch(r"[a-f0-9]{64}", pricing["evidence_sha256"]))
    )


def policy_allows_human_review(policy: GeneratedPlanPolicyResult) -> bool:
    return (
        policy.human_approval_required
        and policy.verdict.value
        in {
            "REVIEW_REQUIRED",
            "ELIGIBLE_FOR_HUMAN_REVIEW",
        }
        and all(
            isinstance(finding.severity, str) and finding.severity.lower() == "review"
            for finding in policy.findings
        )
    )
