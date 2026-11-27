from davdeploy.domain import InfrastructurePlanDecision, InfrastructurePlanState
from davdeploy.models import InfrastructurePlanDecisionRecord
from davdeploy.security import Principal
from davdeploy.service import plan_hash
from sqlalchemy import select
from test_product import founder, make_service, operator


def plan_content() -> dict:
    return {
        "kind": "davdeploy.aws.infrastructure-plan.review.v1",
        "application_analysis": {
            "repository": "https://github.com/example/service",
            "branch": "main",
            "request": "Deploy a private FastAPI service with monitoring.",
        },
        "target": {"provider": "aws", "account_id": "123456789012", "region": "us-east-1"},
        "observability": {
            "metrics_backend": "Prometheus-compatible Amazon Managed Service for Prometheus",
            "dashboard": "Amazon Managed Grafana",
        },
        "policy_findings": {"result": "APPROVAL_REQUIRED"},
    }


def draft(service):
    project = service.create_project(founder(), "lifecycle-app", "https://github.com/example/service")
    return service.create_infrastructure_plan(founder(), project.id, "Private API", plan_content())


def test_developer_submits_and_administrator_approves_exact_revision():
    service, db = make_service()
    revision = draft(service)
    submitted = service.submit_infrastructure_plan(founder(), revision.id)
    assert submitted.state == InfrastructurePlanState.SUBMITTED
    approved = service.decide_infrastructure_plan(
        operator(), revision.id, InfrastructurePlanDecision.APPROVED, revision.content_digest
    )
    assert approved.state == InfrastructurePlanState.APPROVED
    decision = db.scalar(select(InfrastructurePlanDecisionRecord).where(
        InfrastructurePlanDecisionRecord.revision_id == revision.id
    ))
    assert decision and not decision.is_self_approval
    assert decision.approved_digest == revision.content_digest


def test_administrator_can_self_approve_and_audits_exception():
    service, db = make_service()
    project = service.create_project(operator(), "admin-app", "https://github.com/example/admin-service")
    revision = service.create_infrastructure_plan(operator(), project.id, "Admin API", plan_content())
    service.submit_infrastructure_plan(operator(), revision.id)
    service.decide_infrastructure_plan(
        operator(), revision.id, InfrastructurePlanDecision.APPROVED, revision.content_digest
    )
    decision = db.scalar(select(InfrastructurePlanDecisionRecord).where(
        InfrastructurePlanDecisionRecord.revision_id == revision.id
    ))
    assert decision and decision.is_self_approval
    assert decision.authorization_policy == "workspace-administrator-self-approval-allowed"


def test_developer_cannot_decide_submitted_revision():
    service, _ = make_service()
    revision = draft(service)
    service.submit_infrastructure_plan(founder(), revision.id)
    try:
        service.decide_infrastructure_plan(
            founder(), revision.id, InfrastructurePlanDecision.APPROVED, revision.content_digest
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("developer decision was accepted")
    assert revision.state == InfrastructurePlanState.SUBMITTED


def test_rejection_requires_reason_and_new_revision_preserves_history():
    service, _ = make_service()
    revision = draft(service)
    service.submit_infrastructure_plan(founder(), revision.id)
    try:
        service.decide_infrastructure_plan(
            operator(), revision.id, InfrastructurePlanDecision.REJECTED, revision.content_digest
        )
    except ValueError as error:
        assert "reason" in str(error)
    else:
        raise AssertionError("reason-free rejection was accepted")
    rejected = service.decide_infrastructure_plan(
        operator(), revision.id, InfrastructurePlanDecision.REJECTED, revision.content_digest, "Need a budget."
    )
    revision_two = service.revise_infrastructure_plan(
        founder(), rejected.infrastructure_plan_id, {**plan_content(), "monthly_budget_usd": 300}
    )
    assert rejected.state == InfrastructurePlanState.REJECTED
    assert revision_two.revision_number == 2
    assert revision_two.state == InfrastructurePlanState.DRAFT
    assert rejected.content_digest == plan_hash(plan_content())


def test_creator_can_create_revised_draft_from_editable_constraints():
    service, _ = make_service()
    revision = draft(service)

    revised = service.revise_infrastructure_plan_constraints(
        founder(),
        revision.infrastructure_plan_id,
        {
            "monthly_budget_usd": 300,
            "region": "eu-west-1",
            "environment": ["production"],
            "data_classification": "internal",
            "availability_target": "99.99%",
            "workload_type": "event-driven document processor",
            "public_access": True,
            "accepted_assumptions": ["Fixture pricing is enough for draft review."],
            "rejected_assumptions": ["Do not assume private-only browser access."],
        },
    )

    spec = revised.content["application_analysis"]["workload_spec"]
    assert revised.revision_number == 2
    assert revised.state == InfrastructurePlanState.DRAFT
    assert spec["monthly_budget_usd"] == 300
    assert spec["region_constraints"] == ["eu-west-1"]
    assert spec["environments"] == ["production"]
    assert spec["data_classification"] == "internal"
    assert spec["availability_target"] == "99.99%"
    assert spec["workload_type"] == "event-driven document processor"
    assert spec["requires_private_connectivity"] is False
    assert revised.content["assumption_decisions"]["accepted"] == [
        "Fixture pricing is enough for draft review."
    ]
    assert "monthly_budget_usd" in revised.content["revision_diff"]
    assert revised.content_digest == plan_hash(revised.content)


def test_customer_usage_assumptions_are_persisted_only_in_a_new_revision():
    service, _ = make_service()
    original = draft(service)
    usage = {
        "monthly_storage_gb": {"minimum": 10, "maximum": 20},
        "monthly_put_copy_post_list_requests": {"minimum": 100, "maximum": 200},
        "monthly_get_requests": {"minimum": 300, "maximum": 400},
        "monthly_internet_egress_gb": {"minimum": 0, "maximum": 5},
    }

    revised = service.revise_infrastructure_plan_constraints(
        founder(),
        original.infrastructure_plan_id,
        {"pricing_usage_assumptions": usage},
    )

    assert original.revision_number == 1
    assert "pricing_usage_assumptions" not in original.content.get("user_constraints", {})
    assert revised.revision_number == 2
    assert revised.content["user_constraints"]["pricing_usage_assumptions"] == usage
    assert (
        revised.content["application_analysis"]["workload_spec"]["pricing_usage_assumptions"]
        == usage
    )
    assert revised.content["revision_diff"]["pricing_usage_assumptions"] == {
        "before": None,
        "after": usage,
    }
    assert revised.content_digest == plan_hash(revised.content)

    cleared = service.revise_infrastructure_plan_constraints(
        founder(),
        original.infrastructure_plan_id,
        {"pricing_usage_assumptions": None},
    )
    assert cleared.revision_number == 3
    assert "pricing_usage_assumptions" not in cleared.content["user_constraints"]
    assert (
        "pricing_usage_assumptions"
        not in cleared.content["application_analysis"]["workload_spec"]
    )


def test_customer_sqs_usage_assumptions_are_persisted_and_cleared_by_new_revisions():
    service, _ = make_service()
    original = draft(service)
    usage = {
        "monthly_standard_request_units": {"minimum": 1_000, "maximum": 2_000},
        "monthly_fifo_request_units": {"minimum": 0, "maximum": 0},
        "monthly_fair_queue_request_units": {"minimum": 0, "maximum": 0},
        "monthly_cross_region_transfer_gb": {"minimum": 0, "maximum": 0},
        "monthly_internet_egress_gb": {"minimum": 0, "maximum": 0},
    }
    revised = service.revise_infrastructure_plan_constraints(
        founder(), original.infrastructure_plan_id,
        {"sqs_pricing_usage_assumptions": usage},
    )
    assert revised.revision_number == 2
    assert revised.content["user_constraints"]["sqs_pricing_usage_assumptions"] == usage
    assert revised.content["application_analysis"]["workload_spec"]["sqs_pricing_usage_assumptions"] == usage
    assert revised.content["revision_diff"]["sqs_pricing_usage_assumptions"] == {
        "before": None, "after": usage,
    }
    cleared = service.revise_infrastructure_plan_constraints(
        founder(), original.infrastructure_plan_id,
        {"sqs_pricing_usage_assumptions": None},
    )
    assert "sqs_pricing_usage_assumptions" not in cleared.content["user_constraints"]
    assert "sqs_pricing_usage_assumptions" not in cleared.content["application_analysis"]["workload_spec"]



def test_customer_rds_backup_usage_assumptions_are_persisted_and_cleared_by_new_revisions():
    service, _ = make_service()
    original = draft(service)
    usage = {"monthly_backup_storage_gb_month": {"minimum": 2, "maximum": 20}}

    revised = service.revise_infrastructure_plan_constraints(
        founder(),
        original.infrastructure_plan_id,
        {"rds_pricing_usage_assumptions": usage},
    )

    assert revised.revision_number == 2
    assert revised.content["user_constraints"]["rds_pricing_usage_assumptions"] == usage
    assert revised.content["application_analysis"]["workload_spec"]["rds_pricing_usage_assumptions"] == usage
    assert revised.content["revision_diff"]["rds_pricing_usage_assumptions"] == {
        "before": None,
        "after": usage,
    }
    assert revised.content_digest == plan_hash(revised.content)

    cleared = service.revise_infrastructure_plan_constraints(
        founder(),
        original.infrastructure_plan_id,
        {"rds_pricing_usage_assumptions": None},
    )
    assert "rds_pricing_usage_assumptions" not in cleared.content["user_constraints"]
    assert "rds_pricing_usage_assumptions" not in cleared.content["application_analysis"]["workload_spec"]


def test_customer_serverless_usage_assumptions_are_persisted_and_cleared_by_new_revisions():
    service, _ = make_service()
    original = draft(service)
    usage = {
        "lambda_functions": {
            "aws_lambda_function.api": {
                "monthly_invocations": {"minimum": 10, "maximum": 20},
                "average_billed_duration_ms": {"minimum": 15, "maximum": 25},
                "monthly_internet_egress_gb": {"minimum": 0, "maximum": 1},
                "monthly_cloudwatch_log_ingestion_gb": {"minimum": 0, "maximum": 1},
                "monthly_log_storage_gb_month": {"minimum": 0, "maximum": 1},
            }
        },
        "http_apis": {},
    }
    revised = service.revise_infrastructure_plan_constraints(
        founder(), original.infrastructure_plan_id,
        {"serverless_pricing_usage_assumptions": usage},
    )
    assert revised.content["user_constraints"]["serverless_pricing_usage_assumptions"] == usage
    assert revised.content["application_analysis"]["workload_spec"]["serverless_pricing_usage_assumptions"] == usage
    assert revised.content["revision_diff"]["serverless_pricing_usage_assumptions"] == {
        "before": None, "after": usage,
    }
    assert revised.content_digest == plan_hash(revised.content)

    cleared = service.revise_infrastructure_plan_constraints(
        founder(), original.infrastructure_plan_id,
        {"serverless_pricing_usage_assumptions": None},
    )
    assert "serverless_pricing_usage_assumptions" not in cleared.content["user_constraints"]
    assert "serverless_pricing_usage_assumptions" not in cleared.content["application_analysis"]["workload_spec"]


def test_customer_dynamodb_usage_assumptions_are_revision_bound_and_cleared():
    service, _ = make_service()
    original = draft(service)
    usage = {
        "tables": {
            "aws_dynamodb_table.records": {
                "monthly_read_request_units": {"minimum": 1_000, "maximum": 2_000},
                "monthly_write_request_units": {"minimum": 300, "maximum": 600},
                "monthly_storage_gb_month": {"minimum": 1, "maximum": 4},
                "monthly_pitr_storage_gb_month": {"minimum": 1, "maximum": 4},
            }
        }
    }

    revised = service.revise_infrastructure_plan_constraints(
        founder(),
        original.infrastructure_plan_id,
        {"dynamodb_pricing_usage_assumptions": usage},
    )

    assert original.revision_number == 1
    assert "dynamodb_pricing_usage_assumptions" not in original.content.get(
        "user_constraints", {}
    )
    assert revised.revision_number == 2
    assert revised.content["user_constraints"]["dynamodb_pricing_usage_assumptions"] == usage
    assert (
        revised.content["application_analysis"]["workload_spec"][
            "dynamodb_pricing_usage_assumptions"
        ]
        == usage
    )
    assert revised.content["revision_diff"]["dynamodb_pricing_usage_assumptions"] == {
        "before": None,
        "after": usage,
    }
    assert revised.content_digest == plan_hash(revised.content)

    cleared = service.revise_infrastructure_plan_constraints(
        founder(),
        original.infrastructure_plan_id,
        {"dynamodb_pricing_usage_assumptions": None},
    )

    assert cleared.revision_number == 3
    assert "dynamodb_pricing_usage_assumptions" not in cleared.content["user_constraints"]
    assert "dynamodb_pricing_usage_assumptions" not in cleared.content[
        "application_analysis"
    ]["workload_spec"]
    assert cleared.content["revision_diff"]["dynamodb_pricing_usage_assumptions"] == {
        "before": usage,
        "after": None,
    }
    assert cleared.content_digest == plan_hash(cleared.content)
    assert revised.content["user_constraints"]["dynamodb_pricing_usage_assumptions"] == usage
    assert revised.content_digest == plan_hash(revised.content)


def test_customer_vpc_usage_assumptions_are_revision_bound_and_cleared():
    service, _ = make_service()
    original = draft(service)
    usage = {
        "nat_gateways": {
            "aws_nat_gateway.nat": {
                "monthly_available_hours": {"minimum": 700, "maximum": 744},
                "monthly_data_processed_gb": {"minimum": 100, "maximum": 300},
                "monthly_internet_egress_gb": {"minimum": 20, "maximum": 100},
                "monthly_cross_az_payload_gb": {"minimum": 10, "maximum": 50},
            }
        }
    }
    revised = service.revise_infrastructure_plan_constraints(
        founder(), original.infrastructure_plan_id, {"vpc_pricing_usage_assumptions": usage}
    )
    assert original.revision_number == 1
    assert revised.revision_number == 2
    assert revised.content["user_constraints"]["vpc_pricing_usage_assumptions"] == usage
    assert revised.content["application_analysis"]["workload_spec"][
        "vpc_pricing_usage_assumptions"
    ] == usage
    assert revised.content["revision_diff"]["vpc_pricing_usage_assumptions"] == {
        "before": None, "after": usage,
    }
    assert revised.content_digest == plan_hash(revised.content)

    cleared = service.revise_infrastructure_plan_constraints(
        founder(), original.infrastructure_plan_id,
        {"vpc_pricing_usage_assumptions": None},
    )
    assert cleared.revision_number == 3
    assert "vpc_pricing_usage_assumptions" not in cleared.content["user_constraints"]
    assert "vpc_pricing_usage_assumptions" not in cleared.content[
        "application_analysis"
    ]["workload_spec"]
    assert cleared.content["revision_diff"]["vpc_pricing_usage_assumptions"] == {
        "before": usage, "after": None,
    }
    assert cleared.content_digest == plan_hash(cleared.content)


def test_customer_batch_usage_assumptions_are_revision_bound_and_cleared():
    service, _ = make_service()
    original = draft(service)
    usage = {
        "jobs": {"aws_batch_job_definition.jobs": {
            "monthly_jobs": {"minimum": 10, "maximum": 100},
            "average_billed_runtime_seconds": {"minimum": 60, "maximum": 900},
            "cloudwatch_logs": {
                "monthly_ingested_gb": {"minimum": 1, "maximum": 4},
                "monthly_retained_gb_month": {"minimum": 2, "maximum": 8},
            },
        }}
    }
    revised = service.revise_infrastructure_plan_constraints(
        founder(), original.infrastructure_plan_id,
        {"batch_pricing_usage_assumptions": usage},
    )
    assert revised.revision_number == 2
    assert revised.content["user_constraints"]["batch_pricing_usage_assumptions"] == usage
    assert revised.content["application_analysis"]["workload_spec"][
        "batch_pricing_usage_assumptions"
    ] == usage
    assert revised.content["revision_diff"]["batch_pricing_usage_assumptions"] == {
        "before": None, "after": usage,
    }
    assert revised.content_digest == plan_hash(revised.content)

    cleared = service.revise_infrastructure_plan_constraints(
        founder(), original.infrastructure_plan_id,
        {"batch_pricing_usage_assumptions": None},
    )
    assert cleared.revision_number == 3
    assert "batch_pricing_usage_assumptions" not in cleared.content["user_constraints"]
    assert "batch_pricing_usage_assumptions" not in cleared.content[
        "application_analysis"
    ]["workload_spec"]
    assert cleared.content["revision_diff"]["batch_pricing_usage_assumptions"] == {
        "before": usage, "after": None,
    }
    assert cleared.content_digest == plan_hash(cleared.content)


def test_customer_ecr_storage_assumptions_are_revision_bound_and_cleared():
    service, _ = make_service()
    original = draft(service)
    usage = {
        "repositories": {"aws_ecr_repository.images": {
            "monthly_stored_gb": {"minimum": 1, "maximum": 20},
        }}
    }
    revised = service.revise_infrastructure_plan_constraints(
        founder(), original.infrastructure_plan_id,
        {"ecr_pricing_usage_assumptions": usage},
    )
    assert revised.content["user_constraints"]["ecr_pricing_usage_assumptions"] == usage
    assert revised.content["application_analysis"]["workload_spec"][
        "ecr_pricing_usage_assumptions"
    ] == usage
    assert revised.content["revision_diff"]["ecr_pricing_usage_assumptions"] == {
        "before": None, "after": usage,
    }
    assert revised.content_digest == plan_hash(revised.content)

    cleared = service.revise_infrastructure_plan_constraints(
        founder(), original.infrastructure_plan_id,
        {"ecr_pricing_usage_assumptions": None},
    )
    assert "ecr_pricing_usage_assumptions" not in cleared.content["user_constraints"]
    assert "ecr_pricing_usage_assumptions" not in cleared.content[
        "application_analysis"
    ]["workload_spec"]
    assert cleared.content["revision_diff"]["ecr_pricing_usage_assumptions"] == {
        "before": usage, "after": None,
    }
    assert cleared.content_digest == plan_hash(cleared.content)


def test_customer_ecs_express_usage_assumptions_are_revision_bound_and_cleared():
    service, _ = make_service()
    original = draft(service)
    usage = {
        "service_address": "aws_ecs_express_gateway_service.workload[0]",
        "log_group_address": "aws_cloudwatch_log_group.workload",
        "monthly_task_starts": {"minimum": 1, "maximum": 100},
        "average_billed_task_runtime_seconds": {"minimum": 60, "maximum": 3600},
        "average_task_public_ipv4_address_seconds": {"minimum": 60, "maximum": 3600},
        "monthly_alb_billed_hours": {"minimum": 24, "maximum": 744},
        "monthly_alb_lcu_hours": {"minimum": 24, "maximum": 1000},
        "monthly_alb_public_ipv4_address_seconds": {
            "minimum": 172800, "maximum": 267840000,
        },
        "cloudwatch_logs": {
            "monthly_ingested_gb": {"minimum": 0, "maximum": 10},
            "monthly_retained_gb_month": {"minimum": 0, "maximum": 30},
        },
        "monthly_internet_egress_gb": {"minimum": 0, "maximum": 100},
        "monthly_cross_az_transfer_gb": {"minimum": 0, "maximum": 100},
    }
    revised = service.revise_infrastructure_plan_constraints(
        founder(), original.infrastructure_plan_id,
        {"ecs_express_pricing_usage_assumptions": usage},
    )
    assert revised.content["user_constraints"]["ecs_express_pricing_usage_assumptions"] == usage
    assert revised.content["application_analysis"]["workload_spec"][
        "ecs_express_pricing_usage_assumptions"
    ] == usage
    assert revised.content["revision_diff"]["ecs_express_pricing_usage_assumptions"] == {
        "before": None, "after": usage,
    }
    assert revised.content_digest == plan_hash(revised.content)

    cleared = service.revise_infrastructure_plan_constraints(
        founder(), original.infrastructure_plan_id,
        {"ecs_express_pricing_usage_assumptions": None},
    )
    assert "ecs_express_pricing_usage_assumptions" not in cleared.content["user_constraints"]
    assert "ecs_express_pricing_usage_assumptions" not in cleared.content[
        "application_analysis"
    ]["workload_spec"]
    assert cleared.content["revision_diff"]["ecs_express_pricing_usage_assumptions"] == {
        "before": usage, "after": None,
    }
    assert cleared.content_digest == plan_hash(cleared.content)


def test_submitted_revision_cannot_be_regenerated_from_constraint_edits():
    service, _ = make_service()
    revision = draft(service)
    service.submit_infrastructure_plan(founder(), revision.id)

    try:
        service.revise_infrastructure_plan_constraints(
            founder(),
            revision.infrastructure_plan_id,
            {"monthly_budget_usd": 250},
        )
    except ValueError as error:
        assert "draft or rejected" in str(error)
    else:
        raise AssertionError("submitted plan accepted a constraint revision")


def test_submitted_content_cannot_be_silently_changed_or_decided_twice():
    service, _ = make_service()
    revision = draft(service)
    revision.content["target"]["region"] = "eu-west-1"
    try:
        service.submit_infrastructure_plan(founder(), revision.id)
    except ValueError as error:
        assert "integrity" in str(error)
    else:
        raise AssertionError("tampered draft was submitted")

    plan = service._infrastructure_plan(founder(), revision.infrastructure_plan_id)
    revision = service.create_infrastructure_plan(
        founder(), plan.project_id, "Private API revision", plan_content()
    )
    service.submit_infrastructure_plan(founder(), revision.id)
    service.decide_infrastructure_plan(
        operator(), revision.id, InfrastructurePlanDecision.APPROVED, revision.content_digest
    )
    try:
        service.decide_infrastructure_plan(
            operator(), revision.id, InfrastructurePlanDecision.APPROVED, revision.content_digest
        )
    except ValueError as error:
        assert "submitted" in str(error)
    else:
        raise AssertionError("duplicate decision was accepted")


def test_infrastructure_revision_is_tenant_scoped():
    service, _ = make_service()
    revision = draft(service)
    other = Principal("user-other", "org-other", "developer")
    try:
        service.submit_infrastructure_plan(other, revision.id)
    except PermissionError:
        pass
    else:
        raise AssertionError("cross-tenant plan submission was accepted")
