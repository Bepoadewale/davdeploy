from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/template_host_saved_plan.py"
SPEC = importlib.util.spec_from_file_location("template_host_saved_plan", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
SAVED_PLAN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SAVED_PLAN)


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    repo = tmp_path / "repo"
    terraform_root = repo / "infrastructure/terraform/connection-template-host"
    template_root = repo / "infrastructure/cloudformation"
    terraform_root.mkdir(parents=True)
    template_root.mkdir(parents=True)
    (terraform_root / "main.tf").write_text('terraform { required_version = ">= 1.0" }\n')
    (terraform_root / "terraform.lock.hcl").write_text('provider "registry.terraform.io/hashicorp/aws" {}\n')
    (template_root / "customer-discovery-role.yaml").write_text("discovery template\n")
    (template_root / "customer-nova-apply-role.yaml").write_text("apply template\n")
    plan_dir = repo / ".local/template-host-plans/plan.test001"
    plan_dir.mkdir(parents=True)
    plan_dir.chmod(0o700)
    plan = plan_dir / "tfplan"
    plan.write_bytes(b"opaque saved plan for test")
    plan.chmod(0o600)
    return repo, terraform_root, plan_dir, plan


def _args(repo: Path, terraform_root: Path, plan_dir: Path, plan: Path) -> argparse.Namespace:
    return argparse.Namespace(
        plan=str(plan),
        manifest=str(plan_dir / "manifest.json"),
        repo_root=str(repo),
        terraform_root=str(terraform_root),
        sha256=hashlib.sha256(plan.read_bytes()).hexdigest(),
        git_commit="a" * 40,
        terraform_version="1.14.7",
        account="654654474502",
        region="us-east-1",
        state_bucket="davdeploy-tfstate-test",
        state_key="davdeploy/connection-template-host.tfstate",
        lock_table="davdeploy-terraform-locks-test",
        template_bucket="davdeploy-customer-templates-test",
    )


def test_saved_plan_manifest_binds_digest_context_and_template_sources(tmp_path: Path) -> None:
    repo, terraform_root, plan_dir, plan = _fixture(tmp_path)
    args = _args(repo, terraform_root, plan_dir, plan)

    SAVED_PLAN.create(args)
    manifest = plan_dir / "manifest.json"
    document = json.loads(manifest.read_text())

    assert document["manifest_version"] == 1
    assert document["created_at_utc"].endswith("+00:00")
    assert document["saved_plan_sha256"] == args.sha256
    assert document["account"] == args.account
    assert document["state_key"] == args.state_key
    assert len(document["source_sha256"]) == 64
    assert stat.S_IMODE(manifest.stat().st_mode) == 0o600
    assert stat.S_IMODE(plan_dir.stat().st_mode) & 0o077 == 0

    args.manifest = str(manifest)
    args.reviewed_sha256 = args.sha256
    SAVED_PLAN.verify(args)


def test_saved_plan_rejects_tampering_and_wrong_review_digest(tmp_path: Path) -> None:
    repo, terraform_root, plan_dir, plan = _fixture(tmp_path)
    args = _args(repo, terraform_root, plan_dir, plan)
    SAVED_PLAN.create(args)
    args.manifest = str(plan_dir / "manifest.json")
    args.reviewed_sha256 = "0" * 64

    try:
        SAVED_PLAN.verify(args)
    except SAVED_PLAN.SavedPlanError as exc:
        assert "digest mismatch" in str(exc)
    else:
        raise AssertionError("a different reviewed digest must be rejected")

    args.reviewed_sha256 = args.sha256
    plan.write_bytes(b"tampered saved plan")
    try:
        SAVED_PLAN.verify(args)
    except SAVED_PLAN.SavedPlanError as exc:
        assert "digest mismatch" in str(exc)
    else:
        raise AssertionError("a tampered saved plan must be rejected")


def test_saved_plan_rejects_changed_context_and_source(tmp_path: Path) -> None:
    repo, terraform_root, plan_dir, plan = _fixture(tmp_path)
    args = _args(repo, terraform_root, plan_dir, plan)
    SAVED_PLAN.create(args)
    args.manifest = str(plan_dir / "manifest.json")
    args.reviewed_sha256 = args.sha256

    args.account = "111122223333"
    try:
        SAVED_PLAN.verify(args)
    except SAVED_PLAN.SavedPlanError as exc:
        assert "context changed" in str(exc)
    else:
        raise AssertionError("a different AWS account must be rejected")

    args.account = "654654474502"
    (terraform_root / "main.tf").write_text("resource \"example\" \"changed\" {}\n")
    try:
        SAVED_PLAN.verify(args)
    except SAVED_PLAN.SavedPlanError as exc:
        assert "source changed" in str(exc)
    else:
        raise AssertionError("changed Terraform source must be rejected")

    (terraform_root / "main.tf").write_text('terraform { required_version = ">= 1.0" }\n')
    (repo / "infrastructure/cloudformation/customer-nova-apply-role.yaml").write_text(
        "changed apply template\n"
    )
    try:
        SAVED_PLAN.verify(args)
    except SAVED_PLAN.SavedPlanError as exc:
        assert "source changed" in str(exc)
    else:
        raise AssertionError("changed template source must be rejected")


def test_saved_plan_rejects_insecure_permissions_and_symlink_inputs(tmp_path: Path) -> None:
    repo, terraform_root, plan_dir, plan = _fixture(tmp_path)
    args = _args(repo, terraform_root, plan_dir, plan)
    plan.chmod(0o644)
    try:
        SAVED_PLAN.create(args)
    except SAVED_PLAN.SavedPlanError as exc:
        assert "private regular file" in str(exc)
    else:
        raise AssertionError("a group-readable plan must be rejected")


def _prepare_shell_runner(tmp_path: Path) -> tuple[Path, dict[str, str], Path]:
    repo = tmp_path / "shell-repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "infrastructure/terraform/connection-template-host").mkdir(parents=True)
    (repo / "infrastructure/cloudformation").mkdir(parents=True)
    source_root = Path(__file__).resolve().parents[1]
    shutil.copy2(source_root / "scripts/customer-aws-template-host.sh", repo / "scripts/customer-aws-template-host.sh")
    shutil.copy2(source_root / "scripts/template_host_saved_plan.py", repo / "scripts/template_host_saved_plan.py")
    shutil.copy2(
        source_root / "infrastructure/terraform/connection-template-host/main.tf",
        repo / "infrastructure/terraform/connection-template-host/main.tf",
    )
    for name in ("customer-discovery-role.yaml", "customer-nova-apply-role.yaml"):
        shutil.copy2(source_root / f"infrastructure/cloudformation/{name}", repo / f"infrastructure/cloudformation/{name}")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    aws = fake_bin / "aws"
    aws.write_text('#!/bin/sh\necho 654654474502\n')
    aws.chmod(0o755)
    terraform = fake_bin / "terraform"
    terraform.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$TERRAFORM_CALLS"
case "$*" in
  *"version -json"*) echo '{"terraform_version":"1.14.7"}' ;;
  *" plan "*)
    for arg in "$@"; do
      case "$arg" in -out=*) plan_file=${arg#-out=} ;; esac
    done
    printf 'mock saved plan\\n' > "$plan_file"
    ;;
  *" show "*) echo 'Plan: 1 to add, 0 to change, 0 to destroy.' ;;
  *" apply "*) echo "apply:$*" >> "$TERRAFORM_APPLIES" ;;
esac
"""
    )
    terraform.chmod(0o755)

    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Template Host Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture"], check=True)

    calls = tmp_path / "terraform-calls.log"
    applies = tmp_path / "terraform-applies.log"
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "TERRAFORM_CALLS": str(calls),
        "TERRAFORM_APPLIES": str(applies),
        "EXPECTED_AWS_ACCOUNT_ID": "654654474502",
        "TF_STATE_BUCKET": "state-test",
        "TF_LOCK_TABLE": "locks-test",
        "AWS_REGION": "us-east-1",
        "DAVDEPLOY_TEMPLATE_BUCKET": "templates-test",
    }
    return repo, env, applies


def test_runner_applies_only_the_reviewed_saved_plan_and_rejects_tampering(tmp_path: Path) -> None:
    repo, env, applies = _prepare_shell_runner(tmp_path)
    script = repo / "scripts/customer-aws-template-host.sh"
    plan_result = subprocess.run(
        [str(script), "plan"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=repo,
    )
    assert plan_result.returncode == 0, plan_result.stderr + plan_result.stdout
    plan_dir = re.search(r"Saved plan directory: (.+)", plan_result.stdout)
    reviewed_sha = re.search(r"Reviewed plan SHA-256: ([a-f0-9]{64})", plan_result.stdout)
    assert plan_dir and reviewed_sha
    plan_file = Path(plan_dir.group(1)) / "tfplan"
    assert stat.S_IMODE(plan_file.stat().st_mode) == 0o600
    assert not applies.exists()

    apply_env = {**env, "CONFIRM_TEMPLATE_HOST_APPLY": "APPLY_DAVDEPLOY_TEMPLATE_HOST"}
    subprocess.run(
        [str(script), "apply-saved-plan", plan_dir.group(1), reviewed_sha.group(1)],
        capture_output=True,
        text=True,
        env=apply_env,
        cwd=repo,
        check=True,
    )
    apply_calls = applies.read_text().splitlines()
    assert len(apply_calls) == 1
    assert " apply -input=false " in apply_calls[0]
    assert apply_calls[0].endswith(str(plan_file))
    assert "-auto-approve" not in apply_calls[0]

    plan_file.write_text("tampered")
    rejected = subprocess.run(
        [str(script), "apply-saved-plan", plan_dir.group(1), reviewed_sha.group(1)],
        check=False,
        capture_output=True,
        text=True,
        env=apply_env,
        cwd=repo,
    )
    assert rejected.returncode != 0
    assert "digest mismatch" in rejected.stderr
    assert len(applies.read_text().splitlines()) == 1


def test_runner_rejects_unbound_apply_command(tmp_path: Path) -> None:
    repo, env, applies = _prepare_shell_runner(tmp_path)
    rejected = subprocess.run(
        [str(repo / "scripts/customer-aws-template-host.sh"), "apply"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=repo,
    )
    assert rejected.returncode != 0
    assert "usage:" in rejected.stderr
    assert not applies.exists()
