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

- Backend `main` is `373b82a7011a54b046820f7990065bcfc017beac` (PR #414 merged).
- Pricing currently supports selected EBS, S3, SQS, RDS MySQL, ZIP Lambda,
  HTTP API, CloudWatch Standard logs, and modeled egress.
- Merged PR #414 prices a bounded DynamoDB `PAY_PER_REQUEST` Standard table
  with point-in-time recovery (PITR); unsupported configurations remain
  approval-blocking. The pricing source is not deployed.
- Open draft PR #399 at `8dbd08976940e1747e28be4a9fcbfe53d68b6844` contains a
  separate exact-plan apply boundary. Its executable Terraform worker and
  credential-broker path are incomplete.
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
- [x] Focused tests, full verification, documentation checks, and required
      hosted CI pass. All seven required jobs passed in run `43773735458` on
      the code revision, run `43774188730` on evidence head `2118185`, and run
      `43774616215` on final PR head `880fe6b`.
- [x] No hosted runtime flags, Terraform deployment, customer workload, or
      Nova apply path is enabled by this PR.

## Evidence files produced

- `docs/tickets/ticket414.md`
- `docs/test/test414.md`

## Acceptance status

The bounded assumptions, regional product matching, conservative cost math,
approval blockers, evidence-version compatibility, focused tests, full local
verification, documentation checks, and all seven hosted CI jobs are complete.
PR #414 merged as `373b82a7011a54b046820f7990065bcfc017beac`; it is not
deployed and establishes no customer execution evidence.

## Tests / validation performed

- Focused DynamoDB/SQS/usage tests — 31 passed.
- Generated-plan pricing plus DynamoDB/SQS/usage tests — 121 passed.
- `make verify` — passed: 1,253 tests, Ruff, Actions configuration, OpenAPI
  snapshot, and Compose configuration; one existing dependency deprecation
  warning.
- `python3 scripts/check_doc_conventions.py` and `git diff --check` — passed.
- Required GitHub CI — all seven jobs passed on code head `c09313d` in
  [run 43773735458](https://github.com/Bepoadewale/davdeploy/actions/runs/43773735458)
  and on evidence head `2118185` in
  [run 43774188730](https://github.com/Bepoadewale/davdeploy/actions/runs/43774188730).
  All seven jobs also passed on final PR head `880fe6b` in
  [run 43774616215](https://github.com/Bepoadewale/davdeploy/actions/runs/43774616215).

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

- Status: merged and CI verified.
- Source: branch `feat/nova-dynamodb-plan-pricing-414` from PR #413 merge `de873ef9e22a96ec38aa4650741b42ff73f053f1`.
- Implementation commits: `da41107` (`feat: price bounded DynamoDB on-demand plans`) and `fdd05ff` (`fix: bind PITR pricing to table storage bounds`).
- Deployed version: none.
- PR: #414 merged as `373b82a7011a54b046820f7990065bcfc017beac` after all seven
  required checks passed.
- Current operation: add lifecycle regression coverage for the new pricing
  assumption field in PR #415, then continue toward the authenticated customer
  plan journey and comprehensive cost evidence.
- Customer workload execution: none.
- Local verification: focused pricing suites passed (121 tests); `make verify`
  passed (1,253 tests, Ruff, Actions configuration, OpenAPI snapshot and Compose
  configuration; one existing Starlette/httpx deprecation warning).
