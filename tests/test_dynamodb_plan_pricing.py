from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from davdeploy.domain import DynamoDbPricingUsageAssumptions
from davdeploy.generated_plan_pricing import (
    AwsPriceListCatalog,
    PlanPricingStatus,
    TrustedPlanPricingContext,
    evaluate_generated_plan_pricing,
    pricing_evidence_is_approval_eligible,
)
from pydantic import ValidationError

REGION = "us-east-1"
NOW = datetime(2026, 11, 16, 8, 0, tzinfo=UTC)
DIGEST = "d" * 64
ADDRESS = "aws_dynamodb_table.records"


def usage(read=(100_000, 200_000), write=(100_000, 200_000), storage=(1, 2), pitr=(1, 2)):
    return {
        "tables": {
            ADDRESS: {
                "monthly_read_request_units": {"minimum": read[0], "maximum": read[1]},
                "monthly_write_request_units": {"minimum": write[0], "maximum": write[1]},
                "monthly_storage_gb_month": {"minimum": storage[0], "maximum": storage[1]},
                "monthly_pitr_storage_gb_month": {"minimum": pitr[0], "maximum": pitr[1]},
            }
        }
    }


def table_plan(*, pitr=True, table_class="STANDARD", unknown=None):
    values = {
        "name": "app-records",
        "billing_mode": "PAY_PER_REQUEST",
        "table_class": table_class,
        "global_secondary_index": [],
        "local_secondary_index": [],
        "replica": [],
        "point_in_time_recovery": [{"enabled": pitr}],
        "stream_enabled": False,
        "stream_view_type": None,
        "server_side_encryption": [{"enabled": True, "kms_key_arn": None}],
    }
    resources = [
        {
            "address": ADDRESS,
            "mode": "managed",
            "type": "aws_dynamodb_table",
            "values": values,
        },
        {
            "address": "terraform_data.account_guard",
            "mode": "managed",
            "type": "terraform_data",
            "values": {"input": None},
        },
    ]
    changes = []
    known_flags = {
        "billing_mode": False,
        "table_class": False,
        "global_secondary_index": [],
        "local_secondary_index": [],
        "replica": [],
        "point_in_time_recovery": [{"enabled": False}],
        "stream_enabled": False,
        "stream_view_type": False,
        "server_side_encryption": [{"enabled": False, "kms_key_arn": False}],
    }
    for item in resources:
        after_unknown = unknown or {}
        if item["type"] == "terraform_data":
            after_unknown = {"input": False}
        else:
            after_unknown = {**known_flags, **(unknown or {})}
        changes.append(
            {
                "address": item["address"],
                "type": item["type"],
                "change": {
                    "actions": ["create"],
                    "after": item["values"],
                    "after_unknown": after_unknown,
                },
            }
        )
    return {
        "format_version": "1.2",
        "applyable": True,
        "errored": False,
        "configuration": {
            "provider_config": {"aws": {"expressions": {"region": {"constant_value": REGION}}}}
        },
        "planned_values": {"root_module": {"resources": resources}},
        "resource_changes": changes,
    }


class DynamoDbPriceList:
    def __init__(self, *, missing_group=None, ambiguous_group=None):
        self.missing_group = missing_group
        self.ambiguous_group = ambiguous_group
        self.calls = []

    def get_products(self, **kwargs):
        self.calls.append(kwargs)
        filters = {item["Field"]: item["Value"] for item in kwargs["Filters"]}
        group = filters.get("group")
        if self.missing_group is not None and group == self.missing_group:
            return {"PriceList": []}
        product_family = filters["productFamily"]
        if group == "DDB-ReadUnits":
            unit, price, sku = "ReadRequestUnits", "0.0000001250", "read-sku"
        elif group == "DDB-WriteUnits":
            unit, price, sku = "WriteRequestUnits", "0.0000006250", "write-sku"
        elif filters.get("volumeType") == "Amazon DynamoDB - Indexed DataStore":
            unit, price, sku = "GB-Mo", "0.2500000000", "storage-sku"
        else:
            unit, price, sku = "GB-Mo", "0.2000000000", "pitr-sku"
        dimensions = (
            {
                "free": {
                    "beginRange": "0",
                    "endRange": "25",
                    "unit": unit,
                    "pricePerUnit": {"USD": "0.0000000000"},
                },
                "paid": {
                    "beginRange": "25",
                    "endRange": "Inf",
                    "unit": unit,
                    "pricePerUnit": {"USD": price},
                },
            }
            if sku == "storage-sku"
            else {
                "all": {
                    "beginRange": "0",
                    "endRange": "Inf",
                    "unit": unit,
                    "pricePerUnit": {"USD": price},
                }
            }
        )
        attributes = {key: value for key, value in filters.items() if key != "productFamily"}
        product = {
            "product": {
                "sku": sku,
                "productFamily": product_family,
                "attributes": attributes,
            },
            "serviceCode": "AmazonDynamoDB",
            "publicationDate": "2026-11-15T00:00:00Z",
            "terms": {
                "OnDemand": {
                    "term": {
                        "sku": sku,
                        "effectiveDate": "2026-11-01T00:00:00Z",
                        "priceDimensions": dimensions,
                    }
                }
            },
        }
        encoded = json.dumps(product)
        products = (
            [encoded, encoded]
            if self.ambiguous_group is not None and group == self.ambiguous_group
            else [encoded]
        )
        return {"PriceList": products}


def evaluate(*, document=None, assumptions=None, client=None):
    client = client or DynamoDbPriceList()
    context = TrustedPlanPricingContext(
        region=REGION,
        currency="USD",
        monthly_budget_minor=200,
        persisted_context_sha256=DIGEST,
        dynamodb_usage_assumptions=assumptions,
    )
    result = evaluate_generated_plan_pricing(
        document or table_plan(),
        trusted_context=context,
        catalog=AwsPriceListCatalog(client, cache_ttl_seconds=0),
        captured_at=NOW,
    )
    return result, context, client


def test_dynamodb_usage_assumptions_are_bounded_and_address_bound():
    value = DynamoDbPricingUsageAssumptions.model_validate(usage())
    assert value.tables[ADDRESS].monthly_read_request_units.maximum == 200_000
    with pytest.raises(ValidationError):
        DynamoDbPricingUsageAssumptions.model_validate({**usage(), "price_usd": 1})
    with pytest.raises(ValidationError):
        DynamoDbPricingUsageAssumptions.model_validate(
            {"tables": {"aws_s3_bucket.records": usage()["tables"][ADDRESS]}}
        )
    with pytest.raises(ValidationError):
        DynamoDbPricingUsageAssumptions.model_validate(
            usage(read=(0, 1_000_000_000_001))
        )


def test_dynamodb_on_demand_and_pitr_costs_use_exact_regional_products():
    result, context, client = evaluate(assumptions=usage())

    assert result.status == PlanPricingStatus.COMPLETE
    assert result.monthly_low_minor == 52
    assert result.monthly_high_minor == 106
    assert {call["ServiceCode"] for call in client.calls} == {"AmazonDynamoDB"}
    assert len(client.calls) == 4
    assert {line.description for line in result.lines} == {
        "Amazon DynamoDB on-demand read request units",
        "Amazon DynamoDB on-demand write request units",
        "Amazon DynamoDB Standard table storage",
        "Amazon DynamoDB point-in-time recovery storage",
    }
    storage_line = next(line for line in result.lines if line.description.endswith("table storage"))
    assert storage_line.monthly_cost_minor == 25
    assert storage_line.unit_price_low_usd == "0.2500000000"
    evidence = result.as_manifest_document()
    assert evidence["version"] == 7
    assert evidence["dynamodb_usage_assumptions"] == usage()
    assert pricing_evidence_is_approval_eligible(evidence, trusted_context=context, now=NOW)


@pytest.mark.parametrize(
    ("document", "assumptions", "finding"),
    [
        (None, None, "dynamodb_usage_assumptions_missing"),
        (None, usage(pitr=(0, 0)), "dynamodb_pitr_usage_assumption_mismatch"),
        (table_plan(table_class="STANDARD_INFREQUENT_ACCESS"), usage(), "dynamodb_table_class_unpriced"),
        (table_plan(unknown={"billing_mode": True}), usage(), "dynamodb_configuration_unknown"),
    ],
)
def test_unsupported_or_missing_dynamodb_evidence_blocks_approval(document, assumptions, finding):
    result, _, _ = evaluate(document=document, assumptions=assumptions)
    assert result.status == PlanPricingStatus.INCOMPLETE
    assert not result.approval_eligible
    assert finding in {item.code for item in result.findings}


def test_disabled_pitr_requires_zero_pitr_usage_and_omits_backup_line():
    assumptions = usage(pitr=(0, 0))
    result, _, client = evaluate(document=table_plan(pitr=False), assumptions=assumptions)
    assert result.status == PlanPricingStatus.COMPLETE
    assert result.monthly_high_minor == 66
    assert len(client.calls) == 3
    assert all("point-in-time" not in line.description for line in result.lines)


@pytest.mark.parametrize(
    ("client", "expected_finding"),
    [
        (DynamoDbPriceList(missing_group="DDB-ReadUnits"), "regional_price_ambiguous"),
        (DynamoDbPriceList(ambiguous_group="DDB-ReadUnits"), "regional_price_ambiguous"),
    ],
)
def test_missing_or_ambiguous_catalog_products_block_approval(client, expected_finding):
    result, _, _ = evaluate(assumptions=usage(), client=client)
    assert result.status == PlanPricingStatus.INCOMPLETE
    assert not result.approval_eligible
    assert expected_finding in {item.code for item in result.findings}


def test_dynamodb_assumption_digest_changes_approval_context():
    first = DynamoDbPricingUsageAssumptions.model_validate(usage()).model_dump(mode="json")
    changed = usage(read=(100_000, 300_000))
    second = DynamoDbPricingUsageAssumptions.model_validate(changed).model_dump(mode="json")
    result, context, _ = evaluate(assumptions=first)
    evidence = result.as_manifest_document()
    assert context.pricing_context_sha256 != TrustedPlanPricingContext(
        REGION, "USD", 200, DIGEST, dynamodb_usage_assumptions=second
    ).pricing_context_sha256
    assert not pricing_evidence_is_approval_eligible(
        evidence,
        trusted_context=TrustedPlanPricingContext(
            REGION, "USD", 200, DIGEST, dynamodb_usage_assumptions=second
        ),
        now=NOW,
    )
