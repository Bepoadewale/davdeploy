# ticket414 — price bounded DynamoDB on-demand plans

PR: #414 https://github.com/Bepoadewale/davdeploy/pull/414
Branch: `feat/nova-dynamodb-plan-pricing-414`

## Problem / goal

A generated Terraform plan containing `aws_dynamodb_table` currently receives
`resource_pricing_unavailable`, even when the table is a dependency of the
serverless application path. Add a deterministic, region-specific estimate for
a deliberately small supported configuration. Every other table configuration
or unmodeled material cost must continue to block approval.

## Current repo state

- Backend `main` is `de873ef9e22a96ec38aa4650741b42ff73f053f1` (PR #413 merged).
- Pricing currently supports selected EBS, S3, SQS, RDS MySQL, ZIP Lambda,
  HTTP API, CloudWatch Standard logs, and modeled egress.
- DynamoDB remains unpriced. The existing customer workload table uses
  `PAY_PER_REQUEST` and enables point-in-time recovery (PITR).
- Open draft PR #399 contains a separate exact-plan apply boundary. Its
  executable Terraform worker and credential-broker path are incomplete.
- No Nova customer plan or workload has been applied or certified.

## Research / references used

- [Amazon DynamoDB pricing](https://aws.amazon.com/dynamodb/pricing/)
- [DynamoDB on-demand capacity mode](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/on-demand-capacity-mode.html)
- [DynamoDB read and write operations](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/read-write-operations.html)
- [AWS Price List GetProducts API](https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_pricing_GetProducts.html)

DynamoDB bills on-demand reads and writes in request units; item size and
consistency/transaction mode affect consumed units. Storage and PITR backup
storage have separate regional prices. The proposal therefore accepts billed
unit quantities and storage ranges as trusted, revision-bound assumptions; it
does not infer application traffic or use model-authored prices.

## Work planned for the PR

- Add strict bounded usage assumptions keyed by exact planned table address:
  monthly billed read request units, write request units, table storage, and
  PITR storage where PITR is enabled.
- Persist the assumptions through the workload/revision constraint contract,
  trusted pricing context, manifest digest, and approval eligibility.
- Price only a single-region, Standard-class `PAY_PER_REQUEST` table without
  global secondary indexes, replicas, streams, customer-managed KMS keys, or
  other unsupported charge-driving features.
- Require PITR storage bounds to match table storage bounds because AWS bills
  PITR from the size of the PITR-enabled table.
- Match exact current regional AWS Price List products for request units,
  storage, and PITR. Ignore free allowances and use the highest published
  applicable unit price for the conservative upper estimate.
- Keep missing assumptions, unsupported settings, unknown plan values, missing
  or ambiguous catalog results, and unpriced resources approval-blocking.
- Add focused tests for exact matching, bounds, cost math, digest binding,
  unsupported features, missing assumptions, and malformed/ambiguous prices.

## Acceptance criteria

- [x] Strict, price-free monthly assumptions validate and bind to each exact
      Terraform table address.
- [x] Supported on-demand Standard tables are priced with exact regional
      request, storage, and enabled-PITR catalog evidence.
- [x] Monthly low/high totals use conservative price tiers and cent rounding;
      no Free Tier, discount, or credit is assumed.
- [x] Missing, stale, mismatched, unknown, or unsupported pricing evidence
      prevents approval.
- [x] Existing pricing evidence remains readable and is correctly versioned.
- [ ] Focused tests, full verification, documentation checks, and required
      hosted CI pass. Local tests and full verification pass; documentation
      checks and hosted CI remain pending.
- [ ] No hosted runtime flags, Terraform deployment, customer workload, or
      Nova apply path is enabled by this PR.

## Evidence files produced

- `docs/tickets/ticket414.md`
- `docs/test/test414.md`

## Acceptance status

The bounded assumptions, regional product matching, conservative cost math,
approval blockers, evidence-version compatibility, focused tests, and full
local verification are complete. Final documentation checks and required
GitHub CI are the remaining gates before review.

## Tests / validation performed

- Focused DynamoDB/SQS/usage tests — 31 passed.
- Generated-plan pricing plus DynamoDB/SQS/usage tests — 121 passed.
- `make verify` — passed: 1,253 tests, Ruff, Actions configuration, OpenAPI
  snapshot, and Compose configuration; one existing dependency deprecation
  warning.
- `python3 scripts/check_doc_conventions.py` and `git diff --check` — passed.
- Required GitHub CI — pending.

## Boundaries

This PR does not price provisioned-capacity tables, Standard-IA, GSIs, global
tables/replicas, streams, exports, on-demand backups, customer-managed KMS
charges, cross-region transfer, or arbitrary DynamoDB settings. It does not
enable hosted planning or apply, claim complete cost coverage, or certify a
customer workload. Any unsupported material resource continues to block
approval.

## Follow-up work

After the bounded cost model is reviewed and merged, continue toward an
authenticated hosted customer plan journey and comprehensive cost coverage.
Only then continue the separately gated exact-plan apply and lifecycle proof.

## Status ledger

- Status: draft; implementation and local verification complete, documentation
  and hosted CI pending.
- Source: branch `feat/nova-dynamodb-plan-pricing-414` from PR #413 merge `de873ef9e22a96ec38aa4650741b42ff73f053f1`.
- Implementation commit: `da41107` (`feat: price bounded DynamoDB on-demand plans`).
- Deployed version: none.
- Current operation: complete the evidence and docs checks, push the reviewed
  source to this draft PR, and wait for required GitHub checks.
- Customer workload execution: none.
- Local verification: focused pricing suites passed (121 tests); `make verify`
  passed (1,253 tests, Ruff, Actions configuration, OpenAPI snapshot and Compose
  configuration; one existing Starlette/httpx deprecation warning).
