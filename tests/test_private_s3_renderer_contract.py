from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_private_s3_root_enforces_account_scope_and_safe_bucket_defaults():
    terraform = ROOT / "infrastructure/terraform/customer-workload-private-s3"
    main = (terraform / "main.tf").read_text()
    variables = (terraform / "variables.tf").read_text()
    assert "data.aws_caller_identity.current.account_id == var.expected_account_id" in main
    assert "bucket        = local.bucket_name" in main
    assert "force_destroy = false" in main
    assert "DavDeployConnection = var.connection_id" in main
    assert "DavDeployProject    = var.project_id" in main
    assert "DavDeployPlan       = var.plan_digest" in main
    assert "block_public_acls       = true" in main
    assert "block_public_policy     = true" in main
    assert "ignore_public_acls      = true" in main
    assert "restrict_public_buckets = true" in main
    assert 'object_ownership = "BucketOwnerEnforced"' in main
    assert 'sse_algorithm = "AES256"' in main
    assert 'status = "Enabled"' in main
    assert 'variable "expected_account_id"' in variables
    assert 'variable "plan_digest"' in variables


def test_private_s3_runner_uses_approved_project_scoped_saved_plans_and_observation():
    script = (ROOT / "scripts/customer-workload-private-s3.sh").read_text()
    assert "assume-role" in script
    assert "customer_account_id" in script
    assert (
        'bucket_name="davdeploy-${EXPECTED_AWS_ACCOUNT_ID}-${AWS_REGION}-${project_suffix}"'
        in script
    )
    assert (
        "key=davdeploy/customer/${connection_id}/projects/${project_id}/private-s3.tfstate"
        in script
    )
    assert '[[ "$result_uri" == "${customer_state_prefix}runs/${run_id}/result.json" ]]' in script
    assert '[[ "$saved_plan_uri" == "$saved_plan_prefix"* ]]' in script
    assert 'terraform -chdir="$root" apply -input=false "$plan_file"' in script
    assert "head-bucket" in script
    assert "get-public-access-block" in script
    assert "get-bucket-ownership-controls" in script
    assert "get-bucket-encryption" in script
    assert "get-bucket-versioning" in script
    assert "get-bucket-policy" in script
    assert "list-object-versions" in script
    assert 'assert_bucket_empty_for_destroy; fi' in script
    assert '[[ "$operation" == "destroy-saved-plan" ]]' in script
    assert "Private storage contains current or previous object versions" in script
    assert "force_destroy" not in script
    assert "terraform apply -auto-approve" not in script


def test_executor_package_includes_private_s3_renderer_and_terraform_root():
    package_builder = (ROOT / "scripts/build_customer_executor_package.sh").read_text()
    assert "customer-workload-private-s3" in package_builder
    assert "customer-workload-private-s3.sh" in package_builder
