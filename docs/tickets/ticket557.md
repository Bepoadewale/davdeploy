# ticket557 — allow relational database round-trip health targets

PR: draft not opened yet  
Branch: `fix/nova-rds-health-target-557`

## Goal

Allow the typed Nova proposal contract to bind a `database_roundtrip` health
assertion to a supported relational database resource, and tell Nova the exact
target compatibility rules. Preserve deterministic rejection for incompatible
targets and keep plan-only execution boundaries unchanged.

## Current evidence

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

## Work

1. Extend the authoritative health-target compatibility map for
   `aws_db_instance` and `aws_rds_cluster`.
2. Use that same map to give Nova exact target-type guidance in generation and
   bounded repair feedback; version the generation prompt.
3. Add contract and generator regression tests proving RDS is accepted for
   database round-trip, unsupported targets remain rejected, and Nova can
   correct an incompatible target within its existing repair bound.
4. Keep actual database observation and all workload execution gates honest;
   this PR is a contract/generation fix, not runtime health or lifecycle proof.

## Acceptance

- [ ] `database_roundtrip` accepts `aws_db_instance` and `aws_rds_cluster`.
- [ ] Other assertion kinds and incompatible target/resource pairs remain
  rejected.
- [ ] The prompt and safe repair feedback use the same exact compatibility
  mapping as deterministic validation.
- [ ] No health assertion is treated as executed evidence; policy and no-apply
  boundaries remain unchanged.
- [ ] Focused tests, full verification, documentation conventions, clean-room
  cycle, review, and required PR CI pass.
- [ ] Fresh deployed plan-only run advances to an inspectable saved plan or a
  new precise blocker without approval or apply.

## Validation and evidence

Pending. Per-run hosted evidence will be recorded in `docs/test/test557.md`.

## Boundaries and follow-up

No customer approval, apply, or destroy. Do not claim database behavior from a
typed proposal or saved plan. Add and prove an isolated deterministic SQL probe
before claiming relational read/write health. Preserve protected untracked local
files and all existing test/audit evidence.
