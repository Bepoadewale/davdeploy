from __future__ import annotations

import pytest
from davdeploy.security import LOCAL_USERS, Principal
from test_product import make_service


def principal(name: str, *, email: str | None = None, email_verified: bool = False) -> Principal:
    subject, organization_id, role = LOCAL_USERS[name]
    return Principal(subject, organization_id, role, email=email, email_verified=email_verified)


def blog_payload(**overrides: str) -> dict[str, str]:
    return {
        "slug": "building-clearer-cloud-decisions",
        "title": "Building clearer cloud decisions",
        "summary": "How evidence and review can make cloud choices easier to understand.",
        "body": "A practical note about making cloud infrastructure choices with clear trade-offs.",
        "state": "PUBLISHED",
        **overrides,
    }


def test_only_verified_davdeploy_team_email_can_create_public_blog_posts():
    service, _ = make_service()
    founder = principal("founder", email="founder@davdeploy.tech", email_verified=True)

    post = service.create_blog_post(founder, blog_payload())

    assert post["state"] == "PUBLISHED"
    assert service.public_blog_posts()[0]["slug"] == post["slug"]
    with pytest.raises(PermissionError, match="team publishing"):
        service.create_blog_post(
            principal("administrator", email="customer@example.com", email_verified=True),
            blog_payload(slug="not-allowed"),
        )
    with pytest.raises(PermissionError, match="team publishing"):
        service.create_blog_post(
            principal("administrator", email="writer@davdeploy.tech", email_verified=False),
            blog_payload(slug="unverified-team-email"),
        )


def test_signed_in_reader_can_edit_only_own_public_comment():
    service, _ = make_service()
    founder = principal("founder", email="founder@davdeploy.tech", email_verified=True)
    service.create_blog_post(founder, blog_payload())

    comment = service.create_blog_comment(
        principal("administrator"), "building-clearer-cloud-decisions", "Useful perspective.")
    edited = service.update_blog_comment(principal("administrator"), comment["id"], "Very useful.")

    assert edited["body"] == "Very useful."
    assert service.blog_comments("building-clearer-cloud-decisions")[0]["author_name"] == "DavDeploy reader"
    with pytest.raises(PermissionError, match="comment author"):
        service.update_blog_comment(founder, comment["id"], "Changed by someone else.")


def test_only_a_post_author_can_edit_that_post():
    service, _ = make_service()
    founder = principal("founder", email="founder@davdeploy.tech", email_verified=True)
    other_team_member = principal(
        "administrator", email="writer@davdeploy.tech", email_verified=True
    )
    post = service.create_blog_post(founder, blog_payload())

    with pytest.raises(PermissionError, match="post author"):
        service.update_blog_post(other_team_member, post["id"], blog_payload())
