from davdeploy.module_renderers import (
    renderer_command,
    renderer_for,
    renderer_for_profile,
    renderer_manifest,
)


def test_only_checked_in_module_renderer_is_resolved():
    renderer = renderer_for("aws-managed-application", "apply")
    assert renderer.terraform_root == "infrastructure/terraform/customer-workload-app-runner-pilot"
    assert renderer.runner_script == "scripts/customer-workload-app-runner-pilot.sh"
    assert renderer.execution_enabled is True
    manifest = renderer_manifest()
    assert renderer in manifest
    serverless = next(item for item in manifest if item.module_id == "aws-serverless-api")
    assert serverless.execution_enabled is False
    assert serverless.terraform_root == "infrastructure/terraform/customer-workload-serverless-api"
    assert dict(serverless.operation_commands) == {
        "plan": "plan",
        "destroy_plan": "destroy-plan",
        "apply": "apply-saved-plan",
        "observe": "health",
        "destroy": "destroy-saved-plan",
        "verify_cleanup": "verify-cleanup",
    }


def test_unbound_or_unsupported_renderer_work_is_rejected():
    for module_id, operation in (
        ("aws-relational-data", "apply"),
        ("aws-managed-application", "rollback"),
        ("aws-serverless-api", "apply"),
    ):
        try:
            renderer_for(module_id, operation)
        except ValueError as error:
            assert "module" in str(error)
        else:
            raise AssertionError("unbound renderer work was accepted")


def test_serverless_profile_is_opt_in_for_certification_not_customer_execution(monkeypatch):
    monkeypatch.delenv("DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION", raising=False)
    try:
        renderer_for_profile("aws-lambda-api", "apply")
    except ValueError as error:
        assert "not enabled for customer execution" in str(error)
    else:
        raise AssertionError("serverless renderer must stay disabled before hosted certification")

    monkeypatch.setenv("DAVDEPLOY_ENABLE_SERVERLESS_API_HOSTED_CERTIFICATION", "true")
    for operation in ("plan", "destroy_plan", "apply", "observe", "destroy", "verify_cleanup"):
        serverless = renderer_for_profile("aws-lambda-api", operation)
        assert serverless.module_id == "aws-serverless-api"
        assert serverless.execution_enabled is False

    try:
        renderer_for_profile("aws-unknown", "apply")
    except ValueError as error:
        assert "no registered execution renderer" in str(error)
    else:
        raise AssertionError("unknown execution profile must fail closed")


def test_runner_command_mapping_is_fixed_and_operation_specific():
    app_runner = next(
        item for item in renderer_manifest() if item.module_id == "aws-managed-application"
    )
    assert renderer_command(app_runner, "apply") == "apply-saved-plan"
    assert renderer_command(app_runner, "destroy") == "destroy-saved-plan"
    serverless = next(item for item in renderer_manifest() if item.module_id == "aws-serverless-api")
    assert renderer_command(serverless, "observe") == "health"
    assert renderer_command(serverless, "destroy_plan") == "destroy-plan"
