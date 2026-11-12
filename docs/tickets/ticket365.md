# ticket365 — reject literal credentials in Nova proposal arguments

PR: [#365](https://github.com/Bepoadewale/davdeploy/pull/365) (draft)
Branch: `security/nova-secret-reference-contract`

## Problem / goal

Nova-generated Terraform arguments must not carry literal credentials or secret values. Safe secret integration must use typed, controlled references; the customer plan runner must never receive a model-authored secret value.

## Current repo state

The generated deployment contract rejects a short list of exact argument keys and Terraform expressions. Provider-schema validation rejects literals for provider attributes marked sensitive and validates output sensitivity, but the generic proposal contract does not consistently reject common credential-field variants or enforce typed references for secret-named fields. The customer Nova execution path remains gated.

## Research / references used

- Goal handoff: secret material must be resolved through controlled references and never model text.
- Existing module-port contracts accept secret-reference values and never read secret contents.
- `generated_provider_validation.py` checks provider-declared sensitive arguments and generated output metadata against the pinned provider schema.

## Work planned for the PR

- Harden the proposal contract against common credential and secret literal field names, including nested and case/separator variants.
- Permit secret-named arguments only when they contain a typed `resource_reference` declared as `secret_reference`.
- Add regression tests for denied literals, accepted typed references, and ordinary values.
- Preserve existing plan-only and feature-gate boundaries; this PR does not enable a customer secret lookup or Nova apply path.

## Acceptance criteria

- Obvious credential or secret literals fail at contract validation before Terraform configuration is generated.
- Typed references declared as `secret_reference` remain representable without embedding secret material.
- Existing provider-schema sensitivity checks remain authoritative for other sensitive fields.
- No secret value is added to logs, model feedback, plans shown to customers, or evidence.

## Acceptance status

- Implemented and locally verified. Hosted Nova execution remains gated; end-to-end secret lookup is follow-up work.

## Tests / validation performed

- `uv run pytest tests/test_generated_deployment_contract.py -q`: 18 passed.
- `make verify`: 1,004 tests passed; lint, OpenAPI snapshot and Docker Compose configuration checks passed.
- `COMPOSE_PROJECT_NAME=davdeploy_nova_secret365 make local-proof`: passed, including API contract, customer-plan E2E, traces and the full verification suite.
- `git diff --check` and `python3 scripts/check_doc_conventions.py`: passed.

## Evidence files produced

- [`docs/test/test365.md`](../test/test365.md)

## Boundaries

- No credentials are fetched or printed.
- No customer AWS plan/apply or feature-gate change is included.
- This change does not claim end-to-end customer secret provisioning is complete.

## Follow-up work

- Integrate trusted, tenant-scoped secret references and safe runtime resolution in the hosted plan/apply lifecycle. Ensure provider data access never exposes secret values to Nova and approval binds the exact reference and saved plan.
