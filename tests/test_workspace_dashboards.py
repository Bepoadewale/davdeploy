from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from davdeploy.domain import InfrastructurePlanDecision, InfrastructurePlanState
from davdeploy.main import list_customer_plan_revisions
from davdeploy.security import LOCAL_USERS, Principal, issue_local_token, verify_token
from test_infrastructure_plan_lifecycle import plan_content
from test_product import founder, make_service


def administrator() -> Principal:
    subject, organization_id, role = LOCAL_USERS["administrator"]
    return Principal(subject, organization_id, role)


def submitted_plan(service):
    project = service.create_project(founder(), "dashboard-api", "https://github.com/example/dashboard")
    revision = service.create_infrastructure_plan(founder(), project.id, "Dashboard API", plan_content())
    return service.submit_infrastructure_plan(founder(), revision.id)


def test_administrator_local_token_is_accepted_as_a_distinct_product_role():
    principal = verify_token(f"Bearer {issue_local_token('administrator')}")
    assert principal.role == "administrator"
    assert principal.subject != founder().subject


def test_developer_dashboard_shows_only_own_customer_plan_revisions():
    service, _ = make_service()
    revision = submitted_plan(service)
    dashboard = service.workspace_dashboard(founder())
    assert dashboard["user"]["role"] == "developer"
    assert dashboard["pending_approval_count"] == 0
    assert [item["id"] for item in dashboard["plans"]] == [revision.id]


def test_customer_plan_revision_history_paginates_visible_summaries():
    service, _ = make_service()
    project = service.create_project(
        founder(), "revision-history", "https://github.com/example/history"
    )
    own = [
        service.create_infrastructure_plan(
            founder(), project.id, f"Plan {index}", plan_content()
        )
        for index in range(3)
    ]
    collaborator = Principal("workspace-member", founder().organization_id, "developer")
    other = service.create_infrastructure_plan(
        collaborator, project.id, "Member plan", plan_content()
    )
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for index, revision in enumerate([*own, other]):
        revision.created_at = base + timedelta(minutes=index)
    service.db.commit()

    first = service.customer_plan_revision_history(founder(), project.id, limit=2)
    second = service.customer_plan_revision_history(
        founder(), project.id, limit=2, cursor=first["next_cursor"]
    )
    admin = Principal("workspace-admin", founder().organization_id, "administrator")
    all_revisions = service.customer_plan_revision_history(admin, project.id, limit=10)

    assert [item["id"] for item in first["items"]] == [own[2].id, own[1].id]
    assert first["next_cursor"] == own[1].id
    assert [item["id"] for item in second["items"]] == [own[0].id]
    assert second["next_cursor"] is None
    assert {item["id"] for item in all_revisions["items"]} == {
        revision.id for revision in [*own, other]
    }
    assert set(first["items"][0]) == {
        "id",
        "plan_id",
        "project_id",
        "title",
        "revision",
        "state",
        "content_digest",
        "created_at",
        "submitted_at",
    }
    assert "creator_subject" not in first["items"][0]
    assert "content" not in first["items"][0]


def test_customer_plan_revision_history_rejects_invisible_cursors_and_bad_limits():
    service, _ = make_service()
    project = service.create_project(
        founder(), "revision-history", "https://github.com/example/history"
    )
    own = service.create_infrastructure_plan(founder(), project.id, "Own", plan_content())
    collaborator = Principal("workspace-member", founder().organization_id, "developer")
    hidden = service.create_infrastructure_plan(
        collaborator, project.id, "Hidden", plan_content()
    )
    other_project = service.create_project(
        founder(), "other-project", "https://github.com/example/other"
    )
    foreign_project_revision = service.create_infrastructure_plan(
        founder(), other_project.id, "Other project", plan_content()
    )

    with pytest.raises(PermissionError, match="cursor is not visible"):
        service.customer_plan_revision_history(founder(), project.id, cursor=hidden.id)
    with pytest.raises(PermissionError, match="cursor is not visible"):
        service.customer_plan_revision_history(
            founder(), project.id, cursor=foreign_project_revision.id
        )
    with pytest.raises(ValueError, match="cursor is invalid"):
        service.customer_plan_revision_history(founder(), project.id, cursor="not-a-uuid")
    with pytest.raises(ValueError, match="page size"):
        service.customer_plan_revision_history(founder(), project.id, limit=101)
    with pytest.raises(PermissionError, match="project not found"):
        service.customer_plan_revision_history(
            Principal("foreign-user", "foreign-organization", "developer"),
            project.id,
        )
    assert service.customer_plan_revision_history(founder(), project.id)["items"][0]["id"] == own.id


def test_customer_plan_revision_history_route_returns_the_service_contract():
    service, _ = make_service()
    project = service.create_project(
        founder(), "revision-history", "https://github.com/example/history"
    )
    revision = service.create_infrastructure_plan(
        founder(), project.id, "Customer plan", plan_content()
    )

    result = list_customer_plan_revisions(
        project.id, limit=10, cursor=None, principal=founder(), service=service
    )

    assert result["project_id"] == project.id
    assert result["items"][0]["id"] == revision.id
    assert "content" not in result["items"][0]




def test_administrator_dashboard_and_pending_queue_are_workspace_scoped():
    service, _ = make_service()
    revision = submitted_plan(service)
    dashboard = service.workspace_dashboard(administrator())
    assert dashboard["user"]["role"] == "administrator"
    assert dashboard["pending_approval_count"] == 1
    pending = service.pending_infrastructure_plan_revisions(administrator())
    assert pending[0]["id"] == revision.id
    assert pending[0]["state"] == InfrastructurePlanState.SUBMITTED
    assert pending[0]["repository"] == "https://github.com/example/service"
    assert pending[0]["policy_result"] == "APPROVAL_REQUIRED"
    assert pending[0]["not_deployed"] is True
    assert revision.state == InfrastructurePlanState.SUBMITTED


def test_administrator_review_queue_filters_decisions_and_self_approval():
    service, _ = make_service()
    submitted = submitted_plan(service)
    approved = service.decide_infrastructure_plan(
        administrator(),
        submitted.id,
        InfrastructurePlanDecision.APPROVED,
        submitted.content_digest,
    )
    project = service.create_project(
        administrator(), "admin-owned-review", "https://github.com/example/admin"
    )
    own = service.create_infrastructure_plan(
        administrator(), project.id, "Admin-owned API", plan_content()
    )
    service.submit_infrastructure_plan(administrator(), own.id)
    service.decide_infrastructure_plan(
        administrator(), own.id, InfrastructurePlanDecision.APPROVED, own.content_digest
    )

    approved_items = service.admin_infrastructure_plan_revisions(
        administrator(), InfrastructurePlanState.APPROVED
    )
    assert {item["id"] for item in approved_items} == {approved.id, own.id}
    self_approved = service.admin_infrastructure_plan_revisions(administrator(), "SELF_APPROVED")
    assert [item["id"] for item in self_approved] == [own.id]


def test_plan_detail_contains_admin_review_evidence_and_audit_export():
    service, _ = make_service()
    submitted = submitted_plan(service)
    detail = service.infrastructure_plan_revision_detail(administrator(), submitted.id)
    summary = detail["review_summary"]
    assert summary["requester"] == founder().subject
    assert summary["repository"] == "https://github.com/example/service"
    assert summary["region"] == "us-east-1"
    assert summary["policy_result"] == "APPROVAL_REQUIRED"
    assert summary["execution_boundary"].startswith("Approval records")

    service.decide_infrastructure_plan(
        administrator(),
        submitted.id,
        InfrastructurePlanDecision.REJECTED,
        submitted.content_digest,
        "Need a narrower budget.",
    )
    evidence = service.audit_evidence(administrator(), submitted.id)
    rejected = next(item for item in evidence if item["action"] == "infrastructure_plan.rejected")
    assert rejected["label"] == "Plan rejected"
    assert rejected["actor_role"] == "administrator"
    assert rejected["plan_digest"] == submitted.content_digest
    assert rejected["decision_reason"] == "Need a narrower budget."
    assert rejected["export_ready"] is True


def test_developer_cannot_read_administrator_pending_queue():
    service, _ = make_service()
    submitted_plan(service)
    try:
        service.pending_infrastructure_plan_revisions(founder())
    except PermissionError as error:
        assert "administrator" in str(error)
    else:
        raise AssertionError("developer received the administrator queue")
