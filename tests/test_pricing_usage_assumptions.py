import pytest
from davdeploy.domain import (
    InfrastructurePlanConstraintUpdateRequest,
    MonthlyUsageRange,
    S3PricingUsageAssumptions,
    SqsPricingUsageAssumptions,
)
from pydantic import ValidationError


def assumptions():
    return {
        "monthly_storage_gb": {"minimum": 10, "maximum": 20},
        "monthly_put_copy_post_list_requests": {"minimum": 100, "maximum": 200},
        "monthly_get_requests": {"minimum": 300, "maximum": 400},
        "monthly_internet_egress_gb": {"minimum": 0, "maximum": 5},
    }


def test_usage_ranges_accept_explicit_bounded_nonnegative_integer_intervals():
    value = S3PricingUsageAssumptions.model_validate(assumptions())

    assert value.monthly_storage_gb.minimum == 10
    assert value.monthly_storage_gb.maximum == 20
    assert value.model_dump(mode="json") == assumptions()


@pytest.mark.parametrize(
    "value",
    [
        {"minimum": -1, "maximum": 2},
        {"minimum": 3, "maximum": 2},
        {"minimum": 0, "maximum": 1_000_000_000_001},
        {"minimum": 0.5, "maximum": 1},
        {"minimum": 0, "maximum": 1, "price_usd": 0},
    ],
)
def test_usage_range_rejects_negative_reversed_unbounded_noninteger_or_price_input(value):
    with pytest.raises(ValidationError):
        MonthlyUsageRange.model_validate(value)


def test_assumptions_require_all_s3_dimensions_and_forbid_extra_fields():
    incomplete = assumptions()
    del incomplete["monthly_internet_egress_gb"]
    with pytest.raises(ValidationError):
        S3PricingUsageAssumptions.model_validate(incomplete)

    extended = {**assumptions(), "price_usd": 1}
    with pytest.raises(ValidationError):
        S3PricingUsageAssumptions.model_validate(extended)

    too_much_storage = assumptions()
    too_much_storage["monthly_storage_gb"] = {
        "minimum": 0,
        "maximum": 1_000_000_001,
    }
    with pytest.raises(ValidationError):
        S3PricingUsageAssumptions.model_validate(too_much_storage)


def test_constraint_revision_input_is_strict_about_usage_assumption_fields():
    request = InfrastructurePlanConstraintUpdateRequest.model_validate(
        {"pricing_usage_assumptions": assumptions()}
    )
    assert request.pricing_usage_assumptions is not None
    assert InfrastructurePlanConstraintUpdateRequest.model_validate(
        {"pricing_usage_assumptions": None}
    ).model_dump(mode="json", exclude_unset=True) == {"pricing_usage_assumptions": None}
    with pytest.raises(ValidationError):
        InfrastructurePlanConstraintUpdateRequest.model_validate(
            {"pricing_usage_assumptions": assumptions(), "arbitrary": "value"}
        )


def test_sqs_usage_assumptions_are_strict_bounded_request_unit_ranges():
    value = SqsPricingUsageAssumptions.model_validate({
        "monthly_standard_request_units": {"minimum": 100, "maximum": 200},
        "monthly_fifo_request_units": {"minimum": 5, "maximum": 10},
        "monthly_fair_queue_request_units": {"minimum": 0, "maximum": 0},
        "monthly_cross_region_transfer_gb": {"minimum": 0, "maximum": 0},
        "monthly_internet_egress_gb": {"minimum": 0, "maximum": 0},
    })
    assert value.monthly_fifo_request_units.maximum == 10
    with pytest.raises(ValidationError):
        SqsPricingUsageAssumptions.model_validate({
            "monthly_standard_request_units": {"minimum": 0, "maximum": 2},
            "monthly_fifo_request_units": {"minimum": 0, "maximum": 1},
            "monthly_fair_queue_request_units": {"minimum": 0, "maximum": 0},
            "monthly_cross_region_transfer_gb": {"minimum": 0, "maximum": 0},
            "monthly_internet_egress_gb": {"minimum": 0, "maximum": 0},
            "unit_price_usd": "0.0000004",
        })
    with pytest.raises(ValidationError):
        InfrastructurePlanConstraintUpdateRequest.model_validate({
            "sqs_pricing_usage_assumptions": {
                "monthly_standard_request_units": {"minimum": 10, "maximum": 1},
                "monthly_fifo_request_units": {"minimum": 0, "maximum": 0},
                "monthly_fair_queue_request_units": {"minimum": 0, "maximum": 0},
                "monthly_cross_region_transfer_gb": {"minimum": 0, "maximum": 0},
                "monthly_internet_egress_gb": {"minimum": 0, "maximum": 0},
            }
        })
