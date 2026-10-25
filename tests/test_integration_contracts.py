from __future__ import annotations

import json

import pytest
from davdeploy.execution_profiles import execution_profile
from davdeploy.integrations import (
    FixtureAwsDiscovery,
    FixtureGitHubConnection,
    GitHubAppReadOnlyConnection,
    PublicGitHubRepositoryReader,
    configured_github_connection,
)


def test_github_fixture_models_reviewed_desired_state_and_webhook_contracts():
    github = FixtureGitHubConnection()
    pull_request = github.publish_reviewed_desired_state(
        "installation-1", "example/api", "desired/state.yaml", "safe fixture content"
    )
    assert pull_request.status == "SIMULATED"
    assert pull_request.required_checks == ("davdeploy-plan", "davdeploy-policy")
    webhook = github.validate_webhook("push", "delivery-1", "fixture-sha256=valid")
    assert webhook.verification == "SIMULATED_VALID"


def test_live_github_adapter_parses_repository_and_refuses_writes():
    connection = GitHubAppReadOnlyConnection("123", "456", "/private/key.pem")
    assert (
        connection._repository_name("https://github.com/example/service.git") == "example/service"
    )
    with pytest.raises(PermissionError, match="disabled"):
        connection.publish_reviewed_desired_state(
            "456",
            "example/service",
            "davdeploy/package.json",
            json.dumps({"approved_digest": "a" * 64, "branch": "main", "files": []}),
        )
    try:
        connection.publish_desired_state("456", "example/service", "state.yaml", "content")
    except PermissionError as error:
        assert "disabled" in str(error)
    else:
        raise AssertionError("read-only GitHub App adapter allowed a write")


def test_configured_github_connection_reads_private_key_from_secret(monkeypatch):
    class SecretsManager:
        def get_secret_value(self, *, SecretId):
            assert SecretId == "arn:aws:secretsmanager:us-east-1:123456789012:secret:davdeploy/github-app"
            return {"SecretString": json.dumps({"private-key.pem": "private-key"})}

    monkeypatch.setenv("DAVDEPLOY_GITHUB_APP_READ_ONLY", "true")
    monkeypatch.setenv("DAVDEPLOY_GITHUB_APP_ID", "5159790")
    monkeypatch.setenv("DAVDEPLOY_GITHUB_APP_INSTALLATION_ID", "167128937")
    monkeypatch.setenv(
        "DAVDEPLOY_GITHUB_APP_CREDENTIAL_SECRET_ARN",
        "arn:aws:secretsmanager:us-east-1:123456789012:secret:davdeploy/github-app",
    )
    monkeypatch.delenv("DAVDEPLOY_GITHUB_APP_PRIVATE_KEY_PATH", raising=False)
    monkeypatch.setattr("davdeploy.integrations.boto3.client", lambda service: SecretsManager())

    connection = configured_github_connection()

    assert isinstance(connection, GitHubAppReadOnlyConnection)
    assert connection.private_key_path is None
    assert connection._private_key == "private-key"


def test_configured_github_connection_rejects_ambiguous_private_key_sources(monkeypatch):
    monkeypatch.setenv("DAVDEPLOY_GITHUB_APP_READ_ONLY", "true")
    monkeypatch.setenv("DAVDEPLOY_GITHUB_APP_ID", "5159790")
    monkeypatch.setenv("DAVDEPLOY_GITHUB_APP_INSTALLATION_ID", "167128937")
    monkeypatch.setenv("DAVDEPLOY_GITHUB_APP_PRIVATE_KEY_PATH", "/private/key.pem")
    monkeypatch.setenv("DAVDEPLOY_GITHUB_APP_CREDENTIAL_SECRET_ARN", "arn:example")

    with pytest.raises(RuntimeError, match="either"):
        configured_github_connection()


def test_public_github_reader_accepts_only_canonical_public_repositories(monkeypatch):
    calls: list[tuple[str, dict]] = []

    class Response:
        status_code = 200
        text = '{"name":"davdeploy"}'

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        return Response(
            {
                "private": False,
                "full_name": "Bepoadewale/ai-platform-control-plane",
                "default_branch": "main",
            }
        )

    monkeypatch.setattr("davdeploy.integrations.httpx.get", fake_get)
    reader = PublicGitHubRepositoryReader()
    metadata = reader.inspect_repository("https://github.com/Bepoadewale/ai-platform-control-plane")

    assert metadata.provider == "github_public"
    assert metadata.repository == "Bepoadewale/ai-platform-control-plane"
    assert "Authorization" not in calls[0][1]["headers"]
    with pytest.raises(ValueError, match="canonical"):
        reader.inspect_repository("https://example.com/Bepoadewale/ai-platform-control-plane")


def test_public_github_reader_rejects_private_repository_metadata(monkeypatch):
    class Response:
        status_code = 200

        def json(self):
            return {
                "private": True,
                "full_name": "Bepoadewale/private-repository",
                "default_branch": "main",
            }

        def raise_for_status(self):
            return None

    monkeypatch.setattr("davdeploy.integrations.httpx.get", lambda *args, **kwargs: Response())
    with pytest.raises(PermissionError, match="not publicly readable"):
        PublicGitHubRepositoryReader().inspect_repository(
            "https://github.com/Bepoadewale/private-repository"
        )


def test_live_github_adapter_publishes_reviewed_pr_when_explicitly_enabled(monkeypatch):
    calls: list[tuple[str, str, dict | None]] = []

    class Response:
        def __init__(self, payload: dict, status_code: int = 200):
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise AssertionError(f"unexpected HTTP {self.status_code}")

    def fake_get(url, **kwargs):
        calls.append(("GET", url, kwargs.get("json")))
        if url.endswith("/git/ref/heads/main"):
            return Response({"object": {"sha": "base-sha"}})
        if "/git/ref/heads/davdeploy/desired-state-" in url:
            return Response({"object": {"sha": "head-sha"}})
        raise AssertionError(f"unexpected GET {url}")

    def fake_post(url, **kwargs):
        calls.append(("POST", url, kwargs.get("json")))
        if url.endswith("/git/refs"):
            return Response({"ref": kwargs["json"]["ref"]}, 201)
        if url.endswith("/pulls"):
            return Response({"html_url": "https://github.com/example/service/pull/7"}, 201)
        if url.endswith("/statuses/head-sha"):
            return Response({"state": kwargs["json"]["state"]}, 201)
        raise AssertionError(f"unexpected POST {url}")

    def fake_put(url, **kwargs):
        calls.append(("PUT", url, kwargs.get("json")))
        assert kwargs["json"]["branch"].startswith("davdeploy/desired-state-")
        return Response({"content": {"path": url.rsplit("/", 1)[-1]}}, 201)

    connection = GitHubAppReadOnlyConnection("123", "456", "/private/key.pem")
    monkeypatch.setenv("DAVDEPLOY_GITHUB_APP_WRITES_ENABLED", "true")
    monkeypatch.setattr(connection, "_installation_token", lambda: "installation-token")
    monkeypatch.setattr("davdeploy.integrations.httpx.get", fake_get)
    monkeypatch.setattr("davdeploy.integrations.httpx.post", fake_post)
    monkeypatch.setattr("davdeploy.integrations.httpx.put", fake_put)
    digest = "b" * 64
    pull_request = connection.publish_reviewed_desired_state(
        "456",
        "https://github.com/example/service",
        "davdeploy/package.json",
        json.dumps(
            {
                "approved_digest": digest,
                "branch": "main",
                "files": [
                    {
                        "path": "davdeploy/approved-plan.json",
                        "content": {"digest": digest},
                    }
                ],
            }
        ),
    )

    assert pull_request.status == "EXECUTED_GITHUB_PR_CREATED"
    assert pull_request.pull_request_url == "https://github.com/example/service/pull/7"
    assert pull_request.required_checks == ("davdeploy/desired-state-review",)
    assert any(call[0] == "POST" and call[1].endswith("/pulls") for call in calls)
    assert any(call[0] == "POST" and call[1].endswith("/statuses/head-sha") for call in calls)
    assert not any(call[1].endswith("/merge") for call in calls)


def test_aws_fixture_byoc_contract_never_returns_credentials():
    aws = FixtureAwsDiscovery()
    contract = aws.role_contract("connection-123")
    session = aws.assume_scoped_role(contract, "local-product-token")
    assert contract.audience == "davdeploy-byoc"
    assert session.session_reference.startswith("fixture-sts-session:")
    assert "no AWS access key" in session.credential_boundary


def test_execution_profiles_keep_kubernetes_specific_to_the_approved_profile():
    app_runner = execution_profile("aws-app-runner")
    eks = execution_profile("aws-eks-governed")
    assert app_runner.kubernetes_boundary == "not used"
    assert eks.delivery_kind == "kubernetes"
    assert "GitOps" in eks.gitops_boundary
