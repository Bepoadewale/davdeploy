from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from botocore.exceptions import ClientError
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
        ("aws_internet_gateway", {"vpc_id": "vpc-123"}),
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
    assert egress_line.unit_price_low_source_url == "https://aws.amazon.com/s3/pricing/"
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
    assert manifest["version"] == 4
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
