"""Narrow production integration contracts; local V1 does not hold cloud credentials."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

import boto3
import httpx
import jwt
from botocore.exceptions import BotoCoreError, ClientError

from davdeploy.domain import CloudInventorySnapshot


@dataclass(frozen=True)
class RepositoryMetadata:
    provider: str
    installation_id: str
    repository: str
    default_branch: str


@dataclass(frozen=True)
class RepositoryAnalysis:
    provider: str
    repository: str
    selected_branch: str
    default_branch: str
    manifests: tuple[str, ...]
    runtime_hints: tuple[str, ...]
    framework_hints: tuple[str, ...]
    database_hints: tuple[str, ...]
    secret_hints: tuple[str, ...]
    deployment_hints: tuple[str, ...]
    confidence: float
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class GitHubInstallation:
    id: str
    account_login: str
    account_type: str


@dataclass(frozen=True)
class GitHubRepository:
    full_name: str
    html_url: str
    default_branch: str


@dataclass(frozen=True)
class GitHubWebhookContract:
    event: str
    delivery_id: str
    installation_id: str
    repository: str
    verification: str


def verify_github_webhook_signature(secret: str, body: bytes, signature: str) -> bool:
    """Verify GitHub's X-Hub-Signature-256 value without logging the secret or body."""
    if not secret or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@dataclass(frozen=True)
class DesiredStatePullRequest:
    pull_request_url: str
    branch: str
    required_checks: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class AwsRoleContract:
    provider: str
    role_arn: str
    audience: str
    session_duration_minutes: int
    credential_boundary: str


@dataclass(frozen=True)
class AssumedRoleSession:
    session_reference: str
    expires_at: datetime
    credential_boundary: str


class GitHubConnection(Protocol):
    def installations(self) -> list[GitHubInstallation]: ...

    def repositories(self, installation_id: str) -> list[GitHubRepository]: ...

    def branches(self, installation_id: str, repository: str) -> list[str]: ...

    def inspect_repository(
        self, installation_id: str, repository: str, ref: str | None = None
    ) -> RepositoryMetadata: ...

    def analyze_repository(
        self, installation_id: str, repository: str, ref: str | None = None
    ) -> RepositoryAnalysis: ...

    def publish_desired_state(
        self, installation_id: str, repository: str, path: str, content: str
    ) -> str: ...

    def publish_reviewed_desired_state(
        self, installation_id: str, repository: str, path: str, content: str
    ) -> DesiredStatePullRequest: ...

    def validate_webhook(
        self, event: str, delivery_id: str, signature: str
    ) -> GitHubWebhookContract: ...


class PublicGitHubRepositoryReader:
    """Bounded, unauthenticated reader for repositories GitHub exposes as public."""

    api_url = "https://api.github.com"
    execution = "EXECUTED_PUBLIC_READ_ONLY"
    _manifest_candidates = (
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
        "requirements.txt",
        "pyproject.toml",
        "package.json",
        "pnpm-lock.yaml",
        "yarn.lock",
        "go.mod",
        "Cargo.toml",
        ".github/workflows",
        "k8s",
        "kubernetes",
        "helm",
        "charts",
        "terraform",
    )

    @staticmethod
    def repository_name(repository_url: str) -> str:
        parsed = urlparse(repository_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "github.com"
            or parsed.port is not None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("public repository must use a canonical https://github.com URL")
        candidate = parsed.path.strip("/").removesuffix(".git")
        parts = candidate.split("/")
        if len(parts) != 2 or not all(parts):
            raise ValueError("public repository URL must identify one owner and repository")
        return candidate

    @staticmethod
    def _headers(accept: str = "application/vnd.github+json") -> dict[str, str]:
        return {
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "davdeploy-public-repository-reader",
        }

    def inspect_repository(self, repository_url: str) -> RepositoryMetadata:
        name = self.repository_name(repository_url)
        response = httpx.get(f"{self.api_url}/repos/{name}", headers=self._headers(), timeout=10)
        response.raise_for_status()
        payload = response.json()
        if payload.get("private") is not False:
            raise PermissionError("repository is not publicly readable")
        if payload.get("full_name", "").lower() != name.lower():
            raise ValueError("GitHub returned unexpected repository metadata")
        return RepositoryMetadata(
            provider="github_public",
            installation_id="public-read-only",
            repository=str(payload["full_name"]),
            default_branch=str(payload["default_branch"]),
        )

    def branches(self, repository_url: str) -> list[str]:
        metadata = self.inspect_repository(repository_url)
        response = httpx.get(
            f"{self.api_url}/repos/{metadata.repository}/branches",
            headers=self._headers(),
            params={"per_page": 100},
            timeout=10,
        )
        response.raise_for_status()
        return [str(item["name"]) for item in response.json()]

    def analyze_repository(self, repository_url: str, ref: str | None = None) -> RepositoryAnalysis:
        metadata = self.inspect_repository(repository_url)
        selected = ref or metadata.default_branch
        manifests = self._manifest_files(metadata.repository, selected)
        return RepositoryAnalysis(
            provider=metadata.provider,
            repository=metadata.repository,
            selected_branch=selected,
            default_branch=metadata.default_branch,
            manifests=tuple(manifests),
            runtime_hints=tuple(GitHubAppReadOnlyConnection._runtime_hints(manifests)),
            framework_hints=tuple(GitHubAppReadOnlyConnection._framework_hints(manifests)),
            database_hints=tuple(GitHubAppReadOnlyConnection._database_hints(manifests)),
            secret_hints=tuple(GitHubAppReadOnlyConnection._secret_hints(manifests)),
            deployment_hints=tuple(GitHubAppReadOnlyConnection._deployment_hints(manifests)),
            confidence=0.82 if manifests else 0.5,
            limitations=(
                "Public analysis reads repository metadata and selected manifest files only.",
                "Source code, secrets, issue data, and repository writes are excluded.",
            ),
        )

    def _manifest_files(self, repository: str, ref: str) -> dict[str, str]:
        found: dict[str, str] = {}
        for path in self._manifest_candidates:
            response = httpx.get(
                f"{self.api_url}/repos/{repository}/contents/{path}",
                headers=self._headers("application/vnd.github.raw+json"),
                params={"ref": ref},
                timeout=10,
            )
            if response.status_code == 404:
                continue
            response.raise_for_status()
            found[path] = response.text[:20_000]
        return found


class AwsCloudConnection(Protocol):
    """Future adapter: assumes a customer-scoped role with short-lived STS credentials."""

    def discover(self, connection_id: str) -> dict: ...

    def estimate_catalog_version(self, region: str) -> str: ...

    def role_contract(self, connection_id: str) -> AwsRoleContract: ...

    def assume_scoped_role(
        self, contract: AwsRoleContract, subject_token: str
    ) -> AssumedRoleSession: ...


class CloudDiscovery(Protocol):
    def inventory(self, connection_id: str, region: str) -> CloudInventorySnapshot: ...


class SlackNotifier(Protocol):
    def notify(self, channel: str, text: str) -> None: ...


class FixtureGitHubConnection:
    """Local deterministic fixture; it cannot reach GitHub or write a repository."""

    execution = "SIMULATED"

    def installations(self) -> list[GitHubInstallation]:
        return [GitHubInstallation("fixture-installation", "demo-ai-startup", "Organization")]

    def repositories(self, installation_id: str) -> list[GitHubRepository]:
        if installation_id != "fixture-installation":
            raise PermissionError("GitHub installation is not available to this workspace")
        return [
            GitHubRepository(
                "example/support-rag-api", "https://github.com/example/support-rag-api", "main"
            ),
            GitHubRepository(
                "example/fastapi-ai-api", "https://github.com/example/fastapi-ai-api", "main"
            ),
        ]

    def branches(self, installation_id: str, repository: str) -> list[str]:
        if installation_id != "fixture-installation":
            raise PermissionError("GitHub installation is not available to this workspace")
        self._repository_name(repository)
        return ["main", "staging"]

    @staticmethod
    def _repository_name(repository: str) -> str:
        parsed = urlparse(repository)
        candidate = parsed.path.strip("/") if parsed.scheme else repository.strip("/")
        candidate = candidate.removesuffix(".git")
        if len(candidate.split("/")) != 2:
            raise ValueError("repository must be an owner/name GitHub repository")
        return candidate

    def inspect_repository(
        self, installation_id: str, repository: str, ref: str | None = None
    ) -> RepositoryMetadata:
        del ref
        return RepositoryMetadata("fixture", installation_id, repository, "main")

    def analyze_repository(
        self, installation_id: str, repository: str, ref: str | None = None
    ) -> RepositoryAnalysis:
        metadata = self.inspect_repository(installation_id, repository, ref)
        selected = ref or metadata.default_branch
        normalized = self._repository_name(repository)
        if "support-rag-api" in normalized or "fastapi" in normalized:
            return RepositoryAnalysis(
                provider="fixture",
                repository=normalized,
                selected_branch=selected,
                default_branch=metadata.default_branch,
                manifests=("Dockerfile", "requirements.txt", "pyproject.toml"),
                runtime_hints=("python", "containerized"),
                framework_hints=("fastapi",),
                database_hints=("postgresql",),
                secret_hints=("environment variables",),
                deployment_hints=("container image",),
                confidence=0.9,
                limitations=("Fixture analysis reads deterministic manifest hints only.",),
            )
        return RepositoryAnalysis(
            provider="fixture",
            repository=normalized,
            selected_branch=selected,
            default_branch=metadata.default_branch,
            manifests=(),
            runtime_hints=("unknown",),
            framework_hints=(),
            database_hints=(),
            secret_hints=(),
            deployment_hints=(),
            confidence=0.45,
            limitations=("No known fixture manifests were available for this repository.",),
        )

    def publish_desired_state(
        self, installation_id: str, repository: str, path: str, content: str
    ) -> str:
        return f"fixture-pr://{installation_id}/{repository}/{path}"

    def publish_reviewed_desired_state(
        self, installation_id: str, repository: str, path: str, content: str
    ) -> DesiredStatePullRequest:
        return DesiredStatePullRequest(
            pull_request_url=self.publish_desired_state(installation_id, repository, path, content),
            branch=f"davdeploy/desired-state-{installation_id}",
            required_checks=("davdeploy-plan", "davdeploy-policy"),
            status="SIMULATED",
        )

    def validate_webhook(
        self, event: str, delivery_id: str, signature: str
    ) -> GitHubWebhookContract:
        if not signature.startswith("fixture-sha256="):
            raise ValueError("fixture webhook signature is invalid")
        return GitHubWebhookContract(
            event=event,
            delivery_id=delivery_id,
            installation_id="fixture-installation",
            repository="example/support-rag-api",
            verification="SIMULATED_VALID",
        )


class GitHubAppReadOnlyConnection:
    """Live GitHub App reader. It never exposes or persists installation tokens."""

    api_url = "https://api.github.com"
    execution = "EXECUTED_READ_ONLY"

    def __init__(
        self,
        app_id: str,
        installation_id: str,
        private_key_path: str | None = None,
        *,
        private_key: str | None = None,
    ):
        if not private_key_path and not private_key:
            raise ValueError("GitHub App private key material is required")
        self.app_id = app_id
        self.installation_id = installation_id
        self.private_key_path = Path(private_key_path) if private_key_path else None
        self._private_key = private_key

    def _app_jwt(self) -> str:
        now = datetime.now(UTC)
        return jwt.encode(
            {
                "iat": now - timedelta(seconds=30),
                "exp": now + timedelta(minutes=9),
                "iss": self.app_id,
            },
            self._private_key
            or (self.private_key_path.read_text() if self.private_key_path else ""),
            algorithm="RS256",
        )

    def _installation_token(self) -> str:
        response = httpx.post(
            f"{self.api_url}/app/installations/{self.installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {self._app_jwt()}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=10,
        )
        response.raise_for_status()
        return str(response.json()["token"])

    def installations(self) -> list[GitHubInstallation]:
        # This product connection deliberately exposes only its configured installation.
        return [GitHubInstallation(self.installation_id, "configured-github-app", "Installation")]

    def repositories(self, installation_id: str) -> list[GitHubRepository]:
        if installation_id != self.installation_id:
            raise PermissionError("GitHub installation is not configured for this connection")
        response = httpx.get(
            f"{self.api_url}/installation/repositories",
            headers={
                "Authorization": f"Bearer {self._installation_token()}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=10,
        )
        response.raise_for_status()
        return [
            GitHubRepository(item["full_name"], item["html_url"], item["default_branch"])
            for item in response.json().get("repositories", [])
        ]

    def branches(self, installation_id: str, repository: str) -> list[str]:
        if installation_id != self.installation_id:
            raise PermissionError("GitHub installation is not configured for this connection")
        name = self._repository_name(repository)
        response = httpx.get(
            f"{self.api_url}/repos/{name}/branches",
            headers={
                "Authorization": f"Bearer {self._installation_token()}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            params={"per_page": 100},
            timeout=10,
        )
        response.raise_for_status()
        return [str(item["name"]) for item in response.json()]

    @staticmethod
    def _repository_name(repository: str) -> str:
        parsed = urlparse(repository)
        candidate = parsed.path.strip("/") if parsed.scheme else repository.strip("/")
        candidate = candidate.removesuffix(".git")
        if len(candidate.split("/")) != 2:
            raise ValueError("repository must be an owner/name GitHub repository")
        return candidate

    def inspect_repository(
        self, installation_id: str, repository: str, ref: str | None = None
    ) -> RepositoryMetadata:
        del ref
        if installation_id != self.installation_id:
            raise PermissionError("GitHub installation is not configured for this connection")
        name = self._repository_name(repository)
        response = httpx.get(
            f"{self.api_url}/repos/{name}",
            headers={
                "Authorization": f"Bearer {self._installation_token()}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        return RepositoryMetadata(
            "github_app", self.installation_id, name, payload["default_branch"]
        )

    def analyze_repository(
        self, installation_id: str, repository: str, ref: str | None = None
    ) -> RepositoryAnalysis:
        metadata = self.inspect_repository(installation_id, repository, ref)
        selected = ref or metadata.default_branch
        manifests = self._manifest_files(metadata.repository, selected)
        return RepositoryAnalysis(
            provider="github_app",
            repository=metadata.repository,
            selected_branch=selected,
            default_branch=metadata.default_branch,
            manifests=tuple(manifests),
            runtime_hints=tuple(self._runtime_hints(manifests)),
            framework_hints=tuple(self._framework_hints(manifests)),
            database_hints=tuple(self._database_hints(manifests)),
            secret_hints=tuple(self._secret_hints(manifests)),
            deployment_hints=tuple(self._deployment_hints(manifests)),
            confidence=0.82 if manifests else 0.5,
            limitations=(
                "Live analysis reads repository metadata and selected manifest files only.",
                "Source code, secrets, issue data and unauthorized repositories are not read.",
            ),
        )

    def _manifest_files(self, repository: str, ref: str) -> dict[str, str]:
        candidates = (
            "Dockerfile",
            "docker-compose.yml",
            "docker-compose.yaml",
            "compose.yml",
            "compose.yaml",
            "requirements.txt",
            "pyproject.toml",
            "package.json",
            "pnpm-lock.yaml",
            "yarn.lock",
            "go.mod",
            "Cargo.toml",
            ".github/workflows",
            "k8s",
            "kubernetes",
            "helm",
            "charts",
            "terraform",
        )
        headers = {
            "Authorization": f"Bearer {self._installation_token()}",
            "Accept": "application/vnd.github.raw+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        found: dict[str, str] = {}
        for path in candidates:
            response = httpx.get(
                f"{self.api_url}/repos/{repository}/contents/{path}",
                headers=headers,
                params={"ref": ref},
                timeout=10,
            )
            if response.status_code == 404:
                continue
            response.raise_for_status()
            text = response.text if len(response.text) < 20_000 else response.text[:20_000]
            found[path] = text
        return found

    @staticmethod
    def _runtime_hints(manifests: dict[str, str]) -> list[str]:
        joined = "\n".join(manifests.values()).lower()
        hints: list[str] = []
        if "python" in joined or "requirements.txt" in manifests or "pyproject.toml" in manifests:
            hints.append("python")
        if "node" in joined or "package.json" in manifests:
            hints.append("node")
        if "Dockerfile" in manifests:
            hints.append("containerized")
        return hints or ["unknown"]

    @staticmethod
    def _framework_hints(manifests: dict[str, str]) -> list[str]:
        joined = "\n".join(manifests.values()).lower()
        frameworks = []
        for name in ("fastapi", "django", "flask", "next", "express", "react"):
            if name in joined:
                frameworks.append(name)
        return frameworks

    @staticmethod
    def _database_hints(manifests: dict[str, str]) -> list[str]:
        joined = "\n".join(manifests.values()).lower()
        hints = []
        for name in ("postgres", "postgresql", "mysql", "redis", "sqlite", "mongodb"):
            if name in joined:
                hints.append("postgresql" if name == "postgres" else name)
        return sorted(set(hints))

    @staticmethod
    def _secret_hints(manifests: dict[str, str]) -> list[str]:
        joined = "\n".join(manifests.values()).lower()
        hints = []
        if (
            ".env" in joined
            or "secret" in joined
            or "api_key" in joined
            or "database_url" in joined
        ):
            hints.append("environment variables")
        return hints

    @staticmethod
    def _deployment_hints(manifests: dict[str, str]) -> list[str]:
        hints = []
        if "Dockerfile" in manifests:
            hints.append("container image")
        if any(path.startswith(".github/workflows") for path in manifests):
            hints.append("github actions")
        if any(path in manifests for path in ("k8s", "kubernetes", "helm", "charts")):
            hints.append("kubernetes manifests")
        if "terraform" in manifests:
            hints.append("terraform")
        return hints

    def publish_desired_state(
        self, installation_id: str, repository: str, path: str, content: str
    ) -> str:
        return self.publish_reviewed_desired_state(
            installation_id, repository, path, content
        ).pull_request_url

    def publish_reviewed_desired_state(
        self, installation_id: str, repository: str, path: str, content: str
    ) -> DesiredStatePullRequest:
        if os.getenv("DAVDEPLOY_GITHUB_APP_WRITES_ENABLED", "false").lower() != "true":
            raise PermissionError(
                "live GitHub App desired-state writes are disabled; set "
                "DAVDEPLOY_GITHUB_APP_WRITES_ENABLED=true after review"
            )
        if installation_id != self.installation_id:
            raise PermissionError("GitHub installation is not configured for this connection")
        package = self._desired_state_package(path, content)
        repository_name = self._repository_name(repository)
        base_branch = str(package.get("branch") or "main")
        digest = str(package.get("approved_digest") or hashlib.sha256(content.encode()).hexdigest())
        branch = f"davdeploy/desired-state-{digest[:12]}"
        token = self._installation_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        base_ref = httpx.get(
            f"{self.api_url}/repos/{repository_name}/git/ref/heads/{base_branch}",
            headers=headers,
            timeout=10,
        )
        base_ref.raise_for_status()
        base_sha = str(base_ref.json()["object"]["sha"])
        create_ref = httpx.post(
            f"{self.api_url}/repos/{repository_name}/git/refs",
            headers=headers,
            json={"ref": f"refs/heads/{branch}", "sha": base_sha},
            timeout=10,
        )
        if create_ref.status_code not in {201, 422}:
            create_ref.raise_for_status()
        for file in self._desired_state_files(package, path, content):
            put = httpx.put(
                f"{self.api_url}/repos/{repository_name}/contents/{file['path']}",
                headers=headers,
                json={
                    "message": f"Add davdeploy desired state for {digest[:12]}",
                    "content": file["content"],
                    "branch": branch,
                },
                timeout=10,
            )
            put.raise_for_status()
        head_ref = httpx.get(
            f"{self.api_url}/repos/{repository_name}/git/ref/heads/{branch}",
            headers=headers,
            timeout=10,
        )
        head_ref.raise_for_status()
        head_sha = str(head_ref.json()["object"]["sha"])
        pr = httpx.post(
            f"{self.api_url}/repos/{repository_name}/pulls",
            headers=headers,
            json={
                "title": f"davdeploy desired state for approved plan {digest[:12]}",
                "head": branch,
                "base": base_branch,
                "body": (
                    "davdeploy generated this desired-state package from an approved "
                    f"plan digest `{digest}`.\n\n"
                    "Human review is required. davdeploy will not merge this pull request."
                ),
                "maintainer_can_modify": False,
            },
            timeout=10,
        )
        pr.raise_for_status()
        pr_payload = pr.json()
        status = httpx.post(
            f"{self.api_url}/repos/{repository_name}/statuses/{head_sha}",
            headers=headers,
            json={
                "state": "pending",
                "target_url": pr_payload.get("html_url"),
                "description": "Review davdeploy desired state before execution.",
                "context": "davdeploy/desired-state-review",
            },
            timeout=10,
        )
        status.raise_for_status()
        return DesiredStatePullRequest(
            pull_request_url=str(pr_payload["html_url"]),
            branch=branch,
            required_checks=("davdeploy/desired-state-review",),
            status="EXECUTED_GITHUB_PR_CREATED",
        )

    @staticmethod
    def _desired_state_package(path: str, content: str) -> dict:
        try:
            package = json.loads(content)
        except json.JSONDecodeError:
            return {
                "approved_digest": hashlib.sha256(content.encode()).hexdigest(),
                "branch": "main",
                "files": [{"path": path, "content": content}],
            }
        if not isinstance(package, dict):
            raise TypeError("desired-state package must be a JSON object")
        return package

    @staticmethod
    def _desired_state_files(
        package: dict, fallback_path: str, fallback_content: str
    ) -> list[dict[str, str]]:
        import base64

        files = package.get("files")
        rendered: list[dict[str, str]] = []
        if isinstance(files, list):
            for item in files:
                if not isinstance(item, dict) or not item.get("path"):
                    continue
                path = str(item["path"]).lstrip("/")
                if ".." in Path(path).parts:
                    raise ValueError("desired-state file path cannot contain parent traversal")
                content = item.get("content", "")
                if not isinstance(content, str):
                    content = json.dumps(content, indent=2, sort_keys=True) + "\n"
                rendered.append(
                    {
                        "path": path,
                        "content": base64.b64encode(content.encode()).decode(),
                    }
                )
        rendered.append(
            {
                "path": fallback_path.lstrip("/"),
                "content": base64.b64encode(
                    (json.dumps(package, indent=2, sort_keys=True) + "\n").encode()
                    if isinstance(package, dict)
                    else fallback_content.encode()
                ).decode(),
            }
        )
        return rendered

    def validate_webhook(
        self, event: str, delivery_id: str, signature: str
    ) -> GitHubWebhookContract:
        raise PermissionError("live webhook processing is not enabled in read-only mode")


def _github_app_private_key_from_secret(secret_arn: str) -> str:
    """Read one configured GitHub App key without logging or persisting it."""
    try:
        value = str(
            boto3.client("secretsmanager").get_secret_value(SecretId=secret_arn)[
                "SecretString"
            ]
        )
    except (BotoCoreError, ClientError, KeyError) as error:
        raise RuntimeError("configured GitHub App private key is unavailable") from error
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return value
    if isinstance(payload, dict) and isinstance(payload.get("private-key.pem"), str):
        return payload["private-key.pem"]
    raise RuntimeError("configured GitHub App secret does not contain private-key.pem")


def configured_github_connection() -> GitHubConnection:
    """Use live GitHub only after an explicit operator opt-in and complete key configuration."""
    enabled = os.getenv("DAVDEPLOY_GITHUB_APP_READ_ONLY", "false").lower() == "true"
    app_id = os.getenv("DAVDEPLOY_GITHUB_APP_ID")
    installation_id = os.getenv("DAVDEPLOY_GITHUB_APP_INSTALLATION_ID")
    key_path = os.getenv("DAVDEPLOY_GITHUB_APP_PRIVATE_KEY_PATH")
    key_secret_arn = os.getenv("DAVDEPLOY_GITHUB_APP_CREDENTIAL_SECRET_ARN")
    if not enabled:
        return FixtureGitHubConnection()
    if not all([app_id, installation_id]) or not (key_path or key_secret_arn):
        raise RuntimeError(
            "live GitHub App mode requires app ID, installation ID, and private-key configuration"
        )
    if key_path and key_secret_arn:
        raise RuntimeError("configure either a GitHub App private-key path or secret ARN, not both")
    if key_secret_arn:
        return GitHubAppReadOnlyConnection(
            app_id,
            installation_id,
            private_key=_github_app_private_key_from_secret(key_secret_arn),
        )
    assert key_path is not None
    if not Path(key_path).is_file():
        raise RuntimeError("configured GitHub App private key is unavailable")
    return GitHubAppReadOnlyConnection(app_id, installation_id, key_path)


class FixtureAwsDiscovery:
    """Deterministic local discovery. It holds no AWS credentials and makes no network calls."""

    def inventory(self, connection_id: str, region: str) -> CloudInventorySnapshot:
        return CloudInventorySnapshot(
            provider="aws",
            region=region,
            approved_resources=[],
            approved_regions=["us-east-1", "eu-west-1"],
            discovered_at=datetime.now(UTC),
            provenance=f"fixture:{connection_id}",
        )

    def role_contract(self, connection_id: str) -> AwsRoleContract:
        return AwsRoleContract(
            provider="aws",
            role_arn=f"arn:aws:iam::000000000000:role/davdeploy-{connection_id[:8]}",
            audience="davdeploy-byoc",
            session_duration_minutes=60,
            credential_boundary=(
                "Contract only: production uses customer-approved OIDC and STS. "
                "The local fixture returns no AWS credentials."
            ),
        )

    def assume_scoped_role(
        self, contract: AwsRoleContract, subject_token: str
    ) -> AssumedRoleSession:
        if not subject_token:
            raise ValueError("an davdeploy identity token is required")
        return AssumedRoleSession(
            session_reference=f"fixture-sts-session:{contract.role_arn.rsplit('/', maxsplit=1)[-1]}",
            expires_at=datetime.now(UTC) + timedelta(minutes=contract.session_duration_minutes),
            credential_boundary=(
                "Simulated session reference only; no AWS access key, secret, session token, "
                "or live role assumption exists."
            ),
        )


class StsAwsDiscovery:
    """Server-side, short-lived discovery for an already-approved customer role.

    The browser never receives the assumed-role credentials. The process identity must
    already be the configured davdeploy control-plane identity.
    """

    def __init__(self, session: object | None = None):
        self.session = session or boto3.Session()

    def verify(
        self, connection_id: str, role_arn: str, external_id: str, region: str
    ) -> CloudInventorySnapshot:
        sts = self.session.client("sts", region_name=region)
        assumed = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName=f"davdeploy-discovery-{connection_id[:8]}",
            ExternalId=external_id,
            DurationSeconds=900,
        )["Credentials"]
        customer = boto3.Session(
            aws_access_key_id=assumed["AccessKeyId"],
            aws_secret_access_key=assumed["SecretAccessKey"],
            aws_session_token=assumed["SessionToken"],
            region_name=region,
        )
        account = customer.client("sts").get_caller_identity()["Account"]
        resources = [f"aws-account:{account}"]
        resources.extend(self._inventory(customer, region))
        pricing_evidence = self._pricing_evidence(customer, region)
        return CloudInventorySnapshot(
            provider="aws",
            region=region,
            approved_resources=resources,
            approved_regions=[region],
            discovered_at=datetime.now(UTC),
            provenance="live-read-only-sts-discovery",
            pricing_evidence=pricing_evidence,
        )

    @staticmethod
    def _pricing_evidence(customer: object, region: str) -> dict[str, object]:
        """Collect bounded pricing evidence without reading workload data.

        Cost Explorer is customer-account evidence. The AWS Pricing API is a
        public catalog lookup that may be unavailable to a tightly scoped role,
        so failures are retained as limitations rather than silently replaced
        with fixture pricing.
        """
        captured_at = datetime.now(UTC)
        evidence: dict[str, object] = {
            "kind": "aws_pricing_evidence.v1",
            "captured_at": captured_at.isoformat(),
            "region": region,
            "catalog": {"state": "NOT_QUERIED"},
            "cost_explorer": {"state": "NOT_QUERIED"},
            "limitations": [],
        }
        try:
            catalog = customer.client("pricing", region_name="us-east-1")
            response = catalog.get_products(
                ServiceCode="AmazonEC2",
                Filters=[
                    {"Type": "TERM_MATCH", "Field": "location", "Value": "US East (N. Virginia)"},
                    {"Type": "TERM_MATCH", "Field": "instanceType", "Value": "t4g.small"},
                    {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
                    {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
                ],
                MaxResults=1,
            )
            evidence["catalog"] = {
                "state": "EXECUTED",
                "service_code": "AmazonEC2",
                "query": "t4g.small Linux shared in US East (N. Virginia)",
                "product_count": len(response.get("PriceList", [])),
                "catalog_version": captured_at.date().isoformat(),
            }
        except (BotoCoreError, ClientError) as error:
            evidence["catalog"] = {"state": "UNAVAILABLE", "reason": type(error).__name__}
            cast_limitations = evidence["limitations"]
            assert isinstance(cast_limitations, list)
            cast_limitations.append("AWS Pricing catalog was unavailable to the customer discovery role.")
        try:
            end = captured_at.date()
            start = end - timedelta(days=1)
            response = customer.client("ce", region_name="us-east-1").get_cost_and_usage(
                TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
                Granularity="DAILY",
                Metrics=["UnblendedCost"],
            )
            amounts = [
                group.get("Total", {}).get("UnblendedCost", {}).get("Amount", "0")
                for group in response.get("ResultsByTime", [])
            ]
            evidence["cost_explorer"] = {
                "state": "EXECUTED",
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "daily_unblended_cost_usd": amounts,
            }
        except (BotoCoreError, ClientError) as error:
            evidence["cost_explorer"] = {"state": "UNAVAILABLE", "reason": type(error).__name__}
            cast_limitations = evidence["limitations"]
            assert isinstance(cast_limitations, list)
            cast_limitations.append("AWS Cost Explorer was unavailable to the customer discovery role.")
        return evidence

    @staticmethod
    def _inventory(customer: object, region: str) -> list[str]:
        """Collect only counts and identifiers needed by the planner; never workload data."""
        discovered: list[str] = []
        checks = (
            (
                "vpc",
                lambda: customer.client("ec2", region_name=region).describe_vpcs().get("Vpcs", []),
            ),
            (
                "ecr",
                lambda: (
                    customer.client("ecr", region_name=region)
                    .describe_repositories()
                    .get("repositories", [])
                ),
            ),
            (
                "eks",
                lambda: (
                    customer.client("eks", region_name=region).list_clusters().get("clusters", [])
                ),
            ),
            (
                "ecs",
                lambda: (
                    customer.client("ecs", region_name=region)
                    .list_clusters()
                    .get("clusterArns", [])
                ),
            ),
            (
                "rds",
                lambda: (
                    customer.client("rds", region_name=region)
                    .describe_db_instances()
                    .get("DBInstances", [])
                ),
            ),
            (
                "lambda",
                lambda: (
                    customer.client("lambda", region_name=region)
                    .list_functions()
                    .get("Functions", [])
                ),
            ),
            (
                "app-runner",
                lambda: (
                    customer.client("apprunner", region_name=region)
                    .list_services()
                    .get("ServiceSummaryList", [])
                ),
            ),
        )
        for name, query in checks:
            try:
                discovered.append(f"{name}:{len(query())}")
            except (BotoCoreError, ClientError) as error:  # Customer policy may omit a service.
                discovered.append(f"{name}:unavailable:{type(error).__name__}")
        try:
            buckets = customer.client("s3", region_name=region).list_buckets().get("Buckets", [])
            discovered.append(f"s3:{len(buckets)}")
        except (BotoCoreError, ClientError) as error:
            discovered.append(f"s3:unavailable:{type(error).__name__}")
        return discovered
