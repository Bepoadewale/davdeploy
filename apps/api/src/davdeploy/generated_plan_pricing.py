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
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, InvalidOperation
from enum import StrEnum
from itertools import pairwise
from typing import Any, ClassVar, Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from davdeploy.domain import S3PricingUsageAssumptions, SqsPricingUsageAssumptions


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
    lines: tuple[PlanCostLine, ...]
    transitions: tuple[PlanTransition, ...]
    findings: tuple[PlanPricingFinding, ...]
    evidence_sha256: str

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
            "evidence_sha256": self.evidence_sha256,
        }

    def as_manifest_document(self) -> dict[str, Any]:
        return {
            "version": 4,
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
            "usage_assumptions", "sqs_usage_assumptions", "lines", "transitions", "findings", "evidence_sha256",
        }
        legacy_fields = expected_fields - {"sqs_usage_assumptions"}
        if (set(document) != expected_fields and set(document) != legacy_fields) or document.get("version") not in {2, 3, 4}:
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
                lines=lines,
                transitions=transitions,
                findings=findings,
                evidence_sha256=document["evidence_sha256"],
            )
        except (KeyError, TypeError, ValueError):
            raise PlanPricingError("pricing evidence fields are invalid") from None
        if document.get("version") == 4 and result.as_manifest_document() != document:
            raise PlanPricingError("pricing evidence is not canonical")
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
        return cls(
            region=region,
            currency="USD",
            monthly_budget_minor=None if budget_dollars is None else budget_dollars * 100,
            persisted_context_sha256=expected_sha256,
            usage_assumptions=usage_assumptions,
            sqs_usage_assumptions=sqs_usage_assumptions,
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
            low_rate_source_url="https://aws.amazon.com/s3/pricing/",
        )

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
        "aws_subnet",
        "aws_route_table",
        "aws_route",
        "aws_route_table_association",
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
    S3 Standard usage, and Standard/FIFO SQS billed request units have bounded
    mappings. Any unsupported resource or price-driving usage dimension
    prevents approval.
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
    for resource in resources:
        address = resource["address"]
        resource_type = resource["type"]
        values = resource["values"]
        if resource_type in ZERO_DIRECT_CHARGE_RESOURCE_TYPES:
            continue
        if resource_type == "aws_s3_bucket":
            s3_buckets.append(resource)
            continue
        if resource_type == "aws_sqs_queue":
            sqs_queues.append(resource)
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
                            # AWS's 100 GB Internet egress allowance is shared
                            # across commercial services and regions. Use it
                            # only for those low estimates; the budget ceiling
                            # assumes no free allowance.
                            if (
                                assumption_name == "monthly_internet_egress_gb"
                                and not region.startswith(("cn-", "us-gov-"))
                            ):
                                low_quantity = max(0, low_quantity - 100)
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
                            free_units = 1_000_000 if not region.startswith(("cn-", "us-gov-")) else 0
                            for is_fifo, amount, description, rate in rates:
                                low_quantity = amount.minimum
                                if free_units:
                                    applied = min(low_quantity, free_units)
                                    low_quantity -= applied
                                    free_units -= applied
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
            if description == "AWS internet data transfer out" and not trusted_context.region.startswith(
                ("cn-", "us-gov-")
            ):
                expected_low_quantity = max(0, expected_low_quantity - 100)
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
                != "https://aws.amazon.com/s3/pricing/"
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
        free_units = 1_000_000 if not trusted_context.region.startswith(("cn-", "us-gov-")) else 0
        for name in ("Amazon SQS FIFO requests", "Amazon SQS Standard requests"):
            if name not in active:
                continue
            usage, address = active[name]
            line = actual[name]
            free_applied = min(usage.minimum, free_units)
            free_units -= free_applied
            if (
                line.get("quantity") != usage.minimum
                or line.get("quantity_max") != usage.maximum
                or line.get("low_cost_quantity") != usage.minimum - free_applied
                or line.get("address") != address
                or line.get("unit") != "Requests"
            ):
                return False
    expected_within_budget = (
        None
        if trusted_context.monthly_budget_minor is None
        else high <= trusted_context.monthly_budget_minor
    )
    return document.get("within_budget") is expected_within_budget


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
    return isinstance(region_expression, dict) and region_expression.get("constant_value") == region


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
        sqs_usage_assumptions,
    )
    payload = {
        "version": 4,
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
        lines=lines,
        transitions=transitions,
        findings=findings,
        evidence_sha256=_canonical_digest(payload),
    )


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _pricing_context_digest(
    region: str,
    currency: str,
    monthly_budget_minor: int | None,
    persisted_context_sha256: str,
    usage_assumptions: dict[str, Any] | None = None,
    sqs_usage_assumptions: dict[str, Any] | None = None,
) -> str:
    return _canonical_digest(
        {
            "version": 3,
            "region": region,
            "currency": currency,
            "monthly_budget_minor": monthly_budget_minor,
            "persisted_context_sha256": persisted_context_sha256,
            "usage_assumptions": usage_assumptions,
            "sqs_usage_assumptions": sqs_usage_assumptions,
        }
    )
