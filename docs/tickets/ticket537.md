# ticket537 — Constrain Nova Terraform resource names in the generation prompt

PR: #537
Branch: `fix/nova-resource-name-pattern-537`

## Problem / goal

The deployed bounded-diagnostics change exposed why hosted plan run
`0b1e4807-7532-45df-ad99-8edde41a82f4` failed. The accepted revision was
retried once. Nova returned eight schema feedback items across two attempts;
each pointed to `resources[*].name` failing the generated contract's pattern.
No proposal or plan artifact was returned.

The contract requires each Terraform local resource name to match
`^[a-z][a-z0-9_]{0,62}$`, while `resource_id` separately permits hyphens. The
prompt did not state these constraints explicitly.

## Current repo state

- Hosted generation follows the versioned contract in
  `terraform_generation.py` and `generated_deployment_contract.py`.
- Bounded repair was exhausted without a valid proposal; diagnostics now expose
  only safe schema codes and canonical field paths.
- The production schema pattern remains authoritative and will not be relaxed.

## Research / references used

- `apps/api/src/davdeploy/terraform_generation.py` trusted generation task and
  current prompt-version metadata.
- `apps/api/src/davdeploy/generated_deployment_contract.py` resource name and
  resource ID field patterns.
- Hosted safe diagnostics for run
  `0b1e4807-7532-45df-ad99-8edde41a82f4` after PR #534 deployment.
- `tests/test_terraform_generation.py`, `tests/test_nova_plan_runs.py`, and
  `tests/test_customer_plan_review.py`.

## Work planned for the PR

- State the exact schema pattern and safe examples in the trusted generation task.
- Explain that Terraform resource names and stable resource IDs have different
  patterns.
- Advance the prompt version to `terraform-nova2-contract-v5` and use that one
  constant in generation requests, usage records, and failure diagnostics.
- Keep validation and bounded repair unchanged; no relaxation of the contract.

## Acceptance criteria

- [x] Prompt guidance explicitly matches the resource name schema and separates
  `name` from `resource_id`.
- [x] Generation requests and hosted diagnostics/usage report prompt v5.
- [ ] Focused generation, plan-run and customer-review tests pass; Ruff and docs
  convention checks pass.
- [ ] Required hosted CI passes.
- [ ] After protected deployment, the same submitted plan-only revision produces
  either a valid inspectable saved plan or a new specific bounded diagnostic.

## Acceptance status

- [x] Prompt constraints and prompt v5 are implemented and locally tested.
- [ ] Required hosted CI passes.
- [ ] Post-deployment hosted retry is complete and produces a valid saved plan.

## Tests / validation performed

- `uv run --project . --extra dev pytest -q tests/test_terraform_generation.py tests/test_nova_plan_runs.py tests/test_customer_plan_review.py` — 97 passed.
- Ruff passed for the five changed Python files.
- `GITHUB_PR_NUMBER=537 uv run --project . python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.

## Evidence files produced

- `docs/test/test537.md`

## Evidence and observed hosted failure

- Protected plan/apply runs `45931805324` / `45932644787` deployed PR #534 commit
  `95ce2aa76cbefedf94b5949866f7d29ecf4cd995`; migrations passed, six control-plane
  Lambdas are active and their package hash matches the exact release object.
- The retry of the submitted synthetic revision was accepted by the hosted API
  and finished `FAILED` / `NOVA_GENERATION_FAILED` with
  `proposal_invalid`, model `us.amazon.nova-2-lite-v1:0`, prompt
  `terraform-nova2-contract-v4`, 2 attempts, 1 repair, 11,169 input tokens,
  3,070 output tokens, and 12,123 ms latency. Estimated cost was unavailable.
- The safe diagnostics contained eight `string_pattern_mismatch` feedback items
  for `resources[*].name`; no raw proposal, prompt, plan, or provider output was
  exposed. No CodeBuild build, plan artifact, or AWS workload was created.

## Boundaries

- This adjusts prompt guidance and observability versioning only. It does not
  alter schema constraints, policy, permissions, approval, apply or destroy.
- Do not approve or apply a generated workload unless its exact saved plan,
  ownership, policy, live regional pricing and safety evidence pass.

## Follow-up work

Deploy the merged prompt-v5 change through the protected control-plane plan and
apply workflow, then retry the exact submitted synthetic revision and record
its safe result.
