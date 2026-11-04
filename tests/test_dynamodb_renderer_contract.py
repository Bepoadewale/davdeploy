from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dynamodb_root_is_account_guarded_on_demand_encrypted_and_recoverable():
    terraform = ROOT / "infrastructure/terraform/customer-workload-dynamodb"
    main = (terraform / "main.tf").read_text()
    versions = (terraform / "versions.tf").read_text()
    variables = (terraform / "variables.tf").read_text()
    lockfile = (terraform / ".terraform.lock.hcl").read_text()
    assert "data.aws_caller_identity.current.account_id == var.expected_account_id" in main
    assert 'billing_mode = "PAY_PER_REQUEST"' in main
    assert 'hash_key     = "pk"' in main
    assert 'type = "S"' in main
    assert "point_in_time_recovery" in main
    assert "enabled = true" in main
    assert "server_side_encryption" in main
    assert "DavDeployConnection = var.connection_id" in main
    assert "DavDeployProject    = var.project_id" in main
    assert "DavDeployPlan       = var.plan_digest" in main
    assert 'backend "s3" {}' in versions
    assert 'version     = "5.100.0"' in lockfile
    for variable in ("region", "expected_account_id", "connection_id", "project_id", "plan_digest"):
        assert f'variable "{variable}"' in variables


def test_dynamodb_runner_checks_empty_data_before_both_destroy_stages():
    script = (ROOT / "scripts/customer-workload-dynamodb.sh").read_text()
    assert 'key=davdeploy/customer/${connection_id}/projects/${project_id}/regions/${AWS_REGION}/dynamodb.tfstate' in script
    assert '[[ "$result_uri" == "${customer_state_prefix}runs/${run_id}/result.json" ]]' in script
    assert '[[ "$saved_plan_uri" == "$saved_plan_prefix"* ]]' in script
    assert "--limit 1 --select COUNT --no-paginate" in script
    assert "DynamoDB table contains data" in script
    assert 'if [[ "$operation" == "destroy-plan" ]]; then assert_table_empty_for_destroy; fi' in script
    assert 'if [[ "$operation" == "destroy-saved-plan" ]]; then assert_table_empty_for_destroy; fi' in script
    assert "PointInTimeRecoveryStatus == \"ENABLED\"" in script
    assert "PAY_PER_REQUEST" in script
    assert "list-tags-of-resource" in script
    assert 'terraform -chdir="$root" apply -input=false "$plan_file"' in script
    assert "terraform apply -auto-approve" not in script


def test_executor_package_and_terraform_validator_include_dynamodb_renderer():
    builder = (ROOT / "scripts/build_customer_executor_package.sh").read_text()
    validator = (ROOT / "scripts/terraform-validate.sh").read_text()
    assert "customer-workload-dynamodb" in builder
    assert "customer-workload-dynamodb.sh" in builder
    assert 'rm -f "${build_root}/package/infrastructure/terraform/customer-workload-dynamodb/.terraform.lock.hcl"' not in builder
    assert "customer-workload-dynamodb" in validator
