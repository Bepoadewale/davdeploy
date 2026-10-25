"""Validate the public repository's GitHub Actions configuration boundary."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

ALLOWED_VARIABLES = {
    "AWS_CONNECTION_TEMPLATE_URL",
    "AWS_REGION",
    "AWS_TERRAFORM_APPLY_ROLE_ARN",
    "AWS_TERRAFORM_PLAN_ROLE_ARN",
    "COGNITO_DOMAIN_PREFIX",
    "EXPECTED_AWS_ACCOUNT_ID",
    "ENABLE_CUSTOMER_CLOUD_EXECUTION",
    "ENABLE_GITHUB_APP_READ_ONLY",
    "FRONTEND_ORIGIN",
    "GOOGLE_IDENTITY_PROVIDER_ENABLED",
    "DAVDEPLOY_GITHUB_APP_CREDENTIAL_SECRET_ARN",
    "DAVDEPLOY_GITHUB_APP_ID",
    "DAVDEPLOY_GITHUB_APP_INSTALLATION_ID",
    "TF_PLAN_BUCKET",
    "TF_PLAN_KMS_KEY_ARN",
    "TF_RELEASE_BUCKET",
    "TF_RELEASE_KMS_KEY_ARN",
    "TF_STATE_BUCKET",
    "TF_STATE_LOCK_TABLE",
}
ALLOWED_SECRETS = {
    "BUDGET_NOTIFICATION_EMAIL",
    "SES_FROM_ADDRESS",
    "SES_IDENTITY_ARN",
}
SECRET_LIKE = re.compile(
    r"(?:^|_)(?:API_TOKEN|ACCESS_TOKEN|CLIENT_SECRET|WEBHOOK_SECRET|PASSWORD|PRIVATE_KEY|"
    r"SECRET_ACCESS_KEY|ACCESS_KEY_ID)(?:$|_)"
)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    variable_references: set[str] = set()
    secret_references: set[str] = set()
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        variable_references.update(re.findall(r"\bvars\.([A-Z][A-Z0-9_]*)", text))
        secret_references.update(re.findall(r"\bsecrets\.([A-Z][A-Z0-9_]*)", text))

    unknown_variables = variable_references - ALLOWED_VARIABLES
    if unknown_variables:
        fail(f"unclassified GitHub Actions variables: {sorted(unknown_variables)}")

    secret_like_variables = sorted(name for name in variable_references if SECRET_LIKE.search(name))
    if secret_like_variables:
        fail(f"secret-like values must use GitHub Secrets: {secret_like_variables}")

    unknown_secrets = secret_references - ALLOWED_SECRETS
    if unknown_secrets:
        fail(f"unclassified GitHub Actions secrets: {sorted(unknown_secrets)}")

    if "BUDGET_NOTIFICATION_EMAIL" not in secret_references:
        fail("BUDGET_NOTIFICATION_EMAIL must remain referenced through the secrets context")

    print(
        "Actions configuration boundary passed: "
        f"{len(variable_references)} public metadata names and "
        f"{len(secret_references)} secret names classified."
    )


if __name__ == "__main__":
    main()
