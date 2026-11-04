# ticket315 Fail closed on unknown security-critical Terraform settings

PR: #315 https://github.com/Bepoadewale/davdeploy/pull/315 (draft)
Branch: feat/nova-plan-unknown-gates-v2

## Problem / goal

Terraform plan JSON has an `after_unknown` tree. A resource's current planned
values can look safe while Terraform still reports that an important input
setting is unknown until apply. The actual-plan policy must not present those
settings as verified.

## Current repo state

PR #312 evaluates common security risks in an actual generated Terraform plan,
but its policy checks interpreted planned values without examining Terraform's
parallel `after_unknown` metadata. PR #314 adds durable encrypted plan storage
and administrator review approval; it does not yet connect the plan runner to
the hosted worker. Customer apply remains disabled for this Nova path.

## Research / references used

- Terraform plan JSON format: https://developer.hashicorp.com/terraform/internals/json-format
- Terraform provider schema command: https://developer.hashicorp.com/terraform/cli/commands/providers/schema

## Scope

This change adds a bounded unknown-value check for security and retention
settings already examined by the Nova generated-plan policy, including S3
public-access flags and unknown S3 encryption-algorithm values (this does not
validate whether a known algorithm is allowed), and IAM policy/trust documents,
database exposure/encryption/deletion behavior, EBS encryption, KMS key
settings, and DynamoDB encryption/deletion protection. Existing network checks
are unchanged. Computed identifiers and referenced key IDs do not block this
new check by themselves; another policy check may still reject a plan if it
cannot verify how a reference is used. Unknown fields outside this explicit
policy-critical set remain outside this PR's coverage.

This is one hardening step. It does not complete policy coverage, enforce
resource ownership tags, add live pricing/quota checks, or enable hosted apply.

## Work planned for the PR

Inspect Terraform's `after_unknown` metadata for attributes tied to existing
security and data-retention checks. Deny plans when those values are unknown or
the unknown metadata is malformed, while allowing unknown computed identifiers.
Bump the policy version and add focused tests and test evidence.

## Acceptance criteria

- [x] Unknown policy-critical values in Terraform `after_unknown` produce a
  stable deny finding without exposing raw plan values.
- [x] Missing or malformed `after_unknown` metadata for monitored resource
  types fails closed.
- [x] Unknown computed identifiers outside the critical fields remain eligible
  for human review.
- [x] Policy version changes when its evaluation semantics change.
- [x] `make verify` and documentation convention checks pass.
- [x] Independent read-only review found no remaining blocker.
- [ ] Required GitHub CI passes.

## Acceptance status

Implementation, local verification, and independent review are complete.
Required GitHub CI is pending.

## Tests / validation performed

- Focused policy tests: `tests/test_generated_plan_policy.py` — 47 passed.
- Ruff passed for the modified policy and test files.
- `make verify`: 599 passed, plus Ruff, Actions configuration, OpenAPI snapshot,
  and Compose configuration checks passed.
- `python3 scripts/check_doc_conventions.py` and `git diff --check` passed.

## Evidence files produced

Local test commands and scope are recorded in `docs/test/test315.md`.

## Boundaries and follow-up

This PR only evaluates saved Terraform plans. It does not persist plans, invoke
Nova, apply or destroy infrastructure. Follow-up work must cover resource
ownership evidence, trusted regional pricing and budgets, quota checks, and
the hosted plan/apply lifecycle. Existing AWS service-level tests are not
proof of a Nova-generated hosted customer deployment.

## Follow-up work

Resolve safe typed references in policy checks, enforce ownership evidence and
current approval binding, add trustworthy region-specific pricing and usage
assumptions, and check quotas or clearly label them unknown. Then connect the
plan-only runner to the hosted worker.
