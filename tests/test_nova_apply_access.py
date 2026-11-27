from __future__ import annotations

import json

import pytest
from davdeploy.nova_apply_access import (
    MAX_SESSION_POLICY_BYTES,
    NOVA_APPLY_ACCESS_POLICY_VERSION,
    NovaApplyAccessPolicyError,
    build_nova_apply_access_policy,
)

ACCOUNT = "123456789012"
REGION = "us-east-1"


def change(resource_type: str, actions: list[str], before=None, after=None) -> dict:
    return {
        "mode": "managed",
        "type": resource_type,
        "address": f"{resource_type}.example",
        "change": {"actions": actions, "before": before, "after": after},
    }


def policy(*changes: dict):
    return build_nova_apply_access_policy(
        {"resource_changes": list(changes)}, account_id=ACCOUNT, region=REGION
    )


def test_apply_scope_binds_supported_create_to_exact_bucket_and_operations():
    result = policy(change("aws_s3_bucket", ["create"], after={"bucket": "pilot-data"}))

    assert result.version == "nova-apply-plan-scope.v2"
    assert result.version == NOVA_APPLY_ACCESS_POLICY_VERSION
    allows = [
        statement
        for statement in result.document["Statement"]
        if statement["Effect"] == "Allow" and statement.get("Resource") != "*"
    ]
    assert len(allows) == 1
    assert allows[0]["Resource"] == "arn:aws:s3:::pilot-data"
    assert {
        "s3:CreateBucket",
        "s3:GetBucketLocation",
        "s3:GetBucketTagging",
        "s3:ListBucket",
        "s3:PutBucketTagging",
    } <= set(allows[0]["Action"])
    assert result.sha256
    exact_resource_deny = next(
        statement
        for statement in result.document["Statement"]
        if statement.get("Effect") == "Deny"
        and "NotAction" in statement
        and statement.get("Resource") == "arn:aws:s3:::pilot-data"
    )
    assert set(allows[0]["Action"]) <= set(exact_resource_deny["NotAction"])
    assert "sts:GetCallerIdentity" in exact_resource_deny["NotAction"]
    assert {
        "Effect": "Allow",
        "Action": "sts:GetCallerIdentity",
        "Resource": "*",
    } in result.document["Statement"]
    # This action is in the role's cross-service maximum profile but is not
    # allowed for this create plan. The explicit deny blocks direct session-
    # principal resource-policy grants that would bypass an implicit deny.
    assert "s3:PutBucketPolicy" not in allows[0]["Action"]
    assert "s3:PutBucketPolicy" not in exact_resource_deny["NotAction"]
    assert any(
        statement.get("Effect") == "Deny"
        and statement.get("NotAction") == "sts:GetCallerIdentity"
        and statement.get("NotResource") == ["arn:aws:s3:::pilot-data"]
        for statement in result.document["Statement"]
    )
    assert any(
        statement.get("Effect") == "Deny"
        and statement.get("Action") == "s3:*"
        and statement.get("Condition") == {
            "StringNotEquals": {"aws:ResourceAccount": ACCOUNT}
        }
        for statement in result.document["Statement"]
    )


def test_apply_scope_groups_identical_per_resource_action_denies():
    first_arn = f"arn:aws:sqs:{REGION}:{ACCOUNT}:first-queue"
    second_arn = f"arn:aws:sqs:{REGION}:{ACCOUNT}:second-queue"
    result = policy(
        change("aws_sqs_queue", ["create"], after={"name": "first-queue"}),
        change("aws_sqs_queue", ["create"], after={"name": "second-queue"}),
    )

    exact_denies = [
        statement
        for statement in result.document["Statement"]
        if statement.get("Effect") == "Deny"
        and statement.get("NotAction") != "sts:GetCallerIdentity"
        and isinstance(statement.get("Resource"), list)
    ]
    grouped = next(
        statement
        for statement in exact_denies
        if set(statement["Resource"]) == {first_arn, second_arn}
    )
    assert "sqs:DeleteQueue" not in grouped["NotAction"]
    assert "sqs:CreateQueue" in grouped["NotAction"]
    assert "sts:GetCallerIdentity" in grouped["NotAction"]


def test_apply_scope_uses_a_separate_action_deny_for_each_different_scope():
    result = policy(
        change("aws_sqs_queue", ["create"], after={"name": "created-queue"}),
        change("aws_sqs_queue", ["delete"], before={"name": "deleted-queue"}),
    )
    denies = [
        statement
        for statement in result.document["Statement"]
        if statement.get("Effect") == "Deny"
        and "NotAction" in statement
        and statement.get("Resource") != "*"
        and "NotResource" not in statement
    ]
    by_resource = {statement["Resource"]: set(statement["NotAction"]) for statement in denies}
    create_arn = f"arn:aws:sqs:{REGION}:{ACCOUNT}:created-queue"
    delete_arn = f"arn:aws:sqs:{REGION}:{ACCOUNT}:deleted-queue"
    assert set(by_resource) == {create_arn, delete_arn}
    assert "sqs:CreateQueue" in by_resource[create_arn]
    assert "sqs:DeleteQueue" not in by_resource[create_arn]
    assert "sqs:DeleteQueue" in by_resource[delete_arn]
    assert "sqs:CreateQueue" not in by_resource[delete_arn]
def test_apply_scope_fails_closed_when_mixed_plan_exceeds_sts_limit():
    with pytest.raises(NovaApplyAccessPolicyError, match="STS limit"):
        policy(
            change(
                "aws_s3_bucket",
                ["create"],
                after={"bucket": "davdeploy-apply-scope-test-bucket"},
            ),
            change(
                "aws_sqs_queue",
                ["create"],
                after={"name": "davdeploy-apply-scope-test-queue"},
            ),
            change(
                "aws_dynamodb_table",
                ["create"],
                after={"name": "davdeploy-apply-scope-test-table"},
            ),
        )


def test_apply_scope_fits_a_mixed_sqs_dynamodb_plan_under_sts_limit():
    result = policy(
        change(
            "aws_sqs_queue",
            ["create"],
            after={"name": "davdeploy-apply-scope-test-queue"},
        ),
        change(
            "aws_dynamodb_table",
            ["create"],
            after={"name": "davdeploy-apply-scope-test-table"},
        ),
    )
    encoded = json.dumps(result.document, sort_keys=True, separators=(",", ":")).encode()
    assert len(encoded) <= MAX_SESSION_POLICY_BYTES


def test_apply_scope_uses_before_and_after_arns_for_replacement():
    result = policy(
        change(
            "aws_dynamodb_table",
            ["delete", "create"],
            before={"name": "old-table"},
            after={"name": "new-table"},
        )
    )

    scoped = {
        statement["Resource"]: set(statement["Action"])
        for statement in result.document["Statement"]
        if statement["Effect"] == "Allow" and statement.get("Resource") != "*"
    }
    old_arn = f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/old-table"
    new_arn = f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/new-table"
    assert set(scoped) == {old_arn, new_arn}
    assert "dynamodb:DeleteTable" in scoped[old_arn]
    assert "dynamodb:CreateTable" not in scoped[old_arn]
    assert "dynamodb:CreateTable" in scoped[new_arn]
    assert "dynamodb:DeleteTable" not in scoped[new_arn]


def test_apply_scope_combines_actions_only_for_the_same_bucket():
    result = policy(
        change("aws_s3_bucket", ["update"], before={"bucket": "same"}, after={"bucket": "same"}),
        change(
            "aws_s3_bucket_versioning",
            ["update"],
            before={"bucket": "same"},
            after={"bucket": "same"},
        ),
    )

    allow = next(
        statement
        for statement in result.document["Statement"]
        if statement["Effect"] == "Allow" and statement.get("Resource") != "*"
    )
    assert allow["Resource"] == "arn:aws:s3:::same"
    assert "s3:PutBucketTagging" in allow["Action"]
    assert "s3:PutBucketVersioning" in allow["Action"]
    assert "s3:DeleteBucketPolicy" not in allow["Action"]


@pytest.mark.parametrize(
    ("resource_type", "expected_action"),
    [
        ("aws_s3_bucket_cors_configuration", "s3:PutBucketCORS"),
        ("aws_s3_bucket_lifecycle_configuration", "s3:PutLifecycleConfiguration"),
        ("aws_s3_bucket_ownership_controls", "s3:PutBucketOwnershipControls"),
        ("aws_s3_bucket_public_access_block", "s3:PutBucketPublicAccessBlock"),
        (
            "aws_s3_bucket_server_side_encryption_configuration",
            "s3:PutEncryptionConfiguration",
        ),
    ],
)
def test_s3_subresource_deletes_use_the_iam_put_permission(resource_type, expected_action):
    result = policy(
        change(
            resource_type,
            ["delete"],
            before={"bucket": "pilot-data"},
        )
    )

    allow = next(
        statement
        for statement in result.document["Statement"]
        if statement["Effect"] == "Allow" and statement.get("Resource") != "*"
    )
    assert expected_action in allow["Action"]
    assert not any(action.startswith("s3:DeleteBucket") for action in allow["Action"])


@pytest.mark.parametrize(
    "resource_change",
    [
        change("aws_lambda_function", ["create"], after={"function_name": "example"}),
        change("aws_s3_bucket", ["create"], after={"bucket": "*"}),
        change("aws_sqs_queue", ["create"], after={"name": "bad name"}),
        change("aws_s3_bucket", ["import"], after={"bucket": "example"}),
        change("aws_s3_bucket", ["read", "update"], after={"bucket": "example"}),
    ],
)
def test_apply_scope_rejects_unmapped_or_unscopable_changes(resource_change):
    with pytest.raises(NovaApplyAccessPolicyError):
        policy(resource_change)


def test_apply_scope_rejects_noop_only_plan():
    with pytest.raises(NovaApplyAccessPolicyError, match="no supported resource changes"):
        policy(change("aws_s3_bucket", ["no-op"], before={"bucket": "example"}))


def test_apply_scope_rejects_policy_over_the_sts_inline_size_limit():
    changes = [
        change("aws_s3_bucket", ["create"], after={"bucket": f"bucket-{index:03d}-long-name"})
        for index in range(50)
    ]
    with pytest.raises(NovaApplyAccessPolicyError, match="STS limit"):
        policy(*changes)


def test_apply_scope_rejects_unmapped_embedded_bucket_configuration():
    with pytest.raises(NovaApplyAccessPolicyError, match="embedded S3 bucket settings"):
        policy(
            change(
                "aws_s3_bucket",
                ["create"],
                after={"bucket": "pilot-data", "website": [{"index_document": "index.html"}]},
            )
        )


def test_apply_scope_rejects_forced_bucket_deletion():
    with pytest.raises(NovaApplyAccessPolicyError, match="forced S3 bucket deletion"):
        policy(
            change(
                "aws_s3_bucket",
                ["delete"],
                before={"bucket": "pilot-data", "force_destroy": True},
            )
        )
