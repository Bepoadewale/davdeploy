from __future__ import annotations

import pytest
from davdeploy.security import LOCAL_USERS, Principal
from test_product import make_service


def principal(name: str) -> Principal:
    subject, organization_id, role = LOCAL_USERS[name]
    return Principal(subject, organization_id, role)


def blog_payload(**overrides: str) -> dict[str, str]:
    return {
        "slug": "building-clearer-cloud-decisions",
        "title": "Building clearer cloud decisions",
        "summary": "How evidence and review can make cloud choices easier to understand.",
        "body": "A practical note about making cloud infrastructure choices with clear trade-offs.",
        "state": "PUBLISHED",
        **overrides,
    }


def test_only_explicit_team_subjects_can_create_public_blog_posts(monkeypatch):
    service, _ = make_service()
    monkeypatch.setenv("DAVDEPLOY_BLOG_AUTHOR_SUBJECTS", "user-founder")

    post = service.create_blog_post(principal("founder"), blog_payload())

    assert post["state"] == "PUBLISHED"
    assert service.public_blog_posts()[0]["slug"] == post["slug"]
    with pytest.raises(PermissionError, match="team publishing"):
        service.create_blog_post(principal("administrator"), blog_payload(slug="not-allowed"))


def test_signed_in_reader_can_edit_only_own_public_comment(monkeypatch):
    service, _ = make_service()
    monkeypatch.setenv("DAVDEPLOY_BLOG_AUTHOR_SUBJECTS", "user-founder")
    service.create_blog_post(principal("founder"), blog_payload())

    comment = service.create_blog_comment(
        principal("administrator"), "building-clearer-cloud-decisions", "Useful perspective.")
    edited = service.update_blog_comment(principal("administrator"), comment["id"], "Very useful.")

    assert edited["body"] == "Very useful."
    assert service.blog_comments("building-clearer-cloud-decisions")[0]["author_name"] == "DavDeploy reader"
    with pytest.raises(PermissionError, match="comment author"):
        service.update_blog_comment(principal("founder"), comment["id"], "Changed by someone else.")


def test_only_a_post_author_can_edit_that_post(monkeypatch):
    service, _ = make_service()
    monkeypatch.setenv("DAVDEPLOY_BLOG_AUTHOR_SUBJECTS", "user-founder,user-administrator")
    post = service.create_blog_post(principal("founder"), blog_payload())

    with pytest.raises(PermissionError, match="post author"):
        service.update_blog_post(principal("administrator"), post["id"], blog_payload())
