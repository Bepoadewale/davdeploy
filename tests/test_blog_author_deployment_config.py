from pathlib import Path


def test_blog_author_access_has_no_individual_or_deployment_configuration_allowlist():
    runtime = Path("infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    workflow = Path(".github/workflows/terraform-plan.yml").read_text()

    assert "DAVDEPLOY_BLOG_AUTHOR_SUBJECTS" not in runtime
    assert "DAVDEPLOY_BLOG_AUTHOR_SUBJECTS" not in workflow
