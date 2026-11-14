from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pytest
from davdeploy.domain import SqsPricingUsageAssumptions
from davdeploy.generated_plan_pricing import (
    AwsPriceListCatalog,
    PlanPricingStatus,
    TrustedPlanPricingContext,
    evaluate_generated_plan_pricing,
    pricing_evidence_is_approval_eligible,
)
from pydantic import ValidationError

REGION = "us-east-1"
NOW = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
DIGEST = "b" * 64


def assumptions(standard=(0, 0), fifo=(0, 0)):
    return {
        "monthly_standard_request_units": {"minimum": standard[0], "maximum": standard[1]},
        "monthly_fifo_request_units": {"minimum": fifo[0], "maximum": fifo[1]},
        "monthly_fair_queue_request_units": {"minimum": 0, "maximum": 0},
        "monthly_cross_region_transfer_gb": {"minimum": 0, "maximum": 0},
        "monthly_internet_egress_gb": {"minimum": 0, "maximum": 0},
    }


def queue_plan(*, fifo=False, kms=None, unknown_fifo=False, also_standard=False, duplicate_standard=False):
    values = {
        "name": "davdeploy-sqs-pricing-test",
        "fifo_queue": fifo,
        "kms_master_key_id": kms,
    }
    after_unknown = {"fifo_queue": True} if unknown_fifo else {}
    resources = [
        {"address": "aws_sqs_queue.work", "mode": "managed", "type": "aws_sqs_queue", "values": values},
        {"address": "terraform_data.account_guard", "mode": "managed", "type": "terraform_data", "values": {"input": None}},
    ]
    if also_standard:
        resources.insert(1, {"address": "aws_sqs_queue.standard", "mode": "managed", "type": "aws_sqs_queue", "values": {**values, "fifo_queue": False}})
    if duplicate_standard:
        resources.insert(2, {"address": "aws_sqs_queue.standard_extra", "mode": "managed", "type": "aws_sqs_queue", "values": {**values, "fifo_queue": False}})
    changes = [
        {"address": item["address"], "type": item["type"], "change": {"actions": ["create"], "after": item["values"], "after_unknown": (after_unknown if item["address"] == "aws_sqs_queue.work" else {}) if item["type"] == "aws_sqs_queue" else {"input": False}}}
        for item in resources
    ]
    return {
        "format_version": "1.2", "applyable": True, "errored": False,
        "configuration": {"provider_config": {"aws": {"expressions": {"region": {"constant_value": REGION}}}}},
        "planned_values": {"root_module": {"resources": resources}},
        "resource_changes": changes,
    }


class SqsPriceList:
    def __init__(self, *, missing=False):
        self.missing = missing
        self.calls = []

    def get_products(self, **kwargs):
        self.calls.append(kwargs)
        if self.missing:
            return {"PriceList": []}
        filters = {item["Field"]: item["Value"] for item in kwargs["Filters"]}
        fifo = filters["queueType"].startswith("FIFO")
        sku = "fifo-sku" if fifo else "standard-sku"
        rates = ("0.00000050", "0.00000040", "0.00000035") if fifo else ("0.00000040", "0.00000030", "0.00000024")
        bounds = (("0", "100000000000"), ("100000000000", "200000000000"), ("200000000000", "Inf"))
        dimensions = {
            f"tier-{index}": {"beginRange": start, "endRange": end, "unit": "Requests", "pricePerUnit": {"USD": rate}}
            for index, ((start, end), rate) in enumerate(zip(bounds, rates, strict=True))
        }
        product = {
            "product": {"sku": sku, "productFamily": "API Request", "attributes": {"regionCode": REGION, "queueType": filters["queueType"]}},
            "serviceCode": "AWSQueueService", "publicationDate": "2026-11-11T00:00:00Z",
            "terms": {"OnDemand": {"offer": {"sku": sku, "effectiveDate": "2026-11-01T00:00:00Z", "priceDimensions": dimensions}}},
        }
        return {"PriceList": [json.dumps(product)]}


def evaluate(*, doc=None, usage=None, budget=None, client=None):
    client = client or SqsPriceList()
    result = evaluate_generated_plan_pricing(
        doc or queue_plan(),
        trusted_context=TrustedPlanPricingContext(
            REGION, "USD", budget, DIGEST, sqs_usage_assumptions=usage,
        ),
        catalog=AwsPriceListCatalog(client, cache_ttl_seconds=0),
        captured_at=NOW,
    )
    return result, client


def test_sqs_assumptions_require_bounded_integer_ranges_and_forbid_prices():
    value = SqsPricingUsageAssumptions.model_validate(assumptions((5, 10), (2, 4)))
    assert value.monthly_standard_request_units.maximum == 10
    with pytest.raises(ValidationError):
        SqsPricingUsageAssumptions.model_validate({**assumptions(), "price_usd": 1})
    with pytest.raises(ValidationError):
        SqsPricingUsageAssumptions.model_validate(assumptions((0, 1_000_000_000_001)))


def test_sqs_pricing_uses_exact_regional_products_conservative_budget_and_single_free_allowance():
    usage = assumptions((600_000, 800_000), (600_000, 700_000))
    result, client = evaluate(doc=queue_plan(fifo=True, also_standard=True, duplicate_standard=True), usage=usage, budget=70)

    assert result.status == PlanPricingStatus.COMPLETE
    assert result.monthly_low_minor == 4  # shared 1M requests applied once, FIFO first
    assert result.monthly_high_minor == 67  # highest published rates, with conservative cent rounding
    assert result.within_budget is True
    assert {call["ServiceCode"] for call in client.calls} == {"AWSQueueService"}
    assert len(client.calls) == 2
    lines = {line.description: line for line in result.lines}
    assert lines["Amazon SQS FIFO requests"].low_cost_quantity == 0
    assert lines["Amazon SQS Standard requests"].low_cost_quantity == 200_000
    assert sum(line.resource_type == "aws_sqs_queue" for line in result.lines) == 2
    assert lines["Amazon SQS FIFO requests"].catalog_sku == "fifo-sku"
    assert pricing_evidence_is_approval_eligible(
        result.as_manifest_document(),
        trusted_context=TrustedPlanPricingContext(
            REGION, "USD", 70, DIGEST, sqs_usage_assumptions=usage,
        ),
        now=NOW,
    )


def test_sqs_queue_without_revision_bound_usage_blocks_approval():
    result, _ = evaluate()
    assert result.status == PlanPricingStatus.INCOMPLETE
    assert not result.approval_eligible
    assert {finding.code for finding in result.findings} == {"sqs_usage_assumptions_missing"}


@pytest.mark.parametrize(
    ("dimension", "finding"),
    [
        ("monthly_fair_queue_request_units", "sqs_fair_queue_unpriced"),
        ("monthly_cross_region_transfer_gb", "sqs_data_transfer_unpriced"),
        ("monthly_internet_egress_gb", "sqs_data_transfer_unpriced"),
    ],
)
def test_unpriced_sqs_surcharges_and_transfers_block_approval(dimension, finding):
    usage = assumptions((100, 200), (0, 0))
    usage[dimension] = {"minimum": 1, "maximum": 2}
    result, _ = evaluate(doc=queue_plan(fifo=False), usage=usage)

    assert result.status == PlanPricingStatus.INCOMPLETE
    assert finding in {item.code for item in result.findings}
    assert not result.approval_eligible


@pytest.mark.parametrize(
    ("doc", "usage", "expected"),
    [
        (queue_plan(fifo=True), assumptions((1, 2), (0, 0)), "sqs_usage_queue_type_mismatch"),
        (queue_plan(fifo=True, kms="arn:aws:kms:us-east-1:654654474502:key/example"), assumptions((0, 0), (1, 2)), "sqs_kms_unpriced"),
        (queue_plan(fifo=True, unknown_fifo=True), assumptions((0, 0), (1, 2)), "sqs_configuration_unknown"),
    ],
)
def test_sqs_unsupported_or_unknown_configuration_blocks(doc, usage, expected):
    result, _ = evaluate(doc=doc, usage=usage)
    assert result.status == PlanPricingStatus.INCOMPLETE
    assert expected in {finding.code for finding in result.findings}


def test_sqs_exact_product_must_be_present_and_unambiguous():
    result, _ = evaluate(
        doc=queue_plan(fifo=True), usage=assumptions((0, 0), (1_000_000, 1_000_000)),
        client=SqsPriceList(missing=True),
    )
    assert result.status == PlanPricingStatus.INCOMPLETE
    assert "regional_price_ambiguous" in {finding.code for finding in result.findings}


def test_sqs_usage_and_price_are_bound_into_revision_pricing_context_and_manifest():
    usage = assumptions((100, 200), (0, 0))
    context = TrustedPlanPricingContext(REGION, "USD", None, DIGEST, sqs_usage_assumptions=usage)
    changed = TrustedPlanPricingContext(REGION, "USD", None, DIGEST, sqs_usage_assumptions=assumptions((100, 201), (0, 0)))
    assert context.pricing_context_sha256 != changed.pricing_context_sha256
    result, _ = evaluate(doc=queue_plan(fifo=False), usage=usage)
    manifest = result.as_manifest_document()
    assert manifest["version"] == 4
    assert manifest["sqs_usage_assumptions"] == usage
    assert manifest["lines"][0]["catalog_product_sha256"]


def test_sqs_cost_quantity_tampering_is_rejected_even_with_recomputed_document_digest():
    usage = assumptions((100, 200), (0, 0))
    result, _ = evaluate(doc=queue_plan(fifo=False), usage=usage)
    manifest = result.as_manifest_document()
    manifest["lines"][0]["quantity_max"] += 1
    unsigned = {key: value for key, value in manifest.items() if key != "evidence_sha256"}
    manifest["evidence_sha256"] = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()

    assert not pricing_evidence_is_approval_eligible(
        manifest,
        trusted_context=TrustedPlanPricingContext(
            REGION, "USD", None, DIGEST, sqs_usage_assumptions=usage,
        ),
        now=NOW,
    )
