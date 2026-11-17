import pytest
from davdeploy.domain import (
    InfrastructurePlanConstraintUpdateRequest,
    MonthlyUsageRange,
    RdsPricingUsageAssumptions,
    S3PricingUsageAssumptions,
    ServerlessPricingUsageAssumptions,
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


def test_rds_backup_usage_assumptions_are_bounded_and_constraint_input_is_strict():
    usage = {"monthly_backup_storage_gb_month": {"minimum": 2, "maximum": 20}}
    value = RdsPricingUsageAssumptions.model_validate(usage)
    assert value.model_dump(mode="json", exclude_unset=True) == usage

    request = InfrastructurePlanConstraintUpdateRequest.model_validate(
        {"rds_pricing_usage_assumptions": usage}
    )
    assert request.rds_pricing_usage_assumptions == value
    assert InfrastructurePlanConstraintUpdateRequest.model_validate(
        {"rds_pricing_usage_assumptions": None}
    ).model_dump(mode="json", exclude_unset=True) == {
        "rds_pricing_usage_assumptions": None
    }

    with pytest.raises(ValidationError):
        RdsPricingUsageAssumptions.model_validate({
            "monthly_backup_storage_gb_month": {"minimum": 0, "maximum": 1_000_000_001}
        })
    with pytest.raises(ValidationError):
        InfrastructurePlanConstraintUpdateRequest.model_validate({
            "rds_pricing_usage_assumptions": {
                **usage, "unknown_price": "0.10"
            }
        })


def test_aurora_usage_assumptions_require_storage_io_and_backup_overage_together():
    usage = {
        "monthly_backup_storage_gb_month": None,
        "aurora_monthly_storage_gb_month": {"minimum": 20, "maximum": 50},
        "aurora_monthly_io_requests": {"minimum": 0, "maximum": 10_000_000},
        "aurora_monthly_backup_overage_gb_month": {"minimum": 0, "maximum": 5},
        "aurora_monthly_secret_api_requests": {"minimum": 10, "maximum": 50},
        "aurora_monthly_inter_az_transfer_gb": {"minimum": 0, "maximum": 0},
        "aurora_monthly_cross_region_transfer_gb": {"minimum": 0, "maximum": 0},
        "aurora_monthly_internet_egress_gb": {"minimum": 0, "maximum": 0},
    }
    value = RdsPricingUsageAssumptions.model_validate(usage)
    assert value.model_dump(mode="json", exclude_unset=True) == usage
    assert InfrastructurePlanConstraintUpdateRequest.model_validate(
        {"rds_pricing_usage_assumptions": usage}
    ).rds_pricing_usage_assumptions == value

    with pytest.raises(ValidationError):
        RdsPricingUsageAssumptions.model_validate({
            "aurora_monthly_storage_gb_month": {"minimum": 20, "maximum": 50},
        })
    with pytest.raises(ValidationError):
        RdsPricingUsageAssumptions.model_validate({
            **usage,
            "aurora_monthly_io_requests": {"minimum": 10, "maximum": 1},
        })


def test_serverless_usage_assumptions_bind_bounded_quantities_to_resource_addresses():
    value = {
        "lambda_functions": {
            "aws_lambda_function.api": {
                "monthly_invocations": {"minimum": 100, "maximum": 200},
                "average_billed_duration_ms": {"minimum": 25, "maximum": 80},
                "monthly_internet_egress_gb": {"minimum": 0, "maximum": 2},
                "monthly_cloudwatch_log_ingestion_gb": {"minimum": 0, "maximum": 1},
                "monthly_log_storage_gb_month": {"minimum": 0, "maximum": 1},
            }
        },
        "http_apis": {
            "aws_apigatewayv2_api.http": {
                "monthly_requests": {"minimum": 100, "maximum": 200},
                "monthly_internet_egress_gb": {"minimum": 0, "maximum": 2},
            }
        },
    }
    assert ServerlessPricingUsageAssumptions.model_validate(value).model_dump(mode="json") == value
    request = InfrastructurePlanConstraintUpdateRequest.model_validate(
        {"serverless_pricing_usage_assumptions": value}
    )
    assert request.serverless_pricing_usage_assumptions is not None
    assert InfrastructurePlanConstraintUpdateRequest.model_validate(
        {"serverless_pricing_usage_assumptions": None}
    ).model_dump(mode="json", exclude_unset=True) == {
        "serverless_pricing_usage_assumptions": None
    }
    invalid = {**value, "lambda_functions": {"aws_lambda_function.api;destroy": value["lambda_functions"]["aws_lambda_function.api"]}}
    with pytest.raises(ValidationError):
        ServerlessPricingUsageAssumptions.model_validate(invalid)
    bad_duration = {**value, "lambda_functions": {"aws_lambda_function.api": {
        **value["lambda_functions"]["aws_lambda_function.api"],
        "average_billed_duration_ms": {"minimum": 100, "maximum": 10},
    }}}
    with pytest.raises(ValidationError):
        ServerlessPricingUsageAssumptions.model_validate(bad_duration)
    over_transfer = {
        **value,
        "lambda_functions": {
            "aws_lambda_function.api": {
                **value["lambda_functions"]["aws_lambda_function.api"],
                "monthly_internet_egress_gb": {
                    "minimum": 0,
                    "maximum": 500_001,
                },
                "monthly_cloudwatch_log_ingestion_gb": {"minimum": 0, "maximum": 1},
                "monthly_log_storage_gb_month": {"minimum": 0, "maximum": 1},
            }
        },
    }
    with pytest.raises(ValidationError):
        ServerlessPricingUsageAssumptions.model_validate(over_transfer)
