import json
from fnmatch import fnmatchcase

import pytest
from davdeploy.generated_deployment_contract import (
    GeneratedDeploymentProposal,
    GeneratedOutput,
    GeneratedResource,
    WorkloadRequirements,
)
from davdeploy.nova_plan_access import (
    PLAN_ROLE_ACCESS_POLICY_VERSION,
    PLAN_ROLE_READ_ACTIONS,
    PLAN_SCOPED_READ_ACTIONS,
    NovaPlanAccessError,
    build_nova_plan_access_policy,
)

ACCOUNT_ID = "123456789012"
REGION = "us-east-1"


def proposal(*resources):
    return GeneratedDeploymentProposal(
        contract_version="1.0",
        source_revision="revision-1",
        context_digest="a" * 64,
        resources=tuple(resources),
        requirements=WorkloadRequirements(region=REGION),
    )


def resource(resource_id, resource_type, arguments, outputs=()):
    return GeneratedResource(
        resource_id=resource_id,
        resource_type=resource_type,
        name=resource_id.replace("-", "_"),
        arguments=arguments,
        outputs=outputs,
        rationale="Permission profile regression fixture.",
    )


def test_session_policy_is_read_only_proposal_scoped_and_bounded():
    bucket = resource("storage", "aws_s3_bucket", {"bucket": "private-data-123"})
    table = resource("database", "aws_dynamodb_table", {"name": "app-records"})
    queue = resource("jobs", "aws_sqs_queue", {"name": "app-jobs"})
    function = resource("api", "aws_lambda_function", {"function_name": "app-api"})
    api = resource("gateway", "aws_apigatewayv2_api", {"name": "app-gateway"})

    first = build_nova_plan_access_policy(
        proposal(bucket, table, queue, function, api),
        account_id=ACCOUNT_ID,
        region=REGION,
    )
    second = build_nova_plan_access_policy(
        proposal(bucket, table, queue, function, api),
        account_id=ACCOUNT_ID,
        region=REGION,
    )
    assert first == second
    assert first.version == PLAN_ROLE_ACCESS_POLICY_VERSION
    assert len(json.dumps(first.document, separators=(",", ":"))) <= 2048

    statements = first.document["Statement"]
    deny = next(item for item in statements if item["Effect"] == "Deny")
    assert "sts:GetCallerIdentity" in deny["NotAction"]
    for denied in (
        "s3:DeleteBucket",
        "lambda:InvokeFunction",
        "iam:PassRole",
        "dynamodb:DeleteTable",
    ):
        assert not any(fnmatchcase(denied, pattern) for pattern in deny["NotAction"])
    scope_deny = next(item for item in statements if "NotResource" in item)
    assert scope_deny["Effect"] == "Deny"
    assert scope_deny["NotAction"] == ["sts:GetCallerIdentity"]
    assert "arn:aws:s3:::private-data-123" in scope_deny["NotResource"]
    assert "arn:aws:s3:::unrelated-bucket" not in scope_deny["NotResource"]
    account_deny = next(
        item
        for item in statements
        if item["Effect"] == "Deny" and "Condition" in item
    )
    assert account_deny["Condition"] == {
        "StringNotEquals": {"aws:ResourceAccount": ACCOUNT_ID}
    }
    assert account_deny["Action"] == "s3:*"
    assert account_deny["Resource"] == "*"

    allows = [item for item in statements if item["Effect"] == "Allow"]
    assert all("Resource" in item and item["Resource"] != "*" for item in allows)
    allow = allows[0]
    assert "s3:GetBucket*" in allow["Action"]
    assert "dynamodb:Describe*" in allow["Action"]
    assert "lambda:Get*" in allow["Action"]
    assert "arn:aws:s3:::private-data-123" in allow["Resource"]
    assert "arn:aws:dynamodb:us-east-1:123456789012:table/app-records" in allow["Resource"]
    assert "arn:aws:sqs:us-east-1:123456789012:app-jobs" in allow["Resource"]
    assert "arn:aws:lambda:us-east-1:123456789012:function:app-api" in allow["Resource"]


def test_fixed_role_action_patterns_cover_provider_reads_without_data_actions():
    for actions in PLAN_SCOPED_READ_ACTIONS.values():
        for action in actions:
            assert any(fnmatchcase(action, pattern) for pattern in PLAN_ROLE_READ_ACTIONS)
    for forbidden in (
        "s3:GetObject",
        "dynamodb:GetItem",
        "sqs:ReceiveMessage",
        "lambda:InvokeFunction",
        "iam:PassRole",
        "iam:PutRolePolicy",
    ):
        assert not any(fnmatchcase(forbidden, pattern) for pattern in PLAN_ROLE_READ_ACTIONS)


def test_profile_denies_content_reads_and_unrelated_resource_families():
    item = resource("queue", "aws_sqs_queue", {"name": "app-jobs"})
    policy = build_nova_plan_access_policy(proposal(item), account_id=ACCOUNT_ID, region=REGION)
    statement = next(
        item
        for item in policy.document["Statement"]
        if item["Effect"] == "Deny" and item.get("Resource") == "*"
    )
    scope_deny = next(
        item for item in policy.document["Statement"] if "NotResource" in item
    )
    for denied in (
        "s3:GetObject",
        "dynamodb:GetItem",
        "sqs:ReceiveMessage",
        "secretsmanager:GetSecretValue",
        "lambda:InvokeFunction",
        "iam:PassRole",
        "ec2:RunInstances",
    ):
        assert not any(fnmatchcase(denied, pattern) for pattern in statement["NotAction"])

    # A supported action from a service absent from this proposal is denied by
    # the resource scope, including grants directly to the assumed role session.
    assert "arn:aws:lambda:us-east-1:123456789012:function:app-api" not in scope_deny[
        "NotResource"
    ]


def test_resource_references_are_scoped_to_typed_target_identity():
    bucket = resource(
        "storage",
        "aws_s3_bucket",
        {"bucket": "private-data-123"},
        outputs=(GeneratedOutput(name="bucket", value_type="resource_name"),),
    )
    policy = resource(
        "policy",
        "aws_s3_bucket_policy",
        {
            "bucket": {
                "kind": "resource_reference",
                "resource_id": "storage",
                "output_name": "bucket",
                "value_type": "resource_name",
            },
            "policy": "{}",
        },
    )
    built = build_nova_plan_access_policy(
        proposal(bucket, policy), account_id=ACCOUNT_ID, region=REGION
    )
    s3 = next(
        statement
        for statement in built.document["Statement"]
        if statement["Effect"] == "Allow" and "s3:ListBucket" in statement["Action"]
    )
    assert "arn:aws:s3:::private-data-123" in s3["Resource"]


def test_reference_to_wrong_resource_type_fails_closed():
    queue = resource(
        "jobs",
        "aws_sqs_queue",
        {"name": "app-jobs"},
        outputs=(GeneratedOutput(name="name", value_type="resource_name"),),
    )
    policy = resource(
        "bucket-policy",
        "aws_s3_bucket_policy",
        {
            "bucket": {
                "kind": "resource_reference",
                "resource_id": "jobs",
                "output_name": "name",
                "value_type": "resource_name",
            },
            "policy": "{}",
        },
    )
    with pytest.raises(NovaPlanAccessError, match="resource name"):
        build_nova_plan_access_policy(proposal(queue, policy), account_id=ACCOUNT_ID, region=REGION)


def test_composed_api_storage_database_async_profile_fits_sts_policy_limit():
    bucket = resource(
        "storage",
        "aws_s3_bucket",
        {"bucket": "app-private-storage"},
        outputs=(GeneratedOutput(name="bucket", value_type="resource_name"),),
    )
    bucket_policy = resource(
        "storage-policy",
        "aws_s3_bucket_policy",
        {
            "bucket": {
                "kind": "resource_reference",
                "resource_id": "storage",
                "output_name": "bucket",
                "value_type": "resource_name",
            },
            "policy": "{}",
        },
    )
    table = resource("database", "aws_dynamodb_table", {"name": "app-records"})
    queue = resource(
        "jobs",
        "aws_sqs_queue",
        {"name": "app-jobs"},
        outputs=(GeneratedOutput(name="arn", value_type="aws_arn"),),
    )
    role = resource(
        "worker-role",
        "aws_iam_role",
        {"name": "app-worker"},
        outputs=(GeneratedOutput(name="name", value_type="resource_name"),),
    )
    role_policy = resource(
        "worker-policy",
        "aws_iam_role_policy",
        {
            "role": {
                "kind": "resource_reference",
                "resource_id": "worker-role",
                "output_name": "name",
                "value_type": "resource_name",
            },
            "policy": "{}",
        },
    )
    function = resource(
        "worker",
        "aws_lambda_function",
        {"function_name": "app-worker"},
        outputs=(GeneratedOutput(name="arn", value_type="aws_arn"),),
    )
    mapping = resource(
        "queue-consumer",
        "aws_lambda_event_source_mapping",
        {
            "function_name": {
                "kind": "resource_reference",
                "resource_id": "worker",
                "output_name": "arn",
                "value_type": "aws_arn",
            }
        },
    )
    api = resource("api", "aws_apigatewayv2_api", {"name": "app-api"})

    policy = build_nova_plan_access_policy(
        proposal(bucket, bucket_policy, table, queue, role, role_policy, function, mapping, api),
        account_id=ACCOUNT_ID,
        region=REGION,
    )

    encoded = json.dumps(policy.document, sort_keys=True, separators=(",", ":"))
    assert len(encoded) <= 2048
    allow = next(item for item in policy.document["Statement"] if item["Effect"] == "Allow")
    assert "arn:aws:s3:::app-private-storage" in allow["Resource"]
    assert "arn:aws:dynamodb:us-east-1:123456789012:table/app-records" in allow["Resource"]
    assert "arn:aws:sqs:us-east-1:123456789012:app-jobs" in allow["Resource"]
    assert "arn:aws:lambda:us-east-1:123456789012:event-source-mapping:*" in allow["Resource"]
    assert "arn:aws:apigateway:us-east-1::/apis/*" in allow["Resource"]


def test_unsupported_resource_type_fails_before_policy_creation():
    # Bypass the contract to isolate the plan-access allowlist. The contract
    # rejects this forged secret-reference output before a runner can use it.
    source = GeneratedResource.model_construct(
        resource_id="secret",
        resource_type="aws_secretsmanager_secret",
        name="secret",
        arguments={},
        depends_on=(),
        outputs=(GeneratedOutput(name="arn", value_type="secret_reference"),),
        rationale="Unsupported provider resource regression fixture.",
    )
    unsupported = resource(
        "secret-version",
        "aws_secretsmanager_secret_version",
        {
            "secret_id": {
                "kind": "resource_reference",
                "resource_id": "secret",
                "output_name": "arn",
                "value_type": "secret_reference",
            }
        },
    )
    with pytest.raises(NovaPlanAccessError, match="unsupported plan resource types"):
        build_nova_plan_access_policy(
            GeneratedDeploymentProposal.model_construct(
                contract_version="1.0",
                source_revision="revision-1",
                context_digest="a" * 64,
                resources=(source, unsupported),
                requirements=WorkloadRequirements(region=REGION),
            ),
            account_id=ACCOUNT_ID,
            region=REGION,
        )


def test_name_prefix_without_exact_resource_name_fails_closed():
    resource_with_prefix = resource("queue", "aws_sqs_queue", {"name_prefix": "app-jobs-"})
    with pytest.raises(NovaPlanAccessError, match="resource name"):
        build_nova_plan_access_policy(
            proposal(resource_with_prefix), account_id=ACCOUNT_ID, region=REGION
        )


def test_policy_rejects_wrong_trusted_region():
    item = resource("storage", "aws_s3_bucket", {"bucket": "private-data-123"})
    with pytest.raises(NovaPlanAccessError, match="trusted region"):
        build_nova_plan_access_policy(proposal(item), account_id=ACCOUNT_ID, region="us-west-2")
