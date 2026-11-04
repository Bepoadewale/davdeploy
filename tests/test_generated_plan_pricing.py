from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from botocore.exceptions import ClientError
from davdeploy.generated_plan_pricing import (
    AwsPriceListCatalog,
    PlanPricingStatus,
    TrustedPlanPricingContext,
    evaluate_generated_plan_pricing,
)

REGION = "us-east-1"
CAPTURED_AT = datetime(2026, 11, 4, 18, 0, tzinfo=UTC)
PERSISTED_CONTEXT_SHA256 = "a" * 64


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


def evaluate(
    document=None,
    *,
    client=None,
    budget=None,
    declared_budget=None,
    currency="USD",
    context_digest=PERSISTED_CONTEXT_SHA256,
):
    client = client or FakePriceList()
    return (
        evaluate_generated_plan_pricing(
            document or plan(),
            trusted_context=TrustedPlanPricingContext(
                region=REGION,
                currency=currency,
                monthly_budget_minor=budget,
                persisted_context_sha256=context_digest,
            ),
            proposal_declared_budget_minor=declared_budget,
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
    assert result.lines[0].quantity == 50
    assert result.lines[0].unit == "GB-Mo"
    assert result.lines[0].catalog_sku == "sku-gp3"
    assert result.lines[0].catalog_effective_at == "2026-11-01T00:00:00Z"
    assert result.lines[0].catalog_product_sha256
    assert result.budget_source == "PERSISTED_CUSTOMER_CONTEXT"
    assert result.persisted_context_sha256 == PERSISTED_CONTEXT_SHA256
    assert "not a bill forecast or a spend cap" in result.estimate_disclaimer
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["ServiceCode"] == "AmazonEC2"
    assert {item["Field"]: item["Value"] for item in call["Filters"]} == {
        "productFamily": "Storage",
        "volumeApiName": "gp3",
        "regionCode": REGION,
    }
    assert "cost_explorer" not in repr(call).lower()


@pytest.mark.parametrize(("budget", "eligible"), [(400, True), (399, False)])
def test_budget_gate_uses_conservative_estimate(budget, eligible):
    result, _ = evaluate(budget=budget)

    assert result.status == PlanPricingStatus.COMPLETE
    assert result.within_budget is eligible
    assert result.approval_eligible is eligible
    if not eligible:
        assert {item.code for item in result.findings} == {"monthly_budget_exceeded"}


def test_nova_budget_conflict_with_persisted_customer_budget_blocks_approval():
    client = FakePriceList()
    result, _ = evaluate(budget=400, declared_budget=401, client=client)

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert result.approval_eligible is False
    assert result.monthly_budget_minor == 400
    assert result.proposal_declared_budget_minor == 401
    assert {item.code for item in result.findings} == {"proposal_budget_context_mismatch"}
    assert client.calls == []


def test_absent_nova_budget_does_not_override_trusted_persisted_budget():
    result, _ = evaluate(budget=399)

    assert result.monthly_budget_minor == 399
    assert result.proposal_declared_budget_minor is None
    assert result.within_budget is False
    assert result.approval_eligible is False


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
    assert "excludes transition-period charges" in result.estimate_disclaimer


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
    assert first.as_manifest_document()["evidence_sha256"] == first.evidence_sha256
    assert first.as_manifest_document()["budget_source"] == "PERSISTED_CUSTOMER_CONTEXT"
    assert first.as_manifest_document()["persisted_context_sha256"] == PERSISTED_CONTEXT_SHA256


def test_pricing_evidence_digest_is_bound_to_trusted_context_digest():
    original, _ = evaluate(budget=500)
    changed_context, _ = evaluate(budget=500, context_digest="b" * 64)

    assert original.evidence_sha256 != changed_context.evidence_sha256
    assert original.persisted_context_sha256 != changed_context.persisted_context_sha256


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
