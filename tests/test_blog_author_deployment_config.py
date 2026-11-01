from pathlib import Path


def test_blog_author_subject_allowlist_is_a_protected_terraform_input():
    variables = Path("infrastructure/terraform/serverless-control-plane/variables.tf").read_text()
    runtime = Path("infrastructure/terraform/serverless-control-plane/main.tf").read_text()
    workflow = Path(".github/workflows/terraform-plan.yml").read_text()

    assert 'variable "blog_author_subjects"' in variables
    assert 'DAVDEPLOY_BLOG_AUTHOR_SUBJECTS               = join(",", var.blog_author_subjects)' in runtime
    assert "TF_VAR_blog_author_subjects: ${{ vars.DAVDEPLOY_BLOG_AUTHOR_SUBJECTS || '[]' }}" in workflow
