from __future__ import annotations

import json

import pytest
from davdeploy.generated_deployment_contract import GeneratedDeploymentProposal
from davdeploy.generated_plan_ownership import PlanOwnershipScope
from davdeploy.generated_plan_policy import (
    PlanPolicyVerdict,
    _path_contains_unknown,
    evaluate_generated_plan_policy,
)

ACCOUNT = "654654474502"
REGION = "us-east-1"


def ownership_scope():
    return PlanOwnershipScope(
        organization_id="org-test",
        workspace_id="workspace-test",
        project_id="project-test",
        environment_id="production",
        plan_id="plan-internal-id",
        revision_id="revision-internal-id",
    )


def proposal(resources=None):
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
            "contract_version": "1.0",
            "source_revision": "test-revision",
            "context_digest": "a" * 64,
            "requirements": {"region": REGION},
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
            {"publicly_accessible": False, "storage_encrypted": True},
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
                "arguments": {"publicly_accessible": False, "storage_encrypted": True},
                "rationale": "Keep application data private and encrypted.",
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
        ("aws_db_instance", {"publicly_accessible": True, "storage_encrypted": True}, "database_publicly_accessible"),
        ("aws_db_instance", {"publicly_accessible": False, "storage_encrypted": False}, "database_encryption_required"),
        ("aws_db_instance", {"storage_encrypted": True}, "database_publicly_accessible"),
    ],
)
def test_database_publicness_and_encryption_fail_closed(kind, values, expected):
    address = f"{kind}.database"
    resources = [resource(address, kind, values), resource("terraform_data.account_guard", "terraform_data", {"input": None})]
    proposal_value = proposal([{"resource_id": "database", "resource_type": kind, "name": "database", "arguments": {"identifier": "database", **values}, "rationale": "Database."}])
    result = evaluate(plan(resources, [change(address, kind), change("terraform_data.account_guard", "terraform_data")]), proposal_value)
    assert expected in codes(result)


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
