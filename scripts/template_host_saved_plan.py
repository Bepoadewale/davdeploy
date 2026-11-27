"""Create and verify a private manifest for an exact template-host plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MANIFEST_VERSION = 1
SHA256_RE = re.compile(r"[a-f0-9]{64}\Z")
CONTEXT_FIELDS = (
    "git_commit",
    "terraform_version",
    "account",
    "region",
    "state_bucket",
    "state_key",
    "lock_table",
    "template_bucket",
)


class SavedPlanError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_digest(repo_root: Path, terraform_root: Path) -> str:
    """Bind Terraform inputs and both published template files to the plan."""
    candidates = [
        path
        for path in terraform_root.rglob("*")
        if path.is_file()
        and (
            path.suffix in {".tf", ".hcl", ".tfvars"}
            or path.name.endswith((".tf.json", ".tfvars.json"))
        )
    ]
    candidates.extend(
        [
            repo_root / "infrastructure/cloudformation/customer-discovery-role.yaml",
            repo_root / "infrastructure/cloudformation/customer-nova-apply-role.yaml",
            repo_root / "scripts/customer-aws-template-host.sh",
            repo_root / "scripts/template_host_saved_plan.py",
        ]
    )
    digest = hashlib.sha256()
    for path in sorted(set(candidates), key=lambda item: item.relative_to(repo_root).as_posix()):
        if path.is_symlink() or not path.is_file():
            raise SavedPlanError("template-host inputs must be regular files")
        relative = path.relative_to(repo_root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(bytes.fromhex(_sha256(path)))
    return digest.hexdigest()


def _context(args: argparse.Namespace) -> dict[str, str]:
    return {
        "git_commit": args.git_commit,
        "terraform_version": args.terraform_version,
        "account": args.account,
        "region": args.region,
        "state_bucket": args.state_bucket,
        "state_key": args.state_key,
        "lock_table": args.lock_table,
        "template_bucket": args.template_bucket,
    }


def _check_private_regular_file(path: Path, label: str) -> None:
    try:
        parent_info = path.parent.lstat()
    except OSError:
        raise SavedPlanError(f"{label} directory is unavailable") from None
    if not stat.S_ISDIR(parent_info.st_mode) or stat.S_IMODE(parent_info.st_mode) & 0o077:
        raise SavedPlanError(f"{label} directory must be private")
    try:
        info = path.lstat()
    except OSError:
        raise SavedPlanError(f"{label} is unavailable") from None
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
        raise SavedPlanError(f"{label} must be a private regular file")


def _atomic_write_private(path: Path, value: dict[str, Any]) -> None:
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise SavedPlanError("saved-plan directory is unavailable")
    os.chmod(path.parent, 0o700)
    fd, temp_name = tempfile.mkstemp(prefix=".manifest.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def create(args: argparse.Namespace) -> None:
    plan = Path(args.plan)
    manifest = Path(args.manifest)
    _check_private_regular_file(plan, "saved Terraform plan")
    actual_sha = _sha256(plan)
    if not SHA256_RE.fullmatch(args.sha256) or actual_sha != args.sha256:
        raise SavedPlanError("saved Terraform plan digest does not match the requested digest")

    context = _context(args)
    manifest_value = {
        "manifest_version": MANIFEST_VERSION,
        "created_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "saved_plan_sha256": actual_sha,
        "source_sha256": _source_digest(Path(args.repo_root), Path(args.terraform_root)),
        **context,
    }
    _atomic_write_private(manifest, manifest_value)


def verify(args: argparse.Namespace) -> None:
    plan = Path(args.plan)
    manifest = Path(args.manifest)
    _check_private_regular_file(plan, "saved Terraform plan")
    _check_private_regular_file(manifest, "saved-plan manifest")
    try:
        document = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise SavedPlanError("saved-plan manifest is invalid") from None
    if not isinstance(document, dict) or document.get("manifest_version") != MANIFEST_VERSION:
        raise SavedPlanError("unsupported saved-plan manifest")

    actual_sha = _sha256(plan)
    if not SHA256_RE.fullmatch(args.reviewed_sha256) or actual_sha != args.reviewed_sha256:
        raise SavedPlanError("reviewed saved-plan digest mismatch")
    if document.get("saved_plan_sha256") != actual_sha:
        raise SavedPlanError("saved-plan manifest digest mismatch")

    context = _context(args)
    if any(document.get(key) != value for key, value in context.items()):
        raise SavedPlanError("saved-plan deployment context changed; create and review a new plan")
    source_sha = _source_digest(Path(args.repo_root), Path(args.terraform_root))
    if document.get("source_sha256") != source_sha:
        raise SavedPlanError("template-host source changed; create and review a new plan")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("create", "verify"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--plan", required=True)
        sub.add_argument("--manifest", required=True)
        sub.add_argument("--repo-root", required=True)
        sub.add_argument("--terraform-root", required=True)
        for field in CONTEXT_FIELDS:
            sub.add_argument(f"--{field.replace('_', '-')}", dest=field, required=True)
        if name == "create":
            sub.add_argument("--sha256", required=True)
        else:
            sub.add_argument("--reviewed-sha256", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        (create if args.command == "create" else verify)(args)
    except (OSError, SavedPlanError) as exc:
        print(f"template-host saved-plan check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
