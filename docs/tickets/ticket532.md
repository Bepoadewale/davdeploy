# ticket532 — Preserve explicit workload capabilities in Nova intents

PR: #532
Branch: `feat/nova-explicit-requirements-532`

## Problem / goal

The first hosted Nova intent explicitly requested private file storage,
relational records, and asynchronous queue work, but the accepted structured
intent omitted all three capabilities. The architecture planner then omitted
those required components. Preserve allow-listed requirements stated directly
in the customer request even when Nova under-classifies them.

## Current repo state

- The live hosted plan attempt demonstrated the under-classification in
  `docs/test/test531.md`; no customer workload was applied.
- Current source accepts only Nova-returned capabilities for a successful
  Bedrock response. The deterministic fixture provider already has a
  prompt-to-capability map.

## Research / references used

- `apps/api/src/davdeploy/intent.py` structured Nova proposal and deterministic
  fixture provider.
- `apps/api/src/davdeploy/module_catalogue.py` allow-listed capability names.
- `tests/test_nova_intent.py` provider and provenance contract tests.

## Work planned for the PR

- Reuse the bounded capability vocabulary for explicit customer prompt needs
  on Bedrock responses, unioning it with the model's allow-listed output.
- Recognize object storage/bucket and asynchronous worker language.
- Derive `stateful`, `event_driven`, and `multi_service` from the accepted
  requirements and record a capability-resolution version in provenance.
- Avoid matching capability keywords as arbitrary substrings or adding
  explicitly negated terms.

## Acceptance criteria

- [x] Explicit file-storage, relational-data, and queue-worker requirements
  are retained when the model omits capability fields.
- [x] Simple negative wording does not create an omitted capability.
- [x] Unrecognized model capabilities remain filtered by the existing
  allow-list.
- [x] Focused tests and Ruff pass locally.
- [ ] Required hosted CI passes.

## Acceptance status

- [x] Local focused verification passed.
- [ ] Hosted intent and architecture rerun after merge/deployment.
- [ ] A valid generic saved-plan artifact remains unproven.

## Tests / validation performed

- `uv run --project . pytest -q tests/test_nova_intent.py` — 25 passed.
- `uv run --project . ruff check apps/api/src/davdeploy/intent.py tests/test_nova_intent.py` — passed.
- `git diff --check` — passed.
- Hosted CI pending.

## Evidence files produced

`docs/test/test532.md` records the focused local test results and boundary.

## Boundaries

- Only a fixed allow-listed capability vocabulary is added; generated AWS
  resources remain untrusted and pass through the existing validation path.
- This does not enable unimplemented modules, claim execution support, change
  approval ordering, or apply infrastructure.
- Model-reported material unknowns remain intact.

## Follow-up work

Rerun repository discovery, intent, architecture selection, and the plan-only
Terraform proposal against the verified test connection. Ensure unsupported
families and incomplete pricing are reported honestly; do not approve or apply
until a valid exact saved plan and the remaining gates pass.
