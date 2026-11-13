from __future__ import annotations

import json

import pytest
from davdeploy.generated_deployment_contract import GeneratedDeploymentProposal
from davdeploy.generated_plan_ownership import PlanOwnershipScope, UntaggedResourceOwnershipRecord
from davdeploy.generated_plan_policy import (
    PlanPolicyVerdict,
    _check_rds_final_snapshot_changes,
    _path_contains_unknown,
    evaluate_generated_plan_policy,
)

ACCOUNT = "654654474502"
REGION = "us-east-1"
_OMIT = object()


def ownership_scope():
    return PlanOwnershipScope(
        organization_id="org-test",
        workspace_id="workspace-test",
        project_id="project-test",
        environment_id="production",
        plan_id="plan-internal-id",
        revision_id="revision-internal-id",
    )


def proposal(resources=None, *, backup_required=False):
    resources = resources or [
        {
            "resource_id": "bucket",
            "resource_type": "aws_s3_bucket",
            "name": "bucket",
            "arguments": {"bucket": "private-plan-bucket"},
            "rationale": "Private application file storage.",
        },
        {
            "resource_id": "public-access",
            "resource_type": "aws_s3_bucket_public_access_block",
            "name": "public_access",
            "arguments": {
                "bucket": {
                    "kind": "resource_reference",
                    "resource_id": "bucket",
                    "output_name": "id",
                    "value_type": "string",
                },
                "block_public_acls": True,
                "block_public_policy": True,
                "ignore_public_acls": True,
                "restrict_public_buckets": True,
            },
            "rationale": "Keep customer files private.",
        },
    ]
    if resources[0]["resource_type"] == "aws_s3_bucket":
        resources[0]["outputs"] = [{"name": "id", "value_type": "string"}]
    return GeneratedDeploymentProposal.model_validate(
        {
            "contract_version": "1.1",
            "source_revision": "test-revision",
            "context_digest": "a" * 64,
            "requirements": {"region": REGION},
            "recovery": {"backup_required": backup_required},
            "resources": resources,
        }
    )


def resource(address, kind, values):
    if kind.startswith("aws_"):
        values = {**values, "tags": {**ownership_scope().tags(), **values.get("tags", {})}}
    return {"address": address, "mode": "managed", "type": kind, "values": values}


def change(address, kind, actions=("create",), **metadata):
    before = {"tags": ownership_scope().tags()} if any(
        action in actions for action in ("delete", "update", "no-op")
    ) else None
    after = {"tags": ownership_scope().tags()} if any(
        action in actions for action in ("create", "update", "no-op")
    ) else None
    return {
        "address": address,
        "type": kind,
        "change": {
            "actions": list(actions),
            "before": before,
            "after": after,
            "before_sensitive": False,
            "after_sensitive": False,
            "after_unknown": {},
            **metadata,
        },
    }


def plan(resources=None, changes=None, **overrides):
    resources = resources or [
        resource("aws_s3_bucket.bucket", "aws_s3_bucket", {"bucket": "private-plan-bucket"}),
        resource(
            "aws_s3_bucket_public_access_block.public_access",
            "aws_s3_bucket_public_access_block",
            {
                "bucket": "private-plan-bucket",
                "block_public_acls": True,
                "block_public_policy": True,
                "ignore_public_acls": True,
                "restrict_public_buckets": True,
            },
        ),
        resource("terraform_data.account_guard", "terraform_data", {"input": None}),
    ]
    changes = changes or [
        change("aws_s3_bucket.bucket", "aws_s3_bucket"),
        change("aws_s3_bucket_public_access_block.public_access", "aws_s3_bucket_public_access_block"),
        change("terraform_data.account_guard", "terraform_data"),
    ]
    document = {
        "format_version": "1.2",
        "applyable": True,
        "errored": False,
        "complete": True,
        "configuration": {
            "provider_config": {"aws": {"expressions": {"region": {"constant_value": REGION}}}}
        },
        "planned_values": {"root_module": {"resources": resources}},
        "resource_changes": changes,
    }
    document.update(overrides)
    return document


def evaluate(document=None, proposal_value=None):
    return evaluate_generated_plan_policy(
        document or plan(),
        proposal_value or proposal(),
        expected_account_id=ACCOUNT,
        expected_region=REGION,
        ownership_scope=ownership_scope(),
        trusted_configuration={
            "data": {"aws_caller_identity": {"trusted": {}}},
            "resource": {
                "terraform_data": {
                    "account_guard": {
                        "lifecycle": {
                            "precondition": {
                                "condition": '${data.aws_caller_identity.trusted.account_id == "'
                                + ACCOUNT
                                + '"}'
                            }
                        }
                    }
                }
            },
        },
    )


def add_policy_resource(document, kind, name, arguments, *, after_unknown=None):
    address = f"{kind}.{name}"
    document["planned_values"]["root_module"]["resources"].append(
        resource(address, kind, arguments)
    )
    unknown = after_unknown if after_unknown is not None else {}
    document["resource_changes"].append(
        change(address, kind, after_unknown=unknown)
    )
    resources = [item.model_dump(mode="json") for item in proposal().resources]
    resources.append(
        {
            "resource_id": name.replace("_", "-"),
            "resource_type": kind,
            "name": name,
            "arguments": arguments,
            "rationale": "Apply the requested compute configuration with bounded metadata access.",
        }
    )
    return proposal(resources)


def dynamodb_case(point_in_time_recovery=_OMIT, *, backup_required=False, after_unknown=None):
    table_values = {
        "name": "app-records",
        "server_side_encryption": {"enabled": True},
        "deletion_protection_enabled": True,
    }
    if point_in_time_recovery is not _OMIT:
        table_values["point_in_time_recovery"] = point_in_time_recovery
    table_address = "aws_dynamodb_table.records"
    document = plan()
    document["planned_values"]["root_module"]["resources"] = [
        item
        for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "terraform_data"
    ]
    document["resource_changes"] = [
        item for item in document["resource_changes"] if item["type"] == "terraform_data"
    ]
    document["planned_values"]["root_module"]["resources"].append(
        resource(table_address, "aws_dynamodb_table", table_values)
    )
    metadata = {"after_unknown": after_unknown or {}}
    document["resource_changes"].append(
        change(table_address, "aws_dynamodb_table", **metadata)
    )
    proposal_value = proposal(
        [
            {
                "resource_id": "records",
                "resource_type": "aws_dynamodb_table",
                "name": "records",
                "arguments": {"name": "app-records"},
                "rationale": "Store application records.",
            }
        ],
        backup_required=backup_required,
    )
    return document, proposal_value


def add_sqs_queue_policy(document, policy, **change_metadata):
    address = "aws_sqs_queue_policy.queue_access"
    document["planned_values"]["root_module"]["resources"].append(
        resource(address, "aws_sqs_queue_policy", {"policy": policy})
    )
    document["resource_changes"].append(
        change(address, "aws_sqs_queue_policy", **change_metadata)
    )
    return document


def add_lambda_permission(document, values, **change_metadata):
    address = "aws_lambda_permission.function_access"
    document["planned_values"]["root_module"]["resources"].append(
        resource(address, "aws_lambda_permission", values)
    )
    document["resource_changes"].append(
        change(address, "aws_lambda_permission", **change_metadata)
    )
    return document


def add_api_gateway_route(document, authorization_type=_OMIT, *, after_unknown=None):
    address = "aws_apigatewayv2_route.application"
    api_address = "aws_apigatewayv2_api.application"
    document["planned_values"]["root_module"]["resources"].append(
        resource(api_address, "aws_apigatewayv2_api", {"name": "application-api", "protocol_type": "HTTP", "id": "api-123"})
    )
    document["resource_changes"].append(change(api_address, "aws_apigatewayv2_api"))
    values = {"api_id": "api-123", "route_key": "GET /items"}
    if authorization_type is not _OMIT:
        values["authorization_type"] = authorization_type
    document["planned_values"]["root_module"]["resources"].append(
        {"address": address, "mode": "managed", "type": "aws_apigatewayv2_route", "values": values}
    )
    planned_after = values.copy()
    document["resource_changes"].append(
        change(
            address,
            "aws_apigatewayv2_route",
            after=planned_after,
            after_unknown=after_unknown or {},
        )
    )
    document["configuration"]["root_module"] = {
        "resources": [
            {
                "address": address,
                "expressions": {
                    "api_id": {"references": [f"{api_address}.id"]},
                },
            }
        ]
    }
    proposal_resources = [item.model_dump(mode="json") for item in proposal().resources]
    proposal_resources.append(
        {
            "resource_id": "application-api",
            "resource_type": "aws_apigatewayv2_api",
            "name": "application",
            "arguments": {"name": "application-api", "protocol_type": "HTTP"},
            "outputs": [{"name": "id", "value_type": "string"}],
            "rationale": "Provide the API that owns the application route.",
        }
    )
    proposal_resources.append(
        {
            "resource_id": "application-route",
            "resource_type": "aws_apigatewayv2_route",
            "name": "application",
            "arguments": {
                **values,
                "api_id": {
                    "kind": "resource_reference",
                    "resource_id": "application-api",
                    "output_name": "id",
                    "value_type": "string",
                },
            },
            "rationale": "Route API requests to the application.",
        }
    )
    return document, proposal(proposal_resources)


def codes(result):
    return {finding.code for finding in result.findings}


def ebs_volume_policy_case(encryption_state):
    address = "aws_ebs_volume.data"
    tags = ownership_scope().tags()
    values = {"tags": tags}
    planned_after = {"tags": tags}
    after_unknown = {}
    if encryption_state == "false":
        values["encrypted"] = False
        planned_after["encrypted"] = False
    elif encryption_state == "true":
        values["encrypted"] = True
        planned_after["encrypted"] = True
    elif encryption_state == "unknown":
        values["encrypted"] = None
        planned_after["encrypted"] = None
        after_unknown = {"encrypted": True}

    resources = [
        resource(address, "aws_ebs_volume", values),
        resource("terraform_data.account_guard", "terraform_data", {"input": None}),
    ]
    changes = [
        change(
            address,
            "aws_ebs_volume",
            after=planned_after,
            after_unknown=after_unknown,
        ),
        change("terraform_data.account_guard", "terraform_data"),
    ]
    proposal_value = proposal(
        [
            {
                "resource_id": "data-volume",
                "resource_type": "aws_ebs_volume",
                "name": "data",
                "arguments": {"type": "gp3", "size": 8, "encrypted": encryption_state == "true"},
                "rationale": "Store application data on an encrypted EBS volume.",
            }
        ]
    )
    return evaluate(plan(resources, changes), proposal_value)


@pytest.mark.parametrize(
    "encryption_state,expected_finding",
    [
        ("false", "ebs_encryption_required"),
        ("missing", "ebs_encryption_required"),
        ("unknown", "policy_critical_value_unknown"),
        ("true", None),
    ],
)
def test_ebs_volume_requires_known_encryption_enabled(encryption_state, expected_finding):
    result = ebs_volume_policy_case(encryption_state)

    if expected_finding is None:
        assert "ebs_encryption_required" not in codes(result)
        assert result.verdict != PlanPolicyVerdict.DENY
    else:
        assert result.verdict == PlanPolicyVerdict.DENY
        assert expected_finding in codes(result)
        if expected_finding == "ebs_encryption_required":
            finding = next(item for item in result.findings if item.code == expected_finding)
            assert finding.message == "EBS volumes must have encryption enabled."


def test_resource_ownership_tags_are_required_for_every_aws_resource():
    document = plan()
    document["planned_values"]["root_module"]["resources"][0]["values"]["tags"].pop(
        "DavDeployWorkspace"
    )

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "resource_ownership_tags_missing" in codes(result)


def test_resource_ownership_mismatch_is_denied():
    document = plan()
    document["planned_values"]["root_module"]["resources"][0]["values"]["tags"][
        "DavDeployProject"
    ] = "another-project"

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "resource_ownership_tags_mismatch" in codes(result)


def test_unknown_resource_ownership_tag_is_denied():
    document = plan()
    document["resource_changes"][0]["change"]["after_unknown"] = {
        "tags": {"DavDeployWorkspace": True}
    }

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "resource_ownership_unknown" in codes(result)


def test_missing_trusted_ownership_scope_is_denied():
    result = evaluate_generated_plan_policy(
        plan(),
        proposal(),
        expected_account_id=ACCOUNT,
        expected_region=REGION,
        ownership_scope=None,
    )

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "plan_policy_input_invalid" in codes(result)


def test_secure_composed_s3_plan_is_eligible_only_for_human_review():
    result = evaluate()
    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert result.human_approval_required is True
    assert result.findings == ()


@pytest.mark.parametrize(
    ("kind", "options"),
    [
        (
            "aws_instance",
            {"http_endpoint": "enabled", "http_tokens": "required"},
        ),
        (
            "aws_launch_template",
            [{"http_endpoint": "enabled", "http_tokens": "required"}],
        ),
        (
            "aws_launch_configuration",
            [{"http_endpoint": "enabled", "http_tokens": "required"}],
        ),
    ],
)
def test_ec2_metadata_access_requires_imdsv2_tokens(kind, options):
    document = plan()
    proposal_value = add_policy_resource(
        document, kind, "secure_compute", {"metadata_options": options}
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert not any(code.startswith("instance_metadata_") for code in codes(result))


@pytest.mark.parametrize("kind", ["aws_instance", "aws_launch_template"])
def test_ec2_metadata_endpoint_may_be_explicitly_disabled(kind):
    document = plan()
    proposal_value = add_policy_resource(
        document,
        kind,
        "metadata_disabled",
        {
            "metadata_options": {
                "http_endpoint": "disabled",
                "http_tokens": "optional",
            }
        },
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert not any(code.startswith("instance_metadata_") for code in codes(result))


@pytest.mark.parametrize("kind", ["aws_instance", "aws_launch_template"])
def test_ec2_metadata_endpoint_with_optional_tokens_is_denied(kind):
    document = plan()
    proposal_value = add_policy_resource(
        document,
        kind,
        "imdsv1_compatible",
        {
            "metadata_options": {
                "http_endpoint": "enabled",
                "http_tokens": "optional",
            }
        },
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "instance_metadata_v2_required" in codes(result)


def test_regional_ec2_metadata_defaults_must_require_imdsv2():
    document = plan()
    proposal_value = add_policy_resource(
        document,
        "aws_ec2_instance_metadata_defaults",
        "regional_defaults",
        {"region": REGION, "http_tokens": "required"},
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert "instance_metadata_defaults_require_v2" not in codes(result)


@pytest.mark.parametrize("tokens", ["optional", "no_preference"])
def test_regional_ec2_metadata_defaults_that_do_not_require_imdsv2_are_denied(tokens):
    document = plan()
    proposal_value = add_policy_resource(
        document,
        "aws_ec2_instance_metadata_defaults",
        "regional_defaults",
        {"region": REGION, "http_tokens": tokens},
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "instance_metadata_defaults_require_v2" in codes(result)


@pytest.mark.parametrize(
    "options",
    [None, [], [{"http_endpoint": "enabled"}, {"http_endpoint": "disabled"}]],
)
def test_malformed_or_missing_ec2_metadata_options_are_denied(options):
    document = plan()
    proposal_value = add_policy_resource(
        document,
        "aws_instance",
        "unknown_metadata",
        {"metadata_options": options},
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "instance_metadata_options_unknown" in codes(result)


@pytest.mark.parametrize(
    "kind",
    [
        "aws_instance",
        "aws_launch_template",
        "aws_launch_configuration",
        "aws_ec2_instance_metadata_defaults",
    ],
)
def test_unknown_ec2_metadata_token_requirement_is_denied(kind):
    document = plan()
    options = (
        {"http_tokens": "required"}
        if kind == "aws_ec2_instance_metadata_defaults"
        else {
            "metadata_options": [
                {"http_endpoint": "enabled", "http_tokens": "required"}
            ]
        }
    )
    unknown = (
        {"http_tokens": True}
        if kind == "aws_ec2_instance_metadata_defaults"
        else {"metadata_options": [{"http_tokens": True}]}
    )
    proposal_value = add_policy_resource(
        document,
        kind,
        "unknown_tokens",
        options,
        after_unknown=unknown,
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


@pytest.mark.parametrize(
    "flag",
    ["block_public_acls", "block_public_policy", "ignore_public_acls", "restrict_public_buckets"],
)
def test_s3_public_access_must_be_blocked_in_all_four_settings(flag):
    document = plan()
    document["planned_values"]["root_module"]["resources"][1]["values"][flag] = False
    assert "s3_public_access_block_incomplete" in codes(evaluate(document))


def test_missing_s3_public_access_block_is_denied():
    document = plan()
    document["planned_values"]["root_module"]["resources"].pop(1)
    document["resource_changes"].pop(1)
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_public_access_block_missing" in codes(result)
    assert "plan_resource_inventory_mismatch" in codes(result)


@pytest.mark.parametrize("acl", ["public-read", "public-read-write", "authenticated-read"])
def test_public_s3_acl_is_denied(acl):
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(
        resource("aws_s3_bucket_acl.bucket_acl", "aws_s3_bucket_acl", {"acl": acl})
    )
    return_resource = change("aws_s3_bucket_acl.bucket_acl", "aws_s3_bucket_acl")
    document["resource_changes"].append(return_resource)
    result = evaluate(document)
    assert "s3_public_acl" in codes(result)


def test_public_s3_policy_is_denied():
    document = plan()
    policy = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": "*", "Action": "s3:GetObject", "Resource": "*"}]}
    document["planned_values"]["root_module"]["resources"].append(
        resource("aws_s3_bucket_policy.policy", "aws_s3_bucket_policy", {"policy": json.dumps(policy)})
    )
    document["resource_changes"].append(change("aws_s3_bucket_policy.policy", "aws_s3_bucket_policy"))
    proposal_value = proposal(
        [
            *(item.model_dump(mode="json") for item in proposal().resources),
            {
                "resource_id": "bucket-policy",
                "resource_type": "aws_s3_bucket_policy",
                "name": "policy",
                "arguments": {"bucket": "private-plan-bucket", "policy": json.dumps(policy)},
                "rationale": "Public delivery requires review.",
            },
        ]
    )
    result = evaluate(document, proposal_value)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "s3_public_policy_denied" in codes(result)


@pytest.mark.parametrize("principal", ["*", {"AWS": "*"}, {"AWS": ["*"]}])
def test_public_sqs_queue_policy_is_denied(principal):
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": principal,
                "Action": "sqs:ReceiveMessage",
                "Resource": "arn:aws:sqs:us-east-1:654654474502:async-work",
            }
        ],
    }
    document = add_sqs_queue_policy(plan(), json.dumps(policy))

    assert "sqs_public_policy_denied" in codes(evaluate(document))


def test_sqs_queue_policy_allow_with_not_principal_is_denied():
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "NotPrincipal": {"AWS": "arn:aws:iam::654654474502:root"},
                "Action": "sqs:ReceiveMessage",
                "Resource": "arn:aws:sqs:us-east-1:654654474502:async-work",
            }
        ],
    }
    document = add_sqs_queue_policy(plan(), json.dumps(policy))

    assert "sqs_public_policy_denied" in codes(evaluate(document))


def test_specific_sqs_queue_policy_principal_does_not_trigger_public_policy_denial():
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "sns.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "Resource": "arn:aws:sqs:us-east-1:654654474502:async-work",
            }
        ],
    }
    document = add_sqs_queue_policy(plan(), json.dumps(policy))

    assert "sqs_public_policy_denied" not in codes(evaluate(document))


def test_unknown_sqs_queue_policy_is_denied_even_if_after_value_looks_safe():
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "sns.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "Resource": "arn:aws:sqs:us-east-1:654654474502:async-work",
            }
        ],
    }
    document = add_sqs_queue_policy(plan(), json.dumps(policy), after_unknown={"policy": True})

    assert "policy_critical_value_unknown" in codes(evaluate(document))


def test_malformed_sqs_queue_policy_is_denied_without_echoing_policy_text():
    secret_text = "private-policy-secret"
    document = add_sqs_queue_policy(plan(), f"{{{secret_text}")

    result = evaluate(document)

    assert "policy_document_invalid" in codes(result)
    assert secret_text not in repr(result)


def test_public_sqs_queue_policy_finding_does_not_echo_policy_values():
    secret_action = "sqs:SendMessage-private-policy-secret"
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": "*",
                "Action": secret_action,
                "Resource": "arn:aws:sqs:us-east-1:654654474502:async-work",
            }
        ],
    }
    document = add_sqs_queue_policy(plan(), json.dumps(policy))

    result = evaluate(document)

    assert "sqs_public_policy_denied" in codes(result)
    assert secret_action not in repr(result)


@pytest.mark.parametrize("source_arn", [None, "", "*"])
def test_unscoped_lambda_wildcard_principal_is_denied(source_arn):
    values = {
        "action": "lambda:InvokeFunction",
        "function_name": "application-handler",
        "principal": "*",
    }
    if source_arn is not None:
        values["source_arn"] = source_arn
    document = add_lambda_permission(plan(), values)

    assert "lambda_unscoped_public_invoke_denied" in codes(evaluate(document))


def test_scoped_lambda_wildcard_principal_requires_human_review():
    document = add_lambda_permission(
        plan(),
        {
            "action": "lambda:InvokeFunction",
            "function_name": "application-handler",
            "principal": "*",
            "source_arn": "arn:aws:execute-api:us-east-1:654654474502:api-id/*/*/*",
        },
    )

    result = evaluate(document)

    assert "lambda_public_invoke_review" in codes(result)
    assert result.human_approval_required


def test_specific_lambda_service_principal_is_not_public_invoke():
    document = add_lambda_permission(
        plan(),
        {
            "action": "lambda:InvokeFunction",
            "function_name": "application-handler",
            "principal": "apigateway.amazonaws.com",
            "source_arn": "arn:aws:execute-api:us-east-1:654654474502:api-id/*/*/*",
        },
    )

    assert "lambda_unscoped_public_invoke_denied" not in codes(evaluate(document))
    assert "lambda_public_invoke_review" not in codes(evaluate(document))


def test_open_api_gateway_route_requires_human_review():
    document, proposal_value = add_api_gateway_route(plan(), "NONE")

    result = evaluate(document, proposal_value)

    # This provider resource has no tags argument, so ownership fails closed
    # until exact ownership records for untaggable resources are implemented.
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "api_gateway_open_route_review" in codes(result)
    finding = next(item for item in result.findings if item.code == "api_gateway_open_route_review")
    assert "GET /items" not in repr(finding)


@pytest.mark.parametrize("authorization_type", ["JWT", "AWS_IAM", "CUSTOM"])
def test_authenticated_api_gateway_routes_do_not_trigger_open_route_review(authorization_type):
    document, proposal_value = add_api_gateway_route(plan(), authorization_type)

    result = evaluate(document, proposal_value)

    assert "api_gateway_open_route_review" not in codes(result)
    # Route authorization is recognized, while untaggable ownership remains denied.
    assert result.verdict == PlanPolicyVerdict.DENY


def test_authenticated_route_with_exact_remote_state_record_passes_ownership_check():
    document, proposal_value = add_api_gateway_route(plan(), "AWS_IAM")

    result = evaluate_generated_plan_policy(
        document,
        proposal_value,
        expected_account_id=ACCOUNT,
        expected_region=REGION,
        ownership_scope=ownership_scope(),
        trusted_configuration={
            "data": {"aws_caller_identity": {"trusted": {}}},
            "resource": {
                "terraform_data": {
                    "account_guard": {
                        "lifecycle": {
                            "precondition": {
                                "condition": '${data.aws_caller_identity.trusted.account_id == "'
                                + ACCOUNT
                                + '"}'
                            }
                        }
                    }
                }
            },
        },
        untagged_resource_ownership=(
            UntaggedResourceOwnershipRecord(
                address="aws_apigatewayv2_route.application",
                resource_type="aws_apigatewayv2_route",
            ),
        ),
    )

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert "resource_ownership_tags_missing" not in codes(result)
    assert "api_gateway_open_route_review" not in codes(result)


def test_api_gateway_route_cannot_target_api_outside_deployment():
    document, proposal_value = add_api_gateway_route(plan(), "AWS_IAM")
    document["configuration"]["root_module"]["resources"][0]["expressions"]["api_id"][
        "references"
    ] = ["aws_apigatewayv2_api.external.id"]

    result = evaluate_generated_plan_policy(
        document,
        proposal_value,
        expected_account_id=ACCOUNT,
        expected_region=REGION,
        ownership_scope=ownership_scope(),
        trusted_configuration={
            "data": {"aws_caller_identity": {"trusted": {}}},
            "resource": {
                "terraform_data": {
                    "account_guard": {
                        "lifecycle": {
                            "precondition": {
                                "condition": '${data.aws_caller_identity.trusted.account_id == "'
                                + ACCOUNT
                                + '"}'
                            }
                        }
                    }
                }
            },
        },
        untagged_resource_ownership=(
            UntaggedResourceOwnershipRecord(
                address="aws_apigatewayv2_route.application",
                resource_type="aws_apigatewayv2_route",
            ),
        ),
    )

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "api_gateway_route_target_not_owned" in codes(result)


@pytest.mark.parametrize("authorization_type", [_OMIT, None, "", "INVALID", ["JWT"]])
def test_missing_or_invalid_api_gateway_route_authorization_is_denied(authorization_type):
    document, proposal_value = add_api_gateway_route(plan(), authorization_type)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "api_gateway_route_authorization_unknown" in codes(result)


def test_unknown_api_gateway_route_authorization_is_denied():
    document, proposal_value = add_api_gateway_route(
        plan(), "JWT", after_unknown={"authorization_type": True}
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


@pytest.mark.parametrize(
    "unknown_field",
    ["principal", "source_arn", "source_account", "principal_org_id", "function_url_auth_type"],
)
def test_unknown_lambda_permission_security_fields_are_denied(unknown_field):
    document = add_lambda_permission(
        plan(),
        {
            "action": "lambda:InvokeFunction",
            "function_name": "application-handler",
            "principal": "apigateway.amazonaws.com",
        },
        after_unknown={unknown_field: True},
    )

    assert "policy_critical_value_unknown" in codes(evaluate(document))


@pytest.mark.parametrize(
    "policy",
    [
        {"Statement": "malformed"},
        {"Statement": ["malformed"]},
        {"Statement": {"Effect": "Allow", "Action": 7, "Principal": "*", "Resource": "*"}},
        {"Statement": {"Effect": "Allow", "Action": "s3:GetObject", "Principal": [], "Resource": "*"}},
    ],
)
def test_malformed_public_bucket_policy_fails_closed(policy):
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(
        resource("aws_s3_bucket_policy.policy", "aws_s3_bucket_policy", {"policy": json.dumps(policy)})
    )
    document["resource_changes"].append(change("aws_s3_bucket_policy.policy", "aws_s3_bucket_policy"))
    proposal_value = proposal(
        [
            *(item.model_dump(mode="json") for item in proposal().resources),
            {"resource_id": "bucket-policy", "resource_type": "aws_s3_bucket_policy", "name": "policy",
             "arguments": {"bucket": "private-plan-bucket", "policy": json.dumps(policy)},
             "rationale": "Malformed policy regression."},
        ]
    )
    assert evaluate(document, proposal_value).verdict == PlanPolicyVerdict.DENY


@pytest.mark.parametrize("port", [22, 3306, 5432, 6379])
def test_public_admin_or_database_ingress_is_denied(port):
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(
        resource(
            "aws_security_group_rule.ingress",
            "aws_security_group_rule",
            {"protocol": "tcp", "from_port": port, "to_port": port, "cidr_blocks": ["0.0.0.0/0"]},
        )
    )
    document["resource_changes"].append(change("aws_security_group_rule.ingress", "aws_security_group_rule"))
    assert "public_sensitive_port" in codes(evaluate(document))


def test_public_web_ingress_is_flagged_for_review():
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(
        resource(
            "aws_security_group_rule.web",
            "aws_security_group_rule",
            {"protocol": "tcp", "from_port": 443, "to_port": 443, "cidr_blocks": ["0.0.0.0/0"]},
        )
    )
    document["resource_changes"].append(change("aws_security_group_rule.web", "aws_security_group_rule"))
    assert "public_web_ingress_review" in codes(evaluate(document))


def test_unknown_ingress_source_fails_closed():
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(
        resource("aws_security_group_rule.unknown", "aws_security_group_rule", {"from_port": 8080, "to_port": 8080})
    )
    document["resource_changes"].append(change("aws_security_group_rule.unknown", "aws_security_group_rule"))
    assert "security_group_ingress_unknown" in codes(evaluate(document))


def test_unknown_s3_public_access_setting_is_denied_from_plan_unknowns():
    document = plan()
    document["resource_changes"][1]["change"]["after_unknown"] = {"block_public_acls": True}
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


def test_unknown_iam_policy_document_is_denied_even_when_after_values_look_safe():
    policy = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {"Effect": "Allow", "Action": "s3:GetObject", "Resource": "arn:aws:s3:::private-plan-bucket/*"}
            ],
        }
    )
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(
        resource("aws_iam_policy.app", "aws_iam_policy", {"policy": policy})
    )
    document["resource_changes"].append(
        change(
            "aws_iam_policy.app",
            "aws_iam_policy",
            after_unknown={"policy": True},
        )
    )
    proposal_value = proposal(
        [
            *(item.model_dump(mode="json") for item in proposal().resources),
            {
                "resource_id": "app-policy",
                "resource_type": "aws_iam_policy",
                "name": "app",
                "arguments": {"policy": policy},
                "rationale": "Limit application access to its own files.",
            },
        ]
    )
    result = evaluate(document, proposal_value)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


def test_unknown_database_encryption_is_denied_even_when_after_values_look_safe():
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(
        resource(
            "aws_db_instance.database",
            "aws_db_instance",
            {"publicly_accessible": False, "storage_encrypted": True, "backup_retention_period": 7},
        )
    )
    document["resource_changes"].append(
        change(
            "aws_db_instance.database",
            "aws_db_instance",
            after_unknown={"storage_encrypted": True},
        )
    )
    proposal_value = proposal(
        [
            *(item.model_dump(mode="json") for item in proposal().resources),
            {
                "resource_id": "database",
                "resource_type": "aws_db_instance",
                "name": "database",
                "arguments": {"publicly_accessible": False, "storage_encrypted": True, "backup_retention_period": 7},
                "rationale": "Keep application data private and encrypted.",
            },
        ]
    )
    result = evaluate(document, proposal_value)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


def test_unknown_rds_backup_retention_is_denied_even_when_after_values_look_safe():
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(
        resource(
            "aws_db_instance.database",
            "aws_db_instance",
            {"publicly_accessible": False, "storage_encrypted": True, "backup_retention_period": 7},
        )
    )
    document["resource_changes"].append(
        change(
            "aws_db_instance.database",
            "aws_db_instance",
            after_unknown={"backup_retention_period": True},
        )
    )
    proposal_value = proposal(
        [
            *(item.model_dump(mode="json") for item in proposal().resources),
            {
                "resource_id": "database",
                "resource_type": "aws_db_instance",
                "name": "database",
                "arguments": {"publicly_accessible": False, "storage_encrypted": True, "backup_retention_period": 7},
                "rationale": "Keep application data private, encrypted, and recoverable.",
            },
        ]
    )
    result = evaluate(document, proposal_value)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


def test_unknown_computed_identifier_does_not_block_policy_review():
    document = plan()
    document["resource_changes"][1]["change"]["after_unknown"] = {"id": True}
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW


def test_unresolved_kms_key_reference_is_outside_encryption_algorithm_unknown_gate():
    unknowns = {
        "rule": [
            {"apply_server_side_encryption_by_default": {"kms_master_key_id": True}}
        ]
    }
    assert not _path_contains_unknown(
        unknowns,
        ("rule", "apply_server_side_encryption_by_default", "sse_algorithm"),
    )


def test_malformed_unknown_metadata_fails_closed():
    document = plan()
    document["resource_changes"][1]["change"]["after_unknown"] = ["invalid"]
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_unknown_structure_invalid" in codes(result)


def test_non_boolean_unknown_leaf_fails_closed():
    document = plan()
    document["resource_changes"][1]["change"]["after_unknown"] = {"block_public_acls": False}
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_unknown_structure_invalid" in codes(result)


@pytest.mark.parametrize("metadata", [None, "missing"])
def test_missing_unknown_metadata_fails_closed_for_monitored_resource(metadata):
    document = plan()
    change_document = document["resource_changes"][1]["change"]
    if metadata == "missing":
        change_document.pop("after_unknown")
    else:
        change_document["after_unknown"] = metadata
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_unknown_structure_invalid" in codes(result)


def test_malformed_ingress_cidr_fails_closed():
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(
        resource(
            "aws_security_group_rule.bad_cidr", "aws_security_group_rule",
            {"from_port": 8080, "to_port": 8080, "cidr_blocks": ["not-a-cidr"]},
        )
    )
    document["resource_changes"].append(change("aws_security_group_rule.bad_cidr", "aws_security_group_rule"))
    assert "security_group_ingress_unknown" in codes(evaluate(document))


def test_scoped_security_group_source_is_not_treated_as_unknown_or_public():
    ingress = resource(
        "aws_security_group_rule.internal", "aws_security_group_rule",
        {"from_port": 8080, "to_port": 8080, "protocol": "tcp", "source_security_group_id": "sg-0123456789abcdef0"},
    )
    document = plan()
    document["planned_values"]["root_module"]["resources"].append(ingress)
    document["resource_changes"].append(change("aws_security_group_rule.internal", "aws_security_group_rule"))
    proposal_value = proposal(
        [
            *(item.model_dump(mode="json") for item in proposal().resources),
            {"resource_id": "internal-ingress", "resource_type": "aws_security_group_rule", "name": "internal",
             "arguments": {"from_port": 8080, "to_port": 8080, "protocol": "tcp", "source_security_group_id": "sg-0123456789abcdef0"},
             "rationale": "Allow traffic from a scoped application security group."},
        ]
    )
    result = evaluate(document, proposal_value)
    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert result.findings == ()


@pytest.mark.parametrize(
    "policy,expected_code",
    [
        (
            {"Statement": {"Effect": "Allow", "Action": "*", "Resource": "*"}},
            "iam_privileged_wildcard",
        ),
        (
            {"Statement": {"Effect": "Allow", "Action": "iam:PassRole", "Resource": "*"}},
            "iam_passrole_unbounded_denied",
        ),
        (
            {"Statement": {"Effect": "Allow", "Action": "sts:AssumeRole", "Resource": "*"}},
            "sts_assume_role_unbounded_denied",
        ),
        (
            {
                "Statement": {
                    "Effect": "Allow",
                    "Action": "sts:Assume*",
                    "Resource": "arn:aws:iam::654654474502:role/app",
                }
            },
            "sts_assume_role_unbounded_denied",
        ),
        (
            {
                "Statement": {
                    "Effect": "Allow",
                    "Action": "iam:CreateRole",
                    "Resource": "arn:aws:iam::654654474502:role/*",
                }
            },
            "iam_permission_management_denied",
        ),
    ],
)
def test_privileged_iam_is_denied(policy, expected_code):
    result = evaluate(
        plan(
            resources=[
                resource(
                    "aws_iam_policy.application", "aws_iam_policy", {"policy": json.dumps(policy)}
                ),
                resource("terraform_data.account_guard", "terraform_data", {"input": None}),
            ],
            changes=[
                change("aws_iam_policy.application", "aws_iam_policy"),
                change("terraform_data.account_guard", "terraform_data"),
            ],
        ),
        proposal(
            [
                {
                    "resource_id": "application",
                    "resource_type": "aws_iam_policy",
                    "name": "application",
                    "arguments": {"name": "application", "policy": json.dumps(policy)},
                    "rationale": "Application permissions.",
                }
            ]
        ),
    )
    assert result.verdict == PlanPolicyVerdict.DENY
    assert expected_code in codes(result)


def evaluate_application_policy(policy_document):
    encoded = json.dumps(policy_document)
    resource_address = "aws_iam_policy.application"
    resources = [
        resource(resource_address, "aws_iam_policy", {"name": "application", "policy": encoded}),
        resource("terraform_data.account_guard", "terraform_data", {"input": None}),
    ]
    generated = proposal(
        [
            {
                "resource_id": "application",
                "resource_type": "aws_iam_policy",
                "name": "application",
                "arguments": {"name": "application", "policy": encoded},
                "rationale": "Application permissions.",
            }
        ]
    )
    return evaluate(
        plan(
            resources,
            [
                change(resource_address, "aws_iam_policy"),
                change("terraform_data.account_guard", "terraform_data"),
            ],
        ),
        generated,
    )


def evaluate_role_trust(trust_document):
    encoded = json.dumps(trust_document)
    role_address = "aws_iam_role.application"
    resources = [
        resource(role_address, "aws_iam_role", {"name": "application", "assume_role_policy": encoded}),
        resource("terraform_data.account_guard", "terraform_data", {"input": None}),
    ]
    generated = proposal(
        [
            {
                "resource_id": "application",
                "resource_type": "aws_iam_role",
                "name": "application",
                "arguments": {"name": "application", "assume_role_policy": trust_document},
                "rationale": "Application runtime role.",
            }
        ]
    )
    return evaluate(
        plan(
            resources,
            [change(role_address, "aws_iam_role"), change("terraform_data.account_guard", "terraform_data")],
        ),
        generated,
    )


@pytest.mark.parametrize(
    "policy",
    [
        {
            "Statement": {
                "Effect": "Allow",
                "NotAction": "iam:DeleteRole",
                "Resource": "arn:aws:iam::654654474502:role/app",
            }
        },
        {
            "Statement": {
                "Effect": "Allow",
                "Action": "iam:CreatePolicyVersion",
                "Resource": "arn:aws:iam::654654474502:policy/app",
            }
        },
        {
            "Statement": {
                "Effect": "Allow",
                "Action": "iam:AttachRolePolicy",
                "Resource": "arn:aws:iam::654654474502:role/app",
            }
        },
    ],
)
def test_exact_resource_iam_management_and_not_action_are_denied(policy):
    result = evaluate_application_policy(policy)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert {"iam_not_action_policy_denied", "iam_permission_management_denied"} & codes(result)


@pytest.mark.parametrize(
    "resource_arn,condition",
    [
        ("*", {"StringEquals": {"iam:PassedToService": "lambda.amazonaws.com"}}),
        ("arn:aws:iam::654654474502:role/app", None),
        (
            "arn:aws:iam::654654474502:role/app",
            {"StringNotEquals": {"iam:PassedToService": "lambda.amazonaws.com"}},
        ),
        (
            "arn:aws:iam::654654474502:role/*",
            {"StringEquals": {"iam:PassedToService": "lambda.amazonaws.com"}},
        ),
        (
            "arn:aws:iam::654654474502:role/app",
            {"StringEquals": {"iam:PassedToService": "*.amazonaws.com"}},
        ),
    ],
)
def test_unbounded_or_malformed_passrole_is_denied(resource_arn, condition):
    statement = {"Effect": "Allow", "Action": "iam:PassRole", "Resource": resource_arn}
    if condition is not None:
        statement["Condition"] = condition
    result = evaluate_application_policy({"Statement": statement})
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "iam_passrole_unbounded_denied" in codes(result)


def test_exact_passrole_with_literal_service_condition_requires_human_review():
    result = evaluate_application_policy(
        {
            "Statement": {
                "Effect": "Allow",
                "Action": "iam:PassRole",
                "Resource": "arn:aws:iam::654654474502:role/app/runtime",
                "Condition": {"StringEquals": {"iam:PassedToService": ["lambda.amazonaws.com"]}},
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.REVIEW_REQUIRED
    assert "iam_passrole_requires_review" in codes(result)


def test_scoped_read_only_iam_policy_remains_eligible():
    result = evaluate_application_policy(
        {
            "Statement": {
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:GetObjectVersion"],
                "Resource": "arn:aws:s3:::application-files/*",
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert result.findings == ()


@pytest.mark.parametrize(
    "action,resource_arn",
    [
        (
            "secretsmanager:GetSecretValue",
            "arn:aws:secretsmanager:us-east-1:654654474502:secret:application-password-AbCdEf",
        ),
        ("secretsmanager:BatchGetSecretValue", "*"),
        ("secretsmanager:Get*", "arn:aws:secretsmanager:us-east-1:654654474502:secret:app-*"),
        ("secretsmanager:*", "*"),
        ("SecretsManager:GETSECRETVALUE", "arn:aws:secretsmanager:us-east-1:654654474502:secret:app-AbCdEf"),
    ],
)
def test_unbound_secrets_manager_value_reads_are_denied(action, resource_arn):
    result = evaluate_application_policy(
        {
            "Statement": {
                "Effect": "Allow",
                "Action": action,
                "Resource": resource_arn,
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.DENY
    finding = next(
        item for item in result.findings if item.code == "iam_secret_value_read_unbound"
    )
    assert resource_arn not in finding.message
    assert "SecretValue" not in finding.message


def test_secrets_manager_metadata_read_remains_eligible():
    result = evaluate_application_policy(
        {
            "Statement": {
                "Effect": "Allow",
                "Action": "secretsmanager:DescribeSecret",
                "Resource": "arn:aws:secretsmanager:us-east-1:654654474502:secret:app-AbCdEf",
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert result.findings == ()


def test_specific_same_account_assume_role_requires_human_review():
    result = evaluate_application_policy(
        {
            "Statement": {
                "Effect": "Allow",
                "Action": "sts:AssumeRole",
                "Resource": "arn:aws:iam::654654474502:role/app/reader",
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.REVIEW_REQUIRED
    assert "sts_assume_role_requires_review" in codes(result)


def test_external_assume_role_is_denied():
    result = evaluate_application_policy(
        {
            "Statement": {
                "Effect": "Allow",
                "Action": "sts:AssumeRole",
                "Resource": "arn:aws:iam::111122223333:role/external",
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "sts_assume_role_unbounded_denied" in codes(result)


def test_external_account_role_trust_is_denied():
    result = evaluate_role_trust(
        {
            "Statement": {
                "Effect": "Allow",
                "Principal": {"AWS": "arn:aws:iam::111122223333:root"},
                "Action": "sts:AssumeRole",
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "iam_external_trust_denied" in codes(result)


def test_same_account_role_trust_requires_human_review():
    result = evaluate_role_trust(
        {
            "Statement": {
                "Effect": "Allow",
                "Principal": {"AWS": f"arn:aws:iam::{ACCOUNT}:root"},
                "Action": "sts:AssumeRole",
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.REVIEW_REQUIRED
    assert "iam_same_account_trust_requires_review" in codes(result)


def test_allow_not_principal_trust_is_denied():
    result = evaluate_role_trust(
        {
            "Statement": {
                "Effect": "Allow",
                "NotPrincipal": {"AWS": f"arn:aws:iam::{ACCOUNT}:role/blocked"},
                "Action": "sts:AssumeRole",
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "iam_not_principal_trust_denied" in codes(result)


def test_exact_aws_service_trust_is_accepted_without_extra_review():
    result = evaluate_role_trust(
        {
            "Statement": {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        }
    )
    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert result.findings == ()


def test_non_admin_managed_policy_attachment_requires_human_review():
    resources = [
        resource(
            "aws_iam_role.application",
            "aws_iam_role",
            {
                "name": "application",
                "assume_role_policy": json.dumps(
                    {
                        "Statement": {
                            "Effect": "Allow",
                            "Principal": {"Service": "lambda.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        }
                    }
                ),
            },
        ),
        resource(
            "aws_iam_role_policy_attachment.runtime",
            "aws_iam_role_policy_attachment",
            {"policy_arn": "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"},
        ),
        resource("terraform_data.account_guard", "terraform_data", {"input": None}),
    ]
    generated = proposal(
        [
            {
                "resource_id": "application",
                "resource_type": "aws_iam_role",
                "name": "application",
                "arguments": {
                    "name": "application",
                    "assume_role_policy": {
                        "Version": "2012-10-17",
                        "Statement": {
                            "Effect": "Allow",
                            "Principal": {"Service": "lambda.amazonaws.com"},
                            "Action": "sts:AssumeRole",
                        },
                    },
                },
                "outputs": [{"name": "name", "value_type": "string"}],
                "rationale": "Lambda runtime role.",
            },
            {
                "resource_id": "runtime",
                "resource_type": "aws_iam_role_policy_attachment",
                "name": "runtime",
                "arguments": {
                    "role": {
                        "kind": "resource_reference",
                        "resource_id": "application",
                        "output_name": "name",
                        "value_type": "string",
                    },
                    "policy_arn": "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                },
                "rationale": "Permit application logging.",
            },
        ]
    )
    document = plan(resources, [change(item["address"], item["type"]) for item in resources])
    result = evaluate(document, generated)
    assert result.verdict == PlanPolicyVerdict.REVIEW_REQUIRED
    assert "iam_managed_policy_contents_unverified" in codes(result)


def test_wildcard_role_trust_and_administrator_attachment_are_denied():
    resources = [
        resource("aws_iam_role.application", "aws_iam_role", {"assume_role_policy": json.dumps({"Statement": {"Effect": "Allow", "Principal": "*", "Action": "sts:AssumeRole"}})}),
        resource("aws_iam_role_policy_attachment.admin", "aws_iam_role_policy_attachment", {"policy_arn": "arn:aws:iam::aws:policy/AdministratorAccess"}),
        resource("terraform_data.account_guard", "terraform_data", {"input": None}),
    ]
    generated = [
        {"resource_id": "application", "resource_type": "aws_iam_role", "name": "application", "arguments": {"name": "application", "assume_role_policy": json.dumps({"Statement": {"Effect": "Allow", "Principal": "*", "Action": "sts:AssumeRole"}})}, "rationale": "Application role."},
        {"resource_id": "admin", "resource_type": "aws_iam_role_policy_attachment", "name": "admin", "arguments": {"role": "application", "policy_arn": "arn:aws:iam::aws:policy/AdministratorAccess"}, "rationale": "Test denied attachment."},
    ]
    document = plan(resources, [change(item["address"], item["type"]) for item in resources])
    result = evaluate(document, proposal(generated))
    assert {"iam_wildcard_trust", "iam_administrator_access_attached"}.issubset(codes(result))


@pytest.mark.parametrize(
    "kind,values,expected",
    [
        ("aws_db_instance", {"publicly_accessible": True, "storage_encrypted": True, "backup_retention_period": 7}, "database_publicly_accessible"),
        ("aws_db_instance", {"publicly_accessible": False, "storage_encrypted": False, "backup_retention_period": 7}, "database_encryption_required"),
        ("aws_db_instance", {"storage_encrypted": True, "backup_retention_period": 7}, "database_publicly_accessible"),
    ],
)
def test_database_publicness_and_encryption_fail_closed(kind, values, expected):
    address = f"{kind}.database"
    resources = [resource(address, kind, values), resource("terraform_data.account_guard", "terraform_data", {"input": None})]
    proposal_value = proposal([{"resource_id": "database", "resource_type": kind, "name": "database", "arguments": {"identifier": "database", **values}, "rationale": "Database."}])
    result = evaluate(plan(resources, [change(address, kind), change("terraform_data.account_guard", "terraform_data")]), proposal_value)
    assert expected in codes(result)


@pytest.mark.parametrize(
    "kind,retention",
    [
        ("aws_db_instance", _OMIT),
        ("aws_db_instance", "seven"),
        ("aws_rds_cluster", _OMIT),
        ("aws_rds_cluster", 1.5),
    ],
)
def test_rds_backup_retention_must_be_explicit_and_well_formed(kind, retention):
    values = {"publicly_accessible": False, "storage_encrypted": True}
    if retention is not _OMIT:
        values["backup_retention_period"] = retention
    address = f"{kind}.database"
    resources = [
        resource(address, kind, values),
        resource("terraform_data.account_guard", "terraform_data", {"input": None}),
    ]
    proposal_value = proposal(
        [
            {
                "resource_id": "database",
                "resource_type": kind,
                "name": "database",
                "arguments": {"identifier": "database", **values},
                "rationale": "Database with an explicit backup policy.",
            }
        ]
    )
    result = evaluate(
        plan(resources, [change(address, kind), change("terraform_data.account_guard", "terraform_data")]),
        proposal_value,
    )
    assert "database_backup_retention_invalid" in codes(result)


@pytest.mark.parametrize(
    "kind,retention,expected",
    [
        ("aws_db_instance", 0, "database_backup_retention_disabled"),
        ("aws_db_instance", -1, "database_backup_retention_invalid"),
        ("aws_db_instance", 36, "database_backup_retention_invalid"),
        ("aws_db_instance", True, "database_backup_retention_invalid"),
        ("aws_rds_cluster", 0, "database_backup_retention_invalid"),
        ("aws_rds_cluster", 7, None),
    ],
)
def test_rds_backup_retention_is_bounded_and_disabled_instance_backups_require_review(kind, retention, expected):
    values = {
        "publicly_accessible": False,
        "storage_encrypted": True,
        "backup_retention_period": retention,
    }
    address = f"{kind}.database"
    resources = [
        resource(address, kind, values),
        resource("terraform_data.account_guard", "terraform_data", {"input": None}),
    ]
    proposal_value = proposal(
        [
            {
                "resource_id": "database",
                "resource_type": kind,
                "name": "database",
                "arguments": {"identifier": "database", **values},
                "rationale": "Database with an explicit backup policy.",
            }
        ]
    )
    result = evaluate(
        plan(resources, [change(address, kind), change("terraform_data.account_guard", "terraform_data")]),
        proposal_value,
    )
    if expected is None:
        assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
        assert "database_backup_retention_invalid" not in codes(result)
    else:
        assert expected in codes(result)


@pytest.mark.parametrize(
    "skip_snapshot,identifier,expected",
    [
        (True, None, "rds_final_snapshot_skipped"),
        (False, "final-database-snapshot", None),
        (False, None, "rds_final_snapshot_identifier_missing"),
    ],
)
def test_rds_replacement_requires_valid_final_snapshot_or_explicit_review(skip_snapshot, identifier, expected):
    address = "aws_db_instance.database"
    before = {
        "tags": ownership_scope().tags(),
        "skip_final_snapshot": skip_snapshot,
        "final_snapshot_identifier": identifier,
    }
    values = {
        "publicly_accessible": False,
        "storage_encrypted": True,
        "backup_retention_period": 7,
    }
    document = plan(
        [
            resource(address, "aws_db_instance", values),
            resource("terraform_data.account_guard", "terraform_data", {"input": None}),
        ],
        [
            change(
                address,
                "aws_db_instance",
                ("delete", "create"),
                before=before,
                after={"tags": ownership_scope().tags()},
            ),
            change("terraform_data.account_guard", "terraform_data"),
        ],
    )
    proposal_value = proposal(
        [
            {
                "resource_id": "database",
                "resource_type": "aws_db_instance",
                "name": "database",
                "arguments": {"identifier": "database", **values},
                "rationale": "Database with explicit retention and encryption.",
            }
        ]
    )
    result = evaluate(document, proposal_value)
    if expected is None:
        assert result.verdict == PlanPolicyVerdict.REVIEW_REQUIRED
        assert "rds_final_snapshot_skipped" not in codes(result)
        assert "destructive_change_requires_review" in codes(result)
    else:
        assert expected in codes(result)


@pytest.mark.parametrize(
    "before,expected",
    [
        ({"skip_final_snapshot": True}, "rds_final_snapshot_skipped"),
        ({"skip_final_snapshot": False, "final_snapshot_identifier": "final-db"}, None),
        ({"skip_final_snapshot": False}, "rds_final_snapshot_identifier_missing"),
        ({"skip_final_snapshot": "unknown"}, "rds_final_snapshot_setting_unknown"),
    ],
)
def test_rds_delete_final_snapshot_policy(before, expected):
    findings = []
    _check_rds_final_snapshot_changes(
        {
            "resource_changes": [
                {
                    "address": "aws_db_instance.database",
                    "type": "aws_db_instance",
                    "change": {"actions": ["delete"], "before": before},
                }
            ]
        },
        findings,
    )
    codes_found = {finding.code for finding in findings}
    if expected is None:
        assert "rds_final_snapshot_skipped" not in codes_found
        assert "rds_final_snapshot_identifier_missing" not in codes_found
    else:
        assert expected in codes_found


def test_unexpected_region_or_resource_inventory_is_denied():
    wrong_region = plan()
    wrong_region["configuration"]["provider_config"]["aws"]["expressions"]["region"]["constant_value"] = "eu-west-1"
    assert evaluate(wrong_region).verdict == PlanPolicyVerdict.DENY
    extra = plan()
    extra["planned_values"]["root_module"]["resources"].append(resource("aws_s3_bucket.extra", "aws_s3_bucket", {"bucket": "unapproved"}))
    assert "plan_resource_inventory_mismatch" in codes(evaluate(extra))


@pytest.mark.parametrize("guard", [None, "${true}", '${data.aws_caller_identity.trusted.account_id == "111111111111"}'])
def test_missing_or_mismatched_trusted_account_guard_is_denied(guard):
    trusted = {
        "data": {"aws_caller_identity": {"trusted": {}}},
        "resource": {"terraform_data": {"account_guard": {"lifecycle": {"precondition": {"condition": guard}}}}},
    }
    result = evaluate_generated_plan_policy(
        plan(),
        proposal(),
        expected_account_id=ACCOUNT,
        expected_region=REGION,
        ownership_scope=ownership_scope(),
        trusted_configuration=trusted,
    )
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "plan_policy_input_invalid" in codes(result)


def test_nested_unproposed_resource_is_not_hidden_from_inventory():
    document = plan()
    document["planned_values"]["root_module"]["child_modules"] = [
        {"resources": [resource("module.hidden.aws_s3_bucket.extra", "aws_s3_bucket", {"bucket": "extra"})]}
    ]
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "plan_resource_inventory_mismatch" in codes(result)


def test_unexplained_unknown_plan_shape_fails_closed_without_echoing_values():
    secret = "super-secret-plan-value"
    document = plan()
    document["planned_values"]["root_module"]["resources"] = secret
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert secret not in repr(result)


def test_delete_replacement_and_sensitive_change_require_human_review():
    document = plan()
    document["resource_changes"] = [
        change("aws_s3_bucket.bucket", "aws_s3_bucket", ("delete",), before_sensitive={"secret": True}),
        change("aws_s3_bucket_public_access_block.public_access", "aws_s3_bucket_public_access_block"),
        change("terraform_data.account_guard", "terraform_data"),
    ]
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.REVIEW_REQUIRED
    assert {"destructive_change_requires_review", "sensitive_change_requires_review"}.issubset(codes(result))


def test_delete_requires_matching_ownership_on_the_existing_resource():
    document = plan()
    document["resource_changes"][0] = change(
        "aws_s3_bucket.bucket",
        "aws_s3_bucket",
        ("delete",),
        before={"tags": {**ownership_scope().tags(), "DavDeployPlanId": "another-plan"}},
    )

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "resource_ownership_tags_mismatch" in codes(result)


def test_replacement_with_matching_ownership_on_both_sides_requires_review():
    document = plan()
    document["resource_changes"][0] = change(
        "aws_s3_bucket.bucket",
        "aws_s3_bucket",
        ("delete", "create"),
    )

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.REVIEW_REQUIRED
    assert "destructive_change_requires_review" in codes(result)
    assert "resource_ownership_tags_mismatch" not in codes(result)


def test_replacement_requires_matching_ownership_before_and_after():
    document = plan()
    document["resource_changes"][0] = change(
        "aws_s3_bucket.bucket",
        "aws_s3_bucket",
        ("delete", "create"),
        before={"tags": {**ownership_scope().tags(), "DavDeployPlanId": "another-plan"}},
        after={"tags": ownership_scope().tags()},
    )

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "resource_ownership_tags_mismatch" in codes(result)


@pytest.mark.parametrize("actions", [("update",), ("delete",), ("delete", "create")])
def test_existing_resource_accepts_prior_source_revision_for_same_plan(actions):
    document = plan()
    existing = change("aws_s3_bucket.bucket", "aws_s3_bucket", actions)
    existing["change"]["before"]["tags"]["DavDeploySourceRevision"] = (
        "sha256:" + "a" * 64
    )
    document["resource_changes"][0] = existing
    if actions == ("delete",):
        # Deleted resources may not appear in planned_values. Their before
        # values still need to prove stable ownership and a valid prior revision.
        document["planned_values"]["root_module"]["resources"] = document[
            "planned_values"
        ]["root_module"]["resources"][1:]

    result = evaluate(document)

    assert "resource_ownership_tags_mismatch" not in codes(result)
    assert "resource_ownership_tags_missing" not in codes(result)
    if actions in (("delete",), ("delete", "create")):
        assert "destructive_change_requires_review" in codes(result)


def test_existing_resource_requires_well_formed_prior_source_revision():
    document = plan()
    existing = change("aws_s3_bucket.bucket", "aws_s3_bucket", ("update",))
    existing["change"]["before"]["tags"]["DavDeploySourceRevision"] = "old-revision"
    document["resource_changes"][0] = existing

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "resource_ownership_tags_mismatch" in codes(result)


def test_desired_resource_requires_exact_current_source_revision():
    document = plan()
    document["resource_changes"][0]["change"]["after"]["tags"][
        "DavDeploySourceRevision"
    ] = "sha256:" + "a" * 64

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "resource_ownership_tags_mismatch" in codes(result)


@pytest.mark.parametrize("actions", [("forget",), ("update", "forget")])
def test_unknown_managed_aws_actions_are_denied(actions):
    document = plan()
    document["resource_changes"][0] = change("aws_s3_bucket.bucket", "aws_s3_bucket", actions)

    result = evaluate(document)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "plan_policy_input_invalid" in codes(result)


def test_delete_of_resource_outside_proposal_is_denied():
    document = plan()
    document["resource_changes"].append(change("aws_s3_bucket.unowned", "aws_s3_bucket", ("delete",)))
    result = evaluate(document)
    assert result.verdict == PlanPolicyVerdict.DENY
    assert "unproposed_resource_change" in codes(result)


def test_dynamodb_pitr_enabled_with_valid_recovery_period_passes_recovery_policy():
    document, proposal_value = dynamodb_case(
        [{"enabled": True, "recovery_period_in_days": 35}], backup_required=True
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert not {"dynamodb_pitr_required", "dynamodb_pitr_disabled", "dynamodb_pitr_recovery_period_invalid"} & codes(result)


def test_dynamodb_pitr_disabled_is_reviewed_when_backups_are_not_required():
    document, proposal_value = dynamodb_case(
        [{"enabled": False, "recovery_period_in_days": 35}]
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.REVIEW_REQUIRED
    assert "dynamodb_pitr_disabled" in codes(result)


@pytest.mark.parametrize(
    "pitr",
    [None, [{"enabled": False, "recovery_period_in_days": 35}]],
)
def test_dynamodb_backup_requirement_denies_missing_or_disabled_pitr(pitr):
    document, proposal_value = dynamodb_case(pitr, backup_required=True)

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "dynamodb_pitr_required" in codes(result)


@pytest.mark.parametrize("unknown_path", ["enabled", "recovery_period_in_days"])
def test_unknown_dynamodb_pitr_values_are_denied(unknown_path):
    document, proposal_value = dynamodb_case(
        [{"enabled": True, "recovery_period_in_days": 30}],
        after_unknown={"point_in_time_recovery": {unknown_path: True}},
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "policy_critical_value_unknown" in codes(result)


@pytest.mark.parametrize("recovery_period", [None, 0, 36, True, "30"])
def test_dynamodb_pitr_enabled_requires_bounded_integer_recovery_period(recovery_period):
    document, proposal_value = dynamodb_case(
        [{"enabled": True, "recovery_period_in_days": recovery_period}],
        backup_required=True,
    )

    result = evaluate(document, proposal_value)

    assert result.verdict == PlanPolicyVerdict.DENY
    assert "dynamodb_pitr_recovery_period_invalid" in codes(result)


def test_dynamodb_pitr_policy_findings_do_not_include_plan_values():
    document, proposal_value = dynamodb_case(
        [{"enabled": False, "recovery_period_in_days": 35}]
    )
    document["planned_values"]["root_module"]["resources"][-1]["values"][
        "sensitive_customer_value"
    ] = "private-data-marker"

    result = evaluate(document, proposal_value)

    assert "dynamodb_pitr_disabled" in codes(result)
    assert "private-data-marker" not in repr(result)
