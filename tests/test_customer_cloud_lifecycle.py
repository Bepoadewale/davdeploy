from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from davdeploy.domain import CloudInventorySnapshot
from davdeploy.integrations import StsAwsDiscovery
from davdeploy.models import Environment
from test_product import founder, make_service


def test_verified_customer_snapshot_is_the_only_non_fixture_planning_input():
    service, _ = make_service()
    connection = service.create_cloud_connection(
        founder(), "Customer cloud", "aws", "byoc_role_contract"
    )
    connection.setup_state = "VERIFIED"
    service.db.commit()
    snapshot = CloudInventorySnapshot(
        provider="aws",
        region="us-east-1",
        approved_resources=["aws-account:654654474502", "vpc:2", "lambda:5"],
        approved_regions=["us-east-1"],
        discovered_at=datetime.now(UTC),
        provenance="live-read-only-sts-discovery",
        pricing_evidence={
            "kind": "aws_pricing_evidence.v1",
            "catalog": {"state": "EXECUTED"},
            "cost_explorer": {"state": "EXECUTED"},
        },
    )
    service.record_cloud_inventory_snapshot(
        founder(),
        connection.id,
        "us-east-1",
        snapshot.provenance,
        snapshot.discovered_at,
        snapshot.model_dump(mode="json"),
    )

    selected = service._planning_inventory(founder(), connection.id, "us-east-1")

    assert selected.provenance == "live-read-only-sts-discovery"
    assert selected.approved_resources == ["aws-account:654654474502", "vpc:2", "lambda:5"]
    assert selected.pricing_evidence["catalog"]["state"] == "EXECUTED"


def test_unverified_customer_connection_cannot_be_used_for_planning():
    service, _ = make_service()
    connection = service.create_cloud_connection(
        founder(), "Unverified cloud", "aws", "byoc_role_contract"
    )

    with pytest.raises(ValueError, match="must be verified"):
        service._planning_inventory(founder(), connection.id, "us-east-1")


def test_customer_cloudformation_contract_keeps_administrator_pilot_opt_in():
    template = Path("infrastructure/cloudformation/customer-discovery-role.yaml").read_text(
        encoding="utf-8"
    )

    assert "davdeployDiscovery-${ConnectionId}" in template
    assert "davdeployDiscoveryBrokerRoleArn" in template
    assert "AccessMode" in template
    assert "CreateAdministratorPilotRole" in template
    assert "ExecutionRole" in template
    assert "AppRunnerEcrAccessRole" in template
    assert "AdministratorAccess" in template
    assert "sts:ExternalId" in template


def test_live_pricing_evidence_labels_catalog_and_cost_explorer_failures():
    StsAwsDiscovery._pricing_evidence_cache.clear()

    class UnavailableClient:
        def get_products(self, **_kwargs):
            from botocore.exceptions import ClientError

            raise ClientError({"Error": {"Code": "AccessDeniedException"}}, "GetProducts")

        def get_cost_and_usage(self, **_kwargs):
            from botocore.exceptions import ClientError

            raise ClientError({"Error": {"Code": "AccessDeniedException"}}, "GetCostAndUsage")

    class Customer:
        def client(self, _name, region_name):
            assert region_name == "us-east-1"
            return UnavailableClient()

    evidence = StsAwsDiscovery._pricing_evidence(Customer(), "us-east-1")

    assert evidence["catalog"]["state"] == "UNAVAILABLE"
    assert evidence["cost_explorer"]["state"] == "UNAVAILABLE"
    assert len(evidence["limitations"]) == 2


def test_live_pricing_evidence_caches_cost_explorer_calls_per_customer_account(monkeypatch):
    StsAwsDiscovery._pricing_evidence_cache.clear()
    monkeypatch.setenv("DAVDEPLOY_PRICING_EVIDENCE_CACHE_SECONDS", "3600")

    class Customer:
        def __init__(self):
            self.cost_explorer_calls = 0

        def client(self, name, region_name):
            assert region_name == "us-east-1"
            if name == "pricing":
                return self
            assert name == "ce"
            return self

        def get_products(self, **_kwargs):
            return {"PriceList": ["catalog-result"]}

        def get_cost_and_usage(self, **_kwargs):
            self.cost_explorer_calls += 1
            return {"ResultsByTime": [{"Total": {"UnblendedCost": {"Amount": "1.23"}}}]}

    customer = Customer()
    first = StsAwsDiscovery._pricing_evidence(customer, "us-east-1", "123456789012")
    second = StsAwsDiscovery._pricing_evidence(customer, "us-east-1", "123456789012")

    assert customer.cost_explorer_calls == 1
    assert first["cache"]["state"] == "MISS"
    assert second["cache"]["state"] == "HIT"
    assert second["cost_explorer"]["daily_unblended_cost_usd"] == ["1.23"]


def test_fixture_observed_outputs_redact_sensitive_values_before_customer_readback():
    """Keep the future observer contract testable without a customer cloud account."""
    service, _ = make_service()
    project = service.create_project(
        founder(), "future-observation", "https://github.com/example/app"
    )
    environment = Environment(
        organization_id=founder().organization_id,
        project_id=project.id,
        name="staging",
        environment_type="staging",
        state="READY",
        desired_state={"execution_mode": "FIXTURE"},
    )
    service.db.add(environment)
    service.db.flush()

    service._record_environment_observation_assets(
        environment,
        {
            "outputs": [
                {
                    "name": "application_url",
                    "type": "https_url",
                    "value": "https://staging.example.test",
                    "source": "fixture-observer",
                    "sensitive": False,
                },
                {
                    "name": "database_password",
                    "type": "secret_reference",
                    "value": "never-return-a-customer-secret",
                    "source": "fixture-observer",
                    "sensitive": True,
                },
            ],
            "resources": [
                {
                    "provider": "aws",
                    "resource_type": "app_runner_service",
                    "name": "fixture-service",
                    "region": "us-east-1",
                    "status": "OBSERVED",
                    "tags": {"fixture": "true"},
                }
            ],
        },
    )
    service.db.commit()

    outputs = {item["name"]: item for item in service._environment_outputs(environment.id)}
    resources = service._observed_resources(environment.id)

    assert outputs["application_url"]["value"] == "https://staging.example.test"
    assert outputs["database_password"]["value"] == "***"
    assert outputs["database_password"]["source"] == "fixture-observer"
    assert resources[0]["provider"] == "aws"
    assert resources[0]["type"] == "app_runner_service"
    assert resources[0]["name"] == "fixture-service"
    assert resources[0]["status"] == "OBSERVED"
