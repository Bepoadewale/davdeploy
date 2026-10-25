from pathlib import Path


def test_customer_execution_role_limits_image_push_to_connection_repository():
    template = Path("infrastructure/cloudformation/customer-discovery-role.yaml").read_text()

    assert "- ecr:BatchGetImage" in template
    assert 'repository/davdeploy-${ConnectionId}-workload' in template
    assert "PushOnlyConnectionScopedWorkloadImage" in template
