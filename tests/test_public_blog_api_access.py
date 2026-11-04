from __future__ import annotations

from davdeploy.db import make_engine, run_migrations
from davdeploy.main import app, product_service
from davdeploy.policy import PolicyClient
from davdeploy.security import LOCAL_USERS, Principal
from davdeploy.service import ProductService
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from test_product import LocalExecutor
from test_public_blog import blog_payload


def test_public_blog_reads_are_anonymous_and_authoring_routes_require_sign_in(tmp_path):
    engine = make_engine(f"sqlite+pysqlite:///{tmp_path / 'blog-api.db'}")
    run_migrations(engine)
    db = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    service = ProductService(
        db,
        policy=PolicyClient(fixture=True),
        executor=LocalExecutor(),
    )
    service.seed_local_identity()
    author = Principal(
        "verified-team-writer",
        LOCAL_USERS["founder"][1],
        "developer",
        email="writer@davdeploy.tech",
        email_verified=True,
    )
    published = service.create_blog_post(author, blog_payload())
    reader = Principal("blog-reader", LOCAL_USERS["founder"][1], "developer")
    comment = service.create_blog_comment(
        reader, published["slug"], "A public comment for route coverage."
    )
    app.dependency_overrides[product_service] = lambda: service
    try:
        with TestClient(app) as client:
            post_list = client.get("/api/v1/blog/posts")
            post_detail = client.get(f"/api/v1/blog/posts/{published['slug']}")
            comments = client.get(f"/api/v1/blog/posts/{published['slug']}/comments")

            assert post_list.status_code == 200
            assert [item["slug"] for item in post_list.json()] == [published["slug"]]
            assert post_detail.status_code == 200
            assert post_detail.json()["id"] == published["id"]
            assert comments.status_code == 200
            assert [item["id"] for item in comments.json()] == [comment["id"]]

            anonymous_writes = [
                client.post(
                    f"/api/v1/blog/posts/{published['slug']}/comments",
                    json={"body": "Anonymous write must be rejected."},
                ),
                client.patch(
                    f"/api/v1/blog/comments/{comment['id']}",
                    json={"body": "Anonymous edit must be rejected."},
                ),
                client.get("/api/v1/blog/team/posts"),
                client.post(
                    "/api/v1/blog/team/posts",
                    json=blog_payload(slug="anonymous-must-not-publish"),
                ),
                client.patch(
                    f"/api/v1/blog/team/posts/{published['id']}",
                    json=blog_payload(title="Anonymous edit must be rejected."),
                ),
                client.get("/api/v1/blog/author-access"),
            ]
            # FastAPI reports a missing required Authorization header as 422;
            # the routes remain inaccessible without a bearer token.
            assert [response.status_code for response in anonymous_writes] == [422] * 6
    finally:
        app.dependency_overrides.pop(product_service, None)
