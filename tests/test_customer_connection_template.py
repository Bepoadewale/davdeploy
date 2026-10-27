from pathlib import Path


def test_customer_template_has_only_an_explicit_administrator_pilot_execution_role():
    template = Path("infrastructure/cloudformation/customer-discovery-role.yaml").read_text()

    assert "ExecutionRole" in template
    assert "AppRunner" not in template
    assert "AdministratorAccess" in template
