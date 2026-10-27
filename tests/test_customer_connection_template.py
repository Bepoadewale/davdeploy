from pathlib import Path


def test_customer_template_contains_no_execution_role():
    template = Path("infrastructure/cloudformation/customer-discovery-role.yaml").read_text()

    assert "ExecutionRole" not in template
    assert "AppRunner" not in template
    assert "AdministratorAccess" not in template
