from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from botocore.exceptions import ClientError
from davdeploy.domain import (
    BatchPricingUsageAssumptions,
    EcrPricingUsageAssumptions,
    RdsPricingUsageAssumptions,
    VpcPricingUsageAssumptions,
)
from davdeploy.generated_plan_pricing import (
    AwsPriceListCatalog,
    GeneratedPlanPricingEvidence,
    PlanPricingError,
    PlanPricingStatus,
    PriceListUnavailableError,
    TrustedPlanPricingContext,
    evaluate_generated_plan_pricing,
    pricing_evidence_document_is_valid,
    pricing_evidence_is_approval_eligible,
    pricing_evidence_is_fresh,
)

REGION = "us-east-1"
CAPTURED_AT = datetime(2026, 11, 4, 18, 0, tzinfo=UTC)
PERSISTED_CONTEXT_SHA256 = "a" * 64


def rds_values(**overrides):
    values = {
        "engine": "mysql",
        "instance_class": "db.m6g.large",
        "storage_type": "gp3",
        "allocated_storage": 20,
        "multi_az": False,
        "publicly_accessible": False,
        "backup_retention_period": 7,
        "engine_lifecycle_support": "open-source-rds-extended-support-disabled",
        "performance_insights_enabled": False,
        "monitoring_interval": 0,
        "max_allocated_storage": 0,
        "iops": 3000,
        "storage_throughput": 125,
        "kms_key_id": None,
        "enabled_cloudwatch_logs_exports": [],
        "replicate_source_db": None,
        "license_model": "general-public-license",
    }
    values.update(overrides)
    return values


RDS_USAGE = {"monthly_backup_storage_gb_month": {"minimum": 0, "maximum": 10}}
AURORA_USAGE = {
    "monthly_backup_storage_gb_month": None,
    "aurora_monthly_storage_gb_month": {"minimum": 50, "maximum": 100},
    "aurora_monthly_io_requests": {"minimum": 1_000_000, "maximum": 10_000_000},
    "aurora_monthly_backup_overage_gb_month": {"minimum": 0, "maximum": 20},
    "aurora_monthly_secret_api_requests": {"minimum": 50, "maximum": 200},
    "aurora_monthly_inter_az_transfer_gb": {"minimum": 0, "maximum": 0},
    "aurora_monthly_cross_region_transfer_gb": {"minimum": 0, "maximum": 0},
    "aurora_monthly_internet_egress_gb": {"minimum": 0, "maximum": 0},
}


def rds_plan(*, values=None, after_unknown=None):
    return plan(
        resource_type="aws_db_instance",
        resource_values=values or rds_values(),
    ) if after_unknown is None else _rds_plan_with_unknown(values or rds_values(), after_unknown)


def _rds_plan_with_unknown(values, after_unknown):
    document = rds_plan(values=values)
    rds_change = next(item for item in document["resource_changes"] if item["type"] == "aws_db_instance")
    rds_change["change"]["after_unknown"] = after_unknown
    return document


def aurora_values(**overrides):
    values = {
        "engine": "aurora-postgresql",
        "engine_mode": "provisioned",
        "storage_type": "aurora",
        "manage_master_user_password": True,
        "storage_encrypted": True,
        "backup_retention_period": 7,
        "serverlessv2_scaling_configuration": [{
            "min_capacity": 0.5,
            "max_capacity": 2,
            "seconds_until_auto_pause": None,
        }],
        "engine_lifecycle_support": "open-source-rds-extended-support-disabled",
        "enable_http_endpoint": False,
        "kms_key_id": None,
        "master_user_secret_kms_key_id": None,
        "global_cluster_identifier": None,
        "enabled_cloudwatch_logs_exports": [],
    }
    values.update(overrides)
    return values


def aurora_instance_values(**overrides):
    values = {
        "engine": "aurora-postgresql",
        "instance_class": "db.serverless",
        "publicly_accessible": False,
        "monitoring_interval": 0,
        "performance_insights_enabled": False,
    }
    values.update(overrides)
    return values


def aurora_plan(*, cluster=None, instance=None):
    extra = (
        resource("aws_db_subnet_group.database", "aws_db_subnet_group", {"name": "db"}),
        resource("aws_security_group.database", "aws_security_group", {"name": "db"}),
        resource("aws_rds_cluster.this", "aws_rds_cluster", cluster or aurora_values()),
        resource("aws_rds_cluster_instance.writer", "aws_rds_cluster_instance", instance or aurora_instance_values()),
    )
    return plan(resource_type="terraform_data", resource_values={"input": None}, extra_resources=extra)


class FakeRdsPriceList:
    def __init__(self):
        self.calls = []

    def get_products(self, **kwargs):
        self.calls.append(kwargs)
        filters = {item["Field"]: item["Value"] for item in kwargs["Filters"]}
        service = kwargs["ServiceCode"]
        family = filters["productFamily"]
        usage_type = filters.get("usagetype")
        if service == "AWSSecretsManager" and family == "Secret":
            price, unit, sku = "0.40", "Secrets", "aurora-secret"
        elif service == "AWSSecretsManager" and family == "API Request":
            price, unit, sku = "0.000005", "API Requests", "aurora-secret-api"
        elif service != "AmazonRDS":
            raise AssertionError("unexpected pricing service")
        elif family == "ServerlessV2":
            price, unit, sku = "0.12", "ACU-Hr", "aurora-acu"
        elif family == "Database Storage" and usage_type == "Aurora:StorageUsage":
            price, unit, sku = "0.10", "GB-Mo", "aurora-storage"
        elif family == "System Operation":
            price, unit, sku = "0.0000002", "IOs", "aurora-io"
        elif family == "Database Instance":
            price, unit, sku = "0.016", "Hrs", "rds-instance"
        elif family == "Database Storage":
            price, unit, sku = "0.115", "GB-Mo", "rds-gp3"
        elif family == "Storage Snapshot" and usage_type == "Aurora:BackupUsage":
            price, unit, sku = "0.021", "GB-Mo", "aurora-backup"
        elif family == "Storage Snapshot":
            price, unit, sku = "0.095", "GB-Mo", "rds-backup"
        else:
            raise AssertionError("unexpected RDS price family")
        attributes = {key: value for key, value in filters.items() if key != "productFamily"}
        product = {
            "product": {"sku": sku, "productFamily": family, "attributes": attributes},
            "serviceCode": service,
            "publicationDate": "2026-11-13T12:00:00Z",
            "terms": {"OnDemand": {"offer": {
                "sku": sku,
                "effectiveDate": "2026-11-01T00:00:00Z",
                "priceDimensions": {"dimension": {
                    "beginRange": "0", "endRange": "Inf", "unit": unit,
                    "pricePerUnit": {"USD": price},
                }},
            }}},
        }
        if service == "AmazonRDS":
            assert usage_type
        return {"PriceList": [json.dumps(product)]}


class FakeServerlessPriceList:
    def get_products(self, **kwargs):
        filters = {item["Field"]: item["Value"] for item in kwargs["Filters"]}
        service = kwargs["ServiceCode"]
        family = filters["productFamily"]
        if service == "AWSLambda":
            group = filters["group"]
            unit = "Requests" if "Requests" in group else "Lambda-GB-Second"
            price = "0.0000002" if unit == "Requests" else "0.0000166667"
        elif service == "AmazonApiGateway":
            unit, price = "Requests", "0.000001"
        elif service == "AmazonCloudWatch":
            if family == "Data Payload":
                unit, price = "GB", "0.50"
            elif family == "Storage Snapshot":
                unit, price = "GB-Mo", "0.03"
            else:
                raise AssertionError("unexpected CloudWatch price family")
        elif service == "AWSDataTransfer":
            unit, price = "GB", "0.09"
        else:
            raise AssertionError(f"unexpected Price List service {service}")
        attributes = {**filters}
        sku = f"{service}-{filters.get('group', filters.get('operation', 'egress'))}"
        product = {
            "product": {"sku": sku, "productFamily": family, "attributes": attributes},
            "serviceCode": service,
            "publicationDate": "2026-11-13T12:00:00Z",
            "terms": {"OnDemand": {"offer": {
                "sku": sku,
                "effectiveDate": "2026-11-01T00:00:00Z",
                "priceDimensions": {"dimension": {
                    "beginRange": "0", "endRange": "Inf", "unit": unit,
                    "pricePerUnit": {"USD": price},
                }},
            }}},
        }
        return {"PriceList": [json.dumps(product)]}


class FakeBatchPriceList:
    def __init__(self):
        self.calls = []

    def get_products(self, **kwargs):
        self.calls.append(kwargs)
        filters = {item["Field"]: item["Value"] for item in kwargs["Filters"]}
        if kwargs["ServiceCode"] == "AmazonECR":
            sku, unit, price = "ecr-standard-storage", "GB-Mo", "0.10"
            attributes = {key: value for key, value in filters.items() if key != "productFamily"}
            product = {
                "product": {
                    "sku": sku,
                    "productFamily": "EC2 Container Registry",
                    "attributes": attributes,
                },
                "serviceCode": "AmazonECR",
                "publicationDate": "2026-11-13T12:00:00Z",
                "terms": {"OnDemand": {"offer": {
                    "sku": sku,
                    "effectiveDate": "2026-11-01T00:00:00Z",
                    "priceDimensions": {"dimension": {
                        "beginRange": "0", "endRange": "Inf", "unit": unit,
                        "pricePerUnit": {"USD": price},
                    }},
                }}},
            }
            return {"PriceList": [json.dumps(product)]}
        if kwargs["ServiceCode"] == "AmazonCloudWatch":
            family = filters["productFamily"]
            if family == "Data Payload":
                unit, price, sku = "GB", "0.50", "batch-log-ingestion"
            elif family == "Storage Snapshot":
                unit, price, sku = "GB-Mo", "0.03", "batch-log-storage"
            else:
                raise AssertionError("unexpected CloudWatch price family")
            product = {
                "product": {
                    "sku": sku,
                    "productFamily": family,
                    "attributes": {**filters},
                },
                "serviceCode": "AmazonCloudWatch",
                "publicationDate": "2026-11-13T12:00:00Z",
                "terms": {"OnDemand": {"offer": {
                    "sku": sku,
                    "effectiveDate": "2026-11-01T00:00:00Z",
                    "priceDimensions": {"dimension": {
                        "beginRange": "0", "endRange": "Inf", "unit": unit,
                        "pricePerUnit": {"USD": price},
                    }},
                }}},
            }
            return {"PriceList": [json.dumps(product)]}
        dimension = "vcpu" if "cputype" in filters else "memory"
        unit = "Hrs"
        price = "0.04048" if dimension == "vcpu" else "0.004445"
        attrs = {
            "productFamily": "Compute",
            "regionCode": REGION,
            "cputype": "perCPU",
            "memorytype": "perGB",
            "usagetype": (
                "USE1-Fargate-vCPU-Hours:perCPU"
                if dimension == "vcpu"
                else "USE1-Fargate-GB-Hours"
            ),
            "tenancy": "Shared",
        }
        sku = f"batch-fargate-{dimension}"
        product = {
            "product": {"sku": sku, "productFamily": "Compute", "attributes": attrs},
            "serviceCode": "AmazonECS",
            "publicationDate": "2026-11-13T12:00:00Z",
            "terms": {"OnDemand": {"offer": {
                "sku": sku,
                "effectiveDate": "2026-11-01T00:00:00Z",
                "priceDimensions": {"dimension": {
                    "beginRange": "0", "endRange": "Inf", "unit": unit,
                    "pricePerUnit": {"USD": price},
                }},
            }}},
        }
        return {"PriceList": [json.dumps(product)]}


class MissingBatchCloudWatchPriceList(FakeBatchPriceList):
    def get_products(self, **kwargs):
        if kwargs["ServiceCode"] == "AmazonCloudWatch":
            self.calls.append(kwargs)
            return {"PriceList": []}
        return super().get_products(**kwargs)


class MissingEcrPriceList(FakeBatchPriceList):
    def get_products(self, **kwargs):
        if kwargs["ServiceCode"] == "AmazonECR":
            self.calls.append(kwargs)
            return {"PriceList": []}
        return super().get_products(**kwargs)


def ebs_values(**overrides):
    values = {
        "type": "gp3",
        "size": 50,
        "iops": 3000,
        "throughput": 125,
        "encrypted": True,
        "kms_key_id": None,
    }
    values.update(overrides)
    return values


def resource(address, resource_type, values):
    return {"address": address, "mode": "managed", "type": resource_type, "values": values}


def change(address, resource_type, values, *, after_unknown=None):
    return {
        "address": address,
        "type": resource_type,
        "change": {
            "actions": ["create"],
            "after": values,
            "after_unknown": after_unknown
            if after_unknown is not None
            else {key: False for key in values},
        },
    }


def plan(
    *, region=REGION, resource_values=None, resource_type="aws_ebs_volume", extra_resources=()
):
    address = f"{resource_type}.data"
    values = resource_values or ebs_values()
    resources = [resource(address, resource_type, values), *extra_resources]
    changes = [change(address, resource_type, values)]
    changes.extend(
        change(item["address"], item["type"], item["values"]) for item in extra_resources
    )
    resources.append(resource("terraform_data.account_guard", "terraform_data", {"input": None}))
    changes.append(change("terraform_data.account_guard", "terraform_data", {"input": None}))
    return {
        "format_version": "1.2",
        "applyable": True,
        "errored": False,
        "configuration": {
            "provider_config": {"aws": {"expressions": {"region": {"constant_value": region}}}}
        },
        "planned_values": {"root_module": {"resources": resources}},
        "resource_changes": changes,
    }


def s3_bucket_plan(*, values=None):
    bucket_values = {
        "bucket": "davdeploy-pricing-test",
        "object_lock_enabled": False,
        "object_lock_configuration": None,
    }
    if values:
        bucket_values.update(values)
    return plan(
        resource_type="terraform_data",
        resource_values={"input": None},
        extra_resources=(resource("aws_s3_bucket.store", "aws_s3_bucket", bucket_values),)
    )


def price_product(
    *,
    region=REGION,
    price="0.08",
    unit="GB-Mo",
    tiers=None,
    sku="sku-gp3",
    effective_at="2026-11-01T00:00:00Z",
):
    price_dimensions = tiers or {
        "dimension": {
            "beginRange": "0",
            "endRange": "Inf",
            "unit": unit,
            "pricePerUnit": {"USD": price},
        }
    }
    return json.dumps(
        {
            "product": {
                "sku": sku,
                "productFamily": "Storage",
                "attributes": {
                    "regionCode": region,
                    "volumeApiName": "gp3",
                },
            },
            "serviceCode": "AmazonEC2",
            "publicationDate": "2026-11-03T12:00:00Z",
            "terms": {
                "OnDemand": {
                    "offer": {
                        "sku": sku,
                        "effectiveDate": effective_at,
                        "priceDimensions": price_dimensions,
                    }
                }
            },
        }
    )


class FakePriceList:
    def __init__(self, products=None, *, error=None, next_token=None):
        self.products = products
        self.error = error
        self.next_token = next_token
        self.calls = []

    def get_products(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        region = next(item["Value"] for item in kwargs["Filters"] if item["Field"] == "regionCode")
        products = self.products if self.products is not None else [price_product(region=region)]
        return {"PriceList": products, "NextToken": self.next_token}


class FakeVpcPriceList:
    def __init__(self):
        self.calls = []

    def get_products(self, **kwargs):
        self.calls.append(kwargs)
        filters = {item["Field"]: item["Value"] for item in kwargs["Filters"]}
        service = kwargs["ServiceCode"]
        if service == "AmazonEC2" and filters.get("groupDescription") == "Hourly charge for NAT Gateways":
            family, unit, price, sku = "NAT Gateway", "Hrs", "0.045", "nat-hours"
        elif service == "AmazonEC2" and "per GB data processed by NatGateways" in filters.get("groupDescription", ""):
            family, unit, price, sku = "NAT Gateway", "GB", "0.045", "nat-bytes"
        elif service == "AmazonVPC":
            family, unit, price, sku = None, "Hrs", "0.005", "public-ipv4"
        elif service == "AWSDataTransfer" and filters.get("transferType") == "IntraRegion":
            family, unit, price, sku = "Data Transfer", "GB", "0.01", "regional-transfer"
        elif service == "AWSDataTransfer":
            family, unit, price, sku = "Data Transfer", "GB", "0.09", "internet-egress"
        else:
            raise AssertionError(f"unexpected VPC pricing query: {service} {filters}")
        attributes = {key: value for key, value in filters.items() if key != "productFamily"}
        product = {
            "product": {"sku": sku, "productFamily": family, "attributes": attributes},
            "serviceCode": service,
            "publicationDate": "2026-11-13T12:00:00Z",
            "terms": {"OnDemand": {"offer": {
                "sku": sku,
                "effectiveDate": "2026-11-01T00:00:00Z",
                "priceDimensions": {"dimension": {
                    "beginRange": "0", "endRange": "Inf", "unit": unit,
                    "pricePerUnit": {"USD": price},
                }},
            }}},
        }
        return {"PriceList": [json.dumps(product)]}


class MissingVpcPriceList:
    def get_products(self, **kwargs):
        return {"PriceList": []}


class FakeS3PriceList:
    def __init__(self):
        self.calls = []

    def get_products(self, **kwargs):
        self.calls.append(kwargs)
        filters = {item["Field"]: item["Value"] for item in kwargs["Filters"]}
        service = kwargs["ServiceCode"]
        family = filters["productFamily"]
        if service == "AmazonS3" and family == "Storage":
            attributes = {"regionCode": REGION, "storageClass": "General Purpose", "volumeType": "Standard"}
            sku = "s3-storage"
            dimensions = {
                "first": {"beginRange": "0", "endRange": "51200", "unit": "GB-Mo", "pricePerUnit": {"USD": "0.023"}},
                "second": {"beginRange": "51200", "endRange": "512000", "unit": "GB-Mo", "pricePerUnit": {"USD": "0.022"}},
                "third": {"beginRange": "512000", "endRange": "Inf", "unit": "GB-Mo", "pricePerUnit": {"USD": "0.021"}},
            }
        elif service == "AmazonS3" and family == "API Request":
            tier = 1 if filters["group"] == "S3-API-Tier1" else 2
            attributes = {"regionCode": REGION, "group": f"S3-API-Tier{tier}"}
            sku, unit, price = (
                f"s3-request-{tier}", "Requests", "0.000005" if tier == 1 else "0.0000004"
            )
            begin, end = "0", "Inf"
            dimensions = {"dimension": {
                "beginRange": begin, "endRange": end, "unit": unit,
                "pricePerUnit": {"USD": price},
            }}
        elif service == "AWSDataTransfer":
            attributes = {"fromRegionCode": REGION, "toLocation": "External", "transferType": "AWS Outbound"}
            sku, unit, price, begin, end = "egress", "GB", "0.09", "0", "10240"
            dimensions = {"dimension": {
                "beginRange": begin, "endRange": end, "unit": unit,
                "pricePerUnit": {"USD": price},
            }}
        else:
            raise AssertionError("unexpected pricing query")
        product = {
            "product": {"sku": sku, "productFamily": family, "attributes": attributes},
            "serviceCode": service,
            "publicationDate": "2026-11-13T12:00:00Z",
            "terms": {"OnDemand": {"offer": {
                "sku": sku,
                "effectiveDate": "2026-11-01T00:00:00Z",
                "priceDimensions": dimensions,
            }}},
        }
        return {"PriceList": [json.dumps(product)]}


class MissingS3PriceList:
    def get_products(self, **kwargs):
        return {"PriceList": []}


def evaluate(
    document=None,
    *,
    client=None,
    budget=None,
    declared_budget=None,
    declared_currency=None,
    currency="USD",
    context_digest=PERSISTED_CONTEXT_SHA256,
    usage_assumptions=None,
    sqs_usage_assumptions=None,
    rds_usage_assumptions=None,
    serverless_usage_assumptions=None,
    dynamodb_usage_assumptions=None,
    vpc_usage_assumptions=None,
    batch_usage_assumptions=None,
    ecr_usage_assumptions=None,
    catalog_client=None,
):
    client = catalog_client or client or FakePriceList()
    return (
        evaluate_generated_plan_pricing(
            document or plan(),
            trusted_context=TrustedPlanPricingContext(
                region=REGION,
                currency=currency,
                monthly_budget_minor=budget,
                persisted_context_sha256=context_digest,
                usage_assumptions=usage_assumptions,
                sqs_usage_assumptions=sqs_usage_assumptions,
                rds_usage_assumptions=rds_usage_assumptions,
                serverless_usage_assumptions=serverless_usage_assumptions,
                dynamodb_usage_assumptions=dynamodb_usage_assumptions,
                vpc_usage_assumptions=vpc_usage_assumptions,
                batch_usage_assumptions=batch_usage_assumptions,
                ecr_usage_assumptions=ecr_usage_assumptions,
            ),
            proposal_declared_budget_minor=declared_budget,
            proposal_declared_currency=declared_currency,
            catalog=AwsPriceListCatalog(client, cache_ttl_seconds=0),
            captured_at=CAPTURED_AT,
        ),
        client,
    )


def test_gp3_price_uses_exact_region_and_known_gib_month_quantity():
    result, client = evaluate(budget=400)

    assert result.status == PlanPricingStatus.COMPLETE
    assert result.monthly_low_minor == result.monthly_high_minor == 400
    assert result.within_budget is True
    assert result.approval_eligible is True
    assert pricing_evidence_is_approval_eligible(
        result.as_manifest_document(),
        trusted_context=TrustedPlanPricingContext(
            REGION, "USD", 400, PERSISTED_CONTEXT_SHA256
        ),
        now=CAPTURED_AT,
    )
    assert result.lines[0].quantity == 50
    assert result.lines[0].unit == "GB-Mo"
    assert result.lines[0].catalog_sku == "sku-gp3"
    assert result.lines[0].catalog_effective_at == "2026-11-01T00:00:00Z"
    assert result.lines[0].catalog_published_at == "2026-11-03T12:00:00Z"
    assert result.lines[0].catalog_product_sha256
    assert result.budget_source == "PERSISTED_CUSTOMER_CONTEXT"
    assert result.persisted_context_sha256 == PERSISTED_CONTEXT_SHA256
    assert (
        result.pricing_context_sha256
        == TrustedPlanPricingContext(
            region=REGION,
            currency="USD",
            monthly_budget_minor=400,
            persisted_context_sha256=PERSISTED_CONTEXT_SHA256,
        ).pricing_context_sha256
    )
    assert "not a bill forecast or a spend cap" in result.estimate_disclaimer
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["ServiceCode"] == "AmazonEC2"
    assert call["MaxResults"] == 100
    assert {item["Field"]: item["Value"] for item in call["Filters"]} == {
        "productFamily": "Storage",
        "volumeApiName": "gp3",
        "regionCode": REGION,
    }
    assert "cost_explorer" not in repr(call).lower()


def test_v2_saved_pricing_evidence_remains_readable_and_approval_compatible():
    result, _ = evaluate(budget=400)
    legacy = result.as_manifest_document()
    legacy["version"] = 2
    legacy.pop("sqs_usage_assumptions")
    legacy.pop("rds_usage_assumptions")
    legacy.pop("serverless_usage_assumptions")
    legacy.pop("dynamodb_usage_assumptions")
    legacy.pop("vpc_usage_assumptions")
    legacy.pop("batch_usage_assumptions")
    legacy.pop("ecr_usage_assumptions")
    for line in legacy["lines"]:
        for field in (
            "quantity_max",
            "monthly_cost_max_minor",
            "unit_price_low_usd",
            "unit_price_low_source_url",
            "low_cost_quantity",
        ):
            line.pop(field)
    unsigned = {key: value for key, value in legacy.items() if key != "evidence_sha256"}
    legacy["evidence_sha256"] = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()

    parsed = GeneratedPlanPricingEvidence.from_manifest_document(legacy)

    assert parsed.status == PlanPricingStatus.COMPLETE
    assert pricing_evidence_is_approval_eligible(
        legacy,
        trusted_context=TrustedPlanPricingContext(
            REGION, "USD", 400, PERSISTED_CONTEXT_SHA256
        ),
        now=CAPTURED_AT,
    )


@pytest.mark.parametrize(("budget", "eligible"), [(400, True), (399, False)])
def test_budget_gate_uses_conservative_estimate(budget, eligible):
    result, _ = evaluate(budget=budget)

    assert result.status == PlanPricingStatus.COMPLETE
    assert result.within_budget is eligible
    assert result.approval_eligible is eligible
    if not eligible:
        assert {item.code for item in result.findings} == {"monthly_budget_exceeded"}


def test_fractional_cent_price_rounds_estimate_up():
    result, _ = evaluate(
        plan(resource_values=ebs_values(size=1)),
        client=FakePriceList([price_product(price="0.0801")]),
    )

    assert result.status == PlanPricingStatus.COMPLETE
    assert result.monthly_low_minor == result.monthly_high_minor == 9


def test_nova_budget_conflict_with_persisted_customer_budget_blocks_approval():
    client = FakePriceList()
    result, _ = evaluate(budget=400, declared_budget=401, client=client)

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.approval_eligible is False
    assert result.monthly_budget_minor == 400
    assert result.proposal_declared_budget_minor == 401
    assert {item.code for item in result.findings} == {"proposal_budget_context_mismatch"}
    assert client.calls == []


def test_nova_currency_conflict_with_persisted_customer_currency_blocks_approval():
    client = FakePriceList()
    result, _ = evaluate(declared_currency="EUR", client=client)

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.approval_eligible is False
    assert result.proposal_declared_currency == "EUR"
    assert {item.code for item in result.findings} == {"proposal_currency_context_mismatch"}
    assert client.calls == []


def test_absent_nova_budget_does_not_override_trusted_persisted_budget():
    result, _ = evaluate(budget=399)

    assert result.monthly_budget_minor == 399
    assert result.proposal_declared_budget_minor is None
    assert result.within_budget is False
    assert result.approval_eligible is False


def test_trusted_pricing_context_is_extracted_only_from_integrity_checked_revision():
    usage = {
        "monthly_storage_gb": {"minimum": 10, "maximum": 20},
        "monthly_put_copy_post_list_requests": {"minimum": 100, "maximum": 200},
        "monthly_get_requests": {"minimum": 300, "maximum": 400},
        "monthly_internet_egress_gb": {"minimum": 0, "maximum": 5},
    }
    revision = {
        "target": {"provider": "aws", "region": REGION},
        "application_analysis": {
            "workload_spec": {
                "monthly_budget_usd": 500,
                "pricing_usage_assumptions": usage,
            },
        },
    }
    revision_sha256 = hashlib.sha256(
        json.dumps(revision, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    context = TrustedPlanPricingContext.from_persisted_revision(
        revision, expected_sha256=revision_sha256
    )

    assert context.region == REGION
    assert context.currency == "USD"
    assert context.monthly_budget_minor == 50_000
    assert context.persisted_context_sha256 == revision_sha256
    assert context.usage_assumptions == usage
    with pytest.raises(ValueError, match="integrity check"):
        TrustedPlanPricingContext.from_persisted_revision(
            {**revision, "target": {"provider": "aws", "region": "eu-west-1"}},
            expected_sha256=revision_sha256,
        )


def test_sqs_usage_is_extracted_from_integrity_checked_customer_revision():
    usage = {
        "monthly_standard_request_units": {"minimum": 100, "maximum": 200},
        "monthly_fifo_request_units": {"minimum": 0, "maximum": 0},
        "monthly_fair_queue_request_units": {"minimum": 0, "maximum": 0},
        "monthly_cross_region_transfer_gb": {"minimum": 0, "maximum": 0},
        "monthly_internet_egress_gb": {"minimum": 0, "maximum": 0},
    }
    revision = {
        "target": {"provider": "aws", "region": REGION},
        "application_analysis": {"workload_spec": {"sqs_pricing_usage_assumptions": usage}},
    }
    revision_sha256 = hashlib.sha256(
        json.dumps(revision, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    context = TrustedPlanPricingContext.from_persisted_revision(
        revision, expected_sha256=revision_sha256
    )
    assert context.sqs_usage_assumptions == usage
    with pytest.raises(ValueError, match="integrity check"):
        TrustedPlanPricingContext.from_persisted_revision(
            {**revision, "application_analysis": {"workload_spec": {}}},
            expected_sha256=revision_sha256,
        )



def test_rds_usage_is_extracted_from_integrity_checked_customer_revision():
    usage = {"monthly_backup_storage_gb_month": {"minimum": 2, "maximum": 20}}
    revision = {
        "target": {"provider": "aws", "region": REGION},
        "application_analysis": {
            "workload_spec": {"rds_pricing_usage_assumptions": usage}
        },
    }
    revision_sha256 = hashlib.sha256(
        json.dumps(revision, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    context = TrustedPlanPricingContext.from_persisted_revision(
        revision, expected_sha256=revision_sha256
    )

    assert context.rds_usage_assumptions == usage


def test_legacy_rds_context_survives_default_null_aurora_fields_in_serialized_workload():
    expanded_usage = RdsPricingUsageAssumptions.model_validate(RDS_USAGE).model_dump(mode="json")
    revision = {
        "target": {"provider": "aws", "region": REGION},
        "application_analysis": {
            "workload_spec": {"rds_pricing_usage_assumptions": expanded_usage}
        },
    }
    revision_sha256 = hashlib.sha256(
        json.dumps(revision, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    context = TrustedPlanPricingContext.from_persisted_revision(
        revision, expected_sha256=revision_sha256
    )

    assert context.rds_usage_assumptions == expanded_usage
    result, _ = evaluate(
        rds_plan(), rds_usage_assumptions=context.rds_usage_assumptions,
        context_digest=revision_sha256, catalog_client=FakeRdsPriceList(),
    )
    assert result.status == PlanPricingStatus.COMPLETE
    assert pricing_evidence_is_approval_eligible(
        result.as_manifest_document(),
        trusted_context=context,
        now=CAPTURED_AT,
    )


def test_aurora_usage_is_extracted_and_bound_to_integrity_checked_revision():
    revision = {
        "target": {"provider": "aws", "region": REGION},
        "application_analysis": {
            "workload_spec": {"rds_pricing_usage_assumptions": AURORA_USAGE}
        },
    }
    revision_sha256 = hashlib.sha256(
        json.dumps(revision, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    context = TrustedPlanPricingContext.from_persisted_revision(
        revision, expected_sha256=revision_sha256
    )
    assert context.rds_usage_assumptions == AURORA_USAGE
    changed = {**AURORA_USAGE, "aurora_monthly_storage_gb_month": {"minimum": 20, "maximum": 50}}
    assert TrustedPlanPricingContext(
        REGION, "USD", None, revision_sha256, rds_usage_assumptions=changed
    ).pricing_context_sha256 != context.pricing_context_sha256
    assert context.pricing_context_sha256 != TrustedPlanPricingContext(
        REGION, "USD", None, revision_sha256
    ).pricing_context_sha256
    with pytest.raises(ValueError, match="integrity check"):
        TrustedPlanPricingContext.from_persisted_revision(
            {
                **revision,
                "application_analysis": {"workload_spec": {}},
            },
            expected_sha256=revision_sha256,
        )


def test_serverless_usage_is_extracted_and_bound_to_trusted_revision_digest():
    usage = serverless_usage()
    revision = {
        "target": {"provider": "aws", "region": REGION},
        "application_analysis": {
            "workload_spec": {"serverless_pricing_usage_assumptions": usage}
        },
    }
    revision_sha256 = hashlib.sha256(
        json.dumps(revision, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    context = TrustedPlanPricingContext.from_persisted_revision(
        revision, expected_sha256=revision_sha256
    )
    assert context.serverless_usage_assumptions == usage
    assert context.pricing_context_sha256 != TrustedPlanPricingContext(
        REGION, "USD", None, revision_sha256
    ).pricing_context_sha256
    with pytest.raises(ValueError, match="integrity check"):
        TrustedPlanPricingContext.from_persisted_revision(
            {**revision, "application_analysis": {"workload_spec": {}}},
            expected_sha256=revision_sha256,
        )


def test_approved_revision_without_a_budget_has_no_trusted_ceiling():
    revision = {
        "target": {"provider": "aws", "region": REGION},
        "application_analysis": {"workload_spec": {}},
    }
    revision_sha256 = hashlib.sha256(
        json.dumps(revision, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    context = TrustedPlanPricingContext.from_persisted_revision(
        revision, expected_sha256=revision_sha256
    )

    assert context.monthly_budget_minor is None


def test_delete_transition_is_recorded_and_not_misread_as_missing_final_state():
    document = plan()
    ebs = document["planned_values"]["root_module"]["resources"].pop(0)
    ebs_change = document["resource_changes"].pop(0)
    ebs_change["change"] = {
        "actions": ["delete"],
        "before": ebs["values"],
        "after": None,
        "after_unknown": False,
    }
    document["resource_changes"].append(ebs_change)

    result, client = evaluate(document, client=FakePriceList())

    assert result.status == PlanPricingStatus.COMPLETE
    assert result.monthly_low_minor == result.monthly_high_minor == 0
    assert result.approval_eligible is True
    assert result.transitions[0].address == ebs["address"]
    assert result.transitions[0].treatment == "REMOVED_FROM_POST_APPLY_STEADY_STATE"
    assert client.calls == []


def test_replacement_prices_final_state_and_records_transition_exclusion():
    document = plan()
    ebs_change = document["resource_changes"][0]
    ebs_change["change"]["actions"] = ["delete", "create"]

    result, _ = evaluate(document)

    assert result.status == PlanPricingStatus.COMPLETE
    assert result.monthly_low_minor == result.monthly_high_minor == 400
    assert result.transitions[0].treatment == "REPLACEMENT_TRANSITION_CHARGES_EXCLUDED"
    assert "excludes transition-period charges" in result.estimate_disclaimer.lower()


def test_aws_change_without_final_state_blocks_pricing():
    document = plan()
    document["planned_values"]["root_module"]["resources"].pop(0)
    result, _ = evaluate(document)

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.approval_eligible is False
    assert {item.code for item in result.findings} == {"resource_final_state_missing"}


def test_final_aws_resource_without_change_record_blocks_pricing():
    document = plan()
    document["resource_changes"].pop(0)
    result, _ = evaluate(document)

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.approval_eligible is False
    assert {item.code for item in result.findings} == {"resource_change_missing"}


def test_region_mismatch_fails_before_catalog_call():
    client = FakePriceList()
    result, _ = evaluate(plan(region="eu-west-1"), client=client)

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.approval_eligible is False
    assert {item.code for item in result.findings} == {"plan_region_mismatch"}
    assert client.calls == []


@pytest.mark.parametrize(
    ("products", "next_token"),
    [
        ([], None),
        ([price_product(), price_product(sku="second")], None),
        ([price_product()], "more"),
    ],
)
def test_missing_ambiguous_or_truncated_price_results_fail_closed(products, next_token):
    client = FakePriceList(products, next_token=next_token)
    result, _ = evaluate(client=client)

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.approval_eligible is False
    assert {item.code for item in result.findings} == {"regional_price_ambiguous"}


@pytest.mark.parametrize(
    "product",
    [
        price_product(region="eu-west-1"),
        price_product(price="not-a-number"),
        price_product(price="0"),
        price_product(unit="GB"),
        price_product(effective_at="not-a-timestamp"),
        price_product(effective_at="2026-11-01T00:00:00"),
        price_product(
            tiers={
                "first": {
                    "beginRange": "0",
                    "endRange": "10",
                    "unit": "GB-Mo",
                    "pricePerUnit": {"USD": "0.08"},
                },
                "second": {
                    "beginRange": "10",
                    "endRange": "Inf",
                    "unit": "GB-Mo",
                    "pricePerUnit": {"USD": "0.06"},
                },
            }
        ),
    ],
)
def test_wrong_region_or_ambiguous_unit_price_is_unreviewable(product):
    result, _ = evaluate(client=FakePriceList([product]))

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.approval_eligible is False
    assert {item.code for item in result.findings} == {"regional_price_ambiguous"}


def test_price_api_error_is_unavailable_and_never_uses_fixture_price():
    client = FakePriceList(
        error=ClientError({"Error": {"Code": "AccessDeniedException"}}, "GetProducts")
    )
    result, _ = evaluate(client=client)

    assert result.status == PlanPricingStatus.UNAVAILABLE
    assert result.monthly_low_minor is None
    assert result.monthly_high_minor is None
    assert result.approval_eligible is False
    assert result.findings[0].code == "regional_price_lookup_unavailable"


@pytest.mark.parametrize(
    ("resource_type", "values"),
    [
        ("aws_s3_bucket", {"bucket": "has-variable-storage-and-requests"}),
        ("aws_instance", {"instance_type": "t4g.small", "ami": "ami-x"}),
        ("aws_ebs_volume", ebs_values(type="gp2")),
        ("aws_ebs_volume", ebs_values(iops=6000)),
        ("aws_ebs_volume", ebs_values(throughput=250)),
        ("aws_ebs_volume", ebs_values(kms_key_id="arn:aws:kms:us-east-1:123456789012:key/abc")),
    ],
)
def test_unpriced_variable_or_custom_storage_resources_block_approval(resource_type, values):
    client = FakePriceList()
    result, _ = evaluate(plan(resource_type=resource_type, resource_values=values), client=client)

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.approval_eligible is False
    assert result.monthly_low_minor is None
    assert client.calls == []
    if resource_type == "aws_internet_gateway":
        assert result.findings[0].code == "resource_pricing_unavailable"


@pytest.mark.parametrize(
    "unknowns",
    [
        {"size": True},
        {"type": True},
        {"iops": True},
        {"throughput": True},
        {"kms_key_id": True},
        ["malformed"],
    ],
)
def test_unknown_or_malformed_price_drivers_block_approval(unknowns):
    document = plan()
    volume_change = document["resource_changes"][0]
    volume_change["change"]["after_unknown"] = unknowns
    client = FakePriceList()
    result, _ = evaluate(document, client=client)

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.approval_eligible is False
    assert client.calls == []


def test_zero_charge_trusted_guard_and_network_resources_do_not_make_api_calls():
    document = {
        "applyable": True,
        "errored": False,
        "configuration": {
            "provider_config": {"aws": {"expressions": {"region": {"constant_value": REGION}}}}
        },
        "planned_values": {
            "root_module": {
                "resources": [
                    resource("terraform_data.account_guard", "terraform_data", {"input": None}),
                    resource("aws_vpc.main", "aws_vpc", {"cidr_block": "10.0.0.0/16"}),
                ]
            }
        },
        "resource_changes": [
            change("terraform_data.account_guard", "terraform_data", {"input": None}),
            change("aws_vpc.main", "aws_vpc", {"cidr_block": "10.0.0.0/16"}),
        ],
    }
    client = FakePriceList()
    result, _ = evaluate(document, client=client)

    assert result.status == PlanPricingStatus.COMPLETE
    assert result.monthly_low_minor == result.monthly_high_minor == 0
    assert result.approval_eligible is True
    assert result.lines == ()
    assert client.calls == []


def test_public_list_price_evidence_digest_is_deterministic_and_plan_bound():
    first, _ = evaluate(budget=500)
    repeated, _ = evaluate(budget=500)
    changed_plan, _ = evaluate(plan(resource_values=ebs_values(size=51)), budget=500)

    assert first.evidence_sha256 == repeated.evidence_sha256
    assert first.evidence_sha256 != changed_plan.evidence_sha256
    assert first.plan_json_sha256 != changed_plan.plan_json_sha256
    manifest = first.as_manifest_document()
    assert pricing_evidence_document_is_valid(manifest) is True
    assert manifest["evidence_sha256"] == first.evidence_sha256
    assert manifest["budget_source"] == "PERSISTED_CUSTOMER_CONTEXT"
    assert manifest["proposal_declared_currency"] is None
    assert manifest["persisted_context_sha256"] == PERSISTED_CONTEXT_SHA256
    assert manifest["pricing_context_sha256"] == first.pricing_context_sha256
    unsigned_manifest = {key: value for key, value in manifest.items() if key != "evidence_sha256"}
    encoded = json.dumps(
        unsigned_manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    assert hashlib.sha256(encoded.encode()).hexdigest() == first.evidence_sha256


def test_pricing_evidence_manifest_digest_rejects_changed_cost_or_context():
    result, _ = evaluate(budget=500)
    manifest = result.as_manifest_document()

    changed_cost = {**manifest, "monthly_high_minor": 1}
    changed_context = {**manifest, "pricing_context_sha256": "f" * 64}

    assert pricing_evidence_document_is_valid(changed_cost) is False
    assert pricing_evidence_document_is_valid(changed_context) is False
    assert pricing_evidence_document_is_valid(None) is False


def test_usage_assumptions_are_carried_in_digest_bound_pricing_evidence():
    assumptions = {
        "monthly_storage_gb": {"minimum": 10, "maximum": 20},
        "monthly_put_copy_post_list_requests": {"minimum": 100, "maximum": 200},
        "monthly_get_requests": {"minimum": 300, "maximum": 400},
        "monthly_internet_egress_gb": {"minimum": 0, "maximum": 5},
    }
    result, _ = evaluate(
        s3_bucket_plan(), budget=500, usage_assumptions=assumptions,
        catalog_client=FakeS3PriceList(),
    )
    manifest = result.as_manifest_document()
    changed_context = TrustedPlanPricingContext(
        REGION,
        "USD",
        500,
        PERSISTED_CONTEXT_SHA256,
        {**assumptions, "monthly_get_requests": {"minimum": 300, "maximum": 401}},
    )

    assert result.status == PlanPricingStatus.COMPLETE
    assert result.usage_assumptions == assumptions
    assert manifest["usage_assumptions"] == assumptions
    assert pricing_evidence_document_is_valid(manifest)
    assert result.safe_summary()["usage_assumptions"] == assumptions
    parsed = GeneratedPlanPricingEvidence.from_manifest_document(manifest)
    assert parsed.usage_assumptions == assumptions
    assert result.monthly_low_minor == 21
    assert result.monthly_high_minor == 93
    assert len(result.lines) == 4
    assert all(line.quantity_max is not None for line in result.lines)
    assert all(line.catalog_product_sha256 for line in result.lines)
    egress_line = next(line for line in result.lines if "transfer out" in line.description)
    assert egress_line.unit_price_usd == "0.09"
    assert egress_line.unit_price_low_usd == "0.05"
    assert egress_line.unit_price_low_source_url == "https://aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer"
    assert egress_line.low_cost_quantity == 0
    assert pricing_evidence_is_approval_eligible(
        manifest,
        trusted_context=TrustedPlanPricingContext(
            REGION, "USD", 500, PERSISTED_CONTEXT_SHA256, assumptions
        ),
        now=CAPTURED_AT,
    )
    assert not pricing_evidence_is_approval_eligible(
        manifest, trusted_context=changed_context, now=CAPTURED_AT
    )

    malformed = {**manifest, "usage_assumptions": {**assumptions, "unit_price_usd": "0"}}
    unsigned = {key: value for key, value in malformed.items() if key != "evidence_sha256"}
    malformed["evidence_sha256"] = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()
    with pytest.raises(PlanPricingError, match="pricing evidence fields are invalid"):
        GeneratedPlanPricingEvidence.from_manifest_document(malformed)


def test_s3_without_usage_assumptions_remains_incomplete_and_skips_catalog():
    client = FakeS3PriceList()
    result, _ = evaluate(s3_bucket_plan(), catalog_client=client)

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.approval_eligible is False
    assert {finding.code for finding in result.findings} == {"s3_usage_assumptions_missing"}
    assert client.calls == []


def nat_gateway_plan(*, connectivity_type="public", extra_resources=()):
    nat = {
        "connectivity_type": connectivity_type,
        "allocation_id": "eipalloc-nat-test",
        "secondary_allocation_ids": [],
    }
    eip = {"id": "eipalloc-nat-test", "domain": "vpc"}
    return plan(
        resource_type="terraform_data",
        resource_values={"input": None},
        extra_resources=(
            resource("aws_eip.nat", "aws_eip", eip),
            resource("aws_nat_gateway.nat", "aws_nat_gateway", nat),
            *extra_resources,
        ),
    )


NAT_USAGE = {
    "nat_gateways": {
        "aws_nat_gateway.nat": {
            "monthly_available_hours": {"minimum": 720, "maximum": 720},
            "monthly_data_processed_gb": {"minimum": 100, "maximum": 100},
            "monthly_internet_egress_gb": {"minimum": 25, "maximum": 25},
            "monthly_cross_az_payload_gb": {"minimum": 10, "maximum": 10},
        }
    }
}


def test_nat_gateway_pricing_covers_hours_processing_ipv4_egress_and_cross_az():
    client = FakeVpcPriceList()
    result, _ = evaluate(
        nat_gateway_plan(), catalog_client=client, vpc_usage_assumptions=NAT_USAGE
    )
    assert result.status == PlanPricingStatus.COMPLETE
    assert result.monthly_low_minor == 4_195
    assert result.monthly_high_minor == 4_295
    assert result.approval_eligible is True
    assert len(result.lines) == 5
    assert len([line for line in result.lines if "public IPv4" in line.description]) == 1
    cross_az = next(line for line in result.lines if "Cross-AZ" in line.description)
    assert cross_az.quantity == cross_az.quantity_max == 20
    assert cross_az.unit_price_usd == "0.01"
    assert all(line.catalog_product_sha256 for line in result.lines)
    manifest = result.as_manifest_document()
    assert manifest["version"] == 10
    assert manifest["vpc_usage_assumptions"] == NAT_USAGE
    assert GeneratedPlanPricingEvidence.from_manifest_document(manifest) == result
    assert pricing_evidence_is_approval_eligible(
        manifest,
        trusted_context=TrustedPlanPricingContext(
            REGION, "USD", None, PERSISTED_CONTEXT_SHA256,
            vpc_usage_assumptions=NAT_USAGE,
        ),
        now=CAPTURED_AT,
    )


def test_complete_vpc_topology_prices_nat_and_treats_internet_gateway_as_zero_direct_charge():
    topology = (
        resource("aws_vpc.main", "aws_vpc", {"id": "vpc-main"}),
        resource("aws_internet_gateway.main", "aws_internet_gateway", {"vpc_id": "vpc-main"}),
        resource("aws_subnet.public", "aws_subnet", {"id": "subnet-public", "vpc_id": "vpc-main"}),
        resource("aws_subnet.private", "aws_subnet", {"id": "subnet-private", "vpc_id": "vpc-main"}),
        resource("aws_route_table.public", "aws_route_table", {"vpc_id": "vpc-main"}),
        resource("aws_route_table.private", "aws_route_table", {"vpc_id": "vpc-main"}),
        resource("aws_route_table_association.public", "aws_route_table_association", {"subnet_id": "subnet-public"}),
        resource("aws_route_table_association.private", "aws_route_table_association", {"subnet_id": "subnet-private"}),
        resource("aws_route.public_default", "aws_route", {"route_table_id": "rtb-public"}),
        resource("aws_route.private_default", "aws_route", {"route_table_id": "rtb-private"}),
    )
    result, _ = evaluate(
        nat_gateway_plan(extra_resources=topology),
        catalog_client=FakeVpcPriceList(),
        vpc_usage_assumptions=NAT_USAGE,
    )

    assert result.status == PlanPricingStatus.COMPLETE
    assert result.approval_eligible is True
    assert not any(finding.code == "resource_pricing_unavailable" for finding in result.findings)


def test_nat_gateway_without_usage_assumptions_blocks_before_price_lookup():
    client = FakeVpcPriceList()
    result, _ = evaluate(nat_gateway_plan(), catalog_client=client)
    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.approval_eligible is False
    assert {finding.code for finding in result.findings} == {"vpc_usage_assumptions_missing"}
    assert client.calls == []


def test_nat_gateway_missing_regional_price_blocks_approval():
    result, _ = evaluate(
        nat_gateway_plan(),
        catalog_client=MissingVpcPriceList(),
        vpc_usage_assumptions=NAT_USAGE,
    )
    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.approval_eligible is False
    assert "regional_price_ambiguous" in {finding.code for finding in result.findings}


def test_nat_gateway_unmatched_elastic_ip_blocks_approval():
    document = nat_gateway_plan()
    extra_eip = resource("aws_eip.unrelated", "aws_eip", {"id": "eipalloc-unrelated", "domain": "vpc"})
    document["planned_values"]["root_module"]["resources"].append(extra_eip)
    document["resource_changes"].append(change(
        "aws_eip.unrelated", "aws_eip", extra_eip["values"]
    ))
    client = FakeVpcPriceList()
    result, _ = evaluate(document, catalog_client=client, vpc_usage_assumptions=NAT_USAGE)
    assert result.status == PlanPricingStatus.INCOMPLETE
    assert "vpc_unbound_public_ipv4" in {finding.code for finding in result.findings}
    assert client.calls == []


def test_nat_gateway_duplicate_known_eip_ids_block_pricing():
    document = nat_gateway_plan()
    duplicate_eip = resource(
        "aws_eip.duplicate", "aws_eip", {"id": "eipalloc-nat-test", "domain": "vpc"}
    )
    document["planned_values"]["root_module"]["resources"].append(duplicate_eip)
    document["resource_changes"].append(
        change("aws_eip.duplicate", "aws_eip", duplicate_eip["values"])
    )
    client = FakeVpcPriceList()

    result, _ = evaluate(
        document, catalog_client=client, vpc_usage_assumptions=NAT_USAGE
    )

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert "vpc_nat_shape_or_usage_unsupported" in {
        finding.code for finding in result.findings
    }
    assert client.calls == []


def test_nat_gateway_unsupported_eip_shape_blocks_pricing():
    client = FakeVpcPriceList()
    result, _ = evaluate(
        nat_gateway_plan(connectivity_type="private"),
        catalog_client=client,
        vpc_usage_assumptions=NAT_USAGE,
    )
    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.approval_eligible is False
    assert "vpc_nat_shape_or_usage_unsupported" in {finding.code for finding in result.findings}
    assert client.calls == []


def test_nat_gateway_unknown_allocation_is_bound_by_configuration_reference():
    document = nat_gateway_plan()
    eip_values = document["planned_values"]["root_module"]["resources"][1]["values"]
    eip_values["id"] = None
    eip_change = next(item for item in document["resource_changes"] if item["type"] == "aws_eip")
    eip_change["change"]["after"]["id"] = None
    eip_change["change"]["after_unknown"]["id"] = True
    nat_values = document["planned_values"]["root_module"]["resources"][2]["values"]
    nat_values["allocation_id"] = None
    nat_change = next(item for item in document["resource_changes"] if item["type"] == "aws_nat_gateway")
    nat_change["change"]["after"]["allocation_id"] = None
    nat_change["change"]["after_unknown"]["allocation_id"] = True
    document["configuration"]["root_module"] = {
        "resources": [
            {"address": "aws_eip.nat", "expressions": {}},
            {"address": "aws_nat_gateway.nat", "expressions": {
                "allocation_id": {
                    "references": ["aws_eip.nat.id", "aws_eip.nat"]
                },
            }},
        ],
        "module_calls": {},
    }
    result, _ = evaluate(
        document, catalog_client=FakeVpcPriceList(), vpc_usage_assumptions=NAT_USAGE
    )
    assert result.status == PlanPricingStatus.COMPLETE


def test_nat_gateway_module_relative_reference_binds_unknown_nat_and_eip_ids():
    document = nat_gateway_plan()
    module_eip_address = "module.network.aws_eip.nat"
    module_nat_address = "module.network.aws_nat_gateway.nat"
    eip_values = document["planned_values"]["root_module"]["resources"][1]["values"]
    eip_values["id"] = None
    nat_values = document["planned_values"]["root_module"]["resources"][2]["values"]
    nat_values["allocation_id"] = None
    for item in document["planned_values"]["root_module"]["resources"]:
        if item["address"] == "aws_eip.nat":
            item["address"] = module_eip_address
        elif item["address"] == "aws_nat_gateway.nat":
            item["address"] = module_nat_address
    for item in document["resource_changes"]:
        if item["address"] == "aws_eip.nat":
            item["address"] = module_eip_address
            item["change"]["after"]["id"] = None
            item["change"]["after_unknown"]["id"] = True
        elif item["address"] == "aws_nat_gateway.nat":
            item["address"] = module_nat_address
            item["change"]["after"]["allocation_id"] = None
            item["change"]["after_unknown"]["allocation_id"] = True
    document["configuration"]["root_module"] = {
        "resources": [],
        "module_calls": {
            "network": {
                "module": {
                    "resources": [
                        {"address": "aws_eip.nat", "expressions": {}},
                        {
                            "address": "aws_nat_gateway.nat",
                            "expressions": {
                                "allocation_id": {
                                    "references": ["aws_eip.nat.id", "aws_eip.nat"]
                                }
                            },
                        },
                    ],
                    "module_calls": {},
                }
            }
        },
    }
    module_usage = {
        "nat_gateways": {
            module_nat_address: NAT_USAGE["nat_gateways"]["aws_nat_gateway.nat"]
        }
    }

    result, _ = evaluate(
        document,
        catalog_client=FakeVpcPriceList(),
        vpc_usage_assumptions=module_usage,
    )

    assert result.status == PlanPricingStatus.COMPLETE
    assert result.approval_eligible is True


def test_nat_gateway_count_instance_resolves_its_configuration_reference():
    document = nat_gateway_plan()
    indexed_eip = "aws_eip.nat[0]"
    indexed_nat = "aws_nat_gateway.nat[0]"
    eip_values = document["planned_values"]["root_module"]["resources"][1]["values"]
    eip_values["id"] = None
    nat_values = document["planned_values"]["root_module"]["resources"][2]["values"]
    nat_values["allocation_id"] = None
    for item in document["planned_values"]["root_module"]["resources"]:
        if item["address"] == "aws_eip.nat":
            item["address"] = indexed_eip
        elif item["address"] == "aws_nat_gateway.nat":
            item["address"] = indexed_nat
    for item in document["resource_changes"]:
        if item["address"] == "aws_eip.nat":
            item["address"] = indexed_eip
            item["change"]["after"]["id"] = None
            item["change"]["after_unknown"]["id"] = True
        elif item["address"] == "aws_nat_gateway.nat":
            item["address"] = indexed_nat
            item["change"]["after"]["allocation_id"] = None
            item["change"]["after_unknown"]["allocation_id"] = True
    document["configuration"]["root_module"] = {
        "resources": [
            {"address": "aws_eip.nat", "expressions": {}},
            {
                "address": "aws_nat_gateway.nat",
                "expressions": {
                    "allocation_id": {
                        "references": ["aws_eip.nat.id", "aws_eip.nat"]
                    }
                },
            },
        ],
        "module_calls": {},
    }
    indexed_usage = {
        "nat_gateways": {
            indexed_nat: NAT_USAGE["nat_gateways"]["aws_nat_gateway.nat"]
        }
    }

    result, _ = evaluate(
        document,
        catalog_client=FakeVpcPriceList(),
        vpc_usage_assumptions=indexed_usage,
    )

    assert result.status == PlanPricingStatus.COMPLETE
    assert result.approval_eligible is True


def test_nat_gateway_unknown_secondary_allocations_block_pricing():
    document = nat_gateway_plan()
    nat_change = next(
        item for item in document["resource_changes"]
        if item["type"] == "aws_nat_gateway"
    )
    nat_change["change"]["after_unknown"]["secondary_allocation_ids"] = True
    client = FakeVpcPriceList()

    result, _ = evaluate(
        document, catalog_client=client, vpc_usage_assumptions=NAT_USAGE
    )

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert "vpc_nat_shape_or_usage_unsupported" in {
        finding.code for finding in result.findings
    }
    assert client.calls == []


def test_nat_gateway_unknown_allocation_with_wrong_reference_blocks_pricing():
    document = nat_gateway_plan()
    nat_values = document["planned_values"]["root_module"]["resources"][2]["values"]
    nat_values["allocation_id"] = None
    nat_change = next(item for item in document["resource_changes"] if item["type"] == "aws_nat_gateway")
    nat_change["change"]["after"]["allocation_id"] = None
    nat_change["change"]["after_unknown"]["allocation_id"] = True
    document["configuration"]["root_module"] = {
        "resources": [
            {"address": "aws_eip.nat", "expressions": {}},
            {"address": "aws_nat_gateway.nat", "expressions": {
                "allocation_id": {"references": ["aws_eip.other.id"]},
            }},
        ],
        "module_calls": {},
    }
    client = FakeVpcPriceList()
    result, _ = evaluate(document, catalog_client=client, vpc_usage_assumptions=NAT_USAGE)
    assert result.status == PlanPricingStatus.INCOMPLETE
    assert "vpc_nat_shape_or_usage_unsupported" in {finding.code for finding in result.findings}
    assert client.calls == []


def test_vpc_usage_assumptions_are_bounded_and_keyed_by_exact_nat_address():
    with pytest.raises(ValueError, match="NAT Gateway hours"):
        VpcPricingUsageAssumptions.model_validate({"nat_gateways": {
            "aws_nat_gateway.nat": {
                **NAT_USAGE["nat_gateways"]["aws_nat_gateway.nat"],
                "monthly_available_hours": {"minimum": 0, "maximum": 745},
            }
        }})
    with pytest.raises(ValueError, match="invalid NAT Gateway address"):
        VpcPricingUsageAssumptions.model_validate({"nat_gateways": {
            "aws_nat_gateway.extra.bad": NAT_USAGE["nat_gateways"]["aws_nat_gateway.nat"]
        }})
    with pytest.raises(ValueError):
        VpcPricingUsageAssumptions.model_validate({"nat_gateways": {
            "aws_nat_gateway.nat": {
                **NAT_USAGE["nat_gateways"]["aws_nat_gateway.nat"],
                "unit_price_usd": "0.0001",
            }
        }})


def test_vpc_usage_assumptions_are_extracted_from_digest_checked_revision():
    revision = {
        "target": {"provider": "aws", "region": REGION},
        "application_analysis": {
            "workload_spec": {"vpc_pricing_usage_assumptions": NAT_USAGE}
        },
    }
    revision_sha256 = hashlib.sha256(
        json.dumps(revision, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    context = TrustedPlanPricingContext.from_persisted_revision(
        revision, expected_sha256=revision_sha256
    )
    assert context.vpc_usage_assumptions == NAT_USAGE
    assert context.pricing_context_sha256 != TrustedPlanPricingContext(
        REGION, "USD", None, revision_sha256
    ).pricing_context_sha256


def batch_plan(*, runtime_platform=None, ephemeral_storage=None, explicit_logs=False):
    compute = {
        "type": "MANAGED", "state": "ENABLED", "compute_resources": [{
            "type": "FARGATE", "max_vcpus": 6,
        }],
    }
    queue = {
        "state": "ENABLED", "compute_environment_order": [{
            "order": 1, "compute_environment": "aws_batch_compute_environment.jobs",
        }],
    }
    properties = {
        "image": "public.ecr.aws/library/busybox@sha256:" + "a" * 64,
        "resourceRequirements": [
            {"type": "VCPU", "value": "0.25"},
            {"type": "MEMORY", "value": "512"},
        ],
    }
    if explicit_logs:
        properties["logConfiguration"] = {
            "logDriver": "awslogs",
            "options": {
                "awslogs-group": "/aws/batch/jobs",
                "awslogs-region": REGION,
                "awslogs-stream-prefix": "batch",
            },
        }
    if runtime_platform is not None:
        properties["runtimePlatform"] = runtime_platform
    if ephemeral_storage is not None:
        properties["ephemeralStorage"] = ephemeral_storage
    job = {
        "type": "container", "platform_capabilities": ["FARGATE"],
        "container_properties": json.dumps(properties),
    }
    extra_resources = [
        resource("aws_batch_compute_environment.jobs", "aws_batch_compute_environment", compute),
        resource("aws_batch_job_queue.jobs", "aws_batch_job_queue", queue),
        resource("aws_batch_job_definition.jobs", "aws_batch_job_definition", job),
    ]
    if explicit_logs:
        extra_resources.append(resource(
            "aws_cloudwatch_log_group.batch",
            "aws_cloudwatch_log_group",
            {
                "name": "/aws/batch/jobs",
                "retention_in_days": 30,
                "log_group_class": "STANDARD",
                "kms_key_id": None,
            },
        ))
    return plan(
        resource_type="terraform_data", resource_values={"input": None},
        extra_resources=tuple(extra_resources),
    )


def ecr_plan(**overrides):
    values = {
        "name": "davdeploy-test-images",
        "image_tag_mutability": "IMMUTABLE",
        "force_delete": False,
        "encryption_configuration": [{"encryption_type": "AES256", "kms_key": None}],
    }
    values.update(overrides)
    return plan(
        resource_type="terraform_data",
        resource_values={"input": None},
        extra_resources=(resource("aws_ecr_repository.images", "aws_ecr_repository", values),),
    )


BATCH_USAGE = {
    "jobs": {
        "aws_batch_job_definition.jobs": {
            "monthly_jobs": {"minimum": 10, "maximum": 20},
            "average_billed_runtime_seconds": {"minimum": 30, "maximum": 120},
        }
    }
}

ECR_USAGE = {
    "repositories": {
        "aws_ecr_repository.images": {
            "monthly_stored_gb": {"minimum": 2, "maximum": 5},
        },
    },
}

BATCH_LOG_USAGE = {
    "jobs": {
        "aws_batch_job_definition.jobs": {
            **BATCH_USAGE["jobs"]["aws_batch_job_definition.jobs"],
            "cloudwatch_logs": {
                "monthly_ingested_gb": {"minimum": 1, "maximum": 4},
                "monthly_retained_gb_month": {"minimum": 2, "maximum": 8},
            },
        }
    }
}


def test_batch_fargate_usage_is_priced_by_bound_job_and_applies_one_minute_floor():
    client = FakeBatchPriceList()
    result, _ = evaluate(
        batch_plan(), batch_usage_assumptions=BATCH_USAGE, catalog_client=client
    )

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.monthly_low_minor is result.monthly_high_minor is None
    assert "batch_supporting_costs_unpriced" in {item.code for item in result.findings}
    assert not result.approval_eligible
    assert {line.description for line in result.lines} == {
        "AWS Fargate Linux/x86 vCPU", "AWS Fargate Linux/x86 memory",
    }
    assert {
        line.description: (line.quantity, line.quantity_max)
        for line in result.lines
    } == {
        "AWS Fargate Linux/x86 vCPU": (150_000, 600_000),
        "AWS Fargate Linux/x86 memory": (307_200, 1_228_800),
    }
    assert result.batch_usage_assumptions == BATCH_USAGE
    manifest = result.as_manifest_document()
    assert manifest["version"] == 10
    assert manifest["batch_usage_assumptions"] == BATCH_USAGE
    assert GeneratedPlanPricingEvidence.from_manifest_document(manifest) == result
    bound_context = TrustedPlanPricingContext(
        REGION, "USD", None, PERSISTED_CONTEXT_SHA256,
        batch_usage_assumptions=BATCH_USAGE,
    )
    assert not pricing_evidence_is_approval_eligible(
        manifest, trusted_context=bound_context, now=CAPTURED_AT
    )
    assert not pricing_evidence_is_approval_eligible(
        manifest,
        trusted_context=TrustedPlanPricingContext(
            REGION, "USD", None, PERSISTED_CONTEXT_SHA256
        ),
        now=CAPTURED_AT,
    )
    assert len(client.calls) == 2


def test_batch_explicit_cloudwatch_logs_are_regionally_priced_and_digest_bound():
    client = FakeBatchPriceList()
    result, _ = evaluate(
        batch_plan(explicit_logs=True),
        batch_usage_assumptions=BATCH_LOG_USAGE,
        catalog_client=client,
    )

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert not result.approval_eligible
    assert "batch_supporting_costs_unpriced" in {item.code for item in result.findings}
    log_lines = [line for line in result.lines if "CloudWatch Logs" in line.description]
    assert {
        line.description: (
            line.quantity,
            line.quantity_max,
            line.unit,
            line.monthly_cost_minor,
            line.monthly_cost_max_minor,
        )
        for line in log_lines
    } == {
        "AWS Batch CloudWatch Logs ingestion": (1, 4, "GB", 50, 200),
        "AWS Batch CloudWatch Logs storage": (2, 8, "GB-Mo", 6, 24),
    }
    manifest = result.as_manifest_document()
    assert manifest["batch_usage_assumptions"] == BATCH_LOG_USAGE
    assert result.safe_summary()["batch_usage_assumptions"] == BATCH_LOG_USAGE
    assert GeneratedPlanPricingEvidence.from_manifest_document(manifest) == result
    assert pricing_evidence_document_is_valid(manifest)
    tampered = json.loads(json.dumps(manifest))
    tampered["batch_usage_assumptions"]["jobs"][
        "aws_batch_job_definition.jobs"
    ]["cloudwatch_logs"]["monthly_ingested_gb"]["maximum"] += 1
    assert not pricing_evidence_document_is_valid(tampered)
    assert len(client.calls) == 4
    assert {call["ServiceCode"] for call in client.calls} == {
        "AmazonECS", "AmazonCloudWatch",
    }


def test_batch_legacy_usage_and_evidence_remain_canonical_without_log_fields():
    parsed = BatchPricingUsageAssumptions.model_validate(BATCH_USAGE)
    assert parsed.model_dump(mode="json", exclude_none=True) == BATCH_USAGE
    result, _ = evaluate(
        batch_plan(), batch_usage_assumptions=BATCH_USAGE,
        catalog_client=FakeBatchPriceList(),
    )
    manifest = result.as_manifest_document()
    assert manifest["batch_usage_assumptions"] == BATCH_USAGE
    assert GeneratedPlanPricingEvidence.from_manifest_document(manifest) == result


def test_ecr_standard_storage_uses_exact_address_regional_price_and_bound_usage():
    client = FakeBatchPriceList()
    result, _ = evaluate(
        ecr_plan(), ecr_usage_assumptions=ECR_USAGE, catalog_client=client
    )

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert not result.approval_eligible
    assert "ecr_supporting_costs_unpriced" in {item.code for item in result.findings}
    assert [(line.address, line.description, line.quantity, line.quantity_max,
             line.unit, line.monthly_cost_minor, line.monthly_cost_max_minor)
            for line in result.lines] == [(
        "aws_ecr_repository.images",
        "Amazon ECR standard image storage",
        2,
        5,
        "GB-Mo",
        20,
        50,
    )]
    manifest = result.as_manifest_document()
    assert manifest["version"] == 10
    assert manifest["ecr_usage_assumptions"] == ECR_USAGE
    assert result.safe_summary()["ecr_usage_assumptions"] == ECR_USAGE
    assert GeneratedPlanPricingEvidence.from_manifest_document(manifest) == result
    assert pricing_evidence_document_is_valid(manifest)
    tampered = json.loads(json.dumps(manifest))
    tampered["ecr_usage_assumptions"]["repositories"][
        "aws_ecr_repository.images"
    ]["monthly_stored_gb"]["maximum"] += 1
    assert not pricing_evidence_document_is_valid(tampered)
    assert client.calls == [{
        "ServiceCode": "AmazonECR",
        "Filters": [
            {"Type": "TERM_MATCH", "Field": "productFamily", "Value": "EC2 Container Registry"},
            {"Type": "TERM_MATCH", "Field": "storageType", "Value": "S3"},
            {"Type": "TERM_MATCH", "Field": "regionCode", "Value": REGION},
        ],
        "MaxResults": 100,
    }]


def test_v9_pricing_manifest_remains_readable_and_normalizes_to_current_shape():
    result, _ = evaluate()
    legacy = result.as_manifest_document()
    legacy["version"] = 9
    legacy.pop("ecr_usage_assumptions")
    unsigned = {key: value for key, value in legacy.items() if key != "evidence_sha256"}
    legacy["evidence_sha256"] = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()

    parsed = GeneratedPlanPricingEvidence.from_manifest_document(legacy)
    normalized = parsed.as_manifest_document()

    assert normalized["version"] == 10
    assert normalized["ecr_usage_assumptions"] is None
    assert pricing_evidence_document_is_valid(normalized)


def test_ecr_pricing_fails_closed_for_missing_usage_and_nonstandard_encryption():
    missing_usage, missing_client = evaluate(ecr_plan(), catalog_client=FakeBatchPriceList())
    assert "ecr_storage_assumptions_missing" in {item.code for item in missing_usage.findings}
    assert not any(line.resource_type == "aws_ecr_repository" for line in missing_usage.lines)
    assert not missing_client.calls

    kms_plan = ecr_plan(encryption_configuration=[{"encryption_type": "KMS", "kms_key": "alias/customer"}])
    unsupported, unsupported_client = evaluate(
        kms_plan, ecr_usage_assumptions=ECR_USAGE, catalog_client=FakeBatchPriceList()
    )
    assert "ecr_storage_shape_unsupported" in {item.code for item in unsupported.findings}
    assert not any(line.resource_type == "aws_ecr_repository" for line in unsupported.lines)
    assert not unsupported_client.calls

    missing_rate, rate_client = evaluate(
        ecr_plan(), ecr_usage_assumptions=ECR_USAGE,
        catalog_client=MissingEcrPriceList(),
    )
    assert "regional_price_ambiguous" in {item.code for item in missing_rate.findings}
    assert not any(line.resource_type == "aws_ecr_repository" for line in missing_rate.lines)
    assert len(rate_client.calls) == 1

    with pytest.raises(ValueError):
        EcrPricingUsageAssumptions.model_validate({
            "repositories": {
                "aws_s3_bucket.invalid": {
                    "monthly_stored_gb": {"minimum": 1, "maximum": 2},
                },
            },
        })


def test_batch_explicit_logs_require_usage_and_do_not_remove_supporting_cost_blocker():
    result, client = evaluate(
        batch_plan(explicit_logs=True),
        batch_usage_assumptions=BATCH_USAGE,
        catalog_client=FakeBatchPriceList(),
    )
    assert result.status == PlanPricingStatus.INCOMPLETE
    assert not result.approval_eligible
    assert "batch_log_usage_assumptions_missing" in {item.code for item in result.findings}
    assert "batch_supporting_costs_unpriced" in {item.code for item in result.findings}
    assert len(client.calls) == 2


def test_batch_missing_cloudwatch_prices_fail_closed_without_log_lines():
    result, client = evaluate(
        batch_plan(explicit_logs=True),
        batch_usage_assumptions=BATCH_LOG_USAGE,
        catalog_client=MissingBatchCloudWatchPriceList(),
    )
    assert result.status == PlanPricingStatus.INCOMPLETE
    assert not result.approval_eligible
    assert "regional_price_ambiguous" in {
        item.code for item in result.findings
    }
    assert not any("CloudWatch Logs" in line.description for line in result.lines)
    assert [call["ServiceCode"] for call in client.calls].count("AmazonCloudWatch") == 1


@pytest.mark.parametrize(
    ("field", "value", "unknown", "expected"),
    [
        ("retention_in_days", None, False, "batch_log_retention_unbounded"),
        ("log_group_class", "INFREQUENT_ACCESS", False, "batch_log_class_unpriced"),
        ("kms_key_id", "arn:aws:kms:us-east-1:654654474502:key/example", False, "batch_log_kms_unpriced"),
        ("retention_in_days", 30, True, "batch_log_group_unknown"),
    ],
)
def test_batch_log_group_requires_bounded_standard_retention(
    field, value, unknown, expected
):
    document = batch_plan(explicit_logs=True)
    group = next(
        item for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "aws_cloudwatch_log_group"
    )
    group_change = next(
        item for item in document["resource_changes"]
        if item["type"] == "aws_cloudwatch_log_group"
    )
    group["values"][field] = value
    group_change["change"]["after"][field] = value
    if unknown:
        group_change["change"]["after_unknown"][field] = True
    result, _ = evaluate(
        document,
        batch_usage_assumptions=BATCH_LOG_USAGE,
        catalog_client=FakeBatchPriceList(),
    )
    assert result.status == PlanPricingStatus.INCOMPLETE
    assert expected in {item.code for item in result.findings}
    assert not any("CloudWatch Logs" in line.description for line in result.lines)


def test_batch_logs_require_the_managed_destination_to_be_in_the_plan():
    document = batch_plan(explicit_logs=True)
    document["planned_values"]["root_module"]["resources"] = [
        item for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] != "aws_cloudwatch_log_group"
    ]
    document["resource_changes"] = [
        item for item in document["resource_changes"]
        if item["type"] != "aws_cloudwatch_log_group"
    ]
    result, _ = evaluate(
        document,
        batch_usage_assumptions=BATCH_LOG_USAGE,
        catalog_client=FakeBatchPriceList(),
    )
    assert result.status == PlanPricingStatus.INCOMPLETE
    assert "batch_log_group_mismatch" in {item.code for item in result.findings}
    assert not any("CloudWatch Logs" in line.description for line in result.lines)


@pytest.mark.parametrize(
    ("update", "expected"),
    [
        ({"logDriver": "splunk"}, "batch_log_configuration_unsupported"),
        ({"awslogs-region": "us-west-2"}, "batch_log_configuration_unsupported"),
        ({"awslogs-create-group": "true"}, "batch_log_configuration_unsupported"),
        ({"awslogs-extra": "unsupported"}, "batch_log_configuration_unsupported"),
    ],
)
def test_batch_cloudwatch_log_configuration_fails_closed(update, expected):
    document = batch_plan(explicit_logs=True)
    job = next(
        item for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "aws_batch_job_definition"
    )
    job_properties = json.loads(job["values"]["container_properties"])
    configuration = job_properties["logConfiguration"]
    if "logDriver" in update:
        configuration.update(update)
    else:
        configuration["options"].update(update)
    job["values"]["container_properties"] = json.dumps(job_properties)
    result, client = evaluate(
        document,
        batch_usage_assumptions=BATCH_LOG_USAGE,
        catalog_client=FakeBatchPriceList(),
    )
    assert result.status == PlanPricingStatus.INCOMPLETE
    assert expected in {item.code for item in result.findings}
    assert not any("CloudWatch Logs" in line.description for line in result.lines)
    assert all(call["ServiceCode"] == "AmazonECS" for call in client.calls)


@pytest.mark.parametrize(
    ("kwargs", "finding"),
    [
        ({"runtime_platform": {"operatingSystemFamily": "LINUX", "cpuArchitecture": "ARM64"}},
         "batch_pricing_shape_unsupported"),
        ({"ephemeral_storage": {"sizeInGiB": 21}}, "batch_pricing_shape_unsupported"),
    ],
)
def test_batch_pricing_fails_closed_for_unpriced_runtime_or_storage(kwargs, finding):
    result, client = evaluate(
        batch_plan(**kwargs),
        batch_usage_assumptions=BATCH_USAGE,
        catalog_client=FakeBatchPriceList(),
    )

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert finding in {item.code for item in result.findings}
    assert not result.approval_eligible
    assert client.calls == []


def test_batch_plan_without_usage_assumptions_is_unpriced_and_not_approvable():
    result, _ = evaluate(batch_plan(), catalog_client=FakeBatchPriceList())

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert {item.code for item in result.findings} == {
        "batch_usage_assumptions_missing",
        "batch_supporting_costs_unpriced",
    }
    assert not result.approval_eligible


def test_batch_usage_assumptions_are_bounded_and_exact_address_keyed():
    parsed = BatchPricingUsageAssumptions.model_validate(BATCH_USAGE)
    assert parsed.model_dump(mode="json", exclude_none=True) == BATCH_USAGE
    with pytest.raises(ValueError):
        BatchPricingUsageAssumptions.model_validate({
            "jobs": {"aws_batch_job_queue.jobs": BATCH_USAGE["jobs"]["aws_batch_job_definition.jobs"]}
        })
    over_bound = json.loads(json.dumps(BATCH_LOG_USAGE))
    over_bound["jobs"]["aws_batch_job_definition.jobs"]["cloudwatch_logs"][
        "monthly_ingested_gb"
    ]["maximum"] = 500_001
    with pytest.raises(ValueError, match="CloudWatch Logs"):
        BatchPricingUsageAssumptions.model_validate(over_bound)


def test_batch_usage_assumptions_are_extracted_from_digest_checked_revision():
    revision = {
        "target": {"provider": "aws", "region": REGION},
        "application_analysis": {
            "workload_spec": {"batch_pricing_usage_assumptions": BATCH_USAGE}
        },
    }
    revision_sha256 = hashlib.sha256(
        json.dumps(revision, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    context = TrustedPlanPricingContext.from_persisted_revision(
        revision, expected_sha256=revision_sha256
    )
    assert context.batch_usage_assumptions == BATCH_USAGE
    assert context.pricing_context_sha256 != TrustedPlanPricingContext(
        REGION, "USD", None, revision_sha256
    ).pricing_context_sha256


def test_batch_log_assumptions_are_extracted_from_the_digest_checked_revision():
    revision = {
        "target": {"provider": "aws", "region": REGION},
        "application_analysis": {
            "workload_spec": {"batch_pricing_usage_assumptions": BATCH_LOG_USAGE}
        },
    }
    revision_sha256 = hashlib.sha256(
        json.dumps(revision, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    context = TrustedPlanPricingContext.from_persisted_revision(
        revision, expected_sha256=revision_sha256
    )
    assert context.batch_usage_assumptions == BATCH_LOG_USAGE
    assert context.pricing_context_sha256 != TrustedPlanPricingContext(
        REGION, "USD", None, revision_sha256,
        batch_usage_assumptions=BATCH_USAGE,
    ).pricing_context_sha256


def test_ecr_storage_assumptions_are_extracted_from_digest_checked_revision():
    revision = {
        "target": {"provider": "aws", "region": REGION},
        "application_analysis": {
            "workload_spec": {"ecr_pricing_usage_assumptions": ECR_USAGE}
        },
    }
    revision_sha256 = hashlib.sha256(
        json.dumps(revision, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    context = TrustedPlanPricingContext.from_persisted_revision(
        revision, expected_sha256=revision_sha256
    )
    assert context.ecr_usage_assumptions == ECR_USAGE
    assert context.pricing_context_sha256 != TrustedPlanPricingContext(
        REGION, "USD", None, revision_sha256
    ).pricing_context_sha256
    with pytest.raises(ValueError):
        BatchPricingUsageAssumptions.model_validate({
            "jobs": {"aws_batch_job_definition.jobs": {
                "monthly_jobs": {"minimum": 2, "maximum": 1},
                "average_billed_runtime_seconds": {"minimum": 1, "maximum": 10},
            }}
        })


def test_s3_high_usage_range_controls_budget_and_preserves_estimate_range():
    assumptions = {
        "monthly_storage_gb": {"minimum": 10, "maximum": 20},
        "monthly_put_copy_post_list_requests": {"minimum": 100, "maximum": 200},
        "monthly_get_requests": {"minimum": 300, "maximum": 400},
        "monthly_internet_egress_gb": {"minimum": 0, "maximum": 5},
    }
    result, _ = evaluate(
        s3_bucket_plan(), budget=50, usage_assumptions=assumptions,
        catalog_client=FakeS3PriceList(),
    )

    assert result.status == PlanPricingStatus.COMPLETE
    assert result.monthly_low_minor == 21
    assert result.monthly_high_minor == 93
    assert result.within_budget is False
    assert result.approval_eligible is False
    manifest = result.as_manifest_document()
    assert manifest["version"] == 10
    assert pricing_evidence_document_is_valid(manifest)
    assert not pricing_evidence_is_approval_eligible(
        manifest,
        trusted_context=TrustedPlanPricingContext(
            REGION, "USD", 50, PERSISTED_CONTEXT_SHA256, assumptions
        ),
        now=CAPTURED_AT,
    )


def test_s3_cost_tampering_is_rejected_even_with_recomputed_document_digest():
    assumptions = {
        "monthly_storage_gb": {"minimum": 10, "maximum": 20},
        "monthly_put_copy_post_list_requests": {"minimum": 100, "maximum": 200},
        "monthly_get_requests": {"minimum": 300, "maximum": 400},
        "monthly_internet_egress_gb": {"minimum": 0, "maximum": 5},
    }
    result, _ = evaluate(
        s3_bucket_plan(), budget=500, usage_assumptions=assumptions,
        catalog_client=FakeS3PriceList(),
    )
    manifest = result.as_manifest_document()
    lines = [dict(item) for item in manifest["lines"]]
    lines[0]["monthly_cost_max_minor"] += 1
    unsigned = {
        **manifest,
        "lines": lines,
        "monthly_high_minor": manifest["monthly_high_minor"] + 1,
    }
    unsigned.pop("evidence_sha256")
    tampered = {
        **unsigned,
        "evidence_sha256": hashlib.sha256(
            json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        ).hexdigest(),
    }

    assert pricing_evidence_document_is_valid(tampered)
    assert not pricing_evidence_is_approval_eligible(
        tampered,
        trusted_context=TrustedPlanPricingContext(
            REGION, "USD", 500, PERSISTED_CONTEXT_SHA256, assumptions
        ),
        now=CAPTURED_AT,
    )

    quantity_lines = [dict(item) for item in manifest["lines"]]
    storage_line = next(
        item for item in quantity_lines if item["description"] == "Amazon S3 Standard storage"
    )
    high_delta = 49 - storage_line["monthly_cost_max_minor"]
    storage_line["quantity_max"] += 1
    storage_line["monthly_cost_max_minor"] = 49
    quantity_unsigned = {
        **manifest,
        "lines": quantity_lines,
        "monthly_high_minor": manifest["monthly_high_minor"] + high_delta,
    }
    quantity_unsigned.pop("evidence_sha256")
    quantity_tampered = {
        **quantity_unsigned,
        "evidence_sha256": hashlib.sha256(
            json.dumps(
                quantity_unsigned,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode()
        ).hexdigest(),
    }

    assert pricing_evidence_document_is_valid(quantity_tampered)
    assert not pricing_evidence_is_approval_eligible(
        quantity_tampered,
        trusted_context=TrustedPlanPricingContext(
            REGION, "USD", 500, PERSISTED_CONTEXT_SHA256, assumptions
        ),
        now=CAPTURED_AT,
    )


def test_s3_object_lock_blocks_but_aggregate_assumptions_price_multiple_buckets():
    assumptions = {
        "monthly_storage_gb": {"minimum": 1, "maximum": 1},
        "monthly_put_copy_post_list_requests": {"minimum": 0, "maximum": 0},
        "monthly_get_requests": {"minimum": 0, "maximum": 0},
        "monthly_internet_egress_gb": {"minimum": 0, "maximum": 0},
    }
    locked, _ = evaluate(
        s3_bucket_plan(values={"object_lock_enabled": True}),
        usage_assumptions=assumptions,
        catalog_client=FakeS3PriceList(),
    )
    multiple, _ = evaluate(
        plan(resource_type="terraform_data", resource_values={"input": None}, extra_resources=(
            resource("aws_s3_bucket.one", "aws_s3_bucket", {
                "bucket": "one", "object_lock_enabled": False, "object_lock_configuration": None,
            }),
            resource("aws_s3_bucket.two", "aws_s3_bucket", {
                "bucket": "two", "object_lock_enabled": False, "object_lock_configuration": None,
            }),
        )),
        usage_assumptions=assumptions,
        catalog_client=FakeS3PriceList(),
    )

    assert locked.status == PlanPricingStatus.INCOMPLETE
    assert "s3_object_lock_unpriced" in {item.code for item in locked.findings}
    assert multiple.status == PlanPricingStatus.COMPLETE
    assert multiple.approval_eligible is True
    assert len(multiple.lines) == 4


def test_s3_egress_above_published_price_limit_blocks_approval():
    assumptions = {
        "monthly_storage_gb": {"minimum": 0, "maximum": 0},
        "monthly_put_copy_post_list_requests": {"minimum": 0, "maximum": 0},
        "monthly_get_requests": {"minimum": 0, "maximum": 0},
        "monthly_internet_egress_gb": {"minimum": 500_001, "maximum": 500_001},
    }
    result, _ = evaluate(
        s3_bucket_plan(), usage_assumptions=assumptions,
        catalog_client=FakeS3PriceList(),
    )

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.approval_eligible is False
    assert "s3_egress_price_limit_exceeded" in {item.code for item in result.findings}


def test_missing_s3_price_product_keeps_the_plan_incomplete():
    assumptions = {
        "monthly_storage_gb": {"minimum": 1, "maximum": 1},
        "monthly_put_copy_post_list_requests": {"minimum": 0, "maximum": 0},
        "monthly_get_requests": {"minimum": 0, "maximum": 0},
        "monthly_internet_egress_gb": {"minimum": 0, "maximum": 0},
    }
    result, _ = evaluate(
        s3_bucket_plan(), usage_assumptions=assumptions,
        catalog_client=MissingS3PriceList(),
    )

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.approval_eligible is False
    assert {item.code for item in result.findings} == {"regional_price_ambiguous"}


def test_pricing_evidence_digest_is_bound_to_trusted_context_digest():
    original, _ = evaluate(budget=500)
    changed_context, _ = evaluate(budget=500, context_digest="b" * 64)

    assert original.evidence_sha256 != changed_context.evidence_sha256
    assert original.persisted_context_sha256 != changed_context.persisted_context_sha256


def test_trusted_context_digest_binds_region_currency_budget_and_source_digest():
    original = TrustedPlanPricingContext(REGION, "USD", 50_000, PERSISTED_CONTEXT_SHA256)
    changed_contexts = (
        TrustedPlanPricingContext("eu-west-1", "USD", 50_000, PERSISTED_CONTEXT_SHA256),
        TrustedPlanPricingContext(REGION, "EUR", 50_000, PERSISTED_CONTEXT_SHA256),
        TrustedPlanPricingContext(REGION, "USD", 51_000, PERSISTED_CONTEXT_SHA256),
        TrustedPlanPricingContext(REGION, "USD", 50_000, "b" * 64),
    )

    assert all(
        context.pricing_context_sha256 != original.pricing_context_sha256
        for context in changed_contexts
    )


def test_trusted_context_digest_binds_usage_assumptions():
    baseline = {
        "monthly_storage_gb": {"minimum": 10, "maximum": 20},
        "monthly_put_copy_post_list_requests": {"minimum": 100, "maximum": 200},
        "monthly_get_requests": {"minimum": 300, "maximum": 400},
        "monthly_internet_egress_gb": {"minimum": 0, "maximum": 5},
    }
    original = TrustedPlanPricingContext(
        REGION, "USD", 50_000, PERSISTED_CONTEXT_SHA256, baseline
    )
    changed = {
        **baseline,
        "monthly_storage_gb": {"minimum": 10, "maximum": 21},
    }
    updated = TrustedPlanPricingContext(
        REGION, "USD", 50_000, PERSISTED_CONTEXT_SHA256, changed
    )

    assert original.pricing_context_sha256 != updated.pricing_context_sha256


def test_non_usd_budget_is_not_compared_against_usd_prices():
    result, client = evaluate(currency="EUR", budget=1000)

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.within_budget is None
    assert result.approval_eligible is False
    assert client.calls == []


def test_cached_catalog_query_is_bound_to_region_and_filter():
    AwsPriceListCatalog._cache.clear()
    client = FakePriceList()
    catalog = AwsPriceListCatalog(client, cache_ttl_seconds=3600, clock=lambda: 100.0)

    catalog.ebs_gp3_storage_rate("us-east-1")
    catalog.ebs_gp3_storage_rate("us-east-1")
    catalog.ebs_gp3_storage_rate("eu-west-1")

    assert len(client.calls) == 2
    assert client.calls[0]["Filters"][-1]["Value"] == "us-east-1"
    assert client.calls[1]["Filters"][-1]["Value"] == "eu-west-1"


@pytest.mark.parametrize(
    ("age", "fresh"),
    [
        (timedelta(hours=23, minutes=59), True),
        (timedelta(hours=24), True),
        (timedelta(hours=24, seconds=1), False),
        (timedelta(minutes=-5), True),
        (timedelta(minutes=-5, seconds=-1), False),
    ],
)
def test_pricing_evidence_freshness_is_bounded(age, fresh):
    current = CAPTURED_AT + timedelta(days=3)
    captured = (current - age).isoformat().replace("+00:00", "Z")

    assert pricing_evidence_is_fresh(captured, now=current) is fresh


@pytest.mark.parametrize("captured_at", ["bad", "2026-11-04T18:00:00", None])
def test_malformed_or_timezone_free_pricing_time_is_stale(captured_at):
    assert pricing_evidence_is_fresh(captured_at, now=CAPTURED_AT) is False


def test_expired_price_cache_never_falls_back_to_stale_rate():
    AwsPriceListCatalog._cache.clear()
    clock_value = [100.0]
    catalog = AwsPriceListCatalog(
        FakePriceList(), cache_ttl_seconds=3_600, clock=lambda: clock_value[0]
    )
    catalog.ebs_gp3_storage_rate(REGION)
    clock_value[0] = 3_701.0
    catalog.client = FakePriceList(
        error=ClientError({"Error": {"Code": "AccessDeniedException"}}, "GetProducts")
    )

    with pytest.raises(PriceListUnavailableError):
        catalog.ebs_gp3_storage_rate(REGION)


def test_rds_mysql_price_includes_instance_gp3_and_backup_range_bound_to_context():
    usage = RDS_USAGE
    result, client = evaluate(
        rds_plan(),
        budget=1_500,
        rds_usage_assumptions=usage,
        catalog_client=FakeRdsPriceList(),
    )

    assert result.status == PlanPricingStatus.COMPLETE
    assert result.monthly_low_minor == 1_398
    assert result.monthly_high_minor == 1_493
    assert result.within_budget is True
    assert result.rds_usage_assumptions == usage
    assert len(result.lines) == 3
    assert {line.description for line in result.lines} == {
        "Amazon RDS for MySQL Single-AZ instance hours",
        "Amazon RDS for MySQL GP3 storage",
        "RDS MySQL backup storage",
    }
    assert pricing_evidence_is_approval_eligible(
        result.as_manifest_document(),
        trusted_context=TrustedPlanPricingContext(
            region=REGION,
            currency="USD",
            monthly_budget_minor=1_500,
            persisted_context_sha256=PERSISTED_CONTEXT_SHA256,
            rds_usage_assumptions=usage,
        ),
        now=CAPTURED_AT,
    )
    assert len(client.calls) == 3


def test_rds_without_backup_usage_assumptions_blocks_before_price_lookup():
    client = FakeRdsPriceList()
    result, _ = evaluate(rds_plan(), catalog_client=client)

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.approval_eligible is False
    assert {item.code for item in result.findings} == {"rds_usage_assumptions_missing"}
    assert client.calls == []


@pytest.mark.parametrize(
    ("overrides", "unknown_field", "expected_code"),
    [
        ({"publicly_accessible": True}, None, "rds_deployment_unpriced"),
        ({"multi_az": True}, None, "rds_deployment_unpriced"),
        ({"instance_class": "db.t4g.micro"}, None, "rds_instance_class_unpriced"),
        ({"kms_key_id": "arn:aws:kms:us-east-1:654654474502:key/example"}, None, "rds_customer_kms_unpriced"),
        ({}, "allocated_storage", "rds_cost_driver_unknown"),
    ],
)
def test_unsupported_rds_configuration_blocks_before_price_lookup(overrides, unknown_field, expected_code):
    values = rds_values(**overrides)
    after_unknown = {key: False for key in values}
    if unknown_field:
        after_unknown[unknown_field] = True
    client = FakeRdsPriceList()
    result, _ = evaluate(
        rds_plan(values=values, after_unknown=after_unknown if unknown_field else None),
        rds_usage_assumptions=RDS_USAGE,
        catalog_client=client,
    )

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.approval_eligible is False
    assert expected_code in {item.code for item in result.findings}
    assert client.calls == []


def test_rds_backup_assumption_tampering_invalidates_approval_context():
    result, _ = evaluate(
        rds_plan(),
        budget=1_500,
        rds_usage_assumptions=RDS_USAGE,
        catalog_client=FakeRdsPriceList(),
    )
    changed_usage = {"monthly_backup_storage_gb_month": {"minimum": 0, "maximum": 11}}

    assert not pricing_evidence_is_approval_eligible(
        result.as_manifest_document(),
        trusted_context=TrustedPlanPricingContext(
            REGION, "USD", 1_500, PERSISTED_CONTEXT_SHA256,
            rds_usage_assumptions=changed_usage,
        ),
        now=CAPTURED_AT,
    )


def test_bounded_aurora_serverless_v2_standard_price_is_bound_to_usage_assumptions():
    result, client = evaluate(
        aurora_plan(),
        rds_usage_assumptions=AURORA_USAGE,
        catalog_client=FakeRdsPriceList(),
    )

    assert result.status == PlanPricingStatus.COMPLETE
    assert result.monthly_low_minor == 4_940
    assert result.monthly_high_minor == 18_803
    assert result.rds_usage_assumptions == AURORA_USAGE
    assert len(result.lines) == 6
    assert {line.description for line in result.lines} == {
        "Aurora PostgreSQL Serverless v2 ACU-hours",
        "Aurora Standard storage",
        "Aurora Standard I/O requests",
        "Aurora billable backup storage overage",
        "AWS Secrets Manager secret storage for the RDS-managed credential",
        "AWS Secrets Manager API requests for credential reads and rotation",
    }
    capacity = next(line for line in result.lines if "ACU-hours" in line.description)
    assert (capacity.quantity, capacity.quantity_max, capacity.unit) == (365, 1460, "ACU-Hr")
    assert capacity.catalog_sku == "aurora-acu"
    assert {call["ServiceCode"] for call in client.calls} == {"AmazonRDS", "AWSSecretsManager"}
    io_query = next(call for call in client.calls if any(
        item["Value"] == "Aurora:StorageIOUsage" for item in call["Filters"]
    ))
    assert {item["Field"]: item["Value"] for item in io_query["Filters"]} == {
        "productFamily": "System Operation",
        "databaseEngine": "Aurora PostgreSQL",
        "group": "Aurora I/O Operation",
        "usagetype": "Aurora:StorageIOUsage",
        "regionCode": REGION,
    }
    secret_query = next(
        call for call in client.calls if call["ServiceCode"] == "AWSSecretsManager"
        and any(item["Value"] == "AWSSecretsManager-Secret" for item in call["Filters"])
    )
    assert {item["Field"]: item["Value"] for item in secret_query["Filters"]} == {
        "productFamily": "Secret",
        "group": "AWSSecretsManager-Secret",
        "regionCode": REGION,
    }
    assert pricing_evidence_is_approval_eligible(
        result.as_manifest_document(),
        trusted_context=TrustedPlanPricingContext(
            REGION, "USD", None, PERSISTED_CONTEXT_SHA256,
            rds_usage_assumptions=AURORA_USAGE,
        ),
        now=CAPTURED_AT,
    )
    assert GeneratedPlanPricingEvidence.from_manifest_document(
        result.as_manifest_document()
    ).as_manifest_document() == result.as_manifest_document()


@pytest.mark.parametrize(
    ("cluster_overrides", "instance_overrides", "expected_code"),
    [
        ({"storage_type": "aurora-iopt1"}, {}, "aurora_configuration_unpriced"),
        ({"enable_http_endpoint": True}, {}, "aurora_configuration_unpriced"),
        ({"serverlessv2_scaling_configuration": [{"min_capacity": 0.5, "max_capacity": 3, "seconds_until_auto_pause": None}]}, {}, "aurora_configuration_unpriced"),
        ({}, {"instance_class": "db.r7g.large"}, "aurora_instance_shape_unpriced"),
        ({"storage_encrypted": False}, {}, "aurora_configuration_unpriced"),
    ],
)
def test_unsupported_aurora_shape_blocks_before_catalog_lookup(
    cluster_overrides, instance_overrides, expected_code
):
    client = FakeRdsPriceList()
    result, _ = evaluate(
        aurora_plan(
            cluster=aurora_values(**cluster_overrides),
            instance=aurora_instance_values(**instance_overrides),
        ),
        rds_usage_assumptions=AURORA_USAGE,
        catalog_client=client,
    )

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.approval_eligible is False
    assert expected_code in {finding.code for finding in result.findings}
    assert client.calls == []


def test_aurora_missing_or_tampered_usage_ranges_block_approval():
    client = FakeRdsPriceList()
    missing, _ = evaluate(aurora_plan(), catalog_client=client)
    assert missing.status == PlanPricingStatus.INCOMPLETE
    assert {finding.code for finding in missing.findings} == {"aurora_usage_assumptions_missing"}
    assert client.calls == []

    transfer_usage = {
        **AURORA_USAGE,
        "aurora_monthly_cross_region_transfer_gb": {"minimum": 0, "maximum": 1},
    }
    transfer_client = FakeRdsPriceList()
    transfer, _ = evaluate(
        aurora_plan(), rds_usage_assumptions=transfer_usage,
        catalog_client=transfer_client,
    )
    assert transfer.status == PlanPricingStatus.INCOMPLETE
    assert "aurora_transfer_usage_unpriced" in {finding.code for finding in transfer.findings}
    assert transfer_client.calls == []

    inter_az_usage = {
        **AURORA_USAGE,
        "aurora_monthly_inter_az_transfer_gb": {"minimum": 0, "maximum": 1},
    }
    inter_az, _ = evaluate(
        aurora_plan(), rds_usage_assumptions=inter_az_usage,
        catalog_client=FakeRdsPriceList(),
    )
    assert inter_az.status == PlanPricingStatus.INCOMPLETE
    assert "aurora_transfer_usage_unpriced" in {finding.code for finding in inter_az.findings}

    result, _ = evaluate(
        aurora_plan(), rds_usage_assumptions=AURORA_USAGE,
        catalog_client=FakeRdsPriceList(),
    )
    changed = {**AURORA_USAGE, "aurora_monthly_io_requests": {"minimum": 1_000_000, "maximum": 11_000_000}}
    assert not pricing_evidence_is_approval_eligible(
        result.as_manifest_document(),
        trusted_context=TrustedPlanPricingContext(
            REGION, "USD", None, PERSISTED_CONTEXT_SHA256,
            rds_usage_assumptions=changed,
        ),
        now=CAPTURED_AT,
    )


def serverless_usage():
    return {
        "lambda_functions": {
            "aws_lambda_function.api": {
                "monthly_invocations": {"minimum": 1_000_000, "maximum": 2_000_000},
                "average_billed_duration_ms": {"minimum": 80, "maximum": 150},
                "monthly_internet_egress_gb": {"minimum": 0, "maximum": 3},
                "monthly_cloudwatch_log_ingestion_gb": {"minimum": 0, "maximum": 2},
                "monthly_log_storage_gb_month": {"minimum": 0, "maximum": 5},
            }
        },
        "http_apis": {
            "aws_apigatewayv2_api.http": {
                "monthly_requests": {"minimum": 1_000_000, "maximum": 2_000_000},
                "monthly_internet_egress_gb": {"minimum": 2, "maximum": 5},
            }
        },
    }


def serverless_plan(*, lambda_overrides=None, unknown_key=None, additional_resources=()):
    lambda_values = {
        "function_name": "example-api",
        "package_type": "Zip",
        "architectures": ["arm64"],
        "memory_size": 512,
        "ephemeral_storage": {"size": 512},
        "timeout": 30,
        "snap_start": None,
        "vpc_config": {"subnet_ids": [], "security_group_ids": []},
        "reserved_concurrent_executions": -1,
        "logging_config": [],
    }
    lambda_values.update(lambda_overrides or {})
    api_values = {"protocol_type": "HTTP", "disable_execute_api_endpoint": False}
    result = plan(
        resource_type="terraform_data",
        resource_values={"input": None},
        extra_resources=(
            resource("aws_lambda_function.api", "aws_lambda_function", lambda_values),
            resource("aws_apigatewayv2_api.http", "aws_apigatewayv2_api", api_values),
            resource(
                "aws_cloudwatch_log_group.lambda",
                "aws_cloudwatch_log_group",
                {
                    "name": "/aws/lambda/example-api",
                    "retention_in_days": 30,
                    "log_group_class": "STANDARD",
                    "kms_key_id": None,
                },
            ),
            *additional_resources,
        ),
    )
    if unknown_key:
        item = next(
            item for item in result["resource_changes"]
            if item["type"] == "aws_lambda_function"
        )
        item["change"]["after_unknown"][unknown_key] = True
    return result


def test_lambda_and_http_api_use_regional_prices_and_explicit_usage_ranges():
    usage = serverless_usage()
    AwsPriceListCatalog._cache.clear()
    result, _ = evaluate(
        serverless_plan(),
        budget=100_000,
        serverless_usage_assumptions=usage,
        catalog_client=FakeServerlessPriceList(),
    )

    assert result.status == PlanPricingStatus.COMPLETE
    assert len(result.lines) == 7
    assert result.monthly_high_minor > result.monthly_low_minor
    assert result.serverless_usage_assumptions == usage
    assert pricing_evidence_is_approval_eligible(
        result.as_manifest_document(),
        trusted_context=TrustedPlanPricingContext(
            REGION, "USD", 100_000, PERSISTED_CONTEXT_SHA256,
            serverless_usage_assumptions=usage,
        ),
        now=CAPTURED_AT,
    )


@pytest.mark.parametrize(
    ("overrides", "unknown_key", "expected"),
    [
        ({"package_type": "Image"}, None, "lambda_artifact_type_unpriced"),
        ({"memory_size": 16_384}, None, "lambda_memory_unpriced"),
        ({"vpc_config": {"subnet_ids": ["subnet-123"], "security_group_ids": []}}, None, "lambda_vpc_transfer_unpriced"),
        ({}, "memory_size", "lambda_cost_driver_unknown"),
    ],
)
def test_unsupported_lambda_settings_block_before_price_lookup(overrides, unknown_key, expected):
    client = FakeServerlessPriceList()
    AwsPriceListCatalog._cache.clear()
    result, _ = evaluate(
        serverless_plan(lambda_overrides=overrides, unknown_key=unknown_key),
        serverless_usage_assumptions=serverless_usage(),
        catalog_client=client,
    )
    assert result.status == PlanPricingStatus.INCOMPLETE
    assert expected in {finding.code for finding in result.findings}


def test_serverless_usage_bounds_and_resource_addresses_are_approval_bound():
    usage = serverless_usage()
    result, _ = evaluate(
        serverless_plan(), serverless_usage_assumptions=usage,
        catalog_client=FakeServerlessPriceList(),
    )
    changed = {**usage, "lambda_functions": {
        "aws_lambda_function.api": {
            **usage["lambda_functions"]["aws_lambda_function.api"],
            "monthly_invocations": {"minimum": 1_000_000, "maximum": 3_000_000},
        }
    }}
    assert not pricing_evidence_is_approval_eligible(
        result.as_manifest_document(),
        trusted_context=TrustedPlanPricingContext(
            REGION, "USD", None, PERSISTED_CONTEXT_SHA256,
            serverless_usage_assumptions=changed,
        ),
        now=CAPTURED_AT,
    )


@pytest.mark.parametrize(
    ("resource_type", "values", "expected"),
    [
        (
            "aws_apigatewayv2_stage",
            {
                "access_log_settings": {"destination_arn": "arn:example", "format": "{}"},
                "default_route_settings": {"detailed_metrics_enabled": False},
                "route_settings": [],
            },
            "http_api_access_logs_unpriced",
        ),
        (
            "aws_apigatewayv2_integration",
            {"connection_type": "VPC_LINK", "connection_id": "link-1"},
            "http_api_vpc_link_unpriced",
        ),
    ],
)
def test_http_api_stage_and_integration_surcharges_fail_closed(resource_type, values, expected):
    extra = resource(f"{resource_type}.optional", resource_type, values)
    result, _ = evaluate(
        serverless_plan(additional_resources=(extra,)),
        serverless_usage_assumptions=serverless_usage(),
        catalog_client=FakeServerlessPriceList(),
    )
    assert result.status == PlanPricingStatus.INCOMPLETE
    assert expected in {finding.code for finding in result.findings}


@pytest.mark.parametrize(
    ("field", "value", "unknown", "expected"),
    [
        ("retention_in_days", None, False, "lambda_log_retention_unbounded"),
        ("log_group_class", "INFREQUENT_ACCESS", False, "lambda_log_class_unpriced"),
        ("kms_key_id", "arn:aws:kms:us-east-1:654654474502:key/example", False, "lambda_log_kms_unpriced"),
        ("retention_in_days", 30, True, "lambda_log_group_unknown"),
    ],
)
def test_lambda_log_group_requires_bounded_standard_retention(field, value, unknown, expected):
    document = serverless_plan()
    group = next(
        item for item in document["planned_values"]["root_module"]["resources"]
        if item["type"] == "aws_cloudwatch_log_group"
    )
    group_change = next(
        item for item in document["resource_changes"]
        if item["type"] == "aws_cloudwatch_log_group"
    )
    group["values"][field] = value
    group_change["change"]["after"][field] = value
    if unknown:
        group_change["change"]["after_unknown"][field] = True
    result, _ = evaluate(
        document,
        serverless_usage_assumptions=serverless_usage(),
        catalog_client=FakeServerlessPriceList(),
    )
    assert result.status == PlanPricingStatus.INCOMPLETE
    assert expected in {finding.code for finding in result.findings}


def test_cloudwatch_log_group_without_priced_lambda_blocks_approval():
    log_group = resource(
        "aws_cloudwatch_log_group.orphan",
        "aws_cloudwatch_log_group",
        {
            "name": "/aws/lambda/unpriced",
            "retention_in_days": 30,
            "log_group_class": "STANDARD",
            "kms_key_id": None,
        },
    )
    result, _ = evaluate(
        plan(
            resource_type="terraform_data",
            resource_values={"input": None},
            extra_resources=(log_group,),
        )
    )
    assert result.status == PlanPricingStatus.INCOMPLETE
    assert "cloudwatch_log_group_unpriced" in {finding.code for finding in result.findings}
