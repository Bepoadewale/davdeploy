# ticket407 — trusted regional pricing for Nova saved plans

PR: draft
Branch: `feat/nova-regional-pricing-evidence`

## Goal

Add deterministic AWS regional price evidence for material resources in a Nova
Terraform plan. Price inputs come from trusted code and AWS pricing data, carry
provenance and timestamps, state usage assumptions, and bind to the exact plan
manifest. Incomplete, stale, ambiguous, unpriced, or policy-critical unknown
costs keep a plan ineligible for approval. Estimates are not a bill or a hard
spending cap.

## Current state

Backend `main` is `a6fff370479657a85949d59a82acee048cb46121` (PR #406), with
all seven merged-main CI jobs passing and the control-plane release evidence
recorded in `docs/test/test406.md`. Nova actual-plan policy and exact saved-plan
plus workspace storage exist. Approval remains blocked because no trusted
regional pricing evaluator is wired. Closed PR #318 added unmerged prototype
code; this PR will review and reuse safe parts only where they fit the current
contracts. The user's resumed goal specifies timestamped regional prices and
usage assumptions.

## Work planned

- Map supported Terraform plan resource types and material cost dimensions to
  explicit trusted price lookups and bounded usage assumptions.
- Resolve current prices from an AWS-published source with region, currency,
  service/SKU, effective/publication time, retrieval time, and provenance.
- Calculate transparent monthly ranges and identify unknown or unsupported
  costs. Avoid claims of completeness when supporting resources or usage are
  not priced.
- Bind canonical price evidence and policy version into the immutable plan
  manifest; recheck freshness and context at approval and apply preflight.
- Keep external pricing access bounded, time-limited, cached with provenance,
  and replaceable by deterministic fixtures in tests. Never let Nova provide
  or override prices.
- Add focused tests and update implementation/readiness evidence truthfully.

## Acceptance criteria

- [ ] Prices are bound to the planned AWS region and use trusted source data.
- [ ] Every material planned resource is priced or explicitly marked unknown;
  critical unknowns block approval.
- [ ] Monthly ranges expose units, usage assumptions, supporting costs,
  currency, timestamps, source and limitations.
- [ ] Evidence is canonical, digest-bound to the immutable manifest, and
  freshness is checked at approval.
- [ ] Negative cases cover stale, mismatched, ambiguous, tampered, unpriced,
  and policy-critical unknown cost evidence.
- [ ] Focused tests, full verification, documentation conventions and required
  CI pass; no AWS workload resources are created or changed.

## Evidence and boundaries

This PR will use price response fixtures and injected clients. Any live price
catalog request will be read-only and must not require customer workload
permissions. No plan is applied and no spending or billing claim is made.
`docs/test/test407.md` will record runtime validation when implementation
begins.

## Follow-up

After pricing is verified, continue the separate exact-plan apply dispatcher,
customer-role permission verification, hosted application lifecycle, and
observed health/recovery/destroy acceptance. Do not enable hosted execution or
claim customer deployment readiness from pricing code or CI alone.
