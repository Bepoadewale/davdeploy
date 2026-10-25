from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from davdeploy.domain import CloudInventorySnapshot
from davdeploy.integrations import StsAwsDiscovery
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


def test_customer_cloudformation_contract_keeps_execution_separate_from_discovery():
    template = Path("infrastructure/cloudformation/customer-discovery-role.yaml").read_text(
        encoding="utf-8"
    )

    assert "davdeployDiscovery-${ConnectionId}" in template
    assert "davdeployExecution-${ConnectionId}" in template
    assert "davdeployDiscoveryBrokerRoleArn" in template
    assert "davdeployExecutionBrokerRoleArn" in template
    execution = template.split("  ExecutionRole:", 1)[1].split("  AppRunnerEcrAccessRole:", 1)[0]
    assert "davdeployBoundedAppRunnerExecution" in execution
    assert "iam:PassRole" in execution
    assert "CreateBoundedCustomerWorkloadResources" in execution
    assert "TagNewCustomerWorkloadResources" in execution
    assert "ReconcileTagsOnlyOnOwnedCustomerWorkloadResources" in execution
    assert "logs:TagResource" in execution
    assert "ec2:ModifyVpcAttribute" in execution
    assert "ec2:RevokeSecurityGroupEgress" in execution
    assert "ecr:ListTagsForResource" in execution
    assert "apprunner:ListTagsForResource" in execution
    assert "logs:ListTagsForResource" in execution
    assert "ReconcileOnlyTaggedCustomerWorkloadResources" in execution
    assert "logs:PutRetentionPolicy" in execution
    assert "CreateOnlyAppRunnerServiceLinkedRoles" in execution
    assert "iam:CreateServiceLinkedRole" in execution
    assert "iam:AWSServiceName:" in execution
    assert "- apprunner.amazonaws.com" in execution
    assert "- networking.apprunner.amazonaws.com" in execution
    assert "aws:RequestedRegion: !Ref AWS::Region" in execution
    assert "aws:RequestTag/ConnectionId" in execution
    assert "aws:ResourceTag/ConnectionId" in execution
    assert "sts:ExternalId" in execution


def test_live_pricing_evidence_labels_catalog_and_cost_explorer_failures():
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
