"""Create isolated, backend-free Terraform plans for typed Nova proposals."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from davdeploy.generated_deployment_contract import (
    GeneratedDeploymentProposal,
    terraform_resource_blocks,
)
from davdeploy.generated_plan_inspection import (
    TerraformPlanInspectionError,
    TerraformPlanSummary,
    inspect_terraform_plan,
)
from davdeploy.generated_plan_ownership import (
    PlanOwnershipError,
    PlanOwnershipScope,
    inject_trusted_ownership_tags,
)
from davdeploy.generated_plan_policy import (
    GeneratedPlanPolicyResult,
    evaluate_generated_plan_policy,
)
from davdeploy.generated_provider_validation import (
    GeneratedProviderSchemaError,
    validate_generated_proposal,
)

PINNED_TERRAFORM_VERSION = "1.14.7"
PINNED_AWS_PROVIDER_VERSION = "5.100.0"


class TerraformPlanExecutionError(RuntimeError):
    """A generated proposal could not safely produce a Terraform saved plan."""


@dataclass(frozen=True)
class GeneratedTerraformPlan:
    summary: TerraformPlanSummary
    policy: GeneratedPlanPolicyResult
    target_account_id: str
    region: str
    terraform_version: str
    aws_provider_version: str
    provider_lockfile_sha256: str
    proposal_sha256: str
    context_sha256: str
    configuration_sha256: str
    ownership_scope_sha256: str
    ownership_plan_id_sha256: str
    saved_plan_sha256: str
    saved_plan_path: str


class GeneratedTerraformPlanRunner:
    """Run only fixed Terraform validation and plan commands.

    The runner has no apply or destroy method. It requires an exact pinned CLI
    and provider lockfile, verifies the active AWS account, and writes all
    files into a caller-owned private workspace.
    """

    def __init__(
        self,
        *,
        provider_lockfile: str | Path,
        expected_terraform_version: str,
        expected_aws_provider_version: str,
        terraform_binary: str = "terraform",
        command_timeout_seconds: int = 300,
        identity_provider: Callable[[], str] | None = None,
    ):
        if not re.fullmatch(r"\d+\.\d+\.\d+", expected_terraform_version):
            raise ValueError("expected Terraform version must be an exact semantic version")
        if not re.fullmatch(r"\d+\.\d+\.\d+", expected_aws_provider_version):
            raise ValueError("expected AWS provider version must be an exact semantic version")
        if command_timeout_seconds < 1 or command_timeout_seconds > 1_800:
            raise ValueError("Terraform command timeout must be between 1 and 1800 seconds")
        self.provider_lockfile = Path(provider_lockfile)
        self.expected_terraform_version = expected_terraform_version
        self.expected_aws_provider_version = expected_aws_provider_version
        self.terraform_binary = terraform_binary
        self.command_timeout_seconds = command_timeout_seconds
        self.identity_provider = identity_provider or self._aws_account_id

    def plan(
        self,
        proposal: GeneratedDeploymentProposal,
        *,
        expected_account_id: str,
        region: str,
        ownership_scope: PlanOwnershipScope,
        workspace: str | Path,
        aws_credentials: dict[str, str] | None = None,
    ) -> GeneratedTerraformPlan:
        """Validate and plan; never apply, destroy, or return resource values."""
        if not isinstance(ownership_scope, PlanOwnershipScope):
            raise TerraformPlanExecutionError("trusted plan ownership scope is required")
        if not re.fullmatch(r"\d{12}", expected_account_id):
            raise TerraformPlanExecutionError("trusted AWS account ID is invalid")
        if not re.fullmatch(r"[a-z]{2}(?:-[a-z0-9]+)+-\d", region):
            raise TerraformPlanExecutionError("trusted AWS region is invalid")
        if proposal.requirements.region != region:
            raise TerraformPlanExecutionError("proposal region does not match trusted region")
        if any(key.startswith("AWS_ENDPOINT_URL") for key in os.environ):
            raise TerraformPlanExecutionError("custom AWS endpoints are not allowed for planning")

        actual_account_id = self.identity_provider()
        if actual_account_id != expected_account_id:
            raise TerraformPlanExecutionError("active AWS identity does not match trusted account")

        lockfile_bytes = self._read_lockfile()
        lockfile_version = self._provider_version(lockfile_bytes.decode("utf-8"))
        if lockfile_version != self.expected_aws_provider_version:
            raise TerraformPlanExecutionError("AWS provider lockfile version does not match pin")
        lockfile_digest = hashlib.sha256(lockfile_bytes).hexdigest()
        proposal_bytes = json.dumps(
            proposal.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

        working_root = self._secure_workspace(Path(workspace))
        plan_path = working_root / "saved.tfplan"
        if plan_path.exists() or plan_path.is_symlink():
            raise TerraformPlanExecutionError("saved plan path already exists")

        config = self._trusted_configuration(
            proposal, region, expected_account_id, self.expected_terraform_version
        )
        terraform_environment = self._terraform_environment(aws_credentials)
        config_bytes = json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self._write_private(working_root / "main.tf.json", config_bytes)
        self._write_private(working_root / ".terraform.lock.hcl", lockfile_bytes)

        version_output = self._run(
            ["version", "-json"], working_root, env=terraform_environment
        )
        try:
            installed_version = json.loads(version_output.stdout)["terraform_version"]
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            raise TerraformPlanExecutionError("Terraform did not report a valid version") from error
        if installed_version != self.expected_terraform_version:
            raise TerraformPlanExecutionError("Terraform CLI version does not match trusted pin")

        self._run(
            ["init", "-backend=false", "-input=false", "-lockfile=readonly", "-no-color"],
            working_root,
            env=terraform_environment,
        )
        schema_output = self._run(
            ["providers", "schema", "-json"], working_root, env=terraform_environment
        )
        try:
            schema = json.loads(schema_output.stdout)
            validate_generated_proposal(proposal, schema)
            inject_trusted_ownership_tags(config, schema, ownership_scope)
        except (json.JSONDecodeError, GeneratedProviderSchemaError, PlanOwnershipError) as error:
            raise TerraformPlanExecutionError(
                "proposal failed pinned AWS provider schema validation or ownership validation"
            ) from error

        config_bytes = json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self._rewrite_private(working_root / "main.tf.json", config_bytes)
        config_digest = hashlib.sha256(config_bytes).hexdigest()

        self._run(["validate", "-no-color"], working_root, env=terraform_environment)
        self._run(
            [
                "plan",
                "-input=false",
                "-lock=false",
                "-no-color",
                f"-out={plan_path}",
            ],
            working_root,
            allowed_exit_codes=frozenset({0, 2}),
            env=terraform_environment,
        )
        if not plan_path.is_file() or plan_path.is_symlink():
            raise TerraformPlanExecutionError("Terraform did not produce a saved plan")
        os.chmod(plan_path, stat.S_IRUSR | stat.S_IWUSR)
        plan_size = plan_path.stat().st_size
        if plan_size <= 0 or plan_size > 128 * 1024 * 1024:
            raise TerraformPlanExecutionError("saved Terraform plan is empty or exceeds size limit")
        plan_bytes = plan_path.read_bytes()

        with tempfile.TemporaryFile(mode="w+b") as json_output:
            self._run(
                ["show", "-json", str(plan_path)],
                working_root,
                stdout_file=json_output,
                env=terraform_environment,
            )
            json_output.seek(0, os.SEEK_END)
            if json_output.tell() > 32 * 1024 * 1024:
                raise TerraformPlanExecutionError("Terraform JSON plan exceeds size limit")
            json_output.seek(0)
            try:
                document = json.loads(json_output.read())
                summary = inspect_terraform_plan(document)
            except (json.JSONDecodeError, TerraformPlanInspectionError, RecursionError) as error:
                raise TerraformPlanExecutionError("Terraform JSON plan could not be safely inspected") from error
        if summary.errored or (not summary.applyable and summary.create_count + summary.update_count + summary.delete_count + summary.replacement_count > 0):
            raise TerraformPlanExecutionError("Terraform produced an errored or non-applyable plan")
        policy = evaluate_generated_plan_policy(
            document,
            proposal,
            expected_account_id=expected_account_id,
            expected_region=region,
            ownership_scope=ownership_scope,
            trusted_configuration=config,
        )

        return GeneratedTerraformPlan(
            summary=summary,
            policy=policy,
            target_account_id=expected_account_id,
            region=region,
            terraform_version=installed_version,
            aws_provider_version=lockfile_version,
            provider_lockfile_sha256=lockfile_digest,
            proposal_sha256=hashlib.sha256(proposal_bytes).hexdigest(),
            context_sha256=proposal.context_digest,
            configuration_sha256=config_digest,
            ownership_scope_sha256=ownership_scope.scope_sha256(),
            ownership_plan_id_sha256=ownership_scope.plan_id_sha256(),
            saved_plan_sha256=hashlib.sha256(plan_bytes).hexdigest(),
            saved_plan_path=str(plan_path),
        )

    def _run(
        self,
        args: list[str],
        working_root: Path,
        *,
        allowed_exit_codes: frozenset[int] = frozenset({0}),
        stdout_file=None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess:
        try:
            result = subprocess.run(
                [self.terraform_binary, *args],
                cwd=working_root,
                stdout=stdout_file if stdout_file is not None else subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=stdout_file is None,
                timeout=self.command_timeout_seconds,
                check=False,
                env=env if env is not None else self._terraform_environment(),
            )
        except (OSError, subprocess.TimeoutExpired):
            raise TerraformPlanExecutionError(
                f"Terraform {args[0]} failed to start or exceeded its timeout"
            ) from None
        if result.returncode not in allowed_exit_codes:
            raise TerraformPlanExecutionError(
                f"Terraform {args[0]} failed with exit code {result.returncode}"
            )
        return result

    @staticmethod
    def _trusted_configuration(
        proposal: GeneratedDeploymentProposal,
        region: str,
        expected_account_id: str,
        terraform_version: str,
    ) -> dict[str, Any]:
        generated = {
            "terraform": {
                "required_version": f"= {terraform_version}",
                "required_providers": {
                    "aws": {"source": "hashicorp/aws", "version": "~> 5.0"}
                },
            },
            "provider": {"aws": {"region": region}},
            "data": {"aws_caller_identity": {"trusted": {}}},
            "resource": terraform_resource_blocks(proposal),
        }
        if "terraform_data" in generated["resource"] and "account_guard" in generated["resource"]["terraform_data"]:
            raise TerraformPlanExecutionError("proposal uses a reserved trusted Terraform resource address")
        generated["resource"].setdefault("terraform_data", {})["account_guard"] = {
            "lifecycle": {
                "precondition": {
                    "condition": "${data.aws_caller_identity.trusted.account_id == "
                    + json.dumps(expected_account_id)
                    + "}",
                    "error_message": "Terraform credentials do not match the approved AWS account.",
                }
            }
        }
        return generated

    def _read_lockfile(self) -> bytes:
        path = self.provider_lockfile
        if path.is_symlink() or not path.is_file():
            raise TerraformPlanExecutionError("trusted Terraform provider lockfile is unavailable")
        return path.read_bytes()

    def _provider_version(self, lockfile: str) -> str:
        match = re.search(
            r'provider\s+"registry\.terraform\.io/hashicorp/aws"\s*\{(?P<body>[^}]*)\}',
            lockfile,
            flags=re.DOTALL,
        )
        version = re.search(r'^\s*version\s*=\s*"(\d+\.\d+\.\d+)"', match["body"], flags=re.MULTILINE) if match else None
        if version is None:
            raise TerraformPlanExecutionError("AWS provider version is missing from trusted lockfile")
        return version[1]

    @staticmethod
    def _secure_workspace(workspace: Path) -> Path:
        if workspace.is_symlink():
            raise TerraformPlanExecutionError("Terraform workspace cannot be a symbolic link")
        workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not workspace.is_dir() or workspace.is_symlink():
            raise TerraformPlanExecutionError("Terraform workspace is not a private directory")
        if stat.S_IMODE(workspace.stat().st_mode) & 0o077:
            raise TerraformPlanExecutionError("Terraform workspace permissions must be private")
        return workspace.resolve()

    @staticmethod
    def _write_private(path: Path, content: bytes) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags, 0o600)
            with os.fdopen(descriptor, "wb") as file:
                file.write(content)
        except FileExistsError as error:
            raise TerraformPlanExecutionError("Terraform workspace already contains generated files") from error

    @staticmethod
    def _rewrite_private(path: Path, content: bytes) -> None:
        flags = os.O_WRONLY | os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(path, flags)
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
                os.close(descriptor)
                raise TerraformPlanExecutionError("generated Terraform file is not private")
            with os.fdopen(descriptor, "wb") as file:
                file.write(content)
        except (FileNotFoundError, OSError) as error:
            raise TerraformPlanExecutionError("generated Terraform configuration is unavailable") from error

    @staticmethod
    def _terraform_environment(
        aws_credentials: dict[str, str] | None = None,
    ) -> dict[str, str]:
        allowed = {
            "PATH",
            "HOME",
            "TMPDIR",
            "LANG",
            "LC_ALL",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "AWS_PROFILE",
            "AWS_DEFAULT_PROFILE",
            "AWS_CONFIG_FILE",
            "AWS_SHARED_CREDENTIALS_FILE",
            "AWS_ROLE_ARN",
            "AWS_WEB_IDENTITY_TOKEN_FILE",
        }
        environment = {key: value for key, value in os.environ.items() if key in allowed}
        if aws_credentials is not None:
            access_key = aws_credentials.get("AccessKeyId")
            secret_key = aws_credentials.get("SecretAccessKey")
            session_token = aws_credentials.get("SessionToken")
            if not all(
                isinstance(value, str) and value
                for value in (access_key, secret_key, session_token)
            ):
                raise TerraformPlanExecutionError(
                    "assumed AWS role returned incomplete temporary credentials"
                )
            for key in (
                "AWS_PROFILE",
                "AWS_DEFAULT_PROFILE",
                "AWS_CONFIG_FILE",
                "AWS_SHARED_CREDENTIALS_FILE",
                "AWS_ROLE_ARN",
                "AWS_WEB_IDENTITY_TOKEN_FILE",
            ):
                environment.pop(key, None)
            environment.update(
                {
                    "AWS_ACCESS_KEY_ID": access_key,
                    "AWS_SECRET_ACCESS_KEY": secret_key,
                    "AWS_SESSION_TOKEN": session_token,
                }
            )
        return environment

    @staticmethod
    def _aws_account_id() -> str:
        try:
            response = boto3.client("sts").get_caller_identity()
        except (BotoCoreError, ClientError):
            raise TerraformPlanExecutionError(
                "could not verify the active AWS account identity"
            ) from None
        account = response.get("Account")
        if not isinstance(account, str):
            raise TerraformPlanExecutionError("AWS STS returned an invalid account identity")
        return account


def verify_saved_plan_artifact(path: str | Path, expected_sha256: str) -> None:
    """Verify a saved plan before any future transfer or use."""
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise TerraformPlanExecutionError("saved plan digest is invalid")
    plan_path = Path(path)
    if plan_path.is_symlink() or not plan_path.is_file():
        raise TerraformPlanExecutionError("saved plan artifact is unavailable")
    if stat.S_IMODE(plan_path.stat().st_mode) & 0o077:
        raise TerraformPlanExecutionError("saved plan artifact permissions are not private")
    digest = hashlib.sha256()
    with plan_path.open("rb") as plan_file:
        for chunk in iter(lambda: plan_file.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_sha256:
        raise TerraformPlanExecutionError("saved plan artifact digest does not match")
