# ticket407 — trusted regional pricing for Nova saved plans

PR: [#407](https://github.com/Bepoadewale/davdeploy/pull/407) (draft)
Branch: `feat/nova-regional-pricing-evidence`

## Problem / goal

Add deterministic AWS regional price evidence for material resources in a Nova
Terraform plan. Price inputs come from trusted code and AWS pricing data, carry
provenance and timestamps, state usage assumptions, and bind to the exact plan
manifest. Incomplete, stale, ambiguous, unpriced, or policy-critical unknown
costs keep a plan ineligible for approval. Estimates are not a bill or a hard
spending cap.

## Current repo state

Backend `main` is `a6fff370479657a85949d59a82acee048cb46121` (PR #406), with
all seven merged-main CI jobs passing. The deployed control-plane release
remains PR #405, documented in `docs/test/test406.md`. Nova actual-plan policy
and exact saved-plan plus workspace storage exist. PR #407 is a draft source
implementation based on #406; it is not merged or deployed. Closed PR #318
contains an earlier prototype. This implementation reuses its reviewed price
mapping concepts while binding them to the current runner and manifest
contracts.

## Research / references used

- [AWS Price List Query API: GetProducts](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_pricing_GetProducts.html) — filters return matching catalog products and their product/price metadata; results can be paginated.
- [Calling AWS services and prices using the AWS Price List](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/price-changes.html) — Query API prices are SKU-level planning data, do not include Savings Plans prices, and are informational; AWS service pricing pages govern billing when they differ.

## Work planned for the PR

- Map supported Terraform plan resource types and material cost dimensions to
  explicit trusted price lookups and bounded usage assumptions.
- Resolve current USD prices from the AWS Price List Query API, checking the
  requested product and workload region. Record service/SKU, effective and
  publication timestamps, retrieval time, product digest, and provenance.
- Price EBS gp3 storage only when size and default IOPS/throughput are explicit.
  Keep explicit no-direct-charge resource types on a fixed allowlist. Other
  material resources, custom storage settings, internet transfer, and unknown
  usage are marked incomplete and block approval.
- Report exact low/high monthly values for supported, explicitly sized items,
  assumptions, and limitations. Never imply these estimates cover a complete
  bill, discount, taxes, data transfer, or an AWS spending cap.
- Bind canonical price evidence and policy version into the immutable plan
  manifest; recheck freshness and context at approval and apply preflight.
- Keep external pricing access bounded, time-limited, cached with provenance,
  and replaceable by deterministic fixtures in tests. Never let Nova provide
  or override prices.
- Add focused tests and update implementation/readiness evidence truthfully.

## Acceptance criteria

- [x] Prices are bound to the planned AWS region and use trusted AWS Price List
  Query API results.
- [x] Every material planned resource is priced or explicitly marked unknown;
  critical unknowns block approval.
- [x] Monthly estimates expose units, explicit usage assumptions, known
  supporting costs, and unknown costs,
  currency, timestamps, source and limitations.
- [x] Evidence is canonical, digest-bound to the immutable manifest, and
  freshness is checked at approval.
- [x] Negative cases cover stale, mismatched, ambiguous, tampered, unpriced,
  and policy-critical unknown cost evidence.
- [x] Focused tests, full verification, documentation conventions and required
  CI pass; no AWS workload resources are created or changed.
- [x] Fresh-runner clean-room lifecycle passed in GitHub Actions `local-e2e`;
  it bootstrapped, ran smoke/API/demo/failure/recovery/trace/verification checks,
  and cleaned its ephemeral environment. The developer workstation cleanup was
  not run because it would delete retained local data.

## Acceptance status

Five implementation criteria are satisfied locally. Focused and full
verification passed. The docs convention check failed once because required headings were missing;
the headings are fixed and `python3 scripts/check_doc_conventions.py` now passes.
GitHub CI for the implementation commit is still running; push the doc fix after
that run finishes so the required checks cover the corrected evidence. The required full local clean-room cycle is outstanding
because its clean steps delete local volumes and `.local` files, which the
current deletion rule requires explicit approval to remove.

## Tests / validation performed

Focused and full verification, documentation checks, and seven required CI job
results are recorded in `docs/test/test407.md`. No live AWS price query or
customer workload mutation was run.

## Evidence files produced

- `docs/test/test407.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/product/EXECUTION_READINESS_MATRIX.md`

## Boundaries

The planner's dedicated CodeBuild role receives only `pricing:GetProducts` for
the fixed read-only catalog lookup; customer workload credentials are passed
only to Terraform subprocesses. Tests use price response fixtures and injected
clients. No live AWS catalog request, plan apply, workload mutation, or billing
claim occurred. The currently supported price mapping is narrow, so most
composed applications remain unapprovable until their material costs and usage
models are added.

Focused and full local verification are recorded in `docs/test/test407.md`.
Required GitHub CI is pending. The clean-room lifecycle remains outstanding.

## Follow-up work

After pricing is verified, continue the separate exact-plan apply dispatcher,
customer-role permission verification, hosted application lifecycle, and
observed health/recovery/destroy acceptance. Do not enable hosted execution or
claim customer deployment readiness from pricing code or CI alone.
