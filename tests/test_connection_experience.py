from __future__ import annotations

import json

from davdeploy.db import make_engine, run_migrations
from davdeploy.integrations import RepositoryAnalysis, RepositoryMetadata
from davdeploy.main import app, product_service, verify_token
from davdeploy.models import GitHubWebhookDelivery
from davdeploy.policy import PolicyClient
from davdeploy.security import LOCAL_USERS, Principal
from davdeploy.service import ProductService
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from test_product import LocalExecutor, founder, make_service


def other_tenant() -> Principal:
    subject, organization_id, role = LOCAL_USERS["other-tenant"]
    return Principal(subject, organization_id, role)


def test_administrator_pilot_quick_create_requires_explicit_acknowledgement():
    class QuickCreateService:
        def aws_quick_create_setup(self, *_args):
            raise AssertionError("service must not be called without acknowledgement")

    app.dependency_overrides[product_service] = lambda: QuickCreateService()
    app.dependency_overrides[verify_token] = founder
    try:
        response = TestClient(app).post(
            "/api/v1/cloud-connections/connection-1/aws-quick-create",
            json={"account_id": "123456789012", "access_mode": "administrator-pilot"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {
        "detail": "acknowledge administrator access before enabling the deployment pilot"
    }


def test_fixture_github_connection_lists_only_authorized_repositories_and_branches():
    service, _ = make_service()
    status = service.github_connection_status(founder())
    assert status["execution"] == "SIMULATED"
    assert status["writes_enabled"] is False
    installation_id = status["installations"][0]["id"]
    repositories = service.github_repositories(founder(), installation_id)
    assert repositories[0]["full_name"] == "example/support-rag-api"
    branches = service.github_branches(founder(), installation_id, repositories[0]["full_name"])
    assert branches == ["main", "staging"]


def test_project_persists_selected_repository_branch_for_safe_read_only_discovery():
    service, _ = make_service()
    project = service.create_project(
        founder(),
        "branch-selection",
        "https://github.com/example/support-rag-api",
        "staging",
    )
    discovered = service.repository_discovery(founder(), project.id)
    assert discovered["selected_branch"] == "staging"
    assert discovered["execution"] == "SIMULATED"
    assert discovered["analysis"]["framework_hints"] == ["fastapi"]
    assert "Dockerfile" in discovered["analysis"]["manifests"]


def test_seeded_example_repository_stays_on_the_deterministic_fixture():
    service, _ = make_service()
    project = service.create_project(
        founder(),
        "seeded-example",
        "https://github.com/example/demo-draft-plan",
        "main",
    )

    discovered = service.repository_discovery(founder(), project.id)

    assert discovered["execution"] == "SIMULATED"
    assert discovered["analysis"]["repository"] == "example/demo-draft-plan"


def test_repository_analysis_is_persisted_and_feeds_intent_spec():
    service, _ = make_service()
    project = service.create_project(
        founder(),
        "repo-analysis",
        "https://github.com/example/support-rag-api",
        "main",
    )
    service.repository_discovery(founder(), project.id)
    intent = service.create_intent(
        founder(),
        project.id,
        "Deploy this AI API in AWS. Keep customer data private. Support 20 requests per second and peak at 100 requests per second. Keep monthly infrastructure under $500. Create staging and production. Enable monitoring.",
        project.repository_url,
        None,
        "repo-analysis-001",
    )

    analysis = intent.spec["repository_analysis"]
    assert analysis["repository"] == "example/support-rag-api"
    assert analysis["selected_branch"] == "main"
    assert intent.spec["runtime"] == "python-fastapi"
    assert intent.spec["stateful"] is True


def test_public_repository_discovery_uses_real_read_only_evidence():
    class PublicReader:
        execution = "EXECUTED_PUBLIC_READ_ONLY"

        def inspect_repository(self, repository_url):
            assert repository_url == "https://github.com/Bepoadewale/ai-platform-control-plane"
            return RepositoryMetadata(
                "github_public",
                "public-read-only",
                "Bepoadewale/ai-platform-control-plane",
                "main",
            )

        def branches(self, repository_url):
            self.inspect_repository(repository_url)
            return ["main"]

        def analyze_repository(self, repository_url, ref=None):
            self.inspect_repository(repository_url)
            return RepositoryAnalysis(
                provider="github_public",
                repository="Bepoadewale/ai-platform-control-plane",
                selected_branch=ref or "main",
                default_branch="main",
                manifests=("pyproject.toml", "Dockerfile"),
                runtime_hints=("python", "containerized"),
                framework_hints=("fastapi",),
                database_hints=("postgresql",),
                secret_hints=("environment variables",),
                deployment_hints=("container image",),
                confidence=0.82,
                limitations=("Public read-only evidence.",),
            )

    service, _ = make_service()
    service.public_github = PublicReader()
    project = service.create_project(
        founder(),
        "public-repository",
        "https://github.com/Bepoadewale/ai-platform-control-plane",
        "main",
    )
    discovered = service.repository_discovery(founder(), project.id)

    assert discovered["execution"] == "EXECUTED_PUBLIC_READ_ONLY"
    assert discovered["analysis"]["repository"] == "Bepoadewale/ai-platform-control-plane"
    assert discovered["analysis"]["manifests"] == ["pyproject.toml", "Dockerfile"]


def test_aws_connection_detail_and_disconnect_are_tenant_scoped_and_credential_free():
    service, _ = make_service()
    connection = service.create_cloud_connection(
        founder(), "Customer account", "aws", "byoc_role_contract"
    )
    detail = service.cloud_connection_detail(founder(), connection.id)
    assert detail["credentials_stored"] is False
    assert detail["deployment_permission"] == "not granted"
    try:
        service.cloud_connection_detail(other_tenant(), connection.id)
    except PermissionError:
        pass
    else:
        raise AssertionError("other tenant read an AWS connection")
    service.disconnect_cloud_connection(founder(), connection.id)
    assert service.cloud_connections(founder()) == []


def signed_fixture_webhook(service, event: str, delivery_id: str, payload: dict):
    return service.receive_github_webhook(
        event=event,
        delivery_id=delivery_id,
        signature="fixture-sha256=valid",
        body=json.dumps(payload).encode(),
    )


def test_github_webhook_installation_states_are_persisted_and_visible():
    service, _ = make_service()
    payload = {
        "action": "created",
        "installation": {
            "id": 5159790,
            "account": {"login": "Bepoadewale", "type": "User"},
            "repository_selection": "selected",
            "permissions": {"metadata": "read", "contents": "read"},
        },
        "davdeploy": {"organization_id": founder().organization_id},
    }

    processed = signed_fixture_webhook(service, "installation", "delivery-install", payload)

    assert processed["state"] == "CONNECTED"
    status = service.github_connection_status(founder())
    assert status["installation_states"][0]["installation_id"] == "5159790"
    assert status["installation_states"][0]["state"] == "CONNECTED"
    assert status["recent_webhook_deliveries"][0]["delivery_id"] == "delivery-install"


def test_github_webhook_duplicate_delivery_is_replay_protected():
    service, db = make_service()
    payload = {
        "action": "created",
        "installation": {"id": 5159790, "account": {"login": "Bepoadewale"}},
        "davdeploy": {"organization_id": founder().organization_id},
    }

    first = signed_fixture_webhook(service, "installation", "delivery-replay", payload)
    second = signed_fixture_webhook(service, "installation", "delivery-replay", payload)

    assert first["status"] == "PROCESSED"
    assert second["status"] == "DUPLICATE"
    assert db.query(GitHubWebhookDelivery).filter_by(delivery_id="delivery-replay").count() == 1


def test_github_webhook_records_revoked_repository_and_branch_states():
    service, _ = make_service()
    base = {
        "installation": {"id": 5159790, "account": {"login": "Bepoadewale"}},
        "repository": {"full_name": "Bepoadewale/ai-platform-control-plane"},
        "davdeploy": {"organization_id": founder().organization_id},
    }

    repo_change = signed_fixture_webhook(
        service,
        "installation_repositories",
        "delivery-repository-change",
        base | {"action": "removed"},
    )
    branch_change = signed_fixture_webhook(
        service, "push", "delivery-push", base | {"ref": "refs/heads/main"}
    )
    revoked = signed_fixture_webhook(
        service, "installation", "delivery-revoked", base | {"action": "deleted"}
    )

    assert repo_change["state"] == "REPOSITORY_ACCESS_CHANGED"
    assert branch_change["state"] == "BRANCH_UPDATED"
    assert revoked["state"] == "REVOKED"
    status = service.github_connection_status(founder())
    assert status["installation_states"][0]["state"] == "REVOKED"


def test_github_webhook_missing_permission_and_bad_signature_fail_closed():
    service, _ = make_service()
    payload = {
        "action": "created",
        "installation": {
            "id": 5159790,
            "account": {"login": "Bepoadewale"},
            "permissions": {"metadata": "none"},
        },
        "davdeploy": {"organization_id": founder().organization_id},
    }
    processed = signed_fixture_webhook(
        service, "installation", "delivery-missing-permission", payload
    )
    assert processed["state"] == "MISSING_PERMISSION"

    try:
        service.receive_github_webhook(
            event="installation",
            delivery_id="delivery-bad-signature",
            signature="fixture-sha256=bad",
            body=json.dumps(payload).encode(),
        )
    except PermissionError as error:
        assert "signature" in str(error)
    else:
        raise AssertionError("invalid GitHub webhook signature was accepted")


def test_github_webhook_endpoint_records_signed_fixture_delivery(tmp_path):
    engine = make_engine(f"sqlite+pysqlite:///{tmp_path / 'webhook.db'}")
    run_migrations(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    service = ProductService(db, policy=PolicyClient(fixture=True), executor=LocalExecutor())
    service.seed_local_identity()
    app.dependency_overrides[product_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/api/v1/github/webhooks",
            headers={
                "X-GitHub-Event": "installation",
                "X-GitHub-Delivery": "delivery-endpoint",
                "X-Hub-Signature-256": "fixture-sha256=valid",
            },
            json={
                "action": "created",
                "installation": {"id": 5159790, "account": {"login": "Bepoadewale"}},
                "davdeploy": {"organization_id": founder().organization_id},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "PROCESSED"
    assert (
        service.github_connection_status(founder())["installation_states"][0]["state"]
        == "CONNECTED"
    )


def test_github_webhook_endpoint_rejects_missing_delivery_metadata_and_oversized_payload(tmp_path):
    engine = make_engine(f"sqlite+pysqlite:///{tmp_path / 'webhook-boundary.db'}")
    run_migrations(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    service = ProductService(db, policy=PolicyClient(fixture=True), executor=LocalExecutor())
    service.seed_local_identity()
    app.dependency_overrides[product_service] = lambda: service
    try:
        missing_delivery = TestClient(app).post(
            "/api/v1/github/webhooks",
            headers={
                "X-GitHub-Event": "installation",
                "X-Hub-Signature-256": "fixture-sha256=valid",
            },
            json={"davdeploy": {"organization_id": founder().organization_id}},
        )
        oversized = TestClient(app).post(
            "/api/v1/github/webhooks",
            headers={
                "X-GitHub-Event": "installation",
                "X-GitHub-Delivery": "delivery-oversized",
                "X-Hub-Signature-256": "fixture-sha256=valid",
            },
            content=b"x" * 1_000_001,
        )
    finally:
        app.dependency_overrides.clear()

    assert missing_delivery.status_code == 409
    assert missing_delivery.json() == {"detail": "GitHub event and delivery ID are required"}
    assert oversized.status_code == 409
    assert oversized.json() == {"detail": "GitHub webhook payload is too large"}
