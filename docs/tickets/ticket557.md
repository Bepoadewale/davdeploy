# ticket557 — allow relational database round-trip health targets

PR: [#557](https://github.com/Bepoadewale/davdeploy/pull/557) (draft)

Branch: `fix/nova-rds-health-target-557`

## Problem / goal

Allow the typed Nova proposal contract to bind a `database_roundtrip` health
assertion to a supported relational database resource, and tell Nova the exact
target compatibility rules. Preserve deterministic rejection for incompatible
targets and keep plan-only execution boundaries unchanged.

## Current repo state

- Backend main: `a63453c2096196659c5d16bc136ed5df03bf768b` (PR #556 merged).
- Hosted run `96533832-bea0-47f5-89db-b006d9a3b8ed` failed before CodeBuild with
  sanitized `incompatible_health_target` feedback. No artifact or Terraform
  plan was created; no customer workload was applied.
- The contract currently permits `database_roundtrip` only for
  `aws_dynamodb_table`, while this first hosted scenario requires a relational
  database and the proposal has a managed RDS secret reference.
- RDS proposal policy, plan-role read profile, and bounded Aurora pricing exist
  in source. Runtime relational database behavior and a generic hosted lifecycle
  remain unproven.

## Research / references used

- `apps/api/src/davdeploy/generated_deployment_contract.py` — authoritative
  assertion target compatibility map and proposal validator.
- `apps/api/src/davdeploy/terraform_generation.py` — generation prompt,
  canonical safe feedback, and bounded repair loop.
- `docs/product/NOVA_CAPABILITY_EVIDENCE_MATRIX.md` — RDS policy/pricing
  evidence remains source-only; live SQL behavior is not proven.

## Work planned for the PR

1. Extend the authoritative health-target compatibility map for
   `aws_db_instance` and `aws_rds_cluster`.
2. Use that same map to give Nova exact target-type guidance in generation and
   bounded repair feedback; version the generation prompt.
3. Add contract and generator regression tests proving RDS is accepted for
   database round-trip, unsupported targets remain rejected, and Nova can
   correct an incompatible target within its existing repair bound.
4. Keep actual database observation and all workload execution gates honest;
   this PR is a contract/generation fix, not runtime health or lifecycle proof.

## Acceptance criteria

- [x] `database_roundtrip` accepts `aws_db_instance` and `aws_rds_cluster`.
- [x] Other assertion kinds and incompatible target/resource pairs remain
  rejected.
- [x] The prompt and safe repair feedback use the same exact compatibility
  mapping as deterministic validation.
- [x] A malformed health target gets a canonical target field path and bounded
  repair keeps the database round-trip assertion bound to the RDS resource.
- [x] No health assertion is treated as executed evidence; policy and no-apply
  boundaries remain unchanged.
- [x] Focused tests (114), full `make verify` (2,084), Ruff, OpenAPI snapshot,
  Actions configuration, Compose, documentation conventions, and diff checks
  pass locally.
- [ ] Required full clean-room cycle, review, and PR CI pass.
- [ ] Fresh deployed plan-only run advances to an inspectable saved plan or a
  new precise blocker without approval or apply.

## Acceptance status

Implementation and local verification are complete. Focused contract/generation
tests pass (114); full `make verify` passes (2,084 tests), and Ruff, OpenAPI
snapshot, Actions configuration, Compose, documentation conventions, and diff
checks pass. The required clean-room cycle, PR CI, protected release, and fresh
hosted plan-only attempt remain pending.

## Tests / validation performed

Focused contract and generation tests: 114 passed. Final-head `make verify`
passed 2,084 tests, Ruff, Actions configuration, OpenAPI snapshot, and Compose
checks, with one existing Starlette deprecation warning. Documentation
conventions and `git diff --check` passed. The first full verification run found
two stale v18 expectations; both were updated to v19 before the passing run.
The clean-room cycle and PR CI remain pending.

## Evidence files produced

- `docs/tickets/ticket557.md`
- `docs/test/test557.md`

## Boundaries

No customer approval, apply, or destroy. Do not claim database behavior from a
typed proposal or saved plan. Add and prove an isolated deterministic SQL probe
before claiming relational read/write health. Preserve protected untracked local
files and all existing test/audit evidence.

## Follow-up work

Implement and independently verify the bounded SQL round-trip observer before
claiming actual relational database behavior; complete the first hosted
plan-only evidence and then address any new precise blocker.
