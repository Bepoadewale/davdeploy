# ticket542 — Bounded Nova identifier repair feedback

PR: #542
Branch: `fix/nova-id-repair-feedback-542`

## Problem / goal

The hosted Nova plan retry using prompt v6 still failed before CodeBuild because
the model returned invalid resource and health-target identifiers. Its bounded
repair attempt repeated the schema errors. Give Nova a single short identifier
contract and safe, deterministic correction guidance for those known errors.

## Current repo state

- Main is at `33e54879ebdd95a26ef65ff4e80e9d8416339e4c`; prompt v6 is deployed.
- Hosted run `0b1e4807-7532-45df-ad99-8edde41a82f4` failed generation under v6
  after two model attempts and one repair. Safe diagnostics showed three
  `resources[*].resource_id` pattern errors, one resource graph `value_error`,
  two health target pattern errors, and three cost assumption ID pattern errors.
- No CodeBuild build, saved plan, or customer workload was created by that
  attempt. Reported usage was 11,617 input tokens, 4,934 output tokens,
  17,777 ms; estimated cost was unavailable.
- The draft PR starts from the merged v6 release. No AWS workload is authorized
  or required by this PR.

## Research / references used

- Existing v1.1 proposal contract in
  `apps/api/src/davdeploy/generated_deployment_contract.py`.
- Existing bounded validation-feedback sanitization and hosted diagnostics in
  `apps/api/src/davdeploy/terraform_generation.py` and plan-run tests.
- Prior hosted v6 attempt diagnostics, recorded above without model text,
  credentials, or raw proposals.

## Work planned for the PR

- Use a short lowercase resource ID pattern consistently across resources,
  references, cost assumptions, and health assertions.
- Tell Nova to copy IDs exactly and avoid verbose or AWS-type-derived IDs.
- Add only fixed allowlisted guidance for identifier pattern and resource graph
  validation errors; strip all model-supplied guidance and unknown detail.
- Test the canonical feedback, graph feedback, and secret-text exclusion.

## Acceptance criteria

- [x] Identifier fields share `^[a-z][a-z0-9-]{0,23}$`.
- [x] Known identifier and graph errors receive deterministic safe guidance.
- [x] Arbitrary guidance and sensitive diagnostic strings cannot be persisted.
- [x] Focused tests, lint, and documentation convention checks pass locally.
- [x] Required GitHub CI passes on the implementation head.
- [ ] Deploy the merged control-plane change, then make one authenticated hosted
      retry and inspect its safe outcome.

## Acceptance status

Implementation, focused local verification, and required CI are complete on
head `6d8bd80c03c42f4c481f36b883f119791932f90d`. Protected deployment and the
hosted v7 retry remain pending. No valid saved plan or workload is claimed.

## Tests / validation performed

- Hosted v6 retry evidence: see `docs/test/test542.md`.
- `pytest tests/test_terraform_generation.py tests/test_nova_plan_runs.py
  tests/test_customer_plan_review.py -q` — 99 passed.
- Ruff on the changed Python files — passed.
- `python scripts/check_doc_conventions.py` — passed.
- `git diff --check` — passed.
- GitHub Actions run `45947901539` — all seven checks passed for
  `6d8bd80c03c42f4c481f36b883f119791932f90d`.
- Bootstrap run `45947613695` for the initial implementation-only commit failed
  because tests still asserted the old v6 prompt and pre-guidance feedback
  shape. Those assertions and the schema coverage were corrected before the
  passing final implementation head above.

## Evidence files produced

- `docs/test/test542.md` — hosted v6 failure and the v7 retry boundary.
- Safe hosted v7 retry output will be appended here after deployment.

## Boundaries

- No approval or apply of a Nova customer workload.
- No Terraform operation, customer resources, or control-plane infrastructure
  changes are part of this PR's implementation.
- Diagnostics contain only fixed codes, canonical paths, fixed guidance, and
  aggregate model usage; never record raw model output or credentials.
- Preserve unrelated local files and AWS audit evidence.

## Follow-up work

- If v7 still fails schema validation, use the bounded safe diagnostics to
  choose the next correction; do not loosen validation or approve the plan.
- Continue the hosted acceptance path only after an inspectable saved plan is
  produced and independently reviewed under the Nova goal.
