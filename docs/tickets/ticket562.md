# ticket562 — give Nova safe feedback for malformed resource objects

PR: pending

Branch: `fix/nova-resource-shape-feedback-562`

## Problem / goal

After PR #561 was merged and deployed, the fresh v23 hosted plan-only run
failed before CodeBuild with ten safe `missing` or `extra_forbidden`
diagnostics collapsed to `resources[*]`. The diagnostics do not reveal which
resource-object fields need repair. Add fixed shape guidance for these root
resource-object errors while preserving schema rejection and not echoing
untrusted field names or proposal data.

## Current repo state

- Backend `main`: `17df898510290134e0ef1770f51506d81474bb64` (PR #561 merged).
- Protected release apply run `46081012438` succeeded after applying saved
  plan `46080412351`. Migration, Lambda hash, API health, and workspace-admin
  checks passed.
- Hosted v23 run `40c14f88-5a49-4df7-9fd0-199e6454b98a` failed with no
  artifact after two attempts and one repair. Final safe feedback contains
  only `missing`/`extra_forbidden` at `resources[*]`.
- Review revision `0005b2f5-71b7-4efd-8b7e-70f2664a4e16` remains submitted
  with no approval decision. No customer workload plan, approval, apply, or
  destroy is claimed.

## Research / references used

- `generated_deployment_contract.py` defines the strict resource fields and
  generated proposal schema.
- `terraform_generation.py` canonicalizes validator paths, strips raw input,
  and allowlists fixed repair guidance for bounded Nova retries.
- `docs/test/test561.md` and private `DAVDEPLOY_NOVA_GOAL_STATUS.md` preserve
  hosted v22/v23 results.

## Work planned for the PR

1. For root `resources[*]` missing-field errors, give fixed guidance naming
   the contract-required `resource_id`, `resource_type`, `name`, `arguments`,
   and `rationale` fields, plus the only optional resource keys.
2. For root `resources[*]` extra-field errors, tell Nova to remove wrapper or
   undeclared keys and place provider resource arguments under `arguments`.
3. Keep the schema validator unchanged and suppress the untrusted extra key,
   input, resource ID, and values in feedback.
4. Add safe path/guidance and bounded-repair tests; bump the prompt version and
   record exact evidence.
5. Pass focused/full and clean-room checks, review/merge via PR, perform the
   exact protected release workflow, then make one fresh v24 review-only run.

## Acceptance criteria

- [ ] `missing` and `extra_forbidden` root-resource errors receive distinct
  fixed, actionable guidance.
- [ ] Feedback reveals no raw unknown key, input value, resource ID, or
  rationale.
- [ ] Strict schema rejection remains unchanged; malformed and executable
  payloads are still rejected before any credentialed runner.
- [ ] Focused/full tests, docs conventions, and required clean-room proof pass.
- [ ] PR review and all required current-head CI checks pass.
- [ ] One fresh v24 run reaches an inspectable plan or a precise next blocker;
  no customer workload approval/apply/destroy occurs.

## Acceptance status

In progress. Ticket created before substantive code changes. Implementation
and validation are pending.

## Tests / validation performed

Pending.

## Evidence files produced

Pending.

## Boundaries

Do not relax the generated deployment contract, expose raw proposal/plan/state
data or secrets, change execution roles, or claim customer deployment or
lifecycle evidence.

## Follow-up work

Use the next hosted result to address the earliest remaining contract,
pricing, plan-policy, state, or lifecycle blocker. Keep the workload unapproved
and unapplied.

