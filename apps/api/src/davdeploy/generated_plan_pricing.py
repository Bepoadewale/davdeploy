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
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, ClassVar, Protocol

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from davdeploy.domain import S3PricingUsageAssumptions


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
            "evidence_sha256": self.evidence_sha256,
        }

    def as_manifest_document(self) -> dict[str, Any]:
        return {
            "version": 2,
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
            "usage_assumptions", "lines", "transitions", "findings", "evidence_sha256",
        }
        if set(document) != expected_fields or document.get("version") != 2:
            raise PlanPricingError("pricing evidence shape is invalid")
        try:
            usage_assumptions = document["usage_assumptions"]
            if usage_assumptions is not None:
                usage_assumptions = S3PricingUsageAssumptions.model_validate(
                    usage_assumptions
                ).model_dump(mode="json")
                if usage_assumptions != document["usage_assumptions"]:
                    raise ValueError("non-canonical usage assumptions")
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
                lines=lines,
                transitions=transitions,
                findings=findings,
                evidence_sha256=document["evidence_sha256"],
            )
        except (KeyError, TypeError, ValueError):
            raise PlanPricingError("pricing evidence fields are invalid") from None
        if result.as_manifest_document() != document:
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

    @property
    def pricing_context_sha256(self) -> str:
        """Digest all trusted price constraints and their persisted source together."""
        return _pricing_context_digest(
            self.region,
            self.currency,
            self.monthly_budget_minor,
            self.persisted_context_sha256,
            self.usage_assumptions,
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
        return cls(
            region=region,
            currency="USD",
            monthly_budget_minor=None if budget_dollars is None else budget_dollars * 100,
            persisted_context_sha256=expected_sha256,
            usage_assumptions=usage_assumptions,
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

    Nova-authored price, SKU, and usage text is not read here. Only gp3 EBS
    storage has a billable mapping in this initial version. Any unsupported
    resource or usage dimension prevents approval.
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
        )

    resources = _planned_managed_resources(document)
    changes = _changes_by_address(document)
    transitions, transition_findings = _classify_aws_transitions(resources, changes)
    pricing_catalog = catalog or AwsPriceListCatalog()
    lines: list[PlanCostLine] = []
    findings: list[PlanPricingFinding] = list(transition_findings)
    unavailable = False
    for resource in resources:
        address = resource["address"]
        resource_type = resource["type"]
        values = resource["values"]
        if resource_type in ZERO_DIRECT_CHARGE_RESOURCE_TYPES:
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

    total_minor = sum(item.monthly_cost_minor for item in lines)
    within_budget = None if monthly_budget_minor is None else total_minor <= monthly_budget_minor
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
    for line in lines:
        if not isinstance(line, dict):
            return False
        amount = line.get("monthly_cost_minor")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            return False
        line_total += amount
    # This version's supported mappings have exact quantities and rates, so
    # the evidence must present one exact total rather than an invented range.
    if low != high or high != line_total:
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
) -> GeneratedPlanPricingEvidence:
    lines = tuple(sorted(lines, key=lambda item: item.address))
    transitions = tuple(sorted(transitions, key=lambda item: (item.address, item.actions)))
    findings = tuple(sorted(findings, key=lambda item: (item.code, item.address or "")))
    low = high = sum(item.monthly_cost_minor for item in lines)
    if status != PlanPricingStatus.COMPLETE:
        low = high = None
    if budget is not None and status == PlanPricingStatus.COMPLETE and within_budget is None:
        within_budget = high is not None and high <= budget
    plan_digest = _canonical_digest(document) if isinstance(document, (dict, list)) else "0" * 64
    pricing_context_digest = _pricing_context_digest(
        region, currency, budget, persisted_context_sha256, usage_assumptions
    )
    payload = {
        "version": 2,
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
) -> str:
    return _canonical_digest(
        {
            "version": 2,
            "region": region,
            "currency": currency,
            "monthly_budget_minor": monthly_budget_minor,
            "persisted_context_sha256": persisted_context_sha256,
            "usage_assumptions": usage_assumptions,
        }
    )
