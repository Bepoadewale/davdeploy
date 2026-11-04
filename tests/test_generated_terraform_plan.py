from __future__ import annotations

import hashlib
import json
import os
import textwrap

import pytest
from davdeploy.generated_deployment_contract import GeneratedDeploymentProposal
from davdeploy.generated_terraform_plan import (
    GeneratedTerraformPlanRunner,
    TerraformPlanExecutionError,
    verify_saved_plan_artifact,
)

LOCKFILE = '''provider "registry.terraform.io/hashicorp/aws" {
  version = "5.100.0"
  constraints = "~> 5.0"
  hashes = ["h1:trusted"]
}
'''


def proposal():
    return GeneratedDeploymentProposal.model_validate(
        {
            "contract_version": "1.0",
            "source_revision": "test-revision",
            "context_digest": "a" * 64,
            "requirements": {"region": "us-east-1"},
            "resources": [
                {
                    "resource_id": "bucket",
                    "resource_type": "aws_s3_bucket",
                    "name": "bucket",
                    "arguments": {"bucket": "davdeploy-plan-test-unique"},
                    "outputs": [{"name": "arn", "value_type": "aws_arn"}],
                    "rationale": "Private application object storage.",
                }
            ],
        }
    )


def fake_terraform(tmp_path, *, applyable=True, errored=False):
    executable = tmp_path / "terraform-fake"
    schema = {
        "provider_schemas": {
            "registry.terraform.io/hashicorp/aws": {
                "provider": {"version": 0},
                "resource_schemas": {
                    "aws_s3_bucket": {
                        "block": {
                            "attributes": {
                                "bucket": {"type": "string", "required": True},
                                "force_destroy": {"type": "bool", "optional": True},
                                "arn": {"type": "string", "computed": True},
                            },
                            "block_types": {},
                        }
                    }
                },
            }
        }
    }
    plan_doc = {
        "format_version": "1.2",
        "applyable": applyable,
        "errored": errored,
        "resource_changes": [
            {
                "address": "aws_s3_bucket.bucket",
                "type": "aws_s3_bucket",
                "change": {
                    "actions": ["create"],
                    "before_sensitive": False,
                    "after_sensitive": False,
                },
            }
        ],
        "resource_drift": [],
    }
    source = f'''#!/usr/bin/env python3
import json
import os
import pathlib
import sys

args = sys.argv[1:]
with open(".terraform-command-log", "a") as command_log:
    command_log.write(" ".join(args) + "\\n")
pathlib.Path(".terraform-cli-args-plan").write_text(os.environ.get("TF_CLI_ARGS_plan", ""))
if args == ["version", "-json"]:
    print(json.dumps({{"terraform_version": "1.14.7"}}))
elif args and args[0] == "providers":
    print(json.dumps(json.loads({json.dumps(json.dumps(schema))})))
elif args and args[0] == "plan":
    target = next(item.split("=", 1)[1] for item in args if item.startswith("-out="))
    pathlib.Path(target).write_bytes(b"binary-saved-plan")
elif args and args[0] == "show":
    print(json.dumps(json.loads({json.dumps(json.dumps(plan_doc))})))
elif args and args[0] in {{"init", "validate"}}:
    pass
else:
    raise SystemExit(91)
'''
    executable.write_text(textwrap.dedent(source))
    executable.chmod(0o700)
    return executable


def runner(tmp_path, *, identity="654654474502", fake=None):
    lockfile = tmp_path / "aws.lock.hcl"
    lockfile.write_text(LOCKFILE)
    return GeneratedTerraformPlanRunner(
        provider_lockfile=lockfile,
        expected_terraform_version="1.14.7",
        expected_aws_provider_version="5.100.0",
        terraform_binary=str(fake or fake_terraform(tmp_path)),
        identity_provider=lambda: identity,
    )


def test_plan_runs_pinned_backend_free_flow_and_returns_digests(tmp_path, monkeypatch):
    monkeypatch.setenv("TF_CLI_ARGS_plan", "-destroy")
    workspace = tmp_path / "private-run"
    result = runner(tmp_path).plan(
        proposal(),
        expected_account_id="654654474502",
        region="us-east-1",
        workspace=workspace,
    )
    assert result.summary.create_count == 1
    assert result.summary.applyable is True
    assert result.target_account_id == "654654474502"
    assert result.region == "us-east-1"
    assert result.terraform_version == "1.14.7"
    assert result.aws_provider_version == "5.100.0"
    assert len(result.proposal_sha256) == 64
    assert len(result.provider_lockfile_sha256) == 64
    assert len(result.configuration_sha256) == 64
    assert len(result.saved_plan_sha256) == 64
    assert os.stat(result.saved_plan_path).st_mode & 0o777 == 0o600
    generated = json.loads((workspace / "main.tf.json").read_text())
    assert "backend" not in generated["terraform"]
    assert generated["provider"]["aws"]["region"] == "us-east-1"
    assert "data.aws_caller_identity.trusted.account_id" in json.dumps(generated)
    assert "654654474502" in json.dumps(generated)
    commands = (workspace / ".terraform-command-log").read_text().splitlines()
    assert commands == [
        "version -json",
        "init -backend=false -input=false -lockfile=readonly -no-color",
        "providers schema -json",
        "validate -no-color",
        f"plan -input=false -lock=false -no-color -out={workspace / 'saved.tfplan'}",
        f"show -json {workspace / 'saved.tfplan'}",
    ]
    assert not hasattr(GeneratedTerraformPlanRunner, "apply")
    assert (workspace / ".terraform-cli-args-plan").read_text() == ""


def test_target_account_mismatch_blocks_before_creating_workspace(tmp_path):
    workspace = tmp_path / "never-created"
    with pytest.raises(TerraformPlanExecutionError, match="does not match trusted account"):
        runner(tmp_path, identity="111111111111").plan(
            proposal(),
            expected_account_id="654654474502",
            region="us-east-1",
            workspace=workspace,
        )
    assert not workspace.exists()


def test_proposal_region_must_match_trusted_region(tmp_path):
    with pytest.raises(TerraformPlanExecutionError, match="region does not match"):
        runner(tmp_path).plan(
            proposal(),
            expected_account_id="654654474502",
            region="eu-west-1",
            workspace=tmp_path / "workspace",
        )


def test_provider_lockfile_version_must_match_exact_pin(tmp_path):
    value = runner(tmp_path)
    value.expected_aws_provider_version = "5.99.0"
    with pytest.raises(TerraformPlanExecutionError, match="lockfile version does not match"):
        value.plan(
            proposal(),
            expected_account_id="654654474502",
            region="us-east-1",
            workspace=tmp_path / "workspace",
        )


def test_workspace_must_have_private_permissions(tmp_path):
    workspace = tmp_path / "public-workspace"
    workspace.mkdir(mode=0o755)
    workspace.chmod(0o755)
    with pytest.raises(TerraformPlanExecutionError, match="permissions must be private"):
        runner(tmp_path).plan(
            proposal(),
            expected_account_id="654654474502",
            region="us-east-1",
            workspace=workspace,
        )


def test_custom_aws_endpoint_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://127.0.0.1:4566")
    with pytest.raises(TerraformPlanExecutionError, match="custom AWS endpoints"):
        runner(tmp_path).plan(
            proposal(),
            expected_account_id="654654474502",
            region="us-east-1",
            workspace=tmp_path / "workspace",
        )


@pytest.mark.parametrize("applyable, errored", [(False, True), (False, False)])
def test_failed_or_non_applyable_changed_plan_fails_closed(tmp_path, applyable, errored):
    fake = fake_terraform(tmp_path, applyable=applyable, errored=errored)
    with pytest.raises(TerraformPlanExecutionError, match="errored or non-applyable"):
        runner(tmp_path, fake=fake).plan(
            proposal(),
            expected_account_id="654654474502",
            region="us-east-1",
            workspace=tmp_path / "workspace",
        )


def test_invalid_provider_schema_stops_before_terraform_plan(tmp_path):
    fake = fake_terraform(tmp_path)
    source = fake.read_text().replace("aws_s3_bucket", "aws_missing_bucket")
    fake.write_text(source)
    with pytest.raises(TerraformPlanExecutionError, match="schema validation"):
        runner(tmp_path, fake=fake).plan(
            proposal(),
            expected_account_id="654654474502",
            region="us-east-1",
            workspace=tmp_path / "workspace",
        )


def test_stale_saved_plan_path_is_rejected(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o700)
    (workspace / "saved.tfplan").write_bytes(b"untrusted")
    with pytest.raises(TerraformPlanExecutionError, match="already exists"):
        runner(tmp_path).plan(
            proposal(),
            expected_account_id="654654474502",
            region="us-east-1",
            workspace=workspace,
        )


def test_saved_plan_artifact_digest_detects_tampering(tmp_path):
    artifact = tmp_path / "saved.tfplan"
    artifact.write_bytes(b"original-plan")
    artifact.chmod(0o600)
    original_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    verify_saved_plan_artifact(artifact, original_digest)
    artifact.write_bytes(b"changed-plan")
    with pytest.raises(TerraformPlanExecutionError, match="digest does not match"):
        verify_saved_plan_artifact(artifact, original_digest)
