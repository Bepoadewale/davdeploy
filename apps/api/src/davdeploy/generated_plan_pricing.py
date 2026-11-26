"""Conservative monthly pricing for selected Nova Terraform plan resources.

This module is deliberately separate from policy evaluation. It prices only
resource families whose billable quantity is explicit in the Terraform plan;
all other material resources remain unreviewable until a trusted usage model
is implemented for them.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, InvalidOperation
from enum import StrEnum
from itertools import pairwise
from typing import Any, ClassVar, Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from davdeploy.domain import (
    BatchPricingUsageAssumptions,
    DynamoDbPricingUsageAssumptions,
    EcrPricingUsageAssumptions,
    EcsExpressPricingUsageAssumptions,
    RdsPricingUsageAssumptions,
    S3PricingUsageAssumptions,
    ServerlessPricingUsageAssumptions,
    SqsPricingUsageAssumptions,
    VpcPricingUsageAssumptions,
)


class PlanPricingStatus(StrEnum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    UNAVAILABLE = "UNAVAILABLE"


class PlanPricingError(ValueError):
    """Raised for malformed plan/pricing evidence without raw AWS values."""


class PriceListUnavailableError(PlanPricingError):
    """The public AWS price service did not return a usable response."""


MAX_PRICING_EVIDENCE_AGE = timedelta(hours=24)
MAX_PRICING_EVIDENCE_FUTURE_SKEW = timedelta(minutes=5)


@dataclass(frozen=True)
class PlanPricingFinding:
    code: str
    address: str | None
    message: str


@dataclass(frozen=True)
class PlanCostLine:
    address: str
    resource_type: str
    description: str
    quantity: int
    unit: str
    unit_price_usd: str
    monthly_cost_minor: int
    catalog_sku: str
    catalog_product_sha256: str
    catalog_published_at: str
    catalog_effective_at: str
    quantity_max: int | None = None
    monthly_cost_max_minor: int | None = None
    unit_price_low_usd: str | None = None
    unit_price_low_source_url: str | None = None
    low_cost_quantity: int | None = None


@dataclass(frozen=True)
class PlanTransition:
    address: str
    resource_type: str
    actions: tuple[str, ...]
    treatment: str


@dataclass(frozen=True)
class GeneratedPlanPricingEvidence:
    status: PlanPricingStatus
    region: str
    currency: str
    captured_at: str
    rate_type: str
    monthly_low_minor: int | None
    monthly_high_minor: int | None
    monthly_budget_minor: int | None
    proposal_declared_budget_minor: int | None
    proposal_declared_currency: str | None
    budget_source: str
    persisted_context_sha256: str
    pricing_context_sha256: str
    estimate_disclaimer: str
    within_budget: bool | None
    plan_json_sha256: str
    usage_assumptions: dict[str, Any] | None
    sqs_usage_assumptions: dict[str, Any] | None
    rds_usage_assumptions: dict[str, Any] | None
    serverless_usage_assumptions: dict[str, Any] | None
    dynamodb_usage_assumptions: dict[str, Any] | None
    vpc_usage_assumptions: dict[str, Any] | None
    batch_usage_assumptions: dict[str, Any] | None
    ecr_usage_assumptions: dict[str, Any] | None
    lines: tuple[PlanCostLine, ...]
    transitions: tuple[PlanTransition, ...]
    findings: tuple[PlanPricingFinding, ...]
    evidence_sha256: str
    ecs_express_usage_assumptions: dict[str, Any] | None = None

    @property
    def approval_eligible(self) -> bool:
        return self.status == PlanPricingStatus.COMPLETE and self.within_budget is not False

    def fresh_for_approval(self, *, now: datetime | None = None) -> bool:
        return pricing_evidence_is_fresh(self.captured_at, now=now)

    def safe_summary(self) -> dict[str, Any]:
        """Expose customer-facing estimate facts without Terraform plan contents."""
        return {
            "status": self.status.value,
            "currency": self.currency,
            "rate_type": self.rate_type,
            "monthly_low_minor": self.monthly_low_minor,
            "monthly_high_minor": self.monthly_high_minor,
            "monthly_budget_minor": self.monthly_budget_minor,
            "within_budget": self.within_budget,
            "captured_at": self.captured_at,
            "estimate_disclaimer": self.estimate_disclaimer,
            "usage_assumptions": self.usage_assumptions,
            "sqs_usage_assumptions": self.sqs_usage_assumptions,
            "rds_usage_assumptions": self.rds_usage_assumptions,
            "serverless_usage_assumptions": self.serverless_usage_assumptions,
            "dynamodb_usage_assumptions": self.dynamodb_usage_assumptions,
            "vpc_usage_assumptions": self.vpc_usage_assumptions,
            "batch_usage_assumptions": self.batch_usage_assumptions,
            "ecr_usage_assumptions": self.ecr_usage_assumptions,
            "ecs_express_usage_assumptions": self.ecs_express_usage_assumptions,
            "evidence_sha256": self.evidence_sha256,
        }

    def as_manifest_document(self) -> dict[str, Any]:
        return {
            "version": 11,
            "status": self.status.value,
            "region": self.region,
            "currency": self.currency,
            "rate_type": self.rate_type,
            "estimate_disclaimer": self.estimate_disclaimer,
            "freshness_max_age_seconds": int(MAX_PRICING_EVIDENCE_AGE.total_seconds()),
            "future_clock_skew_seconds": int(MAX_PRICING_EVIDENCE_FUTURE_SKEW.total_seconds()),
            "captured_at": self.captured_at,
            "monthly_low_minor": self.monthly_low_minor,
            "monthly_high_minor": self.monthly_high_minor,
            "monthly_budget_minor": self.monthly_budget_minor,
            "proposal_declared_budget_minor": self.proposal_declared_budget_minor,
            "proposal_declared_currency": self.proposal_declared_currency,
            "budget_source": self.budget_source,
            "persisted_context_sha256": self.persisted_context_sha256,
            "pricing_context_sha256": self.pricing_context_sha256,
            "within_budget": self.within_budget,
            "plan_json_sha256": self.plan_json_sha256,
            "usage_assumptions": self.usage_assumptions,
            "sqs_usage_assumptions": self.sqs_usage_assumptions,
            "rds_usage_assumptions": self.rds_usage_assumptions,
            "serverless_usage_assumptions": self.serverless_usage_assumptions,
            "dynamodb_usage_assumptions": self.dynamodb_usage_assumptions,
            "vpc_usage_assumptions": self.vpc_usage_assumptions,
            "batch_usage_assumptions": self.batch_usage_assumptions,
            "ecr_usage_assumptions": self.ecr_usage_assumptions,
            "ecs_express_usage_assumptions": self.ecs_express_usage_assumptions,
            "lines": [
                {
                    "address": item.address,
                    "resource_type": item.resource_type,
                    "description": item.description,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "unit_price_usd": item.unit_price_usd,
                    "monthly_cost_minor": item.monthly_cost_minor,
                    "catalog_sku": item.catalog_sku,
                    "catalog_product_sha256": item.catalog_product_sha256,
                    "catalog_published_at": item.catalog_published_at,
                    "catalog_effective_at": item.catalog_effective_at,
                    "quantity_max": item.quantity_max,
                    "monthly_cost_max_minor": item.monthly_cost_max_minor,
                    "unit_price_low_usd": item.unit_price_low_usd,
                    "unit_price_low_source_url": item.unit_price_low_source_url,
                    "low_cost_quantity": item.low_cost_quantity,
                }
                for item in self.lines
            ],
            "transitions": [
                {
                    "address": item.address,
                    "resource_type": item.resource_type,
                    "actions": list(item.actions),
                    "treatment": item.treatment,
                }
                for item in self.transitions
            ],
            "findings": [
                {"code": item.code, "address": item.address, "message": item.message}
                for item in self.findings
            ],
            "evidence_sha256": self.evidence_sha256,
        }

    @classmethod
    def from_manifest_document(cls, document: Any) -> GeneratedPlanPricingEvidence:
        """Parse a bounded worker result and require its canonical digest."""
        if not pricing_evidence_document_is_valid(document):
            raise PlanPricingError("pricing evidence digest is invalid")
        expected_fields = {
            "version", "status", "region", "currency", "rate_type",
            "estimate_disclaimer", "freshness_max_age_seconds",
            "future_clock_skew_seconds", "captured_at", "monthly_low_minor",
            "monthly_high_minor", "monthly_budget_minor",
            "proposal_declared_budget_minor", "proposal_declared_currency",
            "budget_source", "persisted_context_sha256",
            "pricing_context_sha256", "within_budget", "plan_json_sha256",
            "usage_assumptions", "sqs_usage_assumptions", "rds_usage_assumptions",
            "serverless_usage_assumptions", "dynamodb_usage_assumptions",
            "vpc_usage_assumptions", "batch_usage_assumptions",
            "ecr_usage_assumptions",
            "ecs_express_usage_assumptions",
            "lines", "transitions", "findings", "evidence_sha256",
        }
        version = document.get("version")
        version_10_fields = expected_fields - {"ecs_express_usage_assumptions"}
        version_9_fields = version_10_fields - {"ecr_usage_assumptions"}
        version_8_fields = version_9_fields - {"batch_usage_assumptions"}
        version_7_fields = version_8_fields - {"vpc_usage_assumptions"}
        version_6_fields = version_7_fields - {"dynamodb_usage_assumptions"}
        version_5_fields = version_6_fields - {"serverless_usage_assumptions"}
        version_4_fields = version_5_fields - {"rds_usage_assumptions"}
        legacy_fields = version_4_fields - {"sqs_usage_assumptions"}
        valid_shape = (
            version == 11 and set(document) == expected_fields
            or version == 10 and set(document) == version_10_fields
            or version == 9 and set(document) == version_9_fields
            or version == 8 and set(document) == version_8_fields
            or version == 7 and set(document) == version_7_fields
            or version == 6 and set(document) == version_6_fields
            or version == 5 and set(document) == version_5_fields
            or version == 4 and set(document) == version_4_fields
            or version in {2, 3} and set(document) == legacy_fields
        )
        if not valid_shape:
            raise PlanPricingError("pricing evidence shape is invalid")
        try:
            usage_assumptions = document["usage_assumptions"]
            if usage_assumptions is not None:
                usage_assumptions = S3PricingUsageAssumptions.model_validate(
                    usage_assumptions
                ).model_dump(mode="json")
                if usage_assumptions != document["usage_assumptions"]:
                    raise ValueError("non-canonical usage assumptions")
            raw_sqs_usage = document.get("sqs_usage_assumptions")
            sqs_usage = None if raw_sqs_usage is None else SqsPricingUsageAssumptions.model_validate(raw_sqs_usage).model_dump(mode="json")
            if sqs_usage != raw_sqs_usage:
                raise ValueError("non-canonical SQS usage assumptions")
            raw_rds_usage = document.get("rds_usage_assumptions")
            rds_usage = (
                None
                if raw_rds_usage is None
                else RdsPricingUsageAssumptions.model_validate(raw_rds_usage).model_dump(
                    mode="json", exclude_unset=True
                )
            )
            if rds_usage != raw_rds_usage:
                raise ValueError("non-canonical RDS usage assumptions")
            raw_serverless_usage = document.get("serverless_usage_assumptions")
            serverless_usage = (
                None
                if raw_serverless_usage is None
                else ServerlessPricingUsageAssumptions.model_validate(
                    raw_serverless_usage
                ).model_dump(mode="json")
            )
            if serverless_usage != raw_serverless_usage:
                raise ValueError("non-canonical serverless usage assumptions")
            raw_dynamodb_usage = document.get("dynamodb_usage_assumptions")
            dynamodb_usage = (
                None
                if raw_dynamodb_usage is None
                else DynamoDbPricingUsageAssumptions.model_validate(
                    raw_dynamodb_usage
                ).model_dump(mode="json")
            )
            if dynamodb_usage != raw_dynamodb_usage:
                raise ValueError("non-canonical DynamoDB usage assumptions")
            raw_vpc_usage = document.get("vpc_usage_assumptions")
            vpc_usage = (
                None
                if raw_vpc_usage is None
                else VpcPricingUsageAssumptions.model_validate(raw_vpc_usage).model_dump(
                    mode="json", exclude_none=True
                )
            )
            if vpc_usage != raw_vpc_usage:
                raise ValueError("non-canonical VPC usage assumptions")
            raw_batch_usage = document.get("batch_usage_assumptions")
            batch_usage = (
                None
                if raw_batch_usage is None
                else BatchPricingUsageAssumptions.model_validate(
                    raw_batch_usage
                ).model_dump(mode="json", exclude_none=True)
            )
            if batch_usage != raw_batch_usage:
                raise ValueError("non-canonical Batch usage assumptions")
            raw_ecr_usage = document.get("ecr_usage_assumptions")
            ecr_usage = (
                None
                if raw_ecr_usage is None
                else EcrPricingUsageAssumptions.model_validate(raw_ecr_usage).model_dump(
                    mode="json"
                )
            )
            if ecr_usage != raw_ecr_usage:
                raise ValueError("non-canonical ECR usage assumptions")
            raw_ecs_express_usage = document.get("ecs_express_usage_assumptions")
            ecs_express_usage = (
                None
                if raw_ecs_express_usage is None
                else EcsExpressPricingUsageAssumptions.model_validate(
                    raw_ecs_express_usage
                ).model_dump(mode="json")
            )
            if ecs_express_usage != raw_ecs_express_usage:
                raise ValueError("non-canonical ECS Express usage assumptions")
            lines = tuple(PlanCostLine(**item) for item in document["lines"])
            transitions = tuple(
                PlanTransition(
                    address=item["address"],
                    resource_type=item["resource_type"],
                    actions=tuple(item["actions"]),
                    treatment=item["treatment"],
                )
                for item in document["transitions"]
            )
            findings = tuple(PlanPricingFinding(**item) for item in document["findings"])
            result = cls(
                status=PlanPricingStatus(document["status"]),
                region=document["region"],
                currency=document["currency"],
                captured_at=document["captured_at"],
                rate_type=document["rate_type"],
                monthly_low_minor=document["monthly_low_minor"],
                monthly_high_minor=document["monthly_high_minor"],
                monthly_budget_minor=document["monthly_budget_minor"],
                proposal_declared_budget_minor=document["proposal_declared_budget_minor"],
                proposal_declared_currency=document["proposal_declared_currency"],
                budget_source=document["budget_source"],
                persisted_context_sha256=document["persisted_context_sha256"],
                pricing_context_sha256=document["pricing_context_sha256"],
                estimate_disclaimer=document["estimate_disclaimer"],
                within_budget=document["within_budget"],
                plan_json_sha256=document["plan_json_sha256"],
                usage_assumptions=usage_assumptions,
                sqs_usage_assumptions=sqs_usage,
                rds_usage_assumptions=rds_usage,
                serverless_usage_assumptions=serverless_usage,
                dynamodb_usage_assumptions=dynamodb_usage,
                vpc_usage_assumptions=vpc_usage,
                batch_usage_assumptions=batch_usage,
                ecr_usage_assumptions=ecr_usage,
                lines=lines,
                transitions=transitions,
                findings=findings,
                evidence_sha256=document["evidence_sha256"],
                ecs_express_usage_assumptions=ecs_express_usage,
            )
        except (KeyError, TypeError, ValueError):
            raise PlanPricingError("pricing evidence fields are invalid") from None
        if document.get("version") == 11 and result.as_manifest_document() != document:
            raise PlanPricingError("pricing evidence is not canonical")
        if document.get("version") != 11:
            normalized = result.as_manifest_document()
            normalized.pop("evidence_sha256")
            result = replace(result, evidence_sha256=_canonical_digest(normalized))
        return result


@dataclass(frozen=True)
class CatalogRate:
    sku: str
    unit: str
    unit_price_usd: str
    effective_at: str
    published_at: str
    product_digest: str
    low_unit_price_usd: str | None = None
    low_rate_source_url: str | None = None


class PriceListClient(Protocol):
    def get_products(self, **kwargs: Any) -> dict[str, Any]: ...


@dataclass(frozen=True)
class TrustedPlanPricingContext:
    """Pricing constraints copied from an integrity-checked persisted revision.

    Callers must construct this from trusted database state, never from Nova's
    proposal. ``persisted_context_sha256`` must be the digest of that exact
    persisted context so the resulting evidence can be bound to approval.
    """

    region: str
    currency: str
    monthly_budget_minor: int | None
    persisted_context_sha256: str
    usage_assumptions: dict[str, Any] | None = None
    sqs_usage_assumptions: dict[str, Any] | None = None
    rds_usage_assumptions: dict[str, Any] | None = None
    serverless_usage_assumptions: dict[str, Any] | None = None
    dynamodb_usage_assumptions: dict[str, Any] | None = None
    vpc_usage_assumptions: dict[str, Any] | None = None
    batch_usage_assumptions: dict[str, Any] | None = None
    ecr_usage_assumptions: dict[str, Any] | None = None
    ecs_express_usage_assumptions: dict[str, Any] | None = None

    @property
    def pricing_context_sha256(self) -> str:
        """Digest all trusted price constraints and their persisted source together."""
        return _pricing_context_digest(
            self.region,
            self.currency,
            self.monthly_budget_minor,
            self.persisted_context_sha256,
            self.usage_assumptions,
            self.sqs_usage_assumptions,
            self.rds_usage_assumptions,
            self.serverless_usage_assumptions,
            self.dynamodb_usage_assumptions,
            self.vpc_usage_assumptions,
            self.batch_usage_assumptions,
            self.ecr_usage_assumptions,
            self.ecs_express_usage_assumptions,
        )

    @classmethod
    def from_persisted_revision(
        cls, revision_content: dict[str, Any], *, expected_sha256: str
    ) -> TrustedPlanPricingContext:
        """Build pricing limits from a digest-checked persisted revision, not Nova output.

        The service boundary must separately enforce the revision's lifecycle state.
        """
        if (
            not isinstance(revision_content, dict)
            or not isinstance(expected_sha256, str)
            or not re.fullmatch(r"[a-f0-9]{64}", expected_sha256)
            or _canonical_digest(revision_content) != expected_sha256
        ):
            raise PlanPricingError("persisted customer revision integrity check failed")
        target = revision_content.get("target")
        app_analysis = revision_content.get("application_analysis")
        workload_spec = (
            app_analysis.get("workload_spec") if isinstance(app_analysis, dict) else None
        )
        provider = target.get("provider") if isinstance(target, dict) else None
        region = target.get("region") if isinstance(target, dict) else None
        budget_dollars = (
            workload_spec.get("monthly_budget_usd") if isinstance(workload_spec, dict) else None
        )
        raw_usage_assumptions = (
            workload_spec.get("pricing_usage_assumptions")
            if isinstance(workload_spec, dict)
            else None
        )
        raw_sqs_usage_assumptions = (
            workload_spec.get("sqs_pricing_usage_assumptions")
            if isinstance(workload_spec, dict)
            else None
        )
        raw_rds_usage_assumptions = (
            workload_spec.get("rds_pricing_usage_assumptions")
            if isinstance(workload_spec, dict)
            else None
        )
        raw_serverless_usage_assumptions = (
            workload_spec.get("serverless_pricing_usage_assumptions")
            if isinstance(workload_spec, dict)
            else None
        )
        raw_dynamodb_usage_assumptions = (
            workload_spec.get("dynamodb_pricing_usage_assumptions")
            if isinstance(workload_spec, dict)
            else None
        )
        raw_vpc_usage_assumptions = (
            workload_spec.get("vpc_pricing_usage_assumptions")
            if isinstance(workload_spec, dict)
            else None
        )
        raw_batch_usage_assumptions = (
            workload_spec.get("batch_pricing_usage_assumptions")
            if isinstance(workload_spec, dict)
            else None
        )
        raw_ecr_usage_assumptions = (
            workload_spec.get("ecr_pricing_usage_assumptions")
            if isinstance(workload_spec, dict)
            else None
        )
        raw_ecs_express_usage_assumptions = (
            workload_spec.get("ecs_express_pricing_usage_assumptions")
            if isinstance(workload_spec, dict)
            else None
        )
        if provider != "aws":
            raise PlanPricingError("persisted customer revision is not an AWS plan")
        if not isinstance(region, str) or not re.fullmatch(r"[a-z]{2}(?:-[a-z0-9]+)+-\d", region):
            raise PlanPricingError("persisted customer revision has no trusted AWS region")
        if budget_dollars is not None and (
            isinstance(budget_dollars, bool)
            or not isinstance(budget_dollars, int)
            or budget_dollars < 1
        ):
            raise PlanPricingError("persisted customer revision has an invalid USD budget")
        if raw_usage_assumptions is None:
            usage_assumptions = None
        else:
            try:
                usage_assumptions = S3PricingUsageAssumptions.model_validate(
                    raw_usage_assumptions
                ).model_dump(mode="json")
            except (TypeError, ValueError):
                raise PlanPricingError(
                    "persisted customer revision has invalid pricing usage assumptions"
                ) from None
        if raw_sqs_usage_assumptions is None:
            sqs_usage_assumptions = None
        else:
            try:
                sqs_usage_assumptions = SqsPricingUsageAssumptions.model_validate(
                    raw_sqs_usage_assumptions
                ).model_dump(mode="json")
            except (TypeError, ValueError):
                raise PlanPricingError("persisted customer revision has invalid SQS pricing usage assumptions") from None
        if raw_rds_usage_assumptions is None:
            rds_usage_assumptions = None
        else:
            try:
                rds_usage_assumptions = RdsPricingUsageAssumptions.model_validate(
                    raw_rds_usage_assumptions
                ).model_dump(mode="json", exclude_unset=True)
            except (TypeError, ValueError):
                raise PlanPricingError("persisted customer revision has invalid RDS pricing usage assumptions") from None
        if raw_serverless_usage_assumptions is None:
            serverless_usage_assumptions = None
        else:
            try:
                serverless_usage_assumptions = ServerlessPricingUsageAssumptions.model_validate(
                    raw_serverless_usage_assumptions
                ).model_dump(mode="json")
            except (TypeError, ValueError):
                raise PlanPricingError("persisted customer revision has invalid serverless pricing usage assumptions") from None
        if raw_dynamodb_usage_assumptions is None:
            dynamodb_usage_assumptions = None
        else:
            try:
                dynamodb_usage_assumptions = DynamoDbPricingUsageAssumptions.model_validate(
                    raw_dynamodb_usage_assumptions
                ).model_dump(mode="json")
            except (TypeError, ValueError):
                raise PlanPricingError("persisted customer revision has invalid DynamoDB pricing usage assumptions") from None
        if raw_vpc_usage_assumptions is None:
            vpc_usage_assumptions = None
        else:
            try:
                vpc_usage_assumptions = VpcPricingUsageAssumptions.model_validate(
                    raw_vpc_usage_assumptions
                ).model_dump(mode="json", exclude_none=True)
            except (TypeError, ValueError):
                raise PlanPricingError("persisted customer revision has invalid VPC pricing usage assumptions") from None
        if raw_batch_usage_assumptions is None:
            batch_usage_assumptions = None
        else:
            try:
                batch_usage_assumptions = BatchPricingUsageAssumptions.model_validate(
                    raw_batch_usage_assumptions
                ).model_dump(mode="json", exclude_none=True)
            except (TypeError, ValueError):
                raise PlanPricingError("persisted customer revision has invalid Batch pricing usage assumptions") from None
        if raw_ecr_usage_assumptions is None:
            ecr_usage_assumptions = None
        else:
            try:
                ecr_usage_assumptions = EcrPricingUsageAssumptions.model_validate(
                    raw_ecr_usage_assumptions
                ).model_dump(mode="json")
            except (TypeError, ValueError):
                raise PlanPricingError("persisted customer revision has invalid ECR pricing usage assumptions") from None
        if raw_ecs_express_usage_assumptions is None:
            ecs_express_usage_assumptions = None
        else:
            try:
                ecs_express_usage_assumptions = EcsExpressPricingUsageAssumptions.model_validate(
                    raw_ecs_express_usage_assumptions
                ).model_dump(mode="json")
            except (TypeError, ValueError):
                raise PlanPricingError("persisted customer revision has invalid ECS Express pricing usage assumptions") from None
        return cls(
            region=region,
            currency="USD",
            monthly_budget_minor=None if budget_dollars is None else budget_dollars * 100,
            persisted_context_sha256=expected_sha256,
            usage_assumptions=usage_assumptions,
            sqs_usage_assumptions=sqs_usage_assumptions,
            rds_usage_assumptions=rds_usage_assumptions,
            serverless_usage_assumptions=serverless_usage_assumptions,
            dynamodb_usage_assumptions=dynamodb_usage_assumptions,
            vpc_usage_assumptions=vpc_usage_assumptions,
            batch_usage_assumptions=batch_usage_assumptions,
            ecr_usage_assumptions=ecr_usage_assumptions,
            ecs_express_usage_assumptions=ecs_express_usage_assumptions,
        )


class AwsPriceListCatalog:
    """Bounded AWS public price lookup; no billing history or write API calls."""

    _cache: ClassVar[dict[tuple[str, str], tuple[float, CatalogRate]]] = {}
    _cache_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(
        self,
        client: PriceListClient | None = None,
        *,
        cache_ttl_seconds: int = 3_600,
        clock: Any = time.monotonic,
    ) -> None:
        if cache_ttl_seconds < 0 or cache_ttl_seconds > 86_400:
            raise ValueError("price catalog cache lifetime is invalid")
        self.client = client or boto3.client("pricing", region_name="us-east-1")
        self.cache_ttl_seconds = cache_ttl_seconds
        self.clock = clock

    def ebs_gp3_storage_rate(self, region: str) -> CatalogRate:
        if not isinstance(region, str) or not re.fullmatch(r"[a-z]{2}(?:-[a-z0-9]+)+-\d", region):
            raise PlanPricingError("plan region is invalid")
        cache_key = (region, "AmazonEC2:gp3:GB-Mo:OnDemand")
        now = self.clock()
        with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached and cached[0] > now:
                return cached[1]

        filters = [
            {"Type": "TERM_MATCH", "Field": "productFamily", "Value": "Storage"},
            {"Type": "TERM_MATCH", "Field": "volumeApiName", "Value": "gp3"},
            {"Type": "TERM_MATCH", "Field": "regionCode", "Value": region},
        ]
        try:
            response = self.client.get_products(
                ServiceCode="AmazonEC2",
                Filters=filters,
                MaxResults=100,
            )
        except (BotoCoreError, ClientError, OSError, ValueError, TypeError):
            raise PriceListUnavailableError("AWS regional price lookup is unavailable") from None
        if not isinstance(response, dict):
            raise PriceListUnavailableError("AWS regional price response is malformed")
        if response.get("NextToken"):
            raise PlanPricingError("AWS regional price results are truncated")
        raw_products = response.get("PriceList")
        if not isinstance(raw_products, list) or len(raw_products) != 1:
            raise PlanPricingError("AWS regional price match is missing or ambiguous")
        rate = _parse_gp3_product(raw_products[0], region)
        with self._cache_lock:
            self._cache[cache_key] = (now + self.cache_ttl_seconds, rate)
        return rate

    def s3_standard_storage_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonS3",
            region,
            "s3-standard-storage",
            [
                ("productFamily", "Storage"),
                ("storageClass", "General Purpose"),
                ("volumeType", "Standard"),
                ("regionCode", region),
            ],
            "GB-Mo",
        )

    def s3_standard_request_rate(self, region: str, *, tier: int) -> CatalogRate:
        if tier not in {1, 2}:
            raise PlanPricingError("S3 request price tier is unsupported")
        return self._regional_rate(
            "AmazonS3",
            region,
            f"s3-standard-requests-tier-{tier}",
            [
                ("productFamily", "API Request"),
                ("group", f"S3-API-Tier{tier}"),
                ("regionCode", region),
            ],
            "Requests",
        )

    def sqs_request_rate(self, region: str, *, fifo: bool) -> CatalogRate:
        queue_type = "FIFO (first-in, first-out)" if fifo else "Standard"
        return self._regional_rate(
            "AWSQueueService",
            region,
            f"sqs-requests-{queue_type}",
            [
                ("productFamily", "API Request"),
                ("queueType", queue_type),
                ("regionCode", region),
            ],
            "Requests",
        )

    def rds_mysql_instance_rate(self, region: str, instance_class: str) -> CatalogRate:
        if not isinstance(instance_class, str) or not re.fullmatch(
            r"db\.(?:m|r)[0-9]+[a-z]?\.[a-z0-9]+", instance_class
        ):
            raise PlanPricingError("RDS instance class is unsupported for bounded pricing")
        return self._regional_rate(
            "AmazonRDS",
            region,
            f"rds-mysql-instance-single-az-{instance_class}",
            [
                ("productFamily", "Database Instance"),
                ("databaseEngine", "MySQL"),
                ("instanceType", instance_class),
                ("licenseModel", "No license required"),
                ("deploymentOption", "Single-AZ"),
                ("usagetype", f"InstanceUsage:{instance_class}"),
                ("regionCode", region),
            ],
            "Hrs",
        )

    def rds_mysql_gp3_storage_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonRDS",
            region,
            "rds-mysql-gp3-storage-single-az",
            [
                ("productFamily", "Database Storage"),
                ("databaseEngine", "MySQL"),
                ("deploymentOption", "Single-AZ"),
                ("usagetype", "RDS:GP3-Storage"),
                ("regionCode", region),
            ],
            "GB-Mo",
        )

    def rds_mysql_backup_storage_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonRDS",
            region,
            "rds-mysql-backup-storage",
            [
                ("productFamily", "Storage Snapshot"),
                ("databaseEngine", "MySQL"),
                ("deploymentOption", "Single-AZ"),
                ("usagetype", "RDS:ChargedBackupUsage"),
                ("regionCode", region),
            ],
            "GB-Mo",
        )

    def aurora_serverless_v2_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonRDS",
            region,
            "aurora-postgresql-serverless-v2-standard",
            [
                ("productFamily", "ServerlessV2"),
                ("databaseEngine", "Aurora PostgreSQL"),
                ("usagetype", "Aurora:ServerlessV2Usage"),
                ("regionCode", region),
            ],
            "ACU-Hr",
        )

    def aurora_standard_storage_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonRDS",
            region,
            "aurora-postgresql-standard-storage",
            [
                ("productFamily", "Database Storage"),
                ("databaseEngine", "Aurora PostgreSQL"),
                ("volumeType", "General Purpose-Aurora"),
                ("usagetype", "Aurora:StorageUsage"),
                ("regionCode", region),
            ],
            "GB-Mo",
        )

    def aurora_standard_io_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonRDS",
            region,
            "aurora-postgresql-standard-io",
            [
                ("productFamily", "System Operation"),
                ("databaseEngine", "Aurora PostgreSQL"),
                ("group", "Aurora I/O Operation"),
                ("usagetype", "Aurora:StorageIOUsage"),
                ("regionCode", region),
            ],
            "IOs",
        )

    def aurora_backup_overage_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonRDS",
            region,
            "aurora-postgresql-backup-storage",
            [
                ("productFamily", "Storage Snapshot"),
                ("databaseEngine", "Aurora PostgreSQL"),
                ("usagetype", "Aurora:BackupUsage"),
                ("regionCode", region),
            ],
            "GB-Mo",
        )

    def aurora_secret_storage_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AWSSecretsManager",
            region,
            "aurora-managed-secret-storage",
            [
                ("productFamily", "Secret"),
                ("group", "AWSSecretsManager-Secret"),
                ("regionCode", region),
            ],
            "Secrets",
        )

    def aurora_secret_api_request_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AWSSecretsManager",
            region,
            "aurora-managed-secret-api-requests",
            [
                ("productFamily", "API Request"),
                ("group", "AWSSecretsManager-APIRequest"),
                ("regionCode", region),
            ],
            "API Requests",
        )

    def dynamodb_read_request_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonDynamoDB",
            region,
            "dynamodb-on-demand-standard-read-request-units",
            [
                ("productFamily", "Amazon DynamoDB PayPerRequest Throughput"),
                ("group", "DDB-ReadUnits"),
                ("regionCode", region),
            ],
            "ReadRequestUnits",
        )

    def dynamodb_write_request_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonDynamoDB",
            region,
            "dynamodb-on-demand-standard-write-request-units",
            [
                ("productFamily", "Amazon DynamoDB PayPerRequest Throughput"),
                ("group", "DDB-WriteUnits"),
                ("regionCode", region),
            ],
            "WriteRequestUnits",
        )

    def dynamodb_standard_storage_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonDynamoDB",
            region,
            "dynamodb-standard-table-storage",
            [
                ("productFamily", "Database Storage"),
                ("volumeType", "Amazon DynamoDB - Indexed DataStore"),
                ("regionCode", region),
            ],
            "GB-Mo",
        )

    def dynamodb_pitr_storage_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonDynamoDB",
            region,
            "dynamodb-pitr-backup-storage",
            [
                ("productFamily", "Database Storage"),
                ("volumeType", "Amazon DynamoDB - Point-In-Time-Restore (PITR) Backup Storage"),
                ("regionCode", region),
            ],
            "GB-Mo",
        )

    def lambda_request_rate(self, region: str, architecture: str) -> CatalogRate:
        if architecture not in {"x86_64", "arm64"}:
            raise PlanPricingError("Lambda architecture is unsupported for bounded pricing")
        suffix = "-ARM" if architecture == "arm64" else ""
        return self._regional_rate(
            "AWSLambda",
            region,
            f"lambda-requests-{architecture}",
            [
                ("productFamily", "Serverless"),
                ("group", f"AWS-Lambda-Requests{suffix}"),
                ("regionCode", region),
            ],
            "Requests",
        )

    def lambda_duration_rate(self, region: str, architecture: str) -> CatalogRate:
        if architecture not in {"x86_64", "arm64"}:
            raise PlanPricingError("Lambda architecture is unsupported for bounded pricing")
        suffix = "-ARM" if architecture == "arm64" else ""
        return self._regional_rate(
            "AWSLambda",
            region,
            f"lambda-duration-{architecture}",
            [
                ("productFamily", "Serverless"),
                ("group", f"AWS-Lambda-Duration{suffix}"),
                ("regionCode", region),
            ],
            "Lambda-GB-Second",
        )

    def cloudwatch_log_ingestion_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonCloudWatch",
            region,
            "cloudwatch-standard-log-ingestion",
            [
                ("productFamily", "Data Payload"),
                ("group", "Ingested Logs"),
                ("groupDescription", "Existing system, application, and custom log files"),
                ("version", "Current"),
                ("operation", "PutLogEvents"),
                ("logsDestination", "Amazon CloudWatch Logs"),
                ("regionCode", region),
            ],
            "GB",
        )

    def cloudwatch_standard_log_storage_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonCloudWatch",
            region,
            "cloudwatch-standard-log-storage",
            [
                ("productFamily", "Storage Snapshot"),
                ("groupDescription", "Amazon CloudWatch Logs Storage Current version"),
                ("version", "Current"),
                ("regionCode", region),
            ],
            "GB-Mo",
        )

    def ecr_standard_storage_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonECR",
            region,
            "ecr-standard-storage",
            [
                ("productFamily", "EC2 Container Registry"),
                ("storageType", "S3"),
                ("regionCode", region),
            ],
            "GB-Mo",
        )

    def http_api_request_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonApiGateway",
            region,
            "api-gateway-http-api-requests",
            [
                ("productFamily", "API Calls"),
                ("operation", "ApiGatewayHttpApi"),
                ("regionCode", region),
            ],
            "Requests",
        )

    def aws_internet_egress_rate(self, region: str) -> CatalogRate:
        rate = self._regional_rate(
            "AWSDataTransfer",
            region,
            "aws-internet-egress",
            [
                ("productFamily", "Data Transfer"),
                ("fromRegionCode", region),
                ("toLocation", "External"),
                ("transferType", "AWS Outbound"),
            ],
            "GB",
        )
        # AWS's public data transfer page publishes a lowest Internet egress
        # tier of $0.05/GB above 150 TB/month. Price List returns only the first
        # tier for this usage code, so use that documented rate only as the
        # lower estimate while preserving the matched catalog product digest.
        return CatalogRate(
            rate.sku,
            rate.unit,
            rate.unit_price_usd,
            rate.effective_at,
            rate.published_at,
            rate.product_digest,
            low_unit_price_usd="0.05",
            low_rate_source_url="https://aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer",
        )

    def nat_gateway_hourly_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonEC2", region, "nat-gateway-hours",
            [
                ("productFamily", "NAT Gateway"),
                ("groupDescription", "Hourly charge for NAT Gateways"),
                ("regionCode", region),
            ],
            "Hrs",
        )

    def nat_gateway_data_processing_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonEC2", region, "nat-gateway-data-processing",
            [
                ("productFamily", "NAT Gateway"),
                ("groupDescription", "Charge for per GB data processed by NatGateways"),
                ("regionCode", region),
            ],
            "GB",
        )

    def public_ipv4_in_use_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonVPC", region, "public-ipv4-in-use",
            [
                ("group", "VPCPublicIPv4Address"),
                ("groupDescription", "Hourly charge for In-use Public IPv4 Addresses"),
                ("regionCode", region),
            ],
            "Hrs",
        )

    def application_load_balancer_hourly_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AWSELB", region, "application-load-balancer-hours",
            [
                ("productFamily", "Load Balancer-Application"),
                ("group", "ELB:Balancing"),
                ("groupDescription", "LoadBalancer hourly usage by Application Load Balancer"),
                ("regionCode", region),
            ],
            "Hrs",
        )

    def application_load_balancer_lcu_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AWSELB", region, "application-load-balancer-lcu-hours",
            [
                ("productFamily", "Load Balancer-Application"),
                ("group", "ELB:Balancing"),
                ("groupDescription", "Used Application Load Balancer capacity units-hr"),
                ("regionCode", region),
            ],
            "LCU-Hrs",
        )

    def cloudwatch_standard_alarm_metric_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonCloudWatch", region, "cloudwatch-standard-alarm-metric-month",
            [
                ("productFamily", "Alarm"),
                ("group", "Alarm"),
                ("groupDescription", "CloudWatch Alarms"),
                ("usagetype", "CW:AlarmMonitorUsage"),
                ("regionCode", region),
            ],
            "Alarms",
        )

    def interface_vpc_endpoint_hourly_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonVPC",
            region,
            "interface-vpc-endpoint-hours",
            [
                ("productFamily", "VpcEndpoint"),
                ("endpointType", "PrivateLink"),
                ("group", "VPCE:VpcEndpoint"),
                ("groupDescription", "Hourly charge for VPC Endpoints"),
                ("operation", "VpcEndpoint"),
                ("regionCode", region),
            ],
            "Hrs",
        )

    def interface_vpc_endpoint_data_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AmazonVPC",
            region,
            "interface-vpc-endpoint-data",
            [
                ("productFamily", "VpcEndpoint"),
                ("endpointType", "PrivateLink"),
                ("group", "VPCE:VpcEndpoint"),
                ("groupDescription", "Charge for per GB data processed by VPC Endpoints"),
                ("operation", "VpcEndpoint"),
                ("regionCode", region),
            ],
            "GB",
        )

    def regional_data_transfer_rate(self, region: str) -> CatalogRate:
        return self._regional_rate(
            "AWSDataTransfer", region, "regional-data-transfer",
            [
                ("productFamily", "Data Transfer"),
                ("fromRegionCode", region),
                ("toRegionCode", region),
                ("transferType", "IntraRegion"),
            ],
            "GB",
        )

    def fargate_linux_x86_rate(self, region: str, *, dimension: str) -> CatalogRate:
        """Find the exact Linux/x86 On-Demand Fargate hourly rate for one dimension."""
        if dimension not in {"vcpu", "memory"}:
            raise PlanPricingError("Fargate price dimension is unsupported")
        if not isinstance(region, str) or not re.fullmatch(r"[a-z]{2}(?:-[a-z0-9]+)+-\d", region):
            raise PlanPricingError("plan region is invalid")
        rate_key = f"fargate-linux-x86-{dimension}-hourly"
        cache_key = (region, rate_key)
        now = self.clock()
        with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached and cached[0] > now:
                return cached[1]

        attribute = "cputype" if dimension == "vcpu" else "memorytype"
        value = "perCPU" if dimension == "vcpu" else "perGB"
        suffix = (
            "Fargate-vCPU-Hours:perCPU"
            if dimension == "vcpu"
            else "Fargate-GB-Hours"
        )
        filters = [
            {"Type": "TERM_MATCH", "Field": "productFamily", "Value": "Compute"},
            {"Type": "TERM_MATCH", "Field": "regionCode", "Value": region},
            {"Type": "TERM_MATCH", "Field": attribute, "Value": value},
        ]
        try:
            response = self.client.get_products(
                ServiceCode="AmazonECS", Filters=filters, MaxResults=100
            )
        except (BotoCoreError, ClientError, OSError, ValueError, TypeError):
            raise PriceListUnavailableError("AWS regional price lookup is unavailable") from None
        if not isinstance(response, dict):
            raise PriceListUnavailableError("AWS regional price response is malformed")
        if response.get("NextToken"):
            raise PlanPricingError("AWS regional Fargate price results are truncated")
        raw_products = response.get("PriceList")
        if not isinstance(raw_products, list):
            raise PriceListUnavailableError("AWS regional Fargate price response is malformed")
        matches: list[tuple[str, dict[str, str]]] = []
        for raw in raw_products:
            try:
                product_doc = json.loads(raw) if isinstance(raw, str) else None
            except (json.JSONDecodeError, TypeError):
                raise PlanPricingError("AWS regional Fargate product is malformed") from None
            product = product_doc.get("product") if isinstance(product_doc, dict) else None
            attrs = product.get("attributes") if isinstance(product, dict) else None
            usage_type = attrs.get("usagetype") if isinstance(attrs, dict) else None
            if (
                isinstance(product, dict)
                and isinstance(attrs, dict)
                and isinstance(product_doc, dict)
                and
                product_doc.get("serviceCode") == "AmazonECS"
                and product.get("productFamily") == "Compute"
                and attrs.get("regionCode") == region
                and attrs.get(attribute) == value
                and isinstance(usage_type, str)
                and usage_type.endswith(suffix)
                and "cpuArchitecture" not in attrs
                and attrs.get("operatingSystem") in (None, "Linux")
                and attrs.get("tenancy") == "Shared"
            ):
                matches.append((raw, attrs))
        if len(matches) != 1:
            raise PlanPricingError("AWS regional Fargate price match is missing or ambiguous")
        expected = {
            "productFamily": "Compute",
            "regionCode": region,
            attribute: value,
        }
        rate = _parse_regional_product(matches[0][0], "AmazonECS", expected, "hours")
        with self._cache_lock:
            self._cache[cache_key] = (now + self.cache_ttl_seconds, rate)
        return rate

    def _regional_rate(
        self,
        service_code: str,
        region: str,
        rate_key: str,
        attributes: list[tuple[str, str]],
        expected_unit: str,
    ) -> CatalogRate:
        if not isinstance(region, str) or not re.fullmatch(r"[a-z]{2}(?:-[a-z0-9]+)+-\d", region):
            raise PlanPricingError("plan region is invalid")
        cache_key = (region, rate_key)
        now = self.clock()
        with self._cache_lock:
            cached = self._cache.get(cache_key)
            if cached and cached[0] > now:
                return cached[1]
        filters = [
            {"Type": "TERM_MATCH", "Field": field, "Value": value}
            for field, value in attributes
        ]
        try:
            response = self.client.get_products(
                ServiceCode=service_code, Filters=filters, MaxResults=100
            )
        except (BotoCoreError, ClientError, OSError, ValueError, TypeError):
            raise PriceListUnavailableError("AWS regional price lookup is unavailable") from None
        if not isinstance(response, dict):
            raise PriceListUnavailableError("AWS regional price response is malformed")
        if response.get("NextToken"):
            raise PlanPricingError("AWS regional price results are truncated")
        raw_products = response.get("PriceList")
        if not isinstance(raw_products, list) or len(raw_products) != 1:
            raise PlanPricingError("AWS regional price match is missing or ambiguous")
        rate = _parse_regional_product(
            raw_products[0], service_code, dict(attributes), expected_unit
        )
        with self._cache_lock:
            self._cache[cache_key] = (now + self.cache_ttl_seconds, rate)
        return rate


# These resources have no direct hourly, request, storage, or transfer charge.
# Any billable companion resources and usage-based services are priced
# separately; an unlisted resource never inherits this zero-cost treatment.
ZERO_DIRECT_CHARGE_RESOURCE_TYPES = frozenset(
    {
        "terraform_data",
        "aws_vpc",
        "aws_internet_gateway",
        "aws_subnet",
        "aws_route_table",
        "aws_route",
        "aws_route_table_association",
        "aws_db_subnet_group",
        "aws_main_route_table_association",
        "aws_security_group",
        "aws_security_group_rule",
        "aws_vpc_security_group_ingress_rule",
        "aws_vpc_security_group_egress_rule",
        "aws_network_acl",
        "aws_network_acl_rule",
        "aws_iam_role",
        "aws_iam_policy",
        "aws_iam_role_policy",
        "aws_iam_role_policy_attachment",
        "aws_iam_instance_profile",
        "aws_key_pair",
        "aws_apigatewayv2_route",
        "aws_apigatewayv2_deployment",
        "aws_batch_compute_environment",
        "aws_batch_job_queue",
        "aws_batch_job_definition",
    }
)


def evaluate_generated_plan_pricing(
    document: dict[str, Any],
    *,
    trusted_context: TrustedPlanPricingContext,
    proposal_declared_budget_minor: int | None = None,
    proposal_declared_currency: str | None = None,
    catalog: AwsPriceListCatalog | None = None,
    captured_at: datetime | None = None,
) -> GeneratedPlanPricingEvidence:
    """Price plan resources from trusted mappings and explicit plan quantities.

    Nova-authored price, SKU, and usage text is not read here. EBS gp3, plain
    S3 Standard usage, Standard/FIFO SQS billed request units, and bounded
    private Single-AZ RDS MySQL configurations have mappings. Any unsupported
    resource or price-driving usage dimension prevents approval.
    """
    if not isinstance(trusted_context, TrustedPlanPricingContext):
        raise PlanPricingError("trusted persisted pricing context is required")
    region = trusted_context.region
    currency = trusted_context.currency
    monthly_budget_minor = trusted_context.monthly_budget_minor
    persisted_context_sha256 = trusted_context.persisted_context_sha256
    if not isinstance(persisted_context_sha256, str) or not re.fullmatch(
        r"[a-f0-9]{64}", persisted_context_sha256
    ):
        raise PlanPricingError("trusted persisted context digest is invalid")
    if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
        raise PlanPricingError("trusted pricing currency is invalid")
    if not isinstance(region, str) or not re.fullmatch(r"[a-z]{2}(?:-[a-z0-9]+)+-\d", region):
        raise PlanPricingError("trusted pricing region is invalid")
    if proposal_declared_budget_minor is not None and (
        isinstance(proposal_declared_budget_minor, bool)
        or not isinstance(proposal_declared_budget_minor, int)
        or proposal_declared_budget_minor < 0
    ):
        raise PlanPricingError("proposal-declared budget is invalid")
    if proposal_declared_currency is not None and (
        not isinstance(proposal_declared_currency, str)
        or not re.fullmatch(r"[A-Z]{3}", proposal_declared_currency)
    ):
        raise PlanPricingError("proposal-declared currency is invalid")
    captured_at = captured_at or datetime.now(UTC)
    if captured_at.tzinfo is None:
        raise PlanPricingError("pricing evidence timestamp must include a timezone")
    captured_at_text = captured_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if (
        not isinstance(document, dict)
        or document.get("applyable") is not True
        or document.get("errored") is not False
    ):
        return _evidence(
            PlanPricingStatus.INCOMPLETE,
            region,
            currency,
            captured_at_text,
            monthly_budget_minor,
            document,
            (),
            (
                PlanPricingFinding(
                    "terraform_plan_not_reviewable",
                    None,
                    "Terraform did not provide a clean, applyable plan for pricing review.",
                ),
            ),
            proposal_declared_budget_minor=proposal_declared_budget_minor,
            proposal_declared_currency=proposal_declared_currency,
            persisted_context_sha256=persisted_context_sha256,
            usage_assumptions=trusted_context.usage_assumptions,
            sqs_usage_assumptions=trusted_context.sqs_usage_assumptions,
            rds_usage_assumptions=trusted_context.rds_usage_assumptions,
            serverless_usage_assumptions=trusted_context.serverless_usage_assumptions,
            dynamodb_usage_assumptions=trusted_context.dynamodb_usage_assumptions,
            vpc_usage_assumptions=trusted_context.vpc_usage_assumptions,
            batch_usage_assumptions=trusted_context.batch_usage_assumptions,
            ecr_usage_assumptions=trusted_context.ecr_usage_assumptions,
            ecs_express_usage_assumptions=trusted_context.ecs_express_usage_assumptions,
        )
    if monthly_budget_minor is not None and (
        isinstance(monthly_budget_minor, bool)
        or not isinstance(monthly_budget_minor, int)
        or monthly_budget_minor < 0
    ):
        raise PlanPricingError("monthly budget is invalid")
    if currency != "USD":
        return _evidence(
            PlanPricingStatus.INCOMPLETE,
            region,
            currency,
            captured_at_text,
            monthly_budget_minor,
            document,
            (),
            (
                PlanPricingFinding(
                    "unsupported_currency", None, "Only USD price evidence is available."
                ),
            ),
            proposal_declared_budget_minor=proposal_declared_budget_minor,
            proposal_declared_currency=proposal_declared_currency,
            persisted_context_sha256=persisted_context_sha256,
            usage_assumptions=trusted_context.usage_assumptions,
            sqs_usage_assumptions=trusted_context.sqs_usage_assumptions,
            rds_usage_assumptions=trusted_context.rds_usage_assumptions,
            serverless_usage_assumptions=trusted_context.serverless_usage_assumptions,
            dynamodb_usage_assumptions=trusted_context.dynamodb_usage_assumptions,
            vpc_usage_assumptions=trusted_context.vpc_usage_assumptions,
            batch_usage_assumptions=trusted_context.batch_usage_assumptions,
            ecr_usage_assumptions=trusted_context.ecr_usage_assumptions,
            ecs_express_usage_assumptions=trusted_context.ecs_express_usage_assumptions,
        )
    if proposal_declared_currency is not None and proposal_declared_currency != currency:
        return _evidence(
            PlanPricingStatus.INCOMPLETE,
            region,
            currency,
            captured_at_text,
            monthly_budget_minor,
            document,
            (),
            (
                PlanPricingFinding(
                    "proposal_currency_context_mismatch",
                    None,
                    "Nova's currency does not match the persisted customer currency.",
                ),
            ),
            proposal_declared_budget_minor=proposal_declared_budget_minor,
            proposal_declared_currency=proposal_declared_currency,
            persisted_context_sha256=persisted_context_sha256,
            usage_assumptions=trusted_context.usage_assumptions,
            sqs_usage_assumptions=trusted_context.sqs_usage_assumptions,
            rds_usage_assumptions=trusted_context.rds_usage_assumptions,
            serverless_usage_assumptions=trusted_context.serverless_usage_assumptions,
            dynamodb_usage_assumptions=trusted_context.dynamodb_usage_assumptions,
            vpc_usage_assumptions=trusted_context.vpc_usage_assumptions,
            batch_usage_assumptions=trusted_context.batch_usage_assumptions,
            ecr_usage_assumptions=trusted_context.ecr_usage_assumptions,
            ecs_express_usage_assumptions=trusted_context.ecs_express_usage_assumptions,
        )
    if (
        proposal_declared_budget_minor is not None
        and proposal_declared_budget_minor != monthly_budget_minor
    ):
        return _evidence(
            PlanPricingStatus.INCOMPLETE,
            region,
            currency,
            captured_at_text,
            monthly_budget_minor,
            document,
            (),
            (
                PlanPricingFinding(
                    "proposal_budget_context_mismatch",
                    None,
                    "Nova's budget statement does not match the persisted customer budget.",
                ),
            ),
            proposal_declared_budget_minor=proposal_declared_budget_minor,
            proposal_declared_currency=proposal_declared_currency,
            persisted_context_sha256=persisted_context_sha256,
            usage_assumptions=trusted_context.usage_assumptions,
            sqs_usage_assumptions=trusted_context.sqs_usage_assumptions,
            rds_usage_assumptions=trusted_context.rds_usage_assumptions,
            serverless_usage_assumptions=trusted_context.serverless_usage_assumptions,
            dynamodb_usage_assumptions=trusted_context.dynamodb_usage_assumptions,
            vpc_usage_assumptions=trusted_context.vpc_usage_assumptions,
            batch_usage_assumptions=trusted_context.batch_usage_assumptions,
            ecr_usage_assumptions=trusted_context.ecr_usage_assumptions,
            ecs_express_usage_assumptions=trusted_context.ecs_express_usage_assumptions,
        )
    if not _plan_region_matches(document, region):
        return _evidence(
            PlanPricingStatus.INCOMPLETE,
            region,
            currency,
            captured_at_text,
            monthly_budget_minor,
            document,
            (),
            (
                PlanPricingFinding(
                    "plan_region_mismatch", None, "Plan and trusted pricing regions do not match."
                ),
            ),
            proposal_declared_budget_minor=proposal_declared_budget_minor,
            persisted_context_sha256=persisted_context_sha256,
            usage_assumptions=trusted_context.usage_assumptions,
            sqs_usage_assumptions=trusted_context.sqs_usage_assumptions,
            rds_usage_assumptions=trusted_context.rds_usage_assumptions,
            serverless_usage_assumptions=trusted_context.serverless_usage_assumptions,
            dynamodb_usage_assumptions=trusted_context.dynamodb_usage_assumptions,
            vpc_usage_assumptions=trusted_context.vpc_usage_assumptions,
            batch_usage_assumptions=trusted_context.batch_usage_assumptions,
            ecr_usage_assumptions=trusted_context.ecr_usage_assumptions,
            ecs_express_usage_assumptions=trusted_context.ecs_express_usage_assumptions,
        )

    resources = _planned_managed_resources(document)
    changes = _changes_by_address(document)
    transitions, transition_findings = _classify_aws_transitions(resources, changes)
    pricing_catalog = catalog
    lines: list[PlanCostLine] = []
    findings: list[PlanPricingFinding] = list(transition_findings)
    unavailable = False
    s3_buckets: list[dict[str, Any]] = []
    sqs_queues: list[dict[str, Any]] = []
    rds_instances: list[dict[str, Any]] = []
    aurora_clusters: list[dict[str, Any]] = []
    aurora_instances: list[dict[str, Any]] = []
    dynamodb_tables: list[dict[str, Any]] = []
    nat_gateways: list[dict[str, Any]] = []
    elastic_ips: list[dict[str, Any]] = []
    interface_vpc_endpoints: list[dict[str, Any]] = []
    planned_subnets: list[dict[str, Any]] = []
    lambda_functions: list[dict[str, Any]] = []
    http_apis: list[dict[str, Any]] = []
    lambda_log_groups: list[dict[str, Any]] = []
    ecr_repositories: list[dict[str, Any]] = []
    ecs_express_services: list[dict[str, Any]] = []
    priced_ecr_addresses: set[str] = set()
    for resource in resources:
        address = resource["address"]
        resource_type = resource["type"]
        values = resource["values"]
        if resource_type == "aws_nat_gateway":
            nat_gateways.append(resource)
            continue
        if resource_type == "aws_eip":
            elastic_ips.append(resource)
            continue
        if resource_type == "aws_vpc_endpoint":
            endpoint_type = values.get("vpc_endpoint_type")
            service_name = values.get("service_name")
            route_table_ids = values.get("route_table_ids")
            if (
                endpoint_type == "Gateway"
                and service_name in {
                    f"com.amazonaws.{region}.s3",
                    f"com.amazonaws.{region}.dynamodb",
                }
                and isinstance(route_table_ids, list)
                and route_table_ids
                and all(isinstance(item, str) and item for item in route_table_ids)
                and len(set(route_table_ids)) == len(route_table_ids)
            ):
                # AWS does not charge for S3 and DynamoDB gateway endpoints.
                continue
            interface_vpc_endpoints.append(resource)
            continue
        if resource_type == "aws_subnet":
            planned_subnets.append(resource)
            continue
        if resource_type in ZERO_DIRECT_CHARGE_RESOURCE_TYPES:
            continue
        if resource_type == "aws_s3_bucket":
            s3_buckets.append(resource)
            continue
        if resource_type == "aws_sqs_queue":
            sqs_queues.append(resource)
            continue
        if resource_type == "aws_db_instance":
            rds_instances.append(resource)
            continue
        if resource_type == "aws_rds_cluster":
            aurora_clusters.append(resource)
            continue
        if resource_type == "aws_rds_cluster_instance":
            aurora_instances.append(resource)
            continue
        if resource_type == "aws_dynamodb_table":
            dynamodb_tables.append(resource)
            continue
        if resource_type == "aws_lambda_function":
            lambda_functions.append(resource)
            continue
        if resource_type == "aws_cloudwatch_log_group":
            lambda_log_groups.append(resource)
            continue
        if resource_type == "aws_ecr_repository":
            ecr_repositories.append(resource)
            continue
        if resource_type == "aws_ecs_express_gateway_service":
            ecs_express_services.append(resource)
            continue
        if resource_type == "aws_apigatewayv2_api":
            http_apis.append(resource)
            continue
        if resource_type == "aws_apigatewayv2_stage":
            stage_error = _validate_http_api_stage(values, changes.get(address))
            if stage_error:
                findings.append(PlanPricingFinding(stage_error[0], address, stage_error[1]))
            continue
        if resource_type == "aws_apigatewayv2_integration":
            integration_error = _validate_http_api_integration(values, changes.get(address))
            if integration_error:
                findings.append(PlanPricingFinding(integration_error[0], address, integration_error[1]))
            continue
        if resource_type != "aws_ebs_volume":
            findings.append(
                PlanPricingFinding(
                    "resource_pricing_unavailable",
                    address,
                    "This resource has no verified price and usage calculation yet.",
                )
            )
            continue
        change = changes.get(address)
        if change is None:
            # The transition classifier already records that a final resource
            # has no matching change object. Do not manufacture a second price
            # finding from the same missing evidence.
            continue
        error = _validate_gp3_volume(values, change)
        if error:
            findings.append(PlanPricingFinding(error[0], address, error[1]))
            continue
        try:
            if pricing_catalog is None:
                pricing_catalog = AwsPriceListCatalog()
            rate = pricing_catalog.ebs_gp3_storage_rate(region)
        except PriceListUnavailableError:
            unavailable = True
            findings.append(
                PlanPricingFinding(
                    "regional_price_lookup_unavailable",
                    address,
                    "DavDeploy could not verify the current regional AWS price.",
                )
            )
            continue
        except PlanPricingError:
            findings.append(
                PlanPricingFinding(
                    "regional_price_ambiguous",
                    address,
                    "DavDeploy could not identify one exact regional AWS price.",
                )
            )
            continue
        quantity = values["size"]
        unit_cost = Decimal(rate.unit_price_usd)
        monthly_decimal = unit_cost * quantity
        monthly_minor = int((monthly_decimal * 100).quantize(Decimal(1), rounding=ROUND_CEILING))
        lines.append(
            PlanCostLine(
                address=address,
                resource_type=resource_type,
                description="Amazon EBS gp3 storage",
                quantity=quantity,
                unit="GB-Mo",
                unit_price_usd=rate.unit_price_usd,
                monthly_cost_minor=monthly_minor,
                catalog_sku=rate.sku,
                catalog_product_sha256=rate.product_digest,
                catalog_published_at=rate.published_at,
                catalog_effective_at=rate.effective_at,
            )
        )

    ecs_express_shape_valid = False
    if ecs_express_services:
        ecs_express_shape_valid = _validate_ecs_express_pricing_shape(
            document,
            resources,
            ecs_express_services,
            ecr_repositories,
            lambda_log_groups,
            region,
        )

    ecr_usage_document = trusted_context.ecr_usage_assumptions
    if ecr_repositories:
        if not ecs_express_shape_valid:
            findings.append(PlanPricingFinding(
                "ecr_supporting_costs_unpriced", None,
                "ECR standard storage is priced when bounded; archive retrieval, cross-region or internet transfer, image signing, replication, and other linked usage remain unpriced.",
            ))
        if ecr_usage_document is None:
            findings.append(PlanPricingFinding(
                "ecr_storage_assumptions_missing", ecr_repositories[0]["address"],
                "Monthly stored image GB-month bounds are required for each planned private ECR repository.",
            ))
        else:
            try:
                ecr_usage = EcrPricingUsageAssumptions.model_validate(
                    ecr_usage_document
                )
            except (TypeError, ValueError):
                findings.append(PlanPricingFinding(
                    "ecr_storage_assumptions_invalid", ecr_repositories[0]["address"],
                    "Persisted ECR storage usage assumptions are invalid.",
                ))
            else:
                expected_repositories = {item["address"] for item in ecr_repositories}
                if set(ecr_usage.repositories) != expected_repositories:
                    findings.append(PlanPricingFinding(
                        "ecr_storage_resource_mismatch", ecr_repositories[0]["address"],
                        "Storage bounds must cover every planned ECR repository exactly once.",
                    ))
                else:
                    for repository in ecr_repositories:
                        address = repository["address"]
                        values = repository["values"]
                        encryption = values.get("encryption_configuration")
                        if (
                            not isinstance(encryption, list)
                            or len(encryption) != 1
                            or not isinstance(encryption[0], dict)
                            or encryption[0].get("encryption_type") != "AES256"
                            or encryption[0].get("kms_key") not in (None, "")
                        ):
                            findings.append(PlanPricingFinding(
                                "ecr_storage_shape_unsupported", address,
                                "ECR pricing currently supports the standard private repository with AES256 encryption; customer KMS and unknown encryption settings are unsupported.",
                            ))
                            continue
                        usage = ecr_usage.repositories[address].monthly_stored_gb
                        try:
                            if pricing_catalog is None:
                                pricing_catalog = AwsPriceListCatalog()
                            rate = pricing_catalog.ecr_standard_storage_rate(region)
                        except PriceListUnavailableError:
                            unavailable = True
                            findings.append(PlanPricingFinding(
                                "regional_price_lookup_unavailable", address,
                                "DavDeploy could not verify current regional Amazon ECR storage prices.",
                            ))
                        except PlanPricingError:
                            findings.append(PlanPricingFinding(
                                "regional_price_ambiguous", address,
                                "DavDeploy could not identify the exact regional Amazon ECR standard-storage price.",
                            ))
                        else:
                            low_rate = Decimal(rate.low_unit_price_usd or rate.unit_price_usd)
                            lines.append(PlanCostLine(
                                address=address,
                                resource_type="aws_ecr_repository",
                                description="Amazon ECR standard image storage",
                                quantity=usage.minimum,
                                quantity_max=usage.maximum,
                                unit="GB-Mo",
                                unit_price_usd=rate.unit_price_usd,
                                monthly_cost_minor=int((
                                    low_rate * usage.minimum * 100
                                ).quantize(Decimal(1), rounding=ROUND_FLOOR)),
                                monthly_cost_max_minor=int((
                                    Decimal(rate.unit_price_usd) * usage.maximum * 100
                                ).quantize(Decimal(1), rounding=ROUND_CEILING)),
                                catalog_sku=rate.sku,
                                catalog_product_sha256=rate.product_digest,
                                catalog_published_at=rate.published_at,
                                catalog_effective_at=rate.effective_at,
                                unit_price_low_usd=format(low_rate, "f"),
                                low_cost_quantity=usage.minimum,
                            ))
                            priced_ecr_addresses.add(address)
    elif ecr_usage_document is not None:
        findings.append(PlanPricingFinding(
            "ecr_storage_assumptions_stale", None,
            "ECR storage usage assumptions do not match any ECR repository in this plan.",
        ))

    ecs_express_usage_document = trusted_context.ecs_express_usage_assumptions
    if ecs_express_services:
        if not ecs_express_shape_valid:
            findings.append(PlanPricingFinding(
                "ecs_express_pricing_shape_unsupported",
                ecs_express_services[0]["address"],
                "Only the exact single-service, same-region public-VPC pilot inventory is priced.",
            ))
        elif ecs_express_usage_document is None:
            findings.append(PlanPricingFinding(
                "ecs_express_usage_assumptions_missing",
                ecs_express_services[0]["address"],
                "Trusted workload, load-balancer, public IPv4, log, and transfer bounds are required.",
            ))
        else:
            try:
                ecs_usage = EcsExpressPricingUsageAssumptions.model_validate(
                    ecs_express_usage_document
                )
            except (TypeError, ValueError):
                findings.append(PlanPricingFinding(
                    "ecs_express_usage_assumptions_invalid",
                    ecs_express_services[0]["address"],
                    "Persisted ECS Express usage assumptions are invalid.",
                ))
            else:
                service = ecs_express_services[0]
                address = service["address"]
                usage = ecs_usage
                try:
                    if pricing_catalog is None:
                        pricing_catalog = AwsPriceListCatalog()
                    rates = [
                        (
                            "AWS Fargate Linux/x86 vCPU",
                            usage.monthly_task_starts.minimum * max(60, usage.average_billed_task_runtime_seconds.minimum) * 256,
                            usage.monthly_task_starts.maximum * max(60, usage.average_billed_task_runtime_seconds.maximum) * 256,
                            "milli-vCPU-seconds",
                            pricing_catalog.fargate_linux_x86_rate(region, dimension="vcpu"),
                            3_600_000,
                        ),
                        (
                            "AWS Fargate Linux/x86 memory",
                            usage.monthly_task_starts.minimum * max(60, usage.average_billed_task_runtime_seconds.minimum) * 512,
                            usage.monthly_task_starts.maximum * max(60, usage.average_billed_task_runtime_seconds.maximum) * 512,
                            "MiB-seconds",
                            pricing_catalog.fargate_linux_x86_rate(region, dimension="memory"),
                            3_686_400,
                        ),
                        (
                            "AWS ECS Express Application Load Balancer hours",
                            usage.monthly_alb_billed_hours.minimum,
                            usage.monthly_alb_billed_hours.maximum,
                            "Hrs",
                            pricing_catalog.application_load_balancer_hourly_rate(region),
                            1,
                        ),
                        (
                            "AWS ECS Express Application Load Balancer capacity",
                            usage.monthly_alb_lcu_hours.minimum,
                            usage.monthly_alb_lcu_hours.maximum,
                            "LCU-Hrs",
                            pricing_catalog.application_load_balancer_lcu_rate(region),
                            1,
                        ),
                        (
                            "AWS ECS Express task public IPv4 addresses",
                            usage.monthly_task_starts.minimum * max(60, usage.average_task_public_ipv4_address_seconds.minimum),
                            usage.monthly_task_starts.maximum * max(60, usage.average_task_public_ipv4_address_seconds.maximum),
                            "IPv4-address-seconds",
                            pricing_catalog.public_ipv4_in_use_rate(region),
                            3_600,
                        ),
                        (
                            "AWS ECS Express load-balancer public IPv4 addresses",
                            usage.monthly_alb_public_ipv4_address_seconds.minimum,
                            usage.monthly_alb_public_ipv4_address_seconds.maximum,
                            "IPv4-address-seconds",
                            pricing_catalog.public_ipv4_in_use_rate(region),
                            3_600,
                        ),
                        (
                            "AWS ECS Express CloudWatch Logs ingestion",
                            usage.cloudwatch_logs.monthly_ingested_gb.minimum,
                            usage.cloudwatch_logs.monthly_ingested_gb.maximum,
                            "GB",
                            pricing_catalog.cloudwatch_log_ingestion_rate(region),
                            1,
                        ),
                        (
                            "AWS ECS Express CloudWatch Logs storage",
                            usage.cloudwatch_logs.monthly_retained_gb_month.minimum,
                            usage.cloudwatch_logs.monthly_retained_gb_month.maximum,
                            "GB-Mo",
                            pricing_catalog.cloudwatch_standard_log_storage_rate(region),
                            1,
                        ),
                        (
                            "AWS ECS Express standard deployment alarm",
                            1,
                            1,
                            "Alarms",
                            pricing_catalog.cloudwatch_standard_alarm_metric_rate(region),
                            1,
                        ),
                    ]
                    if usage.monthly_internet_egress_gb.maximum:
                        rates.append((
                            "AWS ECS Express internet data transfer out",
                            usage.monthly_internet_egress_gb.minimum,
                            usage.monthly_internet_egress_gb.maximum,
                            "GB",
                            pricing_catalog.aws_internet_egress_rate(region),
                            1,
                        ))
                    if usage.monthly_cross_az_transfer_gb.maximum:
                        rates.append((
                            "AWS ECS Express cross-AZ data transfer in and out",
                            usage.monthly_cross_az_transfer_gb.minimum * 2,
                            usage.monthly_cross_az_transfer_gb.maximum * 2,
                            "GB",
                            pricing_catalog.regional_data_transfer_rate(region),
                            1,
                        ))
                except PriceListUnavailableError:
                    unavailable = True
                    findings.append(PlanPricingFinding(
                        "regional_price_lookup_unavailable", address,
                        "DavDeploy could not verify one or more regional ECS Express prices.",
                    ))
                except PlanPricingError:
                    findings.append(PlanPricingFinding(
                        "regional_price_ambiguous", address,
                        "DavDeploy could not identify exact regional ECS Express prices.",
                    ))
                else:
                    for description, low_quantity, high_quantity, unit, rate, divisor in rates:
                        unit_rate = Decimal(rate.unit_price_usd) / divisor
                        low_rate = Decimal(rate.low_unit_price_usd or rate.unit_price_usd) / divisor
                        lines.append(PlanCostLine(
                            address=address,
                            resource_type="aws_ecs_express_gateway_service",
                            description=description,
                            quantity=low_quantity,
                            quantity_max=high_quantity,
                            unit=unit,
                            unit_price_usd=format(unit_rate, "f"),
                            monthly_cost_minor=int((low_rate * low_quantity * 100).quantize(Decimal(1), rounding=ROUND_FLOOR)),
                            monthly_cost_max_minor=int((unit_rate * high_quantity * 100).quantize(Decimal(1), rounding=ROUND_CEILING)),
                            catalog_sku=rate.sku,
                            catalog_product_sha256=rate.product_digest,
                            catalog_published_at=rate.published_at,
                            catalog_effective_at=rate.effective_at,
                            unit_price_low_usd=format(low_rate, "f"),
                            unit_price_low_source_url=rate.low_rate_source_url,
                            low_cost_quantity=low_quantity,
                        ))
    elif ecs_express_usage_document is not None:
        findings.append(PlanPricingFinding(
            "ecs_express_usage_assumptions_stale", None,
            "ECS Express usage assumptions do not match any ECS Express service in this plan.",
        ))

    batch_jobs = [
        item for item in resources if item["type"] == "aws_batch_job_definition"
    ]
    batch_resources = [
        item for item in resources
        if item["type"] in {
            "aws_batch_compute_environment",
            "aws_batch_job_queue",
            "aws_batch_job_definition",
        }
    ]
    if (
        lambda_log_groups and not lambda_functions and not http_apis and not batch_resources
        and not ecs_express_shape_valid
    ):
        findings.append(
            PlanPricingFinding(
                "cloudwatch_log_group_unpriced",
                lambda_log_groups[0]["address"],
                "CloudWatch log groups are priced only when bound to a supported workload.",
            )
        )
    batch_usage_document = trusted_context.batch_usage_assumptions
    if batch_resources:
        findings.append(PlanPricingFinding(
            "batch_supporting_costs_unpriced", None,
            "Batch pricing includes bounded Fargate compute, supported CloudWatch Logs usage, eligible same-plan ECR storage, and explicitly modeled public IPv4 assignment; uncovered image transfer, network path charges, unsupported public IPv4 usage, and other material linked usage still block approval.",
        ))
        for job in batch_jobs:
            try:
                properties = json.loads(job["values"].get("container_properties"))
            except (json.JSONDecodeError, TypeError, RecursionError):
                properties = None
            image_value = properties.get("image") if isinstance(properties, dict) else None
            image_reference, image_error = _private_ecr_image_reference(image_value)
            if image_error is not None:
                findings.append(PlanPricingFinding(
                    "batch_image_ecr_reference_invalid", job["address"],
                    "A private ECR image reference must use an exact regional registry, repository name, and sha256 digest.",
                ))
            elif image_reference is None:
                findings.append(PlanPricingFinding(
                    "batch_image_source_unpriced", job["address"],
                    "Batch image pricing requires a digest-pinned same-region private ECR image linked to one priced same-plan repository.",
                ))
            elif image_reference is not None:
                image_account, image_region, image_repository = image_reference
                if image_region != region:
                    findings.append(PlanPricingFinding(
                        "batch_image_region_mismatch", job["address"],
                        "Private ECR images are linked for pricing only when their registry region matches the plan region.",
                    ))
                else:
                    matching_repositories = [
                        item for item in ecr_repositories
                        if item["values"].get("registry_id") == image_account
                        and item["values"].get("name") == image_repository
                    ]
                    if len(matching_repositories) != 1:
                        findings.append(PlanPricingFinding(
                            "batch_image_repository_unbound", job["address"],
                            "The private ECR image must match exactly one same-plan repository by registry account and repository name.",
                        ))
                    elif matching_repositories[0]["address"] not in priced_ecr_addresses:
                        findings.append(PlanPricingFinding(
                            "batch_image_storage_unpriced", matching_repositories[0]["address"],
                            "The same-plan ECR repository storage assumptions or regional price are missing or unsupported.",
                        ))
        batch_compute = [
            item for item in batch_resources
            if item["type"] == "aws_batch_compute_environment"
        ]
        batch_queues = [
            item for item in batch_resources
            if item["type"] == "aws_batch_job_queue"
        ]
        if len(batch_compute) != 1 or len(batch_queues) != 1 or len(batch_jobs) != 1:
            findings.append(PlanPricingFinding(
                "batch_pricing_shape_unsupported", None,
                "Pricing supports exactly one managed Fargate environment, queue, and job definition.",
            ))
        if batch_usage_document is None:
            findings.append(PlanPricingFinding(
                "batch_usage_assumptions_missing",
                batch_jobs[0]["address"] if batch_jobs else None,
                "Monthly job-count and billed-runtime assumptions are required for Batch pricing.",
            ))
        else:
            try:
                batch_usage = BatchPricingUsageAssumptions.model_validate(
                    batch_usage_document
                )
            except (TypeError, ValueError):
                findings.append(PlanPricingFinding(
                    "batch_usage_assumptions_invalid",
                    batch_jobs[0]["address"] if batch_jobs else None,
                    "Persisted Batch usage assumptions are invalid.",
                ))
            else:
                if set(batch_usage.jobs) != {item["address"] for item in batch_jobs}:
                    findings.append(PlanPricingFinding(
                        "batch_usage_resource_mismatch",
                        batch_jobs[0]["address"] if batch_jobs else None,
                        "Usage bounds must cover every planned Batch job definition exactly once.",
                    ))
                elif (
                    len(batch_compute) == 1
                    and len(batch_queues) == 1
                    and len(batch_jobs) == 1
                ):
                    compute_values = batch_compute[0]["values"]
                    queue_values = batch_queues[0]["values"]
                    job = batch_jobs[0]
                    job_values = job["values"]
                    compute_resources = compute_values.get("compute_resources")
                    try:
                        properties = json.loads(job_values.get("container_properties"))
                    except (json.JSONDecodeError, TypeError, RecursionError):
                        properties = None
                    requirements = (
                        properties.get("resourceRequirements")
                        if isinstance(properties, dict)
                        else None
                    )
                    requirements_by_type = {}
                    if isinstance(requirements, list):
                        for requirement in requirements:
                            if (
                                isinstance(requirement, dict)
                                and isinstance(requirement.get("type"), str)
                            ):
                                requirements_by_type[requirement["type"]] = requirement.get("value")
                    cpu_raw = requirements_by_type.get("VCPU")
                    memory_raw = requirements_by_type.get("MEMORY")
                    try:
                        cpu_decimal = Decimal(cpu_raw)
                        cpu_millicores = int(cpu_decimal * 1000)
                        memory_mib = int(memory_raw)
                    except (InvalidOperation, TypeError, ValueError):
                        cpu_decimal = None
                        cpu_millicores = memory_mib = 0
                    runtime_platform = properties.get("runtimePlatform") if isinstance(properties, dict) else None
                    runtime_supported = runtime_platform in (
                        None,
                        {"operatingSystemFamily": "LINUX", "cpuArchitecture": "X86_64"},
                    )
                    supported_pairs = {
                        "0.25": {512, 1024, 2048},
                        "0.5": set(range(1024, 4097, 1024)),
                        "1": set(range(2048, 8193, 1024)),
                        "2": set(range(4096, 16385, 1024)),
                    }
                    cpu_text = format(cpu_decimal, "f") if cpu_decimal is not None else ""
                    compute_type_valid = (
                        compute_values.get("type") == "MANAGED"
                        and compute_values.get("state") == "ENABLED"
                        and len(compute_resources) == 1
                        and isinstance(compute_resources[0], dict)
                        and compute_resources[0].get("type") == "FARGATE"
                        and isinstance(compute_resources[0].get("max_vcpus"), int)
                        and not isinstance(compute_resources[0].get("max_vcpus"), bool)
                        and 1 <= compute_resources[0].get("max_vcpus", 0) <= 6
                    ) if isinstance(compute_resources, list) else False
                    queue_valid = (
                        queue_values.get("state") == "ENABLED"
                        and isinstance(queue_values.get("compute_environment_order"), list)
                        and len(queue_values["compute_environment_order"]) == 1
                        and isinstance(queue_values["compute_environment_order"][0], dict)
                        and queue_values["compute_environment_order"][0].get("order") == 1
                    )
                    job_valid = (
                        job_values.get("type") == "container"
                        and job_values.get("platform_capabilities") == ["FARGATE"]
                        and isinstance(properties, dict)
                        and isinstance(requirements, list)
                        and len(requirements) == 2
                        and set(requirements_by_type) == {"VCPU", "MEMORY"}
                        and cpu_text in supported_pairs
                        and memory_mib in supported_pairs.get(cpu_text, set())
                        and runtime_supported
                        and "ephemeralStorage" not in properties
                    )
                    if not (compute_type_valid and queue_valid and job_valid):
                        findings.append(PlanPricingFinding(
                            "batch_pricing_shape_unsupported", job["address"],
                            "Only the known Linux/x86 Fargate job shape with default ephemeral storage is priced.",
                        ))
                    else:
                        try:
                            if pricing_catalog is None:
                                pricing_catalog = AwsPriceListCatalog()
                            cpu_rate = pricing_catalog.fargate_linux_x86_rate(
                                region, dimension="vcpu"
                            )
                            memory_rate = pricing_catalog.fargate_linux_x86_rate(
                                region, dimension="memory"
                            )
                        except PriceListUnavailableError:
                            unavailable = True
                            findings.append(PlanPricingFinding(
                                "regional_price_lookup_unavailable", job["address"],
                                "DavDeploy could not verify current regional Fargate prices.",
                            ))
                        except PlanPricingError:
                            findings.append(PlanPricingFinding(
                                "regional_price_ambiguous", job["address"],
                                "DavDeploy could not identify exact regional Linux/x86 Fargate prices.",
                            ))
                        else:
                            usage = batch_usage.jobs[job["address"]]
                            lower_seconds = max(60, usage.average_billed_runtime_seconds.minimum)
                            upper_seconds = max(60, usage.average_billed_runtime_seconds.maximum)
                            quantities = (
                                (
                                    "AWS Fargate Linux/x86 vCPU",
                                    cpu_rate,
                                    cpu_millicores,
                                    3_600_000,
                                    "milli-vCPU-seconds",
                                ),
                                (
                                    "AWS Fargate Linux/x86 memory",
                                    memory_rate,
                                    memory_mib,
                                    3_686_400,
                                    "MiB-seconds",
                                ),
                            )
                            for description, rate, units_per_task, divisor, unit in quantities:
                                low_quantity = (
                                    usage.monthly_jobs.minimum * lower_seconds * units_per_task
                                )
                                high_quantity = (
                                    usage.monthly_jobs.maximum * upper_seconds * units_per_task
                                )
                                unit_price = Decimal(rate.unit_price_usd) / divisor
                                low_unit_price = Decimal(rate.low_unit_price_usd or rate.unit_price_usd) / divisor
                                lines.append(PlanCostLine(
                                    address=job["address"],
                                    resource_type="aws_batch_job_definition",
                                    description=description,
                                    quantity=low_quantity,
                                    quantity_max=high_quantity,
                                    unit=unit,
                                    unit_price_usd=format(unit_price, "f"),
                                    monthly_cost_minor=int(
                                        (low_unit_price * low_quantity * 100).quantize(
                                            Decimal(1), rounding=ROUND_FLOOR
                                        )
                                    ),
                                    monthly_cost_max_minor=int(
                                        (unit_price * high_quantity * 100).quantize(
                                            Decimal(1), rounding=ROUND_CEILING
                                        )
                                    ),
                                    catalog_sku=rate.sku,
                                    catalog_product_sha256=rate.product_digest,
                                    catalog_published_at=rate.published_at,
                                    catalog_effective_at=rate.effective_at,
                                    unit_price_low_usd=format(low_unit_price, "f"),
                                    low_cost_quantity=low_quantity,
                                ))
                            network_configuration = properties.get("networkConfiguration")
                            public_ip_enabled = False
                            if "networkConfiguration" in properties:
                                if (
                                    not isinstance(network_configuration, dict)
                                    or set(network_configuration) != {"assignPublicIp"}
                                    or network_configuration.get("assignPublicIp")
                                    not in {"ENABLED", "DISABLED"}
                                ):
                                    findings.append(PlanPricingFinding(
                                        "batch_public_ip_setting_unsupported",
                                        job["address"],
                                        "Batch public IPv4 pricing requires a known ENABLED or DISABLED assignment setting.",
                                    ))
                                else:
                                    public_ip_enabled = (
                                        network_configuration["assignPublicIp"] == "ENABLED"
                                    )
                            if public_ip_enabled:
                                address_usage = (
                                    usage.average_public_ipv4_address_seconds_per_attempt
                                )
                                if address_usage is None:
                                    findings.append(PlanPricingFinding(
                                        "batch_public_ip_usage_assumptions_missing",
                                        job["address"],
                                        "Trusted per-attempt public IPv4 address-duration bounds are required.",
                                    ))
                                max_attempts = usage.maximum_attempts_per_job
                                if max_attempts is None:
                                    findings.append(PlanPricingFinding(
                                        "batch_public_ip_attempt_bound_missing",
                                        job["address"],
                                        "Trusted maximum attempts per submitted job are required for public IPv4 pricing.",
                                    ))
                                if max_attempts is not None and address_usage is not None:
                                    try:
                                        public_ipv4_rate = (
                                            pricing_catalog.public_ipv4_in_use_rate(region)
                                        )
                                    except PriceListUnavailableError:
                                        unavailable = True
                                        findings.append(PlanPricingFinding(
                                            "regional_price_lookup_unavailable",
                                            job["address"],
                                            "DavDeploy could not verify the regional in-use public IPv4 price.",
                                        ))
                                    except PlanPricingError:
                                        findings.append(PlanPricingFinding(
                                            "regional_price_ambiguous",
                                            job["address"],
                                            "DavDeploy could not identify the exact regional in-use public IPv4 price.",
                                        ))
                                    else:
                                        lower_address_seconds = (
                                            usage.monthly_jobs.minimum
                                            * max(60, address_usage.minimum)
                                        )
                                        upper_address_seconds = (
                                            usage.monthly_jobs.maximum
                                            * max_attempts
                                            * max(60, address_usage.maximum)
                                        )
                                        seconds_per_hour = 3600
                                        low_hourly_rate = Decimal(
                                            public_ipv4_rate.low_unit_price_usd
                                            or public_ipv4_rate.unit_price_usd
                                        )
                                        hourly_rate = Decimal(
                                            public_ipv4_rate.unit_price_usd
                                        )
                                        lines.append(PlanCostLine(
                                            address=job["address"],
                                            resource_type="aws_batch_job_definition",
                                            description="AWS Batch Fargate in-use public IPv4 addresses",
                                            quantity=lower_address_seconds,
                                            quantity_max=upper_address_seconds,
                                            unit="IPv4-address-seconds",
                                            unit_price_usd=format(
                                                hourly_rate / seconds_per_hour, "f"
                                            ),
                                            monthly_cost_minor=int((
                                                low_hourly_rate
                                                * lower_address_seconds
                                                / seconds_per_hour
                                                * 100
                                            ).quantize(Decimal(1), rounding=ROUND_FLOOR)),
                                            monthly_cost_max_minor=int((
                                                hourly_rate
                                                * upper_address_seconds
                                                / seconds_per_hour
                                                * 100
                                            ).quantize(Decimal(1), rounding=ROUND_CEILING)),
                                            catalog_sku=public_ipv4_rate.sku,
                                            catalog_product_sha256=(
                                                public_ipv4_rate.product_digest
                                            ),
                                            catalog_published_at=(
                                                public_ipv4_rate.published_at
                                            ),
                                            catalog_effective_at=(
                                                public_ipv4_rate.effective_at
                                            ),
                                            unit_price_low_usd=format(
                                                low_hourly_rate / seconds_per_hour, "f"
                                            ),
                                            low_cost_quantity=lower_address_seconds,
                                        ))
                            log_group_name, log_config_error = _batch_awslogs_group_name(
                                properties, region
                            )
                            if log_config_error:
                                findings.append(PlanPricingFinding(
                                    "batch_log_configuration_unsupported",
                                    job["address"],
                                    "Batch log pricing requires an explicit same-region awslogs group with supported options.",
                                ))
                            else:
                                usage_logs = usage.cloudwatch_logs
                                if usage_logs is None:
                                    findings.append(PlanPricingFinding(
                                        "batch_log_usage_assumptions_missing",
                                        job["address"],
                                        "Bounded CloudWatch Logs ingestion and retained-storage assumptions are required.",
                                    ))
                                elif usage.monthly_jobs.maximum > 0 and (
                                    usage_logs.monthly_ingested_gb.maximum == 0
                                    or usage_logs.monthly_retained_gb_month.maximum == 0
                                ):
                                    findings.append(PlanPricingFinding(
                                        "batch_log_usage_assumptions_unbounded",
                                        job["address"],
                                        "Batch jobs require nonzero upper bounds for log ingestion and retained log storage.",
                                    ))
                                else:
                                    named_log_groups = [
                                        group for group in lambda_log_groups
                                        if group["values"].get("name") == log_group_name
                                    ]
                                    if len(named_log_groups) != 1:
                                        findings.append(PlanPricingFinding(
                                            "batch_log_group_mismatch",
                                            job["address"],
                                            "The Batch awslogs destination must match exactly one planned CloudWatch log group.",
                                        ))
                                    else:
                                        log_group = named_log_groups[0]
                                        group_error = _validate_batch_log_group(
                                            log_group["values"],
                                            changes.get(log_group["address"]),
                                            log_group_name,
                                        )
                                        if group_error:
                                            findings.append(PlanPricingFinding(
                                                group_error[0], log_group["address"], group_error[1]
                                            ))
                                        else:
                                            try:
                                                if pricing_catalog is None:
                                                    pricing_catalog = AwsPriceListCatalog()
                                                log_rates = (
                                                    (
                                                        pricing_catalog.cloudwatch_log_ingestion_rate(region),
                                                        "AWS Batch CloudWatch Logs ingestion",
                                                        usage_logs.monthly_ingested_gb,
                                                        "GB",
                                                    ),
                                                    (
                                                        pricing_catalog.cloudwatch_standard_log_storage_rate(region),
                                                        "AWS Batch CloudWatch Logs storage",
                                                        usage_logs.monthly_retained_gb_month,
                                                        "GB-Mo",
                                                    ),
                                                )
                                            except PriceListUnavailableError:
                                                unavailable = True
                                                findings.append(PlanPricingFinding(
                                                    "regional_price_lookup_unavailable",
                                                    log_group["address"],
                                                    "DavDeploy could not verify current regional CloudWatch Logs prices.",
                                                ))
                                            except PlanPricingError:
                                                findings.append(PlanPricingFinding(
                                                    "regional_price_ambiguous",
                                                    log_group["address"],
                                                    "DavDeploy could not identify exact regional CloudWatch Logs prices.",
                                                ))
                                            else:
                                                for rate, description, amount, unit in log_rates:
                                                    low_rate = Decimal(
                                                        rate.low_unit_price_usd or rate.unit_price_usd
                                                    )
                                                    lines.append(PlanCostLine(
                                                        address=job["address"],
                                                        resource_type="aws_batch_job_definition",
                                                        description=description,
                                                        quantity=amount.minimum,
                                                        quantity_max=amount.maximum,
                                                        unit=unit,
                                                        unit_price_usd=rate.unit_price_usd,
                                                        monthly_cost_minor=int((
                                                            low_rate * amount.minimum * 100
                                                        ).quantize(Decimal(1), rounding=ROUND_FLOOR)),
                                                        monthly_cost_max_minor=int((
                                                            Decimal(rate.unit_price_usd)
                                                            * amount.maximum * 100
                                                        ).quantize(Decimal(1), rounding=ROUND_CEILING)),
                                                        catalog_sku=rate.sku,
                                                        catalog_product_sha256=rate.product_digest,
                                                        catalog_published_at=rate.published_at,
                                                        catalog_effective_at=rate.effective_at,
                                                        unit_price_low_usd=format(low_rate, "f"),
                                                        low_cost_quantity=amount.minimum,
                                                    ))

    elif batch_usage_document is not None:
        findings.append(PlanPricingFinding(
            "batch_usage_assumptions_stale", None,
            "Batch usage assumptions do not match any Batch resources in this plan.",
        ))

    if s3_buckets:
        if trusted_context.usage_assumptions is None:
            findings.append(
                PlanPricingFinding(
                    "s3_usage_assumptions_missing",
                    s3_buckets[0]["address"],
                    "S3 Standard storage, request, and internet transfer usage assumptions are required.",
                )
            )
        else:
            bucket = s3_buckets[0]
            bucket_error = None
            for item in s3_buckets:
                error = _validate_s3_bucket(item["values"], changes.get(item["address"]))
                if error:
                    bucket_error = (item, error)
                    break
            if bucket_error:
                invalid_bucket, error = bucket_error
                findings.append(
                    PlanPricingFinding(error[0], invalid_bucket["address"], error[1])
                )
            else:
                try:
                    if pricing_catalog is None:
                        pricing_catalog = AwsPriceListCatalog()
                    usage = S3PricingUsageAssumptions.model_validate(
                        trusted_context.usage_assumptions
                    )
                    s3_rates = (
                        ("Amazon S3 Standard storage", "monthly_storage_gb", "GB-Mo",
                         pricing_catalog.s3_standard_storage_rate(region)),
                        ("Amazon S3 Standard PUT/COPY/POST/LIST requests",
                         "monthly_put_copy_post_list_requests", "Requests",
                         pricing_catalog.s3_standard_request_rate(region, tier=1)),
                        ("Amazon S3 Standard GET requests", "monthly_get_requests", "Requests",
                         pricing_catalog.s3_standard_request_rate(region, tier=2)),
                        ("AWS internet data transfer out", "monthly_internet_egress_gb", "GB",
                         pricing_catalog.aws_internet_egress_rate(region)),
                    )
                    if usage.monthly_internet_egress_gb.maximum > 500_000:
                        findings.append(
                            PlanPricingFinding(
                                "s3_egress_price_limit_exceeded",
                                bucket["address"],
                                "S3 internet egress above 500 TB per month needs a separate AWS quote.",
                            )
                        )
                    else:
                        for description, assumption_name, unit, rate in s3_rates:
                            amount = getattr(usage, assumption_name)
                            unit_price = Decimal(rate.unit_price_usd)
                            low_unit_price = Decimal(
                                rate.low_unit_price_usd or rate.unit_price_usd
                            )
                            low_quantity = amount.minimum
                            low_minor = int(
                                (low_unit_price * low_quantity * 100).quantize(
                                    Decimal(1), rounding=ROUND_FLOOR
                                )
                            )
                            high_minor = int(
                                (unit_price * amount.maximum * 100).quantize(
                                    Decimal(1), rounding=ROUND_CEILING
                                )
                            )
                            lines.append(
                                PlanCostLine(
                                    address="usage_assumptions.s3",
                                    resource_type="aws_s3_bucket",
                                    description=description,
                                    quantity=amount.minimum,
                                    quantity_max=amount.maximum,
                                    unit=unit,
                                    unit_price_usd=rate.unit_price_usd,
                                    monthly_cost_minor=low_minor,
                                    monthly_cost_max_minor=high_minor,
                                    unit_price_low_usd=format(low_unit_price, "f"),
                                    unit_price_low_source_url=rate.low_rate_source_url,
                                    low_cost_quantity=low_quantity,
                                    catalog_sku=rate.sku,
                                    catalog_product_sha256=rate.product_digest,
                                    catalog_published_at=rate.published_at,
                                    catalog_effective_at=rate.effective_at,
                                )
                            )
                except PriceListUnavailableError:
                    unavailable = True
                    findings.append(
                        PlanPricingFinding(
                            "regional_price_lookup_unavailable",
                            bucket["address"],
                            "DavDeploy could not verify current regional S3 or transfer prices.",
                        )
                    )
                except PlanPricingError:
                    findings.append(
                        PlanPricingFinding(
                            "regional_price_ambiguous",
                            bucket["address"],
                            "DavDeploy could not identify one exact regional S3 or transfer price.",
                        )
                    )
                except (TypeError, ValueError):
                    findings.append(
                        PlanPricingFinding(
                            "s3_usage_assumptions_invalid",
                            bucket["address"],
                            "Persisted S3 usage assumptions are invalid for pricing.",
                        )
                    )

    if sqs_queues:
        assumptions = trusted_context.sqs_usage_assumptions
        if assumptions is None:
            findings.append(PlanPricingFinding(
                "sqs_usage_assumptions_missing", sqs_queues[0]["address"],
                "Monthly billed request-unit assumptions are required for SQS queues.",
            ))
        else:
            invalid_queue = next(
                ((queue, error) for queue in sqs_queues
                 if (error := _validate_sqs_queue(queue["values"], changes.get(queue["address"]))) is not None),
                None,
            )
            try:
                usage = SqsPricingUsageAssumptions.model_validate(assumptions)
            except (TypeError, ValueError):
                findings.append(PlanPricingFinding(
                    "sqs_usage_assumptions_invalid", sqs_queues[0]["address"],
                    "Persisted SQS request usage assumptions are invalid for pricing.",
                ))
            else:
                if usage.monthly_fair_queue_request_units.maximum > 0:
                    findings.append(PlanPricingFinding(
                        "sqs_fair_queue_unpriced", sqs_queues[0]["address"],
                        "Fair Queue requests have a separate surcharge that is not priced yet.",
                    ))
                if (
                    usage.monthly_cross_region_transfer_gb.maximum > 0
                    or usage.monthly_internet_egress_gb.maximum > 0
                ):
                    findings.append(PlanPricingFinding(
                        "sqs_data_transfer_unpriced", sqs_queues[0]["address"],
                        "Cross-region and internet SQS data transfer are not priced yet.",
                    ))
                if invalid_queue:
                    queue, error = invalid_queue
                    findings.append(PlanPricingFinding(error[0], queue["address"], error[1]))
                else:
                    queue_types = {bool(queue["values"].get("fifo_queue")) for queue in sqs_queues}
                    standard = usage.monthly_standard_request_units
                    fifo = usage.monthly_fifo_request_units
                    if (False not in queue_types and standard.maximum) or (True not in queue_types and fifo.maximum):
                        findings.append(PlanPricingFinding(
                            "sqs_usage_queue_type_mismatch", sqs_queues[0]["address"],
                            "Usage assumptions include requests for a queue type absent from the Terraform plan.",
                        ))
                    else:
                        try:
                            if pricing_catalog is None:
                                pricing_catalog = AwsPriceListCatalog()
                            rates = []
                            for is_fifo, amount, description in (
                                (True, fifo, "Amazon SQS FIFO requests"),
                                (False, standard, "Amazon SQS Standard requests"),
                            ):
                                if amount.maximum == 0:
                                    continue
                                rate = pricing_catalog.sqs_request_rate(region, fifo=is_fifo)
                                rates.append((is_fifo, amount, description, rate))
                            for is_fifo, amount, description, rate in rates:
                                low_quantity = amount.minimum
                                low_rate = Decimal(rate.low_unit_price_usd or rate.unit_price_usd)
                                high_rate = Decimal(rate.unit_price_usd)
                                low_minor = int((low_rate * low_quantity * 100).quantize(Decimal(1), rounding=ROUND_FLOOR))
                                high_minor = int((high_rate * amount.maximum * 100).quantize(Decimal(1), rounding=ROUND_CEILING))
                                lines.append(PlanCostLine(
                                    address="usage_assumptions.sqs.fifo" if is_fifo else "usage_assumptions.sqs.standard",
                                    resource_type="aws_sqs_queue", description=description,
                                    quantity=amount.minimum, quantity_max=amount.maximum, unit="Requests",
                                    unit_price_usd=rate.unit_price_usd, monthly_cost_minor=low_minor,
                                    monthly_cost_max_minor=high_minor, unit_price_low_usd=format(low_rate, "f"),
                                    low_cost_quantity=low_quantity, catalog_sku=rate.sku,
                                    catalog_product_sha256=rate.product_digest,
                                    catalog_published_at=rate.published_at,
                                    catalog_effective_at=rate.effective_at,
                                ))
                        except PriceListUnavailableError:
                            unavailable = True
                            findings.append(PlanPricingFinding(
                                "regional_price_lookup_unavailable", sqs_queues[0]["address"],
                                "DavDeploy could not verify current regional SQS request prices.",
                            ))
                        except PlanPricingError:
                            findings.append(PlanPricingFinding(
                                "regional_price_ambiguous", sqs_queues[0]["address"],
                                "DavDeploy could not identify one exact regional SQS request price.",
                            ))

    if aurora_clusters or aurora_instances:
        address = aurora_clusters[0]["address"] if aurora_clusters else aurora_instances[0]["address"]
        if rds_instances:
            findings.append(PlanPricingFinding(
                "rds_mixed_engine_shape_unpriced", address,
                "A plan cannot mix Aurora cluster and standalone RDS pricing shapes.",
            ))
        elif len(aurora_clusters) != 1 or len(aurora_instances) != 1:
            findings.append(PlanPricingFinding(
                "aurora_topology_unpriced", address,
                "Only one Aurora cluster with one Serverless v2 writer is priced.",
            ))
        elif trusted_context.rds_usage_assumptions is None:
            findings.append(PlanPricingFinding(
                "aurora_usage_assumptions_missing", address,
                "Explicit monthly Aurora storage, I/O, and billable backup-overage ranges are required.",
            ))
        else:
            try:
                usage = RdsPricingUsageAssumptions.model_validate(
                    trusted_context.rds_usage_assumptions
                )
                if (
                    usage.monthly_backup_storage_gb_month is not None
                    or usage.aurora_monthly_storage_gb_month is None
                    or usage.aurora_monthly_io_requests is None
                    or usage.aurora_monthly_backup_overage_gb_month is None
                    or usage.aurora_monthly_secret_api_requests is None
                    or usage.aurora_monthly_inter_az_transfer_gb is None
                    or usage.aurora_monthly_cross_region_transfer_gb is None
                    or usage.aurora_monthly_internet_egress_gb is None
                ):
                    raise ValueError("Aurora usage assumptions do not match")
            except (TypeError, ValueError):
                findings.append(PlanPricingFinding(
                    "aurora_usage_assumptions_invalid", address,
                    "Persisted Aurora storage, I/O, and backup assumptions must all be explicit.",
                ))
            else:
                cluster, instance = aurora_clusters[0], aurora_instances[0]
                error = (
                    ("aurora_transfer_usage_unpriced", "Aurora inter-AZ, cross-region, and internet transfer must be explicitly bounded at zero for this pricing release.")
                    if usage.aurora_monthly_inter_az_transfer_gb.maximum > 0
                    or usage.aurora_monthly_cross_region_transfer_gb.maximum > 0
                    or usage.aurora_monthly_internet_egress_gb.maximum > 0
                    else _validate_aurora_cluster(
                        cluster["values"], changes.get(cluster["address"])
                    ) or _validate_aurora_instance(
                        instance["values"], changes.get(instance["address"])
                    )
                )
                if error:
                    findings.append(PlanPricingFinding(error[0], address, error[1]))
                else:
                    try:
                        if pricing_catalog is None:
                            pricing_catalog = AwsPriceListCatalog()
                        lines.extend(_aurora_cost_lines(
                            cluster_address=cluster["address"],
                            region=region,
                            cluster_values=cluster["values"],
                            usage=usage,
                            catalog=pricing_catalog,
                        ))
                    except PriceListUnavailableError:
                        unavailable = True
                        findings.append(PlanPricingFinding(
                            "regional_price_lookup_unavailable", address,
                            "DavDeploy could not verify current regional Aurora prices.",
                        ))
                    except (PlanPricingError, KeyError, IndexError, TypeError, ValueError):
                        findings.append(PlanPricingFinding(
                            "regional_price_ambiguous", address,
                            "DavDeploy could not identify exact regional Aurora prices.",
                        ))
    elif (
        trusted_context.rds_usage_assumptions is not None
        and _has_aurora_usage_assumptions(trusted_context.rds_usage_assumptions)
    ):
        findings.append(PlanPricingFinding(
            "aurora_usage_assumptions_stale", None,
            "Aurora usage assumptions do not match any cluster in this plan.",
        ))

    if rds_instances:
        usage_document = trusted_context.rds_usage_assumptions
        if usage_document is None:
            findings.append(
                PlanPricingFinding(
                    "rds_usage_assumptions_missing",
                    rds_instances[0]["address"],
                    "Monthly RDS backup storage usage assumptions are required.",
                )
            )
        else:
            try:
                usage = RdsPricingUsageAssumptions.model_validate(usage_document)
            except (TypeError, ValueError):
                findings.append(
                    PlanPricingFinding(
                        "rds_usage_assumptions_invalid",
                        rds_instances[0]["address"],
                        "Persisted RDS backup storage assumptions are invalid.",
                    )
                )
            else:
                invalid_instance = next(
                    (
                        (instance, error)
                        for instance in rds_instances
                        if (
                            error := _validate_rds_instance(
                                instance["values"], changes.get(instance["address"])
                            )
                        )
                        is not None
                    ),
                    None,
                )
                if invalid_instance:
                    instance, error = invalid_instance
                    findings.append(
                        PlanPricingFinding(error[0], instance["address"], error[1])
                    )
                elif usage.monthly_backup_storage_gb_month is None or any(
                    value is not None
                    for value in (
                        usage.aurora_monthly_storage_gb_month,
                        usage.aurora_monthly_io_requests,
                        usage.aurora_monthly_backup_overage_gb_month,
                        usage.aurora_monthly_secret_api_requests,
                        usage.aurora_monthly_inter_az_transfer_gb,
                        usage.aurora_monthly_cross_region_transfer_gb,
                        usage.aurora_monthly_internet_egress_gb,
                    )
                ):
                    findings.append(PlanPricingFinding(
                        "rds_usage_assumptions_invalid",
                        rds_instances[0]["address"],
                        "Standalone RDS pricing requires backup storage assumptions only.",
                    ))
                elif any(
                    instance["values"].get("backup_retention_period", 0) > 0
                    for instance in rds_instances
                ) and usage.monthly_backup_storage_gb_month.maximum == 0:
                    findings.append(
                        PlanPricingFinding(
                            "rds_backup_usage_assumption_mismatch",
                            rds_instances[0]["address"],
                            "Enabled RDS backups require a nonzero backup storage usage ceiling.",
                        )
                    )
                else:
                    try:
                        if pricing_catalog is None:
                            pricing_catalog = AwsPriceListCatalog()
                        for instance in rds_instances:
                            values = instance["values"]
                            address = instance["address"]
                            instance_rate = pricing_catalog.rds_mysql_instance_rate(
                                region, values["instance_class"]
                            )
                            storage_rate = pricing_catalog.rds_mysql_gp3_storage_rate(region)
                            for description, quantity, unit, rate in (
                                (
                                    "Amazon RDS for MySQL Single-AZ instance hours",
                                    730,
                                    "Hrs",
                                    instance_rate,
                                ),
                                (
                                    "Amazon RDS for MySQL GP3 storage",
                                    values["allocated_storage"],
                                    "GB-Mo",
                                    storage_rate,
                                ),
                            ):
                                monthly_minor = int(
                                    (
                                        Decimal(rate.unit_price_usd)
                                        * quantity
                                        * 100
                                    ).quantize(Decimal(1), rounding=ROUND_CEILING)
                                )
                                lines.append(
                                    PlanCostLine(
                                        address=address,
                                        resource_type="aws_db_instance",
                                        description=description,
                                        quantity=quantity,
                                        unit=unit,
                                        unit_price_usd=rate.unit_price_usd,
                                        monthly_cost_minor=monthly_minor,
                                        catalog_sku=rate.sku,
                                        catalog_product_sha256=rate.product_digest,
                                        catalog_published_at=rate.published_at,
                                        catalog_effective_at=rate.effective_at,
                                    )
                                )
                        backup_max = usage.monthly_backup_storage_gb_month.maximum
                        if backup_max:
                            backup_rate = pricing_catalog.rds_mysql_backup_storage_rate(region)
                            backup_high = int(
                                (
                                    Decimal(backup_rate.unit_price_usd)
                                    * backup_max
                                    * 100
                                ).quantize(Decimal(1), rounding=ROUND_CEILING)
                            )
                            lines.append(
                                PlanCostLine(
                                    address="usage_assumptions.rds",
                                    resource_type="aws_db_instance",
                                    description="RDS MySQL backup storage",
                                    quantity=usage.monthly_backup_storage_gb_month.minimum,
                                    quantity_max=backup_max,
                                    unit="GB-Mo",
                                    unit_price_usd=backup_rate.unit_price_usd,
                                    monthly_cost_minor=int((Decimal(backup_rate.unit_price_usd) * usage.monthly_backup_storage_gb_month.minimum * 100).quantize(Decimal(1), rounding=ROUND_FLOOR)),
                                    monthly_cost_max_minor=backup_high,
                                    unit_price_low_usd=backup_rate.unit_price_usd,
                                    low_cost_quantity=usage.monthly_backup_storage_gb_month.minimum,
                                    catalog_sku=backup_rate.sku,
                                    catalog_product_sha256=backup_rate.product_digest,
                                    catalog_published_at=backup_rate.published_at,
                                    catalog_effective_at=backup_rate.effective_at,
                                )
                            )
                    except PriceListUnavailableError:
                        unavailable = True
                        findings.append(
                            PlanPricingFinding(
                                "regional_price_lookup_unavailable",
                                rds_instances[0]["address"],
                                "DavDeploy could not verify current regional RDS prices.",
                            )
                        )
                    except PlanPricingError:
                        findings.append(
                            PlanPricingFinding(
                                "regional_price_ambiguous",
                                rds_instances[0]["address"],
                                "DavDeploy could not identify exact regional RDS prices.",
                            )
                        )

    serverless_document = trusted_context.serverless_usage_assumptions
    if lambda_functions or http_apis:
        if serverless_document is None:
            findings.append(
                PlanPricingFinding(
                    "serverless_usage_assumptions_missing",
                    (lambda_functions or http_apis)[0]["address"],
                    "Explicit request, duration, and transfer bounds are required for Lambda and HTTP APIs.",
                )
            )
        else:
            try:
                serverless_usage = ServerlessPricingUsageAssumptions.model_validate(
                    serverless_document
                )
            except (TypeError, ValueError):
                findings.append(
                    PlanPricingFinding(
                        "serverless_usage_assumptions_invalid",
                        (lambda_functions or http_apis)[0]["address"],
                        "Persisted Lambda and HTTP API usage assumptions are invalid.",
                    )
                )
            else:
                lambda_by_address = {item["address"]: item for item in lambda_functions}
                api_by_address = {item["address"]: item for item in http_apis}
                lambda_usage = serverless_usage.lambda_functions
                api_usage = serverless_usage.http_apis
                if set(lambda_usage) != set(lambda_by_address) or set(api_usage) != set(api_by_address):
                    findings.append(
                        PlanPricingFinding(
                            "serverless_usage_resource_mismatch",
                            (lambda_functions or http_apis)[0]["address"],
                            "Usage bounds must cover every planned Lambda and HTTP API exactly once.",
                        )
                    )
                else:
                    lambda_log_group_names = {
                        address: _lambda_log_group_name(resource["values"])
                        for address, resource in lambda_by_address.items()
                    }
                    expected_log_group_names = {
                        name for name in lambda_log_group_names.values() if name is not None
                    }
                    log_groups_by_name = {item["values"].get("name"): item for item in lambda_log_groups}
                    if (
                        None in lambda_log_group_names.values()
                        or len(expected_log_group_names) != len(lambda_log_group_names)
                        or set(log_groups_by_name) != expected_log_group_names
                        or len(log_groups_by_name) != len(lambda_log_groups)
                    ):
                        findings.append(
                            PlanPricingFinding(
                                "lambda_log_group_mismatch",
                                (lambda_functions or http_apis)[0]["address"],
                                "Each Lambda needs one explicitly retained Standard CloudWatch log group matching its logging configuration.",
                            )
                        )
                    else:
                        for address, group_name in lambda_log_group_names.items():
                            group = log_groups_by_name[group_name]
                            group_error = _validate_lambda_log_group(
                                group["values"], changes.get(group["address"]), group_name
                            )
                            if group_error:
                                findings.append(
                                    PlanPricingFinding(group_error[0], group["address"], group_error[1])
                                )
                    try:
                        if pricing_catalog is None:
                            pricing_catalog = AwsPriceListCatalog()
                        for address, resource in lambda_by_address.items():
                            values = resource["values"]
                            change = changes.get(address)
                            error = _validate_lambda_function(values, change)
                            if error:
                                findings.append(PlanPricingFinding(error[0], address, error[1]))
                                continue
                            group_name = lambda_log_group_names.get(address)
                            group = log_groups_by_name.get(group_name)
                            if group is None or _validate_lambda_log_group(
                                group["values"], changes.get(group["address"]), group_name
                            ):
                                continue
                            assumption = lambda_usage[address]
                            architecture = values["architectures"][0]
                            request_rate = pricing_catalog.lambda_request_rate(region, architecture)
                            duration_rate = pricing_catalog.lambda_duration_rate(region, architecture)
                            transfer_rate = pricing_catalog.aws_internet_egress_rate(region)
                            log_ingestion_rate = pricing_catalog.cloudwatch_log_ingestion_rate(region)
                            log_storage_rate = pricing_catalog.cloudwatch_standard_log_storage_rate(region)
                            requests = assumption.monthly_invocations
                            duration = assumption.average_billed_duration_ms
                            egress = assumption.monthly_internet_egress_gb
                            log_ingestion = assumption.monthly_cloudwatch_log_ingestion_gb
                            log_storage = assumption.monthly_log_storage_gb_month
                            memory_gb = Decimal(values["memory_size"]) / Decimal(1024)
                            for rate, description, quantity, unit, scale in (
                                (request_rate, "AWS Lambda invocations", requests, "Requests", Decimal(1)),
                                (
                                    duration_rate,
                                    "AWS Lambda billed duration at declared average and memory",
                                    requests,
                                    "Invocations × GB-seconds per invocation",
                                    memory_gb * Decimal(duration.minimum) / Decimal(1000),
                                ),
                            ):
                                low_cost = (
                                    Decimal(rate.unit_price_usd)
                                    * Decimal(quantity.minimum)
                                    * scale
                                    * 100
                                )
                                if description.startswith("AWS Lambda billed"):
                                    high_scale = memory_gb * Decimal(duration.maximum) / Decimal(1000)
                                else:
                                    high_scale = scale
                                high_cost = (
                                    Decimal(rate.unit_price_usd)
                                    * Decimal(quantity.maximum)
                                    * high_scale
                                    * 100
                                )
                                lines.append(
                                    PlanCostLine(
                                        address=address,
                                        resource_type="aws_lambda_function",
                                        description=description,
                                        quantity=quantity.minimum,
                                        quantity_max=quantity.maximum,
                                        unit=unit,
                                        unit_price_usd=rate.unit_price_usd,
                                        monthly_cost_minor=int(low_cost.quantize(Decimal(1), rounding=ROUND_FLOOR)),
                                        monthly_cost_max_minor=int(high_cost.quantize(Decimal(1), rounding=ROUND_CEILING)),
                                        catalog_sku=rate.sku,
                                        catalog_product_sha256=rate.product_digest,
                                        catalog_published_at=rate.published_at,
                                        catalog_effective_at=rate.effective_at,
                                    )
                                )
                            low_rate = Decimal(transfer_rate.low_unit_price_usd or transfer_rate.unit_price_usd)
                            lines.append(
                                PlanCostLine(
                                    address=address,
                                    resource_type="aws_lambda_function",
                                    description="AWS Lambda internet data transfer out",
                                    quantity=egress.minimum,
                                    quantity_max=egress.maximum,
                                    unit="GB",
                                    unit_price_usd=transfer_rate.unit_price_usd,
                                    monthly_cost_minor=int((low_rate * egress.minimum * 100).quantize(Decimal(1), rounding=ROUND_FLOOR)),
                                    monthly_cost_max_minor=int((Decimal(transfer_rate.unit_price_usd) * egress.maximum * 100).quantize(Decimal(1), rounding=ROUND_CEILING)),
                                    unit_price_low_usd=format(low_rate, "f"),
                                    unit_price_low_source_url=transfer_rate.low_rate_source_url,
                                    low_cost_quantity=egress.minimum,
                                    catalog_sku=transfer_rate.sku,
                                    catalog_product_sha256=transfer_rate.product_digest,
                                    catalog_published_at=transfer_rate.published_at,
                                    catalog_effective_at=transfer_rate.effective_at,
                                )
                            )
                            if requests.maximum > 0 and (
                                log_ingestion.maximum == 0 or log_storage.maximum == 0
                            ):
                                findings.append(
                                    PlanPricingFinding(
                                        "lambda_log_usage_assumptions_unbounded",
                                        address,
                                        "Invoked Lambda functions require nonzero upper bounds for log ingestion and stored log data.",
                                    )
                                )
                            for rate, description, amount, unit in (
                                (
                                    log_ingestion_rate,
                                    "Amazon CloudWatch Logs ingestion",
                                    log_ingestion,
                                    "GB",
                                ),
                                (
                                    log_storage_rate,
                                    "Amazon CloudWatch Logs storage",
                                    log_storage,
                                    "GB-Mo",
                                ),
                            ):
                                lines.append(
                                    PlanCostLine(
                                        address=address,
                                        resource_type="aws_lambda_function",
                                        description=description,
                                        quantity=amount.minimum,
                                        quantity_max=amount.maximum,
                                        unit=unit,
                                        unit_price_usd=rate.unit_price_usd,
                                        monthly_cost_minor=int((Decimal(rate.low_unit_price_usd or rate.unit_price_usd) * amount.minimum * 100).quantize(Decimal(1), rounding=ROUND_FLOOR)),
                                        monthly_cost_max_minor=int((Decimal(rate.unit_price_usd) * amount.maximum * 100).quantize(Decimal(1), rounding=ROUND_CEILING)),
                                        unit_price_low_usd=rate.low_unit_price_usd,
                                        low_cost_quantity=amount.minimum,
                                        catalog_sku=rate.sku,
                                        catalog_product_sha256=rate.product_digest,
                                        catalog_published_at=rate.published_at,
                                        catalog_effective_at=rate.effective_at,
                                    )
                                )
                        for address, resource in api_by_address.items():
                            error = _validate_http_api(resource["values"], changes.get(address))
                            if error:
                                findings.append(PlanPricingFinding(error[0], address, error[1]))
                                continue
                            assumption = api_usage[address]
                            request_rate = pricing_catalog.http_api_request_rate(region)
                            transfer_rate = pricing_catalog.aws_internet_egress_rate(region)
                            requests = assumption.monthly_requests
                            egress = assumption.monthly_internet_egress_gb
                            for rate, description, quantity, unit in (
                                (request_rate, "Amazon API Gateway HTTP API requests", requests, "Requests"),
                                (transfer_rate, "AWS internet data transfer out", egress, "GB"),
                            ):
                                low_quantity = quantity.minimum
                                low_rate = Decimal(rate.low_unit_price_usd or rate.unit_price_usd)
                                high_rate = Decimal(rate.unit_price_usd)
                                lines.append(
                                    PlanCostLine(
                                        address=address,
                                        resource_type="aws_apigatewayv2_api",
                                        description=description,
                                        quantity=quantity.minimum,
                                        quantity_max=quantity.maximum,
                                        unit=unit,
                                        unit_price_usd=rate.unit_price_usd,
                                        monthly_cost_minor=int((low_rate * low_quantity * 100).quantize(Decimal(1), rounding=ROUND_FLOOR)),
                                        monthly_cost_max_minor=int((high_rate * quantity.maximum * 100).quantize(Decimal(1), rounding=ROUND_CEILING)),
                                        unit_price_low_usd=format(low_rate, "f"),
                                        unit_price_low_source_url=rate.low_rate_source_url,
                                        low_cost_quantity=low_quantity,
                                        catalog_sku=rate.sku,
                                        catalog_product_sha256=rate.product_digest,
                                        catalog_published_at=rate.published_at,
                                        catalog_effective_at=rate.effective_at,
                                    )
                                )
                    except PriceListUnavailableError:
                        unavailable = True
                        findings.append(
                            PlanPricingFinding(
                                "regional_price_lookup_unavailable",
                                (lambda_functions or http_apis)[0]["address"],
                                "DavDeploy could not verify current regional serverless prices.",
                            )
                        )
                    except PlanPricingError:
                        findings.append(
                            PlanPricingFinding(
                                "regional_price_ambiguous",
                                (lambda_functions or http_apis)[0]["address"],
                                "DavDeploy could not identify exact regional serverless prices.",
                            )
                        )

    dynamodb_document = trusted_context.dynamodb_usage_assumptions
    if dynamodb_tables:
        if dynamodb_document is None:
            findings.append(
                PlanPricingFinding(
                    "dynamodb_usage_assumptions_missing",
                    dynamodb_tables[0]["address"],
                    "Per-table request, storage, and PITR usage bounds are required for DynamoDB.",
                )
            )
        else:
            try:
                dynamodb_usage = DynamoDbPricingUsageAssumptions.model_validate(
                    dynamodb_document
                )
            except (TypeError, ValueError):
                findings.append(
                    PlanPricingFinding(
                        "dynamodb_usage_assumptions_invalid",
                        dynamodb_tables[0]["address"],
                        "Persisted DynamoDB usage assumptions are invalid.",
                    )
                )
            else:
                tables_by_address = {item["address"]: item for item in dynamodb_tables}
                if set(dynamodb_usage.tables) != set(tables_by_address):
                    findings.append(
                        PlanPricingFinding(
                            "dynamodb_usage_resource_mismatch",
                            dynamodb_tables[0]["address"],
                            "Usage bounds must cover every planned DynamoDB table exactly once.",
                        )
                    )
                else:
                    invalid_table = next(
                        (
                            (address, error)
                            for address, item in tables_by_address.items()
                            if (
                                error := _validate_dynamodb_table(
                                    item["values"], changes.get(address)
                                )
                            )
                            is not None
                        ),
                        None,
                    )
                    if invalid_table:
                        address, error = invalid_table
                        findings.append(PlanPricingFinding(error[0], address, error[1]))
                    else:
                        pitr_addresses = {
                            address
                            for address, item in tables_by_address.items()
                            if _dynamodb_pitr_enabled(item["values"])
                        }
                        usage_mismatch = next(
                            (
                                address
                                for address, assumptions in dynamodb_usage.tables.items()
                                if (
                                    address not in pitr_addresses
                                    and assumptions.monthly_pitr_storage_gb_month.maximum > 0
                                )
                                or (
                                    address in pitr_addresses
                                    and assumptions.monthly_pitr_storage_gb_month
                                    != assumptions.monthly_storage_gb_month
                                )
                            ),
                            None,
                        )
                        if usage_mismatch:
                            findings.append(
                                PlanPricingFinding(
                                    "dynamodb_pitr_usage_assumption_mismatch",
                                    usage_mismatch,
                                    "PITR storage bounds must match table storage when recovery is enabled and be zero when disabled.",
                                )
                            )
                        else:
                            try:
                                if pricing_catalog is None:
                                    pricing_catalog = AwsPriceListCatalog()
                                rates = {
                                    "read": pricing_catalog.dynamodb_read_request_rate(region),
                                    "write": pricing_catalog.dynamodb_write_request_rate(region),
                                    "storage": pricing_catalog.dynamodb_standard_storage_rate(region),
                                }
                                if pitr_addresses:
                                    rates["pitr"] = pricing_catalog.dynamodb_pitr_storage_rate(region)
                                for address, assumptions in dynamodb_usage.tables.items():
                                    for description, quantity, rate in (
                                        (
                                            "Amazon DynamoDB on-demand read request units",
                                            assumptions.monthly_read_request_units,
                                            rates["read"],
                                        ),
                                        (
                                            "Amazon DynamoDB on-demand write request units",
                                            assumptions.monthly_write_request_units,
                                            rates["write"],
                                        ),
                                        (
                                            "Amazon DynamoDB Standard table storage",
                                            assumptions.monthly_storage_gb_month,
                                            rates["storage"],
                                        ),
                                    ):
                                        unit_price = Decimal(rate.unit_price_usd)
                                        lines.append(
                                            PlanCostLine(
                                                address=address,
                                                resource_type="aws_dynamodb_table",
                                                description=description,
                                                quantity=quantity.minimum,
                                                quantity_max=quantity.maximum,
                                                unit=rate.unit,
                                                unit_price_usd=rate.unit_price_usd,
                                                monthly_cost_minor=int(
                                                    (unit_price * quantity.minimum * 100).quantize(
                                                        Decimal(1), rounding=ROUND_FLOOR
                                                    )
                                                ),
                                                monthly_cost_max_minor=int(
                                                    (unit_price * quantity.maximum * 100).quantize(
                                                        Decimal(1), rounding=ROUND_CEILING
                                                    )
                                                ),
                                                unit_price_low_usd=rate.unit_price_usd,
                                                low_cost_quantity=quantity.minimum,
                                                catalog_sku=rate.sku,
                                                catalog_product_sha256=rate.product_digest,
                                                catalog_published_at=rate.published_at,
                                                catalog_effective_at=rate.effective_at,
                                            )
                                        )
                                    if address in pitr_addresses:
                                        quantity = assumptions.monthly_pitr_storage_gb_month
                                        rate = rates["pitr"]
                                        unit_price = Decimal(rate.unit_price_usd)
                                        lines.append(
                                            PlanCostLine(
                                                address=address,
                                                resource_type="aws_dynamodb_table",
                                                description="Amazon DynamoDB point-in-time recovery storage",
                                                quantity=quantity.minimum,
                                                quantity_max=quantity.maximum,
                                                unit=rate.unit,
                                                unit_price_usd=rate.unit_price_usd,
                                                monthly_cost_minor=int(
                                                    (unit_price * quantity.minimum * 100).quantize(
                                                        Decimal(1), rounding=ROUND_FLOOR
                                                    )
                                                ),
                                                monthly_cost_max_minor=int(
                                                    (unit_price * quantity.maximum * 100).quantize(
                                                        Decimal(1), rounding=ROUND_CEILING
                                                    )
                                                ),
                                                unit_price_low_usd=rate.unit_price_usd,
                                                low_cost_quantity=quantity.minimum,
                                                catalog_sku=rate.sku,
                                                catalog_product_sha256=rate.product_digest,
                                                catalog_published_at=rate.published_at,
                                                catalog_effective_at=rate.effective_at,
                                            )
                                        )
                            except PriceListUnavailableError:
                                unavailable = True
                                findings.append(
                                    PlanPricingFinding(
                                        "regional_price_lookup_unavailable",
                                        dynamodb_tables[0]["address"],
                                        "DavDeploy could not verify current regional DynamoDB prices.",
                                    )
                                )
                            except PlanPricingError:
                                findings.append(
                                    PlanPricingFinding(
                                        "regional_price_ambiguous",
                                        dynamodb_tables[0]["address"],
                                        "DavDeploy could not identify exact regional DynamoDB prices.",
                                    )
                                )
    elif dynamodb_document is not None:
        findings.append(
            PlanPricingFinding(
                "dynamodb_usage_assumptions_stale",
                None,
                "DynamoDB usage assumptions do not match any table in this plan.",
            )
        )

    vpc_usage_document = trusted_context.vpc_usage_assumptions
    if nat_gateways:
        if vpc_usage_document is None:
            findings.append(PlanPricingFinding(
                "vpc_usage_assumptions_missing", nat_gateways[0]["address"],
                "NAT hours, processed data, cross-AZ transfer, and internet egress assumptions are required.",
            ))
        else:
            try:
                vpc_usage = VpcPricingUsageAssumptions.model_validate(vpc_usage_document)
                nat_by_address = {item["address"]: item for item in nat_gateways}
                if set(vpc_usage.nat_gateways) != set(nat_by_address):
                    findings.append(PlanPricingFinding(
                        "vpc_usage_assumptions_stale", None,
                        "VPC usage assumptions must match every exact NAT Gateway address in the plan.",
                    ))
                else:
                    eips_by_address = {item["address"]: item for item in elastic_ips}
                    known_eip_ids = [
                        item["values"].get("id")
                        for item in elastic_ips
                        if isinstance(item["values"].get("id"), str)
                    ]
                    eips_by_allocation = {
                        item["values"].get("id"): item for item in elastic_ips
                        if isinstance(item["values"].get("id"), str)
                    }
                    used_eips: set[str] = set()
                    invalid_nat = None
                    if len(eips_by_allocation) != len(known_eip_ids):
                        invalid_nat = nat_gateways[0]["address"]
                    for address, item in nat_by_address.items():
                        if invalid_nat is not None:
                            break
                        values = item["values"]
                        allocation_id = values.get("allocation_id")
                        secondary_ids = values.get("secondary_allocation_ids") or []
                        nat_change = changes.get(address)
                        nat_change_details = (
                            nat_change.get("change")
                            if isinstance(nat_change, dict)
                            else None
                        )
                        after_unknown = (
                            nat_change_details.get("after_unknown")
                            if isinstance(nat_change_details, dict)
                            else None
                        )
                        secondary_ids_unknown = (
                            not isinstance(after_unknown, dict)
                            or not _valid_unknown_tree(after_unknown)
                            or _path_contains_unknown(
                                after_unknown, ("secondary_allocation_ids",)
                            )
                        )
                        if isinstance(allocation_id, str):
                            bound_eip = eips_by_allocation.get(allocation_id)
                            eip_address = bound_eip.get("address") if bound_eip else None
                        else:
                            references = _configured_attribute_references(
                                document, address, "allocation_id"
                            )
                            matches = [
                                candidate for candidate in eips_by_address
                                if references
                                and all(
                                    _reference_matches_resource((reference,), candidate)
                                    for reference in references
                                )
                            ]
                            eip_address = (
                                matches[0]
                                if references and len(matches) == 1
                                else None
                            )
                        eip = eips_by_address.get(eip_address)
                        usage = vpc_usage.nat_gateways[address]
                        if (
                            values.get("connectivity_type") != "public"
                            or secondary_ids
                            or secondary_ids_unknown
                            or eip_address is None
                            or not isinstance(eip, dict)
                            or eip["values"].get("domain") != "vpc"
                            or eip_address in used_eips
                        ):
                            invalid_nat = address
                            break
                        used_eips.add(eip_address)
                        if (
                            usage.monthly_internet_egress_gb.maximum
                            > usage.monthly_data_processed_gb.maximum
                            or usage.monthly_cross_az_payload_gb.maximum
                            > usage.monthly_data_processed_gb.maximum
                        ):
                            invalid_nat = address
                            break
                    if invalid_nat is not None:
                        findings.append(PlanPricingFinding(
                            "vpc_nat_shape_or_usage_unsupported", invalid_nat,
                            "Pricing requires one public NAT Gateway bound to one same-plan Elastic IP and consistent transfer bounds.",
                        ))
                    elif used_eips != set(eips_by_address):
                        findings.append(PlanPricingFinding(
                            "vpc_unbound_public_ipv4", None,
                            "Every planned Elastic IP must be attached to exactly one priced public NAT Gateway.",
                        ))
                    else:
                        if pricing_catalog is None:
                            pricing_catalog = AwsPriceListCatalog()
                        for address in nat_by_address:
                            usage = vpc_usage.nat_gateways[address]
                            rates = [
                                ("Amazon VPC NAT Gateway available hours",
                                 usage.monthly_available_hours,
                                 pricing_catalog.nat_gateway_hourly_rate(region), 1),
                                ("Amazon VPC NAT Gateway data processed",
                                 usage.monthly_data_processed_gb,
                                 pricing_catalog.nat_gateway_data_processing_rate(region), 1),
                                ("Amazon VPC in-use public IPv4 address hours",
                                 usage.monthly_available_hours,
                                 pricing_catalog.public_ipv4_in_use_rate(region), 1),
                            ]
                            if usage.monthly_internet_egress_gb.maximum:
                                rates.append((
                                    "AWS internet data transfer out",
                                    usage.monthly_internet_egress_gb,
                                    pricing_catalog.aws_internet_egress_rate(region), 1,
                                ))
                            if usage.monthly_cross_az_payload_gb.maximum:
                                rates.append((
                                    "Cross-AZ data transfer in and out",
                                    usage.monthly_cross_az_payload_gb,
                                    pricing_catalog.regional_data_transfer_rate(region), 2,
                                ))
                            for description, quantity, rate, multiplier in rates:
                                low_quantity = quantity.minimum * multiplier
                                high_quantity = quantity.maximum * multiplier
                                unit_price = Decimal(rate.unit_price_usd)
                                low_unit_price = Decimal(
                                    rate.low_unit_price_usd or rate.unit_price_usd
                                )
                                lines.append(PlanCostLine(
                                    address=address,
                                    resource_type="aws_nat_gateway",
                                    description=description,
                                    quantity=low_quantity,
                                    quantity_max=high_quantity,
                                    unit=rate.unit,
                                    unit_price_usd=rate.unit_price_usd,
                                    monthly_cost_minor=int(
                                        (low_unit_price * low_quantity * 100).quantize(
                                            Decimal(1), rounding=ROUND_FLOOR
                                        )
                                    ),
                                    monthly_cost_max_minor=int(
                                        (unit_price * high_quantity * 100).quantize(
                                            Decimal(1), rounding=ROUND_CEILING
                                        )
                                    ),
                                    catalog_sku=rate.sku,
                                    catalog_product_sha256=rate.product_digest,
                                    catalog_published_at=rate.published_at,
                                    catalog_effective_at=rate.effective_at,
                                    unit_price_low_usd=format(low_unit_price, "f"),
                                    unit_price_low_source_url=rate.low_rate_source_url,
                                    low_cost_quantity=low_quantity,
                                ))
            except PriceListUnavailableError:
                unavailable = True
                findings.append(PlanPricingFinding(
                    "regional_price_lookup_unavailable", nat_gateways[0]["address"],
                    "DavDeploy could not verify current regional VPC/NAT Gateway prices.",
                ))
            except PlanPricingError:
                findings.append(PlanPricingFinding(
                    "regional_price_ambiguous", nat_gateways[0]["address"],
                    "DavDeploy could not identify exact regional VPC/NAT Gateway prices.",
                ))
            except (TypeError, ValueError):
                findings.append(PlanPricingFinding(
                    "vpc_usage_assumptions_invalid", nat_gateways[0]["address"],
                    "Persisted VPC usage assumptions are invalid for pricing.",
                ))
    elif vpc_usage_document is not None:
        try:
            vpc_usage = VpcPricingUsageAssumptions.model_validate(vpc_usage_document)
        except (TypeError, ValueError):
            findings.append(PlanPricingFinding(
                "vpc_usage_assumptions_invalid", None,
                "Persisted VPC usage assumptions are invalid for pricing.",
            ))
        else:
            if vpc_usage.nat_gateways:
                findings.append(PlanPricingFinding(
                    "vpc_usage_assumptions_stale", None,
                    "NAT Gateway usage assumptions do not match any NAT Gateway in this plan.",
                ))
    vpc_endpoint_usage = None
    if interface_vpc_endpoints:
        endpoint_address = interface_vpc_endpoints[0]["address"]
        if vpc_usage_document is None:
            findings.append(PlanPricingFinding(
                "vpc_endpoint_usage_assumptions_missing", endpoint_address,
                "Monthly provisioned hours and processed-data bounds are required for each interface endpoint.",
            ))
        else:
            try:
                vpc_endpoint_usage = VpcPricingUsageAssumptions.model_validate(
                    vpc_usage_document
                )
            except (TypeError, ValueError):
                findings.append(PlanPricingFinding(
                    "vpc_usage_assumptions_invalid", endpoint_address,
                    "Persisted VPC pricing usage assumptions are invalid.",
                ))
            else:
                endpoint_usages = vpc_endpoint_usage.interface_endpoints or {}
                endpoints_by_address = {
                    item["address"]: item for item in interface_vpc_endpoints
                }
                if set(endpoint_usages) != set(endpoints_by_address):
                    findings.append(PlanPricingFinding(
                        "vpc_endpoint_usage_assumptions_stale", endpoint_address,
                        "Interface endpoint usage bounds must match every exact endpoint address in the plan.",
                    ))
                else:
                    for address, endpoint in endpoints_by_address.items():
                        values = endpoint["values"]
                        service_name = values.get("service_name")
                        subnet_ids = values.get("subnet_ids")
                        az_count = _interface_endpoint_az_count(
                            subnet_ids, planned_subnets, region
                        )
                        if (
                            values.get("vpc_endpoint_type") != "Interface"
                            or not _supported_interface_endpoint_service(
                                service_name, region
                            )
                            or az_count is None
                        ):
                            findings.append(PlanPricingFinding(
                                "vpc_endpoint_shape_unsupported", address,
                                "Only ECR API, ECR Docker, or CloudWatch Logs same-region interface endpoints with known, same-plan subnet IDs in distinct Availability Zones are priced.",
                            ))
                            continue
                        try:
                            if pricing_catalog is None:
                                pricing_catalog = AwsPriceListCatalog()
                            hourly_rate = pricing_catalog.interface_vpc_endpoint_hourly_rate(
                                region
                            )
                            data_rate = pricing_catalog.interface_vpc_endpoint_data_rate(
                                region
                            )
                        except PriceListUnavailableError:
                            unavailable = True
                            findings.append(PlanPricingFinding(
                                "regional_price_lookup_unavailable", address,
                                "DavDeploy could not verify current regional interface endpoint prices.",
                            ))
                            continue
                        except PlanPricingError:
                            findings.append(PlanPricingFinding(
                                "regional_price_ambiguous", address,
                                "DavDeploy could not identify exact regional interface endpoint prices.",
                            ))
                            continue
                        usage = endpoint_usages[address]
                        for description, quantity, rate in (
                            (
                                "Amazon VPC interface endpoint provisioned hours",
                                usage.monthly_billed_hours_per_az.minimum * az_count,
                                hourly_rate,
                            ),
                            (
                                "Amazon VPC interface endpoint data processed",
                                usage.monthly_data_processed_gb.minimum,
                                data_rate,
                            ),
                        ):
                            quantity_max = (
                                usage.monthly_billed_hours_per_az.maximum * az_count
                                if "provisioned hours" in description
                                else usage.monthly_data_processed_gb.maximum
                            )
                            unit_price = Decimal(rate.unit_price_usd)
                            low_unit_price = Decimal(
                                rate.low_unit_price_usd or rate.unit_price_usd
                            )
                            lines.append(PlanCostLine(
                                address=address,
                                resource_type="aws_vpc_endpoint",
                                description=description,
                                quantity=quantity,
                                quantity_max=quantity_max,
                                unit=rate.unit,
                                unit_price_usd=rate.unit_price_usd,
                                monthly_cost_minor=int(
                                    (low_unit_price * quantity * 100).quantize(
                                        Decimal(1), rounding=ROUND_FLOOR
                                    )
                                ),
                                monthly_cost_max_minor=int(
                                    (unit_price * quantity_max * 100).quantize(
                                        Decimal(1), rounding=ROUND_CEILING
                                    )
                                ),
                                catalog_sku=rate.sku,
                                catalog_product_sha256=rate.product_digest,
                                catalog_published_at=rate.published_at,
                                catalog_effective_at=rate.effective_at,
                                unit_price_low_usd=format(low_unit_price, "f"),
                                low_cost_quantity=quantity,
                            ))
    else:
        if vpc_usage_document is not None:
            try:
                vpc_endpoint_usage = VpcPricingUsageAssumptions.model_validate(
                    vpc_usage_document
                )
            except (TypeError, ValueError):
                findings.append(PlanPricingFinding(
                    "vpc_usage_assumptions_invalid", None,
                    "Persisted VPC pricing usage assumptions are invalid.",
                ))
            else:
                if vpc_endpoint_usage.interface_endpoints:
                    findings.append(PlanPricingFinding(
                        "vpc_endpoint_usage_assumptions_stale", None,
                        "Interface endpoint usage assumptions do not match any interface endpoint in this plan.",
                    ))
    if elastic_ips and not nat_gateways:
        findings.append(PlanPricingFinding(
            "resource_pricing_unavailable", elastic_ips[0]["address"],
            "Elastic IP pricing is only supported when the address is bound to a priced NAT Gateway.",
        ))

    total_max_minor = sum(
        item.monthly_cost_minor
        if item.monthly_cost_max_minor is None
        else item.monthly_cost_max_minor
        for item in lines
    )
    within_budget = None if monthly_budget_minor is None else total_max_minor <= monthly_budget_minor
    if within_budget is False:
        findings.append(
            PlanPricingFinding(
                "monthly_budget_exceeded",
                None,
                "The verified monthly estimate exceeds the stated budget ceiling.",
            )
        )
    has_pricing_blocker = any(finding.code != "monthly_budget_exceeded" for finding in findings)
    status = (
        PlanPricingStatus.UNAVAILABLE
        if unavailable
        else PlanPricingStatus.INCOMPLETE
        if has_pricing_blocker
        else PlanPricingStatus.COMPLETE
    )
    return _evidence(
        status,
        region,
        currency,
        captured_at_text,
        monthly_budget_minor,
        document,
        tuple(lines),
        tuple(sorted(findings, key=lambda item: (item.code, item.address or ""))),
        within_budget=within_budget,
        proposal_declared_budget_minor=proposal_declared_budget_minor,
        proposal_declared_currency=proposal_declared_currency,
        persisted_context_sha256=persisted_context_sha256,
        usage_assumptions=trusted_context.usage_assumptions,
        sqs_usage_assumptions=trusted_context.sqs_usage_assumptions,
        rds_usage_assumptions=trusted_context.rds_usage_assumptions,
        serverless_usage_assumptions=trusted_context.serverless_usage_assumptions,
        dynamodb_usage_assumptions=trusted_context.dynamodb_usage_assumptions,
        vpc_usage_assumptions=trusted_context.vpc_usage_assumptions,
        batch_usage_assumptions=trusted_context.batch_usage_assumptions,
        ecr_usage_assumptions=trusted_context.ecr_usage_assumptions,
        ecs_express_usage_assumptions=trusted_context.ecs_express_usage_assumptions,
        transitions=transitions,
    )


def pricing_evidence_is_fresh(captured_at: str, *, now: datetime | None = None) -> bool:
    """Accept evidence up to 24h old and at most 5m ahead of the approval clock."""
    if not isinstance(captured_at, str):
        return False
    try:
        captured = datetime.fromisoformat(captured_at)
    except ValueError:
        return False
    current = now or datetime.now(UTC)
    if captured.tzinfo is None or current.tzinfo is None:
        return False
    age = current.astimezone(UTC) - captured.astimezone(UTC)
    return -MAX_PRICING_EVIDENCE_FUTURE_SKEW <= age <= MAX_PRICING_EVIDENCE_AGE


def pricing_evidence_document_is_valid(document: Any) -> bool:
    """Verify an evidence manifest's digest without exposing raw Terraform JSON."""
    if not isinstance(document, dict):
        return False
    expected = document.get("evidence_sha256")
    if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
        return False
    unsigned = {key: value for key, value in document.items() if key != "evidence_sha256"}
    try:
        return _canonical_digest(unsigned) == expected
    except (TypeError, ValueError, RecursionError):
        return False


def _validate_ecs_express_pricing_shape(
    document: dict[str, Any],
    resources: tuple[dict[str, Any], ...],
    services: list[dict[str, Any]],
    repositories: list[dict[str, Any]],
    log_groups: list[dict[str, Any]],
    region: str,
) -> bool:
    """Accept only the reviewed single-service pilot inventory and bindings."""
    configured_references = _pricing_configured_resource_references(document)

    def references_resource(
        source: str,
        target: str,
        field: str,
        *,
        allow_count_index: bool = False,
    ) -> bool:
        source = source.split("[", maxsplit=1)[0]
        references = configured_references.get(source, {}).get(field, ())
        target_references = tuple(
            reference for reference in references
            if reference == target or reference.startswith(f"{target}.")
        )
        return bool(target_references) and all(
            reference in target_references
            or (allow_count_index and reference == "count.index")
            for reference in references
        )

    def matches_or_references(
        value: Any,
        expected: Any,
        source: str,
        target: str,
        field: str,
        *,
        allow_count_index: bool = False,
    ) -> bool:
        return value == expected if value is not None else references_resource(
            source, target, field, allow_count_index=allow_count_index
        )

    expected_counts = {
        "terraform_data": 1,
        "aws_ecs_express_gateway_service": 1,
        "aws_iam_role": 2,
        "aws_iam_role_policy_attachment": 2,
        "aws_vpc": 1,
        "aws_internet_gateway": 1,
        "aws_subnet": 2,
        "aws_route_table": 1,
        "aws_route_table_association": 2,
        "aws_ecr_repository": 1,
        "aws_cloudwatch_log_group": 1,
    }
    counts = {kind: sum(item["type"] == kind for item in resources) for kind in expected_counts}
    expected_addresses = {
        "terraform_data.account_guard",
        "aws_ecs_express_gateway_service.workload[0]",
        "aws_iam_role.execution",
        "aws_iam_role.infrastructure",
        "aws_iam_role_policy_attachment.execution",
        "aws_iam_role_policy_attachment.infrastructure",
        "aws_vpc.customer",
        "aws_internet_gateway.customer",
        "aws_subnet.public[0]",
        "aws_subnet.public[1]",
        "aws_route_table.public",
        "aws_route_table_association.public[0]",
        "aws_route_table_association.public[1]",
        "aws_ecr_repository.workload",
        "aws_cloudwatch_log_group.workload",
    }
    if (
        any(item["type"] not in expected_counts for item in resources)
        or counts != expected_counts
        or {item["address"] for item in resources} != expected_addresses
        or len(services) != 1
    ):
        return False

    service = services[0]
    address = service["address"]
    values = service["values"]
    if (
        address != "aws_ecs_express_gateway_service.workload[0]"
        or values.get("cpu") not in ("256", 256)
        or values.get("memory") not in ("512", 512)
        or values.get("region") not in (None, region)
        or values.get("wait_for_steady_state") is not True
        or values.get("task_role_arn") not in (None, "")
        or values.get("health_check_path") != "/healthz"
        or values.get("cluster") not in (None, "default")
    ):
        return False

    name = values.get("service_name")
    if not isinstance(name, str) or re.fullmatch(r"davdeploy-ecs-[a-f0-9]{24}", name) is None:
        return False
    containers = values.get("primary_container")
    if not isinstance(containers, list) or len(containers) != 1 or not isinstance(containers[0], dict):
        return False
    container = containers[0]
    repo_values = repositories[0]["values"]
    repo_address = repositories[0]["address"]
    log_values = log_groups[0]["values"]
    log_address = log_groups[0]["address"]
    registry = repo_values.get("registry_id")
    repo_url = repo_values.get("repository_url")
    image = container.get("image")
    account_guard = next(
        item for item in resources if item["address"] == "terraform_data.account_guard"
    )["values"].get("input")
    expected_repository_url = (
        f"{account_guard}.dkr.ecr.{region}.amazonaws.com/{name}"
        if isinstance(account_guard, str) and re.fullmatch(r"\d{12}", account_guard)
        else None
    )
    image_pattern = (
        rf"^{re.escape(account_guard)}\.dkr\.ecr\.{re.escape(region)}\.amazonaws\.com/"
        rf"{re.escape(name)}@sha256:[a-f0-9]{{64}}$"
        if isinstance(account_guard, str) and re.fullmatch(r"\d{12}", account_guard)
        else r"(?!)"
    )
    if (
        repo_address != "aws_ecr_repository.workload"
        or repo_values.get("name") != name
        or not isinstance(expected_repository_url, str)
        or (repo_url is not None and repo_url != expected_repository_url)
        or (registry is not None and registry != account_guard)
        or repo_values.get("encryption_configuration") not in (
            [{"encryption_type": "AES256", "kms_key": None}],
            [{"encryption_type": "AES256"}],
        )
        or not isinstance(image, str)
        or re.fullmatch(image_pattern, image) is None
        or not image.startswith(f"{expected_repository_url}@sha256:")
        or log_address != "aws_cloudwatch_log_group.workload"
        or log_values.get("name") != f"/aws/ecs/{name}"
        or log_values.get("retention_in_days") != 3
        or log_values.get("log_group_class") not in (None, "STANDARD")
        or log_values.get("kms_key_id") not in (None, "")
        or account_guard is None
    ):
        return False
    logs = container.get("aws_logs_configuration")
    if (
        not isinstance(logs, list)
        or len(logs) != 1
        or not isinstance(logs[0], dict)
        or logs[0].get("log_group") != log_values.get("name")
        or logs[0].get("log_stream_prefix") != "customer-test"
        or container.get("container_port") not in (8000, "8000")
        or container.get("environment") != [
            {"name": "DAVDEPLOY_TEST_SCOPE", "value": "same-account-customer-sandbox"}
        ]
        or container.get("secret") not in (None, [])
        or container.get("repository_credentials") not in (None, [])
        or container.get("command") not in (None, [])
    ):
        return False
    scaling = values.get("scaling_target")
    if (
        not isinstance(scaling, list)
        or len(scaling) != 1
        or not isinstance(scaling[0], dict)
        or scaling[0].get("min_task_count") != 1
        or scaling[0].get("max_task_count") != 1
        or scaling[0].get("auto_scaling_metric") != "AVERAGE_CPU"
        or scaling[0].get("auto_scaling_target_value") != 70
    ):
        return False
    network = values.get("network_configuration")
    subnets = [item for item in resources if item["type"] == "aws_subnet"]
    subnet_ids = {item["values"].get("id") for item in subnets}
    network_subnets = (
        network[0].get("subnets")
        if isinstance(network, list) and len(network) == 1 and isinstance(network[0], dict)
        else None
    )
    vpc = next(item for item in resources if item["type"] == "aws_vpc")["values"]
    gateway = next(item for item in resources if item["type"] == "aws_internet_gateway")["values"]
    route_table = next(item for item in resources if item["type"] == "aws_route_table")["values"]
    associations = [item["values"] for item in resources if item["type"] == "aws_route_table_association"]
    expected_subnets = {
        "aws_subnet.public[0]": "10.84.10.0/24",
        "aws_subnet.public[1]": "10.84.11.0/24",
    }
    subnets_valid = all(
        matches_or_references(
            item["values"].get("vpc_id"), vpc.get("id"),
            item["address"], "aws_vpc.customer", "vpc_id",
        )
        and item["values"].get("map_public_ip_on_launch") is True
        and item["values"].get("assign_ipv6_address_on_creation") is not True
        and item["values"].get("cidr_block") == expected_subnets[item["address"]]
        and isinstance(item["values"].get("availability_zone"), str)
        and item["values"]["availability_zone"].startswith(region)
        for item in subnets
    )
    availability_zones = {item["values"].get("availability_zone") for item in subnets}
    routes = route_table.get("route")
    route_valid = (
        isinstance(routes, list)
        and len(routes) == 1
        and isinstance(routes[0], dict)
        and routes[0].get("cidr_block") == "0.0.0.0/0"
        and matches_or_references(
            routes[0].get("gateway_id"), gateway.get("id"),
            "aws_route_table.public", "aws_internet_gateway.customer", "route",
        )
    )
    subnet_ids_by_address = {item["address"]: item["values"].get("id") for item in subnets}
    return (
        isinstance(network_subnets, list)
        and (
            (
                all(isinstance(item, str) for item in network_subnets)
                and set(network_subnets) == subnet_ids
            )
            or (
                len(network_subnets) == 2
                and all(item is None for item in network_subnets)
                and references_resource(
                    "aws_ecs_express_gateway_service.workload",
                    "aws_subnet.public",
                    "network_configuration",
                )
            )
        )
        and network[0].get("security_groups") in (None, [])
        and len(subnets) == 2
        and (
            (all(isinstance(value, str) for value in subnet_ids) and len(subnet_ids) == 2)
            or all(value is None for value in subnet_ids)
        )
        and vpc.get("cidr_block") == "10.84.0.0/16"
        and vpc.get("enable_dns_support") is True
        and vpc.get("enable_dns_hostnames") is True
        and vpc.get("assign_generated_ipv6_cidr_block") is not True
        and matches_or_references(
            gateway.get("vpc_id"), vpc.get("id"),
            "aws_internet_gateway.customer", "aws_vpc.customer", "vpc_id",
        )
        and matches_or_references(
            route_table.get("vpc_id"), vpc.get("id"),
            "aws_route_table.public", "aws_vpc.customer", "vpc_id",
        )
        and route_valid
        and subnets_valid
        and len(availability_zones) == 2
        and len(associations) == 2
        and all(
            matches_or_references(
                next(
                    item["values"] for item in resources
                    if item["address"] == f"aws_route_table_association.public[{index}]"
                ).get("subnet_id"),
                subnet_ids_by_address.get(f"aws_subnet.public[{index}]"),
                f"aws_route_table_association.public[{index}]",
                "aws_subnet.public",
                "subnet_id",
                allow_count_index=True,
            )
            and matches_or_references(
                next(
                    item["values"] for item in resources
                    if item["address"] == f"aws_route_table_association.public[{index}]"
                ).get("route_table_id"),
                route_table.get("id"),
                f"aws_route_table_association.public[{index}]",
                "aws_route_table.public",
                "route_table_id",
            )
            for index in range(2)
        )
    )


def _pricing_configured_resource_references(
    document: dict[str, Any],
) -> dict[str, dict[str, tuple[str, ...]]]:
    configuration = document.get("configuration")
    root = configuration.get("root_module") if isinstance(configuration, dict) else None
    resources = root.get("resources") if isinstance(root, dict) else None
    if not isinstance(resources, list):
        return {}
    result: dict[str, dict[str, tuple[str, ...]]] = {}
    for resource in resources:
        if not isinstance(resource, dict) or not isinstance(resource.get("address"), str):
            continue
        expressions = resource.get("expressions")
        if not isinstance(expressions, dict):
            continue
        result[resource["address"].split("[", maxsplit=1)[0]] = {
            field: tuple(reference for reference in expression.get("references", []) if isinstance(reference, str))
            for field, expression in expressions.items()
            if isinstance(expression, dict) and isinstance(expression.get("references", []), list)
        }
    return result


def pricing_evidence_safe_summary(document: Any) -> dict[str, Any] | None:
    """Return the public-safe summary only for an intact evidence document."""
    if not pricing_evidence_document_is_valid(document):
        return None
    return {
        "status": document.get("status"),
        "currency": document.get("currency"),
        "rate_type": document.get("rate_type"),
        "monthly_low_minor": document.get("monthly_low_minor"),
        "monthly_high_minor": document.get("monthly_high_minor"),
        "monthly_budget_minor": document.get("monthly_budget_minor"),
        "within_budget": document.get("within_budget"),
        "captured_at": document.get("captured_at"),
        "estimate_disclaimer": document.get("estimate_disclaimer"),
        "usage_assumptions": document.get("usage_assumptions"),
        "sqs_usage_assumptions": document.get("sqs_usage_assumptions"),
        "rds_usage_assumptions": document.get("rds_usage_assumptions"),
        "serverless_usage_assumptions": document.get("serverless_usage_assumptions"),
        "dynamodb_usage_assumptions": document.get("dynamodb_usage_assumptions"),
        "vpc_usage_assumptions": document.get("vpc_usage_assumptions"),
        "batch_usage_assumptions": document.get("batch_usage_assumptions"),
        "ecr_usage_assumptions": document.get("ecr_usage_assumptions"),
        "ecs_express_usage_assumptions": document.get("ecs_express_usage_assumptions"),
        "evidence_sha256": document.get("evidence_sha256"),
    }


def pricing_evidence_is_approval_eligible(
    document: Any,
    *,
    trusted_context: TrustedPlanPricingContext,
    now: datetime | None = None,
) -> bool:
    """Recheck the immutable evidence against trusted customer constraints."""
    if not pricing_evidence_document_is_valid(document):
        return False
    if not pricing_evidence_is_fresh(document.get("captured_at"), now=now):
        return False
    if (
        document.get("status") != PlanPricingStatus.COMPLETE.value
        or document.get("region") != trusted_context.region
        or document.get("currency") != trusted_context.currency
        or document.get("monthly_budget_minor") != trusted_context.monthly_budget_minor
        or document.get("persisted_context_sha256") != trusted_context.persisted_context_sha256
        or document.get("pricing_context_sha256") != trusted_context.pricing_context_sha256
        or document.get("usage_assumptions") != trusted_context.usage_assumptions
        or document.get("sqs_usage_assumptions") != trusted_context.sqs_usage_assumptions
        or document.get("rds_usage_assumptions") != trusted_context.rds_usage_assumptions
        or document.get("serverless_usage_assumptions") != trusted_context.serverless_usage_assumptions
        or document.get("dynamodb_usage_assumptions") != trusted_context.dynamodb_usage_assumptions
        or document.get("vpc_usage_assumptions") != trusted_context.vpc_usage_assumptions
        or document.get("batch_usage_assumptions") != trusted_context.batch_usage_assumptions
        or document.get("ecr_usage_assumptions") != trusted_context.ecr_usage_assumptions
        or document.get("ecs_express_usage_assumptions") != trusted_context.ecs_express_usage_assumptions
        or document.get("budget_source") != "PERSISTED_CUSTOMER_CONTEXT"
        or document.get("rate_type") != "ON_DEMAND_PUBLIC_PRICE_LIST"
        or document.get("within_budget") is False
    ):
        return False

    declared_budget = document.get("proposal_declared_budget_minor")
    declared_currency = document.get("proposal_declared_currency")
    if declared_budget not in (None, trusted_context.monthly_budget_minor):
        return False
    if declared_currency not in (None, trusted_context.currency):
        return False

    low, high = document.get("monthly_low_minor"), document.get("monthly_high_minor")
    lines = document.get("lines")
    if (
        isinstance(low, bool)
        or not isinstance(low, int)
        or low < 0
        or isinstance(high, bool)
        or not isinstance(high, int)
        or high < low
        or not isinstance(lines, list)
    ):
        return False
    line_total = 0
    line_max_total = 0
    for line in lines:
        if not isinstance(line, dict):
            return False
        amount = line.get("monthly_cost_minor")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            return False
        line_total += amount
        maximum = line.get("monthly_cost_max_minor", amount)
        if maximum is None:
            maximum = amount
        quantity = line.get("quantity")
        quantity_max = line.get("quantity_max")
        if quantity_max is None:
            quantity_max = quantity
        if (
            isinstance(maximum, bool)
            or not isinstance(maximum, int)
            or maximum < amount
            or isinstance(quantity, bool)
            or not isinstance(quantity, int)
            or quantity < 0
            or isinstance(quantity_max, bool)
            or not isinstance(quantity_max, int)
            or quantity_max < quantity
        ):
            return False
        low_cost_quantity = line.get("low_cost_quantity")
        if low_cost_quantity is None:
            low_cost_quantity = quantity
        if (
            isinstance(low_cost_quantity, bool)
            or not isinstance(low_cost_quantity, int)
            or low_cost_quantity < 0
            or low_cost_quantity > quantity
        ):
            return False
        if line.get("unit_price_low_usd") is not None:
            try:
                low_rate = Decimal(line["unit_price_low_usd"])
                high_rate = Decimal(line["unit_price_usd"])
            except (InvalidOperation, TypeError, ValueError):
                return False
            if (
                not low_rate.is_finite()
                or not high_rate.is_finite()
                or low_rate < 0
                or high_rate < low_rate
                or amount
                != int(
                    (low_rate * low_cost_quantity * 100).quantize(
                        Decimal(1), rounding=ROUND_FLOOR
                    )
                )
                or maximum
                != int(
                    (high_rate * quantity_max * 100).quantize(
                        Decimal(1), rounding=ROUND_CEILING
                    )
                )
            ):
                return False
        line_max_total += maximum
    if low != line_total or high != line_max_total:
        return False
    s3_lines = [line for line in lines if line.get("resource_type") == "aws_s3_bucket"]
    rds_lines = [line for line in lines if line.get("resource_type") == "aws_db_instance"]
    if rds_lines:
        if trusted_context.rds_usage_assumptions is None:
            return False
        try:
            RdsPricingUsageAssumptions.model_validate(trusted_context.rds_usage_assumptions)
        except (TypeError, ValueError):
            return False
        if (
            trusted_context.rds_usage_assumptions.get("monthly_backup_storage_gb_month") is None
            or _has_aurora_usage_assumptions(trusted_context.rds_usage_assumptions)
        ):
            return False
    aurora_lines = [line for line in lines if line.get("resource_type") == "aws_rds_cluster"]
    if aurora_lines:
        if trusted_context.rds_usage_assumptions is None:
            return False
        try:
            aurora_usage = RdsPricingUsageAssumptions.model_validate(
                trusted_context.rds_usage_assumptions
            )
        except (TypeError, ValueError):
            return False
        if (
            aurora_usage.monthly_backup_storage_gb_month is not None
            or aurora_usage.aurora_monthly_storage_gb_month is None
            or aurora_usage.aurora_monthly_io_requests is None
            or aurora_usage.aurora_monthly_backup_overage_gb_month is None
            or aurora_usage.aurora_monthly_secret_api_requests is None
            or aurora_usage.aurora_monthly_inter_az_transfer_gb is None
            or aurora_usage.aurora_monthly_cross_region_transfer_gb is None
            or aurora_usage.aurora_monthly_internet_egress_gb is None
            or aurora_usage.aurora_monthly_inter_az_transfer_gb.maximum > 0
            or aurora_usage.aurora_monthly_cross_region_transfer_gb.maximum > 0
            or aurora_usage.aurora_monthly_internet_egress_gb.maximum > 0
        ):
            return False
        expected_aurora_lines = {
            "Aurora PostgreSQL Serverless v2 ACU-hours": (365, 1460, "ACU-Hr"),
            "Aurora Standard storage": (
                aurora_usage.aurora_monthly_storage_gb_month.minimum,
                aurora_usage.aurora_monthly_storage_gb_month.maximum,
                "GB-Mo",
            ),
            "Aurora Standard I/O requests": (
                aurora_usage.aurora_monthly_io_requests.minimum,
                aurora_usage.aurora_monthly_io_requests.maximum,
                "IOs",
            ),
            "Aurora billable backup storage overage": (
                aurora_usage.aurora_monthly_backup_overage_gb_month.minimum,
                aurora_usage.aurora_monthly_backup_overage_gb_month.maximum,
                "GB-Mo",
            ),
            "AWS Secrets Manager secret storage for the RDS-managed credential": (1, 1, "Secrets"),
            "AWS Secrets Manager API requests for credential reads and rotation": (
                aurora_usage.aurora_monthly_secret_api_requests.minimum,
                aurora_usage.aurora_monthly_secret_api_requests.maximum,
                "API Requests",
            ),
        }
        actual_aurora_lines = {line.get("description"): line for line in aurora_lines}
        if len(aurora_lines) != len(expected_aurora_lines) or set(actual_aurora_lines) != set(expected_aurora_lines):
            return False
        for description, (quantity, quantity_max, unit) in expected_aurora_lines.items():
            line = actual_aurora_lines[description]
            if (
                line.get("quantity") != quantity
                or line.get("quantity_max") != quantity_max
                or line.get("low_cost_quantity") != quantity
                or line.get("unit") != unit
                or not isinstance(line.get("address"), str)
                or line["address"].rsplit(".", 2)[-2] != "aws_rds_cluster"
            ):
                return False
    if s3_lines:
        if trusted_context.usage_assumptions is None:
            return False
        try:
            assumptions = S3PricingUsageAssumptions.model_validate(
                trusted_context.usage_assumptions
            )
        except (TypeError, ValueError):
            return False
        expected_s3_lines = {
            "Amazon S3 Standard storage": (
                assumptions.monthly_storage_gb,
                "GB-Mo",
            ),
            "Amazon S3 Standard PUT/COPY/POST/LIST requests": (
                assumptions.monthly_put_copy_post_list_requests,
                "Requests",
            ),
            "Amazon S3 Standard GET requests": (
                assumptions.monthly_get_requests,
                "Requests",
            ),
            "AWS internet data transfer out": (
                assumptions.monthly_internet_egress_gb,
                "GB",
            ),
        }
        if len(s3_lines) != len(expected_s3_lines):
            return False
        actual_s3_lines = {line.get("description"): line for line in s3_lines}
        if set(actual_s3_lines) != set(expected_s3_lines):
            return False
        for description, (usage, unit) in expected_s3_lines.items():
            line = actual_s3_lines[description]
            expected_low_quantity = usage.minimum
            if (
                line.get("quantity") != usage.minimum
                or line.get("quantity_max") != usage.maximum
                or line.get("low_cost_quantity") != expected_low_quantity
                or line.get("unit") != unit
            ):
                return False
            if description == "AWS internet data transfer out" and (
                line.get("unit_price_low_usd") != "0.05"
                or line.get("unit_price_low_source_url")
                != "https://aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer"
            ):
                return False
    sqs_lines = [line for line in lines if line.get("resource_type") == "aws_sqs_queue"]
    if sqs_lines:
        if trusted_context.sqs_usage_assumptions is None:
            return False
        try:
            assumptions = SqsPricingUsageAssumptions.model_validate(
                trusted_context.sqs_usage_assumptions
            )
        except (TypeError, ValueError):
            return False
        if (
            assumptions.monthly_fair_queue_request_units.maximum > 0
            or assumptions.monthly_cross_region_transfer_gb.maximum > 0
            or assumptions.monthly_internet_egress_gb.maximum > 0
        ):
            return False
        expected = {
            "Amazon SQS Standard requests": (assumptions.monthly_standard_request_units, "usage_assumptions.sqs.standard"),
            "Amazon SQS FIFO requests": (assumptions.monthly_fifo_request_units, "usage_assumptions.sqs.fifo"),
        }
        active = {name: value for name, value in expected.items() if value[0].maximum > 0}
        actual = {line.get("description"): line for line in sqs_lines}
        if set(actual) != set(active):
            return False
        for name in ("Amazon SQS FIFO requests", "Amazon SQS Standard requests"):
            if name not in active:
                continue
            usage, address = active[name]
            line = actual[name]
            if (
                line.get("quantity") != usage.minimum
                or line.get("quantity_max") != usage.maximum
                or line.get("low_cost_quantity") != usage.minimum
                or line.get("address") != address
                or line.get("unit") != "Requests"
            ):
                return False
    serverless_lines = [
        line for line in lines
        if line.get("resource_type") in {"aws_lambda_function", "aws_apigatewayv2_api"}
    ]
    if serverless_lines:
        if trusted_context.serverless_usage_assumptions is None:
            return False
        try:
            assumptions = ServerlessPricingUsageAssumptions.model_validate(
                trusted_context.serverless_usage_assumptions
            )
        except (TypeError, ValueError):
            return False
        expected: dict[tuple[str, str], tuple[int, int, str]] = {}
        for address, usage in assumptions.lambda_functions.items():
            expected[(address, "AWS Lambda invocations")] = (
                usage.monthly_invocations.minimum, usage.monthly_invocations.maximum, "Requests"
            )
            expected[(address, "AWS Lambda billed duration at declared average and memory")] = (
                usage.monthly_invocations.minimum, usage.monthly_invocations.maximum,
                "Invocations × GB-seconds per invocation"
            )
            expected[(address, "AWS Lambda internet data transfer out")] = (
                usage.monthly_internet_egress_gb.minimum,
                usage.monthly_internet_egress_gb.maximum, "GB"
            )
            expected[(address, "Amazon CloudWatch Logs ingestion")] = (
                usage.monthly_cloudwatch_log_ingestion_gb.minimum,
                usage.monthly_cloudwatch_log_ingestion_gb.maximum, "GB"
            )
            expected[(address, "Amazon CloudWatch Logs storage")] = (
                usage.monthly_log_storage_gb_month.minimum,
                usage.monthly_log_storage_gb_month.maximum, "GB-Mo"
            )
        for address, usage in assumptions.http_apis.items():
            expected[(address, "Amazon API Gateway HTTP API requests")] = (
                usage.monthly_requests.minimum, usage.monthly_requests.maximum, "Requests"
            )
            expected[(address, "AWS internet data transfer out")] = (
                usage.monthly_internet_egress_gb.minimum,
                usage.monthly_internet_egress_gb.maximum, "GB"
            )
        actual = {(line.get("address"), line.get("description")): line for line in serverless_lines}
        if set(actual) != set(expected):
            return False
        for key, (quantity, quantity_max, unit) in expected.items():
            line = actual[key]
            if (
                line.get("quantity") != quantity
                or line.get("quantity_max") != quantity_max
                or line.get("unit") != unit
            ):
                return False
    expected_within_budget = (
        None
        if trusted_context.monthly_budget_minor is None
        else high <= trusted_context.monthly_budget_minor
    )
    return document.get("within_budget") is expected_within_budget


def _validate_aurora_cluster(
    values: dict[str, Any], change: dict[str, Any] | None
) -> tuple[str, str] | None:
    if change is None or not isinstance(change.get("change"), dict):
        return "aurora_plan_change_metadata_missing", "The Aurora cluster lacks final pricing metadata."
    plan_change = change["change"]
    after, unknown = plan_change.get("after"), plan_change.get("after_unknown")
    required = (
        "engine", "engine_mode", "storage_type", "manage_master_user_password",
        "storage_encrypted", "backup_retention_period", "serverlessv2_scaling_configuration",
        "engine_lifecycle_support", "enable_http_endpoint", "kms_key_id",
        "master_user_secret_kms_key_id", "global_cluster_identifier",
        "enabled_cloudwatch_logs_exports",
    )
    if (
        not isinstance(after, dict)
        or not isinstance(unknown, dict)
        or not _valid_unknown_tree(unknown)
        or any(key not in values or key not in after or values[key] != after[key] for key in required)
        or any(_path_contains_unknown(unknown, (key,)) for key in required)
    ):
        return "aurora_cost_driver_unknown", "The Aurora plan has missing or unknown price-driving settings."
    scaling = values.get("serverlessv2_scaling_configuration")
    try:
        min_capacity = Decimal(str(scaling[0].get("min_capacity"))) if isinstance(scaling, list) and scaling and isinstance(scaling[0], dict) else None
        max_capacity = Decimal(str(scaling[0].get("max_capacity"))) if isinstance(scaling, list) and scaling and isinstance(scaling[0], dict) else None
    except (InvalidOperation, TypeError, ValueError):
        return "aurora_configuration_unpriced", "Only the private, encrypted Aurora PostgreSQL Serverless v2 Standard shape is priced."
    if (
        values.get("engine") != "aurora-postgresql"
        or values.get("engine_mode") != "provisioned"
        or values.get("storage_type") != "aurora"
        or values.get("manage_master_user_password") is not True
        or values.get("storage_encrypted") is not True
        or values.get("engine_lifecycle_support") != "open-source-rds-extended-support-disabled"
        or values.get("enable_http_endpoint") is not False
        or values.get("kms_key_id") is not None
        or values.get("master_user_secret_kms_key_id") is not None
        or values.get("global_cluster_identifier") is not None
        or values.get("enabled_cloudwatch_logs_exports") not in ([], None)
        or not isinstance(scaling, list)
        or len(scaling) != 1
        or not isinstance(scaling[0], dict)
        or min_capacity != Decimal("0.5")
        or max_capacity != Decimal(2)
        or scaling[0].get("seconds_until_auto_pause") is not None
    ):
        return "aurora_configuration_unpriced", "Only the private, encrypted Aurora PostgreSQL Serverless v2 Standard shape is priced."
    return None


def _validate_aurora_instance(
    values: dict[str, Any], change: dict[str, Any] | None
) -> tuple[str, str] | None:
    if change is None or not isinstance(change.get("change"), dict):
        return "aurora_plan_change_metadata_missing", "The Aurora writer lacks final pricing metadata."
    plan_change = change["change"]
    after, unknown = plan_change.get("after"), plan_change.get("after_unknown")
    required = (
        "engine", "instance_class", "publicly_accessible", "monitoring_interval",
        "performance_insights_enabled",
    )
    if (
        not isinstance(after, dict)
        or not isinstance(unknown, dict)
        or not _valid_unknown_tree(unknown)
        or any(key not in values or key not in after or values[key] != after[key] for key in required)
        or any(_path_contains_unknown(unknown, (key,)) for key in required)
    ):
        return "aurora_cost_driver_unknown", "The Aurora writer plan has missing or unknown price-driving settings."
    if (
        values.get("engine") != "aurora-postgresql"
        or values.get("instance_class") != "db.serverless"
        or values.get("publicly_accessible") is not False
        or values.get("monitoring_interval") not in (0, None)
        or values.get("performance_insights_enabled") is not False
    ):
        return "aurora_instance_shape_unpriced", "Only one private Serverless v2 writer without paid monitoring add-ons is priced."
    return None


def _aurora_cost_lines(
    *,
    cluster_address: str,
    region: str,
    cluster_values: dict[str, Any],
    usage: RdsPricingUsageAssumptions,
    catalog: AwsPriceListCatalog,
) -> list[PlanCostLine]:
    capacity_rate = catalog.aurora_serverless_v2_rate(region)
    storage_rate = catalog.aurora_standard_storage_rate(region)
    io_rate = catalog.aurora_standard_io_rate(region)
    backup_rate = catalog.aurora_backup_overage_rate(region)
    secret_storage_rate = catalog.aurora_secret_storage_rate(region)
    secret_api_rate = catalog.aurora_secret_api_request_rate(region)
    scaling = cluster_values["serverlessv2_scaling_configuration"][0]
    quantities = (
        (
            "Aurora PostgreSQL Serverless v2 ACU-hours",
            "ACU-Hr",
            int(Decimal(str(scaling["min_capacity"])) * 730),
            int(Decimal(str(scaling["max_capacity"])) * 730),
            Decimal(capacity_rate.unit_price_usd),
            capacity_rate,
        ),
        (
            "Aurora Standard storage",
            "GB-Mo",
            usage.aurora_monthly_storage_gb_month.minimum,
            usage.aurora_monthly_storage_gb_month.maximum,
            Decimal(storage_rate.unit_price_usd),
            storage_rate,
        ),
        (
            "Aurora Standard I/O requests",
            "IOs",
            usage.aurora_monthly_io_requests.minimum,
            usage.aurora_monthly_io_requests.maximum,
            Decimal(io_rate.unit_price_usd),
            io_rate,
        ),
        (
            "Aurora billable backup storage overage",
            "GB-Mo",
            usage.aurora_monthly_backup_overage_gb_month.minimum,
            usage.aurora_monthly_backup_overage_gb_month.maximum,
            Decimal(backup_rate.unit_price_usd),
            backup_rate,
        ),
        (
            "AWS Secrets Manager secret storage for the RDS-managed credential",
            "Secrets",
            1,
            1,
            Decimal(secret_storage_rate.unit_price_usd),
            secret_storage_rate,
        ),
        (
            "AWS Secrets Manager API requests for credential reads and rotation",
            "API Requests",
            usage.aurora_monthly_secret_api_requests.minimum,
            usage.aurora_monthly_secret_api_requests.maximum,
            Decimal(secret_api_rate.unit_price_usd),
            secret_api_rate,
        ),
    )
    result: list[PlanCostLine] = []
    for description, unit, quantity, quantity_max, unit_price, rate in quantities:
        result.append(PlanCostLine(
            address=cluster_address,
            resource_type="aws_rds_cluster",
            description=description,
            quantity=quantity,
            quantity_max=quantity_max,
            unit=unit,
            unit_price_usd=format(unit_price, "f"),
            monthly_cost_minor=int(
                (unit_price * quantity * 100).quantize(Decimal(1), rounding=ROUND_FLOOR)
            ),
            monthly_cost_max_minor=int(
                (unit_price * quantity_max * 100).quantize(Decimal(1), rounding=ROUND_CEILING)
            ),
            unit_price_low_usd=format(unit_price, "f"),
            low_cost_quantity=quantity,
            catalog_sku=rate.sku,
            catalog_product_sha256=rate.product_digest,
            catalog_published_at=rate.published_at,
            catalog_effective_at=rate.effective_at,
        ))
    return result


def _validate_rds_instance(
    values: dict[str, Any], change: dict[str, Any] | None
) -> tuple[str, str] | None:
    if change is None or not isinstance(change.get("change"), dict):
        return "rds_plan_change_metadata_missing", "The RDS plan lacks resource-level pricing metadata."
    change_document = change["change"]
    after = change_document.get("after")
    unknown = change_document.get("after_unknown")
    required = (
        "engine", "instance_class", "storage_type", "allocated_storage", "multi_az",
        "publicly_accessible", "backup_retention_period", "engine_lifecycle_support",
        "performance_insights_enabled", "monitoring_interval",
    )
    if (
        not isinstance(after, dict)
        or not isinstance(unknown, dict)
        or not _valid_unknown_tree(unknown)
        or any(key not in values or key not in after or values[key] != after[key] for key in required)
    ):
        return "rds_configuration_unknown", "The RDS plan lacks known final pricing and safety values."
    optional_cost_fields = (
        "max_allocated_storage", "iops", "storage_throughput", "kms_key_id",
        "enabled_cloudwatch_logs_exports", "replicate_source_db", "license_model",
    )
    if any(
        key in values and key in after and values[key] != after[key]
        for key in optional_cost_fields
    ):
        return "rds_plan_final_values_mismatch", "RDS pricing values do not match the final planned resource."
    cost_drivers = required + optional_cost_fields
    if any(_path_contains_unknown(unknown, (key,)) for key in cost_drivers):
        return "rds_cost_driver_unknown", "A price-driving or surcharge setting is unknown in this plan."
    if values.get("engine") != "mysql":
        return "rds_engine_unpriced", "Only RDS for MySQL has a verified price mapping in this release."
    instance_class = values.get("instance_class")
    if not isinstance(instance_class, str) or not re.fullmatch(
        r"db\.(?:m|r)[0-9]+[a-z]?\.[a-z0-9]+", instance_class
    ):
        return "rds_instance_class_unpriced", "Only non-burstable RDS M and R classes are priced in this release."
    if values.get("storage_type") != "gp3":
        return "rds_storage_type_unpriced", "Only RDS GP3 storage is priced in this release."
    if values.get("multi_az") is not False or values.get("publicly_accessible") is not False:
        return "rds_deployment_unpriced", "Only private Single-AZ RDS instances are priced in this release."
    if values.get("engine_lifecycle_support") != "open-source-rds-extended-support-disabled":
        return "rds_extended_support_unpriced", "RDS extended support must be explicitly disabled for this estimate."
    if values.get("performance_insights_enabled") is not False or values.get("monitoring_interval") != 0:
        return "rds_monitoring_unpriced", "RDS Performance Insights and Enhanced Monitoring are not priced."
    if values.get("enabled_cloudwatch_logs_exports") not in (None, []):
        return "rds_logs_unpriced", "RDS CloudWatch log exports have unpriced ingestion and retention costs."
    if values.get("kms_key_id") not in (None, ""):
        return "rds_customer_kms_unpriced", "Customer-managed RDS KMS keys are not priced in this estimate."
    if values.get("license_model") not in (None, "general-public-license"):
        return "rds_license_unpriced", "Only the RDS MySQL license model is priced in this release."
    if values.get("max_allocated_storage") not in (None, 0):
        return "rds_storage_autoscaling_unpriced", "RDS storage autoscaling is not priced in this release."
    if values.get("iops") not in (None, 0, 3000) or values.get("storage_throughput") not in (None, 0, 125):
        return "rds_storage_performance_unpriced", "Custom RDS GP3 IOPS or throughput is not priced."
    size = values.get("allocated_storage")
    if isinstance(size, bool) or not isinstance(size, int) or not 20 <= size <= 65_536:
        return "rds_storage_size_unknown", "RDS GP3 allocated storage is missing or unsupported."
    retention = values.get("backup_retention_period")
    if isinstance(retention, bool) or not isinstance(retention, int) or not 0 <= retention <= 35:
        return "rds_backup_retention_unknown", "RDS backup retention is missing or unsupported."
    return None


def _validate_lambda_function(
    values: dict[str, Any], change: dict[str, Any] | None
) -> tuple[str, str] | None:
    if change is None or not isinstance(change.get("change"), dict):
        return "lambda_plan_change_metadata_missing", "The Lambda plan lacks resource-level pricing metadata."
    change_doc = change["change"]
    after = change_doc.get("after")
    unknown = change_doc.get("after_unknown")
    required = (
        "function_name", "package_type", "architectures", "memory_size", "ephemeral_storage",
        "timeout", "snap_start", "vpc_config", "reserved_concurrent_executions",
        "logging_config",
    )
    if (
        not isinstance(after, dict)
        or not isinstance(unknown, dict)
        or not _valid_unknown_tree(unknown)
        or any(key not in values or key not in after or values[key] != after[key] for key in required)
    ):
        return "lambda_configuration_unknown", "The Lambda plan lacks known final pricing and networking values."
    if any(_path_contains_unknown(unknown, (key,)) for key in required):
        return "lambda_cost_driver_unknown", "A Lambda pricing or network setting is unknown in the plan."
    if values.get("package_type") != "Zip":
        return "lambda_artifact_type_unpriced", "Only ZIP packaged Lambda functions are priced in this release."
    architectures = values.get("architectures")
    if not isinstance(architectures, list) or len(architectures) != 1 or architectures[0] not in {"x86_64", "arm64"}:
        return "lambda_architecture_unpriced", "Only one x86_64 or arm64 Lambda architecture is priced."
    memory = values.get("memory_size")
    if isinstance(memory, bool) or not isinstance(memory, int) or not 128 <= memory <= 10_240:
        return "lambda_memory_unpriced", "Lambda memory must be explicitly bounded from 128 to 10,240 MB."
    ephemeral = values.get("ephemeral_storage")
    size = ephemeral.get("size") if isinstance(ephemeral, dict) else None
    if isinstance(size, bool) or size != 512:
        return "lambda_ephemeral_storage_unpriced", "Only the default 512 MB Lambda ephemeral storage is priced."
    if values.get("snap_start") not in (None, {"apply_on": "None"}):
        return "lambda_snap_start_unpriced", "Lambda SnapStart lifecycle storage and restore charges are not priced."
    vpc = values.get("vpc_config")
    if isinstance(vpc, list) and vpc:
        vpc = vpc[0]
    if isinstance(vpc, dict) and (vpc.get("subnet_ids") or vpc.get("security_group_ids")):
        return "lambda_vpc_transfer_unpriced", "VPC Lambda networking can incur unmodeled NAT and transfer charges."
    if values.get("reserved_concurrent_executions") not in (None, -1):
        return "lambda_reserved_concurrency_unpriced", "Reserved concurrency is outside this bounded Lambda price model."
    timeout = values.get("timeout")
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 900:
        return "lambda_timeout_unknown", "Lambda timeout must be known and no greater than 900 seconds."
    if _lambda_log_group_name(values) is None:
        return "lambda_logging_configuration_unknown", "The Lambda log group cannot be determined from its final logging configuration."
    return None


def _lambda_log_group_name(values: dict[str, Any]) -> str | None:
    function_name = values.get("function_name")
    if not isinstance(function_name, str) or not function_name:
        return None
    configuration = values.get("logging_config")
    if configuration in (None, []):
        return f"/aws/lambda/{function_name}"
    if isinstance(configuration, list) and len(configuration) == 1:
        configuration = configuration[0]
    if not isinstance(configuration, dict):
        return None
    custom_name = configuration.get("log_group")
    if custom_name in (None, ""):
        return f"/aws/lambda/{function_name}"
    return custom_name if isinstance(custom_name, str) and custom_name else None


def _batch_awslogs_group_name(
    properties: dict[str, Any], region: str
) -> tuple[str | None, str | None]:
    configuration = properties.get("logConfiguration")
    if (
        not isinstance(configuration, dict)
        or set(configuration) - {"logDriver", "options", "secretOptions"}
        or configuration.get("logDriver") != "awslogs"
    ):
        return None, "driver"
    if configuration.get("secretOptions") not in (None, []):
        return None, "secret_options"
    options = configuration.get("options")
    if not isinstance(options, dict):
        return None, "options"
    supported_options = {
        "awslogs-group",
        "awslogs-region",
        "awslogs-stream-prefix",
        "awslogs-create-group",
        "awslogs-multiline-pattern",
        "awslogs-datetime-format",
    }
    group_name = options.get("awslogs-group")
    stream_prefix = options.get("awslogs-stream-prefix")
    configured_region = options.get("awslogs-region")
    create_group = options.get("awslogs-create-group")
    if (
        set(options) - supported_options
        or any(not isinstance(value, str) or not value for value in options.values())
        or not isinstance(group_name, str)
        or not group_name
        or not isinstance(stream_prefix, str)
        or not stream_prefix
        or configured_region not in (None, region)
        or create_group not in (None, "false")
    ):
        return None, "unsupported_options"
    return group_name, None


def _validate_lambda_log_group(
    values: dict[str, Any], change: dict[str, Any] | None, expected_name: str
) -> tuple[str, str] | None:
    return _validate_standard_cloudwatch_log_group(
        values, change, expected_name, code_prefix="lambda_log"
    )


def _private_ecr_image_reference(
    image: Any,
) -> tuple[tuple[str, str, str] | None, str | None]:
    """Return account, region, and repository for a digest-pinned private ECR image."""
    if not isinstance(image, str) or ".dkr.ecr." not in image:
        return None, None
    match = re.fullmatch(
        r"(?P<account>[0-9]{12})\.dkr\.ecr\.(?P<region>[a-z]{2}(?:-[a-z0-9]+)+-[0-9])"
        r"\.amazonaws\.com(?:\.cn)?/(?P<repository>[a-z0-9]+(?:[._/-][a-z0-9]+)*)"
        r"(?::[A-Za-z0-9_][A-Za-z0-9_.-]{0,127})?"
        r"@sha256:(?P<digest>[a-f0-9]{64})",
        image,
    )
    if match is None:
        return None, "invalid"
    return (
        match.group("account"),
        match.group("region"),
        match.group("repository"),
    ), None


def _validate_batch_log_group(
    values: dict[str, Any], change: dict[str, Any] | None, expected_name: str
) -> tuple[str, str] | None:
    return _validate_standard_cloudwatch_log_group(
        values, change, expected_name, code_prefix="batch_log"
    )


def _validate_standard_cloudwatch_log_group(
    values: dict[str, Any],
    change: dict[str, Any] | None,
    expected_name: str,
    *,
    code_prefix: str,
) -> tuple[str, str] | None:
    if change is None or not isinstance(change.get("change"), dict):
        return f"{code_prefix}_group_metadata_missing", "The CloudWatch log group lacks resource-level retention metadata."
    change_doc = change["change"]
    after = change_doc.get("after")
    unknown = change_doc.get("after_unknown")
    required = ("name", "retention_in_days", "log_group_class", "kms_key_id")
    if (
        not isinstance(after, dict)
        or not isinstance(unknown, dict)
        or not _valid_unknown_tree(unknown)
        or any(key not in values or key not in after or values[key] != after[key] for key in required)
        or any(_path_contains_unknown(unknown, (key,)) for key in required)
    ):
        return f"{code_prefix}_group_unknown", "The CloudWatch log group lacks known retention, class, or encryption values."
    if values.get("name") != expected_name:
        return f"{code_prefix}_group_mismatch", "The CloudWatch log group does not match the workload logging destination."
    retention = values.get("retention_in_days")
    allowed_retention = {
        1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400,
        545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653,
    }
    if isinstance(retention, bool) or retention not in allowed_retention:
        return f"{code_prefix}_retention_unbounded", "CloudWatch log retention must be an explicit supported expiration period."
    if values.get("log_group_class") != "STANDARD":
        return f"{code_prefix}_class_unpriced", "Only Standard CloudWatch log groups are priced in this release."
    if values.get("kms_key_id") not in (None, ""):
        return f"{code_prefix}_kms_unpriced", "Customer-managed CloudWatch log encryption keys are not priced."
    return None


def _validate_http_api(
    values: dict[str, Any], change: dict[str, Any] | None
) -> tuple[str, str] | None:
    if change is None or not isinstance(change.get("change"), dict):
        return "http_api_plan_change_metadata_missing", "The HTTP API plan lacks resource-level pricing metadata."
    change_doc = change["change"]
    after = change_doc.get("after")
    unknown = change_doc.get("after_unknown")
    required = ("protocol_type", "disable_execute_api_endpoint")
    if (
        not isinstance(after, dict)
        or not isinstance(unknown, dict)
        or not _valid_unknown_tree(unknown)
        or any(key not in values or key not in after or values[key] != after[key] for key in required)
        or any(_path_contains_unknown(unknown, (key,)) for key in required)
    ):
        return "http_api_configuration_unknown", "The HTTP API plan lacks known final protocol values."
    if values.get("protocol_type") != "HTTP":
        return "http_api_protocol_unpriced", "Only API Gateway HTTP APIs have a verified request price."
    return None


def _validate_http_api_stage(
    values: dict[str, Any], change: dict[str, Any] | None
) -> tuple[str, str] | None:
    if change is None or not isinstance(change.get("change"), dict):
        return "http_api_stage_metadata_missing", "The HTTP API stage lacks resource-level cost metadata."
    change_doc = change["change"]
    after = change_doc.get("after")
    unknown = change_doc.get("after_unknown")
    cost_drivers = ("access_log_settings", "default_route_settings", "route_settings")
    if (
        not isinstance(after, dict)
        or not isinstance(unknown, dict)
        or not _valid_unknown_tree(unknown)
        or any(key not in values or key not in after or values[key] != after[key] for key in cost_drivers)
        or any(_path_contains_unknown(unknown, (key,)) for key in cost_drivers)
    ):
        return "http_api_stage_unknown", "The HTTP API stage has unknown log or metrics settings."
    access_logs = values.get("access_log_settings")
    if access_logs not in (None, {}, []):
        return "http_api_access_logs_unpriced", "API access logs can incur CloudWatch ingestion and retention charges."
    default_settings = values.get("default_route_settings")
    if isinstance(default_settings, dict) and default_settings.get("detailed_metrics_enabled") is True:
        return "http_api_metrics_unpriced", "Detailed API metrics can incur CloudWatch charges."
    route_settings = values.get("route_settings")
    if isinstance(route_settings, list) and any(
        isinstance(item, dict) and item.get("detailed_metrics_enabled") is True
        for item in route_settings
    ):
        return "http_api_metrics_unpriced", "Detailed API metrics can incur CloudWatch charges."
    return None


def _validate_http_api_integration(
    values: dict[str, Any], change: dict[str, Any] | None
) -> tuple[str, str] | None:
    if change is None or not isinstance(change.get("change"), dict):
        return "http_api_integration_metadata_missing", "The HTTP API integration lacks resource-level cost metadata."
    change_doc = change["change"]
    after = change_doc.get("after")
    unknown = change_doc.get("after_unknown")
    cost_drivers = ("connection_type", "connection_id")
    if (
        not isinstance(after, dict)
        or not isinstance(unknown, dict)
        or not _valid_unknown_tree(unknown)
        or any(key not in values or key not in after or values[key] != after[key] for key in cost_drivers)
        or any(_path_contains_unknown(unknown, (key,)) for key in cost_drivers)
    ):
        return "http_api_integration_unknown", "The HTTP API integration has unknown connection settings."
    if values.get("connection_type") == "VPC_LINK" or values.get("connection_id"):
        return "http_api_vpc_link_unpriced", "API Gateway VPC links have separate hourly charges."
    return None


def _validate_gp3_volume(
    values: dict[str, Any], change: dict[str, Any] | None
) -> tuple[str, str] | None:
    if change is None or not isinstance(change.get("change"), dict):
        return "plan_change_metadata_missing", "The plan lacks resource-level pricing metadata."
    change_document = change["change"]
    after = change_document.get("after")
    if not isinstance(after, dict):
        return "plan_final_values_missing", "The plan lacks final EBS pricing values."
    cost_drivers = ("type", "size", "iops", "throughput", "kms_key_id")
    for key in cost_drivers:
        if key not in after or key not in values or after[key] != values[key]:
            return (
                "plan_final_values_mismatch",
                "Pricing values do not match the final planned resource.",
            )
    after_unknown = change_document.get("after_unknown")
    if not isinstance(after_unknown, dict) or not _valid_unknown_tree(after_unknown):
        return (
            "plan_unknown_structure_invalid",
            "The plan does not expose safe price-driving values.",
        )
    if any(key not in after_unknown for key in cost_drivers):
        return (
            "plan_unknown_structure_invalid",
            "The plan omits a price-driving unknown-value flag.",
        )
    for key in cost_drivers:
        if _path_contains_unknown(after_unknown, (key,)):
            return "cost_driver_unknown", "A storage price-driving setting is unknown in this plan."
    if values.get("type") != "gp3":
        return (
            "storage_type_unpriced",
            "Only EBS gp3 storage has a verified calculation in this release.",
        )
    size = values.get("size")
    if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= 65_536:
        return "storage_size_unknown", "The planned EBS storage size is missing or unsupported."
    if values.get("iops") != 3_000 or values.get("throughput") != 125:
        return (
            "storage_performance_unpriced",
            "Custom EBS IOPS or throughput is not priced in this release.",
        )
    if values.get("kms_key_id") not in (None, ""):
        return (
            "customer_kms_key_unpriced",
            "A customer-managed encryption key has separate unpriced costs.",
        )
    if not isinstance(values.get("encrypted"), bool):
        return "storage_encryption_unknown", "The planned storage encryption setting is unknown."
    return None


def _validate_sqs_queue(
    values: dict[str, Any], change: dict[str, Any] | None
) -> tuple[str, str] | None:
    if change is None or not isinstance(change.get("change"), dict):
        return "sqs_plan_change_metadata_missing", "The SQS plan lacks resource-level queue metadata."
    after = change["change"].get("after")
    unknown = change["change"].get("after_unknown")
    if not isinstance(after, dict) or not isinstance(unknown, dict) or not _valid_unknown_tree(unknown):
        return "sqs_configuration_unknown", "The planned SQS queue configuration is unknown."
    if unknown.get("fifo_queue") is True or not isinstance(after.get("fifo_queue"), bool):
        return "sqs_configuration_unknown", "The planned SQS queue type is unknown."
    if after.get("kms_master_key_id") not in (None, ""):
        return "sqs_kms_unpriced", "Customer-managed SQS encryption keys are not priced by this estimate."
    if unknown.get("kms_master_key_id") is True:
        return "sqs_configuration_unknown", "The planned SQS encryption configuration is unknown."
    if values.get("fifo_queue") != after.get("fifo_queue"):
        return "sqs_configuration_unknown", "The SQS queue type does not match the final planned resource."
    return None


def _dynamodb_pitr_enabled(values: dict[str, Any]) -> bool | None:
    raw = values.get("point_in_time_recovery")
    if raw in (None, [], {}):
        return False
    if isinstance(raw, dict):
        enabled = raw.get("enabled")
    elif isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], dict):
        enabled = raw[0].get("enabled")
    else:
        return None
    return enabled if isinstance(enabled, bool) else None


def _validate_dynamodb_table(
    values: dict[str, Any], change: dict[str, Any] | None
) -> tuple[str, str] | None:
    if change is None or not isinstance(change.get("change"), dict):
        return "dynamodb_plan_change_metadata_missing", "The DynamoDB plan lacks table-level cost metadata."
    change_doc = change["change"]
    after = change_doc.get("after")
    unknown = change_doc.get("after_unknown")
    required = (
        "billing_mode",
        "table_class",
        "global_secondary_index",
        "local_secondary_index",
        "replica",
        "point_in_time_recovery",
        "stream_enabled",
        "stream_view_type",
        "server_side_encryption",
    )
    if (
        not isinstance(after, dict)
        or not isinstance(unknown, dict)
        or not _valid_unknown_tree(unknown)
        or any(key not in values or key not in after or values[key] != after[key] for key in required)
        or any(_path_contains_unknown(unknown, (key,)) for key in required)
    ):
        return "dynamodb_configuration_unknown", "The DynamoDB plan lacks known final cost-driving settings."
    if values.get("billing_mode") != "PAY_PER_REQUEST":
        return "dynamodb_capacity_mode_unpriced", "Only DynamoDB on-demand capacity tables are priced."
    if values.get("table_class") != "STANDARD":
        return "dynamodb_table_class_unpriced", "Only DynamoDB Standard tables are priced."
    for key, code, message in (
        (
            "global_secondary_index",
            "dynamodb_global_secondary_index_unpriced",
            "DynamoDB global secondary index usage is not included in this estimate.",
        ),
        (
            "local_secondary_index",
            "dynamodb_local_secondary_index_unpriced",
            "DynamoDB local secondary index usage is not included in this estimate.",
        ),
        (
            "replica",
            "dynamodb_global_table_unpriced",
            "DynamoDB global table replicas are not included in this estimate.",
        ),
    ):
        if values.get(key) not in (None, [], {}):
            return code, message
    if values.get("stream_enabled") is True or values.get("stream_view_type") not in (None, ""):
        return "dynamodb_stream_unpriced", "DynamoDB Streams charges are not included in this estimate."
    pitr_enabled = _dynamodb_pitr_enabled(values)
    if pitr_enabled is None:
        return "dynamodb_pitr_configuration_unknown", "The DynamoDB PITR setting is not known."
    encryption = values.get("server_side_encryption")
    if encryption not in (None, [], {}):
        if isinstance(encryption, list) and len(encryption) == 1:
            encryption = encryption[0]
        if not isinstance(encryption, dict) or encryption.get("enabled") is not True:
            return "dynamodb_encryption_configuration_unknown", "DynamoDB server-side encryption settings are not supported."
        if encryption.get("kms_key_arn") not in (None, "") or encryption.get("kms_key_id") not in (None, ""):
            return "dynamodb_customer_kms_unpriced", "Customer-managed DynamoDB encryption keys are not priced."
    return None


def _validate_s3_bucket(
    values: dict[str, Any], change: dict[str, Any] | None
) -> tuple[str, str] | None:
    if change is None or not isinstance(change.get("change"), dict):
        return "plan_change_metadata_missing", "The plan lacks S3 bucket pricing metadata."
    change_document = change["change"]
    after = change_document.get("after")
    unknown = change_document.get("after_unknown")
    if not isinstance(after, dict) or not isinstance(unknown, dict):
        return "plan_final_values_missing", "The plan lacks final S3 bucket pricing values."
    if not _valid_unknown_tree(unknown):
        return "plan_unknown_structure_invalid", "The plan has an invalid S3 unknown-value shape."
    if values.get("object_lock_enabled") is not False or after.get("object_lock_enabled") is not False:
        return (
            "s3_object_lock_unpriced",
            "S3 Object Lock retention and object versions are not included in this estimate.",
        )
    if _path_contains_unknown(unknown, ("object_lock_enabled",)):
        return "s3_configuration_unknown", "The planned S3 Object Lock setting is unknown."
    if values.get("object_lock_configuration") not in (None, {}) or after.get(
        "object_lock_configuration"
    ) not in (None, {}):
        return (
            "s3_object_lock_unpriced",
            "S3 Object Lock retention and object versions are not included in this estimate.",
        )
    if values != after:
        return "plan_final_values_mismatch", "S3 pricing values do not match the final planned bucket."
    return None


def _parse_gp3_product(raw_product: Any, region: str) -> CatalogRate:
    if not isinstance(raw_product, str):
        raise PlanPricingError("AWS regional price result is malformed")
    try:
        product_doc = json.loads(raw_product)
    except (json.JSONDecodeError, TypeError):
        raise PlanPricingError("AWS regional price result is malformed") from None
    if not isinstance(product_doc, dict):
        raise PlanPricingError("AWS regional price result is malformed")
    product = product_doc.get("product")
    if not isinstance(product, dict):
        raise PlanPricingError("AWS regional price result is malformed")
    attributes = product.get("attributes")
    if (
        product_doc.get("serviceCode") != "AmazonEC2"
        or not isinstance(attributes, dict)
        or product.get("productFamily") != "Storage"
        or attributes.get("regionCode") != region
        or attributes.get("volumeApiName") != "gp3"
    ):
        raise PlanPricingError("AWS regional price result did not match the requested product")
    sku = product.get("sku")
    if not isinstance(sku, str) or not sku:
        raise PlanPricingError("AWS regional price SKU is missing")
    terms = product_doc.get("terms")
    on_demand = terms.get("OnDemand") if isinstance(terms, dict) else None
    if not isinstance(on_demand, dict) or len(on_demand) != 1:
        raise PlanPricingError("AWS On-Demand price term is missing or ambiguous")
    term = next(iter(on_demand.values()))
    if not isinstance(term, dict):
        raise PlanPricingError("AWS On-Demand price term is malformed")
    if term.get("sku") != sku:
        raise PlanPricingError("AWS On-Demand price term does not match the product SKU")
    dimensions = term.get("priceDimensions")
    if not isinstance(dimensions, dict) or len(dimensions) != 1:
        raise PlanPricingError("AWS price tiers are missing or ambiguous")
    dimension = next(iter(dimensions.values()))
    if not isinstance(dimension, dict) or dimension.get("unit") != "GB-Mo":
        raise PlanPricingError("AWS storage price unit is unsupported")
    if dimension.get("beginRange") not in ("0", 0) or dimension.get("endRange") != "Inf":
        raise PlanPricingError("AWS tiered storage pricing is unsupported")
    prices = dimension.get("pricePerUnit")
    raw_price = prices.get("USD") if isinstance(prices, dict) else None
    try:
        price = Decimal(str(raw_price))
    except (InvalidOperation, ValueError):
        raise PlanPricingError("AWS USD unit price is invalid") from None
    if not price.is_finite() or price <= 0:
        raise PlanPricingError("AWS USD unit price is invalid")
    effective_at = term.get("effectiveDate")
    published_at = product_doc.get("publicationDate")
    if not isinstance(effective_at, str) or not effective_at:
        raise PlanPricingError("AWS price effective timestamp is missing")
    if not isinstance(published_at, str) or not published_at:
        raise PlanPricingError("AWS price catalog publication timestamp is missing")
    try:
        effective_datetime = datetime.fromisoformat(effective_at)
        published_datetime = datetime.fromisoformat(published_at)
    except ValueError:
        raise PlanPricingError("AWS price catalog timestamp is malformed") from None
    if effective_datetime.tzinfo is None or published_datetime.tzinfo is None:
        raise PlanPricingError("AWS price catalog timestamp is not timezone-aware")
    effective_at = effective_datetime.astimezone(UTC).isoformat().replace("+00:00", "Z")
    published_at = published_datetime.astimezone(UTC).isoformat().replace("+00:00", "Z")
    digest = _canonical_digest(product_doc)
    return CatalogRate(sku, "GB-Mo", format(price, "f"), effective_at, published_at, digest)


def _parse_regional_product(
    raw_product: Any,
    service_code: str,
    expected_attributes: dict[str, str],
    expected_unit: str,
) -> CatalogRate:
    if not isinstance(raw_product, str):
        raise PlanPricingError("AWS regional price result is malformed")
    try:
        product_doc = json.loads(raw_product)
    except (json.JSONDecodeError, TypeError):
        raise PlanPricingError("AWS regional price result is malformed") from None
    if not isinstance(product_doc, dict):
        raise PlanPricingError("AWS regional price result is malformed")
    product = product_doc.get("product")
    attributes = product.get("attributes") if isinstance(product, dict) else None
    if (
        product_doc.get("serviceCode") != service_code
        or not isinstance(product, dict)
        or product.get("productFamily") != expected_attributes.get("productFamily")
        or not isinstance(attributes, dict)
        or any(attributes.get(key) != value for key, value in expected_attributes.items()
               if key != "productFamily")
    ):
        raise PlanPricingError("AWS regional price result did not match the requested product")
    sku = product.get("sku")
    if not isinstance(sku, str) or not sku:
        raise PlanPricingError("AWS regional price SKU is missing")
    terms = product_doc.get("terms")
    on_demand = terms.get("OnDemand") if isinstance(terms, dict) else None
    if not isinstance(on_demand, dict) or len(on_demand) != 1:
        raise PlanPricingError("AWS On-Demand price term is missing or ambiguous")
    term = next(iter(on_demand.values()))
    if not isinstance(term, dict) or term.get("sku") != sku:
        raise PlanPricingError("AWS On-Demand price term does not match the product SKU")
    dimensions = term.get("priceDimensions")
    if not isinstance(dimensions, dict) or not dimensions:
        raise PlanPricingError("AWS price dimensions are missing")
    prices: list[Decimal] = []
    tier_ranges: list[tuple[Decimal, Decimal]] = []
    for dimension in dimensions.values():
        if not isinstance(dimension, dict) or dimension.get("unit") != expected_unit:
            raise PlanPricingError("AWS price unit is unsupported")
        price_per_unit = dimension.get("pricePerUnit")
        raw_price = price_per_unit.get("USD") if isinstance(price_per_unit, dict) else None
        try:
            price = Decimal(str(raw_price))
        except (InvalidOperation, ValueError):
            raise PlanPricingError("AWS USD unit price is invalid") from None
        if not price.is_finite() or price < 0:
            raise PlanPricingError("AWS USD unit price is invalid")
        begin, end = dimension.get("beginRange"), dimension.get("endRange")
        if not isinstance(begin, str) or not isinstance(end, str):
            raise PlanPricingError("AWS price tier bounds are invalid")
        try:
            lower = Decimal(begin)
            upper = Decimal("Infinity") if end == "Inf" else Decimal(end)
        except InvalidOperation:
            raise PlanPricingError("AWS price tier bounds are invalid") from None
        if not lower.is_finite() or lower < 0 or (not upper.is_finite() and end != "Inf"):
            raise PlanPricingError("AWS price tier bounds are invalid")
        if upper.is_finite() and upper <= lower:
            raise PlanPricingError("AWS price tier bounds are invalid")
        prices.append(price)
        tier_ranges.append((lower, upper))
    if service_code != "AWSDataTransfer":
        ordered_ranges = sorted(tier_ranges)
        if ordered_ranges[0][0] != 0 or any(
            left[1] != right[0]
            for left, right in pairwise(ordered_ranges)
        ) or ordered_ranges[-1][1] != Decimal("Infinity"):
            raise PlanPricingError("AWS price tiers do not cover the full usage range")
    # Usage tiers and account-wide free allowances can depend on traffic outside
    # this proposal. Applying the highest published unit rate to all declared
    # usage avoids assuming that a shared allowance or cheaper tier is available.
    price = max(prices)
    effective_at = term.get("effectiveDate")
    published_at = product_doc.get("publicationDate")
    if not isinstance(effective_at, str) or not isinstance(published_at, str):
        raise PlanPricingError("AWS price timestamps are missing")
    try:
        effective_datetime = datetime.fromisoformat(effective_at)
        published_datetime = datetime.fromisoformat(published_at)
    except ValueError:
        raise PlanPricingError("AWS price catalog timestamp is malformed") from None
    if effective_datetime.tzinfo is None or published_datetime.tzinfo is None:
        raise PlanPricingError("AWS price catalog timestamp is not timezone-aware")
    effective_at = effective_datetime.astimezone(UTC).isoformat().replace("+00:00", "Z")
    published_at = published_datetime.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return CatalogRate(
        sku,
        expected_unit,
        format(price, "f"),
        effective_at,
        published_at,
        _canonical_digest(product_doc),
        low_unit_price_usd=format(min(prices), "f"),
    )


def _plan_region_matches(document: dict[str, Any], region: str) -> bool:
    if not isinstance(document, dict):
        return False
    config = document.get("configuration")
    providers = config.get("provider_config") if isinstance(config, dict) else None
    aws = providers.get("aws") if isinstance(providers, dict) else None
    expressions = aws.get("expressions") if isinstance(aws, dict) else None
    region_expression = expressions.get("region") if isinstance(expressions, dict) else None
    if not isinstance(region_expression, dict):
        return False
    if region_expression.get("constant_value") == region:
        return True
    variables = document.get("variables")
    region_variable = variables.get("region") if isinstance(variables, dict) else None
    return (
        region_expression.get("references") == ["var.region"]
        and isinstance(region_variable, dict)
        and region_variable.get("value") == region
    )


def _planned_managed_resources(document: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    planned_values = document.get("planned_values") if isinstance(document, dict) else None
    root = planned_values.get("root_module") if isinstance(planned_values, dict) else None
    if not isinstance(root, dict):
        raise PlanPricingError("plan resource inventory is missing")
    resources: list[dict[str, Any]] = []
    modules = [root]
    while modules:
        module = modules.pop()
        module_resources = module.get("resources", [])
        child_modules = module.get("child_modules", [])
        if (
            not isinstance(module_resources, list)
            or not isinstance(child_modules, list)
            or any(not isinstance(item, dict) for item in module_resources)
            or any(not isinstance(item, dict) for item in child_modules)
        ):
            raise PlanPricingError("plan resource inventory is malformed")
        for item in module_resources:
            mode = item.get("mode", "managed")
            if mode == "managed":
                resources.append(item)
            elif mode != "data":
                raise PlanPricingError("planned resource mode is unsupported")
        modules.extend(child_modules)
        if len(resources) > 2_000:
            raise PlanPricingError("plan resource inventory exceeds its limit")
    result = []
    seen: set[str] = set()
    for item in resources:
        address, resource_type, values = item.get("address"), item.get("type"), item.get("values")
        if (
            not isinstance(address, str)
            or not address
            or not isinstance(resource_type, str)
            or not isinstance(values, dict)
        ):
            raise PlanPricingError("planned resource metadata is malformed")
        if address in seen:
            raise PlanPricingError("planned resource addresses are duplicated")
        seen.add(address)
        result.append({"address": address, "type": resource_type, "values": values})
    return tuple(sorted(result, key=lambda item: item["address"]))


def _changes_by_address(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    changes = document.get("resource_changes")
    if not isinstance(changes, list):
        raise PlanPricingError("resource change inventory is malformed")
    result: dict[str, dict[str, Any]] = {}
    for item in changes:
        if not isinstance(item, dict):
            raise PlanPricingError("resource change metadata is malformed")
        address = item.get("address")
        if not isinstance(address, str) or not address or address in result:
            raise PlanPricingError("resource change address is malformed or duplicated")
        result[address] = item
    return result


def _interface_endpoint_az_count(
    subnet_ids: Any,
    planned_subnets: list[dict[str, Any]],
    region: str,
) -> int | None:
    """Count AZs only when every endpoint subnet ID and AZ is known in-plan."""
    if (
        not isinstance(subnet_ids, list)
        or not 1 <= len(subnet_ids) <= 6
        or any(not isinstance(subnet_id, str) or not subnet_id for subnet_id in subnet_ids)
        or len(set(subnet_ids)) != len(subnet_ids)
    ):
        return None
    subnets_by_id: dict[str, list[dict[str, Any]]] = {}
    for subnet in planned_subnets:
        values = subnet["values"]
        subnet_id = values.get("id")
        if isinstance(subnet_id, str) and subnet_id:
            subnets_by_id.setdefault(subnet_id, []).append(subnet)
    az_names: set[str] = set()
    for subnet_id in subnet_ids:
        matches = subnets_by_id.get(subnet_id, [])
        if len(matches) != 1:
            return None
        az = matches[0]["values"].get("availability_zone")
        if (
            not isinstance(az, str)
            or re.fullmatch(re.escape(region) + r"[a-z]", az) is None
            or az in az_names
        ):
            return None
        az_names.add(az)
    return len(az_names)


def _supported_interface_endpoint_service(service_name: Any, region: str) -> bool:
    if not isinstance(service_name, str):
        return False
    return service_name in {
        f"com.amazonaws.{region}.ecr.api",
        f"com.amazonaws.{region}.ecr.dkr",
        f"com.amazonaws.{region}.logs",
    }


def _configured_attribute_references(
    document: dict[str, Any], resource_address: str, attribute: str
) -> tuple[str, ...]:
    configuration = document.get("configuration")
    root = configuration.get("root_module") if isinstance(configuration, dict) else None
    if not isinstance(root, dict):
        return ()
    modules = [(root, "")]
    while modules:
        module, module_prefix = modules.pop()
        resources = module.get("resources", [])
        module_calls = module.get("module_calls", {})
        if not isinstance(resources, list) or not isinstance(module_calls, dict):
            return ()
        for item in resources:
            if not isinstance(item, dict):
                continue
            local_address = item.get("address")
            if not isinstance(local_address, str):
                continue
            configured_address = (
                f"{module_prefix}{local_address}" if module_prefix else local_address
            )
            if _without_instance_keys(configured_address) != _without_instance_keys(
                resource_address
            ):
                continue
            expressions = item.get("expressions")
            expression = expressions.get(attribute) if isinstance(expressions, dict) else None
            references = expression.get("references") if isinstance(expression, dict) else None
            if not isinstance(references, list):
                return ()
            return tuple(
                f"{module_prefix}{value}" if module_prefix else value
                for value in references
                if isinstance(value, str)
            )
        for name, call in module_calls.items():
            child = call.get("module") if isinstance(call, dict) else None
            if not isinstance(name, str) or not isinstance(child, dict):
                return ()
            modules.append((child, f"{module_prefix}module.{name}."))
    return ()


def _reference_matches_resource(references: tuple[str, ...], address: str) -> bool:
    normalized_address = _without_instance_keys(address)
    return any(
        _without_instance_keys(reference) == normalized_address
        or _without_instance_keys(reference).startswith(f"{normalized_address}.")
        for reference in references
    )


def _without_instance_keys(address: str) -> str:
    """Normalize count/for_each instance selectors for config-to-plan matching."""
    return re.sub(r'\[(?:[0-9]+|"(?:\\.|[^"\\])*")\]', "", address)


def _classify_aws_transitions(
    resources: tuple[dict[str, Any], ...],
    changes: dict[str, dict[str, Any]],
) -> tuple[tuple[PlanTransition, ...], tuple[PlanPricingFinding, ...]]:
    """Prove every AWS managed plan change has an explicit final-state treatment."""
    planned_aws = {
        item["address"]: item["type"] for item in resources if item["type"].startswith("aws_")
    }
    transitions: list[PlanTransition] = []
    findings: list[PlanPricingFinding] = []
    seen_planned_changes: set[str] = set()
    for address, item in changes.items():
        mode = item.get("mode", "managed")
        if mode == "data":
            continue
        resource_type = item.get("type")
        if not isinstance(resource_type, str) or not resource_type.startswith("aws_"):
            continue
        if mode != "managed":
            findings.append(
                PlanPricingFinding(
                    "resource_transition_unknown",
                    address,
                    "The AWS resource mode has no safe transition classification.",
                )
            )
            continue
        change = item.get("change")
        actions = change.get("actions") if isinstance(change, dict) else None
        if (
            not isinstance(actions, list)
            or not actions
            or any(not isinstance(action, str) for action in actions)
        ):
            findings.append(
                PlanPricingFinding(
                    "resource_transition_unknown",
                    address,
                    "The AWS resource change has no safe transition classification.",
                )
            )
            continue
        action_tuple = tuple(actions)
        if action_tuple not in {
            ("no-op",),
            ("create",),
            ("update",),
            ("delete",),
            ("delete", "create"),
            ("create", "delete"),
        }:
            findings.append(
                PlanPricingFinding(
                    "resource_transition_unknown",
                    address,
                    "The AWS resource action is not supported by this pricing review.",
                )
            )
            continue
        if actions == ["delete"]:
            if address in planned_aws:
                findings.append(
                    PlanPricingFinding(
                        "resource_delete_final_state_mismatch",
                        address,
                        "A deleted AWS resource still appears in the final planned state.",
                    )
                )
                continue
            transitions.append(
                PlanTransition(
                    address,
                    resource_type,
                    action_tuple,
                    "REMOVED_FROM_POST_APPLY_STEADY_STATE",
                )
            )
            continue
        if address not in planned_aws:
            findings.append(
                PlanPricingFinding(
                    "resource_final_state_missing",
                    address,
                    "An AWS resource change is missing from the final planned state.",
                )
            )
            continue
        if planned_aws[address] != resource_type:
            findings.append(
                PlanPricingFinding(
                    "resource_transition_type_mismatch",
                    address,
                    "The AWS resource change does not match its final planned resource type.",
                )
            )
            continue
        seen_planned_changes.add(address)
        if "delete" in actions:
            transitions.append(
                PlanTransition(
                    address,
                    resource_type,
                    action_tuple,
                    "REPLACEMENT_TRANSITION_CHARGES_EXCLUDED",
                )
            )
    for address in planned_aws:
        if address not in seen_planned_changes:
            findings.append(
                PlanPricingFinding(
                    "resource_change_missing",
                    address,
                    "The final AWS resource has no matching Terraform change record.",
                )
            )
    return (
        tuple(sorted(transitions, key=lambda item: (item.address, item.actions))),
        tuple(sorted(findings, key=lambda item: (item.code, item.address or ""))),
    )


def _valid_unknown_tree(tree: dict[str, Any]) -> bool:
    for value in tree.values():
        if isinstance(value, bool):
            continue
        if isinstance(value, dict) and _valid_unknown_tree(value):
            continue
        if isinstance(value, list) and all(
            isinstance(item, bool) or (isinstance(item, dict) and _valid_unknown_tree(item))
            for item in value
        ):
            continue
        return False
    return True


def _path_contains_unknown(tree: dict[str, Any], path: tuple[str, ...]) -> bool:
    value: Any = tree
    for part in path:
        if not isinstance(value, dict) or part not in value:
            return False
        value = value[part]
    if value is True:
        return True
    if isinstance(value, dict):
        return any(_path_contains_unknown(value, (key,)) for key in value)
    if isinstance(value, list):
        return any(
            item is True
            or (
                isinstance(item, dict) and any(_path_contains_unknown(item, (key,)) for key in item)
            )
            for item in value
        )
    return False


def _evidence(
    status: PlanPricingStatus,
    region: str,
    currency: str,
    captured_at: str,
    budget: int | None,
    document: Any,
    lines: tuple[PlanCostLine, ...],
    findings: tuple[PlanPricingFinding, ...],
    *,
    within_budget: bool | None = None,
    proposal_declared_budget_minor: int | None = None,
    proposal_declared_currency: str | None = None,
    persisted_context_sha256: str,
    transitions: tuple[PlanTransition, ...] = (),
    usage_assumptions: dict[str, Any] | None = None,
    sqs_usage_assumptions: dict[str, Any] | None = None,
    rds_usage_assumptions: dict[str, Any] | None = None,
    serverless_usage_assumptions: dict[str, Any] | None = None,
    dynamodb_usage_assumptions: dict[str, Any] | None = None,
    vpc_usage_assumptions: dict[str, Any] | None = None,
    batch_usage_assumptions: dict[str, Any] | None = None,
    ecr_usage_assumptions: dict[str, Any] | None = None,
    ecs_express_usage_assumptions: dict[str, Any] | None = None,
) -> GeneratedPlanPricingEvidence:
    lines = tuple(sorted(lines, key=lambda item: item.address))
    transitions = tuple(sorted(transitions, key=lambda item: (item.address, item.actions)))
    findings = tuple(sorted(findings, key=lambda item: (item.code, item.address or "")))
    low = sum(item.monthly_cost_minor for item in lines)
    high = sum(
        item.monthly_cost_minor
        if item.monthly_cost_max_minor is None
        else item.monthly_cost_max_minor
        for item in lines
    )
    if status != PlanPricingStatus.COMPLETE:
        low = high = None
    if budget is not None and status == PlanPricingStatus.COMPLETE and within_budget is None:
        within_budget = high is not None and high <= budget
    plan_digest = _canonical_digest(document) if isinstance(document, (dict, list)) else "0" * 64
    pricing_context_digest = _pricing_context_digest(
        region, currency, budget, persisted_context_sha256, usage_assumptions,
        sqs_usage_assumptions, rds_usage_assumptions, serverless_usage_assumptions,
        dynamodb_usage_assumptions, vpc_usage_assumptions,
        batch_usage_assumptions, ecr_usage_assumptions,
        ecs_express_usage_assumptions,
    )
    payload = {
        "version": 11,
        "status": status.value,
        "region": region,
        "currency": currency,
        "captured_at": captured_at,
        "rate_type": "ON_DEMAND_PUBLIC_PRICE_LIST",
        "estimate_disclaimer": (
            "Post-apply steady-state estimate at public AWS On-Demand list prices for explicitly "
            "priced resources and known usage. Excludes transition-period charges, discounts, "
            "Free Tier, taxes and unmodeled usage; it is not a bill forecast or a spend cap."
        ),
        "freshness_max_age_seconds": int(MAX_PRICING_EVIDENCE_AGE.total_seconds()),
        "future_clock_skew_seconds": int(MAX_PRICING_EVIDENCE_FUTURE_SKEW.total_seconds()),
        "monthly_low_minor": low,
        "monthly_high_minor": high,
        "monthly_budget_minor": budget,
        "proposal_declared_budget_minor": proposal_declared_budget_minor,
        "proposal_declared_currency": proposal_declared_currency,
        "budget_source": "PERSISTED_CUSTOMER_CONTEXT",
        "persisted_context_sha256": persisted_context_sha256,
        "pricing_context_sha256": pricing_context_digest,
        "within_budget": within_budget,
        "plan_json_sha256": plan_digest,
        "usage_assumptions": usage_assumptions,
        "sqs_usage_assumptions": sqs_usage_assumptions,
        "rds_usage_assumptions": rds_usage_assumptions,
        "serverless_usage_assumptions": serverless_usage_assumptions,
        "dynamodb_usage_assumptions": dynamodb_usage_assumptions,
        "vpc_usage_assumptions": vpc_usage_assumptions,
        "batch_usage_assumptions": batch_usage_assumptions,
        "ecr_usage_assumptions": ecr_usage_assumptions,
        "ecs_express_usage_assumptions": ecs_express_usage_assumptions,
        "lines": [
            {
                "address": item.address,
                "resource_type": item.resource_type,
                "description": item.description,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_price_usd": item.unit_price_usd,
                "monthly_cost_minor": item.monthly_cost_minor,
                "catalog_sku": item.catalog_sku,
                "catalog_product_sha256": item.catalog_product_sha256,
                "catalog_published_at": item.catalog_published_at,
                "catalog_effective_at": item.catalog_effective_at,
                "quantity_max": item.quantity_max,
                "monthly_cost_max_minor": item.monthly_cost_max_minor,
                "unit_price_low_usd": item.unit_price_low_usd,
                "unit_price_low_source_url": item.unit_price_low_source_url,
                "low_cost_quantity": item.low_cost_quantity,
            }
            for item in lines
        ],
        "transitions": [
            {
                "address": item.address,
                "resource_type": item.resource_type,
                "actions": list(item.actions),
                "treatment": item.treatment,
            }
            for item in transitions
        ],
        "findings": [
            {"code": item.code, "address": item.address, "message": item.message}
            for item in findings
        ],
    }
    return GeneratedPlanPricingEvidence(
        status=status,
        region=region,
        currency=currency,
        captured_at=captured_at,
        rate_type="ON_DEMAND_PUBLIC_PRICE_LIST",
        monthly_low_minor=low,
        monthly_high_minor=high,
        monthly_budget_minor=budget,
        proposal_declared_budget_minor=proposal_declared_budget_minor,
        proposal_declared_currency=proposal_declared_currency,
        budget_source="PERSISTED_CUSTOMER_CONTEXT",
        persisted_context_sha256=persisted_context_sha256,
        pricing_context_sha256=pricing_context_digest,
        estimate_disclaimer=(
            "Post-apply steady-state estimate at public AWS On-Demand list prices for explicitly "
            "priced resources and known usage. Excludes transition-period charges, discounts, "
            "Free Tier, taxes and unmodeled usage; it is not a bill forecast or a spend cap."
        ),
        within_budget=within_budget,
        plan_json_sha256=plan_digest,
        usage_assumptions=usage_assumptions,
        sqs_usage_assumptions=sqs_usage_assumptions,
        rds_usage_assumptions=rds_usage_assumptions,
        serverless_usage_assumptions=serverless_usage_assumptions,
        dynamodb_usage_assumptions=dynamodb_usage_assumptions,
        vpc_usage_assumptions=vpc_usage_assumptions,
        batch_usage_assumptions=batch_usage_assumptions,
        ecr_usage_assumptions=ecr_usage_assumptions,
        ecs_express_usage_assumptions=ecs_express_usage_assumptions,
        lines=lines,
        transitions=transitions,
        findings=findings,
        evidence_sha256=_canonical_digest(payload),
    )


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _has_aurora_usage_assumptions(value: dict[str, Any]) -> bool:
    return any(
        key.startswith("aurora_") and item is not None
        for key, item in value.items()
    )


def _pricing_context_digest(
    region: str,
    currency: str,
    monthly_budget_minor: int | None,
    persisted_context_sha256: str,
    usage_assumptions: dict[str, Any] | None = None,
    sqs_usage_assumptions: dict[str, Any] | None = None,
    rds_usage_assumptions: dict[str, Any] | None = None,
    serverless_usage_assumptions: dict[str, Any] | None = None,
    dynamodb_usage_assumptions: dict[str, Any] | None = None,
    vpc_usage_assumptions: dict[str, Any] | None = None,
    batch_usage_assumptions: dict[str, Any] | None = None,
    ecr_usage_assumptions: dict[str, Any] | None = None,
    ecs_express_usage_assumptions: dict[str, Any] | None = None,
) -> str:
    payload = {
        "version": 9 if ecs_express_usage_assumptions is None else 10,
        "region": region,
        "currency": currency,
        "monthly_budget_minor": monthly_budget_minor,
        "persisted_context_sha256": persisted_context_sha256,
        "usage_assumptions": usage_assumptions,
        "sqs_usage_assumptions": sqs_usage_assumptions,
        "rds_usage_assumptions": rds_usage_assumptions,
        "serverless_usage_assumptions": serverless_usage_assumptions,
        "dynamodb_usage_assumptions": dynamodb_usage_assumptions,
        "vpc_usage_assumptions": vpc_usage_assumptions,
        "batch_usage_assumptions": batch_usage_assumptions,
        "ecr_usage_assumptions": ecr_usage_assumptions,
    }
    if ecs_express_usage_assumptions is not None:
        payload["ecs_express_usage_assumptions"] = ecs_express_usage_assumptions
    return _canonical_digest(payload)
