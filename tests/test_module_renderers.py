from davdeploy.module_renderers import renderer_for, renderer_manifest


def test_only_checked_in_module_renderer_is_resolved():
    renderer = renderer_for("aws-managed-application", "apply")
    assert renderer.terraform_root == "infrastructure/terraform/customer-workload-app-runner-pilot"
    assert renderer.runner_script == "scripts/customer-workload-app-runner-pilot.sh"
    assert renderer_manifest() == (renderer,)


def test_unbound_or_unsupported_renderer_work_is_rejected():
    for module_id, operation in (("aws-relational-data", "apply"), ("aws-managed-application", "rollback")):
        try:
            renderer_for(module_id, operation)
        except ValueError as error:
            assert "module" in str(error)
        else:
            raise AssertionError("unbound renderer work was accepted")
